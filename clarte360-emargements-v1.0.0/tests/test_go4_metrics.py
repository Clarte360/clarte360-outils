"""CDC R09–R12/R16, synthetic SQLite only, controlled clock and no email transport."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from db import execute, init_db, make_engine, one, q, utcnow_iso
from services import (create_action, create_crm_contact, create_questionnaire_template,
                      create_quality_campaign, save_quality_response, ensure_default_organization)
from client_portal import (client_action_summary, client_public_schedule, client_quality_satisfaction,
                          create_client_portal_account, export_client_quality_csv, grant_client_action,
                          revoke_client_action, set_client_account_active)
from quality_service import QualityActor
import quality_metrics as qm

ADMIN = 'qualite-go4@example.invalid'


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = make_engine('sqlite:///' + str(tmp_path / 'go4_metrics.sqlite'))
    init_db(engine)
    with engine.begin() as conn:
        qm.init_metrics_schema(conn)
    oid = ensure_default_organization(engine, 'Organisme fictif GO4')
    execute(engine, """INSERT INTO admins(email,password_hash,role,active,created_at)
        VALUES(:e,'hash-fictif','ADMIN',1,:n)""", {'e': ADMIN, 'n': utcnow_iso()})
    anchor = datetime.now(timezone.utc).replace(microsecond=0)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return anchor.astimezone(tz) if tz else anchor.replace(tzinfo=None)

    monkeypatch.setattr(qm, 'datetime', FrozenDatetime)
    return {'engine': engine, 'org': oid, 'actor': QualityActor('ADMIN', ADMIN, oid), 'now': anchor}


def action(env, label=None, nature='FORMATION', organization_id=None):
    engine = env['engine']
    label = label or f"TEST-GO4-{one(engine, 'SELECT COUNT(*) n FROM actions')['n'] + 1}"
    aid = create_action(engine, {'action_no': label, 'title': 'Formation fictive ' + label,
        'subtitle': None, 'nature': nature, 'mode': 'INDIVIDUEL', 'client_name': 'Entreprise fictive',
        'client_type': 'ENTREPRISE', 'group_code': None, 'planned_hours': 7, 'expected_participants': 1,
        'admin_email': ADMIN, 'trainer_name': None, 'trainer_email': None, 'location': None,
        'notes': None, 'source': 'TEST'}, ADMIN)
    execute(engine, """UPDATE actions SET organization_id=:o,prestation_type=:p,start_date=:s,end_date=:e
        WHERE id=:a""", {'o': organization_id or env['org'], 'p': nature,
        's': (env['now'] - timedelta(days=5)).date().isoformat(),
        'e': (env['now'] - timedelta(days=3)).date().isoformat(), 'a': aid})
    return aid


def person(env, aid, *, beneficiary_id=None, stable=True):
    engine = env['engine']
    serial = one(engine, 'SELECT COUNT(*) n FROM participants')['n'] + 1
    email = f'personne-{serial}@example.invalid'
    if stable and beneficiary_id is None:
        beneficiary_id = execute(engine, """INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,current_email,
            active,created_at,updated_at) VALUES(:p,'Fictif','Personne','1990-01-01',:e,1,:n,:n)""",
            {'p': 'GO4-' + str(serial), 'e': email, 'n': utcnow_iso()})
    pid = execute(engine, """INSERT INTO participants(action_id,beneficiary_id,last_name,first_name,email,active,created_at)
        VALUES(:a,:b,'Fictif','Personne',:e,1,:n)""", {'a': aid, 'b': beneficiary_id, 'e': email, 'n': utcnow_iso()})
    return pid, beneficiary_id


def template(env, *, kind='HOT', version='1.0', global_item=True, extra_global=False, theme_text='Préparation'):
    engine = env['engine']
    items = [
        {'question_code': 'THEME-A', 'rubric_code': 'R01', 'response_type': 'SCALE_1_5', 'question_text': 'Information', 'required': 0},
        {'question_code': 'THEME-B', 'rubric_code': 'R01', 'response_type': 'SCALE_1_5', 'question_text': theme_text, 'required': 0},
    ]
    if global_item:
        items.append({'question_code': 'GLOBAL', 'rubric_code': 'R10', 'response_type': 'SCALE_1_5', 'question_text': 'Satisfaction globale', 'required': 0})
    if extra_global:
        items.append({'question_code': 'OTHER-GLOBAL', 'rubric_code': 'R10', 'response_type': 'SCALE_1_5', 'question_text': 'Autre globale ambiguë', 'required': 0})
    items.extend([
        {'question_code': 'NPS', 'rubric_code': 'R11', 'response_type': 'NPS_0_10', 'question_text': 'Recommandation', 'required': 0},
        {'question_code': 'COMMENT', 'rubric_code': 'R12', 'response_type': 'TEXT_LONG', 'question_text': 'Commentaire privé', 'required': 0},
    ])
    return create_questionnaire_template(engine, env['org'],
        'TEST-GO4-' + str(one(engine, 'SELECT COUNT(*) n FROM questionnaire_templates')['n']),
        version, 'FORMATION', kind, 'Questionnaire fictif', items, ADMIN)


def invitation(env, aid, tid, *, kind='HOT', score=5, theme=(1, 1), nps=10,
               participant_id=None, completed=True, sent=True, future=False, classification='REAL', raw_score=None):
    engine = env['engine']
    if participant_id is None:
        participant_id, _ = person(env, aid)
    due = env['now'] + (timedelta(days=5) if future else -timedelta(days=2))
    cid, _ = create_quality_campaign(engine, aid, tid, kind, due.isoformat(), participant_id=participant_id, actor=ADMIN)
    qm._snapshot_campaign(engine, cid)
    if classification != 'REAL':
        qm.classify_campaign(engine, env['actor'], cid, classification)
    for question in qm.campaign_questions(engine, cid):
        answer = {'THEME-A': theme[0], 'THEME-B': theme[1], 'GLOBAL': score,
                  'OTHER-GLOBAL': score, 'NPS': nps, 'COMMENT': 'Ne doit jamais être communiqué au client.'}[question['question_code']]
        save_quality_response(engine, cid, question['id'], answer, ADMIN)
        if raw_score is not None and question['question_code'] == 'GLOBAL':
            execute(engine, 'UPDATE quality_responses SET answer_json=:v WHERE campaign_id=:c AND question_id=:q',
                    {'v': raw_score, 'c': cid, 'q': question['id']})
    execute(engine, """UPDATE quality_campaigns SET status=:s,completed_at=:d,sent_at=:sent WHERE id=:c""",
            {'s': 'COMPLETED' if completed else 'PENDING',
             'd': (env['now'] - timedelta(hours=1)).isoformat() if completed else None,
             'sent': (env['now'] - timedelta(days=1)).isoformat() if sent else None, 'c': cid})
    return cid


def blank_invitation(env, aid, tid, *, sent=True, future=False):
    cid = invitation(env, aid, tid, completed=False, sent=sent, future=future)
    execute(env['engine'], 'DELETE FROM quality_responses WHERE campaign_id=:c', {'c': cid})
    return cid


def client(env, aid, stem='contact'):
    engine = env['engine']
    crm = create_crm_contact(engine, 'Contact', 'Fictif', f'{stem}@example.invalid', company='Entreprise fictive')['id']
    cid = create_client_portal_account(engine, crm, ADMIN)
    execute(engine, "UPDATE client_portal_accounts SET password_hash='hash-fictif' WHERE id=:c", {'c': cid})
    grant_client_action(engine, cid, aid, ADMIN)
    return cid


def ready_for_publication(env, aid):
    execute(env['engine'], "UPDATE actions SET status='CLOTUREE' WHERE id=:a", {'a': aid})
    qm.configure_metric_policy(env['engine'], env['actor'], positive_min=4, min_distinct=5,
                               client_enabled=True, confirmed=True)


def test_metrics_schema_is_additive_repeatable_and_does_not_activate_a_policy(env):
    aid = action(env); tid = template(env)
    cid = invitation(env, aid, tid)
    before = one(env['engine'], 'SELECT * FROM quality_campaign_contracts WHERE campaign_id=:c', {'c': cid})
    init_db(env['engine'])
    assert one(env['engine'], 'SELECT * FROM quality_campaign_contracts WHERE campaign_id=:c', {'c': cid}) == before
    assert not qm.metric_policy(env['engine'], env['actor'])['client_enabled']
    assert one(env['engine'], 'SELECT COUNT(*) n FROM quality_metric_policies')['n'] == 0


def test_r09_global_425_satisfaction75_return80_from_actual_sent_cohort(env):
    aid = action(env); tid = template(env)
    for score in (5, 4, 3, 5):
        invitation(env, aid, tid, score=score, theme=(1, 1))
    blank_invitation(env, aid, tid)
    bucket = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']
    assert (bucket['score'], bucket['satisfaction_rate'], bucket['return_rate']) == (4.25, 75, 80)
    assert (bucket['n_global'], bucket['completed'], bucket['sent'], bucket['distinct_respondents']) == (4, 4, 5, 4)


def test_future_unsent_invitation_is_planned_not_a_return_denominator(env):
    aid = action(env); tid = template(env)
    invitation(env, aid, tid, score=4)
    blank_invitation(env, aid, tid, sent=False, future=True)
    bucket = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']
    assert bucket['planned'] == 1 and bucket['invitations'] == 2
    assert bucket['sent'] == 1 and bucket['return_rate'] == 100 and bucket['score'] == 4


def test_drafts_test_and_invalid_global_do_not_inflate_global_average(env):
    aid = action(env); tid = template(env)
    invitation(env, aid, tid, score=5)
    invitation(env, aid, tid, score=1, completed=False)
    invitation(env, aid, tid, score=1, classification='TEST')
    invitation(env, aid, tid, raw_score='10')
    view = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)
    bucket = view['by_kind']['HOT']
    assert bucket['score'] == 5 and bucket['n_global'] == 1 and bucket['drafts'] == 1
    assert bucket['invitations'] == 3
    assert any('OUT_OF_RANGE_ANSWER' in message for message in view['anomalies'])


@pytest.mark.parametrize('raw', ['true', '"5"', '1.5', '-1', '0', '6', 'NaN', 'Infinity', '{bad json'])
def test_invalid_numeric_global_is_an_anomaly_not_clamped(env, raw):
    aid = action(env); tid = template(env)
    invitation(env, aid, tid, raw_score=raw)
    view = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)
    assert view['by_kind']['HOT']['score'] is None
    assert view['by_kind']['HOT']['satisfaction_rate'] is None
    assert view['anomalies']


@pytest.mark.parametrize('score', [None, '', 'N/A'])
def test_empty_and_na_mean_absent_data_not_zero(env, score):
    aid = action(env); tid = template(env)
    invitation(env, aid, tid, score=score)
    bucket = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']
    assert bucket['completed'] == 1 and bucket['n_global'] == 0
    assert bucket['score'] is None and bucket['satisfaction_rate'] is None


@pytest.mark.parametrize('has_global,ambiguous', [(False, False), (True, True)])
def test_missing_or_ambiguous_global_never_uses_other_items(env, has_global, ambiguous):
    aid = action(env); tid = template(env, global_item=has_global, extra_global=ambiguous)
    invitation(env, aid, tid, theme=(5, 5))
    view = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)
    assert view['by_kind']['HOT']['score'] is None
    assert any('GLOBAL_QUESTION' in warning for warning in view['anomalies'])


def test_themes_average_individual_means_with_comparable_items(env):
    aid = action(env); tid = template(env)
    invitation(env, aid, tid, theme=(5, 'N/A'))
    invitation(env, aid, tid, theme=(1, 1))
    themes = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['themes']
    assert len(themes) == 1
    assert (themes[0]['mean'], themes[0]['questionnaires'], themes[0]['items']) == (3, 2, 3)


def test_changed_item_set_remains_separate_with_version_visible(env):
    aid = action(env)
    invitation(env, aid, template(env), theme=(1, 1))
    invitation(env, aid, template(env, version='2.0', theme_text='Autre question'), theme=(5, 5))
    themes = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['themes']
    assert len(themes) == 2 and {row['template_version'] for row in themes} == {'1.0', '2.0'}
    assert {row['mean'] for row in themes} == {1, 5}


def test_hot_cold_trainer_client_prescriber_opco_are_separate(env):
    aid = action(env)
    for kind, value in zip(qm.KINDS, (5, 4, 3, 2, 1, 5)):
        invitation(env, aid, template(env, kind=kind), kind=kind, score=value)
    by_kind = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']
    assert [by_kind[kind]['score'] for kind in qm.KINDS] == [5, 4, 3, 2, 1, 5]
    assert all(by_kind[kind]['n_global'] == 1 for kind in qm.KINDS)


def test_nps_ten_is_not_a_score_on_five(env):
    aid = action(env); tid = template(env)
    for nps in (10, 9, 6, 7):
        invitation(env, aid, tid, score=3, nps=nps)
    bucket = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']
    assert bucket['score'] == 3 and bucket['nps'] == 25 and bucket['n_nps'] == 4


def test_only_successful_initial_receipt_proves_sent_when_campaign_marker_absent(env):
    aid = action(env); tid = template(env)
    good = invitation(env, aid, tid, sent=False)
    bad = blank_invitation(env, aid, tid, sent=False)
    for cid, status in ((good, 'SENT'), (bad, 'FAILED')):
        execute(env['engine'], """INSERT INTO quality_email_events(campaign_id,event_type,due_at,sent_at,status,created_at)
            VALUES(:c,'INITIAL',:n,:n,:s,:n)""", {'c': cid, 's': status, 'n': (env['now'] - timedelta(days=1)).isoformat()})
    bucket = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']
    assert bucket['sent'] == 1 and bucket['return_rate'] == 100


def test_completed_without_send_evidence_is_reported_separately_not_above100(env):
    aid = action(env); tid = template(env)
    invitation(env, aid, tid, sent=False)
    bucket = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']
    assert bucket['completed'] == 1 and bucket['sent'] == 0 and bucket['return_rate'] is None
    assert any('WITHOUT_SENT_EVIDENCE' in warning for warning in bucket['anomalies'])


def test_cancelled_invitation_does_not_lower_active_return_rate(env):
    aid = action(env); tid = template(env)
    invitation(env, aid, tid)
    cancelled = blank_invitation(env, aid, tid)
    execute(env['engine'], "UPDATE quality_campaigns SET status='CANCELLED' WHERE id=:c", {'c': cancelled})
    bucket = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']
    assert bucket['cancelled'] == 1 and bucket['sent'] == 1 and bucket['return_rate'] == 100


def test_r11_template_edits_do_not_change_campaign_questions_or_global_semantics(env):
    aid = action(env); tid = template(env)
    cid = invitation(env, aid, tid, score=4)
    original = qm.campaign_questions(env['engine'], cid)
    global_id = next(row['id'] for row in original if row['question_code'] == 'GLOBAL')
    execute(env['engine'], """UPDATE questionnaire_questions SET rubric_code='R01',response_type='NPS_0_10',
        question_text='Texte ultérieur différent' WHERE id=:q""", {'q': global_id})
    assert qm.campaign_questions(env['engine'], cid) == original
    assert qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']['score'] == 4
    from services import quality_questions
    assert next(row for row in quality_questions(env['engine'], cid) if row['id'] == global_id)['response_type'] == 'SCALE_1_5'
    with pytest.raises(ValueError, match='nouvelle version'):
        qm.configure_template_measure(env['engine'], env['actor'], tid, original[0]['id'])


def test_answer_snapshot_mismatch_is_rejected_from_v1_measure(env):
    aid = action(env); tid = template(env); cid = invitation(env, aid, tid)
    execute(env['engine'], "UPDATE quality_responses SET question_text_snapshot='Version incompatible' WHERE campaign_id=:c AND rubric_code='R10'", {'c': cid})
    view = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)
    assert view['by_kind']['HOT']['score'] is None
    assert any('ANSWER_SNAPSHOT_MISMATCH' in warning for warning in view['anomalies'])


def test_historical_campaign_is_unclassified_until_explicit_adoption(env):
    aid = action(env); tid = template(env)
    cid = invitation(env, aid, tid, score=3)
    # Model the pre-GO4 state, before the additive contract table existed.
    execute(env['engine'], 'DELETE FROM quality_campaign_contracts WHERE campaign_id=:c', {'c': cid})
    execute(env['engine'], "UPDATE questionnaire_questions SET response_type='NPS_0_10',question_text='Nouveau texte' WHERE template_id=:t AND rubric_code='R10'", {'t': tid})
    assert qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']['invitations'] == 0
    qm.classify_campaign(env['engine'], env['actor'], cid, 'REAL')
    view = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)
    assert view['by_kind']['HOT']['score'] == 3
    assert view['campaigns'][0]['template_version'] == 'HISTORIQUE_NON_ATTESTEE'
    assert any('LEGACY_TEMPLATE_VERSION_UNVERIFIED' in warning for warning in view['anomalies'])
    assert one(env['engine'], 'SELECT snapshot_origin FROM quality_campaign_contracts WHERE campaign_id=:c', {'c': cid})['snapshot_origin'] == 'LEGACY_RESPONSE_SNAPSHOTS'


def test_same_person_two_formations_is_two_questionnaires_one_distinct_person(env):
    a1, a2 = action(env), action(env)
    p1, bid = person(env, a1); p2, _ = person(env, a2, beneficiary_id=bid)
    tid = template(env)
    invitation(env, a1, tid, participant_id=p1)
    invitation(env, a2, tid, participant_id=p2)
    view = qm.survey_dashboard(env['engine'], env['actor'])
    assert view['by_kind']['HOT']['n_global'] == 2
    assert view['by_kind']['HOT']['distinct_respondents'] == view['distinct_respondents'] == 1


def test_missing_person_reference_never_counts_as_one_publishable_person(env):
    aid = action(env); pid, _ = person(env, aid, stable=False)
    invitation(env, aid, template(env), participant_id=pid)
    bucket = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)['by_kind']['HOT']
    assert bucket['n_global'] == 1 and bucket['distinct_respondents'] == 0 and bucket['unknown_respondents'] == 1


def test_r12_export_uses_same_family_action_dates_and_classification_without_private_data(env):
    aid, other = action(env), action(env)
    tid = template(env)
    invitation(env, aid, tid, score=4)
    invitation(env, aid, tid, score=1, classification='TEST')
    invitation(env, other, tid, score=1)
    invitation(env, aid, template(env, kind='COLD'), kind='COLD', score=2)
    filters = {'action_id': aid, 'campaign_kinds': ('HOT',),
               'date_from': (env['now'] - timedelta(days=3)).date().isoformat(),
               'date_to': env['now'].date().isoformat()}
    view = qm.survey_dashboard(env['engine'], env['actor'], **filters)
    exported = qm.export_survey_csv(env['engine'], env['actor'], **filters).decode('utf-8-sig')
    assert view['by_kind']['HOT']['n_global'] == 1 and view['by_kind']['HOT']['score'] == 4
    assert 'HOT;4.0;100.0;1;1;1;1;1;100.0;' in exported
    assert view['generated_at'] in exported and qm.METHOD_VERSION in exported
    assert 'REAL' in exported and filters['date_from'] in exported
    assert 'Ne doit jamais' not in exported and '@example.invalid' not in exported and 'token' not in exported
    assert '\nCOLD;' not in exported


def test_admin_auth_and_organization_scope_are_checked_for_dashboard_and_export(env):
    aid = action(env)
    other_org = execute(env['engine'], "INSERT INTO organizations(name,legal_name,created_at,updated_at) VALUES('Autre','Autre',:n,:n)", {'n': utcnow_iso()})
    other_action = action(env, organization_id=other_org)
    for method in (qm.survey_dashboard, qm.export_survey_csv):
        with pytest.raises(PermissionError):
            method(env['engine'], env['actor'], action_id=other_action)
        with pytest.raises(PermissionError):
            method(env['engine'], QualityActor('TRAINER', 9999, env['org']), action_id=aid)
    execute(env['engine'], 'UPDATE admins SET active=0 WHERE email=:e', {'e': ADMIN})
    with pytest.raises(PermissionError):
        qm.survey_dashboard(env['engine'], env['actor'])


def add_slot(env, aid, status='PREVU'):
    return execute(env['engine'], """INSERT INTO slots(action_id,slot_date,start_time,end_time,status,created_at,updated_at)
        VALUES(:a,:d,'09:00','12:00',:s,:n,:n)""", {'a': aid, 'd': (env['now'] + timedelta(days=2)).date().isoformat(),
        's': status, 'n': utcnow_iso()})


def test_r16_one_person_training_calendar_is_visible_but_satisfaction_is_hidden(env):
    aid = action(env); person(env, aid); add_slot(env, aid); add_slot(env, aid, 'REPORTE')
    account = client(env, aid)
    summary = client_action_summary(env['engine'], account, aid)
    assert summary['calendar_visible'] and not summary['collective_training'] and 'participants_count' not in summary
    schedule = client_public_schedule(env['engine'], account, aid)
    assert len(schedule) == 1 and set(schedule[0]) == {'slot_date', 'start_time', 'end_time', 'status'}
    satisfaction = client_quality_satisfaction(env['engine'], account, aid)
    assert satisfaction['status'] != 'AVAILABLE' and 'score' not in satisfaction
    from portal_dashboard import client_dashboard
    assert len(client_dashboard(env['engine'], account)['collective_sessions']) == 1


def test_bc_calendar_and_individual_aggregate_remain_protected(env):
    aid = action(env, nature='BILAN_COMPETENCES'); person(env, aid); add_slot(env, aid)
    account = client(env, aid)
    assert client_public_schedule(env['engine'], account, aid) == []
    assert client_quality_satisfaction(env['engine'], account, aid)['status'] == 'PROTECTED'
    ready_for_publication(env, aid)
    with pytest.raises(PermissionError):
        qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)


def test_calendar_grant_revocation_and_account_inactivity_apply_immediately(env):
    aid = action(env); add_slot(env, aid); account = client(env, aid)
    assert client_public_schedule(env['engine'], account, aid)
    revoke_client_action(env['engine'], account, aid, ADMIN)
    with pytest.raises(PermissionError):
        client_public_schedule(env['engine'], account, aid)
    grant_client_action(env['engine'], account, aid, ADMIN)
    set_client_account_active(env['engine'], account, False, ADMIN)
    with pytest.raises(PermissionError):
        client_public_schedule(env['engine'], account, aid)


def test_no_client_publication_without_confirmed_policy_and_closed_formation(env):
    aid = action(env); tid = template(env)
    for _ in range(5):
        invitation(env, aid, tid)
    with pytest.raises(ValueError, match='Clôturer'):
        qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)
    execute(env['engine'], "UPDATE actions SET status='CLOTUREE' WHERE id=:a", {'a': aid})
    with pytest.raises(ValueError, match='confirmées'):
        qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)
    with pytest.raises(ValueError, match='Confirmer'):
        qm.configure_metric_policy(env['engine'], env['actor'], client_enabled=True)


def test_client_fixed_publication_and_export_contain_only_authorized_aggregate(env):
    aid = action(env); tid = template(env)
    for score in (5, 4, 3, 5, 3):
        invitation(env, aid, tid, score=score)
    account = client(env, aid); ready_for_publication(env, aid)
    published = qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)
    result = client_quality_satisfaction(env['engine'], account, aid)
    assert result == published and result['score'] == 4 and result['satisfaction_rate'] == 60
    assert result['distinct_respondents'] == 5 and result['n_global'] == 5
    serialized = json.dumps(result, ensure_ascii=False)
    assert 'Ne doit jamais' not in serialized and '@example.invalid' not in serialized
    assert not {'campaigns', 'responses', 'questions', 'themes', 'token', 'beneficiary_id', 'participant_id'}.intersection(result)
    exported = export_client_quality_csv(env['engine'], account, aid).decode('utf-8-sig')
    assert published['published_at'] in exported and qm.METHOD_VERSION in exported
    with pytest.raises(TypeError):
        client_quality_satisfaction(env['engine'], account, aid, date_from='2020-01-01')


def test_client_nps_has_its_own_confidentiality_threshold(env):
    aid = action(env); tid = template(env)
    for index in range(5):
        invitation(env, aid, tid, nps=10 if index == 0 else None)
    account = client(env, aid); ready_for_publication(env, aid)
    qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)
    result = client_quality_satisfaction(env['engine'], account, aid)
    assert result['score'] == 5 and result['n_global'] == 5
    assert result['nps'] is None and result['n_nps'] is None and result['nps_status'] == 'PROTECTED'


def test_changing_campaign_family_does_not_reclassify_an_old_answer_silently(env):
    aid = action(env); tid = template(env); cid = invitation(env, aid, tid)
    execute(env['engine'], "UPDATE quality_campaigns SET campaign_kind='COLD' WHERE id=:c", {'c': cid})
    view = qm.survey_dashboard(env['engine'], env['actor'], action_id=aid)
    assert view['by_kind']['COLD']['score'] is None
    assert any('CAMPAIGN_SCOPE_CHANGED' in warning for warning in view['anomalies'])


def test_five_questionnaires_from_one_person_cannot_pass_distinct_threshold(env):
    aid = action(env); pid, _ = person(env, aid)
    for _ in range(5):
        invitation(env, aid, template(env), participant_id=pid)
    ready_for_publication(env, aid)
    with pytest.raises(ValueError, match='effectif distinct'):
        qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)


def test_small_complement_suppressed_even_with_five_valid_responders(env):
    aid = action(env); tid = template(env)
    for _ in range(5):
        invitation(env, aid, tid)
    blank_invitation(env, aid, tid)
    ready_for_publication(env, aid)
    with pytest.raises(ValueError, match='groupe complémentaire'):
        qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)


def test_uninvited_roster_member_also_protects_small_complement(env):
    aid = action(env); tid = template(env)
    for _ in range(5):
        invitation(env, aid, tid)
    person(env, aid)
    ready_for_publication(env, aid)
    with pytest.raises(ValueError, match='groupe complémentaire'):
        qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)


def test_complement_of_five_is_allowed_without_exposing_nonresponders(env):
    aid = action(env); tid = template(env)
    for _ in range(5):
        invitation(env, aid, tid)
        blank_invitation(env, aid, tid)
    ready_for_publication(env, aid)
    result = qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)
    assert result['return_rate'] == 50 and result['n_global'] == 5


def test_publication_retry_is_idempotent_but_changed_second_release_is_blocked(env):
    aid = action(env); tid = template(env)
    for _ in range(5):
        invitation(env, aid, tid)
    account = client(env, aid); ready_for_publication(env, aid)
    first = qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)
    assert qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True) == first
    invitation(env, aid, tid, score=1)
    with pytest.raises(ValueError, match='déduire une réponse'):
        qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)
    assert client_quality_satisfaction(env['engine'], account, aid) == first
    assert one(env['engine'], 'SELECT COUNT(*) n FROM quality_client_publications')['n'] == 1


def test_publication_revoke_and_grant_revoke_remove_read_and_export_access(env):
    aid = action(env); tid = template(env)
    for _ in range(5):
        invitation(env, aid, tid)
    account = client(env, aid); ready_for_publication(env, aid)
    qm.publish_client_satisfaction(env['engine'], env['actor'], aid, confirmed=True)
    qm.revoke_client_satisfaction(env['engine'], env['actor'], aid)
    assert client_quality_satisfaction(env['engine'], account, aid)['status'] == 'NOT_PUBLISHED'
    with pytest.raises(PermissionError):
        export_client_quality_csv(env['engine'], account, aid)
    revoke_client_action(env['engine'], account, aid, ADMIN)
    with pytest.raises(PermissionError):
        client_quality_satisfaction(env['engine'], account, aid)


def test_dashboard_request_count_is_canonical_and_does_not_share_same_company_contacts(env):
    from quality_service import create_action as create_quality_action
    from portal_dashboard import client_dashboard
    aid = action(env)
    contact_a, contact_b = client(env, aid, 'premier'), client(env, aid, 'deuxieme')
    for cid, secret in ((contact_a, 'Secret du premier'), (contact_b, 'Secret du deuxième')):
        create_quality_action(env['engine'], QualityActor('CLIENT', cid, env['org']), secret,
            action_id=aid, origin='DEMANDE_CLIENT', command_id=f'demande-{cid}')
    dashboard = client_dashboard(env['engine'], contact_a)
    assert dashboard['quality_request_count'] == 1
    assert 'Secret du deuxième' not in json.dumps(dashboard, ensure_ascii=False)
