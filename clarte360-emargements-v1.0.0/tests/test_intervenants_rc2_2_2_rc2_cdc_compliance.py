from pathlib import Path
import pytest
from db import make_engine, init_db, one
from services import (
    create_professional_intervenant, create_professional_candidate,
    add_service_family, add_service, add_service_criterion,
    set_human_criterion_assessment, set_human_service_qualification,
    get_person_service_qualification, create_qualification_review_point,
    decide_qualification_review_point, list_qualification_review_points,
    professional_people_operational_view, list_services,
)

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
SERVICES=(ROOT/'services.py').read_text(encoding='utf-8')

def eng():
    e=make_engine('sqlite:///:memory:'); init_db(e); return e

def test_e1_review_point_vocabulary_matches_cdc_and_backend():
    assert "opts=['OUVERT','LEVE','CONFIRME','NON_PERTINENT']" in APP
    assert 'LEVE_HUMAINEMENT' not in APP
    assert 'NON_APPLICABLE' not in APP
    e=eng(); p=create_professional_intervenant(e,'Test E1',actor='admin'); s=list_services(e,True)[0]
    pid=create_qualification_review_point(e,p,s['id'],'Vérifier la pratique','admin',source='HUMAIN')
    assert decide_qualification_review_point(e,pid,'LEVE','admin','Confirmé en entretien')
    assert list_qualification_review_points(e,p,s['id'])[0]['status']=='LEVE'

def test_e2_collaboration_labels_are_business_labels():
    for label in ['Type de collaboration avec Clarté360','À définir','Salarié','Stagiaire','Sous-traitant','Mandataire / Associé']:
        assert label in APP
    assert "selectbox('Type de collaboration',PROFESSIONAL_COLLABORATION_TYPES" not in APP

def test_e3_required_criterion_needs_explicit_exception_when_enforced():
    e=eng(); fid=add_service_family(e,'E3','E3',actor='admin'); sid=add_service(e,'E3_SERVICE','Service E3',family_id=fid,actor='admin')
    cid=add_service_criterion(e,sid,'E3_CRIT','METIER_TECHNIQUE','Critère obligatoire',required=True,minimum_level=3,actor='admin')
    p=create_professional_intervenant(e,'Test E3',actor='admin')
    set_human_criterion_assessment(e,p,cid,2,'admin','Partiel')
    with pytest.raises(ValueError,match='dérogation explicite'):
        set_human_service_qualification(e,p,sid,3,'admin','Validation',exception_reason=None,enforce_required_criteria=True)
    set_human_service_qualification(e,p,sid,3,'admin','Validation',exception_reason='Expérience récente documentée, revue prévue',enforce_required_criteria=True)
    hist=get_person_service_qualification(e,p,sid)['history']
    assert any(x['event_type']=='SERVICE_HUMAN_EXCEPTION' for x in hist)

def test_e4_single_final_validation_controls_criteria_and_service():
    assert 'Enregistrer l’évaluation humaine des critères' not in APP
    assert 'Ces niveaux sont enregistrés avec la validation finale' in APP
    assert 'Grille et qualification humaine enregistrées en une seule validation.' in APP
    final=APP[APP.index("st.markdown('##### Validation humaine de la prestation')"):APP.index("return_action_id=",APP.index("st.markdown('##### Validation humaine de la prestation')"))]
    assert 'set_human_criterion_assessment' in final and 'set_human_service_qualification' in final

def test_e5_e6_operational_tables_have_cdc_pilotage_fields():
    for token in ["'Collaboration'","'Conformité'","'Prochaine révision'","'Missions'","'À faire'"]:
        assert token in APP
    for token in ["'Origine'","'Prestations revendiquées'","'Dernière activité'","'À faire'"]:
        assert token in APP
    e=eng(); p=create_professional_candidate(e,'Candidate E6',actor='admin')
    row=next(x for x in professional_people_operational_view(e) if x['professional_person_id']==p)
    for key in ['collaboration_label','compliance_label','mission_count','todo_count','last_activity','claimed_services','next_action']:
        assert key in row

def test_e7_service_catalog_exposes_criterion_and_qualified_counts():
    e=eng(); rows=list_services(e)
    assert rows and 'criterion_count' in rows[0] and 'qualified_people_count' in rows[0]
    assert "'Critères':x.get('criterion_count')" in APP
    assert "'Personnes qualifiées':x.get('qualified_people_count')" in APP

def test_e8_ai_observability_details_are_visible():
    for token in ['prompt_version','Tokens entrée','Tokens sortie','Documents réellement transmis','Appels API','Retries']:
        assert token in APP

def test_version_is_rc2_compliance_checkpoint():
    import branding
    assert branding.APP_VERSION=='3.0.0-INTERVENANTS-RC2-2-2-RC2'
