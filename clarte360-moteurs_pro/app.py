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

from validation import (decode_progress_bytes, validate_code, validate_email, validate_free_text, validate_name, validate_phone, validate_position, validate_short_text)
from work_guard import fingerprint_guard_state

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_VERSION = "1.8.3-rapport-moteurs-enrichi-vps-hub-ready-garde-fou"
SOCLE_CLARTE360_VERSION = "1.8"
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


# Référentiel éditorial du rapport bénéficiaire — V1.8.3.
# Ces contenus ne modifient ni le questionnaire, ni les calculs, ni le fichier Excel source.
MOTEUR_REPORT_CONTENT = {
    "MP1": {
        "definition": "Accomplir, c’est être stimulé par le fait d’aboutir, d’obtenir un résultat concret et de pouvoir constater le chemin parcouru. Ce moteur trouve son énergie dans la réalisation : terminer ce qui a été entrepris, atteindre un objectif, relever un défi ou transformer un effort en résultat visible. Il ne signifie pas nécessairement rechercher la compétition ou la reconnaissance ; ce qui compte avant tout est la satisfaction de faire, d’avancer et d’arriver au bout.",
        "basse": "La recherche de résultats ou d’objectifs à atteindre n’est pas une source majeure de motivation. La personne peut préférer accorder davantage d’importance au chemin parcouru, à la qualité de l’expérience ou à d’autres dimensions du travail.",
        "moyenne": "Atteindre des objectifs et constater des résultats contribue à la motivation, sans être indispensable en permanence. La personne apprécie de voir son travail avancer et aboutir, tout en pouvant trouver son énergie dans d’autres sources.",
        "haute": "La réalisation et l’atteinte d’objectifs constituent une source importante d’énergie. La personne est particulièrement stimulée lorsqu’elle peut avancer vers un résultat identifiable, mesurer sa progression et éprouver la satisfaction d’avoir mené quelque chose à son terme.",
    },
    "MP2": {
        "definition": "Comprendre, c’est être stimulé par la découverte du pourquoi et du comment. Ce moteur nourrit l’envie d’analyser une situation, de rechercher des informations, de faire des liens, d’approfondir un sujet et de donner du sens à ce qui paraît complexe. Comprendre ne signifie pas nécessairement être très intellectuel ou théorique : il s’agit surtout du plaisir et du besoin de ne pas rester à la surface des choses.",
        "basse": "Approfondir, analyser ou rechercher les mécanismes d’une situation n’est pas une source essentielle de motivation. La personne peut être davantage attirée par l’action, l’expérience ou le résultat directement observable.",
        "moyenne": "Comprendre les situations et disposer d’explications suffisantes contribue au confort et à l’efficacité. La personne apprécie d’approfondir certains sujets lorsque cela lui paraît utile ou intéressant.",
        "haute": "Explorer, analyser et comprendre en profondeur constitue une véritable source d’énergie. La personne aime rechercher les causes, établir des liens, apprendre et disposer d’une compréhension solide avant ou pendant l’action.",
    },
    "MP3": {
        "definition": "Construire, c’est être motivé par le fait de donner une forme concrète à une idée, un projet ou une organisation. Ce moteur s’exprime dans le plaisir de partir d’éléments parfois dispersés pour créer quelque chose de cohérent, structuré et utilisable. Il peut concerner aussi bien un projet, une activité, une méthode, une équipe ou une organisation. Construire ne signifie donc pas seulement créer : c’est aussi assembler, organiser, structurer et faire exister durablement.",
        "basse": "La construction ou la structuration de projets n’est pas une source prioritaire d’énergie. La personne peut préférer intervenir dans un cadre déjà établi ou contribuer à certaines étapes plutôt que bâtir l’ensemble.",
        "moyenne": "Participer à la construction d’un projet ou structurer une activité peut être motivant lorsque le contexte s’y prête. La personne apprécie de contribuer à donner forme aux choses sans nécessairement avoir besoin d’être constamment dans cette dynamique.",
        "haute": "Transformer une idée en réalisation structurée constitue une forte source de motivation. La personne aime bâtir, organiser, assembler les éléments et voir progressivement émerger quelque chose de cohérent et de concret.",
    },
    "MP4": {
        "definition": "Transmettre, c’est trouver de l’énergie dans le fait de faire passer à d’autres ce que l’on sait, ce que l’on a compris ou ce que l’on a appris par l’expérience. Cela peut prendre la forme d’expliquer, former, montrer, partager une méthode, accompagner un apprentissage ou rendre une connaissance accessible. Ce moteur ne suppose pas d’être enseignant ou formateur : il traduit avant tout la satisfaction de voir quelque chose que l’on possède devenir utile à quelqu’un d’autre.",
        "basse": "Partager ses connaissances ou aider d’autres personnes à apprendre n’est pas une source majeure de motivation. La personne peut préférer mobiliser directement son expertise dans ses propres activités.",
        "moyenne": "Transmettre est apprécié dans certaines circonstances, notamment lorsque l’expérience ou l’expertise acquise peut être utile. Cela participe à la satisfaction professionnelle sans constituer nécessairement un besoin permanent.",
        "haute": "Faire comprendre, partager son expérience et favoriser l’apprentissage d’autrui constitue une source importante d’énergie. La personne peut éprouver une réelle satisfaction à constater que ce qu’elle transmet permet à quelqu’un d’autre de progresser ou de devenir plus autonome.",
    },
    "MP5": {
        "definition": "Être utile, c’est être stimulé par la perception que son action répond réellement à un besoin. La motivation vient du fait de servir à quelque chose, de faciliter une situation, d’apporter une solution ou d’aider concrètement une personne, une équipe ou une organisation. Ce moteur ne signifie pas nécessairement se dévouer aux autres : l’utilité peut être technique, organisationnelle, économique, humaine ou sociale. L’essentiel est de pouvoir percevoir à quoi et à qui son travail sert.",
        "basse": "La perception immédiate de l’utilité de son travail n’est pas indispensable pour être motivé. D’autres dimensions de l’activité peuvent procurer davantage de satisfaction.",
        "moyenne": "Savoir que son travail est utile renforce la motivation, particulièrement lorsque l’impact peut être identifié. Cette dimension compte sans devoir être présente dans toutes les activités.",
        "haute": "Percevoir concrètement l’utilité de son action constitue une source essentielle de motivation. La personne a particulièrement besoin de sentir que ce qu’elle fait répond à un besoin réel et apporte quelque chose à quelqu’un ou à une organisation.",
    },
    "MP6": {
        "definition": "Influencer, c’est être stimulé par la possibilité de faire évoluer une décision, une orientation, une idée ou une manière d’agir. Cela peut passer par l’argumentation, la conviction, la négociation, la mobilisation ou la capacité à entraîner d’autres personnes autour d’une proposition. Influencer ne signifie ni manipuler ni dominer : ce moteur traduit surtout l’envie de peser sur ce qui se décide et de contribuer activement à l’orientation des choses, plutôt que de rester simple spectateur.",
        "basse": "Peser sur les décisions ou chercher à convaincre n’est pas une source importante de motivation. La personne peut parfaitement préférer contribuer sans avoir besoin d’orienter les choix des autres.",
        "moyenne": "Pouvoir faire entendre son point de vue et participer aux décisions est appréciable, particulièrement sur les sujets jugés importants. L’influence est recherchée lorsqu’elle paraît utile plutôt que comme une finalité en soi.",
        "haute": "Participer activement aux orientations, convaincre et faire évoluer les décisions constitue une source importante d’énergie. La personne apprécie particulièrement les situations dans lesquelles ses idées peuvent avoir du poids et produire un effet sur les choix ou les actions.",
    },
    "MP7": {
        "definition": "Innover, c’est être stimulé par la possibilité de faire autrement, imaginer de nouvelles solutions et sortir des réponses déjà établies. Ce moteur peut s’exprimer par la créativité, l’expérimentation, l’amélioration d’un fonctionnement ou l’invention de nouvelles façons de faire. Il ne signifie pas rechercher systématiquement la nouveauté : il traduit surtout le plaisir de disposer d’un espace permettant d’explorer, d’essayer et de transformer l’existant.",
        "basse": "La nouveauté et l’expérimentation ne sont pas des sources essentielles de motivation. La personne peut préférer s’appuyer sur des méthodes éprouvées et optimiser ce qui fonctionne déjà.",
        "moyenne": "La nouveauté est stimulante lorsqu’elle répond à un besoin ou apporte une amélioration réelle. La personne peut apprécier l’innovation tout en conservant des repères et des méthodes déjà éprouvées.",
        "haute": "Imaginer, expérimenter et inventer de nouvelles manières de faire constitue une forte source d’énergie. La personne apprécie particulièrement les environnements laissant de la place aux idées nouvelles et à la remise en question constructive de l’existant.",
    },
    "MP8": {
        "definition": "Coopérer, c’est trouver de l’énergie dans le fait de faire avec les autres plutôt que simplement à côté d’eux. Ce moteur concerne le partage, l’entraide, la complémentarité, la circulation des idées et la construction collective. Il ne signifie pas nécessairement être très sociable ni rechercher constamment le contact : il traduit surtout la satisfaction de constater que la contribution de plusieurs personnes permet d’aller plus loin ou de faire mieux ensemble.",
        "basse": "Le travail collectif n’est pas indispensable à la motivation. La personne peut apprécier une forte autonomie et trouver davantage d’énergie lorsqu’elle dispose de son propre espace d’action.",
        "moyenne": "La coopération est appréciée lorsqu’elle facilite le travail ou enrichit le résultat. La personne peut alterner efficacement entre activités autonomes et travail collectif.",
        "haute": "Échanger, partager les responsabilités et construire avec d’autres constitue une source importante d’énergie. La personne apprécie particulièrement les situations où les compétences se complètent et où le résultat naît véritablement d’une dynamique collective.",
    },
    "MP9": {
        "definition": "Progresser, c’est être stimulé par le sentiment de ne pas rester au même point. Ce moteur se nourrit de l’apprentissage, du développement de nouvelles compétences, du dépassement d’une difficulté et de la perception de sa propre évolution. Il ne s’agit pas nécessairement de progresser hiérarchiquement : on peut progresser dans sa maîtrise, son autonomie, ses connaissances, ses responsabilités ou sa façon d’exercer son métier. Ce qui compte est de sentir que l’on continue à évoluer.",
        "basse": "L’apprentissage permanent ou la recherche régulière de nouveaux défis n’est pas indispensable à la motivation. La maîtrise, la stabilité ou l’utilisation de compétences déjà acquises peuvent apporter davantage de satisfaction.",
        "moyenne": "Continuer à apprendre et développer certaines compétences contribue à la motivation, notamment lorsque l’évolution répond à un objectif concret ou à une envie particulière.",
        "haute": "Apprendre, développer ses capacités et constater sa propre évolution constitue une source majeure d’énergie. La sensation de stagnation peut être particulièrement démotivante lorsque les possibilités de développement deviennent trop faibles.",
    },
    "MP10": {
        "definition": "Contribuer, c’est être stimulé par le sentiment de participer à quelque chose qui dépasse sa seule tâche ou son intérêt immédiat. Ce moteur apparaît lorsque l’on perçoit que son travail prend place dans un projet, une mission, une cause ou une ambition collective auxquels on souhaite prendre part. Il peut s’agir d’une contribution économique, sociale, environnementale, professionnelle ou simplement collective. Il ne suppose donc pas une vocation humanitaire : l’essentiel est de pouvoir relier son activité à une finalité plus large à laquelle on souhaite apporter sa part.",
        "basse": "Relier son activité à une finalité collective ou plus large n’est pas indispensable à la motivation. La satisfaction peut davantage provenir du contenu du travail, de ses conditions ou de résultats personnels et immédiats.",
        "moyenne": "Participer à un projet ou à une finalité que l’on juge intéressante renforce la motivation. Cette dimension devient particulièrement importante lorsque le sens du projet est clairement perceptible.",
        "haute": "Sentir que son travail participe à une finalité plus large constitue une source importante d’énergie. La personne peut être particulièrement stimulée lorsqu’elle comprend à quoi elle contribue et qu’elle se reconnaît dans la direction ou la finalité poursuivie.",
    },
}

###############################################################################
# CLARTE360
# MODULE : Informations institutionnelles
# ROLE   : Coordonnees, mentions legales, contact et pied de page PDF
# VERSION: 1.7.0
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


def update_runtime_activity(event: str = "heartbeat", user_activity: bool = True):
    """Met a jour le temps de session et, si necessaire, la derniere activite utilisateur.

    Point important du Socle Clarte360 1.0 :
    - les battements automatiques servent uniquement a recalculer le temps et a
      declencher le timeout ;
    - ils ne doivent jamais etre consideres comme une activite utilisateur ;
    - seules les actions explicites du beneficiaire prolongent la session.

    Le delta ajoute est plafonne a 30 secondes pour eviter de comptabiliser une
    longue absence liee a une fermeture brutale, une veille ou une suspension du navigateur.
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
    now_txt = now_dt.isoformat(timespec="seconds")
    sess["dernier_battement"] = now_txt
    sess["dernier_evenement"] = event
    st.session_state.session_last_heartbeat = now_txt
    if user_activity:
        sess["derniere_activite"] = now_txt
        st.session_state.session_last_activity = now_txt


def update_runtime_heartbeat(event: str = "heartbeat"):
    """Met a jour le battement technique sans prolonger l'inactivite utilisateur."""
    update_runtime_activity(event=event, user_activity=False)


def record_save_event(kind: str):
    update_runtime_activity(kind, user_activity=True)
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
    update_runtime_activity(reason, user_activity=(reason != "timeout_inactivite"))
    sess = _current_session_record()
    if sess:
        now = now_iso()
        if reason != "timeout_inactivite":
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
        "socle_clarte360_version": SOCLE_CLARTE360_VERSION,
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
    """Controle l'inactivite reelle du beneficiaire.

    La fermeture se fait apres 15 minutes sans action utilisateur explicite
    (validation, sauvegarde, sortie). Les reruns automatiques du watchdog ne
    reinitialisent pas ce delai.
    """
    if not st.session_state.get("test_started") or st.session_state.get("session_expired"):
        return
    update_runtime_heartbeat("watchdog")
    limit_seconds = get_session_limit_minutes() * 60
    current = _current_session_record()
    last_activity_raw = st.session_state.get("session_last_activity") or (current or {}).get("derniere_activite") or (current or {}).get("debut")
    try:
        last_activity = datetime.fromisoformat(last_activity_raw)
    except Exception:
        last_activity = datetime.now()
    inactive_seconds = int((datetime.now() - last_activity).total_seconds())
    if inactive_seconds >= limit_seconds:
        if current is not None:
            current["inactivite_secondes_avant_timeout"] = inactive_seconds
        close_runtime_session("timeout_inactivite")
        st.session_state.session_expired = True
        st.rerun()


def timeout_watchdog():
    """Declenche un rerun automatique pour appliquer le timeout sans clic.

    Ordre de preference :
    1. streamlit-autorefresh : composant stable et compatible Streamlit Cloud ;
    2. st.fragment(run_every=...) : secours pour les environnements recents ;
    3. petit script JS de secours, non considere comme source de verite.
    """
    if not st.session_state.get("test_started") or st.session_state.get("session_expired"):
        return

    if st_autorefresh is not None:
        st_autorefresh(interval=10_000, key="clarte360_timeout_watchdog")
        return

    if hasattr(st, "fragment"):
        @st.fragment(run_every="10s")
        def _watchdog_fragment():
            if st.session_state.get("test_started") and not st.session_state.get("session_expired"):
                check_session_limit()
        _watchdog_fragment()
        return

    components.html(
        """
        <script>
        setTimeout(function(){ try { window.parent.location.reload(); } catch(e) { window.location.reload(); } }, 10000);
        </script>
        """,
        height=0,
    )


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
    st.session_state.beneficiaire = {"nom": validate_name(nom, "Nom"), "prenom": validate_name(prenom, "Prénom"), "email": validate_email(email), "consultant": validate_short_text(consultant, "Consultant", 160, False)}
    st.session_state.test_started = True
    st.session_state.final_email_sent = False
    st.session_state.json_downloaded = False
    st.session_state.guard_saved_fingerprint = None
    st.session_state.session_history = []
    init_runtime_session("premiere_connexion")


def restore_from_progress(payload: dict):
    previous_sessions = deepcopy(payload.get("sessions", payload.get("session_history", [])))
    st.session_state.passation_root_id = payload.get("passation_root_id", payload.get("session_id", str(uuid.uuid4())))
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.passation_id = payload.get("passation_id", st.session_state.passation_root_id)
    st.session_state.cursor_order = payload.get("cursor_order_displayed", payload.get("cursor_order", []))
    st.session_state.positions = {str(k): validate_position(v) for k, v in payload.get("positions", {}).items()}
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
    # Le JSON importé constitue le point de sauvegarde de référence.
    st.session_state.guard_saved_fingerprint = persisted_business_fingerprint()
    st.session_state.json_downloaded = True


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
    update_runtime_heartbeat("construction_json")
    scores_df, score_details = compute_results(active, dims, st.session_state.get("positions", {}))
    payload = {
        "outil": get_param(params, "outil_code", "clarte360_moteurs_professionnels"),
        "outil_nom": get_param(params, "outil_nom", APP_FULL_NAME),
        "app_version": APP_VERSION,
        "socle_clarte360_version": SOCLE_CLARTE360_VERSION,
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


def report_content_for(code: str) -> dict:
    return MOTEUR_REPORT_CONTENT.get(str(code).strip(), {"definition": "", "basse": "", "moyenne": "", "haute": ""})


def append_pdf_moteur_details(story, scores_df: pd.DataFrame, h_style, normal):
    story.append(Paragraph("Comprendre vos moteurs professionnels", h_style))
    story.append(Paragraph("Les moteurs ci-dessous sont présentés du résultat le plus élevé au résultat le plus faible. Pour chacun, les trois niveaux de lecture sont volontairement affichés afin de situer le sens du moteur dans son ensemble.", normal))
    story.append(Spacer(1, 0.15*cm))
    for _, r in scores_df.sort_values("Pourcentage", ascending=False).iterrows():
        content = report_content_for(r["Code"])
        story.append(Paragraph(f"<b>{r['Moteur'].upper()} — {r['Pourcentage']:.1f} %</b>", h_style))
        story.append(Paragraph(f"<b>Votre résultat :</b> {r['Lecture']}", normal))
        story.append(Paragraph(f"<b>Ce que signifie ce moteur</b><br/>{content['definition']}", normal))
        story.append(Spacer(1, 0.08*cm))
        story.append(Paragraph("<b>Les trois niveaux de lecture</b>", normal))
        story.append(Paragraph(f"<b>Lecture basse :</b> {content['basse']}", normal))
        story.append(Paragraph(f"<b>Lecture moyenne :</b> {content['moyenne']}", normal))
        story.append(Paragraph(f"<b>Lecture haute :</b> {content['haute']}", normal))
        story.append(Spacer(1, 0.18*cm))


def create_pdf(scores_df: pd.DataFrame, payload: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.2*cm, bottomMargin=1.8*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleClarte", parent=styles["Title"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=18, spaceAfter=10)
    h_style = ParagraphStyle("HClarte", parent=styles["Heading2"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=13, spaceBefore=8, spaceAfter=6)
    normal = styles["BodyText"]
    story = []
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=1.8*cm, height=1.8*cm)
        logo.hAlign = "CENTER"
        story.append(logo)
        story.append(Spacer(1, 0.12*cm))
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
    story.append(Spacer(1, 0.25*cm))
    append_pdf_moteur_details(story, scores_df, h_style, normal)
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
    if st.session_state.get("test_started") and st.button("← Retour à l'application", key="rgpd_top_back"):
        st.session_state.show_rgpd_page = False
        st.rerun()
    st.subheader("Informations légales et protection des données")

    tab_rgpd, tab_mentions, tab_contact = st.tabs(["Protection des données et traçabilité", "Mentions légales", "Nous contacter"])

    with tab_rgpd:
        st.markdown(RGPD_TEXT)
        st.info("Le consentement RGPD est demandé avant la génération du code d'accès et avant toute nouvelle passation.")
        traceability_information_block()

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


def contact_page():
    """Page d'assistance permanente accessible pendant l'utilisation."""
    display_header()
    if st.session_state.get("test_started") and st.button("← Retour à l'application", key="contact_top_back"):
        st.session_state.show_contact_page = False
        st.rerun()
    st.subheader("Contacter Clarté360")
    contact_form()


def contact_form():
    """Formulaire de contact support commun au socle Clarte360."""
    ben = st.session_state.get("beneficiaire") or st.session_state.get("pending_beneficiaire") or {}
    st.markdown("""
    ### Contacter Clarté360
    **Vous avez besoin de contacter Clarté360 ?**  
    Vous pouvez nous adresser une question administrative, signaler un problème technique ou nous faire part d'une suggestion d'amélioration concernant cette application.  
    Pour toute question relative à votre bilan de compétences ou à l'interprétation des exercices, nous vous invitons à vous rapprocher de votre consultant ou accompagnateur.  
    Nous vous répondrons par e-mail et, si vous renseignez votre numéro de téléphone, nous pourrons vous rappeler lorsque cela facilitera le traitement de votre demande.
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
        try:
            prenom = validate_name(prenom, "Prénom"); nom = validate_name(nom, "Nom"); email = validate_email(email)
            telephone = validate_phone(telephone); objet = validate_short_text(objet, "Objet", 180, True); message = validate_free_text(message, "Message", 5000, True)
        except ValueError as exc:
            st.error(str(exc)); return
        if not consent:
            st.error("Le consentement est nécessaire pour transmettre votre demande à Clarté360.")
            return
        tech = technical_context()
        support_id = f"SUP-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
        body = (
            "Demande envoyée depuis une application Clarté360.\n\n"
            f"Identifiant support : {support_id}\n"
            f"Application : {APP_FULL_NAME}\n"
            f"Version : {APP_VERSION}\n"
            f"Socle Clarté360 : {SOCLE_CLARTE360_VERSION}\n"
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
        ok, msg = send_email(f"Clarté360 - Support {support_id} - {APP_NAME}", body, to_email=FINAL_EMAIL_TO)
        if ok:
            st.success(f"Votre demande a bien été transmise à Clarté360. Référence : {support_id}")
        else:
            st.error("Le message n'a pas pu être envoyé automatiquement : " + msg)



def traceability_information_block():
    """Affiche la traçabilité RGPD/session sans dépendre du format interne d'une seule app."""
    update_runtime_heartbeat("affichage_tracabilite")
    sessions = st.session_state.get("session_history", []) or []
    rgpd = st.session_state.get("rgpd_acceptance", {}) or {}

    st.markdown("### Traçabilité de la session")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Session en cours", (st.session_state.get("current_runtime_session_id", "") or "Non ouverte")[:8])
    with c2:
        st.metric("Nombre de sessions", len(sessions))
    with c3:
        st.metric("Temps cumulé", format_duration(total_session_seconds()))

    if rgpd.get("consentement"):
        st.success(f"Consentement RGPD enregistré le : {rgpd.get('date','')} {rgpd.get('heure','')} — version : {rgpd.get('version_texte','')}")
    else:
        st.warning("Aucun consentement RGPD n'est encore enregistré dans le JSON.")

    if sessions:
        rows = []
        for sess in sessions:
            rows.append({
                "Début": sess.get("debut", ""),
                "Dernière activité": sess.get("derniere_activite", ""),
                "Fin": sess.get("fin", ""),
                "Durée": format_duration(sess.get("duree_active_secondes", sess.get("duree_secondes", 0))),
                "Motif ouverture": sess.get("motif_ouverture", ""),
                "Motif fermeture": sess.get("motif_fermeture", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucune session n'est encore enregistrée.")

    saves = []
    for sess in sessions:
        for save in sess.get("sauvegardes", []) or []:
            if isinstance(save, dict):
                saves.append({
                    "Date / heure": save.get("date_heure", ""),
                    "Motif": save.get("type", ""),
                    "Session": sess.get("session_uid", "")[:8],
                    "Durée session": format_duration(save.get("duree_active_secondes", 0)),
                })
    if saves:
        st.markdown("### Sauvegardes enregistrées")
        st.dataframe(pd.DataFrame(saves[-10:]), use_container_width=True, hide_index=True)


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
            payload = decode_progress_bytes(up.getvalue(), active["ID"].astype(str).tolist())
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
    """Barre latérale socle Clarté360 v1.8.

    Avant l'entrée dans le cœur de l'application : éléments institutionnels uniquement.
    Après validation du code : navigation / état métier en haut, puis fonctions JSON et institutionnelles.
    """
    in_app = bool(st.session_state.get("test_started"))

    if in_app:
        st.sidebar.markdown("### Navigation")
        total = len(st.session_state.get("cursor_order", [])) or len(active)
        idx = min(int(st.session_state.get("current_index", 0) or 0), total)
        if st.session_state.get("result_session_closed") or idx >= total:
            st.sidebar.markdown("**Résultats / rapport**")
        else:
            st.sidebar.markdown(f"**Questionnaire : {idx + 1} / {total}**")
        if st.sidebar.button("Revenir à l'application", use_container_width=True):
            st.session_state.show_contact_page = False
            st.session_state.show_rgpd_page = False
            st.rerun()
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Session")
        update_runtime_heartbeat("affichage_sidebar")
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
    else:
        st.sidebar.markdown("### Session")

    st.sidebar.markdown("---")
    if st.sidebar.button("💬 Contacter Clarté360", use_container_width=True):
        st.session_state.show_contact_page = True
        st.session_state.show_rgpd_page = False
        st.rerun()
    if st.sidebar.button("RGPD et mentions légales", use_container_width=True):
        st.session_state.show_rgpd_page = True
        st.session_state.show_contact_page = False
        st.rerun()

    st.sidebar.caption(f"App v{APP_VERSION} · Socle {SOCLE_CLARTE360_VERSION} · Questionnaire {get_param(params, 'version_questionnaire', '0.1')}")
    if not in_app:
        if st.sidebar.button("Réinitialiser la session"):
            reset_all()


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
        try:
            prenom = validate_name(prenom, "Prénom"); nom = validate_name(nom, "Nom"); email = validate_email(email); consultant = validate_short_text(consultant, "Consultant", 160, False)
        except ValueError as exc:
            st.error(str(exc)); return
        if not consent:
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
                else:
                    try:
                        code_checked = validate_code(code_in)
                    except ValueError as exc:
                        st.error(str(exc)); return
                if code_checked == st.session_state.get("access_code"):
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
    st.markdown("### Comprendre vos moteurs professionnels")
    st.caption("Les moteurs sont présentés du résultat le plus élevé au résultat le plus faible. Les trois niveaux de lecture sont affichés pour vous permettre de comprendre chaque moteur dans son ensemble.")
    for _, r in scores_df.sort_values("Pourcentage", ascending=False).iterrows():
        content = report_content_for(r["Code"])
        with st.expander(f"{r['Moteur']} — {r['Pourcentage']:.1f} % — {r['Lecture']}"):
            st.markdown(f"**Votre résultat : {r['Lecture']}**")
            st.markdown("**Ce que signifie ce moteur**")
            st.write(content["definition"])
            st.markdown("**Les trois niveaux de lecture**")
            st.markdown(f"**Lecture basse —** {content['basse']}")
            st.markdown(f"**Lecture moyenne —** {content['moyenne']}")
            st.markdown(f"**Lecture haute —** {content['haute']}")
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
    st.warning("La session a été arrêtée automatiquement après 15 minutes sans activité. Votre progression a été sauvegardée dans le JSON ci-dessous.")
    st.markdown("Téléchargez ce JSON : il permettra de reprendre le travail lors de la prochaine connexion. Une nouvelle session sera créée et le compteur de temps repartira à zéro, tout en conservant l'historique.")
    if not st.session_state.get("expiration_json_saved"):
        record_save_event("sauvegarde_automatique_expiration")
        st.session_state.expiration_json_saved = True
    payload = build_payload(active, dims, params, completed=False)
    st.download_button("Télécharger mon JSON de reprise", data=payload_bytes(payload), file_name=make_filename("moteurs_reprise_timeout_inactivite", "json"), mime="application/json", type="primary", on_click=mark_json_downloaded)


def persisted_business_fingerprint() -> str:
    """Empreinte du travail effectivement présent dans le JSON de reprise.

    Les traces techniques (timestamps, sessions, heartbeats, sauvegardes) sont
    volontairement exclues afin de ne pas créer de fausses alertes.
    """
    return fingerprint_guard_state(
        beneficiaire=st.session_state.get("beneficiaire", {}),
        cursor_order=st.session_state.get("cursor_order", []),
        positions=st.session_state.get("positions", {}),
        rgpd_acceptance=st.session_state.get("rgpd_acceptance", {}),
    )


def current_business_fingerprint(active: pd.DataFrame) -> str:
    """Empreinte du travail courant, y compris un curseur non encore validé."""
    draft_slider = None
    if st.session_state.get("test_started"):
        order = st.session_state.get("cursor_order", []) or []
        idx = int(st.session_state.get("current_index", 0) or 0)
        if 0 <= idx < len(order):
            cid = str(order[idx])
            widget_key = f"slider_{cid}"
            if widget_key in st.session_state:
                current_value = int(st.session_state.get(widget_key))
                positions = st.session_state.get("positions", {}) or {}
                if cid in positions:
                    baseline = int(positions[cid])
                else:
                    try:
                        row = active.set_index("ID").loc[cid]
                        baseline = int(row.get("Position défaut", 5))
                    except Exception:
                        baseline = 5
                if current_value != baseline:
                    draft_slider = {"id": cid, "position": current_value}
    return fingerprint_guard_state(
        beneficiaire=st.session_state.get("beneficiaire", {}),
        cursor_order=st.session_state.get("cursor_order", []),
        positions=st.session_state.get("positions", {}),
        rgpd_acceptance=st.session_state.get("rgpd_acceptance", {}),
        draft_slider=draft_slider,
    )


def mark_json_downloaded():
    # Le JSON contient l'état métier validé, pas un curseur en cours de manipulation.
    st.session_state.guard_saved_fingerprint = persisted_business_fingerprint()
    st.session_state.json_downloaded = True


def install_beforeunload_warning(active: pd.DataFrame):
    """Protège contre F5/fermeture/navigation si le travail a changé depuis le JSON.

    Un téléchargement sécurise uniquement l'état réellement contenu dans le JSON.
    Toute nouvelle réponse validée, ou tout déplacement de curseur non encore
    validé, réarme donc automatiquement la protection.
    """
    saved = st.session_state.get("guard_saved_fingerprint")
    current = current_business_fingerprint(active) if st.session_state.get("test_started") else None
    should_warn = bool(st.session_state.get("test_started") and (not saved or current != saved))
    if should_warn:
        components.html(
            """
            <script>
            window.parent.onbeforeunload = function (e) {
                const message = "Votre travail a changé depuis votre dernière sauvegarde JSON. Téléchargez un nouveau JSON avant de quitter.";
                e.preventDefault();
                e.returnValue = message;
                return message;
            };
            </script>
            """,
            height=0,
        )
    else:
        components.html(
            """<script>window.parent.onbeforeunload = null;</script>""",
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
    install_beforeunload_warning(active)
    if st.session_state.get("show_contact_page"):
        contact_page()
        if not st.session_state.get("test_started") and st.button("Retour à l'application"):
            st.session_state.show_contact_page = False
            st.rerun()
        return
    if st.session_state.get("show_rgpd_page"):
        rgpd_page()
        if not st.session_state.get("test_started") and st.button("Retour"):
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
