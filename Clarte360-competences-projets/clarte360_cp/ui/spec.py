from __future__ import annotations

from dataclasses import dataclass

from clarte360_cp.domain.sources import FORBIDDEN_SOURCE_TYPES
from clarte360_cp.domain.phases import phase_display_number


@dataclass(frozen=True)
class PhaseUiSpec:
    phase_no: int
    label: str
    short_label: str
    group: str
    screen_codes: tuple[str, ...]
    finality: str
    validation_label: str
    next_action_label: str


PHASE_SPECS: tuple[PhaseUiSpec, ...] = (
    PhaseUiSpec(0, "Enrichir le CV", "CV", "Investigation", ("A-P0-01", "A-P0-02"),
                "Rendre le parcours suffisamment précis pour une analyse ROME fiable, sans reconstituer tout le CV.",
                "Bénéficiaire + Accompagnateur", "Travailler les clarifications utiles"),
    PhaseUiSpec(1, "Formaliser les pistes", "Pistes", "Investigation", ("A-P1-01", "A-P1-02"),
                "Partir de ce que le bénéficiaire envisage avant toute hypothèse exploratoire.",
                "Bénéficiaire + Accompagnateur", "Formaliser les pistes envisagées"),
    PhaseUiSpec(2, "Choisir les métiers ROME à étudier", "Métiers ROME", "Investigation", ("A-P2-01", "A-P2-02"),
                "Traduire les pistes en un à trois métiers ROME maximum à analyser en profondeur.",
                "Bénéficiaire + Accompagnateur", "Rechercher et retenir 1 à 3 métiers"),
    PhaseUiSpec(3, "Rapprocher parcours et attendus ROME", "Rapprochement", "Investigation", ("A-P3-01", "A-P3-02"),
                "Présenter d'abord une synthèse des statuts proposés avant le détail des attendus ROME.",
                "Accompagnateur", "Préparer les points à confirmer"),
    PhaseUiSpec(4, "Confirmer les points incertains", "Confirmer", "Investigation", ("A-P4-01",),
                "Traiter une question utile à la fois, en séance, sans renvoyer le bénéficiaire vers une longue liste.",
                "Accompagnateur après prise en compte des réponses du bénéficiaire", "Ouvrir l'entretien ciblé"),
    PhaseUiSpec(5, "Confronter le métier à la réalité", "Réalité", "Investigation", ("A-P5-01", "A-P5-02"),
                "Séparer faits, sources, éclairages et points restant à vérifier avant toute décision.",
                "Accompagnateur", "Décider des vérifications utiles"),
    PhaseUiSpec(6, "Comparer les projets", "Comparer", "Investigation", ("A-P6-01",),
                "Comparer qualitativement les pistes sans score, podium, note globale ni classement automatique.",
                "Accompagnateur", "Mettre en évidence les différences utiles"),
    PhaseUiSpec(7, "Retenir et sécuriser le projet", "Choisir", "Investigation", ("A-P7-01",),
                "Formaliser le choix comme une décision du bénéficiaire, avec une alternative seulement si elle est utile.",
                "Décision Bénéficiaire + formalisation Accompagnateur", "Formaliser le projet retenu"),
    PhaseUiSpec(8, "Construire le plan d'action", "Plan d'action", "Conclusion", ("A-P9-01",),
                "Transformer les écarts et conditions du projet en quelques actions concrètes et réalistes.",
                "Bénéficiaire + Accompagnateur", "Construire le plan d'action"),
    PhaseUiSpec(9, "Préparer les résultats détaillés", "Résultats", "Conclusion", ("A-P8-01",),
                "Préparer une restitution appropriable sans recopier ni fusionner tous les rapports amont.",
                "Bénéficiaire + Accompagnateur", "Préparer la restitution"),
    PhaseUiSpec(10, "Préparer la synthèse", "Synthèse", "Conclusion", ("A-P10-01",),
                "Préparer une synthèse fidèle, concise et traçable, distincte des résultats détaillés.",
                "Bénéficiaire + Accompagnateur puis verrouillage Accompagnateur", "Prévisualiser la synthèse"),
    PhaseUiSpec(11, "Clôturer le dossier", "Clôture", "Conclusion", ("A-P11-01",),
                "Vérifier livrables, remise, conservation/destruction et suivi avant toute clôture.",
                "Accompagnateur", "Vérifier la checklist de clôture"),
)

PHASE_BY_NO = {spec.phase_no: spec for spec in PHASE_SPECS}
PHASE_SPECS = tuple(sorted(PHASE_SPECS, key=lambda spec: phase_display_number(spec.phase_no)))

SOURCE_CARDS: tuple[tuple[str, str], ...] = (
    ("APS_OBJECTIF", "APS + objectif du bilan"),
    ("BOUSSOLE_VALEURS", "Boussole des valeurs"),
    ("MOTEURS_PRO", "Moteurs professionnels"),
    ("PREFERENCES_PRO", "Préférences professionnelles"),
    ("IPIP_REPORT", "Profil de fonctionnement professionnel"),
    ("PIP_REPORT", "PIP RIASEC — accompagnement"),
    ("CV_SOURCE", "CV source"),
)


ENTRY_PAGES = ("entry_context", "entry_preparation", "entry_joint_review", "entry_ideas", "entry_reperes", "entry_directions", "entry_sources")
PHASE_PAGES = tuple(f"phase_{spec.phase_no}" for spec in PHASE_SPECS)
ACCOMPAGNATEUR_PAGES = frozenset({"dashboard", "documents", *ENTRY_PAGES, *PHASE_PAGES})


def phase_page(phase_no: int) -> str:
    if phase_no not in PHASE_BY_NO:
        raise ValueError(f"Phase inconnue: {phase_no}")
    return f"phase_{phase_no}"


@dataclass(frozen=True)
class NextAction:
    title: str
    detail: str
    page: str


def choose_next_action(snapshot, *, linked_source_codes=None) -> NextAction:
    if snapshot.submitted_tasks:
        return NextAction("Débriefer le retour interséance",
                          f"{snapshot.submitted_tasks} retour(s) attendent un débrief avec le bénéficiaire.", "phase_5")
    if snapshot.open_flags:
        phase = snapshot.current_phase if snapshot.current_phase is not None else 0
        return NextAction("Traiter les points à revoir", f"{snapshot.open_flags} point(s) ouvert(s) nécessitent une revue accompagnateur.", phase_page(phase))
    if not snapshot.orientation_published:
        return NextAction("Commencer par « Mes idées à moi »",
                          "Accueillir les idées du bénéficiaire, y compris sans CV, puis relire les cinq repères et choisir les premières directions.",
                          "entry_ideas")
    if linked_source_codes is None:
        cv = next((d for d in snapshot.document_summaries if d.artifact_type == "CV_SOURCE"), None)
        cv_linked = bool(cv and cv.present)
    else:
        cv_linked = "CV_SOURCE" in set(linked_source_codes)
    if not cv_linked:
        return NextAction(
            "Compléter les sept documents obligatoires",
            "Sélectionnez et vérifiez les sept pièces dans Documents avant de préparer le questionnaire.",
            "documents",
        )
    phase = snapshot.current_phase if snapshot.current_phase is not None else 0
    spec = PHASE_BY_NO.get(phase, PHASE_BY_NO[0])
    return NextAction(spec.next_action_label, spec.finality, phase_page(spec.phase_no))

# GO-21 — pages Bénéficiaire. Les numéros de phases sont des identifiants internes,
# jamais une navigation principale affichée au bénéficiaire.
BENEFICIARY_PHASE_PAGES = tuple(f"b_phase_{i}" for i in range(12))
BENEFICIARY_PAGES = frozenset({"b_preparation",
    "b_home", "b_journey", "b_orientation", "b_actions", "b_documents", "b_read", "b_do", "b_validate", "b_done", "b_intersession",
    *BENEFICIARY_PHASE_PAGES,
})

BENEFICIARY_STAGE_BY_PHASE = {
    0: "Explorer", 1: "Explorer", 2: "Explorer",
    3: "Vérifier", 4: "Vérifier", 5: "Vérifier", 6: "Vérifier",
    7: "Choisir",
    8: "Finaliser", 9: "Finaliser", 10: "Finaliser", 11: "Finaliser",
}

BENEFICIARY_SCREEN_CODE_BY_PHASE = {
    0: "B-P0-01", 1: "B-P1-01", 2: "B-P2-01", 3: "B-P3-01",
    4: "B-P4-01", 5: "B-P5-01", 6: "B-P6-01", 7: "B-P7-01",
    8: "B-P8-01", 9: "B-P9-01", 10: "B-P10-01", 11: "B-P11-01",
}


def beneficiary_phase_page(phase_no: int) -> str:
    if phase_no not in PHASE_BY_NO:
        raise ValueError(f"Phase inconnue: {phase_no}")
    return f"b_phase_{phase_no}"
