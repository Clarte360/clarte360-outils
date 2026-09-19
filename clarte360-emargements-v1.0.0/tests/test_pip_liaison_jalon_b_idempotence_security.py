import hashlib, hmac, json
import pytest
from db import init_db, make_engine, one
from services import register_external_incoming_event, claim_external_incoming_event, finish_external_incoming_event, verify_external_event_signature


def eng(tmp_path):
    e=make_engine('sqlite:///' + str(tmp_path/'b.db')); init_db(e); return e


def test_register_is_idempotent_and_does_not_store_payload(tmp_path):
    e=eng(tmp_path); payload={'email':'person@example.com','nested':{'x':1}}
    a=register_external_incoming_event(e,'PIP_PUBLIC','evt-1','CONTACT_VERIFIED',payload)
    b=register_external_incoming_event(e,'PIP_PUBLIC','evt-1','CONTACT_VERIFIED',payload)
    assert a['created'] is True and b['created'] is False
    row=one(e,'SELECT * FROM external_incoming_events WHERE event_id=:e',{'e':'evt-1'})
    assert row['attempts']==0 and row['status']=='RECU'
    assert 'person@example.com' not in json.dumps(row)
    assert row['payload_sha256']==hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def test_same_event_id_with_changed_payload_is_rejected(tmp_path):
    e=eng(tmp_path)
    register_external_incoming_event(e,'PIP_PUBLIC','evt-2','CONTACT_VERIFIED',{'a':1})
    with pytest.raises(ValueError,match='Collision'):
        register_external_incoming_event(e,'PIP_PUBLIC','evt-2','CONTACT_VERIFIED',{'a':2})


def test_retry_lifecycle_and_processed_replay(tmp_path):
    e=eng(tmp_path); p={'a':1}
    register_external_incoming_event(e,'PIP_PUBLIC','evt-3','CONTACT_VERIFIED',p)
    c1=claim_external_incoming_event(e,'PIP_PUBLIC','evt-3'); assert c1['event']['attempts']==1
    finish_external_incoming_event(e,'PIP_PUBLIC','evt-3',error='temporary')
    c2=claim_external_incoming_event(e,'PIP_PUBLIC','evt-3'); assert c2['event']['attempts']==2
    done=finish_external_incoming_event(e,'PIP_PUBLIC','evt-3'); assert done['status']=='TRAITE'
    c3=claim_external_incoming_event(e,'PIP_PUBLIC','evt-3'); assert c3['claimed'] is False and c3['event']['attempts']==2


def test_hmac_verification_is_canonical_and_rejects_bad_signature():
    payload={'z':2,'a':1}; key='secret-test'
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    sig=hmac.new(key.encode(),raw,hashlib.sha256).hexdigest()
    assert verify_external_event_signature(payload,sig,key)
    assert verify_external_event_signature({'a':1,'z':2},'sha256='+sig,key)
    assert not verify_external_event_signature(payload,'0'*64,key)
    assert not verify_external_event_signature(payload,sig,'')
