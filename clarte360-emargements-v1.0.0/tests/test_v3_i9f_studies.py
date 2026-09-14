import io,json
from pathlib import Path
from sqlalchemy import create_engine
from db import init_db,q
from services import load_pip_study_records,study_summary,study_item_quality,study_onet_pairs,export_study_csv,export_study_xlsx,filter_study_records

def eng():
 e=create_engine('sqlite:///:memory:',future=True);init_db(e);return e

def records(tmp_path):
 good={"schema":"clarte360.pip.public-study.v1","study_id":"abc123","passation_id":"SECRET-PASS","journey":"PIP_PUIS_ONET60","onet_selected_timing":"PRE_PIP","pip_bank_version":"PIP-BANK-0.3","pip_answers":{"i1":5,"i2":3},"pip_scoring":{"R":12},"onet_state":{"completed":True,"scores":{"R":20}},"feeling":{"fit":4},"study_consent":True,"completed_at":"2026-09-12T10:00:00","public_identity":{"first_name":"Alice","email":"alice@example.com"},"phone":"0600000000"}
 (tmp_path/'abc.json').write_text(json.dumps(good),encoding='utf-8')
 (tmp_path/'bad.json').write_text('{bad',encoding='utf-8')
 return load_pip_study_records(tmp_path)

def test_loader_strips_identity(tmp_path):
 r=records(tmp_path);assert len(r)==1; assert 'public_identity' not in r[0];assert 'phone' not in r[0];assert r[0]['study_id']=='abc123'

def test_summary_filters_and_item_quality(tmp_path):
 r=records(tmp_path); s=study_summary(r);assert s['terminees']==1 and s['pip_onet']==1 and s['pre_pip']==1
 assert len(filter_study_records(r,{'journey':'PIP_PUIS_ONET60','consent':True}))==1
 iq=study_item_quality(r);assert {x['item_id'] for x in iq}=={'i1','i2'}; assert next(x for x in iq if x['item_id']=='i1')['mean']==5

def test_onet_comparison_only_both_and_separate_timing(tmp_path):
 p=study_onet_pairs(records(tmp_path));assert len(p)==1 and p[0]['timing']=='PRE_PIP';assert 'pip_scoring' in p[0] and 'onet_state' in p[0]

def test_csv_export_has_no_identity_and_is_logged(tmp_path):
 e=eng();data=export_study_csv(e,records(tmp_path),'admin@test','validation',{'journey':'PIP_PUIS_ONET60'})
 text=data.decode('utf-8-sig');assert 'alice@example.com' not in text and 'Alice' not in text and 'SECRET-PASS' not in text
 log=q(e,'SELECT * FROM study_export_events');assert len(log)==1 and log[0]['record_count']==1 and log[0]['format']=='CSV'

def test_xlsx_export_has_no_identity_and_is_logged(tmp_path):
 import openpyxl
 e=eng();data=export_study_xlsx(e,records(tmp_path),'admin@test','validation',{})
 wb=openpyxl.load_workbook(io.BytesIO(data),read_only=True); vals=' '.join(str(v) for row in wb.active.iter_rows(values_only=True) for v in row if v is not None)
 assert 'alice@example.com' not in vals and 'Alice' not in vals and 'SECRET-PASS' not in vals
 assert q(e,'SELECT format,record_count FROM study_export_events')[0]=={'format':'XLSX','record_count':1}

def test_non_consented_record_never_exported(tmp_path):
 r=records(tmp_path);r[0]['study_consent']=False;e=eng();data=export_study_csv(e,r,'admin','test',{})
 assert 'abc123' not in data.decode('utf-8-sig');assert q(e,'SELECT record_count FROM study_export_events')[0]['record_count']==0
