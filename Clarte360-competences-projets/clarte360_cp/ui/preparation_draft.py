"""Brouillon bénéficiaire RC3C : sauvegarde et concurrence sans dépendance UI.

La version attendue appartient aux réponses qui ont initialisé les widgets,
jamais à une lecture serveur plus récente. L'appelant exécute ces fonctions
après le contrôle d'accès de l'application, pas dans un callback de widget.
Les boutons de fin d'étape restent les seuls à poser un indicateur ``done``.
Le runner applicatif sérialise les reruns (``fastReruns=false``) : une nouvelle
tentative ne commence pas pendant la transaction de la précédente exécution.
"""
from __future__ import annotations

import copy
from collections.abc import MutableMapping
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from clarte360_cp.application.orientation import OrientationConflict
from clarte360_cp.application.preparation import PreparationView, save_beneficiary_answers
from clarte360_cp.domain.preparation_v2 import empty_answers_v2, valid_answers_v2


@dataclass(frozen=True)
class PendingSave:
    """Preuve locale écrite avant SQL, conservée si le rerun coupe l'accusé."""
    questionnaire_version: int
    base_row_version: int
    answers: dict


@dataclass(frozen=True)
class DraftBuffer:
    case_id: str
    questionnaire_version: int
    answers: dict
    row_version: int
    view: PreparationView
    conflict: bool = False
    conflict_message: str = ""
    pending: PendingSave | None = None


def _key(case_id: str, questionnaire_version: int) -> str:
    return f"rc3_draft_{case_id}_{questionnaire_version}"


def _normalise(answers: dict, questionnaire: dict) -> dict:
    # La projection bénéficiaire masque les références techniques des sources.
    # L'evidence est en lecture seule et ne fait pas partie des réponses : sa
    # validation documentaire complète reste effectuée côté application/serveur.
    q = copy.deepcopy(questionnaire)
    q.pop("evidence", None)
    return valid_answers_v2(copy.deepcopy(answers), q, final=False)


def _from_view(case_id: str, view: PreparationView) -> DraftBuffer:
    if view.questionnaire is None or view.questionnaire_version is None:
        raise ValueError("Le questionnaire n'est pas encore disponible.")
    if view.active_answers is not None:
        raise ValueError("Vos réponses ont déjà été transmises.")
    answers = view.responses if view.responses is not None else empty_answers_v2(view.questionnaire)
    return DraftBuffer(
        case_id=case_id,
        questionnaire_version=view.questionnaire_version,
        answers=_normalise(answers, view.questionnaire),
        row_version=view.row_version,
        view=copy.deepcopy(view),
    )


def get_draft(state: MutableMapping[str, Any], case_id: str, view: PreparationView) -> DraftBuffer:
    """Hydrate ou acquitte une sauvegarde précisément identifiée comme en attente.

    Une lecture seule ne réinitialise jamais la version attachée aux widgets.
    Exception strictement bornée : SQL a pu réussir puis Streamlit interrompre
    l'assignation de l'accusé local. Seul le prochain état exact de la tentative
    préalablement enregistrée permet alors de confirmer cette sauvegarde.
    """
    if view.questionnaire_version is None:
        raise ValueError("Le questionnaire n'est pas encore disponible.")
    key = _key(case_id, view.questionnaire_version)
    if key not in state:
        state[key] = _from_view(case_id, view)
    buffer = state[key]
    if not isinstance(buffer, DraftBuffer) or buffer.case_id != case_id:
        raise ValueError("Le brouillon doit être rechargé avant de poursuivre.")
    pending = buffer.pending
    if (
        not buffer.conflict and pending is not None
        and pending.questionnaire_version == buffer.questionnaire_version == view.questionnaire_version
        and pending.base_row_version == buffer.row_version
        and view.row_version == pending.base_row_version + 1
        and view.questionnaire_locked and view.invitation_open
        and view.stage == "REPONSES_EN_COURS"
        and view.response_status == "BROUILLON"
        and view.active_answers is None
        and view.responses == pending.answers
    ):
        confirmed = _from_view(case_id, view)
        # Cette assignation peut elle-même être interrompue. Dans ce cas, la
        # preuve pending précédente demeure et autorise le même accusé au rerun
        # suivant, sans nouvelle écriture SQL ni suppression des widgets.
        state[key] = confirmed
        return confirmed
    return buffer


def prepare_draft(
    draft: DraftBuffer,
    questionnaire: dict,
    visible_answers: dict,
    *,
    part: int,
    complete: bool | None = None,
) -> dict:
    """Canonise la partie visible et invalide uniquement les étapes concernées.

    ``complete=None`` correspond à l'autosauvegarde ; True/False à un bouton
    explicite de fin d'étape/brouillon. Les réponses de l'autre partie sont
    reprises de la base locale, jamais d'un rendu devenu ancien.
    """
    if part not in (1, 2) or (complete is not None and not isinstance(complete, bool)):
        raise ValueError("Étape de questionnaire invalide.")
    if part == 2 and not draft.answers["cav1_done"]:
        raise ValueError("Terminez et enregistrez C-AV1 avant de poursuivre C-AV2.")
    name = f"cav{part}"
    candidate = copy.deepcopy(draft.answers)
    candidate[name] = copy.deepcopy(visible_answers[name])
    # Une saisie encore incomplète doit pouvoir être sauvegardée même si la
    # version précédente était marquée terminée (ex. suppression d'un choix).
    candidate["cav1_done"] = False
    candidate["cav2_done"] = False
    candidate = _normalise(candidate, questionnaire)
    original = copy.deepcopy(draft.answers)
    original["cav1_done"] = False
    original["cav2_done"] = False
    original = _normalise(original, questionnaire)
    changed = candidate[name] != original[name]
    candidate["cav1_done"] = draft.answers["cav1_done"]
    candidate["cav2_done"] = draft.answers["cav2_done"]
    if changed:
        if part == 1:
            candidate["cav1_done"] = False
        candidate["cav2_done"] = False
    if complete is not None:
        candidate[f"cav{part}_done"] = complete
        if part == 1:
            candidate["cav2_done"] = False
    return _normalise(candidate, questionnaire)


def save_draft(
    state: MutableMapping[str, Any],
    ctx,
    case_id: str,
    view: PreparationView,
    candidate: dict,
    *,
    database_url: str | None = None,
) -> PreparationView:
    """Sauvegarde une différence valide, sans répétition ni fusion de conflit.

    La vue retournée est celle de la base confirmée : soit le résultat de la
    transaction, soit la vue déjà sauvegardée si rien n'a changé. Après conflit,
    les widgets et la base locale restent disponibles, mais une réhydratation
    explicite est nécessaire avant toute nouvelle tentative d'écriture.
    """
    draft = get_draft(state, case_id, view)
    if draft.conflict:
        raise OrientationConflict(draft.conflict_message)
    if view.questionnaire is None:
        raise ValueError("Le questionnaire n'est pas encore disponible.")
    cleaned = _normalise(candidate, view.questionnaire)
    key = _key(case_id, draft.questionnaire_version)
    try:
        if view.active_answers is not None or view.row_version != draft.row_version:
            raise OrientationConflict(
                "Vos réponses ont changé dans un autre onglet. Vos saisies restent visibles ici. "
                "Rechargez les réponses enregistrées avant de poursuivre."
            )
        if cleaned == draft.answers:
            return copy.deepcopy(draft.view)
        # SafeSessionState peut interrompre une lecture/écriture de session.
        # Cette preuve doit être écrite AVANT SQL : si son assignation est
        # interrompue, la transaction n'a pas commencé ; si celle qui suit le
        # commit est interrompue, get_draft pourra acquitter l'état exact.
        state[key] = replace(draft, pending=PendingSave(
            questionnaire_version=draft.questionnaire_version,
            base_row_version=draft.row_version,
            answers=copy.deepcopy(cleaned),
        ))
        saved = save_beneficiary_answers(
            ctx, case_id, cleaned,
            expected_row_version=draft.row_version,
            database_url=database_url,
        )
    except OrientationConflict as exc:
        state[key] = replace(draft, conflict=True, conflict_message=str(exc), pending=None)
        raise
    except (IntegrityError, StaleDataError) as exc:
        # Une collision très rapprochée peut survenir au flush de la nouvelle
        # réponse, avant la conversion de ces erreurs par _commit côté service.
        # L'échec ne doit exposer aucun SQL ni relancer la saisie automatiquement.
        message = (
            "Une autre session a enregistré des réponses au même moment. "
            "Vos saisies restent visibles ici. Rechargez les réponses enregistrées avant de poursuivre."
        )
        state[key] = replace(draft, conflict=True, conflict_message=message, pending=None)
        raise OrientationConflict(message) from exc
    state[key] = _from_view(case_id, saved)
    return saved


def reload_draft(state: MutableMapping[str, Any], case_id: str, view: PreparationView) -> DraftBuffer:
    """Repart explicitement de la vue serveur sans effacer un autre dossier."""
    replacement = _from_view(case_id, view)
    prefixes = (f"B_{case_id}_", f"rc3_step_{case_id}_", f"rc3_draft_{case_id}_")
    exact = {f"rc3_benef_confirm_{case_id}", f"rc3_draft_conflict_{case_id}"}
    for key in list(state):
        if isinstance(key, str) and (key in exact or key.startswith(prefixes)):
            del state[key]
    state[_key(case_id, replacement.questionnaire_version)] = replacement
    return replacement
