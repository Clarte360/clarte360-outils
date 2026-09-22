from db import make_engine, init_db
from services import (
    list_service_families, add_service_family, update_service_family, delete_service_family,
    list_services, add_service, reassign_services_to_family, list_service_criteria,
)

def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e

def test_j15_families_are_seeded_master_data_and_services_are_backfilled():
    e=eng(); fams=list_service_families(e)
    assert [x['name'] for x in fams[:5]] == ['Bilan de compétences','Formations','Coaching','Conseil','Accompagnements']
    assert all(x.get('family_id') for x in list_services(e))

def test_j15_family_rename_propagates_to_service_projection():
    e=eng(); f=next(x for x in list_service_families(e) if x['name']=='Conseil')
    update_service_family(e,f['id'],{'name':'Conseil & expertise'},'admin','Renommage')
    rows=[x for x in list_services(e) if x.get('family_id')==f['id']]
    assert rows and all(x['family']=='Conseil & expertise' for x in rows)

def test_j15_family_delete_requires_reassignment_and_moves_services():
    e=eng(); a=add_service_family(e,'TEMP','Temporaire',actor='admin'); b=add_service_family(e,'DEST','Destination',actor='admin')
    sid=add_service(e,'SVC_TEMP','Prestation temporaire',family_id=a,actor='admin')
    try:
        delete_service_family(e,a,'admin')
        assert False, 'suppression should require destination'
    except ValueError:
        pass
    assert delete_service_family(e,a,'admin',b) is True
    svc=next(x for x in list_services(e) if x['id']==sid)
    assert svc['family_id']==b and svc['family']=='Destination'

def test_j15_bulk_reassignment_updates_all_selected_services():
    e=eng(); f=add_service_family(e,'NEWF','Nouvelle famille',actor='admin')
    services=list_services(e)[:2]
    assert reassign_services_to_family(e,[x['id'] for x in services],f,'admin')==2
    assert all(next(y for y in list_services(e) if y['id']==x['id'])['family_id']==f for x in services)

def test_j15_all_seeded_services_have_human_checkable_criteria():
    e=eng()
    for svc in list_services(e):
        criteria=list_service_criteria(e,svc['id'],active_only=True)
        assert criteria, svc['service_code']
        assert any(x['required'] for x in criteria)
        assert all(0 <= int(x['minimum_level']) <= 4 for x in criteria)
