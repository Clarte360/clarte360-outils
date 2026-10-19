import copy
import json
from pathlib import Path
import pytest
from clarte360_pip import delivery
from clarte360_pip.connectors import gestion_actions as ga
from clarte360_pip.framework.persistence import build_snapshot,restore_snapshot
from rc3_support import isolate,make_state,add_onet,ui_namespace,events,State

@pytest.mark.parametrize('journey,timing,onet,count',[
 ('PIP_SEUL',None,False,1),('PIP_PUIS_ONET60','POST_PIP_RESULTS',True,2),('PIP_PUIS_ONET60','PRE_PIP',True,2)])
def test_three_validated_routes_emit_expected_reports_once(monkeypatch,tmp_path,journey,timing,onet,count):
    isolate(monkeypatch,tmp_path); s=make_state(journey=journey,onet=onet);s.onet_selected_timing=timing
    ns,ui=ui_namespace(s,real_pdf=True);ns['render_finished']()
    assert len(s.report_documents)==count
    sent=events(tmp_path); assert len(sent)==1 and len(sent[0]['payload']['documents'])==count
    assert all(d['sha256'] and ga.read_report_document(s.passation_id,d).startswith(b'%PDF-') for d in s.report_documents)
    assert 'answers' not in sent[0]['payload']['pip']
    before={d['file_name']:ga.read_report_document(s.passation_id,d) for d in s.report_documents}
    ns['build_pip_report_pdf']=lambda *a:pytest.fail('Existing PDF must not be regenerated')
    ns['build_onet_report_pdf']=lambda *a:pytest.fail('Existing PDF must not be regenerated')
    ns['render_finished'](); assert len(events(tmp_path))==1
    for _,kw in ui.downloads:
        if kw.get('mime')=='application/pdf': assert kw['data']==before[kw['file_name']]


def test_onet_added_after_first_finalization_is_announced_once(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state();ns,ui=ui_namespace(s)
    ns['render_finished']();pip_before=ga.read_report_document(s.passation_id,s.report_documents[0])
    s.onet_selected_timing='POST_PIP_RESULTS';add_onet(s)
    ns['render_finished']();ns['render_finished']()
    sent=events(tmp_path)
    assert [[d['file_name'] for d in e['payload']['documents']] for e in sent]==[[delivery.PIP_NAME],[delivery.ONET_NAME]]
    assert ga.read_report_document(s.passation_id,s.report_documents[0])==pip_before
    restored=State(launch_context=s.launch_context)
    restore_snapshot(build_snapshot(s),restored);ns2,_=ui_namespace(restored);ns2['render_finished']()
    assert len(events(tmp_path))==2


def test_legacy_boolean_uses_journal_proof_not_all_current_refs(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state();ns,_=ui_namespace(s);ns['render_finished']()
    (tmp_path/'delivery'/'accompanied'/f'{s.passation_id}.json').unlink()
    s.pop('delivery_state',None);add_onet(s)
    ns['render_finished']()
    assert len(events(tmp_path))==2
    assert [d['file_name'] for d in events(tmp_path)[1]['payload']['documents']]==[delivery.ONET_NAME]


def test_retry_after_interrupted_publication_uses_same_event(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state();ns,_=ui_namespace(s)
    ns['render_finished'](); original=events(tmp_path)[0]
    receipt=tmp_path/'delivery'/'accompanied'/f'{s.passation_id}.json'
    d=json.loads(receipt.read_text());d['pending_payload']=original['payload'];d['published_documents']={};receipt.write_text(json.dumps(d))
    s.final_event_published=False
    ns['render_finished']()
    assert len(events(tmp_path))==1
    assert s.final_event_published


def test_pending_exists_without_audit_is_repaired_once(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);port=ga.GestionActionsPort(None)
    p=port.publish_event('TERMINE',{'action_id':'TEST-A','beneficiary_id':'TEST-B','prescription_id':'TEST-PRES','passation_id':'TEST-RUN','documents':[]})
    journal=tmp_path/'connector_outbox'/'gestion_actions'/'events.jsonl';journal.unlink()
    envelope=json.loads(p.read_text());port.publish_event('TERMINE',envelope['payload']);port.publish_event('TERMINE',envelope['payload'])
    assert len(events(tmp_path))==1


def test_publication_does_not_append_after_partial_journal(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);p=tmp_path/'connector_outbox'/'gestion_actions'/'events.jsonl';p.parent.mkdir(parents=True);p.write_bytes(b'{"partial":')
    with pytest.raises(ValueError): ga.GestionActionsPort(None).publish_event('EN_COURS',{'passation_id':'TEST-RUN'})
    assert p.read_bytes()==b'{"partial":'

@pytest.mark.parametrize('field,value',[('storage_ref','reports/OTHER/rapport_pip_riasec_clarte360.pdf'),('sha256','0'*64),('size_bytes',-1)])
def test_invalid_report_ref_never_announced(monkeypatch,tmp_path,field,value):
    isolate(monkeypatch,tmp_path);s=make_state();ns,_=ui_namespace(s)
    delivery.accompanied_report(s,delivery.PIP_NAME,lambda:b'%PDF-1.4\noriginal')
    s.report_documents[0][field]=value
    with pytest.raises(ValueError): delivery.publish_accompanied_reports(s,ns['_accompanied_final_payload'])
    assert not events(tmp_path)


def test_symlink_report_is_rejected(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path); outside=tmp_path/'outside.pdf';outside.write_bytes(b'%PDF-1.4')
    p=tmp_path/'reports'/'TEST-RUN'/delivery.PIP_NAME;p.parent.mkdir(parents=True);p.symlink_to(outside)
    with pytest.raises(ValueError): ga.persist_report_document('TEST-RUN',delivery.PIP_NAME,b'%PDF-1.4')


def test_reports_cannot_be_overwritten(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);ref=ga.persist_report_document('TEST-RUN',delivery.PIP_NAME,b'%PDF-1.4\nfirst')
    with pytest.raises(ValueError): ga.persist_report_document('TEST-RUN',delivery.PIP_NAME,b'%PDF-1.4\nother')
    assert ga.read_report_document('TEST-RUN',ref)==b'%PDF-1.4\nfirst'


def test_missing_pdf_retains_existing_reference_and_emits_nothing_new(monkeypatch,tmp_path):
    isolate(monkeypatch,tmp_path);s=make_state();ns,ui=ui_namespace(s);ns['render_finished']()
    path=tmp_path/s.report_documents[0]['storage_ref'];path.unlink()
    ns['render_finished']();assert len(events(tmp_path))==1
    assert any(x[0]=='error' for x in ui.calls)
