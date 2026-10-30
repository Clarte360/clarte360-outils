"""Brouillons RC3C : reprise, complétude explicite et deux onglets réels."""
import copy
from dataclasses import replace

import pytest
from sqlalchemy import func, select

from clarte360_cp.application.orientation import OrientationConflict
from clarte360_cp.application.preparation import (
    create_questionnaire_v2, lock_and_publish_questionnaire, read_preparation,
    submit_beneficiary_answers,
)
from clarte360_cp.repositories.cases import CaseRepository
from clarte360_cp.repositories.models import AuditEvent, PreparationResponse
from clarte360_cp.ui import preparation_draft as draft_module
from clarte360_cp.ui.preparation_draft import DraftBuffer, get_draft, prepare_draft, save_draft, reload_draft
from tests.helpers import context


@pytest.fixture
def case_draft(engine, Session):
    coach = context(scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE", "CP_PUBLISH"], actor="ACC-DRAFT")
    ben = context(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT", "CP_BENEFICIARY_VALIDATE"], actor="BEN-DRAFT")
    with Session() as session:
        cid = CaseRepository(session).open_or_create(coach).case_id
    db = str(engine.url)
    q = create_questionnaire_v2(coach, cid, {
        "APS_OBJECTIF": {"authorized": True, "source_ref": "APS-FICTIF", "idea_list": ["Muséographe"]},
    }, database_url=db)
    lock_and_publish_questionnaire(coach, cid, expected_row_version=q.row_version, database_url=db)
    return db, cid, ben


def read(case_draft):
    db, cid, ben = case_draft
    return read_preparation(ben, cid, database_url=db)


def av1_answers(buffer, q, note="Un contexte à explorer"):
    answers = copy.deepcopy(buffer.answers)
    answers["cav1"]["ideas"] = [{
        "id": q["ideas_active"][0]["id"], "interest": "EXPLORER",
        "meaning": ["Exercer ce métier"], "status": [], "attraction": [], "access": [],
        "context": {"choices": [], "other": ""}, "note": note,
    }]
    return answers


def av2_answers(buffer):
    answers = copy.deepcopy(buffer.answers)
    answers["cav2"]["valeurs"]["free"] = ["Autonomie"]
    answers["cav2"]["moteurs"]["free"] = ["Comprendre"]
    answers["cav2"]["preferences"]["free"] = "Pouvoir échanger dans un cadre clair"
    answers["cav2"]["preferences"]["situation"] = "PAS_IDENTIFIEE"
    return answers


def save(case_draft, state, view, visible, *, part, complete=None):
    db, cid, ben = case_draft
    buffer = get_draft(state, cid, view)
    candidate = prepare_draft(buffer, view.questionnaire, visible, part=part, complete=complete)
    return save_draft(state, ben, cid, view, candidate, database_url=db)


def completed(case_draft, state):
    _, cid, _ = case_draft
    view = read(case_draft)
    buffer = get_draft(state, cid, view)
    view = save(case_draft, state, view, av1_answers(buffer, view.questionnaire), part=1, complete=True)
    buffer = get_draft(state, cid, view)
    return save(case_draft, state, view, av2_answers(buffer), part=2, complete=True)


def counts(Session):
    with Session() as session:
        return (
            session.scalar(select(func.count()).select_from(PreparationResponse)),
            session.scalar(select(func.count()).select_from(AuditEvent)),
        )


def test_autosaved_partial_draft_is_recovered_by_a_new_browser_session(case_draft):
    _, cid, _ = case_draft
    state = {}
    view = read(case_draft)
    buffer = get_draft(state, cid, view)
    visible = av1_answers(buffer, view.questionnaire)
    saved = save(case_draft, state, view, visible, part=1)
    assert saved.responses["cav1"]["ideas"][0]["note"] == "Un contexte à explorer"
    assert not saved.responses["cav1_done"]
    assert not saved.responses["cav2_done"]
    recovered = get_draft({}, cid, read(case_draft))
    assert recovered.answers == saved.responses
    assert recovered.row_version == saved.row_version
    # Le brouillon d'origine utilisé pour le rendu n'a pas été modifié en place.
    assert buffer.answers["cav1"]["ideas"] == []


def test_canonical_noop_does_not_create_versions_or_reset_completion(case_draft, Session):
    _, cid, _ = case_draft
    state = {}
    view = completed(case_draft, state)
    before = counts(Session)
    buffer = get_draft(state, cid, view)
    visible = copy.deepcopy(buffer.answers)
    visible["cav1"]["ideas"][0]["note"] = "  Un contexte à explorer  "
    saved = save(case_draft, state, view, visible, part=1)
    assert saved.row_version == view.row_version
    assert saved.responses["cav1_done"] and saved.responses["cav2_done"]
    assert counts(Session) == before


def test_av1_edit_invalidates_both_steps_but_keeps_av2_and_navigation(case_draft):
    _, cid, _ = case_draft
    state = {}
    view = completed(case_draft, state)
    step_key = f"rc3_step_{cid}_{view.questionnaire_version}"
    state[step_key] = 1
    buffer = get_draft(state, cid, view)
    visible = copy.deepcopy(buffer.answers)
    visible["cav1"]["ideas"][0]["note"] = "Précision ajoutée après relecture"
    # L'autre partie ne peut pas être écrasée par un rendu ancien ou mal formé.
    visible["cav2"]["valeurs"]["free"] = ["Ancienne saisie"]
    saved = save(case_draft, state, view, visible, part=1)
    assert not saved.responses["cav1_done"] and not saved.responses["cav2_done"]
    assert saved.responses["cav2"] == buffer.answers["cav2"]
    assert state[step_key] == 1


def test_av2_incomplete_edit_is_saved_and_only_invalidates_av2(case_draft):
    _, cid, _ = case_draft
    state = {}
    view = completed(case_draft, state)
    step_key = f"rc3_step_{cid}_{view.questionnaire_version}"
    state[step_key] = 2
    buffer = get_draft(state, cid, view)
    visible = copy.deepcopy(buffer.answers)
    visible["cav2"]["valeurs"]["free"] = []
    saved = save(case_draft, state, view, visible, part=2)
    assert saved.responses["cav1_done"] and not saved.responses["cav2_done"]
    assert saved.responses["cav1"] == buffer.answers["cav1"]
    assert state[step_key] == 2
    with pytest.raises(ValueError):
        prepare_draft(get_draft(state, cid, saved), saved.questionnaire, saved.responses, part=2, complete=True)


def test_fresh_read_cannot_rebase_old_widgets_and_conflict_is_latched(case_draft, monkeypatch):
    db, cid, ben = case_draft
    state_a, state_b = {}, {}
    initial = read(case_draft)
    buffer_a = get_draft(state_a, cid, initial)
    buffer_b = get_draft(state_b, cid, initial)
    visible_a = av1_answers(buffer_a, initial.questionnaire, "Réponse onglet A")
    saved_a = save(case_draft, state_a, initial, visible_a, part=1)
    fresh = read(case_draft)
    assert get_draft(state_b, cid, fresh).row_version == initial.row_version
    visible_b = av1_answers(buffer_b, initial.questionnaire, "Réponse onglet B")
    candidate_b = prepare_draft(buffer_b, fresh.questionnaire, visible_b, part=1)
    state_b[f"B_{cid}_note_test"] = "Réponse onglet B"
    with pytest.raises(OrientationConflict):
        save_draft(state_b, ben, cid, fresh, candidate_b, database_url=db)
    blocked = get_draft(state_b, cid, fresh)
    assert blocked.conflict
    assert blocked.row_version == initial.row_version
    assert blocked.answers == buffer_b.answers
    assert state_b[f"B_{cid}_note_test"] == "Réponse onglet B"
    assert read(case_draft).responses == saved_a.responses
    # Un nouveau rerun n'entraîne aucune nouvelle tentative vers la base.
    def forbidden_retry(*args, **kwargs):
        raise AssertionError("Il ne faut pas réessayer après conflit sans rechargement explicite")
    monkeypatch.setattr(draft_module, "save_beneficiary_answers", forbidden_retry)
    with pytest.raises(OrientationConflict):
        save_draft(state_b, ben, cid, initial, candidate_b, database_url=db)


def test_database_change_after_read_is_rejected_using_captured_version(case_draft):
    db, cid, ben = case_draft
    state_a, state_b = {}, {}
    initial = read(case_draft)
    buffer_a = get_draft(state_a, cid, initial)
    buffer_b = get_draft(state_b, cid, initial)
    saved_a = save(case_draft, state_a, initial, av1_answers(buffer_a, initial.questionnaire, "A conservée"), part=1)
    candidate_b = prepare_draft(buffer_b, initial.questionnaire, av1_answers(buffer_b, initial.questionnaire, "B refusée"), part=1)
    # Vue passée volontairement antérieure au commit A : la garde application
    # vérifie encore la version capturée dans une nouvelle transaction SQL.
    with pytest.raises(OrientationConflict):
        save_draft(state_b, ben, cid, initial, candidate_b, database_url=db)
    assert get_draft(state_b, cid, initial).conflict
    assert read(case_draft).responses == saved_a.responses


def test_simultaneous_sql_flush_collision_is_a_latched_conflict(case_draft, monkeypatch, Session):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from clarte360_cp.application import preparation as app_preparation

    db, cid, ben = case_draft
    initial = read(case_draft)
    states = [{}, {}]
    barrier = Barrier(2)
    original_version_r = app_preparation._version_r

    def simultaneous_version_r(*args, **kwargs):
        # Les deux transactions ont lu le même numéro avant tout INSERT.
        barrier.wait(timeout=10)
        return original_version_r(*args, **kwargs)

    monkeypatch.setattr(app_preparation, "_version_r", simultaneous_version_r)

    def write(index):
        buffer = get_draft(states[index], cid, initial)
        candidate = prepare_draft(
            buffer, initial.questionnaire,
            av1_answers(buffer, initial.questionnaire, f"Onglet {index}"), part=1,
        )
        try:
            save_draft(states[index], ben, cid, initial, candidate, database_url=db)
            return "saved", index
        except OrientationConflict:
            return "conflict", index

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(write, (0, 1)))
    assert sorted(outcome for outcome, _ in outcomes) == ["conflict", "saved"]
    loser = next(index for outcome, index in outcomes if outcome == "conflict")
    winner = next(index for outcome, index in outcomes if outcome == "saved")
    assert get_draft(states[loser], cid, initial).conflict
    assert read(case_draft).responses["cav1"]["ideas"][0]["note"] == f"Onglet {winner}"
    assert counts(Session)[0] == 1


def test_explicit_reload_clears_only_this_questionnaires_widgets(case_draft):
    _, cid, _ = case_draft
    state = {}
    initial = read(case_draft)
    get_draft(state, cid, initial)
    state.update({
        f"B_{cid}_note_1": "Ancien champ",
        f"rc3_step_{cid}_{initial.questionnaire_version}": 2,
        f"rc3_benef_confirm_{cid}": True,
        f"rc3_draft_conflict_{cid}": True,
        "B_AUTRE_DOSSIER_note_1": "Conserver",
        "rc3_step_AUTRE_DOSSIER_1": 2,
        "navigation_page": "preparation",
        "launch_context": "contexte à conserver",
        "J_DOSSIER_note": "Conserver revue accompagnateur",
    })
    other_session = {}
    buffer = get_draft(other_session, cid, initial)
    saved = save(case_draft, other_session, initial, av1_answers(buffer, initial.questionnaire, "Version serveur"), part=1)
    new = reload_draft(state, cid, saved)
    assert new.row_version == saved.row_version
    assert new.answers == saved.responses
    assert not new.conflict
    assert not any(key.startswith(f"B_{cid}_") for key in state)
    assert f"rc3_benef_confirm_{cid}" not in state
    assert f"rc3_step_{cid}_{initial.questionnaire_version}" not in state
    assert state["B_AUTRE_DOSSIER_note_1"] == "Conserver"
    assert state["navigation_page"] == "preparation"
    assert state["launch_context"] == "contexte à conserver"
    assert state["J_DOSSIER_note"] == "Conserver revue accompagnateur"


def test_invalid_input_does_not_replace_the_saved_draft(case_draft, Session):
    _, cid, _ = case_draft
    state = {}
    view = read(case_draft)
    buffer = get_draft(state, cid, view)
    invalid = av1_answers(buffer, view.questionnaire, "x" * 1601)
    before = counts(Session)
    with pytest.raises(ValueError):
        prepare_draft(buffer, view.questionnaire, invalid, part=1)
    assert get_draft(state, cid, view).answers == buffer.answers
    assert not get_draft(state, cid, view).conflict
    assert counts(Session) == before


def test_step_completion_and_final_submission_remain_explicit(case_draft):
    db, cid, ben = case_draft
    state = {}
    view = read(case_draft)
    buffer = get_draft(state, cid, view)
    saved = save(case_draft, state, view, av1_answers(buffer, view.questionnaire), part=1)
    with pytest.raises(ValueError, match="C-AV1"):
        prepare_draft(get_draft(state, cid, saved), saved.questionnaire, av2_answers(get_draft(state, cid, saved)), part=2)
    with pytest.raises(ValueError):
        submit_beneficiary_answers(ben, cid, expected_row_version=saved.row_version, database_url=db)
    saved = completed(case_draft, state)
    confirmed = get_draft(state, cid, saved)
    final = submit_beneficiary_answers(ben, cid, expected_row_version=confirmed.row_version, database_url=db)
    assert final.active_answers == confirmed.answers
    with pytest.raises(OrientationConflict):
        save_draft(state, ben, cid, final, confirmed.answers, database_url=db)


class InjectedRerun(BaseException):
    """Arrêt du script comme le contrôle de flux Streamlit, pas erreur métier."""


class InterruptedAcknowledgement(dict):
    """Interrompt précisément l'assignation de l'accusé, après le vrai commit."""
    def __init__(self, failures=1):
        super().__init__()
        self.failures = failures

    def __setitem__(self, key, value):
        old = dict.get(self, key)
        if (
            self.failures and isinstance(old, DraftBuffer) and old.pending is not None
            and isinstance(value, DraftBuffer) and value.pending is None
            and not value.conflict and value.row_version == old.row_version + 1
        ):
            self.failures -= 1
            raise InjectedRerun()
        super().__setitem__(key, value)


def interrupt_after_commit(case_draft, state):
    db, cid, ben = case_draft
    initial = read(case_draft)
    buffer = get_draft(state, cid, initial)
    visible = av1_answers(buffer, initial.questionnaire, "Première précision sauvegardée")
    candidate = prepare_draft(buffer, initial.questionnaire, visible, part=1)
    with pytest.raises(InjectedRerun):
        save_draft(state, ben, cid, initial, candidate, database_url=db)
    return initial, candidate


def test_rerun_after_real_commit_is_acknowledged_before_the_next_input(case_draft, Session):
    _, cid, _ = case_draft
    state = InterruptedAcknowledgement()
    initial, candidate = interrupt_after_commit(case_draft, state)
    persisted = read(case_draft)
    assert persisted.row_version == initial.row_version + 1
    assert persisted.responses == candidate
    assert counts(Session)[0] == 1
    # Ce widget a déjà reçu la saisie suivante lorsque le nouveau script démarre.
    widget = f"B_{cid}_other_next"
    state[widget] = "Deuxième précision conservée"
    confirmed = get_draft(state, cid, persisted)
    assert confirmed.pending is None and not confirmed.conflict
    assert confirmed.row_version == persisted.row_version
    assert confirmed.answers == candidate
    assert state[widget] == "Deuxième précision conservée"
    next_visible = copy.deepcopy(confirmed.answers)
    next_visible["cav1"]["ideas"][0]["context"]["other"] = state[widget]
    saved = save(case_draft, state, persisted, next_visible, part=1)
    assert saved.responses["cav1"]["ideas"][0]["note"] == "Première précision sauvegardée"
    assert saved.responses["cav1"]["ideas"][0]["context"]["other"] == "Deuxième précision conservée"
    assert saved.row_version == initial.row_version + 2
    assert counts(Session)[0] == 2


def test_acknowledgement_can_itself_be_interrupted_without_losing_pending(case_draft, Session):
    _, cid, _ = case_draft
    state = InterruptedAcknowledgement(failures=2)
    initial, candidate = interrupt_after_commit(case_draft, state)
    persisted = read(case_draft)
    with pytest.raises(InjectedRerun):
        get_draft(state, cid, persisted)
    # Une nouvelle lecture reprend le même accusé sans créer de version SQL.
    confirmed = get_draft(state, cid, persisted)
    assert confirmed.row_version == initial.row_version + 1
    assert confirmed.answers == candidate
    assert confirmed.pending is None
    assert counts(Session)[0] == 1


def test_interruption_before_pending_assignment_prevents_any_sql_write(case_draft, Session):
    _, cid, _ = case_draft

    class BeforePending(dict):
        armed = True

        def __setitem__(self, key, value):
            if self.armed and isinstance(value, DraftBuffer) and value.pending is not None:
                self.armed = False
                raise InjectedRerun()
            super().__setitem__(key, value)

    state = BeforePending()
    initial = read(case_draft)
    buffer = get_draft(state, cid, initial)
    visible = av1_answers(buffer, initial.questionnaire)
    with pytest.raises(InjectedRerun):
        save(case_draft, state, initial, visible, part=1)
    assert counts(Session)[0] == 0
    assert get_draft(state, cid, read(case_draft)).pending is None
    saved = save(case_draft, state, read(case_draft), visible, part=1)
    assert saved.row_version == initial.row_version + 1
    assert counts(Session)[0] == 1


@pytest.mark.parametrize("same_content", [False, True])
def test_pending_does_not_adopt_a_later_version_even_when_content_matches(case_draft, same_content):
    db, cid, ben = case_draft
    state = InterruptedAcknowledgement()
    initial, candidate = interrupt_after_commit(case_draft, state)
    persisted = read(case_draft)
    rival = copy.deepcopy(candidate)
    if not same_content:
        rival["cav1"]["ideas"][0]["note"] = "Une autre modification"
    # API métier directe : même contenu possible, mais nouvelle version réelle.
    newer = draft_module.save_beneficiary_answers(
        ben, cid, rival, expected_row_version=persisted.row_version, database_url=db,
    )
    assert newer.row_version == initial.row_version + 2
    old = get_draft(state, cid, newer)
    assert old.row_version == initial.row_version
    assert old.pending is not None
    with pytest.raises(OrientationConflict):
        save_draft(state, ben, cid, newer, candidate, database_url=db)
    blocked = get_draft(state, cid, newer)
    assert blocked.conflict and blocked.pending is None
    assert read(case_draft).responses == rival


def test_no_pending_never_adopts_an_identical_answer_saved_elsewhere(case_draft):
    db, cid, ben = case_draft
    initial = read(case_draft)
    state = {}
    buffer = get_draft(state, cid, initial)
    candidate = prepare_draft(buffer, initial.questionnaire, av1_answers(buffer, initial.questionnaire), part=1)
    rival = draft_module.save_beneficiary_answers(
        ben, cid, candidate, expected_row_version=initial.row_version, database_url=db,
    )
    assert get_draft(state, cid, rival).row_version == initial.row_version
    with pytest.raises(OrientationConflict):
        save_draft(state, ben, cid, rival, candidate, database_url=db)
    assert get_draft(state, cid, rival).conflict


def test_indeterminate_result_after_commit_keeps_the_pending_proof(case_draft, monkeypatch, Session):
    db, cid, ben = case_draft
    state = {}
    initial = read(case_draft)
    buffer = get_draft(state, cid, initial)
    candidate = prepare_draft(buffer, initial.questionnaire, av1_answers(buffer, initial.questionnaire), part=1)
    original_save = draft_module.save_beneficiary_answers

    def result_unavailable(*args, **kwargs):
        original_save(*args, **kwargs)
        raise RuntimeError("Résultat interrompu après transaction")

    monkeypatch.setattr(draft_module, "save_beneficiary_answers", result_unavailable)
    with pytest.raises(RuntimeError):
        save_draft(state, ben, cid, initial, candidate, database_url=db)
    confirmed = get_draft(state, cid, read(case_draft))
    assert confirmed.answers == candidate
    assert confirmed.row_version == initial.row_version + 1
    assert confirmed.pending is None and not confirmed.conflict
    assert counts(Session)[0] == 1


def test_pending_is_not_acknowledged_while_real_transaction_is_uncommitted(case_draft, monkeypatch, Session):
    from clarte360_cp.application import preparation as app_preparation

    _, cid, _ = case_draft
    state = {}
    initial = read(case_draft)
    buffer = get_draft(state, cid, initial)
    candidate = prepare_draft(buffer, initial.questionnaire, av1_answers(buffer, initial.questionnaire), part=1)
    original_commit = app_preparation._commit
    observed = []

    def inspect_before_commit(*args, **kwargs):
        # La réponse a été insérée/flushed dans la vraie transaction SQL,
        # mais une autre connexion voit encore la version de départ.
        fresh = read(case_draft)
        pending = get_draft(state, cid, fresh)
        assert fresh.row_version == initial.row_version
        assert pending.row_version == initial.row_version
        assert pending.answers == buffer.answers
        assert pending.pending is not None
        assert pending.pending.answers == candidate
        assert counts(Session)[0] == 0
        observed.append(pending)
        return original_commit(*args, **kwargs)

    monkeypatch.setattr(app_preparation, "_commit", inspect_before_commit)
    saved = save(case_draft, state, initial, candidate, part=1)
    assert len(observed) == 1
    assert saved.row_version == initial.row_version + 1
    assert get_draft(state, cid, saved).pending is None
    assert counts(Session)[0] == 1


def test_latched_conflict_has_priority_even_over_an_exact_pending_match(case_draft, monkeypatch, Session):
    db, cid, ben = case_draft
    state = InterruptedAcknowledgement()
    initial, candidate = interrupt_after_commit(case_draft, state)
    persisted = read(case_draft)
    key = f"rc3_draft_{cid}_{initial.questionnaire_version}"
    # Un verrou de conflit déjà présent doit primer même si la preuve pending
    # aurait satisfait toutes les conditions de récupération de l'accusé.
    blocked = replace(state[key], conflict=True, conflict_message="Rechargement explicite requis")
    state[key] = blocked
    assert get_draft(state, cid, persisted) is blocked
    assert blocked.row_version == initial.row_version
    assert blocked.pending.answers == candidate

    def forbidden_retry(*args, **kwargs):
        raise AssertionError("Aucune écriture après conflit sans rechargement explicite")

    monkeypatch.setattr(draft_module, "save_beneficiary_answers", forbidden_retry)
    with pytest.raises(OrientationConflict, match="Rechargement explicite"):
        save_draft(state, ben, cid, persisted, candidate, database_url=db)
    assert counts(Session)[0] == 1
    resumed = reload_draft(state, cid, persisted)
    assert not resumed.conflict and resumed.pending is None
    assert resumed.answers == candidate
