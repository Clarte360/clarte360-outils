import json
import pytest
from sqlalchemy import text

from db import make_engine, init_db, execute, one
from services import (
    PROFESSIONAL_COLLABORATION_TYPES,
    create_professional_intervenant,
    get_professional_360,
    list_professional_collaboration_history,
    list_services,
    list_service_criteria,
    save_ai_qualification_proposal,
    get_person_service_qualification,
    set_human_service_qualification,
    set_human_criterion_assessment,
    list_qualification_review_points,
    decide_qualification_review_point,
    reopen_qualification_review_point,
    store_professional_document,
    save_global_professional_ai_analysis,
    latest_global_professional_ai_run,
    review_professional_ai_suggestion,
    list_professional_fact_sources,
    link_qualification_evidence,
    list_qualification_evidence_links,
    delete_professional_if_unused,
)


def eng(tmp_path, name='p1.db'):
    e = make_engine('sqlite:///' + str(tmp_path / name))
    init_db(e)
    return e


def bilan_service(e):
    return next(x for x in list_services(e) if x['service_code'] == 'BILAN_COMPETENCES')


def test_p1_collaboration_target_list_and_legacy_migration(tmp_path):
    assert PROFESSIONAL_COLLABORATION_TYPES == (
        'A_DEFINIR', 'SALARIE', 'STAGIAIRE', 'SOUS_TRAITANT', 'MANDATAIRE_ASSOCIE'
    )
    e = eng(tmp_path)
    p1 = create_professional_intervenant(e, 'Ancien Indépendant', 'ind@example.test', actor='admin')
    p2 = create_professional_intervenant(e, 'Ancien Salarié', 'sal@example.test', actor='admin')
    execute(e, "UPDATE professional_profiles SET collaboration_type='INDEPENDANT' WHERE professional_person_id=:p", {'p': p1})
    execute(e, "UPDATE professional_profiles SET collaboration_type='SALARIE_INTERNE' WHERE professional_person_id=:p", {'p': p2})

    # Re-running init_db simulates an additive upgrade of an existing RC2-2-1 database.
    init_db(e)

    assert get_professional_360(e, p1)['collaboration_type'] == 'A_DEFINIR'
    assert get_professional_360(e, p2)['collaboration_type'] == 'SALARIE'
    h1 = list_professional_collaboration_history(e, p1)
    h2 = list_professional_collaboration_history(e, p2)
    assert h1[0]['old_type'] == 'INDEPENDANT' and h1[0]['reclassification_required'] == 1 and h1[0]['status'] == 'OUVERT'
    assert h2[0]['old_type'] == 'SALARIE_INTERNE' and h2[0]['new_type'] == 'SALARIE' and h2[0]['status'] == 'CLOTURE'

    # Idempotence: a second upgrade does not duplicate migration history.
    init_db(e)
    assert len(list_professional_collaboration_history(e, p1)) == 1
    assert len(list_professional_collaboration_history(e, p2)) == 1


def test_p1_human_protection_is_automatic_and_ai_only_row_is_not_locked(tmp_path):
    e = eng(tmp_path)
    p = create_professional_intervenant(e, 'Protection Humaine', actor='admin')
    s = bilan_service(e)
    cr = list_service_criteria(e, s['id'])[0]
    result = {
        'service_level': 2, 'confidence': .7, 'rationale': 'Proposition',
        'evidence': [], 'missing_points': [],
        'criteria': [{'criterion_id': cr['id'], 'proposed_level': 2, 'confidence': .7, 'rationale': 'Indice', 'evidence_indexes': []}],
    }
    save_ai_qualification_proposal(e, p, s['id'], result, 'admin', 'openai', 'test', 'p1', 'hash')
    q = get_person_service_qualification(e, p, s['id'])['qualification']
    assert q['human_value'] is None
    assert q['human_locked'] == 0

    # Even a legacy caller asking for human_locked=False cannot make a human decision unprotected.
    set_human_service_qualification(e, p, s['id'], 3, 'admin', 'Décision humaine', human_locked=False)
    set_human_criterion_assessment(e, p, cr['id'], 3, 'admin', 'Critère confirmé', human_locked=False)
    detail = get_person_service_qualification(e, p, s['id'])
    assert detail['qualification']['human_locked'] == 1
    assessed = next(x for x in detail['criteria'] if x['id'] == cr['id'])
    assert assessed['assessment_locked'] == 1


def test_p1_upgrade_repairs_incoherent_human_lock_flags(tmp_path):
    e = eng(tmp_path)
    p1 = create_professional_intervenant(e, 'Sans Décision', 'none@example.test', actor='admin')
    p2 = create_professional_intervenant(e, 'Avec Décision', 'yes@example.test', actor='admin')
    s = bilan_service(e)
    now = '2026-10-02T12:00:00+00:00'
    execute(e, """INSERT INTO person_service_qualifications(professional_person_id,service_id,human_locked,created_at,updated_at)
        VALUES(:p,:s,1,:n,:n)""", {'p': p1, 's': s['id'], 'n': now})
    execute(e, """INSERT INTO person_service_qualifications(professional_person_id,service_id,human_value,human_locked,created_at,updated_at)
        VALUES(:p,:s,3,0,:n,:n)""", {'p': p2, 's': s['id'], 'n': now})
    init_db(e)
    assert one(e, 'SELECT human_locked FROM person_service_qualifications WHERE professional_person_id=:p', {'p': p1})['human_locked'] == 0
    assert one(e, 'SELECT human_locked FROM person_service_qualifications WHERE professional_person_id=:p', {'p': p2})['human_locked'] == 1


def test_p1_legacy_ai_missing_points_are_structured_idempotent_and_decidable(tmp_path):
    e = eng(tmp_path)
    p = create_professional_intervenant(e, 'Points IA', actor='admin')
    s = bilan_service(e)
    result = {
        'service_level': 1, 'confidence': .4, 'rationale': 'Dossier partiel',
        'evidence': [], 'criteria': [],
        'missing_points': ['Vérifier la pratique autonome', 'Confirmer la procédure de confidentialité'],
    }
    save_ai_qualification_proposal(e, p, s['id'], result, 'admin', 'openai', 'test', 'p1', 'hash')
    assert list_qualification_review_points(e, p, s['id']) == []

    init_db(e)
    points = list_qualification_review_points(e, p, s['id'])
    assert len(points) == 2
    assert all(x['status'] == 'OUVERT' for x in points)
    assert all(x['source'] == 'MIGRATION' for x in points)
    init_db(e)
    assert len(list_qualification_review_points(e, p, s['id'])) == 2

    point = points[0]
    with pytest.raises(ValueError):
        decide_qualification_review_point(e, point['id'], 'LEVE', 'admin')
    assert decide_qualification_review_point(e, point['id'], 'LEVE', 'admin', 'Confirmé en entretien et dossier vérifié') is True
    assert len(list_qualification_review_points(e, p, s['id'], open_only=True)) == 1
    assert reopen_qualification_review_point(e, point['id'], 'admin', 'Nouveau contrôle requis') is True
    assert len(list_qualification_review_points(e, p, s['id'], open_only=True)) == 2


def test_p1_accepted_fact_keeps_document_provenance_and_is_reusable_across_services(tmp_path):
    e = eng(tmp_path)
    p = create_professional_intervenant(e, 'Fait Réutilisable', actor='admin')
    did = store_professional_document(e, p, b'%PDF-1.4\nP1 test\n', 'cv_p1.pdf', 'CV', 'admin')
    result = {
        'profile': {}, 'specialties': [], 'education': [], 'certifications': [], 'languages': [],
        'identity_alerts': [], 'missing_points': [], 'service_candidates': [],
        'experiences': [{
            'role_title': 'Consultant formateur', 'organization': 'Clarté Test',
            'start_date': '2020-01-01', 'end_date': None, 'description': 'Expérience démontrée',
            'source_document_id': did,
        }],
    }
    save_global_professional_ai_analysis(e, p, result, 'admin', 'openai', 'test', 'p1', 'global-hash', selected_document_ids=[did])
    run = latest_global_professional_ai_run(e, p)
    sug = next(x for x in run['suggestions'] if x['suggestion_type'] == 'EXPERIENCE')
    assert review_professional_ai_suggestion(e, sug['id'], 'ACCEPTE', 'admin') is True

    sources = list_professional_fact_sources(e, p, 'EXPERIENCE')
    assert len(sources) == 1
    assert sources[0]['professional_document_id'] == did
    assert sources[0]['document_name'] == 'cv_p1.pdf'
    assert sources[0]['source_kind'] == 'AI_ACCEPTED'
    fact_ref = sources[0]['fact_ref_id']

    services = list_services(e, active_only=True)[:2]
    l1 = link_qualification_evidence(e, p, services[0]['id'], 'admin', fact_type='EXPERIENCE', fact_ref_id=fact_ref, relevance_comment='Pertinent pour la prestation 1')
    l1_again = link_qualification_evidence(e, p, services[0]['id'], 'admin', fact_type='EXPERIENCE', fact_ref_id=fact_ref, relevance_comment='Ne doit pas dupliquer')
    l2 = link_qualification_evidence(e, p, services[1]['id'], 'admin', fact_type='EXPERIENCE', fact_ref_id=fact_ref, relevance_comment='Pertinent pour la prestation 2')
    assert l1 == l1_again
    assert l2 != l1
    assert len(list_qualification_evidence_links(e, p, services[0]['id'])) == 1
    assert len(list_qualification_evidence_links(e, p, services[1]['id'])) == 1
    assert len(list_professional_fact_sources(e, p, 'EXPERIENCE')) == 1


def test_p1_new_owned_tables_do_not_block_physical_delete_of_unused_test_dossier(tmp_path):
    e = eng(tmp_path)
    p = create_professional_intervenant(e, 'Dossier Jetable', 'delete@example.test', actor='admin')
    # Create a collaboration history row and a sourced fact, all owned by the dossier.
    from services import update_professional_profile, add_professional_specialty, add_professional_fact_source
    update_professional_profile(e, p, {'collaboration_type': 'SALARIE'}, 'admin')
    rid = add_professional_specialty(e, p, 'Test P1', actor='admin')
    add_professional_fact_source(e, p, 'SPECIALTY', rid, 'admin', source_kind='HUMAN')
    assert delete_professional_if_unused(e, p, 'admin') is True
    assert one(e, 'SELECT professional_person_id FROM professional_persons WHERE professional_person_id=:p', {'p': p}) is None


def test_p1_manual_fact_origin_is_human_and_restart_does_not_relabel_it(tmp_path):
    e = eng(tmp_path)
    p = create_professional_intervenant(e, 'Origine Humaine', actor='admin')
    from services import add_professional_experience
    rid = add_professional_experience(e, p, 'Formateur', 'Clarté360', actor='admin')
    sources = list_professional_fact_sources(e, p, 'EXPERIENCE', rid)
    assert len(sources) == 1 and sources[0]['source_kind'] == 'HUMAN'
    init_db(e)
    sources = list_professional_fact_sources(e, p, 'EXPERIENCE', rid)
    assert len(sources) == 1 and sources[0]['source_kind'] == 'HUMAN'


def test_p1_legacy_structured_fact_without_provenance_is_backfilled_as_migration(tmp_path):
    e = eng(tmp_path)
    p = create_professional_intervenant(e, 'Ancien Fait', actor='admin')
    now = '2026-10-01T12:00:00+00:00'
    rid = execute(e, """INSERT INTO professional_experiences(professional_person_id,organization,role_title,current_role,created_at,updated_at)
        VALUES(:p,'Ancienne structure','Ancienne fonction',0,:n,:n)""", {'p': p, 'n': now})
    assert list_professional_fact_sources(e, p, 'EXPERIENCE', rid) == []
    init_db(e)
    sources = list_professional_fact_sources(e, p, 'EXPERIENCE', rid)
    assert len(sources) == 1 and sources[0]['source_kind'] == 'MIGRATION'
    init_db(e)
    assert len(list_professional_fact_sources(e, p, 'EXPERIENCE', rid)) == 1


def test_p1_structured_fact_edit_adds_human_provenance_and_delete_cleans_generic_links(tmp_path):
    e = eng(tmp_path)
    p = create_professional_intervenant(e, 'Edition Fait', actor='admin')
    from services import add_professional_experience, update_professional_structured_row, delete_professional_structured_row
    rid = add_professional_experience(e, p, 'Consultant', 'Structure A', actor='admin')
    s = bilan_service(e)
    link_qualification_evidence(e, p, s['id'], 'admin', fact_type='EXPERIENCE', fact_ref_id=rid, relevance_comment='Lien avant modification')

    assert update_professional_structured_row(
        e, 'professional_experiences', rid, p, {'organization': 'Structure B'}, actor='admin'
    ) is True
    sources = list_professional_fact_sources(e, p, 'EXPERIENCE', rid)
    assert any(x['source_kind'] == 'HUMAN' for x in sources)
    assert len(list_qualification_evidence_links(e, p, s['id'])) == 1

    assert delete_professional_structured_row(e, 'professional_experiences', rid, p, actor='admin') is True
    assert list_professional_fact_sources(e, p, 'EXPERIENCE', rid) == []
    assert list_qualification_evidence_links(e, p, s['id']) == []
