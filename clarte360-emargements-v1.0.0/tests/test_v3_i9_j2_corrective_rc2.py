from pathlib import Path
from db import make_engine, init_db, execute, one
from services import ensure_default_organization, create_action, create_trainer_report, create_beneficiary_report


def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); ensure_default_organization(e); return e


def action(e):
    return create_action(e,dict(action_no='RC2',title='Correctif',subtitle=None,nature='Formation',mode='INDIVIDUEL',client_name=None,client_type='Particulier',group_code=None,planned_hours=1,expected_participants=1,admin_email='a@x.fr',trainer_name=None,trainer_email=None,location=None,notes=None,source='TEST'),'test')


def test_beneficiary_report_always_feeds_quality_even_if_caller_passes_false():
    e=eng(); aid=action(e)
    bid=execute(e,"INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,current_email,created_at,updated_at) VALUES('B1','D','J','1990-01-01','j@x.fr','2026-01-01','2026-01-01')")
    execute(e,"INSERT INTO participants(action_id,last_name,first_name,email,active,created_at,beneficiary_id) VALUES(:a,'D','J','j@x.fr',1,'2026-01-01',:b)",{'a':aid,'b':bid})
    rid=create_beneficiary_report(e,aid,bid,'Besoin de contact','Rappel','Merci de me rappeler',False)
    assert one(e,'SELECT quality_relevant FROM beneficiary_reports WHERE id=:i',{'i':rid})['quality_relevant']==1
    qi=one(e,"SELECT * FROM quality_issues WHERE source_role='BENEFICIAIRE' AND source_ref=:r",{'r':str(rid)})
    assert qi and qi['issue_type']=='SIGNALEMENT_BENEFICIAIRE'


def test_ui_no_longer_asks_user_to_choose_quality_followup():
    src=Path('app.py').read_text(encoding='utf-8')
    assert 'Ce signalement doit également alimenter le suivi qualité' not in src
    assert 'Suivi de mes émargements' in src
    assert 'Signatures bénéficiaires à régulariser' in src
    assert 'Suivi des émargements de cette action' in src
