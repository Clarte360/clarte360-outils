"""Functional phase order for the Clarté360 bilan workflow.

Stored phase identifiers remain stable while the user-facing sequence follows
the A3 methodology.
"""

PHASE_FLOW_ORDER = tuple(range(8)) + (9, 8, 10, 11)
PHASE_POSITION = {phase_no: position for position, phase_no in enumerate(PHASE_FLOW_ORDER)}
PHASE_PREVIOUS = {
    phase_no: PHASE_FLOW_ORDER[position - 1]
    for position, phase_no in enumerate(PHASE_FLOW_ORDER) if position > 0
}
PHASE_NEXT = {
    phase_no: PHASE_FLOW_ORDER[position + 1]
    for position, phase_no in enumerate(PHASE_FLOW_ORDER) if position < len(PHASE_FLOW_ORDER) - 1
}


def phase_display_number(phase_no: int) -> int:
    """Return the step number shown to users while preserving the stored ID."""
    return PHASE_POSITION[int(phase_no)] + 1
