"""Navigation métier RC2-2-2 entre Action et Qualification.

Ces fonctions ne dépendent pas de Streamlit : elles manipulent uniquement un mapping
compatible avec ``st.session_state``. Le parcours peut ainsi être testé sans navigateur.
"""

RETURN_CONTEXT_KEYS = (
    '_rc222_return_action_id',
    '_rc222_return_action_ppid',
    '_rc222_return_action_service_id',
)


def prepare_action_qualification_navigation(state, action_id, professional_person_id, service_id=None):
    """Prépare l'ouverture de la bonne qualification depuis une Action."""
    state['_j2_open_ppid'] = professional_person_id
    if service_id is not None:
        state['_j17_focus_service_id'] = int(service_id)
    else:
        state.pop('_j17_focus_service_id', None)
    state['_rc222_return_action_id'] = int(action_id)
    state['_rc222_return_action_ppid'] = professional_person_id
    state['_rc222_return_action_service_id'] = int(service_id) if service_id is not None else None
    state['_next_nav'] = 'Intervenants / Partenaires'
    return state


def mark_qualification_saved_for_action(state, professional_person_id):
    """Mémorise qu'une validation vient d'être faite dans le contexte de l'Action d'origine."""
    if state.get('_rc222_return_action_id') and state.get('_rc222_return_action_ppid') == professional_person_id:
        state['_rc222_qualification_saved_for_action'] = True
        return True
    return False


def prepare_return_to_action(state, action_id, eligible, reason=None, status=None):
    """Prépare le retour vers l'Action après recalcul réel de l'éligibilité."""
    action_id = int(action_id)
    message = 'Éligibilité recalculée : ' + str(reason or status or '')
    state['selected_action'] = action_id
    state['_rc222_action_focus_tab'] = 'Intervenants'
    state['_action_flash'] = (action_id, 'success' if eligible else 'warning', message)
    for key in RETURN_CONTEXT_KEYS:
        state.pop(key, None)
    state['_next_nav'] = 'Actions'
    return state
