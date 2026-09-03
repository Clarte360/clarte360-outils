from db import make_engine,init_db,one,q,utcnow_iso
from services import ensure_default_organization,add_agency,set_action_modules,create_action,create_questionnaire_template,create_quality_campaign,save_quality_response,archive_action

def eng():
 e=make_engine('sqlite:///:memory:');init_db(e);return e

def test_v2_org_agency_and_action_modules():
 e=eng(); oid=ensure_default_organization(e); gid=add_agency(e,oid,{'name':'Paris'},'admin')
 aid=create_action(e,{'action_no':'V2-1','title':'Test','subtitle':None,'nature':'FORMATION','mode':'INTER','client_name':None,'client_type':'ENTREPRISE','group_code':None,'planned_hours':7,'expected_participants':1,'admin_email':'a@b.fr','trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},'admin')
 set_action_modules(e,aid,'FORMATION',True,True,True,True,oid,gid,'admin'); a=one(e,'SELECT * FROM actions WHERE id=:a',{'a':aid})
 assert a['organization_id']==oid and a['agency_id']==gid and a['use_quality_hot']==1 and a['use_quality_cold']==1

def test_v2_questionnaire_snapshot_and_campaign():
 e=eng(); oid=ensure_default_organization(e)
 aid=create_action(e,{'action_no':'V2-2','title':'BC','subtitle':None,'nature':'BC','mode':'INDIVIDUEL','client_name':None,'client_type':'PARTICULIER','group_code':None,'planned_hours':12,'expected_participants':1,'admin_email':'a@b.fr','trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},'admin')
 tid=create_questionnaire_template(e,oid,'BC_FIN','1.0','BC','HOT','Fin BC',[{'question_code':'Q1','rubric_code':'R01','response_type':'SCALE','question_text':'Satisfaction ?','required':True}])
 cid,tok=create_quality_campaign(e,aid,tid,'HOT',utcnow_iso()); q1=one(e,'SELECT * FROM questionnaire_questions WHERE template_id=:t',{'t':tid}); save_quality_response(e,cid,q1['id'],{'value':5})
 r=one(e,'SELECT * FROM quality_responses WHERE campaign_id=:c',{'c':cid}); assert r['rubric_code']=='R01' and r['question_text_snapshot']=='Satisfaction ?' and tok

def test_v2_archive_action():
 e=eng(); aid=create_action(e,{'action_no':'V2-3','title':'Archive','subtitle':None,'nature':'FORMATION','mode':'INDIVIDUEL','client_name':None,'client_type':'PARTICULIER','group_code':None,'planned_hours':1,'expected_participants':1,'admin_email':'a@b.fr','trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},'admin')
 ok,_=archive_action(e,aid,'admin'); assert ok and one(e,'SELECT status FROM actions WHERE id=:a',{'a':aid})['status']=='ARCHIVEE'
