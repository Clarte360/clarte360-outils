"""Audit metadata for CV analyses without retaining CV text or proposals."""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from clarte360_cp.application.orientation import _context
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import AuditEvent


def record_cv_ai_analysis(ctx, case_id: str, source_ref: str, source_version: str | int,
                          metadata: Mapping[str, Any], *, database_url: str | None = None) -> str:
    """Record a successful proposal event; never store the CV text or AI output."""
    if not isinstance(source_ref, str) or not source_ref.strip() or len(source_ref) > 160:
        raise ValueError("Référence de CV non valide.")
    version = str(source_version).strip()
    if not version or len(version) > 40:
        raise ValueError("Version du CV non valide.")
    if not isinstance(metadata, Mapping):
        raise ValueError("Métadonnées IA non valides.")
    model = str(metadata.get("model", "")).strip()
    prompt_version = str(metadata.get("prompt_version", "")).strip()
    digest = str(metadata.get("output_hash", "")).strip().lower()
    source_refs = metadata.get("source_refs", [])
    if (metadata.get("provider") != "openai" or metadata.get("store") is not False
            or not model or len(model) > 160 or not prompt_version or len(prompt_version) > 100
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
            or source_refs != [source_ref]):
        raise ValueError("Métadonnées de traçabilité CV incomplètes.")
    duration = metadata.get("duration_seconds")
    if not isinstance(duration, (int, float)) or duration < 0:
        raise ValueError("Durée d’analyse IA non valide.")
    usage = {}
    for key in ("input_tokens", "output_tokens"):
        value = metadata.get(key)
        if value is not None and (not isinstance(value, int) or value < 0):
            raise ValueError("Consommation IA non valide.")
        usage[key] = value

    engine = build_engine(database_url)
    session = session_factory(engine)()
    try:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        event = AuditEvent(
            case_id=case_id,
            event_type="CV_ENRICHMENT_IA_PROPOSEE",
            object_type="GDA_DOCUMENT",
            object_id=source_ref,
            object_version=None,
            actor_type=ctx.actor_role.value,
            actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({
                "source_ref": source_ref,
                "source_version": version,
                "provider": "openai",
                "model": model,
                "prompt_version": prompt_version,
                "store": False,
                "output_hash": digest,
                "duration_seconds": round(float(duration), 3),
                **usage,
                "status": "PROPOSITIONS_A_VALIDER",
            }, ensure_ascii=False, separators=(",", ":")),
        )
        session.add(event)
        session.commit()
        return event.audit_event_id
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
