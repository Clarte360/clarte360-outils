import json
from sqlalchemy import text
from db import make_engine, init_db
from services import (
    list_services, add_service, update_service, service_versions,
    add_service_criterion, update_service_criterion, list_service_criteria,
    criterion_versions, delete_service, delete_service_criterion,
)


def _engine():
    e=make_engine('sqlite:///:memory:')
    init_db(e)
    return e


def test_j1_seeded_catalog_is_idempotent_and_administrable():
    e=_engine()
    rows=list_services(e)
    codes={x['service_code'] for x in rows}
    assert len(rows) == 26
    assert 'BILAN_COMPETENCES' in codes
    assert 'FORMATION_POSTURE_DIRIGEANT_LEADERSHIP' in codes
    assert 'FORMATION_DEMARCHE_QHSE' in codes
    assert 'COACHING_PROFESSIONNEL_INDIVIDUEL' in codes
    assert 'CONSEIL_QHSE_SANTE_RSE' in codes
    assert 'QHSE_LEADER_INFLUENCE' not in codes
    assert 'FORMATIONS_CIBLEES' not in codes
    assert all((x.get('family') or '') != 'Qualiopi' for x in rows)
    init_db(e)
    assert len(list_services(e)) == 26


def test_j1_manual_service_is_immediately_in_catalog_and_versioned():
    e=_engine()
    sid=add_service(e,'AUDIT_QHSE','Audit QHSE','QHSE','Audit de système','MIXTE',actor='admin')
    svc=next(x for x in list_services(e) if x['id']==sid)
    assert svc['active'] == 1
    assert svc['current_version'] == 1
    update_service(e,sid,{'name':'Audit QHSE & RSE','active':False},'admin','Élargissement du périmètre')
    svc=next(x for x in list_services(e) if x['id']==sid)
    assert svc['name']=='Audit QHSE & RSE'
    assert svc['active']==0
    versions=service_versions(e,sid)
    assert [x['version_no'] for x in versions] == [2,1]
    assert versions[0]['change_reason']=='Élargissement du périmètre'


def test_j1_criterion_supports_categories_levels_evidence_and_history():
    e=_engine()
    sid=next(x['id'] for x in list_services(e) if x['service_code']=='COACHING_PROFESSIONNEL_INDIVIDUEL')
    cid=add_service_criterion(
        e,sid,'POSTURE_COACH','ACCOMPAGNEMENT_COACHING','Posture d’accompagnement',
        'Critère explicite de qualification',True,2.0,3,['CV','certification'],24,'admin')
    rows=list_service_criteria(e,sid)
    cr=next(x for x in rows if x['id']==cid)
    assert cr['required']==1
    assert cr['minimum_level']==3
    assert json.loads(cr['accepted_evidence_json'])==['CV','certification']
    update_service_criterion(e,cid,{'minimum_level':4,'accepted_evidence':['CV','certification','référence mission']},'admin','Exigence renforcée')
    versions=criterion_versions(e,cid)
    assert [x['version_no'] for x in versions] == [2,1]
    assert versions[0]['minimum_level']==4
    assert json.loads(versions[0]['accepted_evidence_json'])[-1]=='référence mission'


def test_j1_no_qualification_is_inferred_from_seed_or_criteria():
    e=_engine()
    with e.connect() as c:
        tables={r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        criteria_count=c.execute(text('SELECT COUNT(*) FROM service_competency_criteria')).scalar_one()
    assert criteria_count == 0
    assert 'professional_qualifications' not in tables


def test_j1_service_and_criterion_can_be_deleted_before_dependency():
    e=_engine()
    sid=add_service(e,'TEST_TEMP','Prestation temporaire','Formations',actor='admin')
    cid=add_service_criterion(e,sid,'TEMP','METIER_TECHNIQUE','Critère temporaire',actor='admin')
    assert delete_service_criterion(e,cid,'admin') is True
    assert list_service_criteria(e,sid)==[]
    assert delete_service(e,sid,'admin') is True
    assert all(x['id']!=sid for x in list_services(e))
