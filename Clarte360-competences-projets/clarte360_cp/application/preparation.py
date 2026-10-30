"""GO22 RC2 - Q verrouille, R1 beneficiaire et R2 revue conjointe.

Cette couche est entierement deterministe. Aucune connexion IA, SMTP ou
inter-application fictive. Le Hub devra fournir des sources verifiees et un
lancement signe, sans duplication de PDF.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from clarte360_cp.application.orientation import _context, OrientationAccessDenied, OrientationConflict
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.domain.preparation import (
    SCHEMA_Q, difference, empty_answers, fingerprint, generate_questionnaire,
    valid_answers, valid_questionnaire, SCHEMA_Q_V2, SCHEMA_R_V2, generate_questionnaire_v2, public_questionnaire_v2,
)
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import (
    AuditEvent, Cav3Analysis, PreparationQuestionnaire, PreparationResponse, PreparationState, Validation,
)


@dataclass(frozen=True)
class PreparationView:
    questionnaire: dict | None
    questionnaire_locked: bool
    questionnaire_version: int | None
    row_version: int
    invitation_open: bool
    stage: str
    responses: dict | None
    response_status: str | None
    active_answers: dict | None
    active_response_version: int | None
    reviewed_in_session: bool
    joint_draft: dict | None
    source_count: int


def _doc(obj) -> dict | None:
    return json.loads(obj.content_json) if obj else None


def _q(session, state):
    return session.get(PreparationQuestionnaire, state.questionnaire_id) if state and state.questionnaire_id else None


def _r(session, identity):
    return session.get(PreparationResponse, identity) if identity else None


def _data(session, state, *, beneficiary: bool = False) -> PreparationView:
    q = _q(session, state)
    invited = bool(state and state.invitation_open and q and q.state == "VERROUILLE")
    if beneficiary and not invited:
        return PreparationView(None, False, None, state.row_version if state else 0, False,
                               "EN_ATTENTE", None, None, None, None, False, None, 0)
    draft = _r(session, state.response_draft_id) if state else None
    active = _r(session, state.active_response_id) if state else None
    joint = _r(session, state.joint_draft_id) if state and not beneficiary else None
    return PreparationView(
        questionnaire=(public_questionnaire_v2(_doc(q)) if beneficiary and q and _doc(q).get("schema") == SCHEMA_Q_V2 else _doc(q)), questionnaire_locked=bool(q and q.state == "VERROUILLE"),
        questionnaire_version=q.version_no if q else None,
        row_version=state.row_version if state else 0,
        invitation_open=invited, stage=state.state if state else "NON_PREPARE",
        responses=_doc(active) if beneficiary and active else (_doc(draft) if draft else None),
        response_status=active.state if active else (draft.state if draft else None),
        active_answers=_doc(active), active_response_version=active.version_no if active else None,
        reviewed_in_session=bool(state and active and state.reviewed_response_id == active.response_id),
        joint_draft=_doc(joint), source_count=len(_doc(q)["source_refs"]) if q else 0,
    )


def _begin(ctx, case_id, *, role, scope, database_url):
    engine = build_engine(database_url)
    factory = session_factory(engine)
    session = factory()
    try:
        _context(session, ctx, case_id, role=role, scope=scope)
    except BaseException:
        session.close()
        raise
    return session


def _check_state(session, case_id, expected):
    state = session.get(PreparationState, case_id)
    current = state.row_version if state else 0
    if current != expected:
        raise OrientationConflict("Ce questionnaire a changé dans une autre session. Rechargez avant de continuer.")
    return state


def _new_state(session, case_id):
    state = PreparationState(case_id=case_id, row_version=1)
    session.add(state)
    session.flush()
    return state


def _version_q(session, state, ctx, questionnaire, status):
    validated = valid_questionnaire(questionnaire)
    v = PreparationQuestionnaire(
        case_id=state.case_id, version_no=state.next_q_version, state=status,
        content_json=json.dumps(validated, ensure_ascii=False, separators=(",", ":")),
        sha256=fingerprint(validated), created_by=ctx.actor_id,
    )
    session.add(v)
    session.flush()
    state.questionnaire_id = v.questionnaire_id
    state.next_q_version += 1
    return v


def _version_r(session, state, ctx, questionnaire_id, answers, status, *, parent=None, confirm=None):
    q = session.get(PreparationQuestionnaire, questionnaire_id)
    final = status in {"BENEFICIAIRE_VALIDE", "REVUE_CONJOINTE"}
    content = valid_answers(answers, _doc(q), final=final)
    v = PreparationResponse(
        case_id=state.case_id, questionnaire_id=questionnaire_id,
        version_no=state.next_r_version, state=status,
        content_json=json.dumps(content, ensure_ascii=False, separators=(",", ":")),
        sha256=fingerprint(content), created_by=ctx.actor_id,
        parent_response_id=parent, confirmation_method=confirm,
    )
    session.add(v)
    session.flush()
    state.next_r_version += 1
    return v


def _audit(session, ctx, case_id, label, object_id, version, metadata=None):
    # Les contenus des reponses ne sont JAMAIS reproduits dans les logs.
    session.add(AuditEvent(case_id=case_id, event_type=label, object_type="CAV1_CAV2",
                           object_id=object_id, object_version=version,
                           actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
                           metadata_json_minimized=json.dumps(metadata or {}, ensure_ascii=False)))


def _commit(session, case_id, *, beneficiary=False):
    try:
        session.commit()
    except (IntegrityError, StaleDataError) as exc:
        session.rollback()
        raise OrientationConflict("Modification concurrente : aucune saisie n'a été écrasée.") from exc
    return _data(session, session.get(PreparationState, case_id), beneficiary=beneficiary)


def read_preparation(ctx, case_id: str, *, database_url: str | None = None) -> PreparationView:
    session = _begin(ctx, case_id, role=ctx.actor_role, scope="CP_CASE_READ", database_url=database_url)
    try:
        return _data(session, session.get(PreparationState, case_id),
                     beneficiary=ctx.actor_role is ActorRole.BENEFICIAIRE)
    finally:
        session.close()


def create_questionnaire(ctx, case_id, sources: dict, *, context="AUTRE", intro="",
                         expected_row_version=0, database_url=None) -> PreparationView:
    q = generate_questionnaire(sources, context=context, intro=intro)
    return save_questionnaire(ctx, case_id, q, expected_row_version=expected_row_version, database_url=database_url)


def create_questionnaire_v2(ctx, case_id, sources: dict, *, context="AUTRE", intro="", expected_row_version=0, database_url=None) -> PreparationView:
    """Generation deterministe de la Q unique RC3, sans import d'autres PDF."""
    from clarte360_cp.repositories.gda_documents import current_document_review_snapshot
    source_purpose = {
        "CV_SOURCE": "CV_SOURCE",
        "APS_OBJECTIF": "APS_OBJECTIF", "APS_P1": "APS_OBJECTIF",
        "BOUSSOLE_VALEURS": "BOUSSOLE_VALEURS", "MOTEURS_PRO": "MOTEURS_PRO",
        "PREFERENCES_PRO": "PREFERENCES_PRO", "IPIP_REPORT": "IPIP_REPORT",
        "PIP_REPORT": "PIP_REPORT",
    }
    session = session_factory(build_engine(database_url))()
    try:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        snapshot = current_document_review_snapshot(session, case_id)
        pending = [row["document"].display_name for row in snapshot.values() if row["status"] == "A_VERIFIER"]
        if pending:
            raise ValueError("Avant de préparer le questionnaire, vérifiez dans Documents les pièces encore en attente : " + ", ".join(pending))
        if snapshot:
            for code, purpose in source_purpose.items():
                selected = sources.get(code) if isinstance(sources, dict) else None
                ref = str(selected.get("source_ref") or "").strip() if isinstance(selected, dict) else ""
                if not ref:
                    continue
                current = snapshot.get(purpose)
                if (not current or current["status"] != "D5_DOCUMENT_VALIDE"
                        or current["document"].source_ref != ref):
                    raise ValueError(f"La source « {code} » doit être reliée et vérifiée dans Documents avant de préparer le questionnaire.")
    finally:
        session.close()
    q = generate_questionnaire_v2(sources, context=context, intro=intro)
    return save_questionnaire(ctx, case_id, q, expected_row_version=expected_row_version,
                              database_url=database_url, allow_source_refresh=True)


def record_questionnaire_source_analysis_consent(ctx, case_id, source_refs, *, database_url=None):
    """Audit the one-time beneficiary consent before selected source text is sent to AI."""
    refs = list(dict.fromkeys(str(ref).strip() for ref in source_refs if str(ref).strip()))
    if not refs or len(refs) > 7 or any(len(ref) > 240 for ref in refs):
        raise ValueError("Les références des pièces à analyser sont invalides.")
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE", database_url=database_url)
    try:
        _audit(session, ctx, case_id, "QUESTIONNAIRE_SOURCE_ANALYSIS_CONSENT_RECORDED",
               f"Q-SOURCE-ANALYSIS:{case_id}", 1,
               {"provider": "openai", "store": False, "source_refs": refs,
                "consent": "BENEFICIARY_INFORMED_AND_ACCEPTED"})
        session.commit()
    finally:
        session.close()


def save_questionnaire(ctx, case_id, questionnaire, *, expected_row_version, database_url=None,
                       allow_source_refresh=False) -> PreparationView:
    data = valid_questionnaire(questionnaire)
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE", database_url=database_url)
    try:
        state = _check_state(session, case_id, expected_row_version)
        if state and state.questionnaire_id and _q(session, state).state == "VERROUILLE":
            raise ValueError("Questionnaire définitivement verrouillé : aucune modification de Q-V1 possible.")
        if state and state.questionnaire_id and data.get("schema") == SCHEMA_Q_V2:
            old = _doc(_q(session, state))
            if old and old.get("schema") == SCHEMA_Q_V2:
                # Les résumés de résultats proviennent des rapports autorisés ;
                # on ne les réécrit pas manuellement en modifiant une question.
                if old.get("evidence", {}) != data.get("evidence", {}) and not allow_source_refresh:
                    raise ValueError("Résultats sources immuables : recréez une nouvelle Q depuis les rapports vérifiés.")
                before = {x["id"]: x for x in old["ideas_active"] + old["ideas_archived"]}
                after = {x["id"]: x for x in data["ideas_active"] + data["ideas_archived"]}
                for ident, item in before.items():
                    if ident not in after or item["origin"] != after[ident]["origin"] or item["source_wording"] != after[ident]["source_wording"]:
                        raise ValueError("Provenance APS immuable : archivez les pistes, ne réécrivez pas la source.")
        if state is None:
            state = _new_state(session, case_id)
        version = _version_q(session, state, ctx, data, "BROUILLON")
        state.state = "QUESTIONNAIRE_BROUILLON"
        _audit(session, ctx, case_id, "CAV_Q_DRAFT", version.questionnaire_id, version.version_no)
        return _commit(session, case_id)
    finally:
        session.close()


def lock_questionnaire(ctx, case_id, *, expected_row_version, database_url=None, publish_to_beneficiary=False) -> PreparationView:
    """Fige Q. En RC3A, peut aussi ouvrir l'acces dans LA MEME transaction.

    Par defaut le contrat RC2 conserve sa validation en deux operations.
    Le parcours unifie RC3A utilise lock_and_publish_questionnaire pour eviter
    un questionnaire verrouille mais invisible du beneficiaire.
    """
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_VALIDATE", database_url=database_url)
    try:
        state = _check_state(session, case_id, expected_row_version)
        q = _q(session, state)
        if not q or q.state != "BROUILLON":
            raise ValueError("Un questionnaire en brouillon doit être relu avant verrouillage.")
        if publish_to_beneficiary:
            from clarte360_cp.domain.preparation_v2 import SCHEMA_Q_V2 as _Q2
            if _doc(q).get("schema") != _Q2:
                raise ValueError("La mise a disposition simultanee concerne seulement la Q unifiee RC3.")
            if not ctx.has_scope("CP_PUBLISH"):
                raise OrientationAccessDenied("Droit de publication manquant.")
            from clarte360_cp.repositories.gda_documents import current_document_review_snapshot
            snapshot = current_document_review_snapshot(session, case_id)
            pending = [row["document"].display_name for row in snapshot.values() if row["status"] == "A_VERIFIER"]
            if pending:
                raise ValueError("Envoi bloqué : vérifiez ou écartez d’abord les pièces en attente dans Documents.")
            purpose_by_source = {
                "APS_OBJECTIF": "APS_OBJECTIF", "APS_P1": "APS_OBJECTIF",
                "BOUSSOLE_VALEURS": "BOUSSOLE_VALEURS", "MOTEURS_PRO": "MOTEURS_PRO",
                "PREFERENCES_PRO": "PREFERENCES_PRO", "IPIP_REPORT": "IPIP_REPORT",
                "PIP_REPORT": "PIP_REPORT",
            }
            if snapshot:
                for source in _doc(q).get("source_refs", []):
                    purpose = purpose_by_source.get(str(source.get("code") or ""))
                    if not purpose:
                        continue
                    current = snapshot.get(purpose)
                    if (not current or current["status"] != "D5_DOCUMENT_VALIDE"
                            or current["document"].source_ref != source.get("source_ref")):
                        raise ValueError("Envoi bloqué : une source du questionnaire n’est plus reliée et vérifiée dans Documents. Reprenez le brouillon avant de l’envoyer.")
        locked = _version_q(session, state, ctx, _doc(q), "VERROUILLE")
        _audit(session, ctx, case_id, "CAV_Q_LOCKED", locked.questionnaire_id, locked.version_no)
        if publish_to_beneficiary:
            state.invitation_open = True
            state.state = "QUESTIONNAIRE_ACCESSIBLE"
            _audit(session, ctx, case_id, "CAV_ACCESS_OPEN", locked.questionnaire_id, locked.version_no,
                   {"mode": "IN_APP_AFTER_Q_VALIDATION"})
        else:
            state.state = "QUESTIONNAIRE_VERROUILLE"
        return _commit(session, case_id)
    finally:
        session.close()


def lock_and_publish_questionnaire(ctx, case_id, *, expected_row_version, database_url=None) -> PreparationView:
    """Unique clic accompagnateur : Q figee et visible dans l'espace Beneficiaire."""
    return lock_questionnaire(ctx, case_id, expected_row_version=expected_row_version,
                              database_url=database_url, publish_to_beneficiary=True)


def open_beneficiary_access(ctx, case_id, *, expected_row_version, database_url=None) -> PreparationView:
    """Active la consultation depuis le lancement Hub. N'envoie PAS d'e-mail."""
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_PUBLISH", database_url=database_url)
    try:
        state = _check_state(session, case_id, expected_row_version)
        q = _q(session, state)
        if not state or not q or q.state != "VERROUILLE":
            raise ValueError("Invitation impossible : validez d'abord le questionnaire.")
        if state.invitation_open:
            raise ValueError("Le questionnaire est déjà accessible au bénéficiaire.")
        state.invitation_open = True
        state.state = "QUESTIONNAIRE_ACCESSIBLE"
        _audit(session, ctx, case_id, "CAV_ACCESS_OPEN", q.questionnaire_id, q.version_no,
               {"mode": "HUB_ACCESS_ONLY_NO_EMAIL"})
        return _commit(session, case_id)
    finally:
        session.close()


def save_beneficiary_answers(ctx, case_id, answers, *, expected_row_version, database_url=None) -> PreparationView:
    session = _begin(ctx, case_id, role=ActorRole.BENEFICIAIRE, scope="CP_BENEFICIARY_INTERACT", database_url=database_url)
    try:
        state = _check_state(session, case_id, expected_row_version)
        q = _q(session, state)
        if not state or not state.invitation_open or not q or q.state != "VERROUILLE":
            raise OrientationAccessDenied("Questionnaire non encore accessible.")
        if state.active_response_id:
            raise ValueError("Vos réponses sont définitivement transmises. Relecture possible en séance.")
        # Garde SERVEUR RC3 : C-AV2 ne peut pas être enregistré comme terminé
        # avant une version précédemment sauvegardée de C-AV1.
        if _doc(q).get("schema") == SCHEMA_Q_V2 and answers.get("cav2_done"):
            previous = _r(session, state.response_draft_id)
            if not previous or not _doc(previous).get("cav1_done"):
                raise ValueError("Terminez et enregistrez C-AV1 avant de valider C-AV2.")
        version = _version_r(session, state, ctx, q.questionnaire_id, answers, "BROUILLON")
        state.response_draft_id = version.response_id
        state.state = "REPONSES_EN_COURS"
        _audit(session, ctx, case_id, "CAV_R_DRAFT", version.response_id, version.version_no)
        return _commit(session, case_id, beneficiary=True)
    finally:
        session.close()


def submit_beneficiary_answers(ctx, case_id, *, expected_row_version, database_url=None) -> PreparationView:
    session = _begin(ctx, case_id, role=ActorRole.BENEFICIAIRE, scope="CP_BENEFICIARY_VALIDATE", database_url=database_url)
    try:
        state = _check_state(session, case_id, expected_row_version)
        q = _q(session, state)
        if not state or not state.invitation_open or not q or q.state != "VERROUILLE" or state.active_response_id:
            raise ValueError("Transmission non autorisée ou déjà effectuée.")
        draft = _r(session, state.response_draft_id)
        if not draft:
            raise ValueError("Enregistrez d'abord vos réponses personnelles.")
        finalized = _version_r(session, state, ctx, q.questionnaire_id,
                               _doc(draft), "BENEFICIAIRE_VALIDE", parent=draft.response_id)
        state.active_response_id = finalized.response_id
        state.response_draft_id = None
        state.state = "REPONSES_TRANSMISES"
        session.add(Validation(event_key=f"CAV:R1:{finalized.response_id}", case_id=case_id,
                               object_type="CAV_REPONSES", object_id=finalized.response_id,
                               object_version=finalized.version_no, actor_type="BENEFICIAIRE",
                               actor_id=ctx.actor_id, mode="EXPLICITE"))
        _audit(session, ctx, case_id, "CAV_R_BENEFICIARY_SUBMITTED", finalized.response_id, finalized.version_no)
        return _commit(session, case_id, beneficiary=True)
    finally:
        session.close()


def save_joint_review(ctx, case_id, answers, *, expected_row_version, database_url=None) -> PreparationView:
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE", database_url=database_url)
    try:
        state = _check_state(session, case_id, expected_row_version)
        active = _r(session, state.active_response_id) if state else None
        q = _q(session, state)
        if not active or not q:
            raise ValueError("Les réponses du bénéficiaire doivent être transmises avant l'entretien.")
        base_id = state.joint_draft_id or active.response_id
        joint = _version_r(session, state, ctx, q.questionnaire_id,
                           answers, "REVUE_BROUILLON", parent=base_id)
        state.joint_draft_id = joint.response_id
        state.state = "REVUE_EN_COURS"
        _audit(session, ctx, case_id, "CAV_R_JOINT_DRAFT", joint.response_id, joint.version_no)
        return _commit(session, case_id)
    finally:
        session.close()


def confirm_joint_review(ctx, case_id, *, beneficiary_confirmed: bool, method: str,
                         expected_row_version: int, database_url=None) -> PreparationView:
    """Trace les deux accords. En partage d'ecran, le coach recueille et consigne l'accord oral.

    Ce n'est PAS une signature electronique. Un R2 n'est cree que si les reponses changent.
    """
    if not beneficiary_confirmed or method not in {"EN_SEANCE_PRESENTIEL", "PARTAGE_ECRAN_ORAL"}:
        raise ValueError("Confirmation expresse du bénéficiaire en séance nécessaire.")
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_VALIDATE", database_url=database_url)
    try:
        state = _check_state(session, case_id, expected_row_version)
        active = _r(session, state.active_response_id) if state else None
        q = _q(session, state)
        if not active or not q:
            raise ValueError("Aucune réponse personnelle à confirmer.")
        joint_draft = _r(session, state.joint_draft_id) if state.joint_draft_id else None
        if not joint_draft and state.reviewed_response_id == active.response_id:
            raise ValueError("Cette version a déjà été revue conjointement.")
        candidate = _doc(joint_draft) if joint_draft else _doc(active)
        candidate = valid_answers(candidate, _doc(q), final=True)
        was_changed = fingerprint(candidate) != active.sha256
        if was_changed:
            promoted = _version_r(session, state, ctx, q.questionnaire_id, candidate,
                                  "REVUE_CONJOINTE", parent=active.response_id, confirm=method)
            state.active_response_id = promoted.response_id
            active = promoted
        state.reviewed_response_id = active.response_id
        state.joint_draft_id = None
        state.state = "REVUE_CONJOINTE_VALIDEE"
        session.add(Validation(event_key=f"CAV:JOINT_BEN:{active.response_id}", case_id=case_id,
                               object_type="CAV_REPONSES", object_id=active.response_id,
                               object_version=active.version_no, actor_type="BENEFICIAIRE",
                               actor_id=ctx.beneficiary_id, mode=method))
        session.add(Validation(event_key=f"CAV:JOINT_ACC:{active.response_id}", case_id=case_id,
                               object_type="CAV_REPONSES", object_id=active.response_id,
                               object_version=active.version_no, actor_type="ACCOMPAGNATEUR",
                               actor_id=ctx.actor_id, mode="EXPLICITE"))
        _audit(session, ctx, case_id, "CAV_R_JOINT_CONFIRMED", active.response_id, active.version_no,
               {"changed": was_changed, "method": method})
        return _commit(session, case_id)
    finally:
        session.close()


def response_history(ctx, case_id, *, database_url=None) -> list[dict]:
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_READ", database_url=database_url)
    try:
        state = session.get(PreparationState, case_id)
        if not state:
            return []
        versions = session.scalars(select(PreparationResponse).where(PreparationResponse.case_id == case_id)
                                   .order_by(PreparationResponse.version_no)).all()
        # Aucun acces tiers au texte personnel de la personne.
        return [{"no": v.version_no, "state": v.state, "created_by": v.created_by,
                 "created_at": v.created_at.isoformat(), "response": _doc(v),
                 "parent_id": v.parent_response_id} for v in versions]
    finally:
        session.close()


def cav3_context(ctx, case_id, *, database_url=None) -> dict:
    """Entree factuelle CAV3 ; le moteur IA reel sera une interface separee.

    N'ouvre ni CV, ni autres dossiers ni documents employeur non autorises.
    Une preparation sur R1 est provisoire, une nouvelle R2 la rend obsolete.
    """
    view = read_preparation(ctx, case_id, database_url=database_url)
    if ctx.actor_role is not ActorRole.ACCOMPAGNATEUR or not ctx.has_scope("CP_CASE_READ"):
        raise OrientationAccessDenied("Préparation C-AV3 réservée à l'accompagnateur.")
    if not view.questionnaire_locked or view.active_answers is None:
        raise ValueError("Pas encore de réponses bénéficiaire définitivement transmises.")
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_READ", database_url=database_url)
    try:
        state = session.get(PreparationState, case_id)
        response = session.get(PreparationResponse, state.active_response_id) if state and state.active_response_id else None
        draft_response = session.get(PreparationResponse, state.joint_draft_id) if state and state.joint_draft_id else None
        response_id = response.response_id if response else None
        effective_version = response.version_no if response else None
        if (draft_response and _doc(draft_response).get("schema") == SCHEMA_R_V2):
            response_id = draft_response.response_id
            effective_version = draft_response.version_no
    finally:
        session.close()
    if not response_id:
        raise ValueError("La version active des réponses n'est plus disponible.")
    pending_r2 = bool(view.joint_draft and view.joint_draft.get("schema") == SCHEMA_R_V2)
    effective_answers = view.joint_draft if pending_r2 else view.active_answers
    if not pending_r2:
        effective_version = view.active_response_version
    source_stage = "R2_PROVISOIRE" if pending_r2 else ("R2_CONFIRME" if view.response_status == "REVUE_CONJOINTE" else "R1")
    source_fp = fingerprint({"questionnaire": view.questionnaire, "answers": effective_answers,
                             "sources": view.questionnaire["source_refs"]})
    return {"schema": "GO22_CAV3_INPUT_V1", "status": "R2_BROUILLON_NON_VALIDE" if pending_r2 else ("REVU_EN_SEANCE" if view.reviewed_in_session else "PREPARATOIRE_NON_VALIDE"),
            "questionnaire_version": view.questionnaire_version,
            "response_version": effective_version,
            "source_stage": source_stage,
            "response_id": response_id,
            "response_sha256": fingerprint(effective_answers),
            "source_fingerprint": source_fp,
            "questionnaire_sha256": fingerprint(view.questionnaire),
            "reponses": copy.deepcopy(effective_answers),
            "sources": copy.deepcopy(view.questionnaire["source_refs"]),
            "evidence": copy.deepcopy(view.questionnaire.get("evidence", {})),
            "perspective_entreprise": view.questionnaire["enterprise_wording"],
            "regles": ["Aucune conclusion automatique", "Aucun score de compatibilité métier", "Ne pas charger le CV avant C0", "Provenance explicite"]}


def run_cav3_analysis(ctx, case_id, ai_settings=None, *, database_url=None, client=None) -> dict:
    """Run IA from the Accompagnateur account, then persist an immutable snapshot.

    The source is rechecked after the network call to avoid attaching an answer
    returned for R1 to a concurrently revised R2.
    """
    if ctx.actor_role is not ActorRole.ACCOMPAGNATEUR or not ctx.has_scope("CP_CASE_READ"):
        raise OrientationAccessDenied("Préparation C-AV3 réservée à l'accompagnateur.")
    from clarte360_cp.connectors.cav3_ai import Cav3AISettings, analyze_cav3
    settings = (ai_settings if isinstance(ai_settings, Cav3AISettings) else
                Cav3AISettings.from_mapping(ai_settings) if ai_settings is not None else
                Cav3AISettings.from_streamlit_secrets())
    source = cav3_context(ctx, case_id, database_url=database_url)
    kwargs = {"client": client} if client is not None else {}
    output = analyze_cav3(source, settings, **kwargs)
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE", database_url=database_url)
    try:
        state = session.get(PreparationState, case_id)
        current = session.get(PreparationResponse, state.active_response_id) if state and state.active_response_id else None
        draft = session.get(PreparationResponse, state.joint_draft_id) if state and state.joint_draft_id else None
        questionnaire = session.get(PreparationQuestionnaire, state.questionnaire_id) if state and state.questionnaire_id else None
        selected = draft if draft and _doc(draft).get("schema") == SCHEMA_R_V2 else current
        now_fp = fingerprint({"questionnaire": _doc(questionnaire), "answers": _doc(selected),
                              "sources": (_doc(questionnaire) or {}).get("source_refs", [])}) if current and questionnaire else None
        if not current or now_fp != source["source_fingerprint"]:
            raise OrientationConflict("Les réponses ou leurs sources ont changé pendant l'analyse. Relancez C-AV3 sur la version actuelle.")
        row = Cav3Analysis(case_id=case_id, response_id=source["response_id"],
                           response_version=source["response_version"], source_stage=source["source_stage"],
                           source_fingerprint=now_fp,
                           provider=output["provider"], model=output["model"],
                           result_json=json.dumps({**output["result"], "_metadata": output["metadata"]}, ensure_ascii=False, separators=(",", ":")),
                           created_by=ctx.actor_id)
        session.add(row)
        session.flush()
        session.add(AuditEvent(case_id=case_id, event_type="CAV3_IA_ANALYSIS_CREATED", object_type="CAV3_ANALYSIS",
                               object_id=row.analysis_id, object_version=source["response_version"],
                               actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
                               metadata_json_minimized=json.dumps({"provider": output["provider"], "model": output["model"],
                                                                  "source_fingerprint": now_fp}, ensure_ascii=False)))
        session.commit()
        return {"analysis_id": row.analysis_id, "response_version": row.response_version,
                "source_stage": row.source_stage,
                "source_fingerprint": row.source_fingerprint, "provider": row.provider,
                "model": row.model, "result": output["result"], "created_at": row.created_at.isoformat(),
                "current": True}
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def cav3_analysis_history(ctx, case_id, *, database_url=None) -> list[dict]:
    """Return internal analyses, marking those tied to older Q/R snapshots stale."""
    current = cav3_context(ctx, case_id, database_url=database_url)
    session = _begin(ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_READ", database_url=database_url)
    try:
        rows = session.scalars(select(Cav3Analysis).where(Cav3Analysis.case_id == case_id)
                               .order_by(Cav3Analysis.created_at, Cav3Analysis.analysis_id)).all()
        result = []
        for row in rows:
            is_current = row.source_fingerprint == current["source_fingerprint"]
            display_stage = row.source_stage
            if is_current and row.source_stage == "R2_PROVISOIRE" and current["status"] != "R2_BROUILLON_NON_VALIDE":
                display_stage = "R2_CONFIRME"
            result.append({"analysis_id": row.analysis_id, "response_version": row.response_version,
                 "source_stage": display_stage,
                 "provider": row.provider, "model": row.model, "result": json.loads(row.result_json),
                 "created_at": row.created_at.isoformat(),
                 "current": is_current})
        return result
    finally:
        session.close()
