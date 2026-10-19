"""GO4 Streamlit paths against isolated fictitious SQLite, no SMTP/network.

These are functional widget tests, not claims of a human keyboard/zoom review.
The R24 browser checks remain explicitly documented in the delivery evidence.
"""
from pathlib import Path
import uuid

import pytest
from streamlit.testing.v1 import AppTest

from db import make_engine, init_db, execute, one, q, utcnow_iso
import quality_service as quality


@pytest.fixture
def ui_ctx(tmp_path):
    path = tmp_path / "ui_fictive.sqlite"
    engine = make_engine(f"sqlite:///{path}")
    init_db(engine)
    now = utcnow_iso()
    org = execute(engine, "INSERT INTO organizations(name,active,created_at,updated_at) VALUES('Organisme fictif UI',1,:n,:n)", {"n": now})
    execute(engine, "INSERT INTO admins(email,password_hash,active,role,created_at) VALUES('ui@example.invalid','not-a-real-login',1,'ADMIN',:n)", {"n": now})
    actor = quality.QualityActor("ADMIN", "ui@example.invalid", org)
    yield engine, actor, path
    engine.dispose()


def widget(at, kind, label):
    candidates = [item for item in getattr(at, kind) if item.label == label]
    assert len(candidates) == 1, (kind, label, [item.label for item in getattr(at, kind)])
    return candidates[0]


def app(ui_ctx, renderer="plan"):
    _, actor, path = ui_ctx
    script = f'''
from db import make_engine
import quality_service as quality
from quality_ui import render_quality_plan, render_quality_satisfaction, render_quality_watch, render_quality_legacy
engine=make_engine({f"sqlite:///{path}"!r})
actor=quality.QualityActor('ADMIN','ui@example.invalid',{actor.organization_id})
render_quality_{renderer}(engine,actor,key='ui_test')
'''
    return AppTest.from_string(script, default_timeout=20).run()


def seed(ui_ctx, *, step=False):
    engine, actor, _ = ui_ctx
    event_id = quality.create_action(engine, actor, "Consigne à vérifier", "Contexte fictif", command_id=uuid.uuid4().hex)
    execute(engine, "UPDATE quality_events SET public_id='Q-003' WHERE id=:i", {"i": event_id})
    if step:
        quality.add_step(engine, actor, event_id, "Tester la nouvelle consigne", expected_version=1)
    return event_id


def assert_no_exception(at):
    assert not at.exception, [item.message for item in at.exception]


def test_r01_create_preventive_without_training(ui_ctx):
    at = app(ui_ctx)
    assert_no_exception(at)
    widget(at, "button", "Nouvelle action").click().run()
    assert_no_exception(at)
    assert widget(at, "selectbox", "Formation ou bilan").value is None
    widget(at, "text_input", "Action à réaliser").set_value("Préparer l’accessibilité en amont")
    widget(at, "button", "Créer").click().run()
    assert_no_exception(at)
    rows = quality.list_actions(ui_ctx[0], ui_ctx[1])
    assert len(rows) == 1
    assert rows[0]["action_id"] is None and rows[0]["action_nature"] == "PREVENTIVE"
    assert any("enregistrée" in item.value for item in at.success)


def test_creation_error_keeps_entered_context(ui_ctx):
    at = app(ui_ctx)
    widget(at, "button", "Nouvelle action").click().run()
    widget(at, "text_area", "Contexte ou résultat attendu (facultatif)").set_value("Texte à conserver")
    widget(at, "button", "Créer").click().run()
    assert_no_exception(at)
    assert at.error
    assert widget(at, "text_area", "Contexte ou résultat attendu (facultatif)").value == "Texte à conserver"
    assert quality.list_actions(ui_ctx[0], ui_ctx[1]) == []


def test_r02_q003_one_window_explicit_step_and_summary(ui_ctx):
    event_id = seed(ui_ctx, step=True)
    at = app(ui_ctx)
    widget(at, "button", "Clôturer").click().run()
    assert_no_exception(at)
    choice = widget(at, "selectbox", "Issue — Tester la nouvelle consigne")
    assert choice.value == "", "No outcome may be preselected"
    widget(at, "text_area", "Travail réalisé et résultat constaté").set_value("Consigne testée ; comprise sans explication supplémentaire.")
    choice.select("VERIFIED")
    widget(at, "button", "Confirmer la clôture").click().run()
    assert_no_exception(at)
    result = quality.get_action(ui_ctx[0], ui_ctx[1], event_id)
    assert result["event"]["status"] == "CLOTURE"
    assert result["steps"][0]["status"] == "TERMINEE"
    assert len(quality.list_actions(ui_ctx[0], ui_ctx[1])) == 1
    assert widget(at, "button", "Rouvrir")


@pytest.mark.parametrize("choice", ["", "REMAINING", "ABANDONED"])
def test_r03_unfinished_or_unjustified_step_never_partially_closes(ui_ctx, choice):
    event_id = seed(ui_ctx, step=True)
    before = quality.get_action(ui_ctx[0], ui_ctx[1], event_id)
    at = app(ui_ctx)
    widget(at, "button", "Clôturer").click().run()
    widget(at, "text_area", "Travail réalisé et résultat constaté").set_value("Bilan provisoire conservé")
    widget(at, "selectbox", "Issue — Tester la nouvelle consigne").select(choice)
    widget(at, "button", "Confirmer la clôture").click().run()
    assert_no_exception(at)
    assert at.error
    after = quality.get_action(ui_ctx[0], ui_ctx[1], event_id)
    assert after["event"]["row_version"] == before["event"]["row_version"]
    assert after["event"]["status"] == "NOUVEAU"
    assert after["steps"] == before["steps"]
    assert widget(at, "text_area", "Travail réalisé et résultat constaté").value == "Bilan provisoire conservé"


def test_r04_update_without_change_creates_no_event(ui_ctx):
    event_id = seed(ui_ctx)
    before = quality.get_action(ui_ctx[0], ui_ctx[1], event_id)
    at = app(ui_ctx)
    widget(at, "button", "Mettre à jour").click().run()
    widget(at, "button", "Enregistrer").click().run()
    assert_no_exception(at)
    after = quality.get_action(ui_ctx[0], ui_ctx[1], event_id)
    assert after["history"] == before["history"]
    assert after["event"]["row_version"] == before["event"]["row_version"]
    assert any("Aucun changement" in item.value for item in at.success)


def test_r04_comment_only_is_an_advance(ui_ctx):
    event_id = seed(ui_ctx)
    at = app(ui_ctx)
    widget(at, "button", "Mettre à jour").click().run()
    widget(at, "text_area", "Votre avancée").set_value("Préparation en cours, retour attendu.")
    widget(at, "button", "Enregistrer").click().run()
    assert_no_exception(at)
    result = quality.get_action(ui_ctx[0], ui_ctx[1], event_id)
    assert result["event"]["status"] == "NOUVEAU"
    assert [row["message"] for row in result["messages"]] == ["Préparation en cours, retour attendu."]
    assert not any(row["change_kind"] == "STATUT" for row in result["history"])


def test_concurrent_update_keeps_draft_and_requires_explicit_reread(ui_ctx):
    engine, actor, _ = ui_ctx
    event_id = seed(ui_ctx)
    at = app(ui_ctx)
    widget(at, "button", "Mettre à jour").click().run()
    widget(at, "text_area", "Votre avancée").set_value("Mon texte en cours")
    quality.update_action(engine, actor, event_id, expected_version=1, status="EN_ATTENTE")
    widget(at, "button", "Enregistrer").click().run()
    assert_no_exception(at)
    assert at.error and at.warning
    assert widget(at, "text_area", "Votre avancée").value == "Mon texte en cours"
    assert quality.get_action(engine, actor, event_id)["messages"] == []
    widget(at, "button", "Relire la version actualisée").click().run()
    assert_no_exception(at)
    assert widget(at, "selectbox", "Statut").value == "EN_ATTENTE"
    widget(at, "button", "Enregistrer").click().run()
    assert_no_exception(at)
    result = quality.get_action(engine, actor, event_id)
    assert result["event"]["status"] == "EN_ATTENTE"
    assert result["messages"][-1]["message"] == "Mon texte en cours"


def test_r06_close_and_reopen_same_reference(ui_ctx):
    event_id = seed(ui_ctx)
    at = app(ui_ctx)
    widget(at, "button", "Clôturer").click().run()
    widget(at, "text_area", "Travail réalisé et résultat constaté").set_value("Résultat constaté et validé")
    widget(at, "button", "Confirmer la clôture").click().run()
    widget(at, "button", "Rouvrir").click().run()
    widget(at, "text_area", "Pourquoi rouvrir ?").set_value("Un retour nouveau reste à traiter")
    widget(at, "button", "Rouvrir cette action").click().run()
    assert_no_exception(at)
    result = quality.get_action(ui_ctx[0], ui_ctx[1], event_id)
    assert result["event"]["public_id"] == "Q-003"
    assert result["event"]["status"] == "EN_TRAITEMENT"
    assert any("Résultat constaté" in (row.get("after_json") or "") for row in result["history"])


def test_empty_metrics_show_hot_cold_and_explicit_unavailable(ui_ctx):
    at = app(ui_ctx, "satisfaction")
    assert_no_exception(at)
    assert not at.error
    labels = {item.label: item.value for item in at.metric}
    assert labels["À chaud"] == "Non disponible"
    assert labels["À froid"] == "Non disponible"


def actor_app(ui_ctx, actor):
    _, _, path = ui_ctx
    script = f'''
from db import make_engine
import quality_service as quality
from quality_ui import render_quality_plan
engine=make_engine({f"sqlite:///{path}"!r})
actor=quality.QualityActor({actor.role!r},{actor.subject_id!r},{actor.organization_id})
render_quality_plan(engine,actor,key='ui_test')
'''
    return AppTest.from_string(script, default_timeout=20).run()


def training_with_trainer(ui_ctx):
    engine, actor, _ = ui_ctx
    now = utcnow_iso()
    trainer = execute(engine, "INSERT INTO trainers(full_name,email,active,created_at,updated_at) VALUES('Intervenant fictif','trainer-ui@example.invalid',1,:n,:n)", {"n": now})
    training = execute(engine, """INSERT INTO actions(action_no,title,nature,mode,planned_hours,organization_id,trainer_id,status,created_at,updated_at)
        VALUES('FICTIF-UI','Formation fictive','FORMATION','COLLECTIF',1,:o,:t,'ACTIVE',:n,:n)""",
        {"o": actor.organization_id, "t": trainer, "n": now})
    return training, quality.QualityActor("TRAINER", trainer, actor.organization_id)


def test_r05_assign_accept_submit_ui_rights(ui_ctx):
    engine, admin, _ = ui_ctx
    _, trainer = training_with_trainer(ui_ctx)
    event_id = seed(ui_ctx)
    at = app(ui_ctx)
    widget(at, "button", "Confier").click().run()
    choice = widget(at, "selectbox", "À qui ?")
    assert choice.value is None
    # Only existing accounts provided by the service populate the selector.
    candidates = quality.eligible_delegates(engine, admin, event_id)
    choice.select(next(index for index, person in enumerate(candidates) if person["role"] == "TRAINER"))
    widget(at, "text_area", "Résultat attendu").set_value("Vérifier le résultat et rendre compte")
    widget(at, "button", "Confier et notifier").click().run()
    assert_no_exception(at)
    assert quality.get_action(engine, admin, event_id)["event"]["delegation_status"] == "PENDING"
    at_trainer = actor_app(ui_ctx, trainer)
    assert_no_exception(at_trainer)
    assert not any(item.label == "Clôturer" for item in at_trainer.button)
    widget(at_trainer, "button", "Accepter").click().run()
    widget(at_trainer, "button", "Accepter la mission").click().run()
    assert_no_exception(at_trainer)
    widget(at_trainer, "button", "Prêt à valider").click().run()
    widget(at_trainer, "text_area", "Travail réalisé et résultat à valider").set_value("Consigne essayée, résultat conforme")
    widget(at_trainer, "button", "Transmettre pour validation").click().run()
    assert_no_exception(at_trainer)
    event = quality.get_action(engine, admin, event_id)["event"]
    assert event["delegation_status"] == "SUBMITTED" and event["status"] == "A_VERIFIER"


def test_r13_client_ui_only_own_request_and_response(ui_ctx):
    engine, admin, _ = ui_ctx
    training, _ = training_with_trainer(ui_ctx)
    now = utcnow_iso()
    actors = []
    for ordinal in (1, 2):
        contact = execute(engine, """INSERT INTO crm_contacts(public_id,first_name,last_name,email,company,status,created_at,updated_at)
            VALUES(:pid,'Contact','Fictif',:email,'Même entreprise fictive','CLIENT',:n,:n)""",
            {"pid": f"CONTACT-UI-{ordinal}", "email": f"client-{ordinal}@example.invalid", "n": now})
        account = execute(engine, """INSERT INTO client_portal_accounts(crm_contact_id,email,password_hash,active,created_at,updated_at)
            VALUES(:contact,:email,'fictive-password-not-for-login',1,:n,:n)""",
            {"contact": contact, "email": f"client-{ordinal}@example.invalid", "n": now})
        execute(engine, """INSERT INTO client_action_grants(account_id,action_id,role,granted_at,granted_by)
            VALUES(:account,:action,'CONTACT_ADMIN',:n,'ui@example.invalid')""", {"account": account, "action": training, "n": now})
        actors.append(quality.QualityActor("CLIENT", account, admin.organization_id))
    mine = quality.create_action(engine, actors[0], "Ma demande personnelle", "Mon contexte", command_id=uuid.uuid4().hex)
    quality.create_action(engine, actors[1], "Demande autre contact invisible", "Confidentiel", command_id=uuid.uuid4().hex)
    quality.update_action(engine, admin, mine, expected_version=1, comment="Note interne secrète", audience="INTERNAL")
    at = actor_app(ui_ctx, actors[0])
    assert_no_exception(at)
    choice = widget(at, "selectbox", "Ouvrir une action")
    assert len(choice.options) == 1 and "Ma demande personnelle" in choice.options[0]
    assert "Demande autre contact invisible" not in str(at)
    assert "Note interne secrète" not in str(at)
    assert not any(item.label in ("Clôturer", "Confier", "Examiner la suppression unitaire") for item in at.button)
    widget(at, "button", "Répondre").click().run()
    assert not any(item.label in ("Statut", "Qualification des données", "Contexte") for item in at.selectbox)
    widget(at, "text_area", "Votre réponse").set_value("Voici un complément")
    widget(at, "button", "Enregistrer").click().run()
    assert_no_exception(at)
    assert quality.get_action(engine, actors[0], mine)["messages"][-1]["message"] == "Voici un complément"


def test_watch_empty_and_source_inactive_until_configured(ui_ctx):
    import quality_watch as watch
    at = app(ui_ctx, "watch")
    assert_no_exception(at)
    assert not at.error
    widget(at, "text_input", "Nom de la source").set_value("Source fictive non activée")
    widget(at, "text_input", "Lien officiel HTTPS").set_value("https://example.com/fictive-feed.xml")
    widget(at, "button", "Enregistrer la source").click().run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    source = watch.list_sources(ui_ctx[0], ui_ctx[1])[0]
    assert not source["active"] and not source["configuration_validated"]
    assert widget(at, "button", "Contrôler cette source maintenant").disabled
    assert watch.list_runs(ui_ctx[0], ui_ctx[1]) == []


def test_watch_source_edit_preserves_exact_point_zero(ui_ctx):
    import quality_watch as watch
    engine, actor, _ = ui_ctx
    source_id = watch.save_source(engine, actor, name="Source avec point zéro", category="TECHNIQUE",
        url="https://example.com/feed.xml", point_zero="2026-10-19T09:08:07.123456+00:00")
    before = watch.list_sources(engine, actor)[0]
    at = app(ui_ctx, "watch")
    widget(at, "selectbox", "Ajouter ou modifier une source").select(source_id).run()
    widget(at, "text_input", "Nom de la source").set_value("Nom corrigé sans toucher au point zéro")
    widget(at, "button", "Enregistrer la source").click().run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    after = watch.list_sources(engine, actor)[0]
    assert after["name"] == "Nom corrigé sans toucher au point zéro"
    assert after["point_zero"] == before["point_zero"]


def test_watch_source_concurrent_edit_retains_draft_and_read_version(ui_ctx):
    import quality_watch as watch
    engine, actor, _ = ui_ctx
    url = "https://example.com/feed.xml"
    source_id = watch.save_source(engine, actor, name="Nom initial", category="TECHNIQUE", url=url)
    at = app(ui_ctx, "watch")
    widget(at, "selectbox", "Ajouter ou modifier une source").select(source_id).run()
    widget(at, "text_input", "Nom de la source").set_value("Mon brouillon conservé")
    watch.save_source(engine, actor, source_id=source_id, expected_version=1, name="Nom initial", category="TECHNIQUE", url=url, scope="Périmètre actualisé par un autre administrateur")
    widget(at, "button", "Enregistrer la source").click().run()
    assert_no_exception(at)
    assert at.error and at.warning
    assert widget(at, "text_input", "Nom de la source").value == "Mon brouillon conservé"
    assert watch.list_sources(engine, actor)[0]["name"] == "Nom initial"
    widget(at, "button", "Relire : La source de veille").click().run()
    assert_no_exception(at)
    assert widget(at, "text_area", "Périmètre concerné").value == "Périmètre actualisé par un autre administrateur"
    assert widget(at, "text_input", "Nom de la source").value == "Mon brouillon conservé"
    widget(at, "button", "Enregistrer la source").click().run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    source = watch.list_sources(engine, actor)[0]
    assert source["scope"] == "Périmètre actualisé par un autre administrateur"
    assert source["name"] == "Mon brouillon conservé"


def test_watch_unused_source_removal_requires_reason(ui_ctx):
    import quality_watch as watch
    engine, actor, _ = ui_ctx
    source_id = watch.save_source(engine, actor, name="Source inutilisée", category="TECHNIQUE", url="https://example.com/feed.xml")
    at = app(ui_ctx, "watch")
    widget(at, "selectbox", "Ajouter ou modifier une source").select(source_id).run()
    widget(at, "button", "Retirer cette source").click().run()
    assert_no_exception(at)
    assert at.error and len(watch.list_sources(engine, actor)) == 1
    widget(at, "text_area", "Motif du retrait de la source").set_value("Source fictive créée en doublon pour le contrôle")
    widget(at, "button", "Retirer cette source").click().run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    assert watch.list_sources(engine, actor) == []


def test_legacy_unknown_organization_is_adopted_only_after_explicit_selection(ui_ctx):
    engine, actor, _ = ui_ctx
    source_id = execute(engine, """INSERT INTO quality_issues(issue_type,title,description,created_at)
        VALUES('AMELIORATION','Source historique générale','Texte historique intact',:n)""", {"n": utcnow_iso()})
    at = app(ui_ctx, "legacy")
    widget(at, "button", "Intégrer les références historiques de cet organisme").click().run()
    assert_no_exception(at)
    assert quality.list_actions(engine, actor) == []
    selection = widget(at, "multiselect", "Anciennes sources à affecter à cet organisme")
    assert selection.value == []
    assert widget(at, "button", "Affecter au contexte Organisme fictif UI").disabled
    selection.set_value([("QUALITY_ISSUE", source_id)]).run()
    widget(at, "button", "Affecter au contexte Organisme fictif UI").click().run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    rows = quality.list_actions(engine, actor)
    assert len(rows) == 1 and rows[0]["description"] == "Texte historique intact"
    widget(at, "button", "Intégrer les références historiques de cet organisme").click().run()
    assert len(quality.list_actions(engine, actor)) == 1


def test_legacy_ambiguous_source_requires_explicit_target_and_keeps_one_line(ui_ctx):
    engine, actor, _ = ui_ctx
    event_id = quality.create_action(engine, actor, "Même contexte historique", "Contenu conservé", command_id="ambiguous-ui")
    source_id = execute(engine, """INSERT INTO quality_issues(issue_type,title,description,created_at)
        VALUES('AMELIORATION','Même contexte historique','Contenu conservé',:n)""", {"n": utcnow_iso()})
    at = app(ui_ctx, "legacy")
    widget(at, "button", "Intégrer les références historiques de cet organisme").click().run()
    widget(at, "multiselect", "Anciennes sources à affecter à cet organisme").set_value([("QUALITY_ISSUE", source_id)]).run()
    widget(at, "button", "Affecter au contexte Organisme fictif UI").click().run()
    assert_no_exception(at)
    assert len(quality.list_actions(engine, actor)) == 1
    choose = widget(at, "selectbox", "Source historique à rapprocher")
    assert choose.value is None
    choose.select(("QUALITY_ISSUE", source_id)).run()
    target = widget(at, "selectbox", "Action existante correspondant à cette source")
    assert target.value is None
    target.select(event_id).run()
    widget(at, "button", "Confirmer cette correspondance historique").click().run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    linked = one(engine, "SELECT quality_event_id FROM quality_source_links WHERE source_kind='QUALITY_ISSUE' AND source_id=:i", {"i": source_id})
    assert linked["quality_event_id"] == event_id
    assert len(quality.list_actions(engine, actor)) == 1


def test_named_referent_grant_then_inactive_account_revocation(ui_ctx):
    engine, actor, _ = ui_ctx
    _, trainer = training_with_trainer(ui_ctx)
    event_id = seed(ui_ctx)
    at = app(ui_ctx)
    widget(at, "selectbox", "Référent habilité pour cette action").select(("TRAINER", str(trainer.subject_id))).run()
    widget(at, "checkbox", "Autoriser la lecture des notes internes").check()
    widget(at, "checkbox", "Autoriser la validation et la clôture de cette action").check()
    widget(at, "button", "Enregistrer cette habilitation").click().run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    grant = quality.access_grants(engine, actor, event_id)[0]
    assert grant["can_internal"] and grant["can_validate"] and not grant["revoked_at"]
    execute(engine, "UPDATE trainers SET active=0 WHERE id=:i", {"i": trainer.subject_id})
    at.run()
    widget(at, "checkbox", "Révoquer cet accès nominatif").check()
    widget(at, "button", "Enregistrer cette habilitation").click().run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    assert quality.access_grants(engine, actor, event_id)[0]["revoked_at"]


def test_full_application_quality_navigation_on_fictitious_db(ui_ctx):
    _, _, path = ui_ctx
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=25)
    at.secrets["database"] = {"url": f"sqlite:///{path}"}
    at.secrets["email"] = {"enabled": False}
    at.session_state["admin_email"] = "ui@example.invalid"
    at.session_state["admin_workspace"] = "general"
    at.session_state["nav"] = "Qualité"
    at.session_state["qm_org"] = "Organisme fictif UI"
    at.run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    assert {item.label for item in at.tabs} >= {"Plan d’actions unique", "Enquêtes et indicateurs", "Veille", "Historique"}
    assert any(item.label == "Nouvelle action" for item in at.button)


@pytest.mark.parametrize("decision", ["ACTION", "NO_ACTION"])
def test_r07_watch_decision_widget_one_action_or_motivated_no_action(ui_ctx, decision):
    import json
    import socket
    from datetime import datetime, timezone
    import quality_watch as watch
    engine, actor, _ = ui_ctx
    url = "https://feeds.example.com/ui-notices.json"
    sid = watch.save_source(engine, actor, name="Avis fictifs", category="TECHNOLOGIE", url=url,
        format="JSON", active=True, configuration_validated=True)
    payload = {"items": [{"id": "ui-notice-1", "title": "Modification fictive à examiner",
        "summary": "Contexte public fictif", "url": "https://feeds.example.com/notice/1",
        "published_at": "2026-10-19T09:00:00+00:00", "effective_at": "2026-11-01T00:00:00+00:00"}]}
    def transport(target, *, timeout, max_bytes):
        return watch.HttpResponse(200, {"content-type": "application/json"}, json.dumps(payload).encode())
    def resolver(host, port, *, type):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    watch.collect_source(engine, actor, sid, now=datetime(2026, 10, 19, 10, tzinfo=timezone.utc),
                         transport=transport, resolver=resolver)
    original = watch.list_items(engine, actor)[0]
    at = app(ui_ctx, "watch")
    assert_no_exception(at)
    widget(at, "radio", "Décision").set_value(decision)
    widget(at, "text_area", "Analyse / motif de la décision").set_value("Applicable à notre périmètre" if decision == "ACTION" else "Vérification du périmètre : aucune adaptation nécessaire")
    widget(at, "button", "Enregistrer la décision").click().run()
    assert_no_exception(at)
    assert not at.error, [item.value for item in at.error]
    assert len(quality.list_actions(engine, actor)) == (1 if decision == "ACTION" else 0)
    revised = watch.list_items(engine, actor)[0]
    assert revised["decision"] == decision
    for field in ("id", "content_sha256", "title", "summary", "url"):
        assert revised[field] == original[field]


def test_r12_filter_real_rows_and_counts_keep_same_scope(ui_ctx):
    engine, actor, _ = ui_ctx
    real = seed(ui_ctx)
    quality.create_action(engine, actor, "Essai distinct", classification="TEST", command_id=uuid.uuid4().hex)
    at = app(ui_ctx)
    widget(at, "selectbox", "Données du plan").select("REAL").run()
    assert_no_exception(at)
    rows = at.dataframe[0].value
    assert len(rows) == 1 and rows.iloc[0]["Référence"] == "Q-003"
    assert next(item for item in at.metric if item.label == "Actions").value == "1"
    csv = quality.export_plan_csv(engine, actor, classification="REAL").decode("utf-8-sig")
    assert "Q-003" in csv and "Essai distinct" not in csv


@pytest.mark.parametrize("role", ["TRAINER", "BENEFICIARY", "CLIENT"])
def test_general_quality_notification_routes_without_training_id(role):
    import ast
    from types import SimpleNamespace
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text()
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_j4_notification_destination")
    namespace = {"st": SimpleNamespace(session_state={})}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app-quality-notification", "exec"), namespace)
    namespace["_j4_notification_destination"](role, {"target_kind": "QUALITY", "target_id": 7, "action_id": None})
    state = namespace["st"].session_state
    assert state["j4_focus_event_id"] == 7
    if role == "TRAINER":
        assert state["_j6_next_trainer_view"] == "Mes échanges"
    elif role == "BENEFICIARY":
        assert state["p3_beneficiary_action_id"] is None and state["p3_screen_beneficiary"] == "reports"
    else:
        assert state["p4_client_action_id"] is None and state["p3_screen_client_None"] == "quality"


def test_r24_native_labels_and_no_embedded_untrusted_html():
    source = (Path(__file__).resolve().parents[1] / "quality_ui.py").read_text()
    assert "unsafe_allow_html" not in source
    assert 'st.form(' in source and 'st.dialog(' in source
    assert 'index=0, format_func=options.get' in source
    assert 'st.error(str(exc))' in source
    assert 'Relire la version actualisée' in source
    assert 'use_container_width=True' in source
