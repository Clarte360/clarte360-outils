"""GO24 — résultats, synthèse, remise et suivi à six mois."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import func, select

from clarte360_cp.application.orientation import _context, OrientationAccessDenied
from clarte360_cp.domain.enums import ActorRole
from clarte360_cp.repositories import build_engine, session_factory
from clarte360_cp.repositories.models import (
    ActionPlan, Artifact, ArtifactVersion, AuditEvent, Case, ClosureRecord,
    FollowUpPlan, FollowUpResponse, ResultSet, ReviewFlag, SynthesisRecord, Validation,
)


RESULT_FIELDS = (
    ("parcours", "Parcours et éléments déterminants"),
    ("savoirs", "Savoirs et compétences mobilisables"),
    ("projet", "Projet retenu et raisons"),
    ("conditions", "Conditions de réalisation"),
    ("vigilances", "Points de vigilance et vérifications"),
    ("formations", "Formations ou certifications envisagées"),
    ("diploma_status", "Diplôme ou titre obligatoire, le cas échéant"),
    ("diploma_source", "Source officielle et date pour toute obligation mentionnée"),
)

SYNTHESIS_FIELDS = (
    ("objectif", "Objectif du bilan"),
    ("projet", "Projet professionnel retenu"),
    ("conditions", "Conditions et moyens de réalisation"),
    ("plan", "Plan d'action convenu"),
    ("suite", "Perspectives et points à reprendre"),
)


def _clean_payload(fields, payload: dict) -> dict[str, str]:
    cleaned = {}
    for key, label in fields:
        value = str(payload.get(key, "") or "").strip()
        if len(value) > 8000:
            raise ValueError(f"La rubrique « {label} » dépasse 8 000 caractères.")
        cleaned[key] = value
    if any((cleaned.get(k) or "").strip().lower() not in {"", "non concerné", "non applicable", "aucun"}
           for k in ("diploma_status",)) and len(cleaned.get("diploma_source", "")) < 8:
        raise ValueError("Toute obligation de diplôme ou de titre doit citer une source officielle et sa date.")
    return cleaned


def _save_artifact(session, *, case_id: str, artifact_type: str, content: dict,
                   state: str, actor_id: str) -> str:
    artifact = session.scalar(select(Artifact).where(
        Artifact.case_id == case_id, Artifact.artifact_type == artifact_type,
    ).limit(1))
    if artifact is None:
        artifact = Artifact(case_id=case_id, artifact_type=artifact_type,
            artifact_class="LIVRABLE_BILAN", owner_system="C&P",
            visibility_default="BENEFICIAIRE_APRES_PARTAGE")
        session.add(artifact)
        session.flush()
    latest_no = int(session.scalar(select(func.max(ArtifactVersion.version_no)).where(
        ArtifactVersion.artifact_id == artifact.artifact_id)) or 0)
    version = ArtifactVersion(artifact_id=artifact.artifact_id, version_no=latest_no + 1,
        state=state, content_json=json.dumps(content, ensure_ascii=False, sort_keys=True),
        created_by=actor_id)
    session.add(version)
    session.flush()
    artifact.current_version_id = version.artifact_version_id
    return version.artifact_version_id


def save_results(ctx, case_id: str, payload: dict, *, publish: bool = False,
                 database_url: str | None = None) -> int:
    content = _clean_payload(RESULT_FIELDS, payload)
    if not content["parcours"] or not content["savoirs"] or not content["projet"]:
        raise ValueError("Renseignez au minimum le parcours, les savoirs mobilisables et le projet étudié.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR,
                 scope="CP_PUBLISH" if publish else "CP_CASE_WRITE")
        version_no = int(session.scalar(select(func.max(ResultSet.version_no)).where(
            ResultSet.case_id == case_id)) or 0) + 1
        artifact_version_id = _save_artifact(session, case_id=case_id,
            artifact_type="RESULTATS_DETAILLES_FINAL", content=content,
            state="PUBLIE_POUR_RELECTURE" if publish else "BROUILLON", actor_id=ctx.actor_id)
        session.add(ResultSet(case_id=case_id, version_no=version_no,
            state="PUBLIE_POUR_RELECTURE" if publish else "BROUILLON",
            artifact_version_id=artifact_version_id))
        session.add(AuditEvent(case_id=case_id, event_type="RESULTS_PUBLISHED" if publish else "RESULTS_SAVED",
            object_type="RESULTS", object_id=artifact_version_id, object_version=version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"field_count": len(content)})))
        session.commit()
        return version_no


def save_synthesis(ctx, case_id: str, payload: dict, *, publish: bool = False,
                   database_url: str | None = None) -> int:
    content = _clean_payload(SYNTHESIS_FIELDS, payload)
    if any(not content[key] for key in ("objectif", "projet", "conditions", "plan")):
        raise ValueError("La synthèse doit préciser l'objectif, le projet, les conditions et le plan d'action.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR,
                 scope="CP_PUBLISH" if publish else "CP_CASE_WRITE")
        if publish:
            result = session.scalar(select(ResultSet).where(
                ResultSet.case_id == case_id, ResultSet.state == "CONFIRMEE",
            ).order_by(ResultSet.version_no.desc()).limit(1))
            if result is None:
                raise ValueError("La version des résultats détaillés doit d'abord être relue et confirmée par le bénéficiaire.")
        version_no = int(session.scalar(select(func.max(SynthesisRecord.version_no)).where(
            SynthesisRecord.case_id == case_id)) or 0) + 1
        artifact_version_id = _save_artifact(session, case_id=case_id,
            artifact_type="SYNTHESE_FINALE", content=content,
            state="PUBLIE_POUR_RELECTURE" if publish else "BROUILLON", actor_id=ctx.actor_id)
        session.add(SynthesisRecord(case_id=case_id, version_no=version_no,
            state="PUBLIE_POUR_RELECTURE" if publish else "BROUILLON",
            artifact_version_id=artifact_version_id))
        session.add(AuditEvent(case_id=case_id, event_type="SYNTHESIS_PUBLISHED" if publish else "SYNTHESIS_SAVED",
            object_type="SYNTHESIS", object_id=artifact_version_id, object_version=version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"field_count": len(content)})))
        session.commit()
        return version_no


def read_conclusion(ctx, case_id: str, *, database_url: str | None = None) -> dict:
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ctx.actor_role, scope="CP_CASE_READ")
        result_q = select(ResultSet).where(ResultSet.case_id == case_id)
        synth_q = select(SynthesisRecord).where(SynthesisRecord.case_id == case_id)
        if ctx.actor_role is ActorRole.BENEFICIAIRE:
            result_q = result_q.where(ResultSet.state.in_(["PUBLIE_POUR_RELECTURE", "CONFIRMEE", "FINALISEE"]))
            synth_q = synth_q.where(SynthesisRecord.state.in_(["PUBLIE_POUR_RELECTURE", "CONFIRMEE", "FINALISEE"]))
        result = session.scalar(result_q.order_by(ResultSet.version_no.desc()).limit(1))
        synthesis = session.scalar(synth_q.order_by(SynthesisRecord.version_no.desc()).limit(1))
        def content(version_id):
            if not version_id:
                return {}
            version = session.get(ArtifactVersion, version_id)
            try:
                return json.loads(version.content_json or "{}") if version else {}
            except (ValueError, TypeError):
                return {}
        followup = session.scalar(select(FollowUpPlan).where(FollowUpPlan.case_id == case_id))
        if followup is not None and ctx.actor_role is ActorRole.BENEFICIAIRE and followup.state not in {"PLANIFIE", "REALISE"}:
            followup = None
        closure = session.scalar(select(ClosureRecord).where(ClosureRecord.case_id == case_id))
        followup_response = session.scalar(select(FollowUpResponse).where(
            FollowUpResponse.case_id == case_id,
        ).order_by(FollowUpResponse.submitted_at.desc()).limit(1))
        response_content = None
        if followup_response and ctx.actor_role is ActorRole.ACCOMPAGNATEUR:
            try:
                response_content = json.loads(followup_response.response_json)
            except (ValueError, TypeError):
                response_content = None
        return {
            "results": {"id": result.artifact_version_id, "version": result.version_no, "state": result.state,
                        "content": content(result.artifact_version_id)} if result else None,
            "synthesis": {"id": synthesis.artifact_version_id, "version": synthesis.version_no,
                          "state": synthesis.state, "content": content(synthesis.artifact_version_id)} if synthesis else None,
            "followup": {"date": followup.planned_for, "status": followup.state} if followup else None,
            "followup_response": response_content,
            "closed": closure is not None,
        }


def respond_to_conclusion(ctx, case_id: str, *, artifact_version_id: str,
                          object_type: str, response: str, comment: str = "",
                          database_url: str | None = None) -> None:
    object_type = str(object_type).upper()
    response = str(response).upper()
    if object_type not in {"RESULTS", "SYNTHESIS"} or response not in {"CONFIRME", "CORRECTION_DEMANDEE"}:
        raise ValueError("Choisissez l'élément à relire et la réponse proposée.")
    comment = str(comment or "").strip()
    if response == "CORRECTION_DEMANDEE" and len(comment) < 4:
        raise ValueError("Précisez la nuance ou la correction demandée.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.BENEFICIAIRE, scope="CP_BENEFICIARY_VALIDATE")
        version = session.get(ArtifactVersion, artifact_version_id)
        if version is None or version.state != "PUBLIE_POUR_RELECTURE":
            raise OrientationAccessDenied("Cette version n'est pas proposée à votre relecture.")
        artifact = session.get(Artifact, version.artifact_id)
        expected_type = "RESULTATS_DETAILLES_FINAL" if object_type == "RESULTS" else "SYNTHESE_FINALE"
        if artifact is None or artifact.case_id != case_id or artifact.artifact_type != expected_type:
            raise OrientationAccessDenied("Ce document n'appartient pas au dossier courant.")
        prior = session.scalar(select(Validation).where(
            Validation.case_id == case_id, Validation.object_type == object_type,
            Validation.object_id == artifact_version_id,
        ).limit(1))
        if prior:
            raise ValueError("Une réponse a déjà été donnée pour cette version.")
        mode = "CONFIRMEE" if response == "CONFIRME" else "CORRECTION_DEMANDEE"
        session.add(Validation(event_key=f"{object_type}:{artifact_version_id}:{response}", case_id=case_id,
            phase_no=9 if object_type == "RESULTS" else 10, object_type=object_type,
            object_id=artifact_version_id, object_version=version.version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id, mode=mode))
        if response == "CONFIRME" and object_type == "RESULTS":
            row = session.scalar(select(ResultSet).where(ResultSet.artifact_version_id == artifact_version_id))
            if row:
                row.state = "CONFIRMEE"
        elif response == "CONFIRME" and object_type == "SYNTHESIS":
            row = session.scalar(select(SynthesisRecord).where(SynthesisRecord.artifact_version_id == artifact_version_id))
            if row:
                row.state = "CONFIRMEE"
        else:
            session.add(ReviewFlag(case_id=case_id, object_type=object_type,
                object_id=artifact_version_id, reason=comment, impact_level="NORMAL", status="OPEN"))
        session.add(AuditEvent(case_id=case_id, event_type=f"{object_type}_BENEFICIARY_RESPONSE",
            object_type=object_type, object_id=artifact_version_id, object_version=version.version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"response": response})))
        session.commit()


def finalize_synthesis(ctx, case_id: str, *, artifact_version_id: str,
                       database_url: str | None = None) -> None:
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_PUBLISH")
        version = session.get(ArtifactVersion, artifact_version_id)
        artifact = session.get(Artifact, version.artifact_id) if version else None
        if artifact is None or artifact.case_id != case_id or artifact.artifact_type != "SYNTHESE_FINALE":
            raise OrientationAccessDenied("Cette synthèse n'appartient pas au dossier courant.")
        if version.state != "PUBLIE_POUR_RELECTURE":
            raise ValueError("Partagez d'abord cette version pour relecture.")
        confirmation = session.scalar(select(Validation).where(
            Validation.case_id == case_id, Validation.object_type == "SYNTHESIS",
            Validation.object_id == artifact_version_id, Validation.mode == "CONFIRMEE",
        ))
        if confirmation is None:
            raise ValueError("La synthèse doit être relue et confirmée par le bénéficiaire avant sa finalisation.")
        version.state = "FINALISE"
        version.finalized_at = datetime.now(timezone.utc)
        row = session.scalar(select(SynthesisRecord).where(SynthesisRecord.artifact_version_id == artifact_version_id))
        if row:
            row.state = "FINALISEE"
            row.finalized_at = version.finalized_at
        session.add(AuditEvent(case_id=case_id, event_type="SYNTHESIS_FINALIZED",
            object_type="SYNTHESIS", object_id=artifact_version_id, object_version=version.version_no,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id, metadata_json_minimized="{}"))
        session.commit()


def save_followup_plan(ctx, case_id: str, *, planned_for: str,
                       database_url: str | None = None) -> None:
    try:
        target_date = date.fromisoformat(str(planned_for))
    except ValueError:
        raise ValueError("Indiquez une date de suivi au format AAAA-MM-JJ.") from None
    # A six-month follow-up may be scheduled a little early/late around the target.
    today = date.today()
    months = (target_date.year - today.year) * 12 + target_date.month - today.month
    if not 5 <= months <= 7:
        raise ValueError("Le suivi est prévu autour de six mois après la clôture du bilan.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        plan = session.scalar(select(FollowUpPlan).where(FollowUpPlan.case_id == case_id))
        if plan is None:
            session.add(FollowUpPlan(case_id=case_id, planned_for=target_date.isoformat(),
                state="PREPARE", created_by=ctx.actor_id))
        else:
            if session.scalar(select(ClosureRecord).where(ClosureRecord.case_id == case_id)):
                raise ValueError("Le suivi ne peut plus être modifié après la clôture du bilan.")
            plan.planned_for = target_date.isoformat()
            plan.state = "PREPARE"
        session.add(AuditEvent(case_id=case_id, event_type="FOLLOWUP_PLAN_PREPARED",
            object_type="FOLLOWUP", object_id=case_id, object_version=1,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"planned_for": target_date.isoformat()})))
        session.commit()


def close_bilan(ctx, case_id: str, *, retention_action: str, database_url: str | None = None) -> None:
    retention_action = str(retention_action or "").upper()
    if retention_action not in {"CONSERVATION_SELON_REGLES", "DESTRUCTION_DEMANDEE"}:
        raise ValueError("Choisissez le traitement documentaire retenu selon les règles de conservation.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.ACCOMPAGNATEUR, scope="CP_CASE_WRITE")
        plan = session.scalar(select(ActionPlan).where(
            ActionPlan.case_id == case_id, ActionPlan.state == "PUBLIEE",
        ).order_by(ActionPlan.version_no.desc()).limit(1))
        results = session.scalar(select(ResultSet).where(
            ResultSet.case_id == case_id, ResultSet.state == "CONFIRMEE",
        ).order_by(ResultSet.version_no.desc()).limit(1))
        synthesis = session.scalar(select(SynthesisRecord).where(
            SynthesisRecord.case_id == case_id, SynthesisRecord.state == "FINALISEE",
        ).order_by(SynthesisRecord.version_no.desc()).limit(1))
        followup = session.scalar(select(FollowUpPlan).where(FollowUpPlan.case_id == case_id))
        if not all((plan, results, synthesis, followup)):
            raise ValueError("Avant la clôture, partagez le plan, faites confirmer les résultats, finalisez la synthèse et préparez le suivi à six mois.")
        if session.scalar(select(ClosureRecord).where(ClosureRecord.case_id == case_id)):
            raise ValueError("Ce bilan est déjà clôturé.")
        session.add(ClosureRecord(case_id=case_id, action_plan_version=plan.version_no,
            result_set_version=results.version_no, synthesis_version=synthesis.version_no,
            closed_by=ctx.actor_id))
        case = session.get(Case, case_id)
        case.status = "CLOTURE"
        case.closed_at = datetime.now(timezone.utc)
        followup.state = "PLANIFIE"
        session.add(AuditEvent(case_id=case_id, event_type="CASE_CLOSED",
            object_type="CASE", object_id=case_id, object_version=1,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"retention_action": retention_action, "followup": "PLANIFIE"})))
        session.commit()


def submit_followup_response(ctx, case_id: str, *, content: str,
                             database_url: str | None = None) -> None:
    content = str(content or "").strip()
    if len(content) < 10 or len(content) > 8000:
        raise ValueError("Décrivez en quelques lignes la situation actuelle, les avancées et les besoins de suite.")
    engine = build_engine(database_url)
    with session_factory(engine)() as session:
        _context(session, ctx, case_id, role=ActorRole.BENEFICIAIRE, scope="CP_BENEFICIARY_VALIDATE")
        plan = session.scalar(select(FollowUpPlan).where(
            FollowUpPlan.case_id == case_id, FollowUpPlan.state == "PLANIFIE",
        ))
        if plan is None:
            raise OrientationAccessDenied("Aucun suivi à six mois n'est ouvert pour ce dossier.")
        if date.fromisoformat(plan.planned_for) > date.today():
            raise ValueError(f"Le point de suivi est prévu le {plan.planned_for}. Vous pourrez transmettre votre retour à partir de cette date.")
        session.add(FollowUpResponse(case_id=case_id, followup_plan_id=plan.followup_plan_id,
            response_json=json.dumps({"comment": content}, ensure_ascii=False), submitted_by=ctx.actor_id))
        plan.state = "REALISE"
        session.add(AuditEvent(case_id=case_id, event_type="FOLLOWUP_RESPONSE_RECEIVED",
            object_type="FOLLOWUP", object_id=plan.followup_plan_id, object_version=1,
            actor_type=ctx.actor_role.value, actor_id=ctx.actor_id,
            metadata_json_minimized=json.dumps({"length": len(content)})))
        session.commit()
