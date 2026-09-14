import hashlib, hmac, time, pytest
from hub_contract import canonical_payload, verify_hub_context, build_status_event

def sig(p, secret='s'):
    return hmac.new(secret.encode(), canonical_payload(p), hashlib.sha256).hexdigest()

def base(role='admin'):
    return {'tool_id':'contractualisation','hub_source':'GESTION_ACTIONS_I9','role':role,'action_id':'CLA0001','beneficiary_id':'BEN1','expires_at':int(time.time())+60}

def test_admin_only_allowed():
    p=base('admin')
    assert verify_hub_context(p,sig(p),'s')['role']=='admin'

def test_intervenant_role_forbidden():
    p=base('intervenant')
    with pytest.raises(ValueError): verify_hub_context(p,sig(p),'s')

def test_beneficiary_role_forbidden():
    p=base('beneficiaire')
    with pytest.raises(ValueError): verify_hub_context(p,sig(p),'s')

def test_bad_signature_and_expiry():
    p=base()
    with pytest.raises(ValueError): verify_hub_context(p,'bad','s')
    p['expires_at']=1
    with pytest.raises(ValueError): verify_hub_context(p,sig(p),'s',now=2)

def test_status_contract():
    e=build_status_event(action_id='CLA0001',prescription_id=None,status='generated',no_clar='CLA0001')
    assert e['tool_id']=='contractualisation'
