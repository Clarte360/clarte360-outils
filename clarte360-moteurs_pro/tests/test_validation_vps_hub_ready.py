import base64, hashlib, hmac, json, time
import pytest
from validation import *
from hub_contract import verify_launch_token

def token(payload, secret='secret'):
    raw=json.dumps(payload,separators=(',',':')).encode(); p=base64.urlsafe_b64encode(raw).decode().rstrip('='); sig=hmac.new(secret.encode(),raw,hashlib.sha256).digest(); return p+'.'+base64.urlsafe_b64encode(sig).decode().rstrip('=')

def test_names_unicode(): assert validate_name("Élodie-Marie",'Nom') == 'Élodie-Marie'
@pytest.mark.parametrize('v',['A1','../x','😀'])
def test_bad_names(v):
    with pytest.raises(ValueError): validate_name(v)
def test_email(): assert validate_email('a.b@example.fr') == 'a.b@example.fr'
@pytest.mark.parametrize('v',['a@b','a@b.com\nBcc:x@y.com','a@b.com;c@d.com'])
def test_bad_email(v):
    with pytest.raises(ValueError): validate_email(v)
def test_phone(): assert validate_phone('+33 6 12 34 56 78')
def test_position_boundaries(): assert validate_position(0)==0 and validate_position(10)==10
@pytest.mark.parametrize('v',[-1,11,5.5,float('nan'),float('inf'),True])
def test_bad_position(v):
    with pytest.raises(ValueError): validate_position(v)
def test_code(): assert validate_code('123456')=='123456'
def test_bad_code():
    with pytest.raises(ValueError): validate_code('12345')
def legacy_payload():
    return {'app_version':'1.8.0-socle-clarte360','beneficiaire':{'prenom':'Jean','nom':'Dupont','email':'j@d.fr','consultant':'Coach'},'cursor_order_displayed':['C01','C02'],'positions':{'C01':0,'C02':10},'passation_id':'CL360-MP-20260912-ABC12345'}
def test_cloud_180_json_remains_compatible(): assert validate_progress_payload(legacy_payload(),['C01','C02'])
def test_unknown_cursor_rejected():
    p=legacy_payload(); p['positions']['X99']=5
    with pytest.raises(ValueError): validate_progress_payload(p,['C01','C02'])
def test_oversize_json():
    with pytest.raises(ValueError): decode_progress_bytes(b'x'*(MAX_JSON_BYTES+1))
def test_hub_admin_and_intervenant():
    now=int(time.time())
    for role in ('admin','intervenant'):
        p={'tool_id':'moteurs-professionnels','hub_source':'GESTION_ACTIONS_I9','role':role,'beneficiary_id':'B1','action_id':'A1','participant_id':'P1','prescription_id':'R1','iat':now,'exp':now+3600,'scopes':['MOTEURS_RUN']}
        assert verify_launch_token(token(p), 'secret', now)['role']==role
def test_hub_beneficiary_role_rejected():
    now=int(time.time()); p={'tool_id':'moteurs-professionnels','hub_source':'GESTION_ACTIONS_I9','role':'beneficiaire','beneficiary_id':'B1','action_id':'A1','participant_id':'P1','prescription_id':'R1','iat':now,'exp':now+3600,'scopes':['MOTEURS_RUN']}
    with pytest.raises(ValueError): verify_launch_token(token(p),'secret',now)
def test_bad_signature():
    now=int(time.time()); p={'tool_id':'moteurs-professionnels','hub_source':'GESTION_ACTIONS_I9','role':'admin','beneficiary_id':'B1','action_id':'A1','participant_id':'P1','prescription_id':'R1','iat':now,'exp':now+3600,'scopes':['MOTEURS_RUN']}
    with pytest.raises(ValueError): verify_launch_token(token(p,'x'),'secret',now)
def test_identity_config():
    cfg=json.load(open('config/app_identity.json',encoding='utf-8')); assert cfg['deployment_status']=='planned' and cfg['target_url'].startswith('https://')


from work_guard import fingerprint_guard_state, canonical_guard_state

def _gf(pos=None, draft=None):
    return fingerprint_guard_state(beneficiaire={"nom":"Dupont","prenom":"Jean"}, cursor_order=["C01","C02"], positions=pos or {}, rgpd_acceptance={"consentement":True}, draft_slider=draft)

def test_guard_same_business_state_same_fingerprint():
    assert _gf({"C01":5}) == _gf({"C01":5})

def test_guard_validated_answer_rearms_after_saved_state():
    assert _gf({"C01":5}) != _gf({"C01":5,"C02":7})

def test_guard_unvalidated_slider_is_detected():
    assert _gf({"C01":5}) != _gf({"C01":5}, {"id":"C02","position":8})

def test_guard_technical_runtime_data_is_not_part_of_business_state():
    state = canonical_guard_state(beneficiaire={}, cursor_order=[], positions={}, rgpd_acceptance={})
    assert "sessions" not in state and "heartbeat" not in state and "timestamp" not in state

def test_source_clears_beforeunload_when_state_is_saved():
    source=open('app.py',encoding='utf-8').read()
    assert 'window.parent.onbeforeunload = null' in source
    assert 'current_business_fingerprint(active)' in source
