"""CLARTE360 GDA P3: navigation contextuelle independante de la logique metier.

Les identifiants d'ecran sont stables. Aucun droit n'est accorde ici :
les services applicatifs restent la source des autorisations.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Screen:
    key: str
    label: str
    title: str


BENEFICIARY_SCREENS = (
    Screen('home', '\U0001f3e0 Mes actions', 'Mes actions et mon parcours'),
    Screen('profile', '\U0001f464 Mon profil', 'Mes informations personnelles'),
    Screen('journey', '\U0001f393 Mon parcours', 'Ma formation ou mon accompagnement'),
    Screen('planning', '\U0001f4c5 Mon planning', 'Mon planning et mes calendriers'),
    Screen('teams', '\U0001f4bb Mes r\u00e9unions Teams', 'Mes r\u00e9unions Teams'),
    Screen('tools', '\U0001f9ed Mes outils Clart\u00e9360', 'Mes outils et mes r\u00e9sultats'),
    Screen('documents', '\U0001f4c4 Documents administratifs', 'Mes documents administratifs'),
    Screen('courses', '\U0001f4da Cours et travaux', 'Documents de cours et d\u00e9p\u00f4ts individuels'),
    Screen('questionnaires', '\u2705 Questionnaires et actions', 'Questionnaires et actions \u00e0 r\u00e9aliser'),
    Screen('signatures', '\u270d\ufe0f Mes \u00e9margements', 'Mes \u00e9margements et certificats'),
    Screen('reports', '\U0001f4e3 Signaler / informer', 'Mes observations et signalements'),
    Screen('archives', '\U0001f5c2\ufe0f Archives / t\u00e9l\u00e9chargements', 'Mes archives et t\u00e9l\u00e9chargements'),
)

TRAINER_SCREENS = (
    Screen('overview', '\U0001f3e0 Vue d\u2019ensemble', 'Synth\u00e8se de mon intervention'),
    Screen('planning', '\U0001f4c5 Planning', 'Planning et gestion des s\u00e9ances'),
    Screen('teams', '\U0001f4bb Teams', 'R\u00e9unions Teams'),
    Screen('signatures', '\u270d\ufe0f \u00c9margements / QR', '\u00c9margements et signatures'),
    Screen('access', '\U0001f510 Codes participants', 'Codes de connexion des participants'),
    Screen('documents', '\U0001f4da Documents', 'Documents de l\u2019intervention'),
    Screen('tools', '\U0001f9ed Outils Clart\u00e9360', 'Prescriptions et outils Clart\u00e9360'),
    Screen('quality', '\U0001f4cb Qualit\u00e9', 'Suivi qualit\u00e9 de l\u2019action'),
    Screen('reports', '\U0001f4e3 Signaler / informer', 'Transmissions \u00e0 l\u2019administration'),
)

ADMIN_ACTION_SCREENS = (
    Screen('action_parametres', '\u2699\ufe0f Param\u00e8tres', 'Param\u00e8tres de l\u2019action'),
    Screen('action_participants', '\U0001f465 Participants', 'Participants et espaces personnels'),
    Screen('action_intervenants', '\U0001f9d1\u200d\U0001f3eb Intervenants', 'Intervenants et affectations'),
    Screen('action_calendrier', '\U0001f4c5 Calendrier', 'Calendrier et cr\u00e9neaux'),
    Screen('action_teams', '\U0001f4bb Teams', 'R\u00e9unions Teams et pr\u00e9sences'),
    Screen('action_outils', '\U0001f9ed Outils Clart\u00e9360', 'Prescriptions et outils'),
    Screen('action_contractualisation', '\U0001f4dd Contractualisation', 'Contrats et conventions'),
    Screen('action_envois', '\U0001f4e8 Envois et relances', 'Envois, convocations et relances'),
    Screen('action_suivi', '\U0001f4ca Suivi / \u00e9margements', 'Suivi, \u00e9margements et justificatifs'),
    Screen('action_qualite', '\U0001f4cb Qualit\u00e9', 'Qualit\u00e9 de l\u2019action'),
    Screen('action_documents', '\U0001f4c1 Documents', 'Documents et versions'),
    Screen('action_journal', '\U0001f4d6 Journal', 'Journal et tra\u00e7abilit\u00e9'),
)

CLIENT_SCREENS = (
    Screen('home', '🏠 Mes actions', 'Tableau de bord Client / DRH'),
    Screen('actions', '📁 Dossiers autorisés', 'Suivi de mon action'),
    Screen('planning', '📅 Planning collectif', 'Planning des séances collectives'),
    Screen('documents', '📄 Mes documents', 'Justificatifs et dépôts administratifs'),
    Screen('quality', '📋 Suivi qualité', 'Suivi qualité non nominatif'),
    Screen('contact', '✉️ Contacter Clarté360', 'Contacter votre interlocuteur'),
    Screen('profile', '👤 Mon compte', 'Mon identité de contact'),
    Screen('archives', '🗂️ Téléchargements', 'Mes justificatifs téléchargeables'),
)

ADMIN_PAGES = {
    'Tableau de bord': '\U0001f3e0 Tableau de bord',
    'Nouvelle action': '\u2795 Nouvelle action',
    'Importer une action': '\U0001f4e5 Importer une action',
    'Actions': '\U0001f4c2 Actions et dossiers',
    'Relances': '\U0001f4e8 Relances',
    'Qualit\u00e9': '\U0001f4cb Qualit\u00e9',
    '\u00c9tudes PIP/O*NET': '\U0001f50e \u00c9tudes PIP / O*NET',
    'Contacts / Prospects': '\U0001f91d Contacts / Prospects',
    'Espace Client / DRH': '🏢 Espace Client / DRH',
    'Intervenants / Partenaires': '\U0001f9d1\u200d\U0001f4bc Intervenants / Partenaires',
    'Param\u00e8tres': '\u2699\ufe0f Param\u00e8tres',
}


def screens_for_role(role: str, *, action_selected: bool = True) -> tuple[Screen, ...]:
    """P4 offre quatre espaces; aucun droit ne provient de la navigation."""
    role = str(role).strip().upper()
    if role == 'BENEFICIARY':
        return BENEFICIARY_SCREENS if action_selected else BENEFICIARY_SCREENS[:2]
    if role == 'TRAINER':
        return TRAINER_SCREENS
    if role == 'CLIENT':
        return CLIENT_SCREENS if action_selected else (CLIENT_SCREENS[0], CLIENT_SCREENS[6])
    if role == 'ADMIN_ACTION':
        return ADMIN_ACTION_SCREENS
    raise ValueError('Role de navigation inconnu : ' + role)


def preferred_screen(available, requested, default=None):
    """Fail closed to a visible screen, not to a hidden old tab."""
    keys = [x.key for x in available]
    if not keys:
        raise ValueError('Navigation vide')
    return requested if requested in keys else (default if default in keys else keys[0])


def authorized_action_choice(available_action_ids, requested):
    """Never restore a stale or revoked action identifier."""
    try:
        wanted = int(requested)
    except (TypeError, ValueError):
        return None
    return wanted if wanted in {int(i) for i in available_action_ids} else None


def action_rows(rows, selected_action_id):
    if selected_action_id is None:
        return list(rows)
    return [row for row in rows if row.get('action_id') is not None and int(row['action_id']) == int(selected_action_id)]
