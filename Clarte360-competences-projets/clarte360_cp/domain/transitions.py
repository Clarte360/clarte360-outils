from __future__ import annotations

from .enums import PhaseStateValue

ALLOWED_PHASE_TRANSITIONS = {
    PhaseStateValue.NON_DISPONIBLE: {PhaseStateValue.DISPONIBLE},
    PhaseStateValue.DISPONIBLE: {PhaseStateValue.EN_COURS},
    PhaseStateValue.EN_COURS: {PhaseStateValue.EN_ATTENTE_BENEFICIAIRE, PhaseStateValue.EN_ATTENTE_ACCOMPAGNATEUR, PhaseStateValue.VALIDEE},
    PhaseStateValue.EN_ATTENTE_BENEFICIAIRE: {PhaseStateValue.EN_COURS, PhaseStateValue.EN_ATTENTE_ACCOMPAGNATEUR, PhaseStateValue.VALIDEE},
    PhaseStateValue.EN_ATTENTE_ACCOMPAGNATEUR: {PhaseStateValue.EN_COURS, PhaseStateValue.VALIDEE},
    PhaseStateValue.VALIDEE: {PhaseStateValue.REOUVERTE, PhaseStateValue.FIGEE_CLOTURE},
    PhaseStateValue.REOUVERTE: {PhaseStateValue.EN_COURS, PhaseStateValue.EN_ATTENTE_BENEFICIAIRE, PhaseStateValue.EN_ATTENTE_ACCOMPAGNATEUR, PhaseStateValue.VALIDEE},
    PhaseStateValue.FIGEE_CLOTURE: set(),
}


def phase_transition_allowed(source: str, target: str) -> bool:
    try:
        s, t = PhaseStateValue(source), PhaseStateValue(target)
    except ValueError:
        return False
    return t in ALLOWED_PHASE_TRANSITIONS[s]
