"""P5-RC2 J5: admin workspace routing and action-list presentation.

Pure helpers only: permissions, mutating writes, and access control remain in
existing services. A workspace never grants additional access by itself.
"""
from __future__ import annotations
from math import ceil

WORKSPACE_HOME = 'home'
WORKSPACE_GENERAL = 'general'
WORKSPACE_ACTIONS = 'actions'
GENERAL_PAGES = ('Tableau de bord', 'Relances', 'Qualité', 'Études PIP/O*NET',
                 'Contacts / Prospects', 'Espace Client / DRH',
                 'Intervenants / Partenaires', 'Paramètres')
ACTION_PAGES = ('Tableau de bord', 'Nouvelle action', 'Importer une action', 'Actions')
WORKSPACES = (WORKSPACE_HOME, WORKSPACE_GENERAL, WORKSPACE_ACTIONS)
STATUS_PRIORITY = {'ACTIVE': 0, 'A_CLOTURER': 1, 'PLANIFIEE': 2,
                   'BROUILLON': 3, 'CLOTUREE': 4, 'ARCHIVEE': 5}
PAGE_SIZE = 25


def workspace_for_route(route: str | None, fallback: str = WORKSPACE_GENERAL) -> str:
    """Route all existing deep links into the appropriate admin workspace."""
    if route in ('Nouvelle action', 'Importer une action', 'Actions'):
        return WORKSPACE_ACTIONS
    if route in GENERAL_PAGES and route != 'Tableau de bord':
        return WORKSPACE_GENERAL
    return fallback if fallback in (WORKSPACE_GENERAL, WORKSPACE_ACTIONS) else WORKSPACE_GENERAL


def pages_for_workspace(workspace: str) -> tuple[str, ...]:
    if workspace == WORKSPACE_GENERAL:
        return GENERAL_PAGES
    if workspace == WORKSPACE_ACTIONS:
        return ACTION_PAGES
    return ()


def valid_route(workspace: str, route: str | None) -> str:
    pages = pages_for_workspace(workspace)
    if not pages:
        return ''
    return route if route in pages else pages[0]


def _norm_status(row: dict) -> str:
    raw = str(row.get('status') or '').strip().upper()
    return {'ACTIVE': 'ACTIVE', 'ACTIF': 'ACTIVE', 'DRAFT': 'BROUILLON',
            'ARCHIVE': 'ARCHIVEE', 'ARCHIVÉE': 'ARCHIVEE'}.get(raw, raw)


def filter_sort_actions(rows, *, term='', include_archived=False, status='Tous', year='Toutes', prestation='Toutes'):
    """Filter and prioritize open actions, never treating drafts as archives."""
    query = str(term or '').casefold().strip()
    status_filter = str(status or 'Tous')
    year_filter = str(year or 'Toutes')
    result = []
    for row in rows:
        s = _norm_status(row)
        if s == 'ARCHIVEE' and not include_archived:
            continue
        if status_filter != 'Tous' and s != status_filter:
            continue
        if year_filter != 'Toutes':
            if not str(row.get('start_date') or '').startswith(year_filter):
                continue
        if prestation != 'Toutes' and str(row.get('prestation_type') or '') != prestation:
            continue
        fields = (row.get('action_no'), row.get('title'), row.get('client_name'),
                  row.get('first_participant'), row.get('prestation_type'))
        if query and query not in ' '.join(str(x or '') for x in fields).casefold():
            continue
        result.append(row)
    return sorted(result, key=lambda r:(STATUS_PRIORITY.get(_norm_status(r), 9),
                                        -_date_number(r.get('start_date')), -int(r.get('id') or 0)))


def _date_number(value):
    digits = ''.join(c for c in str(value or '')[:10] if c.isdigit())
    return int(digits) if digits else 0


def page_slice(rows, *, page=1, size=PAGE_SIZE):
    """Return (page rows, page index, total pages) with bounded page."""
    if size not in (25, 50):
        raise ValueError('Taille de page invalide')
    n = max(1, ceil(len(rows) / size))
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    page = max(1, min(page, n))
    return list(rows[(page - 1) * size:page * size]), page, n


def action_label(row):
    """Use meaningful client and beneficiary context in selectors."""
    number = str(row.get('action_no') or '?')
    title = str(row.get('title') or '?')
    client = str(row.get('client_name') or 'Client non renseigné')
    count = int(row.get('participant_count') or 0)
    first = str(row.get('first_participant') or 'Aucun stagiaire')
    suffix = 'stagiaire' if count == 1 else 'stagiaires'
    return f'{number} — {title} | {client} | {count} {suffix} | {first}'


def action_list_rows(actions, participant_summary):
    """Project query results into a single table without repeated queries."""
    result=[]
    for a in actions:
        summary=participant_summary.get(int(a['id']), {})
        row={**a, 'participant_count': int(summary.get('participant_count') or 0),
             'first_participant':str(summary.get('first_participant') or '')}
        result.append(row)
    return result
