"""J1 / P5-RC2: fictitious data only. No VPS, production or real identities."""
import hashlib
import json
import os
import uuid
from pathlib import Path

import pytest

import purge_guard as guard
from db import make_engine, init_db, execute, one, q, utcnow_iso
from security import hash_password
from services import create_action, add_participant, add_slot, purge_action

ADMIN='admin@j1.invalid'
PASSWORD='fictitious-test-password'
EVIDENCE='Action exclusivement fictive creee pour recette. Aucune donnee reelle ni piece reglementaire.'


def add_action(engine,code):
    return create_action(engine,dict(action_no=code,title='Dossier fictif '+code,
        subtitle=None,nature='Formation',mode='INDIVIDUEL',client_name=None,
        client_type='Particulier',group_code=None,planned_hours=1.5,
        expected_participants=1,admin_email=ADMIN,trainer_name=None,
        trainer_email=None,location='FICTIF',notes=None,source='TEST'),ADMIN)


@pytest.fixture
def environment(tmp_path):
    data=tmp_path/'data';data.mkdir()
    engine=make_engine('sqlite:///'+str(tmp_path/'j1_fixture.db'))
    init_db(engine)
    execute(engine,'INSERT INTO admins(email,password_hash,created_at) VALUES(:e,:h,:n)',
        {'e':ADMIN,'h':hash_password(PASSWORD),'n':utcnow_iso()})
    victim=add_action(engine,'ESSAI-J1')
    neighbor=add_action(engine,'CLA-NEIGHBOR')
    yield engine,victim,neighbor,data
    engine.dispose()


def certification(engine,aid,code='ESSAI-J1',data_root=None):
    result=guard.certify_test_action(engine,aid,ADMIN,evidence=EVIDENCE,
        confirmation='JE CERTIFIE ESSAI '+code,password=PASSWORD,data_root=data_root)
    assert result[0],result


def remove(engine,aid,data,code='ESSAI-J1'):
    preview=guard.preview_action_purge(engine,aid,data_root=data)
    assert preview
    return purge_action(engine,aid,ADMIN,confirmation='SUPPRIMER ESSAI '+code,
        preview_fingerprint=preview['fingerprint'],data_root=data)


def add_quality(engine,aid,public='QE-J1-1'):
    now=utcnow_iso()
    issue=execute(engine,"""INSERT INTO quality_issues(action_id,issue_type,title,status,created_at)
        VALUES(:a,'OBSERVATION','Observation fictive','OUVERTE',:n)""",{'a':aid,'n':now})
    improvement=execute(engine,"""INSERT INTO improvement_actions(issue_id,action_id,title,status,created_at)
        VALUES(:i,:a,'Amelioration fictive','A_FAIRE',:n)""",{'i':issue,'a':aid,'n':now})
    ev=execute(engine,"""INSERT INTO quality_events(public_id,action_id,family,event_type,status,detected_at,origin,subject,
        created_by,created_at,updated_at) VALUES(:p,:a,'RECLAMATION','OBSERVATION','NOUVEAU',:n,'MANUEL','Fiche fictive',:actor,:n,:n)""",
        {'p':public,'a':aid,'n':now,'actor':ADMIN})
    act=execute(engine,"""INSERT INTO quality_event_actions(quality_event_id,title,created_by,created_at,updated_at)
        VALUES(:q,'Action fictive',:actor,:n,:n)""",{'q':ev,'actor':ADMIN,'n':now})
    msg=execute(engine,"""INSERT INTO quality_event_messages(quality_event_id,author,message,created_at)
        VALUES(:q,:actor,'Une remarque fictive',:n)""",{'q':ev,'actor':ADMIN,'n':now})
    return issue,improvement,ev,act,msg


def add_document(engine,aid,data,content=b'Fictitious document',name='document.pdf'):
    h=hashlib.sha256(content).hexdigest();blob=data/'documents'/h;blob.parent.mkdir(parents=True,exist_ok=True)
    blob.write_bytes(content)
    sid=execute(engine,"""INSERT INTO stored_files(sha256,storage_path,size_bytes,created_at)
        VALUES(:h,:p,:n,:c)""",{'h':h,'p':str(blob),'n':len(content),'c':utcnow_iso()})
    rid=execute(engine,"""INSERT INTO document_references(stored_file_id,action_id,category,display_name,created_at)
        VALUES(:s,:a,'COURS',:n,:c)""",{'s':sid,'a':aid,'n':name,'c':utcnow_iso()})
    nid=execute(engine,"""INSERT INTO document_notifications(document_reference_id,action_id,recipient_type,recipient_id,created_at)
        VALUES(:r,:a,'BENEFICIARY',12,:n)""",{'r':rid,'a':aid,'n':utcnow_iso()})
    return sid,rid,nid,blob


def add_attendance(engine,aid,data):
    pid,_=add_participant(engine,aid,{'last_name':'FICTIF','first_name':'TEST','birth_date':'2000-01-01','email':'test@example.invalid'},ADMIN)
    slot=add_slot(engine,aid,'2026-09-02','10:00','11:00',ADMIN)
    path=data/'signatures'/'signature.png';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fake signature')
    execute(engine,"""INSERT INTO signatures(participant_id,slot_id,signed_at,signature_path,signature_sha256,signer_name,method,status)
        VALUES(:p,:s,:n,:path,'SHA','FICTIF TEST','EMAIL','VALIDE')""",{'p':pid,'s':slot,'n':utcnow_iso(),'path':str(path)})
    return pid,slot,path


def test_title_essai_is_not_permission(environment):
    engine,aid,_,data=environment
    p=guard.preview_action_purge(engine,aid,data_root=data)
    assert not purge_action(engine,aid,ADMIN,confirmation='SUPPRIMER ESSAI ESSAI-J1',preview_fingerprint=p['fingerprint'],data_root=data)[0]
    assert one(engine,'SELECT id FROM actions WHERE id=:a',{'a':aid})


def test_wrong_password_or_weak_evidence_rejected(environment):
    e,a,_,data=environment
    wrong=guard.certify_test_action(e,a,ADMIN,evidence=EVIDENCE,
        confirmation='JE CERTIFIE ESSAI ESSAI-J1',password='wrong')
    assert not wrong[0]
    weak=guard.certify_test_action(e,a,ADMIN,evidence='just test',
        confirmation='JE CERTIFIE ESSAI ESSAI-J1',password=PASSWORD,data_root=data)
    assert not weak[0]
    assert not q(e,'SELECT * FROM action_purge_certifications')


def test_wrong_phrase_wrong_actor_and_stale_preview_denied(environment):
    e,a,_,data=environment
    certification(e,a,data_root=data)
    prev=guard.preview_action_purge(e,a,data_root=data)
    assert not purge_action(e,a,ADMIN,confirmation='ESSAI-J1',preview_fingerprint=prev['fingerprint'],data_root=data)[0]
    assert not purge_action(e,a,'wrong@j1.invalid',confirmation='SUPPRIMER ESSAI ESSAI-J1',preview_fingerprint=prev['fingerprint'],data_root=data)[0]
    execute(e,"UPDATE actions SET title='change',updated_at=:n WHERE id=:a",{'n':utcnow_iso(),'a':a})
    assert not purge_action(e,a,ADMIN,confirmation='SUPPRIMER ESSAI ESSAI-J1',preview_fingerprint=prev['fingerprint'],data_root=data)[0]
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a})


def test_quality_capa_messages_documents_and_neighbor_preserved(environment):
    e,a,b,data=environment
    _,_,eid,cap,msg=add_quality(e,a)
    _,_,bn=add_quality(e,b,public='QE-NEIGHBOR')[:3]
    pid,sid,signature=add_attendance(e,a,data)
    blob_id,rid,nid,blob=add_document(e,a,data)
    execute(e,"UPDATE actions SET final_bundle_path=:p WHERE id=:a",{'a':a,'p':str(data/'bundles'/'final.zip')})
    final=data/'bundles'/'final.zip';final.parent.mkdir(parents=True,exist_ok=True);final.write_bytes(b'fictitious zip')
    neighbor_before=one(e,'SELECT * FROM actions WHERE id=:b',{'b':b})
    before_quality=one(e,'SELECT * FROM quality_events WHERE id=:b',{'b':bn})
    certification(e,a,data_root=data)
    prev=guard.preview_action_purge(e,a,data_root=data)
    assert prev['counts']['quality_events']==1
    assert prev['counts']['quality_event_actions']==1
    assert prev['counts']['quality_event_messages']==1
    assert prev['counts']['document_notifications']==1
    assert prev['counts']['stored_files_to_remove']==1
    ok,msg=remove(e,a,data)
    assert ok,msg
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a}) is None
    for table,pk in [('quality_events',eid),('quality_event_actions',cap),('quality_event_messages',msg),('document_references',rid),('stored_files',blob_id),('document_notifications',nid)]:
        assert one(e,f'SELECT id FROM {table} WHERE id=:i',{'i':pk}) is None,table
    assert not signature.exists() and not blob.exists() and not final.exists()
    assert one(e,'SELECT * FROM actions WHERE id=:b',{'b':b})==neighbor_before
    assert one(e,'SELECT * FROM quality_events WHERE id=:b',{'b':bn})==before_quality
    assert not q(e,'PRAGMA foreign_key_check')
    assert one(e,"SELECT status FROM action_purge_journal")['status']=='COMPLETE'


def test_shared_stored_file_kept(environment):
    e,a,b,data=environment
    sid,rid,nid,blob=add_document(e,a,data,content=b'COMMON')
    other=execute(e,"""INSERT INTO document_references(stored_file_id,action_id,category,display_name,created_at)
        VALUES(:s,:a,'COURS','same-other.pdf',:n)""",{'s':sid,'a':b,'n':utcnow_iso()})
    certification(e,a,data_root=data);p=guard.preview_action_purge(e,a,data_root=data)
    assert p['shared_files_kept']==1
    ok,msg=remove(e,a,data)
    assert ok,msg
    assert blob.exists()
    assert one(e,'SELECT id FROM stored_files WHERE id=:id',{'id':sid})
    assert one(e,'SELECT id FROM document_references WHERE id=:id',{'id':other})


def test_outside_storage_refused_without_modification(environment,tmp_path):
    e,a,b,data=environment
    outside=tmp_path/'outside.pdf';outside.write_bytes(b'out-of-root')
    execute(e,"UPDATE actions SET final_bundle_path=:p WHERE id=:a",{'p':str(outside),'a':a})
    with pytest.raises(ValueError,match='hors repertoire'):
        guard.preview_action_purge(e,a,data_root=data)
    assert outside.read_bytes()==b'out-of-root'
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a})


def test_sql_trigger_failure_rolls_back_sql_and_files(environment):
    e,a,b,data=environment
    _,_,_,file=add_document(e,a,data)
    execute(e,"""CREATE TRIGGER cannot_delete_test BEFORE DELETE ON actions
      WHEN OLD.id=%s BEGIN SELECT RAISE(ABORT, 'simulated SQL failure'); END""" % a)
    certification(e,a,data_root=data)
    ok,reason=remove(e,a,data)
    assert not ok and 'restauration' in reason
    assert file.exists()
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a})
    assert one(e,'SELECT status FROM action_purge_journal')['status']=='ROLLED_BACK'
    assert not q(e,'PRAGMA foreign_key_check')


def test_second_file_move_failure_restores_first(environment,monkeypatch):
    e,a,_,data=environment
    _,_,_,first=add_document(e,a,data)
    second=data/'signatures'/'extra.png';second.parent.mkdir(parents=True,exist_ok=True);second.write_bytes(b'extra')
    # Attach a second physical path through a permitted action-local field.
    execute(e,'UPDATE actions SET final_bundle_path=:p WHERE id=:a',{'p':str(second),'a':a})
    certification(e,a,data_root=data)
    move=os.replace;counter={'n':0}
    def fail_second(source,dest):
        if 'purge_quarantine' in str(dest):
            counter['n']+=1
            if counter['n']==2:
                raise OSError('simulated second move failure')
        return move(source,dest)
    monkeypatch.setattr(guard.os,'replace',fail_second)
    ok,_=remove(e,a,data)
    assert not ok
    assert first.exists() and second.exists()
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a})
    assert one(e,'SELECT status FROM action_purge_journal')['status']=='ROLLED_BACK'


def test_post_commit_cleanup_failure_reports_partial_and_recovers(environment,monkeypatch):
    e,a,_,data=environment
    _,_,_,blob=add_document(e,a,data)
    certification(e,a,data_root=data)
    unlink=Path.unlink
    def failed_cleanup(path,*args,**kwargs):
        if 'purge_quarantine' in str(path):
            raise OSError('simulated unlink failure')
        return unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',failed_cleanup)
    ok,reason=remove(e,a,data)
    assert not ok and 'quarantaine' in reason
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a}) is None
    assert one(e,'SELECT status FROM action_purge_journal')['status']=='CLEANUP_REQUIRED'
    monkeypatch.setattr(Path,'unlink',unlink)
    status=guard.recover_action_purges(e,data_root=data)
    assert status[0]['status']=='COMPLETE'
    assert one(e,'SELECT status FROM action_purge_journal')['status']=='COMPLETE'
    assert not blob.exists()


def test_crash_prepared_restores_staged_files(environment):
    e,a,b,data=environment
    _,_,_,blob=add_document(e,a,data)
    cert=guard.certify_test_action(e,a,ADMIN,evidence=EVIDENCE,
        confirmation='JE CERTIFIE ESSAI ESSAI-J1',password=PASSWORD,data_root=data)
    assert cert[0]
    preview=guard.preview_action_purge(e,a,data_root=data)
    op=uuid.uuid4().hex
    manifest={'files':preview['files'],'fingerprint':preview['fingerprint']}
    execute(e,"""INSERT INTO action_purge_journal(id,action_id,action_no,actor,status,manifest_json,created_at,updated_at)
        VALUES(:id,:a,'ESSAI-J1',:actor,'PREPARED',:j,:t,:t)""",
        {'id':op,'a':a,'actor':ADMIN,'j':json.dumps(manifest),'t':utcnow_iso()})
    entries=guard._manifest_paths({'id':op,'manifest_json':json.dumps(manifest)},data)
    src,dst,_=entries[0]
    dst.parent.mkdir(parents=True,exist_ok=True)
    os.replace(src,dst)
    assert not src.exists() and dst.exists()
    state=guard.recover_action_purges(e,data_root=data)
    assert state[0]['status']=='ROLLED_BACK'
    assert src.exists() and not dst.exists()
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a})


def test_incomplete_operation_blocks_duplicate_purge(environment):
    e,a,_,data=environment
    certification(e,a,data_root=data)
    p=guard.preview_action_purge(e,a,data_root=data)
    execute(e,"""INSERT INTO action_purge_journal(id,action_id,action_no,actor,status,manifest_json,created_at,updated_at)
         VALUES('OLD',:a,'ESSAI-J1',:actor,'PREPARED','{}',:now,:now)""",{'a':a,'actor':ADMIN,'now':utcnow_iso()})
    ok,reason=remove(e,a,data)
    assert not ok and 'Ancienne purge' in reason


def test_unlinked_historical_quality_preserved(environment):
    e,a,_,data=environment
    now=utcnow_iso()
    execute(e,"""INSERT INTO quality_events(public_id,action_id,family,event_type,status,detected_at,origin,subject,created_by,created_at,updated_at)
        VALUES('QE-ORPHAN',NULL,'OBSERVATION','OBSERVATION','NOUVEAU',:n,'MANUEL','Origine inconnue','historique',:n,:n)""",{'n':now})
    certification(e,a,data_root=data)
    assert guard.legacy_quality_orphans(e)['quality_events_without_action']==1
    ok,msg=remove(e,a,data)
    assert ok,msg
    assert one(e,"SELECT id FROM quality_events WHERE public_id='QE-ORPHAN'") is not None


def test_quality_event_indirect_campaign_no_orphan(environment):
    e,a,_,data=environment
    now=utcnow_iso()
    org=execute(e,"INSERT INTO organizations(name,created_at,updated_at) VALUES('Fictif',:n,:n)",{'n':now})
    tpl=execute(e,"""INSERT INTO questionnaire_templates(organization_id,code,version,prestation_type,campaign_kind,title,created_at)
        VALUES(:o,'FICTIVE','1','FORMATION','HOT','Test',:n)""",{'o':org,'n':now})
    campaign=execute(e,"""INSERT INTO quality_campaigns(action_id,template_id,campaign_kind,due_at,token,created_at)
        VALUES(:a,:tpl,'HOT',:n,'fictitious-token',:n)""",{'a':a,'tpl':tpl,'n':now})
    eid=execute(e,"""INSERT INTO quality_events(public_id,action_id,campaign_id,family,event_type,detected_at,subject,created_by,created_at,updated_at)
        VALUES('QE-CAMPAIGN',NULL,:c,'OBSERVATION','OBSERVATION',:n,'Indirect',:actor,:n,:n)""",
        {'c':campaign,'n':now,'actor':ADMIN})
    question=execute(e,"""INSERT INTO questionnaire_questions(template_id,question_code,rubric_code,response_type,question_text)
       VALUES(:tpl,'R01-01','R01','SCALE_1_5','Question fictive')""",{'tpl':tpl})
    rp=execute(e,"""INSERT INTO quality_review_points(action_id,campaign_id,question_id,status,created_at,quality_event_id)
       VALUES(:a,:c,:q,'OUVERT',:n,:evt)""",{'a':a,'c':campaign,'q':question,'n':now,'evt':eid})
    certification(e,a,data_root=data);preview=guard.preview_action_purge(e,a,data_root=data)
    assert preview['counts']['quality_events']==1
    assert preview['counts']['quality_review_points']==1
    assert remove(e,a,data)[0]
    assert one(e,'SELECT id FROM quality_events WHERE id=:i',{'i':eid}) is None
    assert one(e,'SELECT id FROM quality_review_points WHERE id=:i',{'i':rp}) is None


def test_cross_action_quality_reference_blocks(environment):
    e,a,b,data=environment
    i=execute(e,"""INSERT INTO quality_issues(action_id,issue_type,title,status,created_at)
      VALUES(:a,'OBSERVATION','Linked','OUVERTE',:n)""",{'a':a,'n':utcnow_iso()})
    execute(e,"""INSERT INTO improvement_actions(issue_id,action_id,title,status,created_at)
      VALUES(:i,:b,'Should stay','A_FAIRE',:n)""",{'i':i,'b':b,'n':utcnow_iso()})
    with pytest.raises(ValueError,match='autre dossier'):
        guard.preview_action_purge(e,a,data_root=data)
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a})


def test_no_double_action_after_deletion(environment):
    e,a,b,data=environment
    certification(e,a,data_root=data);assert remove(e,a,data)[0]
    again=purge_action(e,a,ADMIN,confirmation='SUPPRIMER ESSAI ESSAI-J1',preview_fingerprint='X',data_root=data)
    assert not again[0]


def test_repeated_migration_idempotent(environment):
    e,a,b,data=environment
    init_db(e);init_db(e)
    assert one(e,"SELECT COUNT(*) n FROM sqlite_master WHERE type='table' AND name='action_purge_certifications'")['n']==1
    assert one(e,"SELECT COUNT(*) n FROM sqlite_master WHERE type='table' AND name='action_purge_journal'")['n']==1


def test_certification_expires_if_dependence_changes_even_with_new_preview(environment):
    e,a,_,data=environment
    certification(e,a,data_root=data)
    execute(e,"UPDATE actions SET title='now different',updated_at=:n WHERE id=:a",{'n':utcnow_iso(),'a':a})
    newer=guard.preview_action_purge(e,a,data_root=data)
    result=purge_action(e,a,ADMIN,confirmation='SUPPRIMER ESSAI ESSAI-J1',
        preview_fingerprint=newer['fingerprint'],data_root=data)
    assert not result[0] and 'attestation' in result[1]
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':a})


def test_signature_path_shared_by_neighbor_is_protected(environment):
    e,a,b,data=environment
    pid,sid,file=add_attendance(e,a,data)
    otherp,otherslot,_=add_attendance(e,b,data)
    execute(e,'UPDATE signatures SET signature_path=:p WHERE participant_id=:id',{'p':str(file),'id':otherp})
    with pytest.raises(ValueError,match='partage'):
        guard.preview_action_purge(e,a,data_root=data)
    assert file.exists()
    assert one(e,'SELECT id FROM actions WHERE id=:a',{'a':b})


def test_legacy_action_with_essai_name_and_real_source_not_automatically_certified(environment):
    e,a,_,data=environment
    execute(e,'UPDATE actions SET source=:src WHERE id=:a',{'src':'MANUEL','a':a})
    p=guard.preview_action_purge(e,a,data_root=data)
    assert p['action_no'].startswith('ESSAI')
    ok,reason=purge_action(e,a,ADMIN,confirmation='SUPPRIMER ESSAI ESSAI-J1',
        preview_fingerprint=p['fingerprint'],data_root=data)
    assert not ok and 'certificat' in reason
