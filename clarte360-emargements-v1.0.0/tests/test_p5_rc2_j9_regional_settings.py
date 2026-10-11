"""J9 — regional parameters: UTC evidence stays untouched, display is localized."""
from datetime import datetime, timezone
from pathlib import Path
import re
import pytest
from sqlalchemy import text
from db import make_engine, init_db, one, execute, utcnow_iso
from services import ensure_default_organization, save_regional_preferences, get_regional_preferences, organization_runtime_config
from regional_settings import (
    DEFAULTS, date_input_format, format_date, format_timestamp, format_wall_time,
    parse_utc_timestamp, preferences_from_org, validate_preferences,
)


@pytest.fixture
def env(tmp_path):
    engine=make_engine('sqlite:///'+str(tmp_path/'j9-fictif.db'))
    init_db(engine)
    oid=ensure_default_organization(engine)
    return engine,oid


def test_default_fr_24h_and_spring_summer(env):
    e,oid=env
    p=get_regional_preferences(e)
    assert p==DEFAULTS
    assert format_timestamp('2026-10-10T11:02:00Z',p)=='10/10/2026 13:02'
    assert format_timestamp('2026-01-10T11:02:00+00:00',p)=='10/01/2026 12:02'
    assert format_timestamp('2026-10-10T11:02:00',p)=='10/10/2026 13:02'  # old naive UTC
    assert date_input_format(p)=='DD/MM/YYYY'


def test_dst_spring_transition_from_utc_no_fake_wall_time(env):
    e,oid=env;p=get_regional_preferences(e)
    assert format_timestamp('2026-03-29T00:30:00Z',p)=='29/03/2026 01:30'
    assert format_timestamp('2026-03-29T01:30:00Z',p)=='29/03/2026 03:30'
    # There is no 02:30 local time at the start of daylight saving.


def test_dst_fall_two_distinct_instants_share_local_hour(env):
    p={'timezone':'Europe/Paris','display_date_format':'FR','display_time_format':'24H','display_language':'fr'}
    first=parse_utc_timestamp('2026-10-25T00:30:00Z');second=parse_utc_timestamp('2026-10-25T01:30:00Z')
    assert first != second
    assert format_timestamp(first,p)==format_timestamp(second,p)=='25/10/2026 02:30'
    # Underlying evidence is UTC and retains its offset, not rewritten into ambiguous local time.


def test_date_only_and_planning_walltime_not_shifted():
    p={'timezone':'America/New_York','display_date_format':'US','display_time_format':'12H','display_language':'en'}
    assert format_date('2026-10-10',p)=='10/10/2026'
    assert format_wall_time('14:30',p)=='02:30 PM'
    assert format_timestamp('2026-10-10T11:02:00+00:00',p)=='10/10/2026 07:02 AM'
    assert date_input_format(p)=='MM/DD/YYYY'
    assert format_date('2026-03-01T01:02:30Z',p)=='03/01/2026'  # date-only does not TZ-convert


def test_all_format_choices_and_empty():
    p={'timezone':'UTC','display_date_format':'ISO','display_time_format':'24H','display_language':'fr'}
    assert format_date('2026-10-10',p)=='2026-10-10'
    assert format_timestamp('2026-10-10T11:02:00Z',p)=='2026-10-10 11:02'
    assert date_input_format(p)=='YYYY-MM-DD'
    assert format_timestamp(None,p)=='—'
    assert format_date('',p)=='—'
    assert format_wall_time('not-a-time',p)=='—'
    assert format_timestamp('nonsense',p)=='—'


@pytest.mark.parametrize('bad', ['Mars/Paris','../etc','', 'A'*110])
def test_reject_bad_timezone(bad):
    with pytest.raises(ValueError,match='Fuseau'):
        validate_preferences(timezone_name=bad)


@pytest.mark.parametrize('fmt,tim,lang',[('XX','24H','fr'),('FR','unknown','fr'),('FR','24H','zz')])
def test_reject_bad_format(fmt,tim,lang):
    with pytest.raises(ValueError):
        validate_preferences(date_format=fmt,time_format=tim,language=lang)


def test_persist_and_reinit_twice_preserves_preferences(env):
    e,oid=env
    old=one(e,'SELECT created_at,updated_at FROM organizations WHERE id=:id',{'id':oid})
    saved=save_regional_preferences(e,oid,timezone_name='Europe/Budapest',date_format='ISO',time_format='12H',language='en',actor='j9-admin')
    assert saved['timezone']=='Europe/Budapest'
    assert get_regional_preferences(e)==saved
    init_db(e);init_db(e)
    assert get_regional_preferences(e)==saved
    assert one(e,'SELECT created_at FROM organizations WHERE id=:id',{'id':oid})['created_at']==old['created_at']
    assert one(e,"SELECT COUNT(*) n FROM audit_log WHERE event_type='REGIONAL_SETTINGS_CHANGED'")['n']==1


def test_invalid_save_leaves_old_values_and_no_audit(env):
    e,oid=env;before=get_regional_preferences(e)
    with pytest.raises(ValueError):save_regional_preferences(e,oid,timezone_name='Europe/Invalid',date_format='FR',time_format='24H',language='fr',actor='j9')
    assert get_regional_preferences(e)==before
    assert one(e,"SELECT COUNT(*) n FROM audit_log WHERE event_type='REGIONAL_SETTINGS_CHANGED'")['n']==0


def test_action_organization_overrides_global_choice(env):
    e,oid=env
    from services import create_action
    other=execute(e,"INSERT INTO organizations(name,timezone,display_date_format,display_time_format,display_language,created_at,updated_at) VALUES('TEST B','America/New_York','US','12H','en',:d,:d)",{'d':utcnow_iso()})
    payload=dict(action_no='J9-TEST',title='Action fictive',subtitle='',nature='FORMATION',mode='INTRA',delivery_mode='PRESENTIEL',client_name='Fictif',client_type='Entreprise',group_code=None,planned_hours=1,expected_participants=1,admin_email='j9@example.org',trainer_name=None,trainer_email=None,location=None,notes=None,source='TEST')
    aid=create_action(e,payload,'j9-test')
    execute(e,'UPDATE actions SET organization_id=:org WHERE id=:a',{'org':other,'a':aid})
    assert get_regional_preferences(e,aid)['timezone']=='America/New_York'
    assert get_regional_preferences(e)['timezone']=='Europe/Paris'
    assert format_timestamp('2026-10-10T11:02:00Z',get_regional_preferences(e,aid))=='10/10/2026 07:02 AM'


def test_display_is_not_storage_or_attendance_mutation(env):
    e,oid=env
    stored=utcnow_iso()
    before=stored
    format_timestamp(stored,get_regional_preferences(e))
    assert stored==before
    p=Path(__file__).resolve().parents[1]/'app.py'
    source=p.read_text(encoding='utf-8')
    assert 'save_regional_preferences(ENGINE' in source
    assert 'format_app_datetime' in source
    assert "TZ=DISPLAY_PREFERENCES['timezone']" in source
    assert 'format=app_date_input_format()' in source
    assert 'strftime(\'%H:%M\')' in source  # backend scheduling still uses local wall clock


def test_readonly_display_preferences_migrated_for_existing_org(env):
    e,oid=env
    cols={x['name'] for x in e.connect().exec_driver_sql('PRAGMA table_info(organizations)').mappings()}
    assert {'display_date_format','display_time_format','display_language'}.issubset(cols)
    with e.connect() as cn:
        assert cn.execute(text('SELECT timezone,display_date_format,display_time_format,display_language FROM organizations WHERE id=:id'),{'id':oid}).mappings().first()['display_date_format']=='FR'


def test_ui_all_portals_get_regional_display_no_raw_timestamp_slicing():
    src=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
    assert "st.subheader('Paramètres régionaux et horaires')" in src
    assert "st.selectbox('Fuseau horaire de référence'" in src
    assert 'format_app_datetime(notice[' in src
    assert "'Date':format_app_datetime(m['created_at'])" in src
    assert "'Date':format_app_datetime(r['created_at'])" in src
    assert 'format_app_deadline' in src
    assert 'format_app_date(x[\'slot_date\'])' in src
    assert 'c3.metric(\'Modalité\'' not in src
    assert "c3.write(delivery_mode_label" in src


def test_association_dashboard_uses_organization_timezone():
    src=(Path(__file__).resolve().parents[1]/'portal_dashboard.py').read_text(encoding='utf-8')
    assert "get_regional_preferences(engine)['timezone']" in src
    assert "datetime.now(ZoneInfo('Europe/Paris'))" not in src


def test_timezone_preview_does_not_save_configuration(env):
    e,oid=env
    before=one(e,'SELECT * FROM organizations WHERE id=:i',{'i':oid})
    for i in range(3):
        preferences_from_org(before)
        format_timestamp('2026-10-10T11:02:00Z',before)
    after=one(e,'SELECT * FROM organizations WHERE id=:i',{'i':oid})
    assert before==after
