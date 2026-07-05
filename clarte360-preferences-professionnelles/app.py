import json
import hashlib
import random
import re
import smtplib
import uuid
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

APP_VERSION = "1.9.2-socle-clarte360"
SOCLE_CLARTE360_VERSION = "3.0"
RGPD_TEXT_VERSION = "RGPD-Clarte360-v1.0-2026-07"
BENEFICIARY_TIMEOUT_MINUTES = 15
APP_TITLE = "Clarté360 - Préférences professionnelles"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_XLSX = BASE_DIR / "data" / "questions_preferences_professionnelles_v1.xlsx"
LOGO_PATH = BASE_DIR / "assets" / "site_icon.png"
RANDOMIZE_OPTIONS = True
FINAL_EMAIL_TO = "contact@clarte360.com"
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

RGPD_TEXT = f"""
### Protection des données personnelles (RGPD)

Cette application Clarté360 fonctionne sans base de données serveur propre à l'application. Aucune donnée n'est enregistrée durablement sur un serveur Clarté360 par l'application.

Le fichier JSON constitue le seul support de conservation de votre travail. Il peut contenir votre identité, votre adresse e-mail, les dates et heures de connexion, la durée des sessions, vos réponses, vos résultats, l'historique des connexions, le code d'accès généré, l'historique des régénérations, le consentement RGPD, la version de l'application et les informations techniques disponibles.

Le fichier JSON appartient exclusivement au bénéficiaire. Vous choisissez librement de le conserver, de le supprimer ou de le transmettre à votre accompagnateur. Si vous le transmettez à votre accompagnateur, celui-ci l'utilise exclusivement dans le cadre du bilan de compétences ou de l'accompagnement Clarté360.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : {RGPD_TEXT_VERSION}.

### Nature des résultats

Les résultats fournis par les applications Clarté360 constituent des supports d'aide à la réflexion et à l'accompagnement. Ils ne constituent ni un diagnostic psychologique, ni un avis médical, ni une décision d'orientation automatique. Leur interprétation s'inscrit dans un dialogue avec le bénéficiaire et, lorsque cela est prévu, avec un professionnel de l'accompagnement.

### Propriété intellectuelle

Les applications, outils, questionnaires, méthodes, graphiques, rapports et contenus proposés par Clarté360 constituent des créations originales protégées. Toute reproduction, adaptation, diffusion ou réutilisation, totale ou partielle, sans autorisation écrite préalable de Clarté360, est interdite.
"""


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🟢",
    layout="centered",
)

st.markdown(
    f"""
    <style>
    :root {{ --clarte-teal: {OFFICIAL_TEAL}; }}
    .stProgress > div > div > div > div {{ background-color: {OFFICIAL_TEAL}; }}
    .clarte-box {{
        border-left: 6px solid {OFFICIAL_TEAL};
        background: {LIGHT_TEAL};
        padding: 1rem 1.1rem;
        border-radius: 0.55rem;
        margin: 1rem 0;
        color: {DARK_TEXT};
    }}
    .objectif-box {{
        border: 1px solid #cfe6e6;
        background: #f8fbfb;
        padding: 1.2rem 1.4rem;
        border-radius: 0.9rem;
        margin: 1rem 0 1.6rem 0;
        color: {DARK_TEXT};
    }}
    .clarte-card {{
        border: 1px solid #d9eeee;
        border-radius: 0.8rem;
        padding: 1rem;
        background: #ffffff;
        box-shadow: 0 1px 8px rgba(0, 128, 128, 0.08);
        margin-bottom: 1rem;
    }}
    .small-muted {{ color: #666; font-size: 0.9rem; }}
    h1, h2, h3 {{ color: {OFFICIAL_TEAL}; }}
    div.stButton > button[kind="primary"] {{ background-color: {OFFICIAL_TEAL}; border-color: {OFFICIAL_TEAL}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

DIMENSION_LABELS = {
    "PP1": "Autonomie",
    "PP2": "Organisation",
    "PP3": "Relations",
    "PP4": "Décision",
    "PP5": "Action",
    "PP6": "Changement",
    "PP7": "Environnement",
    "PP8": "Apprentissage",
    "PP9": "Contribution",
    "PP10": "Responsabilités",
}

DIMENSION_DESCRIPTIONS = {
    "Autonomie": "Préférence pour une marge de manœuvre dans la manière d'organiser et de réaliser son travail.",
    "Organisation": "Préférence concernant la planification, la priorisation et la structuration du travail.",
    "Relations": "Préférence concernant la place des échanges, de la coopération et du collectif dans le travail.",
    "Décision": "Préférence concernant la manière de choisir, d'arbitrer et d'avancer lorsqu'une décision est nécessaire.",
    "Action": "Préférence concernant le passage à l'action, le rythme et le caractère concret des activités.",
    "Changement": "Préférence concernant la nouveauté, l'évolution des méthodes, l'adaptation et les situations peu routinières.",
    "Environnement": "Préférence concernant les conditions matérielles, le niveau de calme, la variété et le cadre de travail.",
    "Apprentissage": "Préférence concernant la manière d'apprendre, de progresser et de s'approprier de nouvelles méthodes.",
    "Contribution": "Préférence concernant la façon d'apporter sa valeur à une équipe, un projet ou une organisation.",
    "Responsabilités": "Préférence concernant le niveau d'implication, de pilotage, d'arbitrage ou d'influence souhaité.",
}

REQUIRED_QUESTION_COLUMNS = [
    "ID", "Dimension", "Libelle dimension", "Question",
    "Reponse A", "Score A", "Reponse B", "Score B", "Reponse C", "Score C", "Reponse D", "Score D",
    "Max question", "Statut", "Version"
]


def sanitize_filename(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9àâäéèêëîïôöùûüçñ\- ]+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", "_", value)
    return value or "beneficiaire"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def validate_questionnaire(df: pd.DataFrame) -> list[str]:
    errors = []
    missing = [c for c in REQUIRED_QUESTION_COLUMNS if c not in df.columns]
    if missing:
        errors.append("Colonnes manquantes : " + ", ".join(missing))
        return errors
    ids = df["ID"].astype(str).str.strip()
    if ids.duplicated().any():
        errors.append("Des ID de questions sont en doublon.")
    active = df[df["Statut"].astype(str).str.lower().str.strip() == "active"]
    if len(active) != 60:
        errors.append(f"Le questionnaire doit contenir exactement 60 questions actives. Actuellement : {len(active)}.")
    for col in ["Score A", "Score B", "Score C", "Score D", "Max question"]:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.isna().any():
            errors.append(f"La colonne {col} contient des valeurs non numériques.")
    for col in ["Question", "Reponse A", "Reponse B", "Reponse C", "Reponse D"]:
        if df[col].astype(str).str.strip().eq("").any():
            errors.append(f"La colonne {col} contient au moins une cellule vide.")
    dim_counts = active.groupby("Dimension").size().to_dict()
    for dim in DIMENSION_LABELS:
        if dim_counts.get(dim, 0) != 6:
            errors.append(f"La dimension {dim} doit contenir 6 questions actives. Actuellement : {dim_counts.get(dim, 0)}.")
    return errors


@st.cache_data(show_spinner=False)
def load_workbook_from_source(content: bytes | None, default_mtime: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = BytesIO(content) if content else DEFAULT_XLSX
    questions = normalize_columns(pd.read_excel(source, sheet_name="Questions"))
    if content:
        source.seek(0)
    dimensions = normalize_columns(pd.read_excel(source, sheet_name="Dimensions"))
    return questions, dimensions


def get_active_questions(questions_df: pd.DataFrame) -> pd.DataFrame:
    active = questions_df[questions_df["Statut"].astype(str).str.lower().str.strip() == "active"].copy()
    active["ID"] = active["ID"].astype(str).str.strip()
    active["Dimension"] = active["Dimension"].astype(str).str.strip()
    for col in ["Score A", "Score B", "Score C", "Score D", "Max question"]:
        active[col] = pd.to_numeric(active[col], errors="coerce").fillna(0).astype(float)
    return active


def start_new_session(active_questions: pd.DataFrame, nom: str, prenom: str, email: str = ""):
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.passation_id = f"CL360-PP-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{st.session_state.session_id[:8].upper()}"
    if not st.session_state.get("rgpd_acceptance"):
        at = st.session_state.get("rgpd_consent_at") or now_iso()
        dt = parse_iso(at) or datetime.now()
        st.session_state.rgpd_acceptance = {"consentement": True, "date": dt.strftime("%Y-%m-%d"), "heure": dt.strftime("%H:%M:%S"), "version_texte": RGPD_TEXT_VERSION}
    st.session_state.rgpd_consent_given = True
    ids = active_questions["ID"].tolist()
    random.shuffle(ids)
    st.session_state.question_order = ids
    option_orders = {}
    for qid in ids:
        opts = ["A", "B", "C", "D"]
        if RANDOMIZE_OPTIONS:
            random.shuffle(opts)
        option_orders[qid] = opts
    st.session_state.option_orders = option_orders
    st.session_state.answers = {}
    st.session_state.current_index = 0
    st.session_state.started_at = datetime.now().isoformat(timespec="seconds")
    st.session_state.beneficiaire = {"nom": nom.strip(), "prenom": prenom.strip(), "email": email.strip()}
    st.session_state.test_started = True
    st.session_state.email_sent = False
    ensure_access_tracking(user_activity=True)


def restore_from_progress(payload: dict):
    st.session_state.session_id = payload.get("session_id", str(uuid.uuid4()))
    st.session_state.question_order = payload.get("question_order_displayed", payload.get("question_order", []))
    st.session_state.option_orders = payload.get("option_orders_displayed", payload.get("option_orders", {}))
    answers_payload = payload.get("answers", {})
    answers = {}
    for qid, val in answers_payload.items():
        if isinstance(val, dict):
            answers[qid] = val.get("selected_option") or val.get("selected")
        else:
            answers[qid] = val
    st.session_state.answers = {str(k): str(v) for k, v in answers.items() if v}
    # Reprise robuste : on reprend toujours à la première question non répondue,
    # en conservant l'ordre initial du questionnaire sauvegardé.
    first_unanswered = None
    for i, qid in enumerate(st.session_state.question_order):
        if qid not in st.session_state.answers:
            first_unanswered = i
            break
    st.session_state.current_index = first_unanswered if first_unanswered is not None else len(st.session_state.question_order)
    st.session_state.started_at = payload.get("started_at", datetime.now().isoformat(timespec="seconds"))
    st.session_state.beneficiaire = payload.get("beneficiaire", {})
    st.session_state.passation_id = payload.get("passation_id", payload.get("session_id", str(uuid.uuid4())))
    st.session_state.test_started = True
    st.session_state.email_sent = bool(payload.get("email_sent", False))
    st.session_state.access = payload.get("access", st.session_state.get("access", {})) or {}
    st.session_state.rgpd_consent_given = bool(payload.get("rgpd", {}).get("consent_given", False)) if isinstance(payload.get("rgpd"), dict) else False
    st.session_state.rgpd_consent_at = payload.get("rgpd", {}).get("consent_at", "") if isinstance(payload.get("rgpd"), dict) else ""
    ensure_access_tracking(user_activity=True)


def reset_all():
    for key in [
        "session_id", "passation_id", "question_order", "option_orders", "answers", "current_index",
        "started_at", "beneficiaire", "test_started", "email_sent", "start_email_sent",
        "pending_beneficiaire", "access_code", "code_sent", "code_message", "code_verified"
    ]:
        st.session_state.pop(key, None)
    st.rerun()


def interpretation_level(pct: float) -> str:
    if pct < 25:
        return "Préférence peu marquée"
    if pct < 50:
        return "Préférence modérée"
    if pct < 75:
        return "Préférence nette"
    return "Préférence forte"


def compute_results(active_questions: pd.DataFrame, answers: dict) -> tuple[pd.DataFrame, dict]:
    scores = {dim: 0.0 for dim in DIMENSION_LABELS}
    max_scores = {dim: 0.0 for dim in DIMENSION_LABELS}
    rows = []
    by_id = active_questions.set_index("ID")
    for qid, row in by_id.iterrows():
        dim = str(row["Dimension"]).strip()
        max_scores[dim] = max_scores.get(dim, 0.0) + float(row.get("Max question", 3))
        selected = answers.get(qid)
        if selected:
            val = float(row.get(f"Score {selected}", 0))
            scores[dim] = scores.get(dim, 0.0) + val
            rows.append({
                "question_id": qid,
                "dimension": dim,
                "selected": selected,
                "score": val,
                "max": float(row.get("Max question", 3)),
            })
    result_rows = []
    for dim, label in DIMENSION_LABELS.items():
        max_val = max_scores.get(dim, 0.0) or 1.0
        pct = round(scores.get(dim, 0.0) / max_val * 100, 1)
        result_rows.append({
            "Code": dim,
            "Dimension": label,
            "Score": scores.get(dim, 0.0),
            "Score max": max_scores.get(dim, 0.0),
            "Pourcentage": pct,
            "Lecture": interpretation_level(pct),
        })
    return pd.DataFrame(result_rows), {"detail_scores": rows}


def build_user_interpretation(results: pd.DataFrame, beneficiaire: dict) -> str:
    top = results.sort_values("Pourcentage", ascending=False).head(3)
    low = results.sort_values("Pourcentage", ascending=True).head(2)
    top_txt = ", ".join([f"{r.Dimension.lower()} ({r.Pourcentage:.0f} %)" for r in top.itertuples()])
    low_txt = ", ".join([f"{r.Dimension.lower()} ({r.Pourcentage:.0f} %)" for r in low.itertuples()])
    prenom = beneficiaire.get("prenom", "")
    intro = f"{prenom}, vos réponses" if prenom else "Vos réponses"
    return (
        f"{intro} ne définissent pas une personnalité. Elles mettent en évidence des préférences professionnelles "
        "déclarées à un moment donné. Elles servent de support à l’échange avec votre consultant Clarté360.\n\n"
        f"Les préférences les plus marquées apparaissent autour de : {top_txt}. "
        f"Les préférences les moins marquées concernent davantage : {low_txt}. "
        "Ces éléments ne constituent pas une orientation automatique : ils ouvrent des pistes de réflexion sur les conditions "
        "dans lesquelles vous vous sentez le plus à l’aise pour travailler."
    )



def questionnaire_checksum() -> str:
    try:
        return hashlib.sha256(DEFAULT_XLSX.read_bytes()).hexdigest()[:16]
    except Exception:
        return "indisponible"


def get_email_config() -> dict | None:
    """Lit la configuration SMTP depuis Streamlit Secrets.

    Aucun mot de passe ne doit être stocké dans GitHub.
    En production Streamlit Cloud, les valeurs sont à renseigner dans Settings > Secrets.
    """
    try:
        cfg = st.secrets.get("email", {})
        required = ["smtp_server", "smtp_port", "smtp_user", "smtp_password", "from_email", "to_email"]
        if not cfg or any(not str(cfg.get(k, "")).strip() for k in required):
            return None
        return {k: cfg.get(k) for k in required}
    except Exception:
        return None


def send_email(to_email: str, subject: str, body: str, attachment: bytes | None = None, attachment_name: str | None = None) -> tuple[bool, str]:
    cfg = get_email_config()
    if cfg is None:
        return False, "SMTP non configuré. Aucun email n'a été envoyé."

    try:
        msg = EmailMessage()
        msg["From"] = cfg["from_email"]
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        if attachment is not None and attachment_name:
            msg.add_attachment(attachment, maintype="application", subtype="json", filename=attachment_name)

        port = int(cfg["smtp_port"])
        server = str(cfg["smtp_server"])
        user = str(cfg["smtp_user"])
        password = str(cfg["smtp_password"])

        if port == 465:
            with smtplib.SMTP_SSL(server, port, timeout=20) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, port, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(user, password)
                smtp.send_message(msg)
        return True, "Email envoyé."
    except Exception as exc:
        return False, f"Erreur d'envoi email : {exc}"


def generate_access_code() -> str:
    return f"{random.randint(100000, 999999)}"


def send_access_code_email(beneficiaire: dict, access_code: str) -> tuple[bool, str]:
    """Envoie le code au bénéficiaire ET une notification à Clarté360.

    Le démarrage du questionnaire est bloqué si l'un des deux envois échoue.
    Cela garantit que Clarté360 est informé qu'une personne va réaliser le test.
    """
    cfg = get_email_config()
    if cfg is None:
        return False, "SMTP non configuré : impossible d'envoyer le code d'accès. Configurez les Secrets Streamlit."

    prenom = beneficiaire.get("prenom", "")
    nom = beneficiaire.get("nom", "")
    email = beneficiaire.get("email", "")
    admin_to = cfg.get("to_email", FINAL_EMAIL_TO) if cfg else FINAL_EMAIL_TO
    now_txt = datetime.now().isoformat(timespec="seconds")

    # 1) Notification Clarté360 : une personne va faire le test.
    subject_admin = "Clarté360 - Nouveau code d'accès Préférences professionnelles"
    body_admin = (
        "Une personne vient de demander un code d'accès pour réaliser l'outil Clarté360 - Préférences professionnelles.\n\n"
        f"Bénéficiaire : {prenom} {nom}\n"
        f"Email : {email}\n"
        f"Date de demande : {now_txt}\n\n"
        "Information : le JSON final sera transmis automatiquement à Clarté360 lorsque la question 60 sera validée.\n\n"
        "Message automatique Clarté360."
    )
    ok_admin, msg_admin = send_email(admin_to, subject_admin, body_admin)
    # Une erreur SMTP de notification administrateur ne doit jamais interrompre l'application.

    # 2) Code d'accès au bénéficiaire.
    subject_user = "Votre code d'accès Clarté360"
    body_user = (
        f"Bonjour {prenom},\n\n"
        "Voici votre code d'accès pour démarrer le questionnaire Clarté360 - Préférences professionnelles :\n\n"
        f"{access_code}\n\n"
        "Ce code permet de sécuriser le démarrage de votre passation.\n\n"
        "À la fin du questionnaire, vous pourrez télécharger votre rapport PDF et votre fichier JSON.\n\n"
        "Clarté360"
    )
    ok_user, msg_user = send_email(email, subject_user, body_user)
    if not ok_user:
        return False, "Code bénéficiaire non envoyé : " + msg_user

    return True, "Code envoyé au bénéficiaire et notification transmise à Clarté360."

def send_start_notification(beneficiaire: dict, passation_id: str) -> tuple[bool, str]:
    """Notification interne optionnelle au démarrage de la passation.

    En local ou sans Streamlit Secrets, la fonction retourne un message non bloquant.
    """
    prenom = beneficiaire.get("prenom", "")
    nom = beneficiaire.get("nom", "")
    email = beneficiaire.get("email", "")
    subject_admin = "Clarté360 - Nouvelle passation démarrée"
    body_admin = (
        "Une nouvelle passation vient de démarrer pour l'outil Préférences professionnelles.\n\n"
        f"Bénéficiaire : {prenom} {nom}\n"
        f"Email : {email}\n"
        f"ID passation : {passation_id}\n"
        f"Date : {datetime.now().isoformat(timespec='seconds')}\n\n"
        "Le JSON final sera transmis automatiquement à la fin si l'envoi SMTP est configuré."
    )
    return send_email(FINAL_EMAIL_TO, subject_admin, body_admin)


def base_export_payload(completed: bool) -> dict:
    beneficiaire = st.session_state.get("beneficiaire", {})
    return {
        "outil": "clarte360_preferences_professionnelles",
        "nom_outil": "Préférences professionnelles",
        "version": APP_VERSION,
        "app_version": APP_VERSION,
        "version_application": APP_VERSION,
        "version_socle_clarte360": SOCLE_CLARTE360_VERSION,
        "session_id": st.session_state.get("session_id", ""),
        "identifiant_session": st.session_state.get("active_session_id", st.session_state.get("session_id", "")),
        "passation_root_id": st.session_state.get("passation_id", st.session_state.get("session_id", "")),
        "passation_id": st.session_state.get("passation_id", st.session_state.get("session_id", "")),
        "beneficiaire": {
            "nom": beneficiaire.get("nom", ""),
            "prenom": beneficiaire.get("prenom", ""),
            "email": beneficiaire.get("email", ""),
        },
        "started_at": st.session_state.get("started_at", ""),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "completed": completed,
        "current_index": st.session_state.get("current_index", 0),
        "questionnaire_source": "questions_preferences_professionnelles_v1.xlsx",
        "questionnaire_checksum": questionnaire_checksum(),
        "question_order_displayed": st.session_state.get("question_order", []),
        "option_orders_displayed": st.session_state.get("option_orders", {}),
        "answers": st.session_state.get("answers", {}),
        "notice": "Outil déclaratif d’exploration. Ne constitue pas un test psychométrique ni un diagnostic.",
        "rgpd": {
            "consent_given": bool(st.session_state.get("rgpd_consent_given", False) or st.session_state.get("rgpd_acceptance", {}).get("consentement", False)),
            "consent_at": st.session_state.get("rgpd_consent_at", ""),
            "text_version": RGPD_TEXT_VERSION,
            "rappel": "Aucune donnée n’est enregistrée durablement sur un serveur Clarté360 par l’application. Le JSON appartient exclusivement au bénéficiaire.",
        },
        "rgpd_acceptance": st.session_state.get("rgpd_acceptance", {}),
        "access": st.session_state.get("access", {}),
        "historique_sessions": st.session_state.get("access", {}).get("sessions", []),
        "temps_cumule_secondes": st.session_state.get("access", {}).get("temps_total_cumule_secondes", 0),
    }


def build_progress_json() -> dict:
    payload = base_export_payload(completed=False)
    payload["type_export"] = "sauvegarde_intermediaire"
    return payload


def build_export_json(active_questions: pd.DataFrame, results: pd.DataFrame, score_details: dict) -> dict:
    by_id = active_questions.set_index("ID")
    payload = base_export_payload(completed=True)
    payload["type_export"] = "resultats_finaux"
    payload["completed_at"] = datetime.now().isoformat(timespec="seconds")
    payload["answers"] = {
        qid: {
            "selected_option": opt,
            "question_text": str(by_id.loc[qid, "Question"]),
            "answer_text": str(by_id.loc[qid, f"Reponse {opt}"]),
            "dimension": str(by_id.loc[qid, "Dimension"]),
            "score": float(by_id.loc[qid, f"Score {opt}"]),
        }
        for qid, opt in st.session_state.answers.items()
    }
    payload["scores"] = results.to_dict(orient="records")
    payload["score_details"] = score_details
    payload["email_sent"] = st.session_state.get("email_sent", False)
    return payload


def plot_bar_results(results: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ordered = results.sort_values("Pourcentage", ascending=True)
    bars = ax.barh(ordered["Dimension"], ordered["Pourcentage"], color=OFFICIAL_TEAL)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Pourcentage")
    ax.set_title("Préférences professionnelles déclarées")
    ax.grid(axis="x", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar, value in zip(bars, ordered["Pourcentage"]):
        ax.text(min(value + 1, 98), bar.get_y() + bar.get_height()/2, f"{value:.0f}%", va="center")
    fig.tight_layout()
    return fig


def plot_radar_results(results: pd.DataFrame):
    labels = results["Dimension"].tolist()
    values = results["Pourcentage"].tolist()
    angles = [n / float(len(labels)) * 2 * 3.141592653589793 for n in range(len(labels))]
    values += values[:1]
    angles += angles[:1]
    fig = plt.figure(figsize=(6, 6))
    ax = plt.subplot(111, polar=True)
    ax.plot(angles, values, color=OFFICIAL_TEAL, linewidth=2)
    ax.fill(angles, values, color=OFFICIAL_TEAL, alpha=0.18)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_title("Profil visuel des préférences", y=1.08)
    fig.tight_layout()
    return fig


def fig_to_png_bytes(fig) -> BytesIO:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight")
    buf.seek(0)
    return buf


def make_pdf(results: pd.DataFrame, interpretation: str, beneficiaire: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.2*cm, bottomMargin=1.2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleTeal", parent=styles["Title"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=18, leading=22)
    h2_teal = ParagraphStyle("H2Teal", parent=styles["Heading2"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=13, leading=16)
    normal = styles["BodyText"]
    story = []
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=2.0*cm, height=2.0*cm)
        logo.hAlign = "CENTER"
        story.append(logo)
    story.append(Paragraph("Clarté360 - Préférences professionnelles", title_style))
    nom = beneficiaire.get("nom", "")
    prenom = beneficiaire.get("prenom", "")
    identite = " ".join([prenom, nom]).strip()
    story.append(Paragraph(f"Bénéficiaire : {identite}", normal))
    story.append(Paragraph(f"Date : {datetime.now().strftime('%d/%m/%Y')}", normal))
    story.append(Spacer(1, 0.25*cm))
    story.append(Paragraph("Première lecture bénéficiaire", h2_teal))
    story.append(Paragraph(interpretation.replace("\n", "<br/>"), normal))
    story.append(Spacer(1, 0.4*cm))

    bar_fig = plot_bar_results(results)
    radar_fig = plot_radar_results(results)
    story.append(Image(fig_to_png_bytes(bar_fig), width=17.0*cm, height=10.0*cm))
    plt.close(bar_fig)
    story.append(Spacer(1, 0.2*cm))
    story.append(Image(fig_to_png_bytes(radar_fig), width=12.0*cm, height=12.0*cm))
    plt.close(radar_fig)
    story.append(Spacer(1, 0.3*cm))

    data = [["Dimension", "Score", "Lecture"]]
    for r in results.sort_values("Pourcentage", ascending=False).itertuples():
        data.append([r.Dimension, f"{r.Pourcentage:.0f} %", r.Lecture])
    table = Table(data, colWidths=[6.5*cm, 3*cm, 6*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(OFFICIAL_TEAL)),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#F5FBFB")),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.35*cm))
    story.append(Paragraph("Ce document est un support d’échange. Il ne constitue ni un diagnostic, ni un test psychométrique, ni une orientation automatique.", styles["Italic"]))
    story.append(Paragraph("Document généré localement. Les données restent sous le contrôle du bénéficiaire.", styles["Italic"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Clarté360 - 60 rue François 1er - 75008 Paris - contact@clarte360.com - www.clarte360.com - SIRET 10234983400014", styles["Italic"]))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def render_header():
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=120)
    st.markdown(f"<h1 style='color:{OFFICIAL_TEAL}; margin-bottom:0;'>Clarté360 - Préférences professionnelles</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#4b5563; font-size:1.05rem; margin-top:0.35rem;'>Version {APP_VERSION} - outil propriétaire d’exploration des préférences professionnelles</p>", unsafe_allow_html=True)


def build_speech_text(question_number: int, total: int, question: str, displayed_labels: list[str]) -> str:
    """Construit le texte lu dans l'ordre exact affiche au beneficiaire.

    Important : les options techniques A/B/C/D peuvent etre melangees pour la cotation.
    La lecture vocale doit suivre l'ordre visible a l'ecran, pas l'ordre technique de la base.
    """
    parts = [f"Question {question_number} sur {total}.", question]
    visible_letters = ["A", "B", "C", "D"]
    for letter, label in zip(visible_letters, displayed_labels):
        parts.append(f"Proposition {letter}. {label}.")
    return " ".join(parts)


def render_speech_button(text_to_read: str):
    escaped = json.dumps(text_to_read, ensure_ascii=False)
    components.html(
        f"""
        <div style="margin: 0.5rem 0 1rem 0;">
          <button onclick="readClarteQuestion()" style="background:{OFFICIAL_TEAL};color:white;border:0;border-radius:8px;padding:0.55rem 0.9rem;cursor:pointer;font-size:15px;">🔊 Lire la question et les propositions</button>
          <button onclick="window.speechSynthesis.cancel()" style="background:#eef3f3;color:#203636;border:1px solid #cbdada;border-radius:8px;padding:0.55rem 0.9rem;cursor:pointer;font-size:15px;margin-left:0.5rem;">■ Arrêter</button>
          <span id="clarte_reading_status" style="margin-left:0.7rem;color:#586666;font-family:sans-serif;font-size:14px;"></span>
        </div>
        <script>
        function readClarteQuestion() {{
            const text = {escaped};
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'fr-FR';
            utterance.rate = 0.95;
            const status = document.getElementById('clarte_reading_status');
            utterance.onstart = function() {{ if(status) status.innerText = 'Lecture en cours...'; }};
            utterance.onend = function() {{ if(status) status.innerText = ''; }};
            utterance.onerror = function() {{ if(status) status.innerText = 'Lecture indisponible sur ce navigateur.'; }};
            window.speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        height=64,
    )


def json_download_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def current_name_part() -> str:
    b = st.session_state.get("beneficiaire", {})
    return sanitize_filename(f"{b.get('prenom','')} {b.get('nom','')}")


def timestamp_part() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def try_send_final_json(json_bytes: bytes, file_name: str, beneficiaire: dict) -> tuple[bool, str]:
    """Envoi SMTP optionnel du JSON final. Nécessite une configuration Streamlit Secrets."""
    subject = f"Clarté360 - JSON préférences - {beneficiaire.get('prenom','')} {beneficiaire.get('nom','')}"
    body = (
        "Bonjour,\n\n"
        "Veuillez trouver ci-joint le JSON final généré par l'outil Clarté360 - Préférences professionnelles.\n\n"
        f"Bénéficiaire : {beneficiaire.get('prenom','')} {beneficiaire.get('nom','')}\n"
        f"Email : {beneficiaire.get('email','')}\n"
        f"Date : {datetime.now().isoformat(timespec='seconds')}\n\n"
        "Message automatique."
    )
    cfg = get_email_config()
    destination = cfg.get("to_email", FINAL_EMAIL_TO) if cfg else FINAL_EMAIL_TO
    ok, msg = send_email(destination, subject, body, attachment=json_bytes, attachment_name=file_name)
    if ok:
        return True, "JSON final transmis automatiquement à Clarté360."
    return False, msg



def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_iso(value: str):
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except Exception:
        return None


def get_client_network() -> dict:
    try:
        headers = dict(st.context.headers)
    except Exception:
        headers = {}
    def h(name):
        for k, v in headers.items():
            if str(k).lower() == name.lower():
                return str(v)
        return ""
    forwarded = h("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (h("x-real-ip") or h("cf-connecting-ip") or "")
    return {"ip": ip, "user_agent": h("user-agent"), "headers_available": bool(headers)}


def ensure_access_tracking(user_activity: bool = True):
    if "active_session_id" not in st.session_state:
        st.session_state.active_session_id = str(uuid.uuid4())
    if "access" not in st.session_state:
        st.session_state.access = {
            "timeout_minutes": BENEFICIARY_TIMEOUT_MINUTES,
            "sessions": [],
            "sauvegardes": [],
            "code_history": [],
            "code_regenerated_count": 0,
            "timed_out": False,
            "timed_out_at": "",
        }
    access = st.session_state.access
    sid = st.session_state.active_session_id
    now = now_iso()
    sess = next((x for x in access["sessions"] if x.get("session_id") == sid), None)
    if sess is None:
        sess = {"session_id": sid, "started_at": now, "last_activity_at": now, "last_seen_at": now, "ended_at": "", "duration_seconds": 0, "app_version": APP_VERSION, "socle_version": SOCLE_CLARTE360_VERSION, "client_network": get_client_network()}
        access["sessions"].append(sess)
    else:
        sess["last_seen_at"] = now
        if user_activity:
            sess["last_activity_at"] = now
    start = parse_iso(sess.get("started_at"))
    if start:
        sess["duration_seconds"] = int((datetime.now() - start).total_seconds())
    access["temps_total_cumule_secondes"] = sum(int(x.get("duration_seconds",0) or 0) for x in access.get("sessions", []))
    access["nombre_sessions"] = len(access.get("sessions", []))


def format_seconds(seconds) -> str:
    total = max(0, int(seconds or 0))
    h, rem = divmod(total, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {sec:02d} s"
    return f"{sec} s"


def beneficiary_has_timed_out() -> bool:
    ensure_access_tracking(user_activity=False)
    access = st.session_state.access
    if access.get("timed_out"):
        return True
    sid = st.session_state.get("active_session_id", "")
    sess = next((x for x in access.get("sessions", []) if x.get("session_id") == sid), None)
    last = parse_iso(sess.get("last_activity_at", "")) if sess else None
    if last and datetime.now() - last > timedelta(minutes=BENEFICIARY_TIMEOUT_MINUTES):
        access["timed_out"] = True
        access["timed_out_at"] = now_iso()
        if sess:
            sess["ended_at"] = now_iso()
            sess["end_reason"] = "timeout_15_minutes"
        return True
    return False


def install_beforeunload_warning():
    if st.session_state.get("test_started") and not st.session_state.get("json_downloaded"):
        components.html("""
        <script>
        window.parent.onbeforeunload = function (e) {
            const message = "Avant de quitter, utilisez le bouton Clarté360 : Quitter et télécharger mon JSON.";
            e.preventDefault();
            e.returnValue = message;
            return message;
        };
        </script>
        """, height=0)


def rgpd_information_block():
    st.markdown(RGPD_TEXT)


def traceability_information_block():
    """Affiche la traçabilité RGPD/session selon le socle Moteurs v1.8."""
    ensure_access_tracking(user_activity=False)
    access = st.session_state.get("access", {}) or {}
    sessions = access.get("sessions", []) or []
    rgpd = st.session_state.get("rgpd_acceptance", {}) or {}

    st.markdown("### Traçabilité de la session")
    c1, c2, c3 = st.columns(3)
    with c1:
        sid = st.session_state.get("active_session_id", st.session_state.get("session_id", "")) or "Non ouverte"
        st.metric("Session en cours", str(sid)[:8])
    with c2:
        st.metric("Nombre de sessions", len(sessions))
    with c3:
        st.metric("Temps cumulé", format_seconds(access.get("temps_total_cumule_secondes", 0)))

    if rgpd.get("consentement"):
        st.success(f"Consentement RGPD enregistré le : {rgpd.get('date','')} {rgpd.get('heure','')} — version : {rgpd.get('version_texte','')}")
    else:
        st.warning("Aucun consentement RGPD n'est encore enregistré dans le JSON.")

    if sessions:
        rows = []
        for sess in sessions:
            rows.append({
                "Début": sess.get("started_at", ""),
                "Dernière activité": sess.get("last_activity_at", sess.get("last_seen_at", "")),
                "Fin": sess.get("ended_at", ""),
                "Durée": format_seconds(sess.get("duration_seconds", 0)),
                "Motif": sess.get("end_reason", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

def legal_mentions_block():
    l = CLARTE360_LEGAL
    st.markdown("### Mentions légales")
    st.write(f"{l['raison_sociale']} {l['forme']} - {l['adresse']} - {l['code_postal_ville']}")
    st.write(f"Tél. : {l['telephone']} - E-mail : {l['email']} - Web : {l['web']}")
    st.write(f"RCS : {l['rcs']} - SIRET : {l['siret']} - NAF : {l['naf']} - TVA intracommunautaire : {l['tva']}")
    st.markdown("### Propriété intellectuelle et responsabilité")
    st.write("Les applications, questionnaires, méthodes, graphiques, rapports et contenus Clarté360 sont protégés. Toute reproduction, adaptation ou diffusion sans autorisation écrite préalable est interdite.")
    st.write("L'application constitue un support pédagogique et d'accompagnement. L'interprétation des résultats doit être réalisée avec le consultant ou l'accompagnateur.")


def contact_form_main():
    b = st.session_state.get("beneficiaire", st.session_state.get("pending_beneficiaire", {})) or {}
    st.info("Vous pouvez nous adresser une question administrative, signaler un problème technique ou nous faire part d’une suggestion concernant cette application. Pour toute question relative à l’interprétation des exercices ou des résultats, rapprochez-vous de votre consultant ou accompagnateur.")
    with st.form("contact_clarte360_form"):
        col1, col2 = st.columns(2)
        with col1:
            prenom = st.text_input("Prénom", value=b.get("prenom", ""))
        with col2:
            nom = st.text_input("Nom", value=b.get("nom", ""))
        email = st.text_input("E-mail", value=b.get("email", ""))
        telephone = st.text_input("Téléphone (facultatif)")
        objet = st.text_input("Objet *")
        message = st.text_area("Message *", height=160)
        consent = st.checkbox("J'accepte que Clarté360 traite ces informations pour répondre à ma demande.")
        submit = st.form_submit_button("Envoyer à Clarté360", type="primary")
    if submit:
        if not objet.strip() or not message.strip() or not consent:
            st.error("Merci de renseigner l'objet, le message et le consentement.")
            return
        ensure_access_tracking(user_activity=True)
        body = f"""Demande depuis l'application Clarté360 - Préférences professionnelles.\n\nNom : {prenom} {nom}\nE-mail : {email}\nTéléphone : {telephone}\nObjet : {objet}\n\nMessage :\n{message}\n\nApplication : {APP_TITLE}\nVersion : {APP_VERSION}\nSocle Clarté360 : {SOCLE_CLARTE360_VERSION}\nSession : {st.session_state.get('active_session_id','')}\nTemps cumulé : {format_seconds(st.session_state.get('access',{}).get('temps_total_cumule_secondes',0))}\nInfos techniques : {json.dumps(get_client_network(), ensure_ascii=False)}\n"""
        ok, msg = send_email(FINAL_EMAIL_TO, f"Clarté360 - Contact application - {objet}", body)
        if ok:
            st.success("Votre message a été transmis à Clarté360.")
        else:
            st.error("Le message n'a pas pu être envoyé automatiquement.")
            st.caption(msg)


def rgpd_page():
    render_header()
    st.subheader("Informations légales et protection des données")
    tab1, tab2, tab3 = st.tabs(["Protection des données et traçabilité", "Mentions légales", "Nous contacter"])
    with tab1:
        rgpd_information_block()
        st.info("Le consentement RGPD est demandé avant la génération du code d'accès et avant toute nouvelle passation.")
        traceability_information_block()
    with tab2:
        legal_mentions_block()
    with tab3:
        contact_form_main()


def render_sidebar():
    with st.sidebar:
        st.markdown("### Session")
        if st.session_state.get("test_started"):
            st.markdown("Votre progression est enregistrée dans votre fichier JSON.")
            if len(st.session_state.get("answers", {})) < len(st.session_state.get("question_order", [])):
                if st.button("💾 Préparer mon JSON pour reprendre plus tard", use_container_width=True):
                    ensure_access_tracking(user_activity=False)
                    st.session_state.exit_json_payload = build_progress_json()
                    st.session_state.exit_json_ready = True
                    st.session_state.access.setdefault("sauvegardes", []).append({"at": now_iso(), "motif": "sauvegarde_manuelle_reprise", "session_id": st.session_state.get("active_session_id", "")})
                    st.rerun()
                if st.button("🚪 Quitter et télécharger mon JSON", type="primary", use_container_width=True):
                    ensure_access_tracking(user_activity=False)
                    for sess in st.session_state.access.get("sessions", []):
                        if sess.get("session_id") == st.session_state.get("active_session_id"):
                            sess["ended_at"] = now_iso(); sess["end_reason"] = "sortie_utilisateur_par_bouton"
                    st.session_state.exit_json_payload = build_progress_json()
                    st.session_state.exit_json_ready = True
                    st.rerun()
            if st.session_state.get("exit_json_ready"):
                st.download_button(
                    "⬇️ Télécharger le JSON préparé",
                    data=json_download_bytes(st.session_state.exit_json_payload),
                    file_name=f"clarte360_preferences_sauvegarde_{current_name_part()}_{timestamp_part()}.json",
                    mime="application/json",
                    use_container_width=True,
                    on_click=lambda: st.session_state.update({"json_downloaded": True}),
                )
        resume_file = st.file_uploader("Importer mon fichier JSON", type=["json"], key="resume_json")
        if resume_file is not None and not st.session_state.get("test_started"):
            try:
                payload = json.loads(resume_file.getvalue().decode("utf-8"))
                if payload.get("outil") != "clarte360_preferences_professionnelles":
                    st.error("Ce fichier JSON ne correspond pas à cet outil.")
                elif payload.get("completed") is True:
                    st.error("Ce JSON correspond à un test déjà terminé. Il ne peut pas servir à reprendre une passation.")
                else:
                    restore_from_progress(payload)
                    st.success("Sauvegarde chargée. Reprise du questionnaire.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Impossible de charger la sauvegarde : {exc}")
        st.markdown("---")
        if st.button("💬 Contacter Clarté360", use_container_width=True):
            st.session_state.show_contact_page = True; st.session_state.show_rgpd_page = False; st.rerun()
        if st.button("RGPD et mentions légales", use_container_width=True):
            st.session_state.show_rgpd_page = True; st.session_state.show_contact_page = False; st.rerun()
        st.caption(f"App v{APP_VERSION} · Socle {SOCLE_CLARTE360_VERSION} · Questionnaire Préférences")
        if not st.session_state.get("test_started") and st.button("Réinitialiser la session", use_container_width=True):
            reset_all()

try:
    questions_df, dimensions_df = load_workbook_from_source(None, DEFAULT_XLSX.stat().st_mtime if DEFAULT_XLSX.exists() else 0)
    active_questions = get_active_questions(questions_df)
    validation_errors = validate_question_bank(active_questions)
    if validation_errors:
        st.error("Le questionnaire Préférences professionnelles n'est pas conforme à la structure attendue.")
        for err in validation_errors:
            st.error(err)
        st.stop()
except Exception as exc:
    st.error(f"Impossible de charger les questions Préférences professionnelles : {exc}")
    st.stop()

render_sidebar()

if st.session_state.get("show_contact_page"):
    render_header()
    st.subheader("Contacter Clarté360")
    contact_form_main()
    if st.button("← Retour à l’application"):
        st.session_state.show_contact_page = False; st.rerun()
    st.stop()
if st.session_state.get("show_rgpd_page"):
    rgpd_page()
    if st.button("← Retour à l’application"):
        st.session_state.show_rgpd_page = False; st.rerun()
    st.stop()

st.markdown(
    """
    <div class="objectif-box">
    <strong>Objectif de l'outil</strong><br>
    Cet outil permet d’explorer votre manière préférée de travailler à partir de situations professionnelles concrètes.
    Il ne s’agit pas d’analyser votre personnalité, mais de repérer vos préférences déclarées concernant l’autonomie,
    l’organisation, les relations professionnelles, la décision, l’action, le changement, l’environnement de travail,
    l’apprentissage, la contribution et les responsabilités. Les résultats servent de support d’échange avec votre consultant Clarté360.
    </div>
    <div class="clarte-box">
    <strong>🔒 Confidentialité et maîtrise de vos données</strong><br>
    Aucune réponse n'est enregistrée pendant la passation. En cas d'interruption, vous pouvez télécharger un JSON de sauvegarde
    et le conserver pour reprendre votre questionnaire. Le JSON final et le rapport PDF sont générés uniquement à la fin.
    Si l'envoi sécurisé est configuré, le JSON final est transmis à Clarté360 pour permettre l'analyse par le consultant.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Comprendre les 10 préférences explorées"):
    st.write("Ces dimensions sont présentées pour vous aider à comprendre le cadre général de l'outil. Pendant le questionnaire, les questions ne sont pas classées par dimension afin de préserver la spontanéité des réponses.")
    for label, description in DIMENSION_DESCRIPTIONS.items():
        st.markdown(f"**{label}** - {description}")

if not st.session_state.get("test_started"):
    st.markdown(f"<h2 style='color:{OFFICIAL_TEAL};'>1. Identification du bénéficiaire</h2>", unsafe_allow_html=True)
    st.write(
        "Ces informations seront intégrées au rapport PDF, au JSON de sauvegarde et au JSON final. "
        "L'adresse email est obligatoire : elle permet de recevoir le code d'accès au questionnaire. Clarté360 reçoit également une notification lorsqu'un code est généré."
    )

    if not st.session_state.get("code_sent"):
        with st.form("beneficiaire_form"):
            col1, col2 = st.columns(2)
            with col1:
                prenom = st.text_input("Prénom *")
            with col2:
                nom = st.text_input("Nom *")
            email = st.text_input("Adresse email *")
            with st.expander("Protection des données personnelles (RGPD)", expanded=True):
                st.markdown(RGPD_TEXT)
            consent = st.checkbox("J'ai lu et j'accepte les conditions RGPD de cette application Clarté360.")
            rgpd_consent = True
            send_code = st.form_submit_button("Recevoir mon code d'accès", type="primary")

        if send_code:
            if not prenom.strip() or not nom.strip() or not email.strip():
                st.error("Merci de renseigner le prénom, le nom et l'adresse email.")
            elif "@" not in email or "." not in email:
                st.error("Merci de renseigner une adresse email valide.")
            elif not consent:
                st.error("Le consentement RGPD est obligatoire avant toute utilisation.")
            else:
                beneficiaire_tmp = {"nom": nom.strip(), "prenom": prenom.strip(), "email": email.strip()}
                code = generate_access_code()
                ok, msg = send_access_code_email(beneficiaire_tmp, code)
                st.session_state.pending_beneficiaire = beneficiaire_tmp
                st.session_state.rgpd_consent_given = True
                st.session_state.rgpd_consent_at = now_iso()
                st.session_state.rgpd_acceptance = {"consentement": True, "date": datetime.now().strftime("%Y-%m-%d"), "heure": datetime.now().strftime("%H:%M:%S"), "version_texte": RGPD_TEXT_VERSION}
                ensure_access_tracking(user_activity=True)
                st.session_state.access.setdefault("code_history", []).append({"at": now_iso(), "email": email.strip(), "status": "generated", "app_version": APP_VERSION})
                st.session_state.access_code = code
                st.session_state.code_sent = ok
                st.session_state.code_message = msg
                if ok:
                    st.success("Un code d'accès vient d'être envoyé à l'adresse email indiquée.")
                    st.rerun()
                else:
                    st.error("Le code n'a pas pu être envoyé. Vérifiez la configuration SMTP dans Streamlit Secrets.")
                    st.caption(msg)
                    st.caption("En ligne, configurez les Secrets SMTP Streamlit pour activer l'envoi du code.")
    else:
        b = st.session_state.get("pending_beneficiaire", {})
        st.success(f"Code envoyé à : {b.get('email','')}")
        code_input = st.text_input("Saisissez le code d'accès reçu par email *", max_chars=6)
        col_a, col_b = st.columns([1, 1])
        with col_a:
            validate_code = st.button("Valider le code et démarrer", type="primary")
        with col_b:
            if st.button("Je n’ai pas reçu mon code"):
                new_code = generate_access_code()
                st.session_state.access_code = new_code
                ok, msg = send_access_code_email(b, new_code)
                ensure_access_tracking(user_activity=True)
                st.session_state.access["code_regenerated_count"] = int(st.session_state.access.get("code_regenerated_count",0)) + 1
                st.session_state.access.setdefault("code_history", []).append({"at": now_iso(), "email": b.get("email",""), "status": "regenerated_sent" if ok else "regenerated_error", "message": msg})
                st.success("Un nouveau code vient d’être envoyé.") if ok else st.error(msg)
            if st.button("Modifier l'adresse email"):
                for k in ["pending_beneficiaire", "access_code", "code_sent", "code_message", "code_verified"]:
                    st.session_state.pop(k, None)
                st.rerun()

        if validate_code:
            expected = str(st.session_state.get("access_code", "")).strip()
            if code_input.strip() == expected:
                st.session_state.code_verified = True
                ensure_access_tracking(user_activity=True)
                st.session_state.access["code_verified"] = True
                st.session_state.access["verified_at"] = now_iso()
                b = st.session_state.get("pending_beneficiaire", {})
                start_new_session(active_questions, nom=b.get("nom", ""), prenom=b.get("prenom", ""), email=b.get("email", ""))
                st.rerun()
            else:
                st.error("Code incorrect. Merci de vérifier le code reçu par email.")
    st.stop()

ensure_access_tracking(user_activity=True)
install_beforeunload_warning()
if beneficiary_has_timed_out():
    st.error("Session interrompue après 15 minutes sans activité. Téléchargez votre JSON puis reprenez avec ce fichier si nécessaire.")
    st.download_button("Télécharger mon JSON de reprise", data=json_download_bytes(build_progress_json()), file_name=f"clarte360_preferences_timeout_{current_name_part()}_{timestamp_part()}.json", mime="application/json")
    st.stop()
beneficiaire = st.session_state.get("beneficiaire", {})
st.markdown(f"**Bénéficiaire :** {beneficiaire.get('prenom','')} {beneficiaire.get('nom','')}")
answered = len(st.session_state.answers)
total = len(st.session_state.question_order)
progress = answered / total if total else 0
st.progress(progress)
st.write(f"{answered} réponse(s) enregistrée(s) sur {total}")

if answered < total:
    idx = st.session_state.current_index
    qid = st.session_state.question_order[idx]
    qrow = active_questions.set_index("ID").loc[qid]
    st.markdown(f"<h2 style='color:{OFFICIAL_TEAL};'>Question {idx + 1} / {total}</h2>", unsafe_allow_html=True)

    options = st.session_state.option_orders[qid]
    labels = {opt: str(qrow[f"Reponse {opt}"]) for opt in options}
    displayed_labels = [labels[opt] for opt in options]
    speech_text = build_speech_text(idx + 1, total, str(qrow["Question"]), displayed_labels)
    render_speech_button(speech_text)

    st.write(str(qrow["Question"]))
    selected_label = st.radio(
        "Choisissez la proposition qui vous correspond le mieux :",
        options=displayed_labels,
        index=None,
        key=f"radio_{qid}",
    )
    if st.button("Valider la réponse", type="primary", disabled=selected_label is None):
        selected_opt = next(opt for opt, label in labels.items() if label == selected_label)
        st.session_state.answers[qid] = selected_opt
        if st.session_state.current_index < total - 1:
            st.session_state.current_index += 1
        else:
            st.session_state.current_index = total
        st.rerun()
else:
    st.success("Questionnaire terminé.")
    results, score_details = compute_results(active_questions, st.session_state.answers)
    interpretation = build_user_interpretation(results, beneficiaire)

    st.markdown(f"<h2 style='color:{OFFICIAL_TEAL};'>Première lecture bénéficiaire</h2>", unsafe_allow_html=True)
    st.write(interpretation)

    bar_fig = plot_bar_results(results)
    radar_fig = plot_radar_results(results)
    st.pyplot(bar_fig)
    st.pyplot(radar_fig)
    plt.close(bar_fig)
    plt.close(radar_fig)

    st.markdown(f"<h2 style='color:{OFFICIAL_TEAL};'>Synthèse chiffrée</h2>", unsafe_allow_html=True)
    st.dataframe(
        results[["Dimension", "Pourcentage", "Lecture"]].sort_values("Pourcentage", ascending=False),
        hide_index=True,
        use_container_width=True,
    )

    export_payload = build_export_json(active_questions, results, score_details)
    name_part = current_name_part()
    passation_part = sanitize_filename(st.session_state.get("passation_id", "passation"))
    final_json_name = f"clarte360_preferences_professionnelles_{name_part}_{passation_part}_{timestamp_part()}.json"
    json_bytes = json_download_bytes(export_payload)

    if not st.session_state.get("email_sent"):
        ok, message = try_send_final_json(json_bytes, final_json_name, beneficiaire)
        st.session_state.email_sent = ok
        if ok:
            st.success(message)
        else:
            st.info(message)

    export_payload = build_export_json(active_questions, results, score_details)
    json_bytes = json_download_bytes(export_payload)
    pdf_bytes = make_pdf(results, interpretation, beneficiaire)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Télécharger le JSON final",
            data=json_bytes,
            file_name=final_json_name,
            mime="application/json",
        )
    with col2:
        st.download_button(
            "Télécharger le rapport PDF",
            data=pdf_bytes,
            file_name=f"clarte360_preferences_professionnelles_{name_part}_{timestamp_part()}.pdf",
            mime="application/pdf",
        )
