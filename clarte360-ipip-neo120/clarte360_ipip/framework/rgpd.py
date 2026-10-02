from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


from clarte360_ipip.version import APP_VERSION
from .config import CLARTE360_LEGAL, RGPD_TEXT_VERSION
from .server_store import atomic_json_write, safe_run_path

NON_CLINICAL_NOTICE = (
    "Cet outil explore des tendances de fonctionnement. Les résultats ne définissent pas la personne "
    "et ne constituent ni une évaluation clinique, ni un diagnostic psychologique ou psychiatrique. "
    "Ils doivent être mis en perspective avec l’expérience, les valeurs, les préférences, les motivations "
    "et le projet professionnel."
)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_information_record(*, ctx: Any, reference_version: str, understood: bool, proceed: bool) -> dict[str, Any]:
    """Trace l'information préalable sans la qualifier abusivement de consentement RGPD."""
    return {
        "schema": "clarte360.ipipneo.information.v1",
        "text_version": RGPD_TEXT_VERSION,
        "recorded_at": _now_utc_iso(),
        "app_version": APP_VERSION,
        "reference_version": reference_version,
        "prescription_id": str(ctx.prescription_id),
        "beneficiary_id": str(ctx.beneficiary_id),
        "action_id": str(ctx.action_id),
        "participant_id": str(ctx.participant_id) if getattr(ctx, "participant_id", None) else None,
        "information_read": True,
        "understanding_confirmed": bool(understood),
        "passation_requested": bool(proceed),
    }


def save_information_record(base_dir, run_id: str, record: dict[str, Any]) -> None:
    target = safe_run_path(base_dir, "information", run_id)
    atomic_json_write(target, record)


def load_information_record(base_dir, run_id: str) -> dict[str, Any] | None:
    import json

    target = safe_run_path(base_dir, "information", run_id)
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def information_is_current(record: dict[str, Any] | None, reference_version: str) -> bool:
    if not record:
        return False
    return (
        record.get("text_version") == RGPD_TEXT_VERSION
        and record.get("app_version") == APP_VERSION
        and record.get("reference_version") == reference_version
        and record.get("information_read") is True
        and record.get("understanding_confirmed") is True
        and record.get("passation_requested") is True
    )


def render_non_clinical_notice() -> None:
    import streamlit as st
    st.warning(NON_CLINICAL_NOTICE)


def render_rgpd_information(*, show_confirmation: bool = False, reference_version: str | None = None) -> tuple[bool, bool]:
    """Affiche l'information RGPD spécifique IPIP.

    Retourne (compréhension confirmée, souhait de poursuivre). Aucune case n'est présentée comme
    un « consentement RGPD » : la passation accompagnée repose sur le cadre de l'accompagnement
    et de la prescription, tandis que l'écran assure information et confirmation de compréhension.
    """
    import streamlit as st
    st.subheader("RGPD et confidentialité")
    st.caption(f"Notice d'information : {RGPD_TEXT_VERSION}")

    st.markdown("#### Qui traite vos données ?")
    st.write(
        f"Le responsable du traitement est **{CLARTE360_LEGAL['raison_sociale']}**, "
        f"{CLARTE360_LEGAL['adresse']}, {CLARTE360_LEGAL['code_postal_ville']}."
    )

    st.markdown("#### Pourquoi ces données sont-elles utilisées ?")
    st.write(
        "Les données servent uniquement à réaliser votre Profil de fonctionnement professionnel, "
        "sauvegarder et reprendre votre passation, calculer vos résultats, produire votre rapport, "
        "recueillir votre ressenti et permettre leur utilisation dans l'accompagnement prescrit."
    )

    st.markdown("#### Quelles données sont traitées ?")
    st.write(
        "L'application traite l'identité technique transmise par Gestion des Actions (identifiants de bénéficiaire, "
        "action, prescription et éventuellement participant), vos réponses aux 120 affirmations, la progression, "
        "les scores calculés, le rapport final et le questionnaire de ressenti."
    )
    st.info(
        "Gestion des Actions reste la source de vérité de votre identité et de la prescription. "
        "Les réponses brutes aux 120 affirmations ne sont pas remontées dans Gestion des Actions par défaut."
    )

    st.markdown("#### Décision automatisée et portée des résultats")
    st.write(
        "Le calcul est déterministe et local. L'outil ne prend aucune décision automatisée produisant un effet "
        "significatif à votre égard et ne formule aucune décision de recrutement, d'aptitude ou de métier."
    )
    render_non_clinical_notice()

    st.markdown("#### Conservation, hébergement et sécurité")
    st.write(
        "Les données de passation sont conservées dans l'environnement serveur Clarté360, séparément du code de "
        "l'application, pendant la durée applicable à l'accompagnement et à la politique de conservation Clarté360. "
        "La durée précise applicable à votre dossier figure dans les documents de l'accompagnement et la politique "
        "de confidentialité en vigueur. Les échanges sont protégés par HTTPS et les secrets techniques ne sont pas "
        "stockés dans le code de l'application."
    )

    st.markdown("#### Qui peut y accéder ?")
    st.write(
        "L'accès est limité aux personnes autorisées dans le cadre de votre accompagnement et aux intervenants "
        "techniques habilités lorsque cela est nécessaire au fonctionnement ou au support."
    )

    st.markdown("#### Vos droits")
    st.write(
        "Selon la situation et la base juridique applicable, vous pouvez exercer les droits prévus par la réglementation, "
        "notamment l'accès, la rectification, l'effacement lorsqu'il est applicable, la limitation et l'opposition "
        "lorsqu'elle est applicable. Pour toute demande concernant vos données : "
        f"**{CLARTE360_LEGAL['email']}**."
    )

    st.markdown("#### Base et confirmation avant passation")
    st.write(
        "Cet écran vous informe sur le traitement réalisé pour la passation. La confirmation ci-dessous n'est pas "
        "présentée comme un « consentement RGPD » : elle atteste que vous avez pris connaissance de l'information, "
        "que vous en comprenez la portée et que vous souhaitez poursuivre la passation prévue dans votre accompagnement."
    )

    if reference_version:
        st.caption(f"Application {APP_VERSION} • Référentiel {reference_version}")

    if not show_confirmation:
        return False, False

    understood = st.checkbox(
        "J'ai pris connaissance des informations ci-dessus et j'en comprends la portée.",
        key="rgpd_understood",
    )
    proceed = st.checkbox(
        "Je confirme souhaiter poursuivre cette passation dans le cadre de mon accompagnement.",
        key="rgpd_proceed",
    )
    return bool(understood), bool(proceed)
