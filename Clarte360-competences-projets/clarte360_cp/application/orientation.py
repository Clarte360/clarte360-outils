"""GO22 - Entrée métier accompagnée, sauvegardée côté serveur.

Ne lit pas une APS tiers ou un rapport de test via API fictive. Les éléments
transcrits manuellement conservent une provenance déclarée et ne sont transmis
qu'au bénéficiaire après une publication explicite. Zéro accès entreprise.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.domain.orientation import blank_orientation, valid_orientation
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import (
    AuditEvent, Case, CaseContextRef, OrientationFeedback, OrientationState,
    OrientationVersion, ReviewFlag, Validation,
)


class OrientationConflict(Exception):
    """Une autre session a modifié l'entrée pendant la saisie."""


class OrientationAccessDenied(PermissionError):
    """Accès refusé pour cette action et ce bénéficiaire."""


@dataclass(frozen=True)
class OrientationView:
    current: dict
    current_version: int
    published: dict | None
    published_version: int | None
    feedback: str | None
    feedback_comment: str | None
    has_draft: bool


def _context(session, ctx, case_id: str, *, role: ActorRole, scope: str) -> None:
    if ctx.actor_role is not role or not ctx.has_scope(scope):
        raise OrientationAccessDenied("Action non autorisée pour votre rôle.")
    case = session.get(Case, case_id)
    ref = session.scalar(select(CaseContextRef).where(CaseContextRef.case_id == case_id))
    if (
        case is None or ref is None or case.purge_state != "ACTIVE"
        or ref.beneficiary_id != ctx.beneficiary_id
        or ref.action_id != ctx.action_id
        or ref.prescription_id != ctx.prescription_id
        or (ref.participant_id is not None and ref.participant_id != ctx.participant_id)
    ):
        raise OrientationAccessDenied("Dossier ou contexte de lancement non concordant.")
    if role is ActorRole.ACCOMPAGNATEUR and case.status in {"CLOTURE", "RECTIFICATION_POST_CLOTURE"}:
        raise OrientationAccessDenied("Dossier clôturé : réouverture formelle nécessaire.")


def _current(session, state: OrientationState | None) -> tuple[dict, int]:
    if state and state.current_version_id:
        version = session.get(OrientationVersion, state.current_version_id)
        if version:
            return json.loads(version.content_json), state.row_version
    return blank_orientation(), state.row_version if state else 0


def _view(session, case_id: str) -> OrientationView:
    state = session.get(OrientationState, case_id)
    current, row_ver = _current(session, state)
    published = None
    pub_version = None
    decision = None
    comment = None
    if state and state.published_version_id:
        publication = session.get(OrientationVersion, state.published_version_id)
        if publication:
            published = json.loads(publication.content_json)
            pub_version = publication.version_no
            feedback = session.scalar(select(OrientationFeedback).where(
                OrientationFeedback.orientation_version_id == publication.orientation_version_id
            ))
            if feedback:
                decision, comment = feedback.decision, feedback.comment
    return OrientationView(current, row_ver, published, pub_version, decision, comment,
                           bool(state and state.current_version_id and state.current_version_id != state.published_version_id))


def read_orientation(ctx, case_id: str, *, database_url: str | None = None) -> OrientationView:
    engine = build_engine(database_url)
    Factory = session_factory(engine)
    with Factory() as session:
        _context(session, ctx, case_id, role=ctx.actor_role, scope="CP_CASE_READ")
        view = _view(session, case_id)
        if ctx.actor_role is ActorRole.BENEFICIAIRE:
            # Une modification non publiée, y compris les confidences, est invisible.
            return OrientationView(view.published or blank_orientation(), view.current_version,
                                   view.published, view.published_version, view.feedback,
                                   view.feedback_comment, False)
        return view


def _guard_original_ideas(previous: dict, proposed: dict) -> None:
    """Une reformulation ne doit jamais effacer l'expression initiale ou sa provenance."""
    old = {i["id"]: i for i in previous["ideas"]}
    new = {i["id"]: i for i in proposed["ideas"]}
    for key, idea in old.items():
        if key not in new:
            raise ValueError("Une idée déjà enregistrée ne peut pas être effacée ; utilisez « Plus aujourd'hui ».")
        if new[key]["original"] != idea["original"] or new[key]["origin"] != idea["origin"]:
            raise ValueError("Les mots initiaux et leur provenance ne sont pas modifiables.")
    old_dir = {d["id"]: d for d in previous["directions"]}
    new_dir = {d["id"]: d for d in proposed["directions"]}
    for key, item in old_dir.items():
        if key not in new_dir:
            raise ValueError("Une direction déjà enregistrée ne peut pas être effacée ; changez sa position.")
        if new_dir[key]["origin"] != item["origin"]:
            raise ValueError("La provenance d'une direction ne peut pas être réécrite.")


def _append_version(session, *, case_id: str, ctx, state: OrientationState | None,
                    expected_row_version: int, document: dict, publish: bool) -> OrientationView:
    if (state.row_version if state else 0) != expected_row_version:
        raise OrientationConflict("Une autre session a enregistré une modification. Rechargez ce dossier avant de réessayer.")
    if state is not None:
        previous, _ = _current(session, state)
        _guard_original_ideas(previous, document)
    if state is None:
        state = OrientationState(case_id=case_id, row_version=1, next_version_no=1)
        session.add(state)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise OrientationConflict("Une autre session a commencé cette saisie. Rechargez le dossier.") from exc
    version = OrientationVersion(case_id=case_id, version_no=state.next_version_no,
                                 state="PUBLIE_RELECTURE" if publish else "BROUILLON",
                                 content_json=json.dumps(document, ensure_ascii=False, separators=(",", ":")),
                                 created_by=ctx.actor_id)
    session.add(version)
    session.flush()
    values = {
        "current_version_id": version.orientation_version_id,
        "next_version_no": state.next_version_no + 1,
        "row_version": state.row_version + 1,
    }
    if publish:
        values["published_version_id"] = version.orientation_version_id
    changed = session.execute(
        update(OrientationState)
        .where(OrientationState.case_id == case_id, OrientationState.row_version == state.row_version)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        session.rollback()
        raise OrientationConflict("Cette orientation a changé entre-temps. Rechargez avant d'enregistrer.")
    if publish:
        # La demande de correction relative à la version remplacée reste historisée
        # mais cesse d'être un blocage actif lors d'une nouvelle publication.
        session.execute(update(ReviewFlag).where(
            ReviewFlag.case_id == case_id, ReviewFlag.object_type == "ORIENTATION",
            ReviewFlag.status == "OPEN"
        ).values(status="RESOLU").execution_options(synchronize_session=False))
    session.add(AuditEvent(case_id=case_id,
                           event_type="ORIENTATION_PUBLISHED" if publish else "ORIENTATION_DRAFT_SAVED",
                           object_type="ORIENTATION", object_id=version.orientation_version_id,
                           object_version=version.version_no, actor_type=ctx.actor_role.value,
                           actor_id=ctx.actor_id, metadata_json_minimized="{}"))
    session.commit()
    session.expire_all()
    return _view(session, case_id)


def save_orientation(ctx, case_id: str, document: dict, *, expected_row_version: int,
                     database_url: str | None = None) -> OrientationView:
    doc = valid_orientation(document)
    engine = build_engine(database_url)
    Factory = session_factory(engine)
    with Factory() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        state = session.get(OrientationState, case_id)
        try:
            return _append_version(session, case_id=case_id, ctx=ctx, state=state,
                                   expected_row_version=expected_row_version, document=doc, publish=False)
        except IntegrityError as exc:
            session.rollback()
            raise OrientationConflict("L'enregistrement a changé dans une autre session ; rechargez le dossier.") from exc


def publish_orientation(ctx, case_id: str, *, expected_row_version: int,
                        database_url: str | None = None) -> OrientationView:
    engine = build_engine(database_url)
    Factory = session_factory(engine)
    with Factory() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_PUBLISH")
        state = session.get(OrientationState, case_id)
        if state is None or state.current_version_id is None:
            raise ValueError("Commencez par enregistrer les idées et les repères.")
        if state.current_version_id == state.published_version_id:
            raise ValueError("Cette version est déjà publiée : aucune nouvelle modification à partager.")
        content, _ = _current(session, state)
        doc = valid_orientation(content)
        if not doc["ideas"] and not doc["no_idea_yet"]:
            raise ValueError("Notez une idée ou le fait que le bénéficiaire n'en a pas encore.")
        try:
            return _append_version(session, case_id=case_id, ctx=ctx, state=state,
                                   expected_row_version=expected_row_version, document=doc, publish=True)
        except IntegrityError as exc:
            session.rollback()
            raise OrientationConflict("Une autre publication vient d'intervenir ; rechargez le dossier.") from exc


def feedback_orientation(ctx, case_id: str, *, published_version: int, decision: str,
                         comment: str = "", database_url: str | None = None) -> OrientationView:
    if decision not in {"CONFIRME", "CORRECTION_DEMANDEE"}:
        raise ValueError("Décision inconnue.")
    clean = comment.strip()
    if len(clean) > 1000:
        raise ValueError("Commentaire trop long.")
    if decision == "CORRECTION_DEMANDEE" and len(clean) < 4:
        raise ValueError("Indiquez la correction attendue.")
    engine = build_engine(database_url)
    Factory = session_factory(engine)
    with Factory() as session:
        _context(session, ctx, case_id, role=ActorRole.BENEFICIAIRE, scope="CP_BENEFICIARY_VALIDATE")
        state = session.get(OrientationState, case_id)
        version = session.get(OrientationVersion, state.published_version_id) if state and state.published_version_id else None
        if version is None or version.version_no != published_version:
            raise OrientationConflict("La version partagée a changé. Rechargez avant de répondre.")
        previous = session.scalar(select(OrientationFeedback).where(
            OrientationFeedback.orientation_version_id == version.orientation_version_id
        ))
        if previous:
            raise OrientationConflict("Une réponse a déjà été enregistrée pour cette version.")
        session.add(OrientationFeedback(case_id=case_id, orientation_version_id=version.orientation_version_id,
                                        decision=decision, comment=clean or None, created_by=ctx.actor_id))
        if decision == "CONFIRME":
            session.add(Validation(event_key=f"ORIENTATION:{version.orientation_version_id}:CONFIRME",
                                   case_id=case_id, object_type="ORIENTATION", object_id=version.orientation_version_id,
                                   object_version=version.version_no, actor_type="BENEFICIAIRE",
                                   actor_id=ctx.actor_id, mode="EXPLICITE"))
        else:
            session.add(ReviewFlag(case_id=case_id, object_type="ORIENTATION",
                                   object_id=version.orientation_version_id,
                                   reason=clean, impact_level="NORMAL", status="OPEN"))
        session.add(AuditEvent(case_id=case_id, event_type="ORIENTATION_FEEDBACK",
                               object_type="ORIENTATION", object_id=version.orientation_version_id,
                               object_version=version.version_no, actor_type="BENEFICIAIRE",
                               actor_id=ctx.actor_id, metadata_json_minimized=json.dumps({"decision":decision})))
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise OrientationConflict("Une autre réponse a été enregistrée. Actualisez votre espace.") from exc
        return _view(session, case_id)
