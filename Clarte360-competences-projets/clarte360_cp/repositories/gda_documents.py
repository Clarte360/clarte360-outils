from __future__ import annotations

import json
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from clarte360_cp.domain.launch import LaunchContext
from .models import AuditEvent, GDAExternalDocument, GDAExternalDocumentLink
from .models import IntegrationReceipt

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
    ).order_by(GDAExternalDocumentLink.linked_at.desc()).limit(1))
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
    ).order_by(GDAExternalDocumentLink.linked_at.desc())).all()
    for link in links:
        latest_by_document.setdefault(link.external_document_id, link)
        latest_by_purpose.setdefault(link.purpose, link)
    return [(doc, (link if link and latest_by_purpose.get(link.purpose, link).link_id == link.link_id else None))
            for doc in documents for link in [latest_by_document.get(doc.external_document_id)]]


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
