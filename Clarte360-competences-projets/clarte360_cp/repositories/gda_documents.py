from __future__ import annotations

import json
import hashlib
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from clarte360_cp.domain.launch import LaunchContext
from clarte360_cp.domain.enums import ActorRole
from .models import AuditEvent, GDAExternalDocument, GDAExternalDocumentLink
from .models import IntegrationReceipt, Validation

ALLOWED_PURPOSES = frozenset({
    "APS_OBJECTIF", "BOUSSOLE_VALEURS", "MOTEURS_PRO", "PREFERENCES_PRO",
    "IPIP_REPORT", "PIP_REPORT", "CV_SOURCE", "AUTRE_PARCOURS",
    "PLAN_ACTION_FINAL", "RESULTATS_DETAILLES_FINAL", "SYNTHESE_FINALE",
})


def save_external_reference(session: Session, ctx: LaunchContext, case_id: str, metadata: dict) -> GDAExternalDocument:
    """Save GDA reference metadata without registering or copying file bytes."""
    if not (ctx.has_scope("CP_CASE_WRITE") or ctx.has_scope("CP_BENEFICIARY_INTERACT")):
        raise PermissionError("Droit insuffisant pour enregistrer cette référence documentaire.")
    digest = str(metadata.get("sha256", "")).lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Empreinte du document GDA invalide.")
    size = int(metadata.get("size_bytes", -1))
    if size < 0 or size > 50 * 1024 * 1024:
        raise ValueError("Taille du document GDA invalide.")
    ref = str(metadata.get("source_ref", ""))
    if not ref or len(ref) > 160 or str(metadata.get("source_kind", "")).upper() in {"ONET_REPORT", "PIP_PUBLIC_REPORT", "PIP_REPORT_PUBLIC"}:
        raise ValueError("Référence documentaire absente ou type de document exclu.")
    existing = session.scalar(select(GDAExternalDocument).where(
        GDAExternalDocument.case_id == case_id,
        GDAExternalDocument.source_ref == ref,
        GDAExternalDocument.sha256 == digest,
    ))
    if existing:
        return existing
    row = GDAExternalDocument(
        case_id=case_id, source_ref=ref,
        source_version=str(metadata.get("source_version", ""))[:100],
        source_kind=str(metadata.get("source_kind", "DOCUMENT_NON_ASSOCIE"))[:80],
        display_name=str(metadata.get("display_name", "Document"))[:180],
        mime_type=str(metadata.get("mime_type", "application/octet-stream"))[:160],
        size_bytes=size, sha256=digest,
        source_created_at=str(metadata.get("created_at", ""))[:80] or None,
        source_created_by_role=str(metadata.get("created_by_role", ""))[:40] or None,
        source_created_by_ref=str(metadata.get("created_by_ref", ""))[:160] or None,
    )
    session.add(row); session.flush()
    _audit(session, case_id, "GDA_DOCUMENT_REFERENCE_SEEN", row.external_document_id, ctx,
           {"source_ref": ref, "sha256": digest, "size_bytes": size, "source_version": row.source_version})
    session.commit()
    return row


def link_document_to_purpose(session: Session, ctx: LaunchContext, case_id: str,
                              external_document_id: str, purpose: str) -> GDAExternalDocumentLink:
    """Append an accompanist's explicit, versioned source-to-need decision."""
    if ctx.actor_role.value != "ACCOMPAGNATEUR" or not ctx.has_scope("CP_SOURCE_MANUAL_IMPORT"):
        raise PermissionError("Seul l’accompagnateur habilité peut relier un document à un besoin du bilan.")
    purpose = str(purpose or "").upper()
    if purpose not in ALLOWED_PURPOSES:
        raise ValueError("Besoin documentaire C&P non reconnu.")
    document = session.get(GDAExternalDocument, external_document_id)
    if not document or document.case_id != case_id:
        raise PermissionError("Cette référence documentaire n’appartient pas au dossier courant.")
    previous = session.scalar(select(GDAExternalDocumentLink).where(
        GDAExternalDocumentLink.case_id == case_id,
        GDAExternalDocumentLink.purpose == purpose,
    ).order_by(GDAExternalDocumentLink.linked_at.desc(), GDAExternalDocumentLink.link_id.desc()).limit(1))
    # Repeated form submission must not create a new history row when the
    # document is already the current source for this need.
    if previous and previous.external_document_id == external_document_id:
        return previous
    row = GDAExternalDocumentLink(
        case_id=case_id, external_document_id=external_document_id, purpose=purpose,
        actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
        supersedes_link_id=previous.link_id if previous else None,
    )
    session.add(row); session.flush()
    _audit(session, case_id, "GDA_DOCUMENT_LINKED_MANUALLY", row.link_id, ctx,
           {"source_ref": document.source_ref, "sha256": document.sha256,
            "purpose": purpose, "supersedes_link_id": row.supersedes_link_id})
    session.commit()
    return row


def list_linked_gda_documents(session: Session, case_id: str) -> list[tuple[GDAExternalDocument, GDAExternalDocumentLink | None]]:
    documents = session.scalars(select(GDAExternalDocument).where(
        GDAExternalDocument.case_id == case_id
    ).order_by(GDAExternalDocument.first_seen_at.desc())).all()
    latest_by_document = {}
    latest_by_purpose = {}
    links = session.scalars(select(GDAExternalDocumentLink).where(
        GDAExternalDocumentLink.case_id == case_id
    ).order_by(GDAExternalDocumentLink.linked_at.desc(), GDAExternalDocumentLink.link_id.desc())).all()
    for link in links:
        latest_by_document.setdefault(link.external_document_id, link)
        latest_by_purpose.setdefault(link.purpose, link)
    return [(doc, (link if link and latest_by_purpose.get(link.purpose, link).link_id == link.link_id else None))
            for doc in documents for link in [latest_by_document.get(doc.external_document_id)]]


def list_current_gda_purpose_links(session: Session, case_id: str) -> dict[str, tuple[GDAExternalDocument, GDAExternalDocumentLink]]:
    """Return the current document for every need, without collapsing multi-purpose links."""
    links = session.scalars(select(GDAExternalDocumentLink).where(
        GDAExternalDocumentLink.case_id == case_id
    ).order_by(GDAExternalDocumentLink.linked_at.desc())).all()
    result = {}
    for link in links:
        if link.purpose in result:
            continue
        document = session.get(GDAExternalDocument, link.external_document_id)
        if document is not None:
            result[link.purpose] = (document, link)
    return result


def _document_review_object_id(case_id: str, document: GDAExternalDocument, purpose: str) -> str:
    """Stable, non-identifying key for one document version in one D5 need."""
    payload = "|".join((case_id, document.source_ref, purpose, document.sha256))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def current_document_review_snapshot(session: Session, case_id: str) -> dict[str, dict]:
    """Return current D5 review states for active document-to-need links.

    GDA's technical validation/publication fields are deliberately not used as
    the C&P review state. The record is local to D5, bound to the exact
    source checksum and current need association, and audited by role.
    """
    links = list_current_gda_purpose_links(session, case_id)
    rows = session.scalars(select(Validation).where(
        Validation.case_id == case_id,
        Validation.object_type == "GDA_DOCUMENT_REVIEW",
    ).order_by(Validation.at.asc(), Validation.validation_id.asc())).all()
    latest = {}
    for row in rows:
        latest[row.object_id] = row
    snapshot = {}
    for purpose, (document, _link) in links.items():
        review = latest.get(_document_review_object_id(case_id, document, purpose))
        status = review.mode if review and review.mode in {
            "D5_DOCUMENT_VALIDE", "D5_DOCUMENT_NON_UTILISE", "D5_DOCUMENT_VERIFIE_NON_UTILISE"
        } else "A_VERIFIER"
        snapshot[purpose] = {"document": document, "status": status,
                             "reviewed_at": review.at if review else None,
                             "reviewed_by": review.actor_id if review else None}
    return snapshot


def record_document_review(session: Session, ctx: LaunchContext, case_id: str,
                           external_document_id: str, purpose: str, status: str) -> str:
    """Record an accompanist's D5 decision for the active link and exact version."""
    record_document_review_batch(session, ctx, case_id, [{
        "external_document_id": external_document_id, "purpose": purpose, "status": status,
    }])
    return str(status or "").upper()


def record_document_review_batch(session: Session, ctx: LaunchContext, case_id: str,
                                 decisions: list[dict[str, str]]) -> int:
    """Atomically save one include/exclude decision for each reviewed source."""
    from clarte360_cp.application.orientation import _context
    _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_VALIDATE")
    if ctx.actor_role.value != "ACCOMPAGNATEUR" or not ctx.has_scope("CP_VALIDATE"):
        raise PermissionError("Seul l’intervenant autorisé peut vérifier les documents dans D5.")
    active_links = list_current_gda_purpose_links(session, case_id)
    staged = []
    seen = set()
    for decision in decisions:
        external_document_id = str(decision.get("external_document_id") or "")
        purpose = str(decision.get("purpose") or "").upper()
        status = str(decision.get("status") or "").upper()
        if status not in {"D5_DOCUMENT_VALIDE", "D5_DOCUMENT_NON_UTILISE", "D5_DOCUMENT_VERIFIE_NON_UTILISE"}:
            raise ValueError("Choisissez une décision pour chaque pièce avant de continuer.")
        document = session.get(GDAExternalDocument, external_document_id)
        if not document or document.case_id != case_id:
            raise PermissionError("Une pièce n’appartient pas au dossier ouvert.")
        if purpose == "UNLINKED":
            if status != "D5_DOCUMENT_NON_UTILISE":
                raise ValueError("Une pièce doit être reliée à un besoin avant d’être retenue pour le questionnaire.")
            if any(linked.external_document_id == document.external_document_id for linked, _link in active_links.values()):
                raise ValueError("Une pièce a été reliée entre-temps. Actualisez Documents avant de continuer.")
        else:
            active = active_links.get(purpose)
            if not active or active[0].external_document_id != document.external_document_id:
                raise ValueError("Un rapprochement a changé. Actualisez Documents avant de continuer.")
        object_id = _document_review_object_id(case_id, document, purpose)
        if object_id in seen:
            continue
        seen.add(object_id)
        current = session.scalar(select(Validation).where(
            Validation.case_id == case_id, Validation.object_type == "GDA_DOCUMENT_REVIEW",
            Validation.object_id == object_id,
        ).order_by(Validation.at.desc(), Validation.validation_id.desc()).limit(1))
        if current and current.mode == status:
            continue
        staged.append((document, purpose, object_id, status))
    for document, purpose, object_id, status in staged:
        session.add(Validation(
            event_key=f"GDA_DOC_REVIEW:{uuid4()}", case_id=case_id, phase_no=None,
            object_type="GDA_DOCUMENT_REVIEW", object_id=object_id, object_version=1,
            actor_type="ACCOMPAGNATEUR", actor_id=ctx.actor_id, mode=status,
        ))
        event_type = (
            "GDA_DOCUMENT_REVIEWED" if status == "D5_DOCUMENT_VALIDE"
            else "GDA_DOCUMENT_VERIFIED_BUT_EXCLUDED" if status == "D5_DOCUMENT_VERIFIE_NON_UTILISE"
            else "GDA_DOCUMENT_EXCLUDED_FROM_QUESTIONNAIRE"
        )
        session.add(AuditEvent(
            case_id=case_id,
            event_type=event_type,
            object_type="GDA_DOCUMENT_REVIEW", object_id=object_id, object_version=1,
            actor_type="ACCOMPAGNATEUR", actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"purpose": purpose, "sha256": document.sha256, "status": status}, separators=(",", ":")),
        ))
    if staged:
        session.commit()
    return len(staged)


def save_document_mapping_batch(session: Session, ctx: LaunchContext, case_id: str,
                                mappings: list[dict[str, str]],
                                excluded_document_ids: list[str] | None = None) -> int:
    """Atomically map the seven first-pass needs and record all keep/skip choices."""
    from clarte360_cp.application.orientation import _context
    _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_VALIDATE")
    if ctx.actor_role is not ActorRole.ACCOMPAGNATEUR or not ctx.has_scope("CP_VALIDATE"):
        raise PermissionError("Seul l’intervenant autorisé peut valider les choix documentaires dans D5.")
    if not ctx.has_scope("CP_SOURCE_MANUAL_IMPORT"):
        raise PermissionError("Le droit de rapprochement documentaire est manquant pour cette action.")

    required_purposes = {
        "CV_SOURCE", "APS_OBJECTIF", "BOUSSOLE_VALEURS", "MOTEURS_PRO",
        "PREFERENCES_PRO", "PIP_REPORT", "IPIP_REPORT", "AUTRE_PARCOURS",
    }
    chosen_by_purpose: dict[str, str] = {}
    chosen_ids: set[str] = set()
    include_by_purpose: dict[str, bool] = {}
    no_document_purposes: list[str] = []
    seen_purposes: set[str] = set()
    for item in mappings:
        purpose = str(item.get("purpose") or "").upper()
        document_id = str(item.get("external_document_id") or "")
        if purpose not in required_purposes or purpose in seen_purposes:
            raise ValueError("Un besoin documentaire est dupliqué ou non reconnu.")
        seen_purposes.add(purpose)
        if not document_id:
            if purpose == "AUTRE_PARCOURS":
                continue
            no_document_purposes.append(purpose)
            continue
        if document_id in chosen_ids:
            raise ValueError("Une même pièce ne peut pas être sélectionnée pour plusieurs besoins.")
        doc = session.get(GDAExternalDocument, document_id)
        if not doc or doc.case_id != case_id:
            raise PermissionError("Une pièce choisie n’appartient pas au dossier courant.")
        if item.get("verified") is not True:
            raise ValueError("Confirmez la vérification de chaque pièce sélectionnée avant de continuer.")
        chosen_by_purpose[purpose] = document_id
        include_by_purpose[purpose] = item.get("include_in_study") is True
        chosen_ids.add(document_id)

    if not (required_purposes - {"AUTRE_PARCOURS"}).issubset(seen_purposes):
        raise ValueError("Les sept besoins du bilan doivent tous recevoir un choix explicite.")

    active_before = list_current_gda_purpose_links(session, case_id)
    for purpose, document_id in chosen_by_purpose.items():
        previous = active_before.get(purpose)
        if previous and previous[0].external_document_id == document_id:
            continue
        row = GDAExternalDocumentLink(
            case_id=case_id, external_document_id=document_id, purpose=purpose,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            supersedes_link_id=previous[1].link_id if previous else None,
        )
        session.add(row)
        session.flush()
        doc = session.get(GDAExternalDocument, document_id)
        _audit(session, case_id, "GDA_DOCUMENT_LINKED_MANUALLY", row.link_id, ctx,
               {"source_ref": doc.source_ref, "sha256": doc.sha256,
                "purpose": purpose, "supersedes_link_id": row.supersedes_link_id,
                "batch": True})

    session.flush()
    active_after = list_current_gda_purpose_links(session, case_id)
    reviews = []
    active_ids = set()
    for purpose, (doc, _link) in active_after.items():
        active_ids.add(doc.external_document_id)
        if chosen_by_purpose.get(purpose) == doc.external_document_id:
            status = "D5_DOCUMENT_VALIDE" if include_by_purpose.get(purpose, True) else "D5_DOCUMENT_VERIFIE_NON_UTILISE"
        else:
            status = "D5_DOCUMENT_NON_UTILISE"
        reviews.append({"external_document_id": doc.external_document_id,
                        "purpose": purpose, "status": status})

    for document_id in excluded_document_ids or []:
        document_id = str(document_id)
        if document_id in chosen_ids or document_id in active_ids:
            continue
        doc = session.get(GDAExternalDocument, document_id)
        if doc and doc.case_id == case_id:
            reviews.append({"external_document_id": document_id,
                            "purpose": "UNLINKED", "status": "D5_DOCUMENT_NON_UTILISE"})
    empty_staged = 0
    for purpose in no_document_purposes:
        object_id = hashlib.sha256(f"{case_id}|BESOIN_SANS_PIECE|{purpose}".encode("utf-8")).hexdigest()
        previous = session.scalar(select(Validation).where(
            Validation.case_id == case_id, Validation.object_type == "GDA_DOCUMENT_REVIEW",
            Validation.object_id == object_id,
        ).order_by(Validation.at.desc(), Validation.validation_id.desc()).limit(1))
        if previous and previous.mode == "D5_BESOIN_SANS_PIECE":
            continue
        session.add(Validation(
            event_key=f"GDA_DOC_REVIEW:{uuid4()}", case_id=case_id, phase_no=None,
            object_type="GDA_DOCUMENT_REVIEW", object_id=object_id, object_version=1,
            actor_type="ACCOMPAGNATEUR", actor_id=ctx.actor_id, mode="D5_BESOIN_SANS_PIECE",
        ))
        session.add(AuditEvent(
            case_id=case_id, event_type="GDA_DOCUMENT_NEED_CONFIRMED_EMPTY",
            object_type="GDA_DOCUMENT_REVIEW", object_id=object_id, object_version=1,
            actor_type="ACCOMPAGNATEUR", actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"purpose": purpose, "status": "D5_BESOIN_SANS_PIECE"}, separators=(",", ":")),
        ))
        empty_staged += 1
    if reviews:
        return record_document_review_batch(session, ctx, case_id, reviews)
    if empty_staged:
        session.commit()
    return empty_staged


def unlinked_document_review_status(session: Session, case_id: str, document: GDAExternalDocument) -> str:
    object_id = _document_review_object_id(case_id, document, "UNLINKED")
    row = session.scalar(select(Validation).where(
        Validation.case_id == case_id, Validation.object_type == "GDA_DOCUMENT_REVIEW",
        Validation.object_id == object_id,
    ).order_by(Validation.at.desc(), Validation.validation_id.desc()).limit(1))
    return row.mode if row and row.mode == "D5_DOCUMENT_NON_UTILISE" else "A_VERIFIER"


def exclude_unlinked_document_from_questionnaire(session: Session, ctx: LaunchContext, case_id: str,
                                                  external_document_id: str) -> str:
    """Record that an available, unlinked piece will not feed the questionnaire."""
    from clarte360_cp.application.orientation import _context
    _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_VALIDATE")
    document = session.get(GDAExternalDocument, external_document_id)
    if not document or document.case_id != case_id:
        raise PermissionError("Cette pièce n’appartient pas au dossier ouvert.")
    active = list_current_gda_purpose_links(session, case_id)
    if any(linked.external_document_id == document.external_document_id for linked, _link in active.values()):
        raise ValueError("Cette pièce est déjà rapprochée. Utilisez sa ligne pour la vérifier ou l’écarter.")
    object_id = _document_review_object_id(case_id, document, "UNLINKED")
    current = session.scalar(select(Validation).where(
        Validation.case_id == case_id, Validation.object_type == "GDA_DOCUMENT_REVIEW",
        Validation.object_id == object_id,
    ).order_by(Validation.at.desc(), Validation.validation_id.desc()).limit(1))
    if current and current.mode == "D5_DOCUMENT_NON_UTILISE":
        return current.mode
    session.add(Validation(
        event_key=f"GDA_DOC_REVIEW:{uuid4()}", case_id=case_id, phase_no=None,
        object_type="GDA_DOCUMENT_REVIEW", object_id=object_id, object_version=1,
        actor_type="ACCOMPAGNATEUR", actor_id=ctx.actor_id, mode="D5_DOCUMENT_NON_UTILISE",
    ))
    session.add(AuditEvent(
        case_id=case_id, event_type="GDA_DOCUMENT_EXCLUDED_FROM_QUESTIONNAIRE",
        object_type="GDA_DOCUMENT_REVIEW", object_id=object_id, object_version=1,
        actor_type="ACCOMPAGNATEUR", actor_id=ctx.actor_id,
        metadata_json_minimized=json.dumps({"source_ref": document.source_ref, "sha256": document.sha256,
                                            "status": "D5_DOCUMENT_NON_UTILISE"}, separators=(",", ":")),
    ))
    session.commit()
    return "D5_DOCUMENT_NON_UTILISE"


def record_gda_receipt(session: Session, ctx: LaunchContext, case_id: str,
                       event_id: str, receipt: dict) -> IntegrationReceipt:
    if not ctx.has_scope("CP_DELIVERABLE_RETURN"):
        raise PermissionError("La remise d’un livrable n’est pas autorisée.")
    stable_receipt = {key: receipt.get(key) for key in ("event_id", "document_reference_id", "sha256")}
    response = json.dumps(stable_receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(response.encode()).hexdigest()
    previous = session.scalar(select(IntegrationReceipt).where(
        IntegrationReceipt.case_id == case_id,
        IntegrationReceipt.external_system == "GESTION_ACTIONS",
        IntegrationReceipt.event_id == event_id,
    ))
    if previous:
        if previous.response_hash != digest:
            raise ValueError("Le reçu GDA diffère de la remise déjà enregistrée.")
        return previous
    row = IntegrationReceipt(
        case_id=case_id, event_id=event_id, external_system="GESTION_ACTIONS",
        external_ref=str(receipt.get("document_reference_id") or "")[:160] or None,
        status=str(receipt.get("status") or "REJECTED"), response_hash=digest,
    )
    session.add(row)
    _audit(session, case_id, "GDA_DELIVERABLE_RECEIPT", row.receipt_id, ctx,
           {"event_id": event_id, "status": row.status, "external_ref": row.external_ref, "response_hash": digest})
    session.commit()
    return row


def _audit(session: Session, case_id: str, event_type: str, object_id: str,
           ctx: LaunchContext, metadata: dict) -> None:
    session.add(AuditEvent(
        case_id=case_id, event_type=event_type, object_type="GDA_DOCUMENT",
        object_id=str(object_id), object_version=None,
        actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
        metadata_json_minimized=json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
    ))
