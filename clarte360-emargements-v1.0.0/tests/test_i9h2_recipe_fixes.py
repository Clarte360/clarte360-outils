from pathlib import Path
from db import make_engine, init_db, execute, one, utcnow_iso
from services import beneficiary_portal_status, seed_tool_catalog, upsert_tool_catalog

ROOT=Path(__file__).resolve().parents[1]

def test_portal_completed_quality_query_uses_real_schema():
    text=(ROOT/'app.py').read_text(encoding='utf-8')
    assert 'qc.updated_at' not in text
    assert "ORDER BY COALESCE(qc.completed_at,qc.created_at) DESC" in text

def test_trainer_task_message_does_not_render_deltagenerator_expression():
    text=(ROOT/'app.py').read_text(encoding='utf-8')
    assert 'st.info(f"{len(tasks)} créneau(x) à contresigner ou à finaliser.") if tasks else' not in text

def test_h2_version():
    from branding import APP_VERSION
    assert APP_VERSION=='3.0.0-I9-J2C-PIP-LIAISON-I-CRM0-RC2'

def test_beneficiary_portal_status_lifecycle(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'x.db'}"); init_db(e)
    now=utcnow_iso()
    execute(e,"INSERT INTO beneficiaries(public_id,last_name,first_name,birth_date,active,created_at,updated_at) VALUES('BEN-T','TEST','Alice','1990-01-01',1,:n,:n)",{'n':now})
    bid=one(e,"SELECT id FROM beneficiaries WHERE public_id='BEN-T'")['id']
    assert beneficiary_portal_status(e,bid)['state']=='ABSENT'
    execute(e,"INSERT INTO beneficiary_portal_accounts(beneficiary_id,email,active,invited_at,created_at,updated_at) VALUES(:b,'a@example.com',1,:n,:n,:n)",{'b':bid,'n':now})
    assert beneficiary_portal_status(e,bid)['state']=='INVITE'
    execute(e,"UPDATE beneficiary_portal_accounts SET email_verified_at=:n,password_hash='x',last_login_at=:n WHERE beneficiary_id=:b",{'n':now,'b':bid})
    st=beneficiary_portal_status(e,bid)
    assert st['state']=='ACTIVE' and st['activated'] is True and st['last_login_at']==now

def test_catalog_admin_update_preserves_pip_connector_contract(tmp_path):
    e=make_engine(f"sqlite:///{tmp_path/'x.db'}"); init_db(e); seed_tool_catalog(e)
    execute(e,"UPDATE tool_catalog SET connector_status='CONNECTED' WHERE tool_code='PIP_RIASEC_ONET'")
    upsert_tool_catalog(e,{'tool_code':'PIP_RIASEC_ONET','name':'PIP RIASEC / O*NET','category':'ORIENTATION_PROFESSIONNELLE','tool_version':'1.0.10-ACCOMPAGNEMENT','base_url':'https://pip-riasec.clarte360.com','launch_type':'EXTERNAL_SIGNED','active':True,'prescription_allowed':True,'allowed_publics':['BENEFICIAIRE']})
    row=one(e,"SELECT * FROM tool_catalog WHERE tool_code='PIP_RIASEC_ONET'")
    assert row['connector_code']=='PIP_RC5'
    assert row['connector_status']=='CONNECTED'
    assert row['launch_type']=='EXTERNAL_SIGNED'
