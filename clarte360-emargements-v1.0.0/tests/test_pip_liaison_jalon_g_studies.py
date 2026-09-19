import json
from services import load_pip_study_records,pip_study_storage_status,_flatten_study_record

def test_storage_status_not_configured_and_missing(tmp_path):
    assert pip_study_storage_status('')['reason']=='NOT_CONFIGURED'
    assert pip_study_storage_status(tmp_path/'absent')['reason']=='MISSING_DIRECTORY'

def test_loader_deduplicates_and_strips_join_keys(tmp_path):
    raw={'schema':'clarte360.pip.public-study.v1','study_id':'STUDY-X','study_consent':True,
         'crm_id':42,'contact_id':7,'source_ref':'CRM-ABC','passation_id':'PASS-SECRET',
         'public_identity':{'email':'x@example.com'},'pip_answers':{'i1':4}}
    (tmp_path/'a.json').write_text(json.dumps(raw),encoding='utf-8')
    (tmp_path/'b.json').write_text(json.dumps(raw),encoding='utf-8')
    rows=load_pip_study_records(tmp_path)
    assert len(rows)==1
    text=json.dumps(rows[0])
    for forbidden in ('CRM-ABC','PASS-SECRET','x@example.com','crm_id','contact_id','source_ref','passation_id'):
        assert forbidden not in text
    assert '_source_file' not in rows[0]

def test_loader_ignores_symlink_and_wrong_schema(tmp_path):
    good=tmp_path/'good.json';good.write_text(json.dumps({'schema':'clarte360.pip.public-study.v1','study_id':'OK'}),encoding='utf-8')
    (tmp_path/'wrong.json').write_text(json.dumps({'schema':'other','study_id':'NO'}),encoding='utf-8')
    try: (tmp_path/'link.json').symlink_to(good)
    except OSError: pass
    rows=load_pip_study_records(tmp_path)
    assert [r['study_id'] for r in rows]==['OK']

def test_flattened_study_never_contains_join_keys():
    row=_flatten_study_record({'study_id':'PSEUDO','study_consent':True,'source_ref':'CRM-X','passation_id':'P-X','pip_answers':{}})
    text=json.dumps(row)
    assert 'CRM-X' not in text and 'P-X' not in text
