import json
import random
import re
import smtplib
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_VERSION = "1.6.1-standard-clarte360"
APP_NAME = "Moteurs professionnels"
APP_FULL_NAME = "Clarté360 – Moteurs professionnels"
RGPD_TEXT_VERSION = "RGPD-Clarte360-v1.0-2026-07"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_XLSX = BASE_DIR / "data" / "moteurs_professionnels_curseurs_v0_1.xlsx"
LOGO_PATH = BASE_DIR / "assets" / "site_icon.png"
FINAL_EMAIL_TO = "contact@clarte360.com"
DEFAULT_SESSION_LIMIT_MINUTES = 15

###############################################################################
# CLARTE360
# MODULE : Informations institutionnelles
# ROLE   : Coordonnees, mentions legales, contact et pied de page PDF
# VERSION: 1.6.1
###############################################################################
CLARTE360_LEGAL = {
    "raison_sociale": "Clarté360",
    "forme": "SAS",
    "adresse": "60 rue François 1er",
    "code_postal_ville": "75008 Paris",
    "telephone": "01 89 48 08 25",
    "email": "contact@clarte360.com",
    "web": "www.clarte360.com",
    "rcs": "102349834",
    "siret": "10234983400014",
    "naf": "8559 A",
    "tva": "FR88102349834",
}

st.set_page_config(
    page_title=APP_FULL_NAME,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🟢",
    layout="centered",
)

st.markdown(f"""
<style>
:root {{ --clarte-teal: {OFFICIAL_TEAL}; }}
.stProgress > div > div > div > div {{ background-color: {OFFICIAL_TEAL}; }}
h1, h2, h3 {{ color: {OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"] {{ background-color: {OFFICIAL_TEAL}; border-color: {OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"]:hover {{ background-color: #006f6f; border-color: #006f6f; }}
.clarte-title-accent {{ color: {OFFICIAL_TEAL}; }}
.clarte-box {{ border-left: 6px solid {OFFICIAL_TEAL}; background: {LIGHT_TEAL}; padding: 1rem 1.1rem; border-radius: .55rem; margin: 1rem 0; color: {DARK_TEXT}; }}
.objectif-box {{ border: 1px solid #cfe6e6; background: #f8fbfb; padding: 1.2rem 1.4rem; border-radius: .9rem; margin: 1rem 0 1.4rem 0; color: {DARK_TEXT}; }}
.clarte-card {{ border: 1px solid #d9eeee; border-radius: .8rem; padding: 1rem; background: #fff; box-shadow: 0 1px 8px rgba(0,128,128,.08); margin-bottom: 1rem; }}
.question-title {{ color: {OFFICIAL_TEAL}; font-size: 2rem; font-weight: 750; margin: 1rem 0 .8rem 0; }}
.slider-instruction {{ color: {DARK_TEXT}; font-weight: 600; font-size: 1rem; margin: .8rem 0 .4rem 0; }}
.positioning-row {{ margin-top: .6rem; margin-bottom: 1.2rem; }}
.slider-card-left, .slider-card-right {{
    border-left: 7px solid {OFFICIAL_TEAL}; padding: 1.15rem 1.25rem; background: #f8fbfb;
    border-radius: .95rem; min-height: 135px; height: 135px; display: flex; align-items: center;
    justify-content: flex-start; box-shadow: 0 3px 16px rgba(0,128,128,.10);
    border-top: 1px solid #d9eeee; border-right: 1px solid #d9eeee; border-bottom: 1px solid #d9eeee;
}}
.slider-card-right {{ border-left-color: #7fb8b8; }}
.slider-card-left b, .slider-card-right b {{ font-size: 1.08rem; line-height: 1.35; }}
.connector-label {{ text-align:center; color:{OFFICIAL_TEAL}; font-size:.85rem; font-weight:700; margin-bottom:.15rem; }}
.small-muted {{ color:#666; font-size:.9rem; }}
div[data-testid="stSlider"] label {{ display: none !important; }}
div[data-testid="stSlider"] [data-testid="stTickBar"],
div[data-testid="stSlider"] [data-testid="stTickBarMin"],
div[data-testid="stSlider"] [data-testid="stTickBarMax"],
div[data-testid="stSlider"] [data-testid="stSliderThumbValue"],
div[data-testid="stSlider"] [class*="ThumbValue"],
div[data-testid="stSlider"] div[role="slider"] + div,
div[data-testid="stSlider"] p {{ display: none !important; }}
div[data-testid="stSlider"] {{ padding-top: 0 !important; }}
div[data-testid="stSlider"] [data-baseweb="slider"] {{ padding-top: 0 !important; padding-bottom: 0 !important; }}
div[data-testid="stSlider"] [data-baseweb="slider"] > div {{ background: #dfeaea !important; height: 10px !important; }}
div[data-testid="stSlider"] div[role="slider"] {{ background-color: {OFFICIAL_TEAL} !important; border: 3px solid white !important; box-shadow: 0 0 0 3px rgba(0,128,128,.25) !important; }}
div[data-testid="stSlider"] div[style*="background"] {{ accent-color: {OFFICIAL_TEAL} !important; }}
.stSlider * {{ accent-color: {OFFICIAL_TEAL} !important; }}
</style>
""", unsafe_allow_html=True)

REQUIRED_CURSOR_COLUMNS = ["ID", "Situation / consigne", "Proposition gauche", "Proposition droite", "Moteur gauche", "Moteur droite", "Position défaut", "Statut", "Version"]

MOTEUR_FALLBACK = {
    "MP1": "Accomplir", "MP2": "Comprendre", "MP3": "Construire", "MP4": "Transmettre", "MP5": "Être utile",
    "MP6": "Influencer", "MP7": "Innover", "MP8": "Coopérer", "MP9": "Progresser", "MP10": "Contribuer",
}

RGPD_TEXT = f"""
### Protection des données personnelles (RGPD)

Cette application Clarté360 fonctionne sans base de données serveur propre à l'application. Aucune donnée n'est enregistrée durablement sur un serveur Clarté360 par l'application.

Le fichier JSON constitue le seul support de conservation de votre travail. Il peut contenir votre identité, votre adresse e-mail, le nom de votre accompagnateur si l'application le prévoit, les dates et heures de connexion, la durée des sessions, vos données saisies dans l'application, commentaires, exemples, cotations, résultats, historique des connexions, code d'accès généré, historique des régénérations, consentement RGPD, version de l'application et informations techniques disponibles.

Le fichier JSON appartient exclusivement au bénéficiaire. Vous choisissez librement de le conserver, de le supprimer ou de le transmettre à votre accompagnateur. Si vous le transmettez à votre accompagnateur, celui-ci l'utilise exclusivement dans le cadre du bilan de compétences ou de l'accompagnement Clarté360.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : {RGPD_TEXT_VERSION}.

### Nature des résultats

Les résultats fournis par les applications Clarté360 constituent des supports d'aide à la réflexion et à l'accompagnement. Ils ne constituent ni un diagnostic psychologique, ni un avis médical, ni une décision d'orientation automatique. Leur interprétation s'inscrit dans un dialogue avec le bénéficiaire et, lorsque cela est prévu, avec un professionnel de l'accompagnement.

### Propriété intellectuelle

Les applications, outils, questionnaires, méthodes, graphiques, rapports et contenus proposés par Clarté360 constituent des créations originales protégées. Toute reproduction, adaptation, diffusion ou réutilisation, totale ou partielle, sans autorisation écrite préalable de Clarté360, est interdite.
"""

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sanitize_filename(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9àâäéèêëîïôöùûüçñ\- ]+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", "_", value)
    return value or "beneficiaire"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_data(show_spinner=False)
def load_data(default_mtime: float):
    curseurs = normalize_columns(pd.read_excel(DEFAULT_XLSX, sheet_name="Curseurs"))
    dims = normalize_columns(pd.read_excel(DEFAULT_XLSX, sheet_name="Dimensions"))
    params = normalize_columns(pd.read_excel(DEFAULT_XLSX, sheet_name="PARAMETRES"))
    return curseurs, dims, params


def validate_curseurs(df: pd.DataFrame) -> list[str]:
    errors = []
    missing = [c for c in REQUIRED_CURSOR_COLUMNS if c not in df.columns]
    if missing:
        return ["Colonnes manquantes : " + ", ".join(missing)]
    ids = df["ID"].astype(str).str.strip()
    if ids.duplicated().any():
        errors.append("Des ID de curseurs sont en doublon.")
    active = df[df["Statut"].astype(str).str.lower().str.strip() == "active"]
    if len(active) != 60:
        errors.append(f"Le questionnaire doit contenir exactement 60 curseurs actifs. Actuellement : {len(active)}.")
    for col in ["Situation / consigne", "Proposition gauche", "Proposition droite", "Moteur gauche", "Moteur droite"]:
        if active[col].astype(str).str.strip().eq("").any():
            errors.append(f"La colonne {col} contient au moins une cellule vide.")
    return errors


def get_active_cursors(df: pd.DataFrame) -> pd.DataFrame:
    active = df[df["Statut"].astype(str).str.lower().str.strip() == "active"].copy()
    active["ID"] = active["ID"].astype(str).str.strip()
    active["Position défaut"] = pd.to_numeric(active["Position défaut"], errors="coerce").fillna(5).astype(int)
    return active


def get_param(params: pd.DataFrame, key: str, default=""):
    if "Paramètre" not in params.columns or "Valeur" not in params.columns:
        return default
    matches = params[params["Paramètre"].astype(str).str.strip() == key]
    if matches.empty:
        return default
    return str(matches.iloc[0]["Valeur"])


def moteur_labels(dims: pd.DataFrame) -> dict:
    if {"Code", "Moteur professionnel"}.issubset(set(dims.columns)):
        return {str(r["Code"]).strip(): str(r["Moteur professionnel"]).strip() for _, r in dims.iterrows()}
    return MOTEUR_FALLBACK.copy()


def generate_code() -> str:
    return f"{random.randint(100000, 999999)}"


def smtp_configured() -> bool:
    try:
        e = st.secrets.get("email", {})
        return all(e.get(k) for k in ["smtp_server", "smtp_port", "smtp_user", "smtp_password", "from_email", "to_email"])
    except Exception:
        return False


def send_email(subject: str, body: str, to_email: str | None = None, attachments: list[tuple[str, bytes, str]] | None = None) -> tuple[bool, str]:
    if not smtp_configured():
        return False, "SMTP non configuré dans les Secrets Streamlit."
    try:
        e = st.secrets["email"]
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = e["from_email"]
        msg["To"] = to_email or e["to_email"]
        msg.set_content(body)
        for filename, content, mime in attachments or []:
            maintype, subtype = mime.split("/", 1)
            msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
        with smtplib.SMTP_SSL(e["smtp_server"], int(e["smtp_port"]), timeout=25) as server:
            server.login(e["smtp_user"], e["smtp_password"])
            server.send_message(msg)
        return True, "Email envoyé."
    except Exception as exc:
        return False, f"Erreur email : {exc}"


def get_session_limit_minutes() -> int:
    try:
        return int(st.secrets.get("security", {}).get("session_limit_minutes", DEFAULT_SESSION_LIMIT_MINUTES))
    except Exception:
        return DEFAULT_SESSION_LIMIT_MINUTES


def init_runtime_session(reason="nouvelle_session"):
    """Crée une session de travail mesurable à partir de l'entrée réelle dans l'app.

    Le temps est comptabilisé par battements réguliers Streamlit et non par simple
    soustraction début/fin. Cela évite de compter plusieurs heures si le navigateur
    est fermé ou si l'ordinateur se met en veille sans repasser proprement par l'app.
    """
    current_id = str(uuid.uuid4())
    now = now_iso()
    st.session_state.current_runtime_session_id = current_id
    st.session_state.session_started_at = now
    st.session_state.session_last_activity = now
    st.session_state.session_last_heartbeat = now
    st.session_state.session_expired = False
    st.session_state.exit_json_ready = False
    history = st.session_state.get("session_history", [])
    history.append({
        "session_uid": current_id,
        "debut": now,
        "validation_code_at": st.session_state.get("code_verified_at", now),
        "derniere_activite": now,
        "dernier_battement": now,
        "fin": None,
        "duree_secondes": 0,
        "duree_active_secondes": 0,
        "motif_fermeture": None,
        "version_application": APP_VERSION,
        "fuseau_horaire": "local_navigateur_non_disponible_streamlit",
        "motif_ouverture": reason,
        "sauvegardes": [],
    })
    st.session_state.session_history = history


def _current_session_record():
    sid = st.session_state.get("current_runtime_session_id")
    if not sid:
        return None
    for sess in st.session_state.get("session_history", []):
        if sess.get("session_uid") == sid:
            return sess
    return None


def update_runtime_activity(event: str = "heartbeat"):
    """Met à jour le temps actif de la session courante.

    Le delta ajouté est plafonné à 30 secondes pour éviter de comptabiliser une
    longue absence liée à une fermeture brutale, une veille, ou une suspension du navigateur.
    """
    sess = _current_session_record()
    if not sess or sess.get("fin"):
        return
    now_dt = datetime.now()
    last_raw = st.session_state.get("session_last_heartbeat") or sess.get("dernier_battement") or sess.get("debut")
    try:
        last_dt = datetime.fromisoformat(last_raw)
    except Exception:
        last_dt = now_dt
    delta = max(0, int((now_dt - last_dt).total_seconds()))
    delta = min(delta, 30)
    current_duration = int(sess.get("duree_active_secondes", sess.get("duree_secondes", 0)) or 0)
    sess["duree_active_secondes"] = current_duration + delta
    sess["duree_secondes"] = sess["duree_active_secondes"]
    sess["derniere_activite"] = now_dt.isoformat(timespec="seconds")
    sess["dernier_battement"] = sess["derniere_activite"]
    sess["dernier_evenement"] = event
    st.session_state.session_last_activity = sess["derniere_activite"]
    st.session_state.session_last_heartbeat = sess["derniere_activite"]


def record_save_event(kind: str):
    update_runtime_activity(kind)
    sess = _current_session_record()
    if not sess:
        return
    saves = sess.get("sauvegardes", [])
    saves.append({"type": kind, "date_heure": now_iso(), "duree_active_secondes": int(sess.get("duree_active_secondes") or 0)})
    sess["sauvegardes"] = saves


def close_runtime_session(reason: str):
    sess = _current_session_record()
    if not sess:
        return
    update_runtime_activity(reason)
    sess = _current_session_record()
    if sess:
        now = now_iso()
        sess["derniere_activite"] = now
        sess["fin"] = now
        sess["motif_fermeture"] = reason


def total_session_seconds() -> int:
    return int(sum(int(s.get("duree_active_secondes", s.get("duree_secondes", 0)) or 0) for s in st.session_state.get("session_history", [])))


def format_duration(seconds: int) -> str:
    """Retourne une duree lisible pour un humain et reutilisable par le support."""
    seconds = max(0, int(seconds or 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d} min {s:02d} s"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


def technical_context() -> dict:
    """Contexte technique transmis au support Clarte360.

    Streamlit ne donne pas directement acces au navigateur, a l'OS ou a la
    resolution sans composant specialise. Les champs sont conserves afin de
    preparer la migration VPS et un futur module de collecte explicite.
    """
    return {
        "application": APP_FULL_NAME,
        "app_version": APP_VERSION,
        "session_id": st.session_state.get("session_id", ""),
        "passation_id": st.session_state.get("passation_id", ""),
        "runtime_session_id": st.session_state.get("current_runtime_session_id", ""),
        "date_heure": now_iso(),
        "temps_session_secondes": int((_current_session_record() or {}).get("duree_active_secondes", 0) or 0),
        "temps_total_secondes": total_session_seconds(),
        "navigateur": "non disponible dans Streamlit sans composant dedie",
        "systeme_exploitation": "non disponible dans Streamlit sans composant dedie",
        "langue": "fr",
        "resolution_ecran": "non disponible dans Streamlit sans composant dedie",
    }


def legal_footer_text(short: bool = False) -> str:
    """Texte institutionnel officiel Clarte360 pour interface et rapports."""
    l = CLARTE360_LEGAL
    if short:
        return f"{l['raison_sociale']} • {l['adresse']} • {l['code_postal_ville']} • {l['telephone']} • {l['email']} • {l['web']}"
    return (
        f"{l['raison_sociale']} – {l['adresse']} – {l['code_postal_ville']} – TEL. : {l['telephone']} – "
        f"EMAIL : {l['email']} – WEB : {l['web']}\n"
        f"RCS : {l['rcs']} – SIRET : {l['siret']} – NAF : {l['naf']} – Id CEE : {l['tva']}"
    )


def check_session_limit():
    if not st.session_state.get("test_started") or st.session_state.get("session_expired"):
        return
    update_runtime_activity()
    limit_seconds = get_session_limit_minutes() * 60
    current = next((s for s in st.session_state.get("session_history", []) if s.get("session_uid") == st.session_state.get("current_runtime_session_id")), None)
    if current and int(current.get("duree_active_secondes", current.get("duree_secondes", 0)) or 0) >= limit_seconds:
        close_runtime_session("expiration_duree_session")
        st.session_state.session_expired = True
        st.rerun()


def timeout_watchdog():
    """Rerun automatique côté Streamlit pour appliquer la limite de session même sans clic utilisateur."""
    if not st.session_state.get("test_started") or st.session_state.get("session_expired"):
        return
    if not hasattr(st, "fragment"):
        return

    @st.fragment(run_every="10s")
    def _watchdog_fragment():
        if st.session_state.get("test_started") and not st.session_state.get("session_expired"):
            check_session_limit()

    _watchdog_fragment()


def start_new_session(active: pd.DataFrame, nom: str, prenom: str, email: str, consultant: str = ""):
    st.session_state.passation_root_id = str(uuid.uuid4())
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.passation_id = f"CL360-MP-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{st.session_state.session_id[:8].upper()}"
    ids = active["ID"].tolist()
    random.shuffle(ids)
    st.session_state.cursor_order = ids
    st.session_state.positions = {}
    st.session_state.current_index = 0
    st.session_state.started_at = now_iso()
    st.session_state.beneficiaire = {"nom": nom.strip(), "prenom": prenom.strip(), "email": email.strip(), "consultant": consultant.strip()}
    st.session_state.test_started = True
    st.session_state.final_email_sent = False
    st.session_state.session_history = []
    init_runtime_session("premiere_connexion")


def restore_from_progress(payload: dict):
    previous_sessions = deepcopy(payload.get("sessions", payload.get("session_history", [])))
    st.session_state.passation_root_id = payload.get("passation_root_id", payload.get("session_id", str(uuid.uuid4())))
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.passation_id = payload.get("passation_id", st.session_state.passation_root_id)
    st.session_state.cursor_order = payload.get("cursor_order_displayed", payload.get("cursor_order", []))
    st.session_state.positions = {str(k): int(v) for k, v in payload.get("positions", {}).items()}
    first_unanswered = None
    for i, cid in enumerate(st.session_state.cursor_order):
        if cid not in st.session_state.positions:
            first_unanswered = i
            break
    st.session_state.current_index = first_unanswered if first_unanswered is not None else len(st.session_state.cursor_order)
    st.session_state.started_at = payload.get("started_at", now_iso())
    st.session_state.beneficiaire = payload.get("beneficiaire", {})
    st.session_state.test_started = True
    st.session_state.final_email_sent = bool(payload.get("final_email_sent", False))
    st.session_state.code_verified = True
    st.session_state.code_verified_at = now_iso()
    st.session_state.rgpd_acceptance = payload.get("rgpd_acceptance", payload.get("rgpd_consent", {}))
    st.session_state.access_history = payload.get("access_history", {})
    st.session_state.session_history = previous_sessions if isinstance(previous_sessions, list) else []
    init_runtime_session("reprise_depuis_json")


def reset_all():
    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)
    st.rerun()


def compute_results(active: pd.DataFrame, dims: pd.DataFrame, positions: dict):
    labels = moteur_labels(dims)
    scores = {code: 0.0 for code in labels.keys()}
    max_scores = {code: 0.0 for code in labels.keys()}
    details = []
    by_id = active.set_index("ID")
    for cid, pos in positions.items():
        if cid not in by_id.index:
            continue
        row = by_id.loc[cid]
        left = str(row["Moteur gauche"]).strip()
        right = str(row["Moteur droite"]).strip()
        pos = int(pos)
        left_pts = (10 - pos) * 10
        right_pts = pos * 10
        if left not in scores:
            scores[left] = 0.0; max_scores[left] = 0.0
        if right not in scores:
            scores[right] = 0.0; max_scores[right] = 0.0
        scores[left] += left_pts
        scores[right] += right_pts
        max_scores[left] += 100
        max_scores[right] += 100
        details.append({"cursor_id": cid, "position": pos, "situation": row["Situation / consigne"], "proposition_gauche": row["Proposition gauche"], "proposition_droite": row["Proposition droite"], "moteur_gauche": left, "moteur_droite": right, "points_gauche": left_pts, "points_droite": right_pts})
    rows = []
    for code, label in labels.items():
        maxv = max_scores.get(code, 0) or 1
        pct = round(scores.get(code, 0) / maxv * 100, 1)
        rows.append({"Code": code, "Moteur": label, "Score": round(scores.get(code, 0), 1), "Score max": round(max_scores.get(code, 0), 1), "Pourcentage": pct, "Lecture": interpretation_level(pct)})
    result = pd.DataFrame(rows).sort_values("Pourcentage", ascending=False)
    return result, {"details": details}


def interpretation_level(pct: float) -> str:
    if pct < 30:
        return "Moteur secondaire"
    if pct < 55:
        return "Moteur présent selon les situations"
    if pct < 75:
        return "Moteur significatif"
    return "Moteur dominant"


def build_payload(active: pd.DataFrame, dims: pd.DataFrame, params: pd.DataFrame, completed=False) -> dict:
    update_runtime_activity()
    scores_df, score_details = compute_results(active, dims, st.session_state.get("positions", {}))
    payload = {
        "outil": get_param(params, "outil_code", "clarte360_moteurs_professionnels"),
        "outil_nom": get_param(params, "outil_nom", APP_FULL_NAME),
        "app_version": APP_VERSION,
        "version_questionnaire": get_param(params, "version_questionnaire", "0.1"),
        "passation_root_id": st.session_state.get("passation_root_id", st.session_state.get("session_id", "")),
        "session_id": st.session_state.get("session_id", ""),
        "passation_id": st.session_state.get("passation_id", ""),
        "beneficiaire": st.session_state.get("beneficiaire", {}),
        "started_at": st.session_state.get("started_at", ""),
        "code_verified_at": st.session_state.get("code_verified_at", ""),
        "completed_at": now_iso() if completed else None,
        "questionnaire_source": DEFAULT_XLSX.name,
        "cursor_order_displayed": st.session_state.get("cursor_order", []),
        "positions": st.session_state.get("positions", {}),
        "scores": scores_df.to_dict(orient="records"),
        "score_details": score_details,
        "sessions": st.session_state.get("session_history", []),
        "temps_total_cumule_secondes": total_session_seconds(),
        "temps_total_cumule_minutes": round(total_session_seconds() / 60, 2),
        "temps_total_cumule_lisible": format_duration(total_session_seconds()),
        "rgpd_acceptance": st.session_state.get("rgpd_acceptance", {}),
        "access_history": st.session_state.get("access_history", {}),
        "notice": "Outil déclaratif d’exploration. Ne constitue pas un test psychométrique ni un diagnostic.",
        "rgpd": "Aucune donnée n’est enregistrée sur un serveur Clarté360. Le JSON appartient exclusivement au bénéficiaire.",
    }
    return payload


def payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def make_filename(prefix="moteurs", ext="json"):
    ben = st.session_state.get("beneficiaire", {})
    nom = sanitize_filename(ben.get("nom", ""))
    prenom = sanitize_filename(ben.get("prenom", ""))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"clarte360_{prefix}_{prenom}_{nom}_{stamp}.{ext}"


def create_bar_chart(scores_df: pd.DataFrame) -> BytesIO:
    fig, ax = plt.subplots(figsize=(8, 5))
    plot_df = scores_df.sort_values("Pourcentage", ascending=True)
    ax.barh(plot_df["Moteur"], plot_df["Pourcentage"])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Score sur 100")
    ax.set_title("Moteurs professionnels déclarés")
    fig.tight_layout()
    bio = BytesIO()
    fig.savefig(bio, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)
    return bio


def create_radar_chart(scores_df: pd.DataFrame) -> BytesIO:
    import numpy as np
    df = scores_df.sort_values("Code")
    labels = df["Moteur"].tolist()
    values = df["Pourcentage"].tolist()
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, values, linewidth=2)
    ax.fill(angles, values, alpha=0.15)
    ax.set_ylim(0, 100)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title("Profil des moteurs", y=1.08)
    fig.tight_layout()
    bio = BytesIO()
    fig.savefig(bio, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)
    return bio


def draw_pdf_footer(canvas, doc):
    """Dessine le pied de page institutionnel Clarte360 sur chaque page PDF."""
    canvas.saveState()
    width, height = doc.pagesize
    canvas.setStrokeColor(colors.HexColor("#CCCCCC"))
    canvas.setLineWidth(0.3)
    canvas.line(1.5 * cm, 1.05 * cm, width - 1.5 * cm, 1.05 * cm)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.setFont("Helvetica", 6.8)
    text = legal_footer_text(short=True)
    canvas.drawCentredString(width / 2, 0.68 * cm, text)
    canvas.drawCentredString(width / 2, 0.42 * cm, f"SIRET {CLARTE360_LEGAL['siret']} • RCS {CLARTE360_LEGAL['rcs']} • TVA {CLARTE360_LEGAL['tva']}")
    canvas.restoreState()


def create_pdf(scores_df: pd.DataFrame, payload: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.2*cm, bottomMargin=1.8*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleClarte", parent=styles["Title"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=18, spaceAfter=10)
    h_style = ParagraphStyle("HClarte", parent=styles["Heading2"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=13, spaceBefore=8, spaceAfter=6)
    normal = styles["BodyText"]
    story = []
    if LOGO_PATH.exists():
        story.append(Image(str(LOGO_PATH), width=1.6*cm, height=1.6*cm))
    story.append(Paragraph(APP_FULL_NAME, title_style))
    ben = payload.get("beneficiaire", {})
    story.append(Paragraph(f"Bénéficiaire : <b>{ben.get('prenom','')} {ben.get('nom','')}</b>", normal))
    story.append(Paragraph(f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal))
    story.append(Paragraph(f"Identifiant de passation : {payload.get('passation_id','')}", normal))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Précaution de lecture", h_style))
    story.append(Paragraph("Cet outil explore des sources d’énergie professionnelle déclarées. Il ne constitue ni un test psychométrique, ni un diagnostic. Les résultats servent de support d’échange avec le consultant.", normal))
    story.append(Paragraph("Résultats", h_style))
    data = [["Moteur", "Score", "Lecture"]] + [[r["Moteur"], f"{r['Pourcentage']:.1f} %", r["Lecture"]] for _, r in scores_df.iterrows()]
    table = Table(data, colWidths=[7*cm, 3*cm, 6*cm])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(OFFICIAL_TEAL)), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#CCCCCC")), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    story.append(table)
    story.append(Spacer(1, 0.3*cm))
    story.append(Image(create_bar_chart(scores_df), width=16*cm, height=9*cm))
    story.append(Spacer(1, 0.2*cm))
    story.append(Image(create_radar_chart(scores_df), width=13*cm, height=13*cm))
    top = scores_df.head(3)
    story.append(Paragraph("Première lecture", h_style))
    top_txt = ", ".join([f"{r['Moteur']} ({r['Pourcentage']:.0f} %)" for _, r in top.iterrows()])
    story.append(Paragraph(f"Les réponses font apparaître prioritairement les moteurs suivants : <b>{top_txt}</b>. Cette lecture doit être discutée et contextualisée pendant l’entretien.", normal))
    story.append(Paragraph("Confidentialité", h_style))
    story.append(Paragraph("Le fichier JSON appartient exclusivement au bénéficiaire. Il peut être conservé, supprimé ou transmis à l'accompagnateur dans le cadre de l'accompagnement.", normal))
    doc.build(story, onFirstPage=draw_pdf_footer, onLaterPages=draw_pdf_footer)
    buffer.seek(0)
    return buffer.read()


def speak_button(text: str, key: str):
    escaped = json.dumps(text)
    if st.button("🔊 Écouter", key=key):
        components.html(f"""
        <script>
        const text = {escaped};
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'fr-FR';
        u.rate = 0.95;
        window.speechSynthesis.speak(u);
        </script>
        """, height=0)
    if st.button("⏹ Arrêter", key=key+"_stop"):
        components.html("<script>window.speechSynthesis.cancel();</script>", height=0)


def display_header():
    c1, c2 = st.columns([1, 5])
    with c1:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=80)
    with c2:
        st.markdown(f"# <span class='clarte-title-accent'>{APP_FULL_NAME}</span>", unsafe_allow_html=True)
        st.caption("Outil propriétaire d’exploration des sources d’énergie professionnelle")


def rgpd_page():
    display_header()
    st.subheader("Informations légales et protection des données")

    tab_rgpd, tab_mentions, tab_contact = st.tabs(["Protection des données", "Mentions légales", "Nous contacter"])

    with tab_rgpd:
        st.markdown(RGPD_TEXT)
        st.info("Le consentement RGPD est demandé avant la génération du code d'accès et avant toute nouvelle passation.")

    with tab_mentions:
        l = CLARTE360_LEGAL
        st.markdown(f"""
        ### {l['raison_sociale']} {l['forme']}

        **Adresse :** {l['adresse']} – {l['code_postal_ville']}  
        **Téléphone :** {l['telephone']}  
        **E-mail :** {l['email']}  
        **Site internet :** {l['web']}  

        **RCS :** {l['rcs']}  
        **SIRET :** {l['siret']}  
        **Code NAF :** {l['naf']}  
        **TVA intracommunautaire :** {l['tva']}
        """)
        st.markdown("""
        ### Propriété intellectuelle
        Les applications, outils, questionnaires, méthodes, graphiques, rapports et contenus proposés par Clarté360 constituent des créations originales protégées. Toute reproduction, adaptation, diffusion ou réutilisation, totale ou partielle, sans autorisation écrite préalable de Clarté360, est interdite.

        ### Responsabilité
        Les résultats proposés constituent des supports de réflexion et d'échange. Ils ne remplacent pas un accompagnement professionnel lorsque celui-ci est prévu et ne constituent ni un diagnostic psychologique, ni un avis médical.
        """)

    with tab_contact:
        contact_form()


def contact_form():
    """Formulaire de contact support commun au socle Clarte360."""
    ben = st.session_state.get("beneficiaire") or st.session_state.get("pending_beneficiaire") or {}
    st.markdown("""
    ### Contacter Clarté360
    Une question, une suggestion ou un problème technique ?  
    Clarté360 vous répondra par e-mail ou, si vous laissez un numéro de téléphone, par téléphone lorsque cela facilite le traitement de votre demande.
    """)
    with st.form("contact_clarte360_form"):
        col1, col2 = st.columns(2)
        with col1:
            prenom = st.text_input("Prénom *", value=ben.get("prenom", ""))
        with col2:
            nom = st.text_input("Nom *", value=ben.get("nom", ""))
        email = st.text_input("Adresse e-mail *", value=ben.get("email", ""))
        telephone = st.text_input("Téléphone (facultatif, si vous souhaitez pouvoir être rappelé)")
        objet = st.text_input("Objet *", value=f"Demande depuis {APP_FULL_NAME}")
        message = st.text_area("Message *", height=160)
        consent = st.checkbox(
            "J'accepte que Clarté360 utilise les informations transmises uniquement pour traiter ma demande. Si je renseigne un numéro de téléphone, j'accepte de pouvoir être contacté par téléphone lorsque cela est utile pour résoudre ma demande."
        )
        submitted = st.form_submit_button("📩 Envoyer mon message", type="primary")
    if submitted:
        if not prenom.strip() or not nom.strip() or not email.strip() or "@" not in email or not objet.strip() or not message.strip():
            st.error("Merci de renseigner les champs obligatoires : prénom, nom, e-mail, objet et message.")
            return
        if not consent:
            st.error("Le consentement est nécessaire pour transmettre votre demande à Clarté360.")
            return
        tech = technical_context()
        body = (
            "Demande envoyée depuis une application Clarté360.\n\n"
            f"Application : {APP_FULL_NAME}\n"
            f"Version : {APP_VERSION}\n"
            f"Prénom : {prenom.strip()}\n"
            f"Nom : {nom.strip()}\n"
            f"Email : {email.strip()}\n"
            f"Téléphone : {telephone.strip() or 'non renseigné'}\n"
            f"Objet : {objet.strip()}\n\n"
            "Message :\n"
            f"{message.strip()}\n\n"
            "Consentement support : accepté.\n\n"
            "Informations techniques :\n"
            + json.dumps(tech, ensure_ascii=False, indent=2)
        )
        ok, msg = send_email(f"Clarté360 - Support - {APP_NAME}", body, to_email=FINAL_EMAIL_TO)
        if ok:
            st.success("Votre message a été transmis à Clarté360.")
        else:
            st.error("Le message n'a pas pu être envoyé automatiquement : " + msg)



def welcome_screen():
    display_header()
    st.markdown(f"### Bienvenue dans l'application Clarté360 – {APP_NAME}")
    st.markdown("Avez-vous conservé le fichier JSON de votre dernière utilisation de cette application ?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Oui → Importer mon fichier JSON", type="primary", use_container_width=True):
            st.session_state.welcome_choice = "import"
            st.rerun()
    with c2:
        if st.button("Non → Commencer une nouvelle session", use_container_width=True):
            st.session_state.welcome_choice = "new"
            st.rerun()


def import_json_screen():
    display_header()
    st.subheader("Reprise d'une session")
    st.markdown("Importez le JSON conservé lors de votre dernière utilisation. Une nouvelle session de connexion sera créée et le compteur de temps de cette nouvelle session repartira à zéro.")
    up = st.file_uploader("Importer mon fichier JSON", type=["json"])
    if up is not None:
        try:
            payload = json.load(up)
            restore_from_progress(payload)
            st.success("JSON chargé. Votre progression a été reprise.")
            st.rerun()
        except Exception as exc:
            st.error(f"JSON non valide : {exc}")
    if st.button("Retour à l'accueil"):
        st.session_state.pop("welcome_choice", None)
        st.rerun()


def prepare_sidebar_json(active, dims, params, reason: str, filename_prefix: str, close_session: bool = False):
    if close_session:
        close_runtime_session(reason)
        st.session_state.exit_mode = "quit"
    else:
        record_save_event(reason)
        st.session_state.exit_mode = "save"
    payload = build_payload(active, dims, params, completed=False)
    st.session_state.exit_json_bytes = payload_bytes(payload)
    st.session_state.exit_json_filename = make_filename(filename_prefix, "json")
    st.session_state.exit_json_ready = True


def sidebar_progress(active, dims, params):
    st.sidebar.markdown("### Session")
    if st.session_state.get("test_started"):
        update_runtime_activity("affichage_sidebar")
        st.sidebar.markdown("Votre progression est enregistrée dans votre fichier JSON.")
        if st.sidebar.button("💾 Préparer mon JSON pour reprendre plus tard", use_container_width=True):
            prepare_sidebar_json(active, dims, params, "sauvegarde_manuelle_reprise", "moteurs_sauvegarde", close_session=False)
            st.rerun()
        if st.sidebar.button("🚪 Quitter et télécharger mon JSON", type="primary", use_container_width=True):
            prepare_sidebar_json(active, dims, params, "sortie_utilisateur_par_bouton", "moteurs_sortie", close_session=True)
            st.rerun()
        if st.session_state.get("exit_json_ready"):
            st.sidebar.download_button(
                "⬇️ Télécharger le JSON préparé",
                data=st.session_state.get("exit_json_bytes", b""),
                file_name=st.session_state.get("exit_json_filename", make_filename("moteurs_sortie", "json")),
                mime="application/json",
                use_container_width=True,
                on_click=mark_json_downloaded,
            )
            st.sidebar.caption("Conservez ce JSON : il est nécessaire pour reprendre votre travail et il contient le temps réellement enregistré.")
    st.sidebar.markdown("---")
    if st.sidebar.button("RGPD et mentions légales", use_container_width=True):
        st.session_state.show_rgpd_page = True
        st.rerun()
    st.sidebar.caption("Clarté360 · contact@clarte360.com")


def identification_screen(active, dims, params):
    display_header()
    st.markdown("""
    <div class="objectif-box">
    <h3>Objectif de l’outil</h3>
    <p>Cet outil aide à explorer ce qui donne durablement de l’énergie dans l’activité professionnelle. Il ne mesure pas une personnalité et ne donne pas un diagnostic. Il sert de support à l’échange avec votre consultant Clarté360.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    <div class="clarte-box">
    <b>Comment répondre ?</b><br>
    Pour chaque situation, vous verrez deux propositions positives. Positionnez le curseur au plus près de la proposition qui vous ressemble le plus aujourd'hui. Si les deux propositions vous correspondent autant l'une que l'autre, laissez-le naturellement au milieu. Aucune note n’est visible pendant la passation.
    </div>
    """, unsafe_allow_html=True)
    with st.expander("Voir les moteurs explorés"):
        for _, r in dims.iterrows():
            st.markdown(f"**{r.get('Moteur professionnel','')}** — {r.get('Définition bénéficiaire','')}")
    with st.expander("Protection des données personnelles (RGPD)", expanded=True):
        st.markdown(RGPD_TEXT)
    st.subheader("Identification")
    with st.form("identification"):
        prenom = st.text_input("Prénom *")
        nom = st.text_input("Nom *")
        email = st.text_input("Adresse email *")
        consultant = st.text_input("Consultant / accompagnateur", value="")
        consent = st.checkbox("J'ai lu et j'accepte les conditions RGPD de cette application Clarté360.")
        submitted = st.form_submit_button("Recevoir mon code d’accès", type="primary")
    if submitted:
        if not prenom.strip() or not nom.strip() or not email.strip() or "@" not in email:
            st.error("Merci de renseigner prénom, nom et une adresse email valide.")
        elif not consent:
            st.error("Le consentement RGPD est obligatoire avant toute utilisation.")
        else:
            st.session_state.rgpd_acceptance = {"consentement": True, "date": datetime.now().strftime("%Y-%m-%d"), "heure": datetime.now().strftime("%H:%M:%S"), "version_texte": RGPD_TEXT_VERSION}
            st.session_state.pending_beneficiaire = {"prenom": prenom.strip(), "nom": nom.strip(), "email": email.strip(), "consultant": consultant.strip()}
            issue_access_code(email.strip(), prenom.strip(), is_regeneration=False)
    if st.session_state.get("access_code"):
        st.subheader("Code d’accès")
        code_in = st.text_input("Saisissez le code reçu par email", max_chars=6)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Valider le code et commencer", type="primary"):
                exp = datetime.fromisoformat(st.session_state.get("code_expires_at"))
                if datetime.now() > exp:
                    st.error("Le code a expiré. Merci de demander un nouveau code.")
                elif code_in.strip() == st.session_state.get("access_code"):
                    b = st.session_state.pending_beneficiaire
                    validation_now = now_iso()
                    st.session_state.code_verified_at = validation_now
                    history = st.session_state.get("access_history", {})
                    history["validation_code"] = {"date_heure": validation_now, "code_valide": True, "version_application": APP_VERSION}
                    st.session_state.access_history = history
                    start_new_session(active, b["nom"], b["prenom"], b["email"], b.get("consultant", ""))
                    st.session_state.code_verified = True
                    st.rerun()
                else:
                    st.error("Code incorrect.")
        with c2:
            if st.button("Je n'ai pas reçu mon code → Générer un nouveau code"):
                b = st.session_state.pending_beneficiaire
                issue_access_code(b["email"], b["prenom"], is_regeneration=True)


def issue_access_code(email: str, prenom: str, is_regeneration: bool):
    code = generate_code()
    minutes = int(st.secrets.get("security", {}).get("code_expiration_minutes", 15)) if "security" in st.secrets else 15
    st.session_state.access_code = code
    st.session_state.code_expires_at = (datetime.now() + timedelta(minutes=minutes)).isoformat(timespec="seconds")
    history = st.session_state.get("access_history", {"generations": [], "nombre_regenerations": 0})
    if is_regeneration:
        history["nombre_regenerations"] = int(history.get("nombre_regenerations", 0)) + 1
    history["generations"].append({"date": datetime.now().strftime("%Y-%m-%d"), "heure": datetime.now().strftime("%H:%M:%S"), "generation": "regeneration" if is_regeneration else "initiale", "envoi": "email", "version_application": APP_VERSION})
    st.session_state.access_history = history
    subject_user = f"Votre code d'accès {APP_FULL_NAME}"
    body_user = f"Bonjour {prenom},\n\nVotre code d'accès au questionnaire {APP_FULL_NAME} est : {code}\n\nCe code est valable {minutes} minutes.\n\nRappel RGPD : aucune donnée n'est enregistrée durablement sur un serveur Clarté360 par l'application. Le fichier JSON appartient exclusivement au bénéficiaire. Les données sont utilisées uniquement dans le cadre de l'accompagnement ou du bilan de compétences, avec votre consentement.\n\nClarté360"
    pending = st.session_state.get("pending_beneficiaire", {}) or {}
    subject_admin = f"Clarté360 - Nouveau code d'accès {APP_NAME}"
    body_admin = (
        f"Une personne vient de demander un code d'accès pour réaliser l'outil {APP_FULL_NAME}.\n\n"
        f"Prénom : {pending.get('prenom', prenom)}\n"
        f"Nom : {pending.get('nom', '')}\n"
        f"Email : {email}\n"
        f"Consultant / accompagnateur : {pending.get('consultant', '')}\n"
        f"Code généré : {code}\n"
        f"Type de génération : {'régénération' if is_regeneration else 'initiale'}\n"
        f"Date/heure : {datetime.now().isoformat(timespec='seconds')}\n"
        f"Version application : {APP_VERSION}\n\n"
        "Consentement RGPD : le bénéficiaire a confirmé avoir lu les informations relatives aux données conservées dans le JSON et a consenti à leur utilisation dans le cadre exclusif de son accompagnement.\n"
        "Rappel : aucune donnée n'est conservée durablement sur un serveur Clarté360 par l'application ; le JSON reste sous le contrôle du bénéficiaire.\n"
    )
    ok_admin, msg_admin = send_email(subject_admin, body_admin)

    ok_user, msg_user = send_email(subject_user, body_user, to_email=email)
    history["generations"][-1]["envoi_beneficiaire"] = "ok" if ok_user else msg_user
    history["generations"][-1]["notification_admin"] = "ok" if ok_admin else msg_admin
    st.session_state.access_history = history
    if ok_user:
        st.success("Un code d’accès vient de vous être envoyé par email.")
        if not ok_admin:
            st.warning("Le code a été envoyé au bénéficiaire, mais la notification à contact@clarte360.com n'a pas abouti : " + msg_admin)
    else:
        st.error("Impossible d’envoyer le code : " + msg_user)
        st.info("Vérifiez les Secrets Streamlit / SMTP OVH.")


def questionnaire_screen(active, dims, params):
    display_header()
    total = len(st.session_state.cursor_order)
    idx = st.session_state.current_index
    if idx >= total:
        results_screen(active, dims, params)
        return
    cid = st.session_state.cursor_order[idx]
    row = active.set_index("ID").loc[cid]
    st.progress(idx / total)
    st.markdown(f"<div class='question-title'>Question {idx + 1} / {total}</div>", unsafe_allow_html=True)
    situation = str(row["Situation / consigne"])
    left = str(row["Proposition gauche"])
    right = str(row["Proposition droite"])
    st.markdown(f"<div class='clarte-card'><h3>{situation}</h3></div>", unsafe_allow_html=True)
    speak_text = f"Question {idx+1} sur {total}. {situation}. Proposition à gauche : {left}. Proposition à droite : {right}. Positionnez le curseur au plus près de la proposition qui vous ressemble le plus aujourd'hui. Si les deux propositions vous correspondent autant l'une que l'autre, laissez-le naturellement au milieu."
    speak_button(speak_text, f"speak_{cid}")
    st.markdown("<div class='slider-instruction'>Positionnez le curseur au plus près de la proposition qui vous ressemble le plus aujourd'hui. Si les deux propositions vous correspondent autant l'une que l'autre, laissez-le naturellement au milieu.</div>", unsafe_allow_html=True)
    default_pos = int(st.session_state.positions.get(cid, int(row.get("Position défaut", 5))))
    col1, col_slider, col2 = st.columns([3.2, 4.8, 3.2], vertical_alignment="center")
    with col1:
        st.markdown(f"<div class='slider-card-left'><b>{left}</b></div>", unsafe_allow_html=True)
    with col_slider:
        st.markdown("<div class='connector-label'>Votre position</div>", unsafe_allow_html=True)
        pos = st.slider("Positionnement", min_value=0, max_value=10, value=default_pos, step=1, key=f"slider_{cid}", label_visibility="collapsed")
    with col2:
        st.markdown(f"<div class='slider-card-right'><b>{right}</b></div>", unsafe_allow_html=True)
    if st.button("Valider et passer à la suite", type="primary", use_container_width=True):
        st.session_state.positions[cid] = int(pos)
        st.session_state.current_index += 1
        record_save_event("validation_question")
        st.session_state.exit_json_ready = False
        st.session_state.json_downloaded = False
        st.rerun()


def results_screen(active, dims, params):
    if not st.session_state.get("result_session_closed"):
        close_runtime_session("questionnaire_termine")
        st.session_state.result_session_closed = True
    payload = build_payload(active, dims, params, completed=True)
    scores_df = pd.DataFrame(payload["scores"])
    st.progress(1.0)
    st.success("Questionnaire terminé.")
    st.subheader("Première lecture de vos moteurs professionnels")
    st.caption("Ces résultats sont déclaratifs et servent de support d’échange avec votre consultant Clarté360.")
    st.dataframe(scores_df[["Moteur", "Pourcentage", "Lecture"]], hide_index=True, use_container_width=True)
    st.image(create_bar_chart(scores_df), caption="Scores par moteur")
    st.image(create_radar_chart(scores_df), caption="Radar des moteurs")
    top = scores_df.sort_values("Pourcentage", ascending=False).head(3)
    st.markdown("### Synthèse courte")
    st.markdown("Vos réponses mettent principalement en avant : " + ", ".join([f"**{r['Moteur']}** ({r['Pourcentage']:.0f} %)" for _, r in top.iterrows()]) + ".")
    json_data = payload_bytes(payload)
    pdf_data = create_pdf(scores_df, payload)
    json_filename = make_filename("moteurs_professionnels", "json")
    pdf_filename = make_filename("rapport_moteurs_professionnels", "pdf")
    if not st.session_state.get("final_email_sent"):
        ok, msg = send_email(subject=f"JSON final – Moteurs professionnels – {payload.get('passation_id')}", body=f"Questionnaire terminé pour {payload['beneficiaire'].get('prenom','')} {payload['beneficiaire'].get('nom','')}.\nID : {payload.get('passation_id')}", attachments=[(json_filename, json_data, "application/json")])
        if ok:
            st.session_state.final_email_sent = True
            st.info("Le JSON final a été transmis à Clarté360.")
        else:
            st.warning("Le JSON final n'a pas pu être envoyé automatiquement : " + msg)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Télécharger mon JSON", data=json_data, file_name=json_filename, mime="application/json", on_click=mark_json_downloaded)
    with c2:
        st.download_button("Télécharger mon rapport PDF", data=pdf_data, file_name=pdf_filename, mime="application/pdf")


def exit_prepared_screen():
    display_header()
    st.success("Votre JSON de sortie est prêt à être téléchargé.")
    st.markdown("Téléchargez le fichier dans la colonne de gauche. Il permettra de reprendre l'application et de conserver correctement l'historique de temps.")
    st.info("Après téléchargement, vous pouvez fermer l'onglet du navigateur.")


def expired_screen(active, dims, params):
    display_header()
    st.warning("La durée maximale de cette session est atteinte. Votre progression a été sauvegardée dans le JSON ci-dessous.")
    st.markdown("Téléchargez ce JSON : il permettra de reprendre le travail lors de la prochaine connexion. Une nouvelle session sera créée et le compteur de temps repartira à zéro, tout en conservant l'historique.")
    if not st.session_state.get("expiration_json_saved"):
        record_save_event("sauvegarde_automatique_expiration")
        st.session_state.expiration_json_saved = True
    payload = build_payload(active, dims, params, completed=False)
    st.download_button("Télécharger mon JSON de reprise", data=payload_bytes(payload), file_name=make_filename("moteurs_reprise_session_expiree", "json"), mime="application/json", type="primary", on_click=mark_json_downloaded)


def mark_json_downloaded():
    st.session_state.json_downloaded = True


def install_beforeunload_warning():
    """Alerte navigateur informative si l'utilisateur ferme sans passer par le JSON.

    Les navigateurs ne permettent pas de bloquer définitivement la croix de fermeture.
    Cette alerte est donc une sécurité complémentaire, pas une garantie absolue.
    """
    if st.session_state.get("test_started") and not st.session_state.get("json_downloaded"):
        components.html(
            """
            <script>
            window.parent.onbeforeunload = function (e) {
                const message = "Avant de quitter, utilisez le bouton Clarté360 : Quitter et préparer mon JSON.";
                e.preventDefault();
                e.returnValue = message;
                return message;
            };
            </script>
            """,
            height=0,
        )


def main():
    if not DEFAULT_XLSX.exists():
        st.error("Fichier questionnaire introuvable dans data/.")
        st.stop()
    curseurs, dims, params = load_data(DEFAULT_XLSX.stat().st_mtime)
    errors = validate_curseurs(curseurs)
    if errors:
        st.error("Erreur dans le fichier Excel du questionnaire :")
        for e in errors:
            st.write("- " + e)
        st.stop()
    active = get_active_cursors(curseurs)
    sidebar_progress(active, dims, params)
    install_beforeunload_warning()
    st.sidebar.caption(f"App v{APP_VERSION} · Questionnaire {get_param(params, 'version_questionnaire', '0.1')}")
    if st.sidebar.button("Réinitialiser la session"):
        reset_all()
    if st.session_state.get("show_rgpd_page"):
        rgpd_page()
        if st.button("Retour"):
            st.session_state.show_rgpd_page = False
            st.rerun()
        return
    if st.session_state.get("session_expired"):
        expired_screen(active, dims, params)
        return
    if st.session_state.get("test_started"):
        if st.session_state.get("exit_json_ready") and st.session_state.get("exit_mode") == "quit":
            exit_prepared_screen()
            return
        timeout_watchdog()
        check_session_limit()
        questionnaire_screen(active, dims, params)
        return
    choice = st.session_state.get("welcome_choice")
    if choice == "import":
        import_json_screen()
    elif choice == "new":
        identification_screen(active, dims, params)
    else:
        welcome_screen()


if __name__ == "__main__":
    main()
