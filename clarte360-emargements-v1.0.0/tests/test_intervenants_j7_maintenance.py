from datetime import date,timedelta
from db import make_engine,init_db,execute,one
from services import (create_professional_intervenant,list_services,set_human_service_qualification,
 professional_maintenance_alerts,act_on_professional_maintenance_alert,archive_professional_document,
 store_professional_document,update_professional_regulatory_status,add_professional_certification)

def eng():
    e=make_engine('sqlite:///:memory:');init_db(e);return e

def test_j7_alerts_expired_and_upcoming_documents():
    e=eng();p=create_professional_intervenant(e,'Alpha',actor='admin'); today=date(2026,9,20)
    store_professional_document(e,p,b'pdf','cert.pdf','CERTIFICATION','admin',valid_until=(today-timedelta(days=1)).isoformat())
    store_professional_document(e,p,b'pdf2','rc.pdf','RC_PRO','admin',valid_until=(today+timedelta(days=30)).isoformat())
    rows=professional_maintenance_alerts(e,today.isoformat(),90)
    assert {x['status'] for x in rows}=={'EXPIRE','A_RENOUVELER'}

def test_j7_qualiopi_and_certification_alerts():
    e=eng();p=create_professional_intervenant(e,'Bravo',actor='admin'); today=date(2026,9,20)
    update_professional_regulatory_status(e,p,{'nda_status':'OUI','nda_number':'11999999999','qualiopi_status':'OUI','qualiopi_scope_training':True,'qualiopi_valid_until':(today+timedelta(days=20)).isoformat()},'admin')
    add_professional_certification(e,p,'Habilitation X','HABILITATION',valid_until=(today-timedelta(days=2)).isoformat(),actor='admin')
    kinds={x['kind'] for x in professional_maintenance_alerts(e,today.isoformat(),90)}
    assert 'QUALIOPI' in kinds and 'HABILITATION' in kinds

def test_j7_qualification_review_is_alerted_but_not_auto_invalidated():
    e=eng();p=create_professional_intervenant(e,'Charlie',actor='admin');s=list_services(e,True)[0];today=date(2026,9,20)
    set_human_service_qualification(e,p,s['id'],3,'admin',review_due_at=(today-timedelta(days=1)).isoformat())
    rows=professional_maintenance_alerts(e,today.isoformat(),90)
    assert any(x['kind']=='REVISION_QUALIFICATION' for x in rows)
    assert one(e,'SELECT human_value FROM person_service_qualifications WHERE professional_person_id=:p AND service_id=:s',{'p':p,'s':s['id']})['human_value']==3

def test_j7_alert_can_be_snoozed_or_treated():
    e=eng();p=create_professional_intervenant(e,'Delta',actor='admin');today=date(2026,9,20)
    did=store_professional_document(e,p,b'x','x.pdf','RC_PRO','admin',valid_until=(today+timedelta(days=10)).isoformat())
    key=f'DOC:{did}';assert professional_maintenance_alerts(e,today.isoformat(),90)
    act_on_professional_maintenance_alert(e,p,key,'REPORTE','admin',snooze_until=(today+timedelta(days=20)).isoformat())
    assert not professional_maintenance_alerts(e,today.isoformat(),90)
    act_on_professional_maintenance_alert(e,p,key,'ROUVERT','admin')
    assert professional_maintenance_alerts(e,today.isoformat(),90)
    act_on_professional_maintenance_alert(e,p,key,'TRAITE','admin')
    assert not professional_maintenance_alerts(e,today.isoformat(),90)

def test_j7_archive_document_removes_from_active_dossier_not_storage():
    e=eng();p=create_professional_intervenant(e,'Echo',actor='admin');did=store_professional_document(e,p,b'z','old.pdf','AUTRE','admin')
    archive_professional_document(e,p,did,'admin')
    row=one(e,'SELECT archived_at,stored_file_id FROM professional_documents WHERE id=:i',{'i':did})
    assert row['archived_at'] and one(e,'SELECT id FROM stored_files WHERE id=:i',{'i':row['stored_file_id']})
