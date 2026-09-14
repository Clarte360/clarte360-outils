from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


class InputValidationError(ValueError):
    pass


def _text(value, field, *, required=False, max_len=255, allow_newlines=False):
    if value is None:
        value = ''
    value = str(value).strip()
    if required and not value:
        raise InputValidationError(f"{field} est obligatoire.")
    if len(value) > max_len:
        raise InputValidationError(f"{field} est trop long (maximum {max_len} caractères).")
    for ch in value:
        cat = unicodedata.category(ch)
        if cat.startswith('C') and not (allow_newlines and ch in '\r\n\t'):
            raise InputValidationError(f"{field} contient un caractère de contrôle interdit.")
    return value


def validate_person_name(value, field='Nom', *, required=True, max_len=100):
    value = _text(value, field, required=required, max_len=max_len)
    if not value:
        return None
    # Unicode letters + spaces + apostrophes + hyphens. No digits / symbols.
    allowed_punct = {"'", '’', '-', ' '}
    if any(not (ch.isalpha() or ch in allowed_punct) for ch in value):
        raise InputValidationError(f"{field} ne peut contenir que des lettres, espaces, apostrophes et tirets.")
    if not any(ch.isalpha() for ch in value):
        raise InputValidationError(f"{field} doit contenir au moins une lettre.")
    if value[0] in allowed_punct or value[-1] in allowed_punct:
        raise InputValidationError(f"{field} ne peut pas commencer ou finir par un espace, une apostrophe ou un tiret.")
    if '  ' in value or '--' in value or "''" in value or '’’' in value:
        raise InputValidationError(f"{field} contient une répétition de séparateurs invalide.")
    return value


def validate_full_name(value, field='Nom et prénom', *, required=True, max_len=160):
    return validate_person_name(value, field, required=required, max_len=max_len)


def validate_email(value, field='E-mail', *, required=False, max_len=254):
    value = _text(value, field, required=required, max_len=max_len)
    if not value:
        return None
    if any(ch.isspace() for ch in value):
        raise InputValidationError(f"{field} ne doit contenir aucun espace.")
    if value.count('@') != 1:
        raise InputValidationError(f"{field} n'est pas une adresse e-mail valide.")
    local, domain = value.rsplit('@', 1)
    if not local or not domain or len(local) > 64 or len(domain) > 253:
        raise InputValidationError(f"{field} n'est pas une adresse e-mail valide.")
    if local[0] == '.' or local[-1] == '.' or '..' in local:
        raise InputValidationError(f"{field} n'est pas une adresse e-mail valide.")
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", local):
        raise InputValidationError(f"{field} contient des caractères non autorisés.")
    labels = domain.split('.')
    if len(labels) < 2 or any(not x for x in labels):
        raise InputValidationError(f"{field} doit contenir un domaine complet (ex. exemple.fr).")
    for label in labels:
        if len(label) > 63 or label.startswith('-') or label.endswith('-') or not re.fullmatch(r'[A-Za-z0-9-]+', label):
            raise InputValidationError(f"{field} contient un domaine invalide.")
    return value.lower()


def validate_phone(value, field='Téléphone', *, required=False):
    value = _text(value, field, required=required, max_len=40)
    if not value:
        return None
    if not re.fullmatch(r'[+0-9(). /-]+', value):
        raise InputValidationError(f"{field} contient des caractères interdits.")
    if value.count('+') > 1 or ('+' in value and not value.startswith('+')):
        raise InputValidationError(f"{field} contient un signe + mal placé.")
    digits = re.sub(r'\D', '', value)
    if not 6 <= len(digits) <= 15:
        raise InputValidationError(f"{field} doit contenir entre 6 et 15 chiffres.")
    return value


def validate_iso_date(value, field='Date', *, required=False, min_date=None, max_date=None):
    if value in (None, ''):
        if required:
            raise InputValidationError(f"{field} est obligatoire.")
        return None
    if isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, date):
        d = value
    else:
        raw = str(value).strip()
        try:
            d = date.fromisoformat(raw[:10])
        except Exception:
            raise InputValidationError(f"{field} doit être une date valide au format AAAA-MM-JJ.")
    if min_date and d < min_date:
        raise InputValidationError(f"{field} est antérieure à la date minimale autorisée ({min_date.isoformat()}).")
    if max_date and d > max_date:
        raise InputValidationError(f"{field} est postérieure à la date maximale autorisée ({max_date.isoformat()}).")
    return d.isoformat()


def validate_birth_date(value, field='Date de naissance', *, required=False):
    if value in (None, ''):
        if required:
            raise InputValidationError(f"{field} est obligatoire.")
        return None
    today = date.today()
    min_d = date(today.year - 120, today.month, min(today.day, 28))
    iso = validate_iso_date(value, field, required=required, min_date=min_d, max_date=today)
    return iso


def validate_date_range(start_value, end_value, start_field='Date de début', end_field='Date de fin'):
    start = validate_iso_date(start_value, start_field, required=True)
    end = validate_iso_date(end_value, end_field, required=True)
    if end < start:
        raise InputValidationError(f"{end_field} ne peut pas être antérieure à {start_field.lower()}.")
    return start, end


def validate_time(value, field='Heure', *, required=True):
    value = _text(value, field, required=required, max_len=8)
    if not value:
        return None
    try:
        parsed = datetime.strptime(value[:5], '%H:%M').time()
    except Exception:
        raise InputValidationError(f"{field} doit être une heure valide au format HH:MM.")
    return parsed.strftime('%H:%M')


def validate_slot(date_value, start_value, end_value):
    d = validate_iso_date(date_value, 'Date du créneau', required=True)
    s = validate_time(start_value, 'Heure de début')
    e = validate_time(end_value, 'Heure de fin')
    if s == e:
        raise InputValidationError("L'heure de fin doit être différente de l'heure de début.")
    return d, s, e


def validate_action_no(value, field="N° d'action", *, required=True):
    value = _text(value, field, required=required, max_len=50).upper()
    if not value:
        return None
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._/-]*', value):
        raise InputValidationError(f"{field} ne peut contenir que lettres, chiffres, point, tiret, underscore ou slash.")
    return value


def validate_code(value, field='Code', *, required=False, max_len=80):
    value = _text(value, field, required=required, max_len=max_len)
    if not value:
        return None
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', value):
        raise InputValidationError(f"{field} contient des caractères non autorisés.")
    return value


def validate_free_text(value, field='Texte', *, required=False, max_len=4000):
    value = _text(value, field, required=required, max_len=max_len, allow_newlines=True)
    return value or None


def validate_short_text(value, field='Champ', *, required=False, max_len=200):
    value = _text(value, field, required=required, max_len=max_len)
    return value or None


def validate_postal_code(value, field='Code postal', *, required=False):
    value = _text(value, field, required=required, max_len=12)
    if not value:
        return None
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 -]*', value):
        raise InputValidationError(f"{field} contient des caractères non autorisés.")
    return value.upper()


def validate_siret(value, field='SIRET', *, required=False):
    value = _text(value, field, required=required, max_len=20)
    if not value:
        return None
    digits = re.sub(r'\s', '', value)
    if not re.fullmatch(r'\d{14}', digits):
        raise InputValidationError(f"{field} doit comporter exactement 14 chiffres.")
    return digits


def validate_nda(value, field='NDA', *, required=False):
    value = _text(value, field, required=required, max_len=20)
    if not value:
        return None
    digits = re.sub(r'[ .-]', '', value)
    if not re.fullmatch(r'\d{11}', digits):
        raise InputValidationError(f"{field} doit comporter exactement 11 chiffres.")
    return digits


def validate_naf(value, field='Code NAF', *, required=False):
    value = _text(value, field, required=required, max_len=8).upper()
    if not value:
        return None
    compact = value.replace(' ', '').replace('.', '')
    if not re.fullmatch(r'\d{4}[A-Z]', compact):
        raise InputValidationError(f"{field} doit avoir le format 4 chiffres + 1 lettre (ex. 8559A).")
    return compact


def validate_vat_id(value, field='TVA / Id CEE', *, required=False):
    value = _text(value, field, required=required, max_len=20).upper().replace(' ', '')
    if not value:
        return None
    if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{2,13}', value):
        raise InputValidationError(f"{field} n'a pas un format intracommunautaire valide.")
    return value


def validate_url(value, field='Site web', *, required=False):
    value = _text(value, field, required=required, max_len=500)
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise InputValidationError(f"{field} doit commencer par http:// ou https:// et contenir un domaine.")
    return value


def validate_timezone(value, field='Fuseau horaire'):
    value = _text(value, field, required=True, max_len=80)
    try:
        ZoneInfo(value)
    except Exception:
        raise InputValidationError(f"{field} IANA inconnu (ex. Europe/Paris).")
    return value


def validate_positive_number(value, field, *, minimum=0, maximum=None, integer=False):
    try:
        n = int(value) if integer else float(value)
    except Exception:
        raise InputValidationError(f"{field} doit être un nombre valide.")
    if n < minimum:
        raise InputValidationError(f"{field} doit être supérieur ou égal à {minimum}.")
    if maximum is not None and n > maximum:
        raise InputValidationError(f"{field} doit être inférieur ou égal à {maximum}.")
    return n


def validate_json_text(value, field='JSON', *, required=False):
    value = _text(value, field, required=required, max_len=50000, allow_newlines=True)
    if not value:
        return '{}' if not required else value
    try:
        parsed = json.loads(value)
    except Exception as exc:
        raise InputValidationError(f"{field} n'est pas un JSON valide : {exc.msg if hasattr(exc, 'msg') else exc}")
    if not isinstance(parsed, dict):
        raise InputValidationError(f"{field} doit contenir un objet JSON {{...}}.")
    return json.dumps(parsed, ensure_ascii=False)


def validate_action_payload(data):
    d = dict(data)
    d['action_no'] = validate_action_no(d.get('action_no'))
    d['title'] = validate_short_text(d.get('title'), 'Intitulé', required=True, max_len=200)
    d['subtitle'] = validate_short_text(d.get('subtitle'), 'Intitulé complémentaire', max_len=200)
    d['client_name'] = validate_short_text(d.get('client_name'), 'Client / entreprise', max_len=200)
    d['group_code'] = validate_code(d.get('group_code'), 'Code de groupe', max_len=80)
    d['admin_email'] = validate_email(d.get('admin_email'), 'E-mail administrateur', required=True)
    d['trainer_email'] = validate_email(d.get('trainer_email'), 'E-mail intervenant')
    if d.get('trainer_name'):
        d['trainer_name'] = validate_full_name(d.get('trainer_name'), 'Nom intervenant', required=False)
    d['location'] = validate_short_text(d.get('location'), 'Lieu / précision', max_len=300)
    d['notes'] = validate_free_text(d.get('notes'), 'Observations', max_len=10000)
    d['planned_hours'] = validate_positive_number(d.get('planned_hours', 0), 'Durée prévue', minimum=0, maximum=10000)
    d['expected_participants'] = validate_positive_number(d.get('expected_participants', 1), 'Nombre prévu de participants', minimum=1, maximum=100000, integer=True)
    return d


def validate_participant_payload(data, *, require_identity=True):
    d = dict(data)
    d['last_name'] = validate_person_name(d.get('last_name'), 'Nom', required=require_identity)
    d['birth_name'] = validate_person_name(d.get('birth_name'), 'Nom de naissance', required=False)
    d['first_name'] = validate_person_name(d.get('first_name'), 'Prénom', required=require_identity)
    d['birth_date'] = validate_birth_date(d.get('birth_date'), required=False)
    d['email'] = validate_email(d.get('email'), 'E-mail', required=False)
    d['phone'] = validate_phone(d.get('phone'), 'Téléphone', required=False)
    d['individual_action_no'] = validate_action_no(d.get('individual_action_no'), "N° action individuel", required=False)
    d['employee_id'] = validate_short_text(d.get('employee_id'), 'Matricule', max_len=80)
    d['company_name'] = validate_short_text(d.get('company_name'), 'Entreprise / client', max_len=200)
    return d


def validate_organization_payload(data):
    d = dict(data)
    d['name'] = validate_short_text(d.get('name'), 'Nom commercial', required=True, max_len=200)
    d['legal_name'] = validate_short_text(d.get('legal_name'), 'Raison sociale', max_len=250)
    d['address'] = validate_short_text(d.get('address'), 'Adresse', max_len=300)
    d['postal_code'] = validate_postal_code(d.get('postal_code'))
    d['city'] = validate_short_text(d.get('city'), 'Ville', max_len=120)
    d['country'] = validate_short_text(d.get('country'), 'Pays', max_len=120)
    d['siret'] = validate_siret(d.get('siret'))
    d['rcs'] = validate_short_text(d.get('rcs'), 'RCS', max_len=80)
    d['naf'] = validate_naf(d.get('naf'))
    d['vat_id'] = validate_vat_id(d.get('vat_id'))
    d['nda'] = validate_nda(d.get('nda'))
    d['website'] = validate_url(d.get('website'))
    d['general_email'] = validate_email(d.get('general_email'), 'E-mail général')
    d['phone'] = validate_phone(d.get('phone'))
    d['timezone'] = validate_timezone(d.get('timezone') or 'Europe/Paris')
    d['privacy_contact'] = validate_email(d.get('privacy_contact'), 'Contact RGPD') if d.get('privacy_contact') else None
    d['privacy_notice'] = validate_free_text(d.get('privacy_notice'), 'Notice RGPD', max_len=20000)
    d['email_from_name'] = validate_short_text(d.get('email_from_name'), 'Nom expéditeur', max_len=120)
    d['email_from_address'] = validate_email(d.get('email_from_address'), 'Adresse expéditeur')
    if d.get('retention_months') not in (None, ''):
        d['retention_months'] = validate_positive_number(d.get('retention_months'), 'Conservation indicative', minimum=0, maximum=1200, integer=True)
    return d


def validate_agency_payload(data):
    d = dict(data)
    d['name'] = validate_short_text(d.get('name'), "Nom de l'agence", required=True, max_len=200)
    d['address'] = validate_short_text(d.get('address'), 'Adresse', max_len=300)
    d['postal_code'] = validate_postal_code(d.get('postal_code'))
    d['city'] = validate_short_text(d.get('city'), 'Ville', max_len=120)
    d['country'] = validate_short_text(d.get('country'), 'Pays', max_len=120)
    d['siret'] = validate_siret(d.get('siret'))
    d['nda'] = validate_nda(d.get('nda'))
    d['email'] = validate_email(d.get('email'), 'E-mail agence')
    d['phone'] = validate_phone(d.get('phone'))
    return d


def validate_trainer_payload(name, email=None, phone=None):
    return (
        validate_full_name(name, 'Nom et prénom', required=True),
        validate_email(email, 'E-mail', required=False),
        validate_phone(phone, 'Téléphone', required=False),
    )


def validate_crm_payload(first_name, last_name, email, phone=None, job_title=None, company=None):
    return {
        'first_name': validate_person_name(first_name, 'Prénom', required=True),
        'last_name': validate_person_name(last_name, 'Nom', required=True),
        'email': validate_email(email, 'E-mail', required=True),
        'phone': validate_phone(phone, 'Téléphone'),
        'job_title': validate_short_text(job_title, 'Fonction', max_len=160),
        'company': validate_short_text(company, 'Entreprise', max_len=200),
    }
