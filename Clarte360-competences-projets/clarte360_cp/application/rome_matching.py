"""GO22: atelier ROME/parcours, propositions IA et validations humaines versionnées."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select, update

from clarte360_cp.application.orientation import _context, OrientationAccessDenied, OrientationConflict
from clarte360_cp.connectors.cav3_ai import Cav3AIError, Cav3AISettings
from clarte360_cp.connectors.rome_matching_ai import analyze_rome_matching
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.domain.rome_matching import RomeStudyItem, rome_study_items, validate_review_rows
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import (
    AuditEvent, CareerItem, CareerVersion, Case, ExternalSnapshot, JobTarget, MatchingEvidence,
    MatchingItem, PhaseEvent, PhaseState,
    RomeMatchingAnalysis, RomeMatchingReview,
)


class RomeMatchingError(RuntimeError):
    """Safe workflow error for ROME matching."""


@dataclass(frozen=True)
class MatchingExperience:
    id: str
    title: str
    kind: str
    organization: str | None
    period: str
    evidence: str


@dataclass(frozen=True)
class MatchingTarget:
    id: str
    code: str
    label: str
    snapshot_id: str | None
    source_date: str | None
    source_version: str | None
    items: tuple[RomeStudyItem, ...]


@dataclass(frozen=True)
class MatchingWorkspace:
    case_id: str
    targets: tuple[MatchingTarget, ...]
    experiences: tuple[MatchingExperience, ...]
    fingerprint_by_target: tuple[tuple[str, str], ...]
    analyses: tuple[dict[str, Any], ...]
    current_reviews: tuple[tuple[str, str, dict[str, Any]], ...]


def _experience_facts(details_json: str | None) -> str:
    if not details_json:
        return ""
    try:
        data = json.loads(details_json)
    except (TypeError, json.JSONDecodeError):
        return str(details_json)[:5000]
    if not isinstance(data, dict):
        return str(data)[:5000]
    keys = (
        "context", "contexte", "activities", "activites", "missions", "responsabilites",
        "autonomie", "realisations", "resultats", "outils", "methodes", "savoirs",
        "savoir_faire", "competences", "faits_valides", "apport_seance", "summary",
    )
    pieces: list[str] = []
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            pieces.append(value.strip())
        elif isinstance(value, list):
            pieces.extend(str(x).strip() for x in value if isinstance(x, (str, int)) and str(x).strip())
        elif isinstance(value, dict):
            pieces.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
    level = data.get("niveau_exercice")
    level_labels = {
        1: "pratique encadrée / contribution",
        2: "maîtrise autonome",
        3: "pilotage / expertise / transmission",
    }
    if isinstance(level, int) and level in level_labels:
        pieces.append(f"Niveau d’exercice discuté en séance : {level} — {level_labels[level]}.")
    return "\n".join(pieces)[:6000]


def _fingerprint(target: MatchingTarget, experiences: tuple[MatchingExperience, ...]) -> str:
    basis = {
        "target_id": target.id,
        "code": target.code,
        "label": target.label,
        "snapshot_id": target.snapshot_id,
        "source_version": target.source_version,
        "items": [{"key": x.key, "label": x.label, "category": x.category} for x in target.items],
        "experiences": [{"id": x.id, "title": x.title, "period": x.period, "evidence": x.evidence} for x in experiences],
    }
    return hashlib.sha256(json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _load_workspace(session, case_id: str) -> MatchingWorkspace:
    targets: list[MatchingTarget] = []
    for target in session.scalars(
        select(JobTarget).where(JobTarget.case_id == case_id, JobTarget.status == "ACTIVE")
        .order_by(JobTarget.selected_order, JobTarget.rome_label)
    ):
        snapshot = session.get(ExternalSnapshot, target.snapshot_id) if target.snapshot_id else None
        payload: dict[str, Any] = {}
        if snapshot:
            try:
                payload = json.loads(snapshot.payload_json)
            except (TypeError, json.JSONDecodeError):
                payload = {}
        targets.append(MatchingTarget(
            id=target.job_target_id, code=target.rome_code, label=target.rome_label,
            snapshot_id=target.snapshot_id,
            source_date=snapshot.effective_date or snapshot.fetched_at.date().isoformat() if snapshot else None,
            source_version=(str(payload.get("version") or payload.get("versionReferentiel")
                            or payload.get("version_referentiel") or payload.get("numero_version"))
                            if snapshot and isinstance(payload, dict) and any(payload.get(k) for k in ("version", "versionReferentiel", "version_referentiel", "numero_version"))
                            else (snapshot.provider + "/" + snapshot.resource_type if snapshot else None)),
            items=rome_study_items(payload),
        ))
    experiences = tuple(
        MatchingExperience(
            id=item.career_item_id, title=item.title, kind=item.item_type, organization=item.organization,
            period=" — ".join(value for value in (item.start_date, item.end_date) if value),
            evidence=_experience_facts(item.details_json),
        )
        for item in session.scalars(select(CareerItem).where(
            CareerItem.case_id == case_id, CareerItem.status == "ACTIVE",
        ).order_by(CareerItem.start_date, CareerItem.title))
    )
    fingerprints = tuple((target.id, _fingerprint(target, experiences)) for target in targets)
    analyses: list[dict[str, Any]] = []
    reviews: list[tuple[str, str, dict[str, Any]]] = []
    for target in targets:
        fp = dict(fingerprints)[target.id]
        for row in session.scalars(select(RomeMatchingAnalysis).where(
            RomeMatchingAnalysis.case_id == case_id, RomeMatchingAnalysis.job_target_id == target.id,
        ).order_by(RomeMatchingAnalysis.created_at.desc())):
            analyses.append({"analysis_id": row.analysis_id, "job_target_id": target.id,
                             "source_fingerprint": row.source_fingerprint, "current": row.source_fingerprint == fp,
                             "provider": row.provider, "model": row.model,
                             "result": json.loads(row.result_json), "created_at": row.created_at.isoformat()})
            break
        latest_review = session.scalar(select(RomeMatchingReview).where(
            RomeMatchingReview.case_id == case_id, RomeMatchingReview.job_target_id == target.id,
        ).order_by(RomeMatchingReview.version_no.desc()).limit(1))
        if latest_review:
            reviews.append((target.id, latest_review.source_fingerprint, json.loads(latest_review.review_json)))
    return MatchingWorkspace(case_id, tuple(targets), experiences, fingerprints,
                             tuple(analyses), tuple(reviews))


def read_rome_matching_workspace(ctx, case_id: str, *, database_url: str | None = None) -> MatchingWorkspace:
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_READ")
        return _load_workspace(session, case_id)


def read_career_cards(ctx, case_id: str, *, database_url: str | None = None) -> tuple[dict[str, Any], ...]:
    """Read the case's active career cards for accompanist-led enrichment."""
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_READ")
        result = []
        for item in session.scalars(select(CareerItem).where(
            CareerItem.case_id == case_id, CareerItem.status == "ACTIVE",
        ).order_by(CareerItem.start_date, CareerItem.title)):
            try:
                details = json.loads(item.details_json or "{}")
            except (TypeError, json.JSONDecodeError):
                details = {}
            if not isinstance(details, dict):
                details = {}
            result.append({"id": item.career_item_id, "kind": item.item_type, "title": item.title,
                "organization": item.organization or "", "period_start": item.start_date or "",
                "period_end": item.end_date or "", "details": details,
                "source_linked": bool(item.source_artifact_version_id)})
        return tuple(result)


def _reopen_dependent_phases(session, case_id: str, ctx, *, reason: str) -> None:
    """Keep shared outputs hidden/reviewable after the underlying career evidence changes."""
    changed_any = False
    for phase_no in (0, *range(3, 12)):
        state = session.scalar(select(PhaseState).where(
            PhaseState.case_id == case_id, PhaseState.phase_no == phase_no,
        ))
        if state is None or state.state not in {"VALIDEE", "FIGEE_CLOTURE"}:
            continue
        previous = state.state
        state.state = "REOUVERTE"
        state.current_version_no += 1
        session.add(PhaseEvent(case_id=case_id, phase_no=phase_no, from_state=previous,
            to_state="REOUVERTE", actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            reason=reason))
        changed_any = True
    if changed_any:
        case = session.get(Case, case_id)
        if case is not None:
            case.current_phase = 0
            case.status = "EN_COURS"


def add_session_experience(ctx, case_id: str, *, title: str, kind: str = "EMPLOI", organization: str = "",
                           period_start: str = "", period_end: str = "", context: str = "",
                           activities: str = "", autonomy: str = "", achievements: str = "",
                           tools: str = "", knowledge: str = "", level_of_exercise: int | None = None,
                           source_ref: str | None = None, source_span_ref: str | None = None,
                           database_url: str | None = None) -> str:
    """Record a beneficiary-confirmed experience detail added during the session."""
    normalized_title = str(title or "").strip()
    if not normalized_title or len(normalized_title) > 240:
        raise ValueError("Indiquez l’intitulé de cette expérience (240 caractères maximum).")
    kind = str(kind or "").strip().upper()
    if kind not in {"EMPLOI", "ETUDE", "FORMATION", "AUTOFORMATION", "AUTRE"}:
        raise ValueError("Choisissez une nature de parcours reconnue.")
    if level_of_exercise not in {None, 1, 2, 3}:
        raise ValueError("Le niveau d’exercice doit être 1, 2 ou 3.")
    details = {
        "context": str(context or "").strip()[:2400],
        "activities": str(activities or "").strip()[:2400],
        "autonomie": str(autonomy or "").strip()[:1200],
        "realisations": str(achievements or "").strip()[:2400],
        "outils": str(tools or "").strip()[:1200],
        "savoirs": str(knowledge or "").strip()[:1600],
        "niveau_exercice": level_of_exercise,
        "niveau_exercice_source": "DISCUTE_EN_SEANCE" if level_of_exercise is not None else None,
        "provenance": "REFERENCE_GDA" if source_ref else "APPORT_SEANCE",
        "source_ref": str(source_ref or "")[:160] or None,
        "nature_parcours": kind,
        "statut_humain": "A_CONFIRMER",
    }
    engine = build_engine(database_url)
    session = session_factory(engine)()
    try:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        evidence_ref = (str(source_span_ref or "").strip()[:160] if source_ref else "")
        if evidence_ref:
            existing = session.scalar(select(CareerItem).where(
                CareerItem.case_id == case_id, CareerItem.source_span_ref == evidence_ref,
                CareerItem.status == "ACTIVE",
            ))
            if existing is not None:
                return existing.career_item_id
        row = CareerItem(
            case_id=case_id, item_type=kind, title=normalized_title,
            organization=str(organization or "").strip()[:240] or None,
            start_date=str(period_start or "").strip()[:20] or None,
            end_date=str(period_end or "").strip()[:20] or None,
            details_json=json.dumps(details, ensure_ascii=False, separators=(",", ":")),
            source_span_ref=(evidence_ref or f"GDA:{str(source_ref)[:150]}" if source_ref else "APPORT_SEANCE"), status="ACTIVE",
        )
        session.add(row); session.flush()
        # A new experience changes the evidence base. Previously saved links
        # remain in immutable review history but are no longer presented as a
        # current review until the accompanist revisits them.
        session.execute(update(MatchingItem).where(
            MatchingItem.case_id == case_id, MatchingItem.review_required == 0,
        ).values(review_required=1))
        _reopen_dependent_phases(session, case_id, ctx,
            reason="Un élément du parcours a été ajouté ; reprendre la validation du parcours et des rapprochements.")
        session.add(AuditEvent(case_id=case_id, event_type="CAREER_ITEM_APPORT_SEANCE",
            object_type="CAREER_ITEM", object_id=row.career_item_id, object_version=1,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"provenance": "REFERENCE_GDA" if source_ref else "APPORT_SEANCE", "statut_humain": "A_CONFIRMER"})))
        session.commit()
        return row.career_item_id
    except BaseException:
        session.rollback(); raise
    finally:
        session.close()


def update_session_experience(ctx, case_id: str, experience_id: str, *, title: str, kind: str,
                              organization: str = "", period_start: str = "", period_end: str = "",
                              context: str = "", activities: str = "", autonomy: str = "",
                              achievements: str = "", tools: str = "", knowledge: str = "",
                              level_of_exercise: int | None = None, beneficiary_reviewed: bool = False,
                              database_url: str | None = None) -> None:
    """Update one structured career card after a human-led session review."""
    normalized_title = str(title or "").strip()
    if not normalized_title or len(normalized_title) > 240:
        raise ValueError("Indiquez l’intitulé de cette expérience (240 caractères maximum).")
    kind = str(kind or "").strip().upper()
    if kind not in {"EMPLOI", "ETUDE", "FORMATION", "AUTOFORMATION", "AUTRE"}:
        raise ValueError("Choisissez une nature de parcours reconnue.")
    if level_of_exercise not in {None, 1, 2, 3}:
        raise ValueError("Le niveau d’exercice doit être 1, 2 ou 3.")
    engine = build_engine(database_url)
    session = session_factory(engine)()
    try:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        row = session.get(CareerItem, experience_id)
        if row is None or row.case_id != case_id or row.status != "ACTIVE":
            raise RomeMatchingError("Cette carte de parcours n’est plus disponible dans ce dossier.")
        try:
            existing = json.loads(row.details_json or "{}")
        except (TypeError, json.JSONDecodeError):
            existing = {}
        if not isinstance(existing, dict):
            existing = {}
        provenance = existing.get("provenance") or ("REFERENCE_GDA" if row.source_artifact_version_id else "APPORT_SEANCE")
        details = {**existing,
            "context": str(context or "").strip()[:2400],
            "activities": str(activities or "").strip()[:2400],
            "autonomie": str(autonomy or "").strip()[:1200],
            "realisations": str(achievements or "").strip()[:2400],
            "outils": str(tools or "").strip()[:1200],
            "savoirs": str(knowledge or "").strip()[:1600],
            "niveau_exercice": level_of_exercise,
            "niveau_exercice_source": "DISCUTE_EN_SEANCE" if level_of_exercise is not None else None,
            "provenance": provenance,
            "nature_parcours": kind,
            "statut_humain": "RELUE_EN_SEANCE" if beneficiary_reviewed else "A_CONFIRMER",
        }
        row.item_type = kind
        row.title = normalized_title
        row.organization = str(organization or "").strip()[:240] or None
        row.start_date = str(period_start or "").strip()[:20] or None
        row.end_date = str(period_end or "").strip()[:20] or None
        row.details_json = json.dumps(details, ensure_ascii=False, separators=(",", ":"))
        next_version = int(session.scalar(select(func.max(CareerVersion.version_no)).where(
            CareerVersion.case_id == case_id)) or 0) + 1
        session.add(CareerVersion(case_id=case_id, version_no=next_version,
            state="RELUE_EN_SEANCE" if beneficiary_reviewed else "BROUILLON",
            summary_json=json.dumps({"experience_id": row.career_item_id, "item_type": row.item_type,
                "title": row.title, "organization": row.organization, "start_date": row.start_date,
                "end_date": row.end_date, "details": details}, ensure_ascii=False, separators=(",", ":"))))
        session.execute(update(MatchingItem).where(
            MatchingItem.case_id == case_id, MatchingItem.review_required == 0,
        ).values(review_required=1))
        _reopen_dependent_phases(session, case_id, ctx,
            reason="Un élément du parcours a été modifié ; reprendre la validation du parcours et des rapprochements.")
        session.add(AuditEvent(case_id=case_id, event_type="CAREER_ITEM_SESSION_REVIEWED",
            object_type="CAREER_ITEM", object_id=row.career_item_id, object_version=1,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"provenance": provenance,
                "beneficiary_reviewed": bool(beneficiary_reviewed), "level_present": level_of_exercise is not None})))
        session.commit()
    except BaseException:
        session.rollback(); raise
    finally:
        session.close()


def _target_context(workspace: MatchingWorkspace, target_id: str) -> tuple[MatchingTarget, str]:
    target = next((x for x in workspace.targets if x.id == target_id), None)
    if target is None:
        raise RomeMatchingError("Ce métier ROME n'est plus sélectionné dans le dossier.")
    fingerprint = dict(workspace.fingerprint_by_target)[target_id]
    return target, fingerprint


def run_rome_matching_analysis(ctx, case_id: str, target_id: str, *, selected_item_keys: list[str] | None = None,
                               ai_settings: Cav3AISettings | None = None,
                               database_url: str | None = None, client: Any | None = None) -> dict[str, Any]:
    workspace = read_rome_matching_workspace(ctx, case_id, database_url=database_url)
    target, fingerprint = _target_context(workspace, target_id)
    if not target.items:
        raise RomeMatchingError("La fiche ROME enregistrée ne contient pas encore de savoirs/compétences exploitables. Actualisez la fiche avant l'analyse.")
    if not workspace.experiences:
        raise RomeMatchingError("Aucune expérience du parcours n'est structurée. Ajoutez ou validez d'abord les éléments du parcours en séance.")
    selected_keys = list(dict.fromkeys(selected_item_keys or [item.key for item in target.items]))
    available_items = {item.key: item for item in target.items}
    if not selected_keys or any(key not in available_items for key in selected_keys):
        raise RomeMatchingError("La sélection d’attendus ne correspond plus à la fiche ROME actuelle.")
    if len(selected_keys) > 40:
        raise RomeMatchingError("Pour garder une analyse lisible en séance, sélectionnez au plus 40 attendus à la fois.")
    selected_items = [available_items[key] for key in selected_keys]
    source_experiences = [{"id": item.id, "title": item.title, "kind": item.kind,
                           "period": item.period, "evidence": item.evidence}
                          for item in workspace.experiences]
    output = analyze_rome_matching(
        {"rome_code": target.code, "label": target.label},
        [{"key": item.key, "label": item.label, "category": item.category} for item in selected_items],
        source_experiences, ai_settings or Cav3AISettings.from_streamlit_secrets(), client=client,
    )
    session = session_factory(build_engine(database_url))()
    try:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        current = _load_workspace(session, case_id)
        current_target, current_fp = _target_context(current, target_id)
        if current_fp != fingerprint:
            raise OrientationConflict("Le métier ROME ou le parcours a changé pendant l'analyse. Relancez-la sur la version actuelle.")
        row = RomeMatchingAnalysis(
            case_id=case_id, job_target_id=target_id, source_fingerprint=fingerprint,
            provider=output["provider"], model=output["model"],
            result_json=json.dumps({**output["result"], "_metadata": output["metadata"],
                                    "_source": {"snapshot_id": current_target.snapshot_id,
                                                "rome_code": current_target.code,
                                                "source_version": current_target.source_version,
                                                "item_keys": selected_keys}},
                                   ensure_ascii=False, separators=(",", ":")),
            created_by=ctx.actor_id,
        )
        session.add(row); session.flush()
        session.add(AuditEvent(case_id=case_id, event_type="ROME_MATCHING_IA_PROPOSED",
            object_type="ROME_MATCHING_ANALYSIS", object_id=row.analysis_id, object_version=1,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"job_target_id": target_id, "fingerprint": fingerprint,
                                                "provider": output["provider"], "model": output["model"]})))
        session.commit()
        return {"analysis_id": row.analysis_id, "job_target_id": target_id, "source_fingerprint": fingerprint,
                "provider": row.provider, "model": row.model, "result": output["result"],
                "created_at": row.created_at.isoformat(), "current": True}
    except BaseException:
        session.rollback(); raise
    finally:
        session.close()


def save_rome_matching_review(ctx, case_id: str, target_id: str, rows: list[dict[str, Any]], *,
                              analysis_id: str | None = None, database_url: str | None = None) -> dict[str, Any]:
    engine = build_engine(database_url)
    session = session_factory(engine)()
    try:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        workspace = _load_workspace(session, case_id)
        target, fingerprint = _target_context(workspace, target_id)
        validated = validate_review_rows(rows, {x.key for x in target.items}, {x.id for x in workspace.experiences})
        analysis = session.get(RomeMatchingAnalysis, analysis_id) if analysis_id else None
        if analysis_id and (analysis is None or analysis.case_id != case_id or analysis.job_target_id != target_id or analysis.source_fingerprint != fingerprint):
            raise OrientationConflict("La proposition IA a été faite sur une version différente. Relancez l'analyse avant de l'utiliser.")
        version_no = int(session.scalar(select(func.max(RomeMatchingReview.version_no)).where(
            RomeMatchingReview.case_id == case_id, RomeMatchingReview.job_target_id == target_id)) or 0) + 1
        items_by_key = {x.key: x for x in target.items}
        experiences_by_id = {x.id: x for x in workspace.experiences}
        suggestions = {}
        if analysis:
            payload = json.loads(analysis.result_json)
            suggestions = {p["rome_item_key"]: p for p in payload.get("propositions", [])}
        reviewed_content: list[dict[str, Any]] = []
        for row in validated:
            ref = items_by_key[row["rome_item_key"]]
            suggestion = suggestions.get(ref.key, {})
            matching = session.scalar(select(MatchingItem).where(
                MatchingItem.case_id == case_id, MatchingItem.job_target_id == target_id,
                MatchingItem.rome_item_key == ref.key,
            ).order_by(MatchingItem.version_no.desc()).limit(1))
            if matching is None:
                matching = MatchingItem(case_id=case_id, job_target_id=target_id, rome_item_key=ref.key,
                                        category=ref.category, rome_label=ref.label, version_no=version_no)
                session.add(matching); session.flush()
            else:
                matching.version_no += 1
                matching.category = ref.category
                matching.rome_label = ref.label
            matching.proposed_status = suggestion.get("statut_propose")
            matching.final_status = row["status"]
            matching.exercise_level = row["exercise_level"]
            matching.review_required = 0
            session.execute(delete(MatchingEvidence).where(MatchingEvidence.matching_id == matching.matching_id))
            evidence_rows = []
            for experience_id in row["experience_ids"]:
                experience = experiences_by_id[experience_id]
                evidence = MatchingEvidence(
                    case_id=case_id, matching_id=matching.matching_id, source_type="CAREER_ITEM",
                    source_id=experience.id, source_version=None, rationale=row["rationale"] or suggestion.get("raisonnement", "Élément de parcours relié en séance."),
                    created_by=ctx.actor_id,
                )
                session.add(evidence)
                evidence_rows.append({"experience_id": experience.id, "title": experience.title,
                                      "period": experience.period, "evidence": experience.evidence})
            reviewed_content.append({
                "rome_item_key": ref.key, "rome_label": ref.label, "category": ref.category,
                "status": row["status"], "rationale": row["rationale"],
                "exercise_level": row["exercise_level"],
                "experiences": evidence_rows,
                "ai_proposal": {k: suggestion.get(k) for k in ("statut_propose", "raisonnement", "question_en_seance")},
            })
        review = RomeMatchingReview(
            case_id=case_id, job_target_id=target_id, version_no=version_no,
            source_fingerprint=fingerprint,
            review_json=json.dumps({"job_code": target.code, "job_label": target.label,
                                    "rome_snapshot_id": target.snapshot_id,
                                    "rome_source_version": target.source_version,
                                    "rome_source_date": target.source_date,
                                    "items": reviewed_content}, ensure_ascii=False, separators=(",", ":")),
            created_by=ctx.actor_id,
        )
        session.add(review); session.flush()
        session.add(AuditEvent(case_id=case_id, event_type="ROME_MATCHING_REVIEW_SAVED",
            object_type="ROME_MATCHING_REVIEW", object_id=review.review_id, object_version=version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"job_target_id": target_id, "items_count": len(reviewed_content),
                                                "version_no": version_no, "fingerprint": fingerprint})))
        session.commit()
        return {"review_id": review.review_id, "version_no": version_no,
                "items_count": len(reviewed_content), "source_fingerprint": fingerprint}
    except BaseException:
        session.rollback(); raise
    finally:
        session.close()
