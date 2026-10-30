"""Load and record official ROME fiche snapshots for the selected métiers."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import func, select, update

from clarte360_cp.application.orientation import _context
from clarte360_cp.connectors.france_travail import FranceTravailRomeClient, FranceTravailSettings
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import AuditEvent, ExternalSnapshot, JobTarget, MatchingItem, SnapshotUsage


class RomeCatalogError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _local_catalog() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "rome_catalog.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise RomeCatalogError("Le référentiel ROME local n’est pas disponible dans cette installation.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise RomeCatalogError("Le référentiel ROME local n’a pas un format exploitable.")
    return payload


def search_local_rome(query: str, *, limit: int = 40) -> tuple[dict[str, str], ...]:
    """Search the packaged dated ROME reference, ranking exact and primary labels first."""
    term = _normalize_search_text(query)
    if not term:
        return ()
    catalog = _local_catalog()
    matches: list[tuple[int, str, dict[str, str]]] = []
    for item in catalog["items"]:
        code = str(item.get("code", ""))
        label = str(item.get("intitule", ""))
        code_text = _normalize_search_text(code)
        label_text = _normalize_search_text(label)
        appellations = item.get("appellations", {})
        aliases = appellations.get("appellation", []) if isinstance(appellations, dict) else []
        if not isinstance(aliases, list):
            aliases = [aliases]
        alias_texts = [_normalize_search_text(row.get("libelle", ""))
                       for row in aliases if isinstance(row, dict)]
        score = 0
        if term == code_text:
            score = 100
        elif term == label_text:
            score = 90
        elif label_text.startswith(term):
            score = 80
        elif term in label_text:
            score = 70
        elif term in alias_texts:
            score = 60
        elif any(alias.startswith(term) for alias in alias_texts):
            score = 50
        elif any(term in alias for alias in alias_texts):
            score = 40
        elif term in code_text:
            score = 30
        if score:
            matches.append((score, label_text, {"code": code, "label": label}))
    matches.sort(key=lambda row: (-row[0], row[1], row[2]["code"]))
    return tuple(row[2] for row in matches[:max(1, min(int(limit), 200))])


def _normalize_search_text(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or "").casefold())
    return "".join(char for char in text if not unicodedata.combining(char)).strip()


def read_local_rome_metadata() -> dict[str, Any]:
    """Return the version/date/count visible for the packaged searchable corpus."""
    catalog = _local_catalog()
    return {
        "version": str(catalog.get("version", "")),
        "publication_date": str(catalog.get("publication_date", "")),
        "entry_count": int(catalog.get("entry_count", len(catalog["items"]))),
        "source_file": str(catalog.get("source_file", "")),
    }


def _persist_target_snapshot(ctx, case_id: str, code: str, title: str, payload: dict[str, Any], *,
                             provider: str, resource_type: str, fetched_at: datetime,
                             effective_date: str, database_url: str | None = None) -> dict[str, Any]:
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    engine = build_engine(database_url)
    session = session_factory(engine)()
    try:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        existing = session.scalar(select(JobTarget).where(
            JobTarget.case_id == case_id, JobTarget.rome_code == code,
            JobTarget.status.in_(("ACTIVE", "PROPOSITION")),
        ).order_by(JobTarget.status))
        active_count = int(session.scalar(select(func.count()).select_from(JobTarget).where(
            JobTarget.case_id == case_id, JobTarget.status == "ACTIVE")) or 0)
        proposal_count = int(session.scalar(select(func.count()).select_from(JobTarget).where(
            JobTarget.case_id == case_id, JobTarget.status == "PROPOSITION")) or 0)
        if not existing and active_count + proposal_count >= 3:
            raise RomeCatalogError("Trois métiers sont déjà actifs ou proposés. Écartez une proposition avant d’en charger un autre.")
        if existing and existing.snapshot_id:
            previous = session.get(ExternalSnapshot, existing.snapshot_id)
            if previous and previous.sha256 == checksum and previous.provider == provider and previous.resource_type == resource_type:
                session.add(AuditEvent(case_id=case_id, event_type="ROME_FICHE_REFRESH_UNCHANGED",
                    object_type="JOB_TARGET", object_id=existing.job_target_id, object_version=1,
                    actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
                    metadata_json_minimized=json.dumps({"rome_code": code, "snapshot_id": existing.snapshot_id,
                        "sha256": checksum, "provider": provider, "checked_at": fetched_at.isoformat(),
                        "effective_date": effective_date})))
                session.commit()
                return {"job_target_id": existing.job_target_id, "code": code, "label": existing.rome_label,
                    "snapshot_id": existing.snapshot_id, "source_version": payload.get("version"),
                    "fetched_at": previous.fetched_at.isoformat(), "sha256": checksum, "status": existing.status,
                    "source_provider": previous.provider, "source_date": previous.effective_date,
                    "unchanged": True}
        row = ExternalSnapshot(case_id=case_id, provider=provider, resource_type=resource_type,
            external_key=code, fetched_at=fetched_at, effective_date=effective_date,
            payload_json=payload_json, sha256=checksum)
        session.add(row); session.flush()
        if existing:
            previous_snapshot_id = existing.snapshot_id
            existing.snapshot_id = row.snapshot_id
            existing.rome_label = title
            target = existing
            if previous_snapshot_id != row.snapshot_id:
                session.execute(update(MatchingItem).where(
                    MatchingItem.case_id == case_id, MatchingItem.job_target_id == target.job_target_id,
                ).values(review_required=1))
        else:
            target = JobTarget(case_id=case_id, rome_code=code, rome_label=title,
                               snapshot_id=row.snapshot_id, status="PROPOSITION")
            session.add(target); session.flush()
        session.add(SnapshotUsage(case_id=case_id, snapshot_id=row.snapshot_id,
            object_type="JOB_TARGET", object_id=target.job_target_id, object_version=1,
            usage_role="METIER_ETUDIE"))
        session.add(AuditEvent(case_id=case_id,
            event_type="ROME_FICHE_OFFLINE_IMPORTED" if provider == "FRANCE_TRAVAIL_OPENDATA" else "ROME_FICHE_REFRESHED",
            object_type="JOB_TARGET", object_id=target.job_target_id, object_version=1,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"rome_code": code, "snapshot_id": target.snapshot_id,
                "sha256": checksum, "provider": provider, "resource_type": resource_type,
                "effective_date": effective_date})))
        session.commit()
        return {"job_target_id": target.job_target_id, "code": code, "label": title,
                "snapshot_id": target.snapshot_id, "source_version": payload.get("version"),
                "fetched_at": fetched_at.isoformat(), "sha256": checksum, "status": target.status,
                "source_provider": provider, "source_date": effective_date}
    except BaseException:
        session.rollback(); raise
    finally:
        session.close()


def read_rome_targets(ctx, case_id: str, *, database_url: str | None = None) -> tuple[dict[str, Any], ...]:
    from clarte360_cp.repositories.models import Case, CaseContextRef
    from clarte360_cp.application.orientation import OrientationAccessDenied
    from sqlalchemy import select
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_READ")
        rows = session.scalars(select(JobTarget).where(JobTarget.case_id == case_id,
            JobTarget.status.in_(("ACTIVE", "PROPOSITION", "ECARTE")))
            .order_by(JobTarget.selected_order, JobTarget.rome_label)).all()
        result = []
        for row in rows:
            snap = session.get(ExternalSnapshot, row.snapshot_id) if row.snapshot_id else None
            version = None
            payload = {}
            if snap and snap.payload_json:
                try:
                    payload = json.loads(snap.payload_json)
                    version = (payload.get("version") or payload.get("versionReferentiel")
                               or payload.get("version_referentiel") or payload.get("numero_version"))
                except (TypeError, ValueError):
                    version = None
            result.append({"id": row.job_target_id, "code": row.rome_code, "label": row.rome_label,
                           "status": row.status, "source_date": snap.effective_date if snap else None,
                           "source_version": str(version) if version is not None else None,
                           "source_provider": snap.provider if snap else None,
                           "source_resource_type": snap.resource_type if snap else None,
                           "definition": str(payload.get("definition") or "") if isinstance(payload, dict) else "",
                           "access_description": str(payload.get("acces_metier") or "") if isinstance(payload, dict) else ""})
        return tuple(result)


def _settings_from_secrets(section: Mapping[str, Any] | None = None, *, require_fiche_scope: bool = True) -> FranceTravailSettings:
    if section is None:
        try:
            import streamlit as st
            section = st.secrets.get("france_travail", {})
        except Exception:
            section = {}
    if not isinstance(section, Mapping):
        raise RomeCatalogError("La configuration centrale France Travail est illisible.")
    try:
        settings = FranceTravailSettings.from_mapping(section)
    except Exception as exc:
        raise RomeCatalogError(str(exc)) from None
    if require_fiche_scope and not settings.rome_fiches_scope:
        raise RomeCatalogError("Le scope ROME Fiches métiers doit être configuré dans la section France Travail centrale.")
    return settings


def search_rome_metiers(query: str, *, settings: FranceTravailSettings | None = None,
                        client: Any | None = None, limit: int = 60) -> tuple[dict[str, str], ...]:
    """Search the France Travail ROME Métiers API, independently of the Fiches scope."""
    api = client or FranceTravailRomeClient(settings or _settings_from_secrets(require_fiche_scope=False))
    try:
        return api.search_metiers(query, limit=limit)
    except Exception as exc:
        message = str(exc)
        if any(secret_word in message.casefold() for secret_word in ("secret", "bearer", "token", "client_id", "client_secret")):
            raise RomeCatalogError("La recherche France Travail a échoué ; le détail de sécurité n’est pas affiché.") from None
        raise RomeCatalogError(message) from None


def _label(payload: dict[str, Any], code: str) -> str:
    for key in ("intitule", "libelle", "label", "nom"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:240]
    for key in ("ficheMetier", "fiche_metier", "metier", "rome"):
        child = payload.get(key)
        if isinstance(child, dict):
            for subkey in ("intitule", "libelle", "label", "nom"):
                value = child.get(subkey)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:240]
    raise RomeCatalogError(f"La fiche API du métier {code} ne contient pas d’intitulé reconnu.")


def prepare_rome_target(ctx, case_id: str, code: str, *, database_url: str | None = None,
                        settings: FranceTravailSettings | None = None, client: Any | None = None,
                        force_refresh: bool = False) -> dict[str, Any]:
    """Fetch a fiche and persist an unconfirmed proposal; selection is explicit in session."""
    normalized = str(code or "").strip().upper()
    if len(normalized) != 5 or not normalized[0].isalpha() or not normalized[1:].isdigit():
        raise RomeCatalogError("Saisissez un code ROME valide (une lettre suivie de quatre chiffres).")
    api = client or FranceTravailRomeClient(settings or _settings_from_secrets())
    try:
        snapshot = api.fetch_fiche_metier(normalized, force_refresh=force_refresh)
    except Exception as exc:
        message = str(exc)
        if any(secret_word in message.casefold() for secret_word in ("secret", "bearer", "token", "client_id", "client_secret")):
            raise RomeCatalogError("L’appel France Travail a échoué ; le détail de sécurité n’est pas affiché.") from None
        raise RomeCatalogError(message) from None
    if snapshot.code != normalized:
        raise RomeCatalogError("La fiche retournée ne correspond pas au code ROME demandé.")
    title = _label(dict(snapshot.payload), normalized)
    return _persist_target_snapshot(ctx, case_id, normalized, title, dict(snapshot.payload),
        provider=snapshot.provider, resource_type=snapshot.resource_type, fetched_at=snapshot.fetched_at,
        effective_date=snapshot.fetched_at.date().isoformat(), database_url=database_url)


def prepare_local_rome_target(ctx, case_id: str, code: str, *, database_url: str | None = None) -> dict[str, Any]:
    normalized = str(code or "").strip().upper()
    entry = next((row for row in _local_catalog()["items"] if row.get("code") == normalized), None)
    if entry is None:
        metadata = read_local_rome_metadata()
        raise RomeCatalogError(f"Ce code ROME n’est pas présent dans le référentiel local {metadata['version']}.")
    catalog = _local_catalog()
    payload = {**entry, "version": catalog["version"], "publication_date": catalog["publication_date"],
               "source_file": catalog["source_file"]}
    return _persist_target_snapshot(ctx, case_id, normalized, str(entry["intitule"]), payload,
        provider="FRANCE_TRAVAIL_OPENDATA", resource_type="ROME_FICHE_METIER_OFFLINE",
        fetched_at=datetime.now(timezone.utc), effective_date=str(catalog["publication_date"]),
        database_url=database_url)


def decide_rome_target(ctx, case_id: str, target_id: str, *, accept: bool,
                       database_url: str | None = None) -> str:
    engine = build_engine(database_url)
    session = session_factory(engine)()
    try:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        target = session.get(JobTarget, target_id)
        if target is None or target.case_id != case_id or target.status != "PROPOSITION":
            raise RomeCatalogError("Cette proposition n’est plus disponible.")
        if accept:
            active_count = int(session.scalar(select(func.count()).select_from(JobTarget).where(
                JobTarget.case_id == case_id, JobTarget.status == "ACTIVE")) or 0)
            if active_count >= 3:
                raise RomeCatalogError("Le dossier contient déjà trois métiers sélectionnés.")
            target.status = "ACTIVE"
            target.beneficiary_confirmed_at = datetime.now(timezone.utc)
            event_type = "ROME_METIER_CONFIRME_EN_SEANCE"
        else:
            target.status = "ECARTE"
            event_type = "ROME_METIER_ECARTE"
        session.add(AuditEvent(case_id=case_id, event_type=event_type, object_type="JOB_TARGET",
            object_id=target.job_target_id, object_version=1, actor_type=ctx.actor_role.value,
            actor_id=ctx.actor_id, metadata_json_minimized=json.dumps({"rome_code": target.rome_code})))
        session.commit()
        return target.status
    except BaseException:
        session.rollback(); raise
    finally:
        session.close()
