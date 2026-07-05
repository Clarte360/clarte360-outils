import json
import hashlib
import random
import re
import smtplib
import uuid
from datetime import datetime
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

APP_VERSION = "1.10.0-socle-clarte360"
SOCLE_CLARTE360_VERSION = "1.8"
APP_NAME = "Préférences professionnelles"
APP_FULL_NAME = "Clarté360 – Préférences professionnelles"
RGPD_TEXT_VERSION = "RGPD-Clarte360-v1.0-2026-07"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_XLSX = BASE_DIR / "data" / "questions_preferences_professionnelles_v1.xlsx"
LOGO_PATH = BASE_DIR / "assets" / "site_icon.png"
RANDOMIZE_OPTIONS = True
FINAL_EMAIL_TO = "contact@clarte360.com"

st.set_page_config(
    page_title="Clarté360 - Préférences professionnelles",
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
    # L'échec de la notification administrateur ne bloque jamais l'application.

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

    if ok_admin:
        return True, "Code envoyé au bénéficiaire et notification transmise à Clarté360."
    return True, "Code envoyé au bénéficiaire. Notification Clarté360 non bloquante : " + msg_admin

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
        "nom_outil": APP_FULL_NAME,
        "app_version": APP_VERSION,
        "version_socle_clarte360": SOCLE_CLARTE360_VERSION,
        "session_id": st.session_state.get("session_id", ""),
        "passation_id": st.session_state.get("passation_id", st.session_state.get("session_id", "")),
        "beneficiaire": {
            "nom": beneficiaire.get("nom", ""),
            "prenom": beneficiaire.get("prenom", ""),
            "email": beneficiaire.get("email", ""),
            "consultant": beneficiaire.get("consultant", ""),
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
        "rgpd": rgpd_payload(),
        "temps": session_meta(),
        "code_access_history": st.session_state.get("code_history", []),
        "notice_rgpd": "Aucune donnée n’est enregistrée durablement sur un serveur Clarté360. Le JSON appartient au bénéficiaire.",
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
        story.append(Image(str(LOGO_PATH), width=2.0*cm, height=2.0*cm))
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
    story.append(Paragraph(legal_footer_text(), styles["Italic"]))
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




###############################################################################
# SOCLE CLARTE360 v1.8 - composants institutionnels et session
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
DEFAULT_SESSION_LIMIT_MINUTES = 15

RGPD_TEXT = f"""
### Protection des données personnelles (RGPD)

Cette application Clarté360 fonctionne sans base de données serveur propre à l'application. Aucune donnée n'est enregistrée durablement sur un serveur Clarté360 par l'application.

Le fichier JSON constitue le support principal de conservation de votre travail. Il peut contenir votre identité, votre adresse e-mail, le nom de votre accompagnateur si l'application le prévoit, les dates et heures de connexion, la durée des sessions, vos données saisies dans l'application, vos réponses, résultats, historique de connexion, code d'accès généré, historique des régénérations, consentement RGPD, version de l'application et informations techniques disponibles.

Le fichier JSON appartient exclusivement au bénéficiaire. Vous choisissez librement de le conserver, de le supprimer ou de le transmettre à votre accompagnateur. Si vous le transmettez à votre accompagnateur, celui-ci l'utilise exclusivement dans le cadre du bilan de compétences ou de l'accompagnement Clarté360.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : {RGPD_TEXT_VERSION}.

### Nature des résultats

Les résultats fournis par les applications Clarté360 constituent des supports d'aide à la réflexion et à l'accompagnement. Ils ne constituent ni un diagnostic psychologique, ni un avis médical, ni une décision d'orientation automatique. Leur interprétation s'inscrit dans un dialogue avec le bénéficiaire et, lorsque cela est prévu, avec un professionnel de l'accompagnement.

### Propriété intellectuelle

Les applications, outils, questionnaires, méthodes, graphiques, rapports et contenus proposés par Clarté360 constituent des créations originales protégées. Toute reproduction, adaptation, diffusion ou réutilisation, totale ou partielle, sans autorisation écrite préalable de Clarté360, est interdite.
"""

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def get_session_limit_minutes() -> int:
    try:
        return int(st.secrets.get("security", {}).get("session_limit_minutes", DEFAULT_SESSION_LIMIT_MINUTES))
    except Exception:
        return DEFAULT_SESSION_LIMIT_MINUTES

def inject_beforeunload_guard():
    components.html("""
    <script>
    window.parent.addEventListener('beforeunload', function (e) {
      e.preventDefault();
      e.returnValue = 'Quitter le site ? Vos modifications risquent de ne pas être enregistrées.';
      return e.returnValue;
    });
    </script>
    """, height=0)

def init_runtime_session(reason="nouvelle_session"):
    sid = str(uuid.uuid4())
    st.session_state.current_runtime_session_id = sid
    st.session_state.session_started_at = now_iso()
    st.session_state.session_last_activity = now_iso()
    st.session_state.session_last_heartbeat = now_iso()
    st.session_state.session_expired = False
    st.session_state.exit_json_ready = False
    hist = st.session_state.get("session_history", [])
    hist.append({"session_uid": sid, "debut": now_iso(), "raison": reason, "duree_secondes": 0})
    st.session_state.session_history = hist

def update_runtime_session():
    if not st.session_state.get("current_runtime_session_id"):
        init_runtime_session("initialisation")
    now = datetime.now()
    last_iso = st.session_state.get("session_last_heartbeat") or now_iso()
    try:
        last = datetime.fromisoformat(last_iso)
    except Exception:
        last = now
    delta = max(0, min(int((now - last).total_seconds()), 60))
    st.session_state.session_elapsed_seconds = int(st.session_state.get("session_elapsed_seconds", 0)) + delta
    st.session_state.session_last_heartbeat = now_iso()
    st.session_state.session_last_activity = now_iso()
    if st.session_state.get("session_history"):
        st.session_state.session_history[-1]["derniere_activite"] = now_iso()
        st.session_state.session_history[-1]["duree_secondes"] = int(st.session_state.get("session_elapsed_seconds", 0))
    limit = get_session_limit_minutes() * 60
    if int(st.session_state.get("session_elapsed_seconds", 0)) >= limit:
        st.session_state.session_expired = True

def formatted_elapsed(seconds: int | None = None) -> str:
    seconds = int(seconds if seconds is not None else st.session_state.get("session_elapsed_seconds", 0))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}min"
    return f"{m}min {s:02d}s"

def legal_footer_text() -> str:
    return (f"{CLARTE360_LEGAL['raison_sociale']} - {CLARTE360_LEGAL['adresse']} - "
            f"{CLARTE360_LEGAL['code_postal_ville']} - Tél. : {CLARTE360_LEGAL['telephone']} - "
            f"E-mail : {CLARTE360_LEGAL['email']} - Web : {CLARTE360_LEGAL['web']} - "
            f"RCS : {CLARTE360_LEGAL['rcs']} - SIRET : {CLARTE360_LEGAL['siret']} - "
            f"NAF : {CLARTE360_LEGAL['naf']} - TVA : {CLARTE360_LEGAL['tva']}")

def session_meta() -> dict:
    return {
        "session_uid": st.session_state.get("current_runtime_session_id", ""),
        "session_started_at": st.session_state.get("session_started_at", ""),
        "session_last_activity": st.session_state.get("session_last_activity", ""),
        "session_elapsed_seconds": int(st.session_state.get("session_elapsed_seconds", 0)),
        "session_elapsed_human": formatted_elapsed(),
        "session_limit_minutes": get_session_limit_minutes(),
        "session_expired": bool(st.session_state.get("session_expired", False)),
        "session_history": st.session_state.get("session_history", []),
    }

def rgpd_payload() -> dict:
    return st.session_state.get("rgpd", {
        "accepted": False,
        "accepted_at": "",
        "text_version": RGPD_TEXT_VERSION,
    })

def render_rgpd_mentions_contact():
    st.markdown(f"<h2 style='color:{OFFICIAL_TEAL};'>Informations légales et protection des données</h2>", unsafe_allow_html=True)
    tabs = st.tabs(["Protection des données", "Mentions légales", "Nous contacter"])
    with tabs[0]:
        st.markdown(RGPD_TEXT)
    with tabs[1]:
        st.markdown(f"""
        **{CLARTE360_LEGAL['raison_sociale']} {CLARTE360_LEGAL['forme']}**  
        {CLARTE360_LEGAL['adresse']}  
        {CLARTE360_LEGAL['code_postal_ville']}  
        Tél. : {CLARTE360_LEGAL['telephone']}  
        E-mail : {CLARTE360_LEGAL['email']}  
        Web : {CLARTE360_LEGAL['web']}  
        RCS : {CLARTE360_LEGAL['rcs']}  
        SIRET : {CLARTE360_LEGAL['siret']}  
        NAF : {CLARTE360_LEGAL['naf']}  
        TVA intracommunautaire : {CLARTE360_LEGAL['tva']}

        Les contenus de l'application sont protégés au titre de la propriété intellectuelle. Les résultats produits sont des supports d'échange et ne constituent pas une décision automatique.
        """)
    with tabs[2]:
        render_contact_form(context="institutionnel")

def render_contact_form(context="sidebar"):
    b = st.session_state.get("beneficiaire", {}) or st.session_state.get("pending_beneficiaire", {}) or {}
    st.write("Vous pouvez nous adresser une question administrative, signaler un problème technique ou nous faire part d’une suggestion concernant cette application.")
    st.write("Pour toute question relative à l’interprétation des exercices ou des résultats, rapprochez-vous de votre consultant ou accompagnateur.")
    with st.form(f"contact_form_{context}"):
        col1, col2 = st.columns(2)
        with col1:
            prenom = st.text_input("Prénom", value=b.get("prenom", ""), key=f"contact_prenom_{context}")
        with col2:
            nom = st.text_input("Nom", value=b.get("nom", ""), key=f"contact_nom_{context}")
        email = st.text_input("E-mail", value=b.get("email", ""), key=f"contact_email_{context}")
        tel = st.text_input("Téléphone facultatif", key=f"contact_tel_{context}")
        objet = st.text_input("Objet", key=f"contact_objet_{context}")
        message = st.text_area("Message", key=f"contact_message_{context}")
        consent = st.checkbox("J'accepte que ces informations soient utilisées pour traiter ma demande.", key=f"contact_consent_{context}")
        submit = st.form_submit_button("Envoyer ma demande à Clarté360", type="primary")
    if submit:
        if not email.strip() or not objet.strip() or not message.strip() or not consent:
            st.error("Merci de renseigner l'e-mail, l'objet, le message et le consentement.")
        else:
            body = f"""Demande transmise depuis {APP_FULL_NAME}

Nom : {nom}
Prénom : {prenom}
E-mail : {email}
Téléphone : {tel}
Objet : {objet}
Message :
{message}

Application : {APP_NAME}
Version : {APP_VERSION}
Socle : {SOCLE_CLARTE360_VERSION}
Date : {now_iso()}
Session : {st.session_state.get('current_runtime_session_id','')}
Temps session : {formatted_elapsed()}
Passation : {st.session_state.get('passation_id','')}
"""
            ok, msg = send_email(FINAL_EMAIL_TO, f"Clarté360 - Contact - {objet}", body)
            if ok:
                st.success("Votre message a été transmis à Clarté360.")
            else:
                st.info("Le message n'a pas pu être envoyé automatiquement. Vous pouvez écrire à contact@clarte360.com.")
                st.caption(msg)

def render_sidebar_common(active_questions=None):
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=86)
        st.markdown(f"### {APP_NAME}")
        st.caption(f"Version application : {APP_VERSION}")
        st.caption(f"Socle Clarté360 : {SOCLE_CLARTE360_VERSION}")
        st.caption(f"Temps de session : {formatted_elapsed()}")
        if st.session_state.get("test_started") and active_questions is not None:
            st.markdown("---")
            st.markdown("### Sauvegarde / sortie")
            progress_payload = build_progress_json()
            st.download_button(
                "Préparer mon JSON pour reprendre plus tard",
                data=json_download_bytes(progress_payload),
                file_name=f"clarte360_preferences_sauvegarde_{current_name_part()}_{timestamp_part()}.json",
                mime="application/json",
                key="sidebar_prepare_json",
            )
            st.download_button(
                "Quitter et télécharger mon JSON",
                data=json_download_bytes(progress_payload),
                file_name=f"clarte360_preferences_sortie_{current_name_part()}_{timestamp_part()}.json",
                mime="application/json",
                key="sidebar_exit_json",
            )
            if st.button("Réinitialiser la session"):
                reset_all()
        st.markdown("---")
        if st.button("RGPD et mentions légales"):
            st.session_state.page = "legal"
            st.rerun()
        if st.button("Contacter Clarté360"):
            st.session_state.show_contact_sidebar = not st.session_state.get("show_contact_sidebar", False)
        if st.session_state.get("show_contact_sidebar"):
            render_contact_form(context="sidebar")

def render_landing(active_questions):
    render_header()
    st.markdown("""
    <div class="objectif-box">
    <strong>Objectif de l'outil</strong><br>
    Cet outil permet d’explorer votre manière préférée de travailler à partir de situations professionnelles concrètes.
    Il ne s’agit pas d’analyser votre personnalité, mais de repérer vos préférences déclarées concernant l’autonomie,
    l’organisation, les relations professionnelles, la décision, l’action, le changement, l’environnement de travail,
    l’apprentissage, la contribution et les responsabilités. Les résultats servent de support d’échange avec votre consultant Clarté360.
    </div>
    """, unsafe_allow_html=True)
    st.markdown("### Reprendre ou commencer")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Importer mon fichier JSON")
        f = st.file_uploader("JSON de sauvegarde", type=["json"], key="landing_resume_json")
        if f is not None:
            try:
                payload = json.loads(f.getvalue().decode("utf-8"))
                if payload.get("outil") != "clarte360_preferences_professionnelles":
                    st.error("Ce fichier JSON ne correspond pas à cet outil.")
                elif payload.get("completed") is True:
                    st.error("Ce JSON correspond à un questionnaire déjà terminé.")
                else:
                    restore_from_progress(payload)
                    init_runtime_session("reprise_json")
                    st.session_state.page = "app"
                    st.success("Sauvegarde chargée. Reprise du questionnaire.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Impossible de charger la sauvegarde : {exc}")
    with col2:
        st.markdown("#### Commencer une nouvelle session")
        if st.button("Commencer une nouvelle session", type="primary", use_container_width=True):
            st.session_state.page = "identification"
            init_runtime_session("nouvelle_session")
            st.rerun()
    with st.expander("Comprendre les 10 préférences explorées"):
        for label, description in DIMENSION_DESCRIPTIONS.items():
            st.markdown(f"**{label}** - {description}")

def accept_rgpd_if_needed():
    if st.session_state.get("rgpd", {}).get("accepted"):
        return True
    st.markdown(f"<h2 style='color:{OFFICIAL_TEAL};'>Consentement RGPD obligatoire</h2>", unsafe_allow_html=True)
    st.markdown(RGPD_TEXT)
    accept = st.checkbox("J'ai lu et j'accepte les conditions d'utilisation et de protection des données.")
    if st.button("Valider le consentement", type="primary"):
        if accept:
            st.session_state.rgpd = {"accepted": True, "accepted_at": now_iso(), "text_version": RGPD_TEXT_VERSION}
            st.rerun()
        else:
            st.error("Le consentement est nécessaire pour utiliser l'application.")
    return False


# Chargement données
questions_df, dimensions_df = load_workbook_from_source(None, DEFAULT_XLSX.stat().st_mtime if DEFAULT_XLSX.exists() else 0)
validation_errors = validate_questionnaire(questions_df)

# Socle visuel et protection navigateur
inject_beforeunload_guard()
update_runtime_session()

if validation_errors:
    render_header()
    st.error("Le questionnaire source contient des erreurs. Merci de corriger le fichier Excel dans le dossier data/ puis de redéployer l'application.")
    for err in validation_errors:
        st.write("- " + err)
    st.stop()

active_questions = get_active_questions(questions_df)
render_sidebar_common(active_questions if st.session_state.get("test_started") else None)

if st.session_state.get("session_expired"):
    render_header()
    st.warning("La session est arrivée au délai de sécurité. Téléchargez votre JSON pour reprendre plus tard.")
    st.download_button(
        "Quitter et télécharger mon JSON",
        data=json_download_bytes(build_progress_json()),
        file_name=f"clarte360_preferences_timeout_{current_name_part()}_{timestamp_part()}.json",
        mime="application/json",
        type="primary",
    )
    st.stop()

page = st.session_state.get("page", "landing")
if page == "legal":
    render_header()
    render_rgpd_mentions_contact()
    if st.button("Retour vers l'application", type="primary"):
        st.session_state.page = "app" if st.session_state.get("test_started") else "landing"
        st.rerun()
    st.stop()

if page == "landing" and not st.session_state.get("test_started"):
    render_landing(active_questions)
    st.stop()

if not st.session_state.get("test_started"):
    render_header()
    if not accept_rgpd_if_needed():
        st.stop()
    st.markdown(f"<h2 style='color:{OFFICIAL_TEAL};'>Identification du bénéficiaire</h2>", unsafe_allow_html=True)
    st.write("Ces informations seront intégrées au rapport PDF, au JSON de sauvegarde et au JSON final.")
    if not st.session_state.get("code_sent"):
        with st.form("beneficiaire_form"):
            col1, col2 = st.columns(2)
            with col1:
                prenom = st.text_input("Prénom *")
            with col2:
                nom = st.text_input("Nom *")
            email = st.text_input("Adresse e-mail *")
            consultant = st.text_input("Consultant / accompagnateur", value="")
            consent = st.checkbox("Je comprends que cet outil est un support d’exploration et non un test psychométrique.")
            send_code = st.form_submit_button("Recevoir mon code d'accès", type="primary")
        if send_code:
            if not prenom.strip() or not nom.strip() or not email.strip():
                st.error("Merci de renseigner le prénom, le nom et l'adresse e-mail.")
            elif "@" not in email or "." not in email:
                st.error("Merci de renseigner une adresse e-mail valide.")
            elif not consent:
                st.error("Merci de confirmer la compréhension du cadre d’utilisation.")
            else:
                beneficiaire_tmp = {"nom": nom.strip(), "prenom": prenom.strip(), "email": email.strip(), "consultant": consultant.strip()}
                code = generate_access_code()
                ok, msg = send_access_code_email(beneficiaire_tmp, code)
                hist = st.session_state.get("code_history", [])
                hist.append({"generated_at": now_iso(), "status": "envoye" if ok else "erreur", "message": msg, "regeneration_number": len(hist)})
                st.session_state.code_history = hist
                st.session_state.pending_beneficiaire = beneficiaire_tmp
                st.session_state.access_code = code
                st.session_state.code_sent = ok
                st.session_state.code_message = msg
                if ok:
                    st.success("Un code d'accès vient d'être envoyé à l'adresse e-mail indiquée.")
                    st.rerun()
                else:
                    st.error("Le code n'a pas pu être envoyé. Vérifiez la configuration SMTP dans Streamlit Secrets.")
                    st.caption(msg)
    else:
        b = st.session_state.get("pending_beneficiaire", {})
        st.success(f"Code envoyé à : {b.get('email','')}")
        code_input = st.text_input("Saisissez le code d'accès reçu par e-mail *", max_chars=6)
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            validate_code = st.button("Valider le code et démarrer", type="primary")
        with col_b:
            resend = st.button("Je n’ai pas reçu mon code")
        with col_c:
            change = st.button("Modifier l'adresse e-mail")
        if resend:
            code = generate_access_code()
            ok, msg = send_access_code_email(b, code)
            hist = st.session_state.get("code_history", [])
            hist.append({"generated_at": now_iso(), "status": "envoye" if ok else "erreur", "message": msg, "regeneration_number": len(hist)})
            st.session_state.code_history = hist
            st.session_state.access_code = code
            if ok:
                st.success("Un nouveau code vient d'être envoyé.")
            else:
                st.error(msg)
        if change:
            for k in ["pending_beneficiaire", "access_code", "code_sent", "code_message", "code_verified"]:
                st.session_state.pop(k, None)
            st.rerun()
        if validate_code:
            expected = str(st.session_state.get("access_code", "")).strip()
            if code_input.strip() == expected:
                st.session_state.code_verified = True
                st.session_state.code_verified_at = now_iso()
                b = st.session_state.get("pending_beneficiaire", {})
                start_new_session(active_questions, nom=b.get("nom", ""), prenom=b.get("prenom", ""), email=b.get("email", ""))
                st.session_state.beneficiaire["consultant"] = b.get("consultant", "")
                st.session_state.page = "app"
                st.rerun()
            else:
                st.error("Code incorrect. Merci de vérifier le code reçu par e-mail.")
    st.stop()

# Application questionnaire
render_header()
st.markdown("""
<div class="clarte-box">
<strong>🔒 Sauvegarde et reprise</strong><br>
Vous pouvez à tout moment préparer votre JSON pour reprendre plus tard. Le fichier JSON appartient au bénéficiaire.
</div>
""", unsafe_allow_html=True)

beneficiaire = st.session_state.get("beneficiaire", {})
st.markdown(f"**Bénéficiaire :** {beneficiaire.get('prenom','')} {beneficiaire.get('nom','')}")
st.caption(f"Identifiant de passation : {st.session_state.get('passation_id','')}")
answered = len(st.session_state.answers)
total = len(st.session_state.question_order)
progress = answered / total if total else 0
st.progress(progress)
st.write(f"{answered} réponse(s) enregistrée(s) sur {total}")

if answered < total:
    idx = st.session_state.current_index
    qid = st.session_state.question_order[idx]
    qrow = active_questions.set_index("ID").loc[qid]
    st.markdown(f"<div class='question-title'>Question {idx + 1} / {total}</div>", unsafe_allow_html=True)
    options = st.session_state.option_orders[qid]
    labels = {opt: str(qrow[f"Reponse {opt}"]) for opt in options}
    displayed_labels = [labels[opt] for opt in options]
    speech_text = build_speech_text(idx + 1, total, str(qrow["Question"]), displayed_labels)
    render_speech_button(speech_text)
    st.markdown(f"<div class='clarte-card'><strong>{str(qrow['Question'])}</strong></div>", unsafe_allow_html=True)
    selected_label = st.radio("Choisissez la proposition qui vous correspond le mieux :", options=displayed_labels, index=None, key=f"radio_{qid}")
    if st.button("Valider la réponse", type="primary", disabled=selected_label is None):
        selected_opt = next(opt for opt, label in labels.items() if label == selected_label)
        st.session_state.answers[qid] = selected_opt
        st.session_state.current_index = min(st.session_state.current_index + 1, total)
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
    plt.close(bar_fig); plt.close(radar_fig)
    st.markdown(f"<h2 style='color:{OFFICIAL_TEAL};'>Synthèse chiffrée</h2>", unsafe_allow_html=True)
    st.dataframe(results[["Dimension", "Pourcentage", "Lecture"]].sort_values("Pourcentage", ascending=False), hide_index=True, use_container_width=True)
    export_payload = build_export_json(active_questions, results, score_details)
    name_part = current_name_part()
    passation_part = sanitize_filename(st.session_state.get("passation_id", "passation"))
    final_json_name = f"clarte360_preferences_professionnelles_{name_part}_{passation_part}_{timestamp_part()}.json"
    json_bytes = json_download_bytes(export_payload)
    if not st.session_state.get("email_sent"):
        ok, message = try_send_final_json(json_bytes, final_json_name, beneficiaire)
        st.session_state.email_sent = ok
        if ok: st.success(message)
        else: st.info(message)
    export_payload = build_export_json(active_questions, results, score_details)
    json_bytes = json_download_bytes(export_payload)
    pdf_bytes = make_pdf(results, interpretation, beneficiaire)
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Télécharger le JSON final", data=json_bytes, file_name=final_json_name, mime="application/json")
    with col2:
        st.download_button("Télécharger le rapport PDF", data=pdf_bytes, file_name=f"clarte360_preferences_professionnelles_{name_part}_{timestamp_part()}.pdf", mime="application/pdf")
