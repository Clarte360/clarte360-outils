import json
import math
import re
from datetime import datetime

class ValidationError(ValueError):
    pass

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_TEXT = 4000
EMAIL_RE = re.compile(r"^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
QUESTION_ID_RE = re.compile(r"^Q\d{3}$")
ALLOWED_OPTIONS = {"A", "B", "C", "D"}


def clean_text(value, field="Texte", max_len=MAX_TEXT, required=False, single_line=False):
    s = str(value or "").strip()
    if required and not s:
        raise ValidationError(f"{field} est obligatoire.")
    if len(s) > max_len:
        raise ValidationError(f"{field} est trop long ({max_len} caractères maximum).")
    if any(ord(c) < 32 and c not in "\n\t" for c in s):
        raise ValidationError(f"{field} contient des caractères non autorisés.")
    if single_line and ("\r" in s or "\n" in s):
        raise ValidationError(f"{field} doit tenir sur une seule ligne.")
    return s


def name(value, field="Nom", required=True):
    s = clean_text(value, field, 100, required, single_line=True)
    if not s:
        return s
    if any(ch.isdigit() for ch in s):
        raise ValidationError(f"{field} ne doit pas contenir de chiffre.")
    if not all(ch.isalpha() or ch in " '-’" for ch in s):
        raise ValidationError(f"{field} contient des caractères non autorisés.")
    if not any(ch.isalpha() for ch in s):
        raise ValidationError(f"{field} est invalide.")
    return re.sub(r"\s+", " ", s)


def email(value, required=True, field="Adresse e-mail"):
    s = clean_text(value, field, 254, required, single_line=True).lower()
    if not s:
        return s
    if not EMAIL_RE.fullmatch(s):
        raise ValidationError(f"{field} invalide.")
    local, domain = s.rsplit("@", 1)
    if len(local) > 64 or len(domain) > 253 or ".." in s:
        raise ValidationError(f"{field} invalide.")
    return s


def phone(value, required=False):
    s = clean_text(value, "Téléphone", 40, required, single_line=True)
    if not s:
        return ""
    if not re.fullmatch(r"\+?[0-9 ().-]+", s):
        raise ValidationError("Téléphone invalide.")
    digits = re.sub(r"\D", "", s)
    if not 7 <= len(digits) <= 15:
        raise ValidationError("Téléphone invalide.")
    return s


def safe_id(value, field="Identifiant", required=True):
    s = clean_text(value, field, 160, required, single_line=True)
    if not s:
        return s
    if not ID_RE.fullmatch(s) or ".." in s:
        raise ValidationError(f"{field} invalide.")
    return s


def access_code(value):
    s = clean_text(value, "Code d'accès", 6, True, single_line=True)
    if not re.fullmatch(r"\d{6}", s):
        raise ValidationError("Le code d'accès doit contenir exactement 6 chiffres.")
    return s


def _iso_or_empty(value, field):
    s = clean_text(value, field, 40, False, single_line=True)
    if s:
        try:
            datetime.fromisoformat(s)
        except ValueError:
            raise ValidationError(f"{field} invalide.")
    return s


def validate_state(data, allow_completed=True):
    if not isinstance(data, dict):
        raise ValidationError("Le JSON doit contenir un objet.")
    if len(data) > 90:
        raise ValidationError("Structure JSON incohérente.")
    if data.get("outil") not in (None, "", "clarte360_preferences_professionnelles"):
        raise ValidationError("Ce JSON ne correspond pas à Préférences professionnelles.")
    completed = data.get("completed", False)
    if not isinstance(completed, bool):
        raise ValidationError("Statut de passation invalide.")
    if completed and not allow_completed:
        raise ValidationError("Ce JSON correspond à un questionnaire déjà terminé.")

    b = data.get("beneficiaire", {})
    if not isinstance(b, dict):
        raise ValidationError("Bénéficiaire invalide.")
    if b.get("prenom"):
        name(b.get("prenom"), "Prénom")
    if b.get("nom"):
        name(b.get("nom"), "Nom")
    if b.get("email"):
        email(b.get("email"))

    for key in ("session_id", "identifiant_session", "passation_root_id", "passation_id"):
        if data.get(key):
            safe_id(data.get(key), key)
    for key in ("started_at", "saved_at", "completed_at"):
        if data.get(key):
            _iso_or_empty(data.get(key), key)

    order = data.get("question_order_displayed", data.get("question_order", []))
    if not isinstance(order, list) or len(order) > 60:
        raise ValidationError("Ordre des questions invalide.")
    order = [str(x).strip() for x in order]
    if any(not QUESTION_ID_RE.fullmatch(x) for x in order) or len(set(order)) != len(order):
        raise ValidationError("Ordre des questions invalide.")

    option_orders = data.get("option_orders_displayed", data.get("option_orders", {}))
    if not isinstance(option_orders, dict) or len(option_orders) > 60:
        raise ValidationError("Ordre des propositions invalide.")
    for qid, opts in option_orders.items():
        qid = str(qid).strip()
        if not QUESTION_ID_RE.fullmatch(qid) or (order and qid not in order):
            raise ValidationError("Identifiant de question invalide dans les propositions.")
        if not isinstance(opts, list) or len(opts) != 4 or set(map(str, opts)) != ALLOWED_OPTIONS:
            raise ValidationError("Ordre des propositions invalide.")

    answers = data.get("answers", {})
    if not isinstance(answers, dict) or len(answers) > 60:
        raise ValidationError("Réponses invalides.")
    for qid, val in answers.items():
        qid = str(qid).strip()
        if not QUESTION_ID_RE.fullmatch(qid) or (order and qid not in order):
            raise ValidationError("Réponse associée à une question inconnue.")
        selected = val.get("selected_option") or val.get("selected") if isinstance(val, dict) else val
        if str(selected) not in ALLOWED_OPTIONS:
            raise ValidationError("Option de réponse invalide.")

    idx = data.get("current_index", 0)
    if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0 or idx > 60:
        raise ValidationError("Position de reprise invalide.")
    if order and idx > len(order):
        raise ValidationError("Position de reprise incohérente.")

    access = data.get("access", {})
    if access and not isinstance(access, dict):
        raise ValidationError("Traçabilité de session invalide.")
    if isinstance(access, dict):
        sessions = access.get("sessions", [])
        if not isinstance(sessions, list) or len(sessions) > 200:
            raise ValidationError("Historique de sessions invalide.")
        saves = access.get("sauvegardes", [])
        if not isinstance(saves, list) or len(saves) > 500:
            raise ValidationError("Historique de sauvegardes invalide.")
    return data


def decode_json_bytes(raw, allow_completed=True):
    if not isinstance(raw, (bytes, bytearray)):
        raise ValidationError("Fichier JSON invalide.")
    if len(raw) == 0:
        raise ValidationError("Le fichier JSON est vide.")
    if len(raw) > MAX_JSON_BYTES:
        raise ValidationError("Fichier JSON trop volumineux (2 Mo maximum).")
    try:
        data = json.loads(bytes(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValidationError("Le fichier doit être un JSON UTF-8 valide.")
    return validate_state(data, allow_completed=allow_completed)


def finite_number(value, field, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ValidationError(f"{field} invalide.")
    try:
        number = float(value)
    except Exception:
        raise ValidationError(f"{field} invalide.")
    if not math.isfinite(number):
        raise ValidationError(f"{field} invalide.")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field} est inférieur à la valeur autorisée.")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field} dépasse la valeur autorisée.")
    return number
