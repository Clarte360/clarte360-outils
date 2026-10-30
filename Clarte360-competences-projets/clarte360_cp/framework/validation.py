from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

MAX_ID_LEN = 160
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


class ValidationError(ValueError):
    """Erreur d'entrée sûre à afficher sans détail technique."""


def clean_text(value: Any, *, max_len: int, field: str, allow_empty: bool = True) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    if _CONTROL_RE.search(text) or "\r" in text:
        raise ValidationError(f"{field} contient des caractères non autorisés.")
    text = text.strip()
    if not text and not allow_empty:
        raise ValidationError(f"{field} est obligatoire.")
    if len(text) > max_len:
        raise ValidationError(f"{field} est trop long.")
    return text


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
    if not isinstance(values, (list, tuple)) or len(values) > max_items:
        raise ValidationError(f"{field} invalide.")
    allowed_set = set(allowed or ())
    out: list[str] = []
    for raw in values:
        text = clean_text(raw, max_len=100, field=field, allow_empty=False)
        if allowed_set and text not in allowed_set:
            raise ValidationError(f"{field} contient une valeur non autorisée.")
        if text not in out:
            out.append(text)
    return tuple(out)


def validate_https_url(value: Any, field: str = "URL") -> str:
    text = clean_text(value, max_len=2048, field=field, allow_empty=False)
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValidationError(f"{field} doit être une URL HTTPS valide.")
    return text


def validate_epoch_window(iat: Any, exp: Any, *, now_epoch: int | None = None, max_lifetime_seconds: int = 900) -> tuple[int, int]:
    try:
        iat_i, exp_i = int(iat), int(exp)
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
