from pathlib import Path
import pytest
from db import make_engine, init_db, one
from services import archive_pip_report_pdf, get_pip_prescription_report, create_beneficiary, create_tool_prescription


def setup_hub(tmp_path, monkeypatch):
    import services
    monkeypatch.setattr(services,'BENEFICIARY_DOC_DIR',tmp_path/'docs'); services.BENEFICIARY_DOC_DIR.mkdir()
    e=make_engine(f"sqlite:///{tmp_path/'t.db'}"); init_db(e)
    # minimal action/trainer/participant and PIP catalog are seeded by init_db where applicable
    from db import execute, utcnow_iso
    now=utcnow_iso()
    tid=execute(e,"INSERT INTO trainers(full_name,email,active,created_at,updated_at) VALUES('Test Form','t@x.fr',1,:n,:n)",{'n':now})
    aid=execute(e,"INSERT INTO actions(action_no,title,nature,mode,status,trainer_id,created_at,updated_at) VALUES('A001','Action test','FORMATION','PRESENTIEL','ACTIVE',:t,:n,:n)",{'t':tid,'n':now})
    bid=create_beneficiary(e,'DOE','Jane','1990-01-01',actor='test')
    pid=execute(e,"INSERT INTO participants(action_id,beneficiary_id,last_name,first_name,email,created_at) VALUES(:a,:b,'DOE','Jane','j@x.fr',:n)",{'a':aid,'b':bid,'n':now})
    tool=one(e,"SELECT id FROM tool_catalog WHERE tool_code='PIP_RIASEC_ONET'")
    if not tool:
        toolid=execute(e,"INSERT INTO tool_catalog(tool_code,name,category,active,prescription_allowed,launch_type,created_at,updated_at) VALUES('PIP_RIASEC_ONET','PIP','OUTIL',1,1,'HUB_REDIRECT',:n,:n)",{'n':now})
    else: toolid=tool['id']
    execute(e,"INSERT OR IGNORE INTO action_tool_permissions(action_id,tool_id,tool_code,allowed,created_by,created_at,updated_at) VALUES(:a,:t,'PIP_RIASEC_ONET',1,'test',:n,:n)",{'a':aid,'t':toolid,'n':now})
    pr=create_tool_prescription(e,'PIP_RIASEC_ONET',bid,aid,participant_id=pid,prescriber_type='ADMIN',prescriber_id='admin@test.fr',actor='test')
    return e,aid,bid,pid,pr['prescription_id'] if isinstance(pr,dict) else pr


def test_pdf_archived_in_existing_document_system_and_linked(tmp_path,monkeypatch):
    e,aid,bid,pid,pres=setup_hub(tmp_path,monkeypatch); pdf=b'%PDF-1.4\nPIP report\n%%EOF'
    rid,sha,dedup=archive_pip_report_pdf(e,pres,pdf,source_event_id='evt-pdf-1',source_reference='secure-ref')
    r=get_pip_prescription_report(e,pres)
    assert r['document_reference_id']==rid and r['action_id']==aid and r['beneficiary_id']==bid
    assert r['participant_id']==pid and r['audience']=='ACTION_BENEFICIARIES' and r['visible_to_beneficiary']==1
    assert r['sha256']==sha and Path(r['storage_path']).read_bytes()==pdf


def test_pdf_replay_same_content_is_idempotent(tmp_path,monkeypatch):
    e,aid,bid,pid,pres=setup_hub(tmp_path,monkeypatch); pdf=b'%PDF-1.4\nsame\n%%EOF'
    a=archive_pip_report_pdf(e,pres,pdf,source_event_id='evt-1')
    b=archive_pip_report_pdf(e,pres,pdf,source_event_id='evt-1')
    assert a[0]==b[0]
    assert one(e,'SELECT COUNT(*) n FROM prescription_documents WHERE prescription_id=:p',{'p':pres})['n']==1
    assert one(e,'SELECT COUNT(*) n FROM document_references WHERE action_id=:a',{'a':aid})['n']==1


def test_different_pdf_cannot_replace_existing_report(tmp_path,monkeypatch):
    e,aid,bid,pid,pres=setup_hub(tmp_path,monkeypatch)
    archive_pip_report_pdf(e,pres,b'%PDF-1.4\none\n%%EOF')
    with pytest.raises(ValueError,match='différent'):
        archive_pip_report_pdf(e,pres,b'%PDF-1.4\ntwo\n%%EOF')
