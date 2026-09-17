import json, math, re
from datetime import date, datetime

class ValidationError(ValueError):
    pass

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_TEXT = 4000
EMAIL_RE = re.compile(r'^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$')
ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$')
HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
DANGEROUS_MARKERS = ('<script', '</script', 'javascript:', '<iframe', '<object', 'onerror=', 'onload=')


def clean_text(value, field='Texte', max_len=MAX_TEXT, required=False):
    s = str(value or '').strip()
    if required and not s:
        raise ValidationError(f'{field} est obligatoire.')
    if len(s) > max_len:
        raise ValidationError(f'{field} est trop long ({max_len} caractères maximum).')
    if any(ord(c) < 32 and c not in '\n\t' for c in s):
        raise ValidationError(f'{field} contient des caractères de contrôle non autorisés.')
    low = s.casefold()
    if any(x in low for x in DANGEROUS_MARKERS):
        raise ValidationError(f'{field} contient un contenu non autorisé.')
    return s


def name(value, field='Nom', required=True):
    s = clean_text(value, field, 100, required)
    if s and (any(ch.isdigit() for ch in s) or not all(ch.isalpha() or ch in " '-’" for ch in s)):
        raise ValidationError(f'{field} contient des caractères non autorisés.')
    return s


def email(value, required=True):
    s = clean_text(value, 'Adresse e-mail', 254, required).lower()
    if s and ('\r' in s or '\n' in s or not EMAIL_RE.fullmatch(s)):
        raise ValidationError('Adresse e-mail invalide.')
    return s


def phone(value, required=False):
    s = clean_text(value, 'Téléphone', 40, required)
    if not s:
        return ''
    if not re.fullmatch(r'\+?[0-9 ().-]+', s):
        raise ValidationError('Téléphone invalide.')
    digits = re.sub(r'\D', '', s)
    if not 7 <= len(digits) <= 15:
        raise ValidationError('Téléphone invalide.')
    return s


def safe_id(value, field='Identifiant', required=True):
    s = clean_text(value, field, 160, required)
    if s and (not ID_RE.fullmatch(s) or '..' in s):
        raise ValidationError(f'{field} invalide.')
    return s


def score(value, field='Cote'):
    if isinstance(value, bool):
        raise ValidationError(f'{field} invalide.')
    try:
        f = float(value)
    except Exception:
        raise ValidationError(f'{field} invalide.')
    if not math.isfinite(f) or f < 0 or f > 10 or int(f) != f:
        raise ValidationError(f'{field} doit être un entier entre 0 et 10.')
    return int(f)


def iso_date(value, field='Date', required=False):
    s = clean_text(value, field, 20, required)
    if not s:
        return ''
    try:
        d = date.fromisoformat(s)
    except Exception:
        raise ValidationError(f'{field} invalide.')
    if d.year < 1900 or d.year > 2100:
        raise ValidationError(f'{field} incohérente.')
    return s


def hex_color(value, field='Couleur'):
    s = clean_text(value, field, 7, True)
    if not HEX_RE.fullmatch(s):
        raise ValidationError(f'{field} invalide.')
    return s.upper()


def validate_state(data):
    if not isinstance(data, dict):
        raise ValidationError('Le JSON doit contenir un objet.')
    if len(data) > 100:
        raise ValidationError('Structure JSON incohérente.')
    b = data.get('beneficiaire', {})
    if not isinstance(b, dict):
        raise ValidationError('Bénéficiaire invalide.')
    if b.get('prenom'): name(b['prenom'], 'Prénom')
    if b.get('nom'): name(b['nom'], 'Nom')
    if b.get('email'): email(b['email'])
    if b.get('consultant'): clean_text(b['consultant'], 'Consultant', 100)
    if b.get('date_realisation'): iso_date(b['date_realisation'], 'Date de réalisation')
    for idkey in ('root_passage_id', 'identifiant_racine_passation'):
        if data.get(idkey): safe_id(data[idkey], idkey)
    vals = data.get('valeurs', [])
    if not isinstance(vals, list) or len(vals) > 24:
        raise ValidationError('La liste des valeurs est invalide (24 maximum).')
    for i, v in enumerate(vals):
        if not isinstance(v, dict):
            raise ValidationError(f'Valeur {i+1} invalide.')
        clean_text(v.get('nom', ''), f'Nom valeur {i+1}', 120, True)
        clean_text(v.get('definition', ''), f'Définition valeur {i+1}', 1200)
        if v.get('couleur'): hex_color(v['couleur'])
        ds = v.get('domaines', [])
        if not isinstance(ds, list) or len(ds) != 5:
            raise ValidationError(f'Les 5 domaines de la valeur {i+1} sont requis.')
        for d in ds:
            if not isinstance(d, dict): raise ValidationError('Domaine invalide.')
            clean_text(d.get('domaine',''), 'Domaine', 80, True)
            clean_text(d.get('periode',''), 'Date/période', 160)
            clean_text(d.get('exemple',''), 'Exemple', 2000)
            sc = score(d.get('cote', 0))
            if sc > 2 and (not str(d.get('periode','')).strip() or not str(d.get('exemple','')).strip()):
                raise ValidationError('Une cote supérieure à 2 exige une période et un exemple concret.')
    ve = data.get('valeurs_energies', {})
    if ve and not isinstance(ve, dict):
        raise ValidationError('Valeurs énergies invalides.')
    if isinstance(ve, dict):
        sel = ve.get('selected', [])
        if not isinstance(sel, list) or len(sel) > 3:
            raise ValidationError('Trois valeurs énergie maximum.')
        for x in sel:
            if not isinstance(x, int) or x < 0 or x >= len(vals):
                raise ValidationError('Sélection de valeur énergie invalide.')
        entries = ve.get('entries', {})
        if not isinstance(entries, dict): raise ValidationError('Données valeurs énergies invalides.')
        for key, e in entries.items():
            if not isinstance(e, dict): raise ValidationError('Donnée valeur énergie invalide.')
            if str(key).isdigit() and int(key) >= len(vals): raise ValidationError('Référence de valeur énergie invalide.')
            score(e.get('score_revise', 0), 'Cotation revisitée')
            clean_text(e.get('commentaire',''), 'Commentaire énergie', 2000)
            for arrkey in ('actions','maintien'):
                arr = e.get(arrkey, [])
                if not isinstance(arr, list) or len(arr) > 5:
                    raise ValidationError('Liste actions/points d’appui invalide.')
                for t in arr: clean_text(t, 'Action/point d’appui', 500)
    return data


def decode_json_bytes(raw):
    if not isinstance(raw, (bytes, bytearray)):
        raise ValidationError('Fichier JSON invalide.')
    if len(raw) > MAX_JSON_BYTES:
        raise ValidationError('Fichier JSON trop volumineux (2 Mo maximum).')
    try:
        data = json.loads(bytes(raw).decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValidationError('Le fichier doit être un JSON UTF-8 valide.')
    return validate_state(data)
