"""Compatibility check against a disposable copy of the unchanged GDA source."""
import sys, shutil, tempfile, json, hashlib, os
from pathlib import Path
from dataclasses import replace
from pytest import MonkeyPatch
PIP=Path(__file__).resolve().parents[1]
if len(sys.argv)!=2:
    raise SystemExit('Usage: python scripts/recette_compatibilite_gda.py CHEMIN_SOURCE_GDA_75af19d')
SOURCE=Path(sys.argv[1]).resolve()
if not (SOURCE/'services.py').is_file():
    raise SystemExit('Source GDA de reference introuvable')
ROOT=Path(tempfile.mkdtemp(prefix='pip_gda_compatibilite_'))

def hashes(path):
    return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file() and not p.is_symlink() and not any(part in {'__pycache__','.venv','.pytest_cache','data','.git','secrets.toml'} or part.startswith('data.backup') for part in p.relative_to(path).parts)}
before=hashes(SOURCE)
with tempfile.TemporaryDirectory(prefix='pip_rc3_gda_') as d:
    root=Path(d);gda=root/'gda';shutil.copytree(SOURCE,gda,ignore=lambda folder,names:[n for n in names if n in {'data','.venv','.git','__pycache__','.pytest_cache','secrets.toml'} or n.startswith('data.backup') or (Path(folder)/n).is_symlink()])
    sys.path[:0]=[str(PIP),str(PIP/'tests'),str(gda),str(gda/'tests')]
    os.chdir(gda)
    from rc3_support import make_state,isolate,ui_namespace,add_onet
    from test_pip_liaison_jalon_f_pdf import setup_hub
    from services import consume_pip_outbox,get_pip_prescription_report,process_pip_accompaniment_event
    from db import one
    from clarte360_pip.domain import LaunchContext,RunMode
    from clarte360_pip.framework.persistence import build_snapshot,restore_snapshot
    results=[]
    for label in ['PIP_SEUL','ONET_APRES_PIP_FINALISE','PIP_ONET_CHOIX_INITIAL','REPRISE_EVENEMENT_DEJA_CONSOMME']:
        scenario=root/label;scenario.mkdir();mp=MonkeyPatch()
        try:
            e,aid,bid,pid,pres=setup_hub(scenario,mp)
            data=scenario/'pip_data';isolate(mp,data)
            s=make_state(run=label,prescription=pres)
            s.launch_context=LaunchContext(mode=RunMode.ACCOMPANIMENT,action_id=str(aid),beneficiary_id=str(bid),participant_id=str(pid),prescription_id=pres,rights=('PIP_RUN','PIP_RESUME','PIP_RESULT_READ','PIP_STATUS'))
            combined=label in {'PIP_ONET_CHOIX_INITIAL','REPRISE_EVENEMENT_DEJA_CONSOMME'}
            if combined:s.onet_selected_timing='PRE_PIP';add_onet(s)
            ns,ui=ui_namespace(s,real_pdf=True);ns['render_finished']()
            outbox=data/'connector_outbox/gestion_actions/events.jsonl'
            if label=='REPRISE_EVENEMENT_DEJA_CONSOMME':
                old=json.loads(outbox.read_text().splitlines()[0]);process_pip_accompaniment_event(e,old)
            result=consume_pip_outbox(e,outbox)
            assert result['errors']==0, (label,result,one(e,"SELECT * FROM connector_cursors WHERE connector_code='PIP_E1'"))
            pip_before=get_pip_prescription_report(e,pres,'PIP_REPORT')
            if label=='ONET_APRES_PIP_FINALISE':
                s.onet_selected_timing='POST_PIP_RESULTS';add_onet(s)
                ns['render_finished']();result=consume_pip_outbox(e,outbox)
                assert result['errors']==0,(label,result)
                assert get_pip_prescription_report(e,pres,'PIP_REPORT')['document_reference_id']==pip_before['document_reference_id']
                assert len(json.loads(outbox.read_text().splitlines()[-1])['payload']['documents'])==1
            expected=1 if label=='PIP_SEUL' else 2
            docs=[]
            for kind in ('PIP_REPORT','ONET_REPORT'):
                doc=get_pip_prescription_report(e,pres,kind)
                if doc:
                    b=Path(doc['storage_path']).read_bytes();assert b.startswith(b'%PDF-') and hashlib.sha256(b).hexdigest()==doc['sha256']
                    assert doc['beneficiary_id']==bid and doc['action_id']==aid and doc['participant_id']==pid
                    docs.append({'kind':kind,'sha256':doc['sha256'],'bytes':len(b)})
            assert len(docs)==expected
            # Refresh publisher, then replay last event as an additional journal line.
            ns['render_finished']();lines=outbox.read_text().splitlines()
            with outbox.open('a') as f:f.write(lines[-1]+'\n')
            again=consume_pip_outbox(e,outbox);assert again['errors']==0
            assert one(e,'SELECT COUNT(*) n FROM prescription_documents WHERE prescription_id=:p',{'p':pres})['n']==expected
            results.append({'scenario':label,'result':'PASS','documents':docs,'replay_without_duplicates':True})
            print('OK',label,expected,'PDF; replay without duplicates')
            e.dispose()
        finally:mp.undo()
assert before==hashes(SOURCE),'The unchanged GDA source must remain identical'
proof={'source_commit':'75af19dafc22141d7ca3690d5bf6c8778430b89e','gda_modified':False,'execution':'local SQLite; actual receiver source unchanged; real PDF bytes; synthetic identities; no network; not VPS', 'results':results}
(ROOT/'integration_unchanged_gda.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))
print('GDA SOURCE UNCHANGED - 4/4 compatibility scenarios passed')
