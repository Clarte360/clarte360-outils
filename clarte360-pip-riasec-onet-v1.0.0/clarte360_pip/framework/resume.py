"""Fail-closed accompanied bootstrap; never create a replacement on a read failure."""
from __future__ import annotations
import logging
from clarte360_pip.domain import RunMode
from clarte360_pip.framework.persistence import restore_snapshot
from clarte360_pip.framework.server_store import load_latest_accompanied_snapshot, SnapshotConflict

LOG = logging.getLogger(__name__)


def context_key(launch):
    return (launch.mode.value, launch.action_id, launch.beneficiary_id,
            launch.participant_id, launch.prescription_id)


def restore_accompanied(launch, state) -> bool:
    if launch.mode is not RunMode.ACCOMPANIMENT:
        return True
    key = context_key(launch)
    if state.get('server_resume_checked') and state.get('server_resume_context') == key:
        return not bool(state.get('server_resume_error'))
    try:
        saved = load_latest_accompanied_snapshot(launch.action_id, launch.beneficiary_id, launch.prescription_id)
        if saved:
            ctx = saved.get('launch_context') or {}
            if ctx.get('participant_id') is not None and ctx['participant_id'] != launch.participant_id:
                raise SnapshotConflict("Participant de la sauvegarde incoherent.")
            restored = {}
            restore_snapshot(saved, restored)  # transactional: no partial state on validation failure
            state.update(restored)
            state['server_resume_restored'] = True
        state['launch_context'] = launch
        state['server_resume_checked'] = True
        state['server_resume_context'] = key
        state.pop('server_resume_error', None)
        return True
    except Exception as exc:
        state['server_resume_checked'] = False
        state['server_resume_error'] = type(exc).__name__
        LOG.error('PIP_RESUME_FAILED category=%s', type(exc).__name__)
        return False
