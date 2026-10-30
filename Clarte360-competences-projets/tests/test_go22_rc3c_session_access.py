"""Accès signé initial, activité réelle et reprise après expiration de session."""
from __future__ import annotations

import copy
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from clarte360_cp.connectors.gestion_actions import LaunchTokenError, build_launch_token
from clarte360_cp.framework.session import (
    SessionExpiredError, reconcile_session_state, resolve_session_launch, touch_activity,
)
from tests.helpers import KEY, payload


T0 = 2_000_000_000
ACC = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_CASE_WRITE", "CP_VALIDATE", "CP_PUBLISH"]
BEN = ["CP_CASE_OPEN", "CP_CASE_READ", "CP_BENEFICIARY_INTERACT", "CP_BENEFICIARY_VALIDATE"]


def signed(*, issued=T0, ttl=900, key=KEY, **kwargs):
    p = payload(**kwargs)
    p.update(iat=issued, exp=issued + ttl)
    return build_launch_token(p, key)


def open_session(state, token, at=T0, *, key=KEY, minutes=15):
    return resolve_session_launch(state, token, key, now_epoch=at, limit_minutes=minutes)


def activity(state, at):
    touch_activity(state, now=datetime.fromtimestamp(at, timezone.utc))


def test_active_session_continues_for_many_interactions_after_link_expiry():
    state = {}
    token = signed(role="BENEFICIAIRE", scopes=BEN)
    initial = open_session(state, token)
    state["ongoing_answer"] = "Texte en cours"
    session_id = state["session_id"]
    for offset in (600, 1200, 1800, 2400, 3000):
        assert open_session(state, token, T0 + offset) == initial
        activity(state, T0 + offset)
    assert state["session_id"] == session_id
    assert state["ongoing_answer"] == "Texte en cours"


def test_expired_link_in_another_browser_is_rejected_without_affecting_active_browser():
    state, new_browser = {}, {}
    token = signed()
    launch = open_session(state, token)
    activity(state, T0 + 800)
    with pytest.raises(LaunchTokenError, match="expiré"):
        open_session(new_browser, token, T0 + 1000)
    assert not new_browser.get("launch_context")
    assert open_session(state, token, T0 + 1000) == launch


@pytest.mark.parametrize("change", [
    {"role": "BENEFICIAIRE", "scopes": BEN},
    {"actor": "OTHER-ACTOR"},
    {"beneficiary": "OTHER-BEN", "action": "OTHER-ACT", "prescription": "OTHER-PRE"},
    {"scopes": ["CP_CASE_OPEN", "CP_CASE_READ"]},
    {},  # un lien renouvelé pour le même dossier est lui aussi vérifié
])
def test_changed_link_discards_all_previous_role_case_and_widget_state(change):
    state = {}
    old = open_session(state, signed(scopes=ACC))
    reconcile_session_state(state, old, "CASE-A", 3)
    state.update(private_note="Ancien dossier", navigation_page="dashboard")
    session_id = state["session_id"]
    new_token = signed(issued=T0 + 10, **change)
    new = open_session(state, new_token, T0 + 10)
    assert state["session_id"] != session_id
    assert state["case_id"] is None
    assert state["navigation_page"] == "home"
    assert "private_note" not in state
    assert state["launch_context"] == new
    assert new.iat == T0 + 10
    if change.get("role") == "BENEFICIAIRE":
        assert not new.has_scope("CP_CASE_WRITE")


@pytest.mark.parametrize("replacement", [
    "", "not-a-token", signed() + "x", signed(ttl=901),
    signed(role="BENEFICIAIRE", scopes=["CP_CASE_OPEN", "CP_CASE_WRITE"]),
])
def test_invalid_replacement_cannot_fall_back_to_old_session(replacement):
    state = {}
    old_token = signed()
    open_session(state, old_token)
    state["private_note"] = "Ancien dossier"
    with pytest.raises(LaunchTokenError):
        open_session(state, replacement, T0 + 100)
    assert not state.get("launch_context")
    assert "private_note" not in state
    with pytest.raises(LaunchTokenError, match="expiré"):
        open_session(state, old_token, T0 + 1000)


def test_key_rotation_invalidates_session_and_requires_new_signature():
    state = {}
    token = signed()
    open_session(state, token)
    with pytest.raises(LaunchTokenError, match="Signature"):
        open_session(state, token, T0 + 10, key="new-key-" * 6)
    assert not state.get("launch_context")
    rotated = signed(issued=T0 + 11, key="new-key-" * 6)
    assert open_session(state, rotated, T0 + 11, key="new-key-" * 6).iat == T0 + 11


def test_automatic_access_checks_do_not_extend_activity_and_timeout_is_sticky():
    state = {}
    token = signed()
    open_session(state, token)
    initial_activity = state["last_activity_at"]
    for offset in range(2, 900, 2):
        open_session(state, token, T0 + offset)
    assert state["last_activity_at"] == initial_activity
    state["private_note"] = "Saisie locale"
    with pytest.raises(SessionExpiredError):
        open_session(state, token, T0 + 900)
    assert "private_note" not in state
    assert not state.get("launch_context")
    # Le rerun provoqué par le fragment doit conserver le motif « session ».
    with pytest.raises(SessionExpiredError):
        open_session(state, token, T0 + 1000)


def test_shorter_configured_timeout_requires_a_renewed_link_even_if_old_link_still_valid():
    state = {}
    old_token = signed()
    open_session(state, old_token, minutes=5)
    with pytest.raises(SessionExpiredError):
        open_session(state, old_token, T0 + 300, minutes=5)
    with pytest.raises(LaunchTokenError):
        open_session(state, "invalid", T0 + 301, minutes=5)
    with pytest.raises(SessionExpiredError):
        open_session(state, old_token, T0 + 302, minutes=5)
    renewed = signed(issued=T0 + 303)
    launch = open_session(state, renewed, T0 + 303, minutes=5)
    assert launch.iat == T0 + 303
    assert state["last_activity_at"] == datetime.fromtimestamp(T0 + 303, timezone.utc).isoformat(timespec="seconds")
    with pytest.raises(SessionExpiredError):
        open_session(state, old_token, T0 + 304, minutes=5)


@pytest.mark.parametrize("bad_activity", [None, "not-a-date", 42, "2039-01-01T00:00:00+00:00"])
def test_missing_corrupt_or_future_activity_fails_closed(bad_activity):
    state = {}
    token = signed()
    open_session(state, token)
    state["last_activity_at"] = bad_activity
    with pytest.raises(SessionExpiredError):
        open_session(state, token, T0 + 10)


def test_reconcile_different_case_removes_unrelated_widgets():
    state = {}
    launch = open_session(state, signed())
    reconcile_session_state(state, launch, "CASE-A", 2)
    state["old_case_field"] = "Texte confidentiel"
    reconcile_session_state(state, launch, "CASE-B", 1)
    assert state["case_id"] == "CASE-B"
    assert "old_case_field" not in state


def test_live_fragment_stops_before_database_read_when_inactive(monkeypatch):
    from clarte360_cp.ui import live_sync

    class Rerun(Exception):
        pass

    class FakeStreamlit:
        def __init__(self, state):
            self.session_state = state
            self.callback = None

        def fragment(self, **kwargs):
            def decorate(fn):
                self.callback = fn
                return fn
            return decorate

        def caption(self, *args):
            pass

        def rerun(self, *, scope):
            assert scope == "app"
            raise Rerun()

    state, reads = {}, []
    clock = [T0]
    token = signed()
    launch = open_session(state, token)
    reconcile_session_state(state, launch, "CASE-A", 1)
    fake = FakeStreamlit(state)
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    monkeypatch.delenv("CLARTE360_GO21_SYNC_PROBE", raising=False)
    monkeypatch.setattr(live_sync, "resolve_launch_context", lambda: open_session(state, token, clock[0]))

    def read(case_id):
        reads.append(case_id)
        return SimpleNamespace(latest_change_at=None)

    monkeypatch.setattr(live_sync, "build_live_sync", read)
    live_sync.render_live_sync_status(launch, "CASE-A")
    clock[0] = T0 + 600
    fake.callback()
    assert reads == ["CASE-A", "CASE-A"]
    clock[0] = T0 + 900
    with pytest.raises(Rerun):
        fake.callback()
    assert reads == ["CASE-A", "CASE-A"]
    assert not state.get("launch_context")


ENTRY_APP = """
import streamlit as st
from clarte360_cp.connectors import LaunchTokenError
from clarte360_cp.ui.entry import resolve_launch_context
from clarte360_cp.framework.session import initialize_session, touch_activity
try:
    launch = resolve_launch_context()
except LaunchTokenError as exc:
    st.error(str(exc))
    st.stop()
initialize_session(launch, "CASE-" + launch.prescription_id, 1)
touch_activity()
st.write(launch.actor_role.value)
st.text_input("Réponse en cours", key="current_draft")
st.button("Continuer", key="continue")
"""


def streamlit_entry(monkeypatch, token):
    from streamlit.testing.v1 import AppTest
    from clarte360_cp.framework import session as session_module

    clock = [T0]

    class ControlledDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(clock[0], tz)

    monkeypatch.setattr(session_module, "datetime", ControlledDatetime)
    app = AppTest.from_string(ENTRY_APP)
    app.secrets["COMPETENCES_PROJETS_CONNECTOR"] = {"LAUNCH_SIGNING_KEY": KEY}
    app.query_params.update(mode="accompagnement", launch=token)
    app.run()
    assert not app.exception
    assert not app.error
    return app, clock


def test_actual_streamlit_reruns_keep_active_answers_then_purge_on_new_role(monkeypatch):
    token = signed(scopes=ACC)
    app, clock = streamlit_entry(monkeypatch, token)
    app.text_input[0].set_value("Réponse du premier rôle").run()
    clock[0] = T0 + 800
    app.button[0].click().run()
    clock[0] = T0 + 1000
    app.button[0].click().run()
    assert not app.exception
    assert not app.error
    assert app.text_input[0].value == "Réponse du premier rôle"
    app.query_params["launch"] = signed(issued=T0 + 1000, role="BENEFICIAIRE", scopes=BEN)
    app.run()
    assert not app.exception
    assert not app.error
    assert app.text_input[0].value == ""
    assert app.session_state["launch_context"].actor_role.value == "BENEFICIAIRE"


def test_actual_streamlit_idle_timeout_and_new_link_reestablish_access(monkeypatch):
    app, clock = streamlit_entry(monkeypatch, signed())
    clock[0] = T0 + 900
    app.button[0].click().run()
    assert not app.exception
    assert "session a expiré" in app.error[0].value
    assert not app.text_input
    clock[0] = T0 + 901
    app.query_params["launch"] = signed(issued=clock[0])
    app.run()
    assert not app.exception
    assert not app.error
    assert len(app.text_input) == 1
    app.query_params["mode"] = "autre"
    app.run()
    assert not app.exception
    assert app.error
    assert not app.text_input
    assert "launch_context" not in app.session_state


@pytest.mark.parametrize("recipe", [False, True])
def test_recovery_help_matches_runtime_without_exposing_recipe_details_elsewhere(monkeypatch, recipe):
    from clarte360_cp.ui.entry import render_access_recovery_help

    messages = []
    monkeypatch.setitem(sys.modules, "streamlit", SimpleNamespace(info=messages.append))
    if recipe:
        monkeypatch.setenv("CLARTE360_GO21_SYNC_PROBE", "1")
    else:
        monkeypatch.delenv("CLARTE360_GO21_SYNC_PROBE", raising=False)
    render_access_recovery_help()
    assert "réponses déjà enregistrées" in messages[0]
    if recipe:
        assert "1_OUVRIR_ACCOMPAGNATEUR.cmd" in messages[0]
        assert "2_OUVRIR_BENEFICIAIRE.cmd" in messages[0]
        assert "ne relancez pas" in messages[0]
    else:
        assert "Gestion des Actions" in messages[0]
        assert ".cmd" not in messages[0]
        assert "recette" not in messages[0]


def prepare_persisted_case(engine):
    from clarte360_cp.application import bootstrap_case
    from clarte360_cp.application.preparation import create_questionnaire_v2, lock_and_publish_questionnaire

    db = str(engine.url)
    coach = open_session({}, signed(scopes=ACC))
    state = {}
    token = signed(role="BENEFICIAIRE", scopes=BEN)
    ben = open_session(state, token)
    boot = bootstrap_case(coach, database_url=db)
    reconcile_session_state(state, ben, boot.case_id, boot.row_version)
    created = create_questionnaire_v2(coach, boot.case_id, {}, database_url=db)
    published = lock_and_publish_questionnaire(
        coach, boot.case_id, expected_row_version=created.row_version, database_url=db,
    )
    return db, coach, state, token, boot.case_id, published


def free_answers(questionnaire):
    from clarte360_cp.domain.preparation import empty_answers

    answers = empty_answers(questionnaire)
    answers["cav1"]["no_idea"] = True
    answers["cav1_done"] = True
    answers["cav2"]["valeurs"]["free"] = ["Respect"]
    answers["cav2"]["moteurs"]["free"] = ["Comprendre les choses"]
    answers["cav2"]["preferences"]["free"] = "Conserver des échanges réguliers"
    answers["cav2"]["preferences"]["situation"] = "PAS_IDENTIFIEE"
    return answers


def test_submission_after_link_expiry_reaches_accompanist_r1(engine):
    from clarte360_cp.application.preparation import (
        read_preparation, save_beneficiary_answers, submit_beneficiary_answers,
    )

    db, coach, state, token, cid, published = prepare_persisted_case(engine)
    ben = open_session(state, token, T0 + 800)
    activity(state, T0 + 800)
    answers = free_answers(published.questionnaire)
    first = save_beneficiary_answers(ben, cid, answers, expected_row_version=published.row_version, database_url=db)
    # L'ouverture originale a plus de 900 s ; la dernière activité a 200 s.
    ben = open_session(state, token, T0 + 1000)
    activity(state, T0 + 1000)
    answers["cav2_done"] = True
    second = save_beneficiary_answers(ben, cid, answers, expected_row_version=first.row_version, database_url=db)
    submitted = submit_beneficiary_answers(ben, cid, expected_row_version=second.row_version, database_url=db)
    received = read_preparation(coach, cid, database_url=db)
    assert received.active_response_version == submitted.active_response_version
    assert received.active_answers["cav2"]["valeurs"]["free"] == ["Respect"]
    assert received.active_answers["cav2_done"] is True


def test_renewed_link_after_idle_timeout_recovers_persisted_answers_and_same_case(engine):
    from clarte360_cp.application import bootstrap_case
    from clarte360_cp.application.preparation import read_preparation, save_beneficiary_answers

    db, coach, state, token, cid, published = prepare_persisted_case(engine)
    ben = open_session(state, token, T0 + 100)
    activity(state, T0 + 100)
    answers = free_answers(published.questionnaire)
    saved = save_beneficiary_answers(ben, cid, answers, expected_row_version=published.row_version, database_url=db)
    expected = copy.deepcopy(saved.active_answers)
    state["unsaved_local_widget"] = "Ne doit pas survivre à la déconnexion"
    with pytest.raises(SessionExpiredError):
        open_session(state, token, T0 + 1000)
    renewed = signed(issued=T0 + 1001, role="BENEFICIAIRE", scopes=BEN)
    resumed = open_session(state, renewed, T0 + 1001)
    boot = bootstrap_case(resumed, database_url=db)
    reconcile_session_state(state, resumed, boot.case_id, boot.row_version)
    recovered = read_preparation(resumed, boot.case_id, database_url=db)
    assert boot.case_id == cid
    assert "unsaved_local_widget" not in state
    assert recovered.active_answers == expected
    assert recovered.row_version == saved.row_version
