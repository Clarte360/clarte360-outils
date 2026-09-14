from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

MAX_NAME_LEN = 100
MAX_SHORT_TEXT_LEN = 200
MAX_FREE_TEXT_LEN = 2000
MAX_EMAIL_LEN = 254
MAX_PHONE_LEN = 40
MAX_JSON_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_ID_LEN = 160

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EMAIL_RE = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$", re.IGNORECASE)
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
_ACCESS_CODE_RE = re.compile(r"^[0-9]{6}$")
_ALLOWED_PHONE_RE = re.compile(r"^[0-9+().\-\s]+$")


class ValidationError(ValueError):
    """Business/input validation error safe to display to an end user."""


def clean_text(value: Any, *, max_len: int, field: str, allow_empty: bool = True) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    if _CONTROL_RE.search(text) or "\r" in text or "\n" in text:
        raise ValidationError(f"{field} contient des caractères non autorisés.")
    text = " ".join(text.strip().split())
    if not text and not allow_empty:
        raise ValidationError(f"{field} est obligatoire.")
    if len(text) > max_len:
        raise ValidationError(f"{field} est trop long (maximum {max_len} caractères).")
    return text


def validate_person_name(value: Any, field: str) -> str:
    text = clean_text(value, max_len=MAX_NAME_LEN, field=field, allow_empty=False)
    for ch in text:
        if ch.isalpha() or ch in " '-’‐‑–.":
            continue
        raise ValidationError(f"{field} contient un caractère non autorisé.")
    if not any(ch.isalpha() for ch in text):
        raise ValidationError(f"{field} doit contenir des lettres.")
    return text


def validate_email(value: Any) -> str:
    text = clean_text(value, max_len=MAX_EMAIL_LEN, field="E-mail", allow_empty=False).lower()
    if "," in text or ";" in text or not _EMAIL_RE.fullmatch(text):
        raise ValidationError("Adresse e-mail invalide. Saisissez une seule adresse complète.")
    return text


def validate_phone(value: Any) -> str:
    text = clean_text(value, max_len=MAX_PHONE_LEN, field="Téléphone", allow_empty=False)
    if not _ALLOWED_PHONE_RE.fullmatch(text):
        raise ValidationError("Téléphone invalide : utilisez uniquement chiffres, espaces, +, parenthèses, points ou tirets.")
    if text.count("+") > 1 or ("+" in text and not text.lstrip().startswith("+")):
        raise ValidationError("Téléphone invalide : le signe + n'est autorisé qu'au début.")
    digits = re.sub(r"\D", "", text)
    if not 7 <= len(digits) <= 15:
        raise ValidationError("Téléphone invalide : le numéro doit contenir entre 7 et 15 chiffres.")
    return text


def validate_optional_short_text(value: Any, field: str) -> str:
    return clean_text(value, max_len=MAX_SHORT_TEXT_LEN, field=field, allow_empty=True)


def validate_free_text(value: Any, field: str, max_len: int = MAX_FREE_TEXT_LEN) -> str:
    # Free text may contain punctuation, accents and international characters, but not control characters.
    return clean_text(value, max_len=max_len, field=field, allow_empty=True)


def validate_access_code(value: Any) -> str:
    code = str(value or "").strip()
    if not _ACCESS_CODE_RE.fullmatch(code):
        raise ValidationError("Le code d'accès doit contenir exactement 6 chiffres.")
    return code


def validate_safe_id(value: Any, field: str, *, required: bool = True) -> str | None:
    if value is None or str(value).strip() == "":
        if required:
            raise ValidationError(f"Identifiant manquant : {field}.")
        return None
    text = str(value).strip()
    if len(text) > MAX_ID_LEN or not _SAFE_ID_RE.fullmatch(text) or ".." in text:
        raise ValidationError(f"Identifiant invalide : {field}.")
    return text


def validate_string_list(values: Any, field: str, *, allowed: Iterable[str] | None = None, max_items: int = 30) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)) or len(values) > max_items:
        raise ValidationError(f"{field} invalide.")
    allowed_set = set(allowed or [])
    out: list[str] = []
    for raw in values:
        text = clean_text(raw, max_len=100, field=field, allow_empty=False)
        if allowed_set and text not in allowed_set:
            raise ValidationError(f"{field} contient une valeur non autorisée.")
        if text not in out:
            out.append(text)
    return tuple(out)


def validate_score(value: Any, field: str, *, minimum: int = 1, maximum: int = 5) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} invalide.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} doit être un nombre.") from exc
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise ValidationError(f"{field} doit être un entier.")
    result = int(numeric)
    if not minimum <= result <= maximum:
        raise ValidationError(f"{field} doit être compris entre {minimum} et {maximum}.")
    return result


def validate_https_url(value: Any, field: str = "URL", *, allow_empty: bool = False) -> str:
    text = clean_text(value, max_len=2048, field=field, allow_empty=allow_empty)
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValidationError(f"{field} doit être une URL HTTPS valide.")
    return text


def validate_epoch_window(iat: Any, exp: Any, *, now_epoch: int | None = None, max_lifetime_seconds: int = 7 * 24 * 3600) -> tuple[int, int]:
    try:
        iat_i = int(iat)
        exp_i = int(exp)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Dates du jeton de lancement invalides.") from exc
    now = int(datetime.now(timezone.utc).timestamp()) if now_epoch is None else int(now_epoch)
    if iat_i > now + 300:
        raise ValidationError("Date de création du jeton incohérente.")
    if exp_i < now:
        raise ValidationError("Ce lien de lancement a expiré.")
    if exp_i <= iat_i or exp_i - iat_i > max_lifetime_seconds:
        raise ValidationError("Durée de validité du jeton incohérente.")
    return iat_i, exp_i


def reject_spreadsheet_formula(value: Any, field: str = "Valeur") -> str:
    text = str(value or "")
    if text.lstrip().startswith(("=", "+", "-", "@")):
        raise ValidationError(f"{field} commence par un caractère de formule interdit.")
    return text


def validate_mapping_size(payload: Any, field: str, *, max_keys: int = 500) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValidationError(f"{field} doit être un objet JSON.")
    if len(payload) > max_keys:
        raise ValidationError(f"{field} est anormalement volumineux.")
    return payload
