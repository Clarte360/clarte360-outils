from db import make_engine,init_db
from services import create_professional_intervenant,link_professional_supplier,list_professional_supplier_links,unlink_professional_supplier,supplier_link_projection,one
from supplier_gateway import GestionClientsSupplierGateway

def eng(tmp_path):
 e=make_engine('sqlite:///'+str(tmp_path/'j10.db')); init_db(e); return e

def test_supplier_link_does_not_create_supplier_identity(tmp_path):
 e=eng(tmp_path);p=create_professional_intervenant(e,'Alice Pro',actor='admin')
 x=link_professional_supplier(e,p,'SUP-001','INDEPENDENT','2026-01-01',actor='admin')
 assert x['supplier_id']=='SUP-001' and x['status']=='ACTIVE'
 assert one(e,'SELECT supplier_id FROM professional_persons WHERE professional_person_id=:p',{'p':p})['supplier_id']=='SUP-001'

def test_change_supplier_keeps_history(tmp_path):
 e=eng(tmp_path);p=create_professional_intervenant(e,'Bob Pro',actor='admin')
 link_professional_supplier(e,p,'SUP-A','SOUS_TRAITANT','2026-01-01',actor='admin')
 link_professional_supplier(e,p,'SUP-B','PARTENAIRE','2026-09-01',actor='admin')
 rows=list_professional_supplier_links(e,p); assert len(rows)==2
 assert next(x for x in rows if x['supplier_id']=='SUP-A')['status']=='INACTIVE'
 assert next(x for x in rows if x['supplier_id']=='SUP-B')['status']=='ACTIVE'

def test_internal_professional_can_have_no_supplier(tmp_path):
 e=eng(tmp_path);p=create_professional_intervenant(e,'Claire Interne','claire@example.test',actor='admin')
 assert list_professional_supplier_links(e,p,True)==[]

def test_gateway_sync_uses_professional_person_id(tmp_path):
 calls=[]
 def transport(method,path,payload,headers):
  calls.append((method,path,payload)); return {'id':'L-42','supplier_id':'SUP-X','professional_person_id':payload['professional_person_id'],'status':'ACTIVE'}
 e=eng(tmp_path);p=create_professional_intervenant(e,'David Pro',actor='admin');g=GestionClientsSupplierGateway(transport=transport)
 x=link_professional_supplier(e,p,'SUP-X','PROFESSIONAL',actor='admin',gateway=g)
 assert x['sync_status']=='SYNCHRONISE' and x['remote_link_id']=='L-42'
 assert calls[0][2]['professional_person_id']==p and calls[0][2]['source_system']=='GESTION_INTERVENANTS'

def test_gateway_failure_preserves_local_link_and_unlink_history(tmp_path):
 def transport(*a,**k): raise RuntimeError('CRM indisponible')
 e=eng(tmp_path);p=create_professional_intervenant(e,'Emma Pro',actor='admin')
 x=link_professional_supplier(e,p,'SUP-Z',actor='admin',gateway=GestionClientsSupplierGateway(transport=transport))
 assert x['sync_status']=='ERREUR' and 'indisponible' in x['sync_error']
 unlink_professional_supplier(e,p,'SUP-Z',actor='admin')
 assert list_professional_supplier_links(e,p,True)==[] and list_professional_supplier_links(e,p)[0]['status']=='INACTIVE'
