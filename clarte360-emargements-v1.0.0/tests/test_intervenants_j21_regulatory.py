from db import make_engine, init_db
from services import create_professional_candidate,get_professional_360,update_professional_regulatory_status,store_professional_document

def eng(tmp_path):
    e=make_engine('sqlite:///'+str(tmp_path/'j21.db'));init_db(e);return e

def test_nda_and_qualiopi_scopes_are_structured(tmp_path):
    e=eng(tmp_path);p=create_professional_candidate(e,'Intervenant Test',actor='admin')
    update_professional_regulatory_status(e,p,{
      'nda_status':'OUI','nda_number':'11999999999','nda_region':'Ile-de-France',
      'qualiopi_status':'OUI','qualiopi_certifier':'Certificateur X','qualiopi_certificate_ref':'Q-001',
      'qualiopi_scope_training':True,'qualiopi_scope_bilan':True},'admin')
    r=get_professional_360(e,p)['regulatory_status']
    assert r['nda_number']=='11999999999';assert r['qualiopi_scope_training']==1;assert r['qualiopi_scope_bilan']==1;assert r['qualiopi_scope_vae']==0

def test_nda_yes_requires_number(tmp_path):
    e=eng(tmp_path);p=create_professional_candidate(e,'Intervenant Test',actor='admin')
    try:
      update_professional_regulatory_status(e,p,{'nda_status':'OUI','qualiopi_status':'NON'},'admin')
      assert False
    except ValueError as ex:
      assert 'numéro de déclaration' in str(ex).lower()

def test_qualiopi_yes_requires_scope_and_documents_categories_exist(tmp_path):
    e=eng(tmp_path);p=create_professional_candidate(e,'Intervenant Test',actor='admin')
    try:
      update_professional_regulatory_status(e,p,{'nda_status':'NON','qualiopi_status':'OUI'},'admin');assert False
    except ValueError as ex:
      assert 'catégorie' in str(ex).lower()
    did=store_professional_document(e,p,b'%PDF-1.4 cert','qualiopi.pdf','QUALIOPI_CERTIFICAT','admin')
    assert did>0
