from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from email.utils import parseaddr
from typing import Any, Iterable

MAX_TEXT = 5000
MAX_SHORT = 250
MAX_APS_BYTES = 2_000_000
MAX_XLSM_BYTES = 25_000_000

_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '\-’][^\W\d_]+)*$", re.UNICODE)
_NO_CLAR_RE = re.compile(r"^CLA\d{4,8}$")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PHONE_ALLOWED_RE = re.compile(r"^[+()\d .\-]{6,32}$")
_POSTAL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{2,11}$")

class ValidationError(ValueError):
    pass

def _s(value: Any) -> str:
    return '' if value is None else str(value)

def clean_text(value: Any, *, field: str, required: bool = False, max_len: int = MAX_TEXT) -> str:
    s = _s(value).replace('\r\n', '\n').replace('\r', '\n').strip()
    if required and not s:
        raise ValidationError(f"{field} est obligatoire.")
    if len(s) > max_len:
        raise ValidationError(f"{field} est trop long (maximum {max_len} caractères).")
    if _CTRL_RE.search(s):
        raise ValidationError(f"{field} contient des caractères de contrôle non autorisés.")
    return s

def clean_name(value: Any, *, field: str, required: bool = True) -> str:
    s = clean_text(value, field=field, required=required, max_len=120)
    if s and not _NAME_RE.fullmatch(s):
        raise ValidationError(f"{field} contient des caractères non autorisés. Les accents, espaces, apostrophes et tirets sont acceptés.")
    return s

def clean_email(value: Any, *, field: str = 'E-mail', required: bool = True) -> str:
    s = clean_text(value, field=field, required=required, max_len=254)
    if not s:
        return s
    if any(c in s for c in ('\r','\n','\t',' ', ',', ';')):
        raise ValidationError(f"{field} doit contenir une seule adresse e-mail valide.")
    _, addr = parseaddr(s)
    if addr != s or s.count('@') != 1:
        raise ValidationError(f"{field} est invalide.")
    local, domain = s.rsplit('@', 1)
    if not local or '.' not in domain or domain.startswith('.') or domain.endswith('.'):
        raise ValidationError(f"{field} est invalide.")
    return s

def clean_phone(value: Any, *, field: str = 'Téléphone', required: bool = False) -> str:
    s = clean_text(value, field=field, required=required, max_len=32)
    if not s:
        return s
    if not _PHONE_ALLOWED_RE.fullmatch(s):
        raise ValidationError(f"{field} contient un format non autorisé.")
    digits = re.sub(r'\D', '', s)
    if not 7 <= len(digits) <= 15:
        raise ValidationError(f"{field} doit contenir entre 7 et 15 chiffres.")
    return s

def clean_no_clar(value: Any) -> str:
    s = clean_text(value, field='N° action Clarté360', required=True, max_len=16).upper()
    if '..' in s or '/' in s or '\\' in s or not _NO_CLAR_RE.fullmatch(s):
        raise ValidationError("Le N° action doit respecter le format CLA suivi de 4 à 8 chiffres.")
    return s

def clean_postal(value: Any, *, required: bool = True) -> str:
    s = clean_text(value, field='Code postal', required=required, max_len=12)
    if s and not _POSTAL_RE.fullmatch(s):
        raise ValidationError('Le code postal contient des caractères non autorisés.')
    return s

def clean_amount(value: Any, *, field: str, minimum: float = 0.0, maximum: float = 1_000_000.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} doit être un nombre.")
    if not math.isfinite(x) or x < minimum or x > maximum:
        raise ValidationError(f"{field} doit être compris entre {minimum:g} et {maximum:g}.")
    return round(x, 2)

def clean_int(value: Any, *, field: str, minimum: int = 1, maximum: int = 1000) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} doit être un entier.")
    try:
        x = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} doit être un entier.")
    if float(value) != x or not minimum <= x <= maximum:
        raise ValidationError(f"{field} doit être un entier entre {minimum} et {maximum}.")
    return x

def clean_date(value: Any, *, field: str, min_date: date | None = None, max_date: date | None = None) -> date:
    if isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, date):
        d = value
    else:
        try:
            d = datetime.fromisoformat(str(value)[:10]).date()
        except Exception as exc:
            raise ValidationError(f"{field} est invalide.") from exc
    if min_date and d < min_date:
        raise ValidationError(f"{field} est antérieure à la date minimale autorisée.")
    if max_date and d > max_date:
        raise ValidationError(f"{field} est postérieure à la date maximale autorisée.")
    return d

def validate_birth_date(value: Any) -> date:
    today = date.today()
    d = clean_date(value, field='Date de naissance', min_date=date(1900,1,1), max_date=today)
    age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    if age < 14 or age > 100:
        raise ValidationError('La date de naissance paraît incohérente (âge attendu entre 14 et 100 ans).')
    return d

def validate_period(start: Any, end: Any, contract_date: Any) -> tuple[date,date,date]:
    c = clean_date(contract_date, field='Date du contrat', min_date=date(2000,1,1), max_date=date.today())
    s = clean_date(start, field="Date de début de l'action", min_date=date(2000,1,1), max_date=date(2100,12,31))
    e = clean_date(end, field="Date de fin de l'action", min_date=date(2000,1,1), max_date=date(2100,12,31))
    if e < s:
        raise ValidationError("La date de fin de l'action ne peut pas être antérieure à la date de début.")
    if s < c:
        raise ValidationError("La date de début de l'action ne peut pas être antérieure à la date du contrat.")
    return s,e,c

def validate_times(start: time, end: time) -> None:
    if not isinstance(start, time) or not isinstance(end, time):
        raise ValidationError('Les horaires sont invalides.')
    if (end.hour, end.minute, end.second) <= (start.hour, start.minute, start.second):
        raise ValidationError("L'horaire de fin doit être postérieur à l'horaire de début.")

def excel_safe_text(value: Any, *, field: str, max_len: int = MAX_TEXT) -> str:
    s = clean_text(value, field=field, required=False, max_len=max_len)
    # neutralise formula injection in generated/import XLSX without altering the visible meaning
    if s.startswith(('=', '+', '-', '@')):
        return "'" + s
    return s

def validate_financements(rows: Iterable[dict], expected_ttc: float) -> list[dict]:
    allowed = {'BENEFICIAIRE','ENTREPRISE','CPF','OPCO','FRANCE TRAVAIL','AUTRE FINANCEUR'}
    out=[]
    for idx, row in enumerate(rows, 1):
        typ = clean_text(row.get('TYPE_FINANCEUR'), field=f'Type financeur ligne {idx}', required=True, max_len=40).upper()
        if typ not in allowed:
            raise ValidationError(f'Type financeur ligne {idx} non reconnu.')
        amt = clean_amount(row.get('MONTANT_TTC') or 0, field=f'Montant TTC ligne {idx}')
        tva = clean_amount(row.get('TAUX_TVA') if row.get('TAUX_TVA') is not None else 20, field=f'TVA ligne {idx}', minimum=0, maximum=100)
        item=dict(row)
        item['TYPE_FINANCEUR']=typ
        item['NOM_FINANCEUR']=excel_safe_text(row.get('NOM_FINANCEUR'), field=f'Nom financeur ligne {idx}', max_len=200)
        item['FACTURE_A_ETABLIR_A']=excel_safe_text(row.get('FACTURE_A_ETABLIR_A'), field=f'Facturation ligne {idx}', max_len=500)
        item['OBSERVATIONS']=excel_safe_text(row.get('OBSERVATIONS'), field=f'Observations ligne {idx}', max_len=1500)
        item['MONTANT_TTC']=amt
        item['TAUX_TVA']=tva
        out.append(item)
    total=round(sum(x['MONTANT_TTC'] for x in out),2)
    if abs(total-round(expected_ttc,2)) >= 0.01:
        raise ValidationError(f'Les financements ({total:.2f} €) ne correspondent pas au total TTC ({expected_ttc:.2f} €).')
    return out

def validate_aps_document(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("Le JSON APS doit contenir un objet JSON.")
    meta=data.get('meta')
    if not isinstance(meta, dict) or meta.get('document_type') != 'APS':
        raise ValidationError('Le JSON fourni ne semble pas être une APS Clarté360.')
    b=data.get('beneficiaire')
    if not isinstance(b, dict):
        raise ValidationError("L'APS ne contient pas de bloc bénéficiaire exploitable.")
    # only validate fields present here; mandatory requirements are enforced at contractualisation time
    if b.get('prenom'): clean_name(b.get('prenom'), field='Prénom bénéficiaire')
    if b.get('nom'): clean_name(b.get('nom'), field='Nom bénéficiaire')
    if b.get('email'): clean_email(b.get('email'))
    if b.get('telephone'): clean_phone(b.get('telephone'))
    if b.get('date_naissance'): validate_birth_date(b.get('date_naissance'))
    return data

def validate_filename(name: str, allowed_suffixes: tuple[str,...]) -> None:
    if not name or '/' in name or '\\' in name or '..' in name:
        raise ValidationError('Nom de fichier non autorisé.')
    if not name.lower().endswith(tuple(s.lower() for s in allowed_suffixes)):
        raise ValidationError('Extension de fichier non autorisée.')
