import base64, hashlib, hmac, json, time, pytest
from validation import *
from hub_contract import verify_launch_token, status_event

def tok(payload,secret='secret'):
    p=base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    s=base64.urlsafe_b64encode(hmac.new(secret.encode(),p.encode(),hashlib.sha256).digest()).decode().rstrip('=')
    return p+'.'+s

def base(role='admin'):
    n=int(time.time()); return {'tool_id':'boussole-valeurs','hub_source':'GESTION_ACTIONS_I9','role':role,'beneficiary_id':'BEN-1','action_id':'CLA0001','participant_id':'PART-1','prescription_id':'PRES-1','scopes':['BOUSSOLE_RUN','BOUSSOLE_STATUS'],'iat':n-1,'exp':n+3600}

@pytest.mark.parametrize('v',["Élodie","Jean-Pierre","O’Connor","D'Angelo"])
def test_names(v): assert name(v)==v
@pytest.mark.parametrize('v',['Jean2','../x','🙂'])
def test_bad_names(v):
    with pytest.raises(ValidationError): name(v)
@pytest.mark.parametrize('v',['a@b.fr','dominique.briet+test@clarte360.com'])
def test_emails(v): assert email(v)
@pytest.mark.parametrize('v',['a@b','a@b.fr\r\nBcc:x@y.fr','a@b.fr;c@d.fr'])
def test_bad_emails(v):
    with pytest.raises(ValidationError): email(v)
@pytest.mark.parametrize('v',['+33 6 12 34 56 78','0612345678'])
def test_phone(v): assert phone(v)
@pytest.mark.parametrize('v',['1','abc'])
def test_bad_phone(v):
    with pytest.raises(ValidationError): phone(v,True)
@pytest.mark.parametrize('v',[0,1,10])
def test_score(v): assert score(v)==v
@pytest.mark.parametrize('v',[-1,11,float('nan'),float('inf'),True,2.5])
def test_bad_score(v):
    with pytest.raises(ValidationError): score(v)
def test_json_invalid():
    with pytest.raises(ValidationError): decode_json_bytes(b'{bad')
def test_json_oversize():
    with pytest.raises(ValidationError): decode_json_bytes(b'x'*(MAX_JSON_BYTES+1))
def test_state_too_many_values():
    with pytest.raises(ValidationError): validate_state({'beneficiaire':{},'valeurs':[{}]*31})
def test_state_energy_max3():
    with pytest.raises(ValidationError): validate_state({'beneficiaire':{},'valeurs':[{}]*4,'valeurs_energies':{'selected':[0,1,2,3],'entries':{}}})
@pytest.mark.parametrize('role',['admin','intervenant'])
def test_hub_roles(role): assert verify_launch_token(tok(base(role)),'secret')['role']==role
def test_hub_beneficiary_not_prescriber():
    with pytest.raises(ValidationError): verify_launch_token(tok(base('beneficiaire')),'secret')
def test_hub_wrong_tool():
    p=base(); p['tool_id']='x'
    with pytest.raises(ValidationError): verify_launch_token(tok(p),'secret')
def test_hub_requires_run():
    p=base(); p['scopes']=['BOUSSOLE_STATUS']
    with pytest.raises(ValidationError): verify_launch_token(tok(p),'secret')
def test_hub_bad_sig():
    with pytest.raises(ValidationError): verify_launch_token(tok(base())+'x','secret')
def test_status_minimal():
    e=status_event(base(),'completed','DOC-1'); assert e['document_ref']=='DOC-1' and 'valeurs' not in e
