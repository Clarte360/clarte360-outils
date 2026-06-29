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

APP_VERSION = "1.6.0"
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
        "started_at", "beneficiaire", "test_started", "email_sent", "pending_beneficiaire",
        "verification_code", "code_sent", "code_status"
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


def generate_verification_code() -> str:
    return str(random.randint(100000, 999999))


def get_email_config():
    try:
        cfg = st.secrets.get("email", None)
    except Exception:
        return None
    return cfg


def send_email(to_email: str, subject: str, body: str, attachment: bytes | None = None, attachment_name: str | None = None) -> tuple[bool, str]:
    cfg = get_email_config()
    if not cfg:
        return False, "Email non configuré dans Streamlit Secrets."
    smtp_host = cfg.get("smtp_server") or cfg.get("smtp_host")
    smtp_port = int(cfg.get("smtp_port", 465))
    smtp_user = cfg.get("smtp_user")
    smtp_password = cfg.get("smtp_password")
    from_email = cfg.get("from_email", smtp_user)
    if not all([smtp_host, smtp_port, smtp_user, smtp_password, from_email]):
        return False, "Configuration SMTP incomplète."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)
    if attachment is not None and attachment_name:
        msg.add_attachment(attachment, maintype="application", subtype="json", filename=attachment_name)
    try:
        # Port 465 : SSL direct. Port 587 : STARTTLS.
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as smtp:
                smtp.login(smtp_user, smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
                if bool(cfg.get("use_tls", True)):
                    smtp.starttls()
                smtp.login(smtp_user, smtp_password)
                smtp.send_message(msg)
        return True, "Email envoyé."
    except Exception as exc:
        return False, f"Envoi email impossible : {exc}"


def send_access_code(beneficiaire: dict, code: str) -> tuple[bool, str]:
    email = beneficiaire.get("email", "").strip()
    prenom = beneficiaire.get("prenom", "")
    nom = beneficiaire.get("nom", "")
    if not email:
        return False, "Adresse email manquante."
    subject_user = "Votre code Clarté360 - Préférences professionnelles"
    body_user = (
        f"Bonjour {prenom},\n\n"
        f"Votre code d'accès au questionnaire Clarté360 - Préférences professionnelles est : {code}\n\n"
        "Ce code vous permet de démarrer votre passation.\n\n"
        "Clarté360"
    )
    ok_user, msg_user = send_email(email, subject_user, body_user)
    # Notification interne à Clarté360. Non bloquante si l'envoi au bénéficiaire a réussi.
    subject_admin = "Clarté360 - Code d'accès généré"
    body_admin = (
        "Un code d'accès vient d'être généré pour l'outil Préférences professionnelles.\n\n"
        f"Bénéficiaire : {prenom} {nom}\n"
        f"Email : {email}\n"
        f"Code : {code}\n"
        f"Date : {datetime.now().isoformat(timespec='seconds')}\n"
        "Le JSON final sera transmis automatiquement à la fin si l'envoi SMTP est configuré."
    )
    send_email(FINAL_EMAIL_TO, subject_admin, body_admin)
    return ok_user, msg_user


def base_export_payload(completed: bool) -> dict:
    beneficiaire = st.session_state.get("beneficiaire", {})
    return {
        "outil": "clarte360_preferences_professionnelles",
        "app_version": APP_VERSION,
        "session_id": st.session_state.get("session_id", ""),
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
        "rgpd": "Aucune donnée n’est enregistrée sur un serveur par l’application locale. Le JSON appartient au bénéficiaire.",
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
    ok, msg = send_email(FINAL_EMAIL_TO, subject, body, attachment=json_bytes, attachment_name=file_name)
    if ok:
        return True, "JSON final transmis automatiquement à Clarté360."
    return False, msg


questionnaire_bytes = None
questions_df, dimensions_df = load_workbook_from_source(None, DEFAULT_XLSX.stat().st_mtime if DEFAULT_XLSX.exists() else 0)
validation_errors = validate_questionnaire(questions_df)

render_header()

if validation_errors:
    st.error("Le questionnaire source contient des erreurs. Merci de corriger le fichier Excel dans le dossier data/ puis de redéployer l'application.")
    for err in validation_errors:
        st.write("- " + err)
    st.stop()

active_questions = get_active_questions(questions_df)

with st.sidebar:
    st.markdown("### Interrompre / reprendre")
    if st.session_state.get("test_started") and len(st.session_state.get("answers", {})) < len(st.session_state.get("question_order", [])):
        progress_payload = build_progress_json()
        st.download_button(
            "💾 Interrompre et télécharger ma sauvegarde JSON",
            data=json_download_bytes(progress_payload),
            file_name=f"clarte360_preferences_sauvegarde_{current_name_part()}_{timestamp_part()}.json",
            mime="application/json",
        )
        st.caption("Conservez ce fichier JSON : il permettra de reprendre exactement à la question suivante.")
    resume_file = st.file_uploader("Reprendre avec un JSON de sauvegarde", type=["json"], key="resume_json")
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
    st.caption(f"Version de l'application : {APP_VERSION}")
    st.caption("Questionnaire : questions_preferences_professionnelles_v1.xlsx")
    st.caption(f"Empreinte : {questionnaire_checksum()}")

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
    st.write("Ces informations seront intégrées au rapport PDF, au JSON de sauvegarde et au JSON final. L'adresse email permet de transmettre un code d'accès au questionnaire.")

    with st.form("beneficiaire_form"):
        col1, col2 = st.columns(2)
        with col1:
            prenom = st.text_input("Prénom *", value=st.session_state.get("pending_beneficiaire", {}).get("prenom", ""))
        with col2:
            nom = st.text_input("Nom *", value=st.session_state.get("pending_beneficiaire", {}).get("nom", ""))
        email = st.text_input("Adresse email *", value=st.session_state.get("pending_beneficiaire", {}).get("email", ""))
        consent = st.checkbox("Je comprends que cet outil est un support d’exploration et non un test psychométrique.")
        request_code = st.form_submit_button("Recevoir mon code d'accès", type="primary")

    if request_code:
        if not prenom.strip() or not nom.strip() or not email.strip():
            st.error("Merci de renseigner le prénom, le nom et l'adresse email.")
        elif "@" not in email or "." not in email:
            st.error("Merci de renseigner une adresse email valide.")
        elif not consent:
            st.error("Merci de confirmer la compréhension du cadre d’utilisation.")
        else:
            code = generate_verification_code()
            beneficiaire_tmp = {"nom": nom.strip(), "prenom": prenom.strip(), "email": email.strip()}
            st.session_state.pending_beneficiaire = beneficiaire_tmp
            st.session_state.verification_code = code
            ok, msg = send_access_code(beneficiaire_tmp, code)
            st.session_state.code_sent = True
            st.session_state.code_status = msg
            if ok:
                st.success("Un code d'accès vient d'être envoyé par email.")
            else:
                st.warning("Email non envoyé automatiquement. Mode local ou SMTP non configuré.")
                st.info(f"Code de test local : {code}")
            st.rerun()

    if st.session_state.get("code_sent"):
        st.markdown(f"<h3 style='color:{OFFICIAL_TEAL};'>2. Saisir le code reçu</h3>", unsafe_allow_html=True)
        if st.session_state.get("code_status"):
            st.caption(st.session_state.code_status)
        with st.form("code_form"):
            entered_code = st.text_input("Code d'accès *")
            start = st.form_submit_button("Commencer le questionnaire", type="primary")
        if start:
            if entered_code.strip() != str(st.session_state.get("verification_code", "")):
                st.error("Code incorrect. Merci de vérifier le code reçu.")
            else:
                b = st.session_state.get("pending_beneficiaire", {})
                start_new_session(active_questions, nom=b.get("nom", ""), prenom=b.get("prenom", ""), email=b.get("email", ""))
                st.rerun()
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
