import io, json
import pandas as pd
from db import make_engine,init_db,one,q,execute
from services import ensure_default_organization,create_action,safe_set_action_modules,create_quality_issue,update_quality_issue,create_improvement_action,update_improvement_action,quality_dashboard,quality_question_stats
from excel_import import read_adca_xlsm,read_clarte360_xlsm

def eng():
 e=make_engine('sqlite:///:memory:');init_db(e);ensure_default_organization(e);return e

def test_issue_and_improvement_workflow():
 e=eng(); oid=one(e,'select id from organizations')['id']; aid=create_action(e,{'action_no':'T1','title':'Test','subtitle':None,'nature':'Formation','mode':'INTRA','client_name':'X','client_type':'ENTREPRISE','group_code':None,'planned_hours':7,'expected_participants':1,'admin_email':'a@b.fr','trainer_name':None,'trainer_email':None,'location':None,'notes':None,'source':'TEST'},'t'); safe_set_action_modules(e,aid,'FORMATION',False,False,True,False,oid,None,'t')
 iid=create_quality_issue(e,aid,'RECLAMATION','Test','Desc','Dom','t'); assert one(e,'select status from quality_issues where id=:i',{'i':iid})['status']=='OUVERTE'; update_quality_issue(e,iid,'CLOTUREE','Dom','t'); assert one(e,'select closed_at from quality_issues where id=:i',{'i':iid})['closed_at']
 mid=create_improvement_action(e,aid,'Corriger','Action','Dom','2026-10-01',iid,'t'); update_improvement_action(e,mid,'TERMINEE','t'); assert one(e,'select completed_at from improvement_actions where id=:i',{'i':mid})['completed_at']

def test_dashboard_empty_and_issue_counts():
 e=eng(); d=quality_dashboard(e); assert d['campaigns']==0 and d['response_rate']==0

def _xls(key):
 conv=pd.DataFrame([{key:'X1','INTITULE_FORMA':'Titre','NOM_ENT':'Client','NOM_STAGIAIRE':'ConvNom','PRENOM_STAGIAIRE':'ConvPre','EMAIL':'c@x.fr','DUREE_HEURES_STAGIAIRE':7}]); stag=pd.DataFrame([{key:'X1','INTITULE_FORMA':'Titre','NOM_ENT':'Client','NOM_STAGIAIRE':'StagNom','PRENOM_STAGIAIRE':'StagPre','EMAIL':'s@x.fr','DUREE_HEURES_STAGIAIRE':7}]); b=io.BytesIO()
 with pd.ExcelWriter(b,engine='openpyxl') as w: conv.to_excel(w,sheet_name='CONV ADM',index=False);stag.to_excel(w,sheet_name='STAGIAIRE',index=False)
 return b.getvalue()

def test_import_mapping_intra_uses_stagiaire():
 d,p=read_adca_xlsm(_xls('NO_ADCA'),'X1','INTRA'); assert d['source_sheet']=='STAGIAIRE' and p[0]['last_name']=='StagNom'

def test_import_mapping_inter_uses_conv_adm():
 d,p=read_clarte360_xlsm(_xls('NO_CLAR'),'X1','INTER'); assert d['source_sheet']=='CONV ADM' and p[0]['last_name']=='ConvNom'
