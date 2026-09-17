import base64, hashlib, hmac, json, time, pytest
from validation import *
from hub_contract import verify_launch_token, status_event

def tok(payload, secret='secret'):
    p=base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    s=base64.urlsafe_b64encode(hmac.new(secret.encode(),p.encode(),hashlib.sha256).digest()).decode().rstrip('=')
    return p+'.'+s

def base(role='admin'):
    n=int(time.time())
    return {'tool_id':'roue-valeurs','hub_source':'GESTION_ACTIONS_I9','role':role,'beneficiary_id':'BEN-1','action_id':'CLA0001','participant_id':'PART-1','prescription_id':'PRES-1','scopes':['ROUE_VALEURS_RUN','ROUE_VALEURS_STATUS'],'iat':n-1,'exp':n+3600}

def state():
    domains = [
        {'domaine': d, 'periode': 'septembre 2026', 'exemple': 'J’ai pris une décision concrète.', 'cote': 8}
        for d in ['Personnel','Travail','Famille','Social','Couple / intimité']
    ]
    return {
        'root_passage_id': 'abc-1',
        'beneficiaire': {'prenom':'Élodie','nom':"O\'Connor",'email':'e@x.fr','consultant':'Clarté360','date_realisation':'2026-09-12'},
        'valeurs': [{'nom':'Liberté','definition':'Être autonome','couleur':'#008080','domaines':domains}],
        'valeurs_energies': {'selected':[0],'entries':{'0':{'score_revise':9,'commentaire':'Porteuse','actions':['Agir','','','',''],'maintien':['','','','','']}}}
    }


@pytest.mark.parametrize('v',["Élodie","Jean-Pierre","O’Connor","D'Angelo","Łukasz"])
def test_names(v): assert name(v)==v
@pytest.mark.parametrize('v',['Jean2','../x','🙂','<script>alert(1)</script>'])
def test_bad_names(v):
    with pytest.raises(ValidationError): name(v)
@pytest.mark.parametrize('v',['a@b.fr','dominique.briet+test@clarte360.com'])
def test_emails(v): assert email(v)
@pytest.mark.parametrize('v',['a@b','a@b.fr\r\nBcc:x@y.fr','a@b.fr;c@d.fr'])
def test_bad_emails(v):
    with pytest.raises(ValidationError): email(v)
@pytest.mark.parametrize('v',['+33 6 12 34 56 78','0612345678','+36 (30) 123-4567'])
def test_phone(v): assert phone(v)
@pytest.mark.parametrize('v',['1','abc'])
def test_bad_phone(v):
    with pytest.raises(ValidationError): phone(v,True)
@pytest.mark.parametrize('v',[0,1,10])
def test_score(v): assert score(v)==v
@pytest.mark.parametrize('v',[-1,11,float('nan'),float('inf'),True,2.5])
def test_bad_score(v):
    with pytest.raises(ValidationError): score(v)
def test_state_valid(): assert validate_state(state())
def test_state_requires_five_domains():
    d=state(); d['valeurs'][0]['domaines']=d['valeurs'][0]['domaines'][:4]
    with pytest.raises(ValidationError): validate_state(d)
def test_score_gt2_requires_evidence():
    d=state(); d['valeurs'][0]['domaines'][0]['exemple']=''
    with pytest.raises(ValidationError): validate_state(d)
def test_old_json_compatible():
    raw=json.dumps(state(),ensure_ascii=False).encode(); assert decode_json_bytes(raw)['valeurs'][0]['nom']=='Liberté'
def test_json_invalid():
    with pytest.raises(ValidationError): decode_json_bytes(b'{bad')
def test_json_oversize():
    with pytest.raises(ValidationError): decode_json_bytes(b'x'*(MAX_JSON_BYTES+1))
def test_too_many_values():
    d=state(); d['valeurs']=d['valeurs']*25
    with pytest.raises(ValidationError): validate_state(d)
def test_energy_max3():
    d=state(); d['valeurs']=d['valeurs']*4; d['valeurs_energies']['selected']=[0,1,2,3]
    with pytest.raises(ValidationError): validate_state(d)
def test_script_free_text_rejected():
    with pytest.raises(ValidationError): clean_text('<script>x</script>')
@pytest.mark.parametrize('role',['admin','intervenant'])
def test_hub_roles(role): assert verify_launch_token(tok(base(role)),'secret')['role']==role
def test_hub_beneficiary_not_prescriber():
    with pytest.raises(ValidationError): verify_launch_token(tok(base('beneficiaire')),'secret')
def test_hub_wrong_tool():
    p=base(); p['tool_id']='x'
    with pytest.raises(ValidationError): verify_launch_token(tok(p),'secret')
def test_hub_requires_run():
    p=base(); p['scopes']=['ROUE_VALEURS_STATUS']
    with pytest.raises(ValidationError): verify_launch_token(tok(p),'secret')
def test_hub_bad_sig():
    with pytest.raises(ValidationError): verify_launch_token(tok(base())+'x','secret')
def test_hub_expired():
    p=base(); p['exp']=int(time.time())-1
    with pytest.raises(ValidationError): verify_launch_token(tok(p),'secret')
def test_status_minimal():
    e=status_event(base(),'completed','DOC-1'); assert e['document_ref']=='DOC-1' and 'valeurs' not in e

from guard_state import business_state_fingerprint

def test_guard_same_business_state_same_fingerprint():
    d = state()
    assert business_state_fingerprint(d) == business_state_fingerprint(json.loads(json.dumps(d)))

def test_guard_business_change_rearms():
    d = state(); saved = business_state_fingerprint(d)
    d['valeurs'][0]['definition'] = 'Une nouvelle définition'
    assert business_state_fingerprint(d) != saved

def test_guard_technical_timestamps_do_not_rearm():
    d = state(); saved = business_state_fingerprint(d)
    d['updated_at'] = '2099-01-01T00:00:00'
    d['sauvegardes'] = [{'at':'2099-01-01','reason':'test'}]
    d['access'] = {'sessions':[{'last_seen_at':'2099-01-01'}]}
    assert business_state_fingerprint(d) == saved

def test_guard_energy_change_rearms():
    d = state(); saved = business_state_fingerprint(d)
    d['valeurs_energies']['entries']['0']['score_revise'] = 7
    assert business_state_fingerprint(d) != saved

def test_guard_beneficiary_change_rearms():
    d = state(); saved = business_state_fingerprint(d)
    d['beneficiaire']['prenom'] = 'Élodie-Marie'
    assert business_state_fingerprint(d) != saved
