import json
from db import make_engine, init_db, one, q
from services import upsert_pip_public_crm_contact, create_crm_contact


def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'a.db')); init_db(e); return e


def test_first_public_contact_created_immediately_with_required_interest(tmp_path):
    e=eng(tmp_path)
    r=upsert_pip_public_crm_contact(e,'Alice','Martin',' Alice.Martin@Example.COM ',marketing_consent=False)
    assert r['email']=='alice.martin@example.com'
    assert r['source']=='PIP_PUBLIC'
    assert r['email_verified_at']
    assert r['marketing_consent']==0
    assert 'PIP-RIASEC' in json.loads(r['interests_json'])
    assert len(q(e,'SELECT * FROM crm_contacts'))==1


def test_same_email_is_upserted_and_interests_are_merged(tmp_path):
    e=eng(tmp_path)
    r1=upsert_pip_public_crm_contact(e,'Alice','Martin','alice@example.com',interests=['Bilan de compétences'])
    r2=upsert_pip_public_crm_contact(e,'Alice','Martin','ALICE@example.com',interests=['Coaching'])
    assert r1['id']==r2['id']
    assert len(q(e,'SELECT * FROM crm_contacts'))==1
    assert json.loads(r2['interests_json'])==['PIP-RIASEC','Bilan de compétences','Coaching']


def test_existing_manual_contact_is_enriched_not_duplicated_or_reclassified(tmp_path):
    e=eng(tmp_path)
    old=create_crm_contact(e,'Alice','Martin','alice@example.com',phone='+33600000000',interests=['Formation'],source='MANUEL')
    r=upsert_pip_public_crm_contact(e,'Alice','Martin','alice@example.com',interests=['Coaching'])
    assert r['id']==old['id'] and r['source']=='MANUEL' and r['phone']=='+33600000000'
    assert json.loads(r['interests_json'])==['PIP-RIASEC','Formation','Coaching']


def test_marketing_yes_then_unspecified_does_not_revoke(tmp_path):
    e=eng(tmp_path)
    r=upsert_pip_public_crm_contact(e,'Alice','Martin','alice@example.com',marketing_consent=True)
    assert r['marketing_consent']==1 and r['marketing_consent_at']
    r=upsert_pip_public_crm_contact(e,'Alice','Martin','alice@example.com',marketing_consent=None)
    assert r['marketing_consent']==1 and r['marketing_revoked_at'] is None


def test_explicit_marketing_no_is_allowed_and_records_revocation(tmp_path):
    e=eng(tmp_path)
    upsert_pip_public_crm_contact(e,'Alice','Martin','alice@example.com',marketing_consent=True)
    r=upsert_pip_public_crm_contact(e,'Alice','Martin','alice@example.com',marketing_consent=False)
    assert r['marketing_consent']==0 and r['marketing_revoked_at']


def test_public_crm_has_no_study_linkage(tmp_path):
    e=eng(tmp_path)
    r=upsert_pip_public_crm_contact(e,'Alice','Martin','alice@example.com')
    assert r['source_ref'] is None
    blob=json.dumps(dict(r),ensure_ascii=False).lower()
    for forbidden in ('study_id','pseudonym','passation_id','holland','riasec_score','pip_answers','onet_answers'):
        assert forbidden not in blob
