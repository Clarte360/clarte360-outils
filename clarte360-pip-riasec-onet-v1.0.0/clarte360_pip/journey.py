from __future__ import annotations

def results_allowed(journey:str, pip_complete:bool, onet_complete:bool=False)->bool:
    if not pip_complete: return False
    if journey=="PIP_SEUL": return True
    if journey=="PIP_PUIS_ONET60": return bool(onet_complete)
    return False

def next_after_pip(journey:str)->str:
    return "onet_pending" if journey=="PIP_PUIS_ONET60" else "pip_results_gate"
