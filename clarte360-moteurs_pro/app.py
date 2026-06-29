import json
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

APP_VERSION = "1.0.0"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_XLSX = BASE_DIR / "data" / "moteurs_professionnels_curseurs_v0_1.xlsx"
LOGO_PATH = BASE_DIR / "assets" / "site_icon.png"
FINAL_EMAIL_TO = "contact@clarte360.com"

st.set_page_config(
    page_title="Clarté360 - Moteurs professionnels",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🟢",
    layout="centered",
)

st.markdown(f"""
<style>
:root {{ --clarte-teal: {OFFICIAL_TEAL}; }}
.stProgress > div > div > div > div {{ background-color: {OFFICIAL_TEAL}; }}
h1, h2, h3 {{ color: {OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"] {{ background-color: {OFFICIAL_TEAL}; border-color: {OFFICIAL_TEAL}; }}
.clarte-box {{ border-left: 6px solid {OFFICIAL_TEAL}; background: {LIGHT_TEAL}; padding: 1rem 1.1rem; border-radius: .55rem; margin: 1rem 0; color: {DARK_TEXT}; }}
.objectif-box {{ border: 1px solid #cfe6e6; background: #f8fbfb; padding: 1.2rem 1.4rem; border-radius: .9rem; margin: 1rem 0 1.4rem 0; color: {DARK_TEXT}; }}
.clarte-card {{ border: 1px solid #d9eeee; border-radius: .8rem; padding: 1rem; background: #fff; box-shadow: 0 1px 8px rgba(0,128,128,.08); margin-bottom: 1rem; }}
.slider-card-left {{ border-left: 6px solid {OFFICIAL_TEAL}; padding: .85rem 1rem; background: #f8fbfb; border-radius: .7rem; min-height: 100px; }}
.slider-card-right {{ border-left: 6px solid #9bc7c7; padding: .85rem 1rem; background: #f8fbfb; border-radius: .7rem; min-height: 100px; }}
.small-muted {{ color:#666; font-size:.9rem; }}
/* Masquer autant que possible les valeurs numériques du slider Streamlit */
div[data-testid="stSlider"] label, div[data-testid="stSlider"] [data-testid="stTickBar"], div[data-testid="stSlider"] div[role="slider"] + div {{ visibility: hidden !important; }}
</style>
""", unsafe_allow_html=True)

REQUIRED_CURSOR_COLUMNS = ["ID", "Situation / consigne", "Proposition gauche", "Proposition droite", "Moteur gauche", "Moteur droite", "Position défaut", "Statut", "Version"]

MOTEUR_FALLBACK = {
    "MP1": "Accomplir",
    "MP2": "Comprendre",
    "MP3": "Construire",
    "MP4": "Transmettre",
    "MP5": "Être utile",
    "MP6": "Influencer",
    "MP7": "Innover",
    "MP8": "Coopérer",
    "MP9": "Progresser",
    "MP10": "Contribuer",
}


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
        port = int(e["smtp_port"])
        with smtplib.SMTP_SSL(e["smtp_server"], port, timeout=25) as server:
            server.login(e["smtp_user"], e["smtp_password"])
            server.send_message(msg)
        return True, "Email envoyé."
    except Exception as exc:
        return False, f"Erreur email : {exc}"


def start_new_session(active: pd.DataFrame, nom: str, prenom: str, email: str):
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.passation_id = f"CL360-MP-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{st.session_state.session_id[:8].upper()}"
    ids = active["ID"].tolist()
    random.shuffle(ids)
    st.session_state.cursor_order = ids
    st.session_state.positions = {}
    st.session_state.current_index = 0
    st.session_state.started_at = datetime.now().isoformat(timespec="seconds")
    st.session_state.beneficiaire = {"nom": nom.strip(), "prenom": prenom.strip(), "email": email.strip()}
    st.session_state.test_started = True
    st.session_state.final_email_sent = False


def restore_from_progress(payload: dict):
    st.session_state.session_id = payload.get("session_id", str(uuid.uuid4()))
    st.session_state.passation_id = payload.get("passation_id", st.session_state.session_id)
    st.session_state.cursor_order = payload.get("cursor_order_displayed", payload.get("cursor_order", []))
    st.session_state.positions = {str(k): int(v) for k, v in payload.get("positions", {}).items()}
    first_unanswered = None
    for i, cid in enumerate(st.session_state.cursor_order):
        if cid not in st.session_state.positions:
            first_unanswered = i
            break
    st.session_state.current_index = first_unanswered if first_unanswered is not None else len(st.session_state.cursor_order)
    st.session_state.started_at = payload.get("started_at", datetime.now().isoformat(timespec="seconds"))
    st.session_state.beneficiaire = payload.get("beneficiaire", {})
    st.session_state.test_started = True
    st.session_state.final_email_sent = bool(payload.get("final_email_sent", False))
    st.session_state.code_verified = True


def reset_all():
    for key in list(st.session_state.keys()):
        if key not in []:
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
        details.append({
            "cursor_id": cid,
            "position": pos,
            "situation": row["Situation / consigne"],
            "proposition_gauche": row["Proposition gauche"],
            "proposition_droite": row["Proposition droite"],
            "moteur_gauche": left,
            "moteur_droite": right,
            "points_gauche": left_pts,
            "points_droite": right_pts,
        })
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
    scores_df, score_details = compute_results(active, dims, st.session_state.get("positions", {}))
    payload = {
        "outil": get_param(params, "outil_code", "clarte360_moteurs_professionnels"),
        "outil_nom": get_param(params, "outil_nom", "Clarté360 – Moteurs professionnels"),
        "app_version": APP_VERSION,
        "version_questionnaire": get_param(params, "version_questionnaire", "0.1"),
        "session_id": st.session_state.get("session_id", ""),
        "passation_id": st.session_state.get("passation_id", ""),
        "beneficiaire": st.session_state.get("beneficiaire", {}),
        "started_at": st.session_state.get("started_at", ""),
        "completed_at": datetime.now().isoformat(timespec="seconds") if completed else None,
        "questionnaire_source": DEFAULT_XLSX.name,
        "cursor_order_displayed": st.session_state.get("cursor_order", []),
        "positions": st.session_state.get("positions", {}),
        "scores": scores_df.to_dict(orient="records"),
        "score_details": score_details,
        "notice": "Outil déclaratif d’exploration. Ne constitue pas un test psychométrique ni un diagnostic.",
        "rgpd": "Aucune donnée n’est enregistrée sur un serveur par l’application. Le JSON appartient au bénéficiaire. Le JSON final peut être transmis à Clarté360 pour préparation de la restitution.",
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


def create_pdf(scores_df: pd.DataFrame, payload: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.2*cm, bottomMargin=1.2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleClarte", parent=styles["Title"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=18, spaceAfter=10)
    h_style = ParagraphStyle("HClarte", parent=styles["Heading2"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=13, spaceBefore=8, spaceAfter=6)
    normal = styles["BodyText"]
    story = []
    if LOGO_PATH.exists():
        story.append(Image(str(LOGO_PATH), width=1.6*cm, height=1.6*cm))
    story.append(Paragraph("Clarté360 – Moteurs professionnels", title_style))
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
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(OFFICIAL_TEAL)),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#CCCCCC")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3*cm))
    bar = create_bar_chart(scores_df)
    radar = create_radar_chart(scores_df)
    story.append(Image(bar, width=16*cm, height=9*cm))
    story.append(Spacer(1, 0.2*cm))
    story.append(Image(radar, width=13*cm, height=13*cm))
    top = scores_df.head(3)
    story.append(Paragraph("Première lecture", h_style))
    top_txt = ", ".join([f"{r['Moteur']} ({r['Pourcentage']:.0f} %)" for _, r in top.iterrows()])
    story.append(Paragraph(f"Les réponses font apparaître prioritairement les moteurs suivants : <b>{top_txt}</b>. Cette lecture doit être discutée et contextualisée pendant l’entretien.", normal))
    story.append(Paragraph("Confidentialité", h_style))
    story.append(Paragraph("Le fichier JSON appartient au bénéficiaire. Dans le cadre de l’accompagnement, il peut être transmis à Clarté360 afin de préparer l’analyse et la restitution.", normal))
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def speak_button(text: str, key: str):
    escaped = json.dumps(text)
    if st.button("🔊 Lire la situation et les deux propositions", key=key):
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
    if st.button("■ Arrêter la lecture", key=key+"_stop"):
        components.html("<script>window.speechSynthesis.cancel();</script>", height=0)


def display_header():
    c1, c2 = st.columns([1, 5])
    with c1:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=80)
    with c2:
        st.title("Clarté360 – Moteurs professionnels")
        st.caption("Outil propriétaire d’exploration des sources d’énergie professionnelle")


def sidebar_progress(active, dims, params):
    st.sidebar.markdown("### Interrompre / reprendre")
    if st.session_state.get("test_started"):
        payload = build_payload(active, dims, params, completed=False)
        st.sidebar.download_button("💾 Sauvegarder ma progression", data=payload_bytes(payload), file_name=make_filename("moteurs_sauvegarde", "json"), mime="application/json")
        st.sidebar.caption("Ce fichier permet de reprendre plus tard exactement là où vous en étiez.")
    up = st.sidebar.file_uploader("Reprendre depuis un JSON de sauvegarde", type=["json"])
    if up is not None and st.sidebar.button("Reprendre le questionnaire"):
        try:
            payload = json.load(up)
            restore_from_progress(payload)
            st.sidebar.success("Reprise chargée.")
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"JSON non valide : {exc}")


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
    Pour chaque situation, vous verrez deux propositions positives. Déplacez le curseur vers la proposition qui vous correspond le plus aujourd’hui. Vous pouvez aussi le laisser au milieu si les deux propositions vous parlent autant. Aucune note n’est visible pendant la passation.
    </div>
    """, unsafe_allow_html=True)
    with st.expander("Voir les moteurs explorés"):
        for _, r in dims.iterrows():
            st.markdown(f"**{r.get('Moteur professionnel','')}** — {r.get('Définition bénéficiaire','')}")
    st.markdown("""
    <div class="clarte-box">
    <b>Confidentialité et maîtrise de vos données</b><br>
    Aucune donnée n’est enregistrée durablement sur un serveur par l’application. Le JSON final est généré à la fin et transmis à Clarté360 pour permettre la préparation de votre restitution. Vous pouvez également le télécharger avec votre rapport PDF.
    </div>
    """, unsafe_allow_html=True)
    st.subheader("Identification")
    with st.form("identification"):
        prenom = st.text_input("Prénom *")
        nom = st.text_input("Nom *")
        email = st.text_input("Adresse email *")
        submitted = st.form_submit_button("Recevoir mon code d’accès", type="primary")
    if submitted:
        if not prenom.strip() or not nom.strip() or not email.strip() or "@" not in email:
            st.error("Merci de renseigner prénom, nom et une adresse email valide.")
        else:
            code = generate_code()
            st.session_state.pending_beneficiaire = {"prenom": prenom.strip(), "nom": nom.strip(), "email": email.strip()}
            st.session_state.access_code = code
            minutes = int(st.secrets.get("security", {}).get("code_expiration_minutes", 15)) if "security" in st.secrets else 15
            st.session_state.code_expires_at = (datetime.now() + timedelta(minutes=minutes)).isoformat(timespec="seconds")
            subject_user = "Votre code d'accès Clarté360 – Moteurs professionnels"
            body_user = f"Bonjour {prenom},\n\nVotre code d'accès au questionnaire Clarté360 – Moteurs professionnels est : {code}\n\nCe code est valable {minutes} minutes.\n\nClarté360"
            ok_user, msg_user = send_email(subject_user, body_user, to_email=email.strip())
            subject_admin = "Nouvelle passation prévue – Moteurs professionnels"
            body_admin = f"{prenom} {nom} ({email}) a demandé un code pour réaliser l'outil Clarté360 – Moteurs professionnels.\nDate : {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            ok_admin, msg_admin = send_email(subject_admin, body_admin)
            st.session_state.code_sent = ok_user
            if ok_user:
                st.success("Un code d’accès vient de vous être envoyé par email.")
                if ok_admin:
                    st.info("Clarté360 a été informé du démarrage prochain de la passation.")
                else:
                    st.warning("Le code est parti, mais la notification administrateur n'a pas pu être envoyée : " + msg_admin)
            else:
                st.error("Impossible d’envoyer le code : " + msg_user)
                st.info("Vérifiez les Secrets Streamlit / SMTP OVH.")
    if st.session_state.get("access_code"):
        st.subheader("Code d’accès")
        code_in = st.text_input("Saisissez le code reçu par email", max_chars=6)
        if st.button("Valider le code et commencer", type="primary"):
            exp = datetime.fromisoformat(st.session_state.get("code_expires_at"))
            if datetime.now() > exp:
                st.error("Le code a expiré. Merci de demander un nouveau code.")
            elif code_in.strip() == st.session_state.get("access_code"):
                b = st.session_state.pending_beneficiaire
                start_new_session(active, b["nom"], b["prenom"], b["email"])
                st.session_state.code_verified = True
                st.rerun()
            else:
                st.error("Code incorrect.")


def questionnaire_screen(active, dims, params):
    display_header()
    total = len(st.session_state.cursor_order)
    idx = st.session_state.current_index
    if idx >= total:
        results_screen(active, dims, params)
        return
    cid = st.session_state.cursor_order[idx]
    row = active.set_index("ID").loc[cid]
    st.progress((idx) / total)
    st.markdown(f"### Question {idx + 1} / {total}")
    situation = str(row["Situation / consigne"])
    left = str(row["Proposition gauche"])
    right = str(row["Proposition droite"])
    st.markdown(f"<div class='clarte-card'><h3>{situation}</h3></div>", unsafe_allow_html=True)
    speak_text = f"Question {idx+1} sur {total}. {situation}. Proposition à gauche : {left}. Proposition à droite : {right}. Déplacez le curseur vers la proposition qui vous correspond le plus."
    speak_button(speak_text, f"speak_{cid}")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div class='slider-card-left'><b>{left}</b></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='slider-card-right'><b>{right}</b></div>", unsafe_allow_html=True)
    default_pos = int(st.session_state.positions.get(cid, int(row.get("Position défaut", 5))))
    pos = st.slider("Déplacez le curseur", min_value=0, max_value=10, value=default_pos, step=1, key=f"slider_{cid}", label_visibility="collapsed")
    cprev, cnext = st.columns([1, 2])
    # Pas de retour arrière volontairement : passation en sens unique.
    with cnext:
        if st.button("Valider et passer à la suite", type="primary", use_container_width=True):
            st.session_state.positions[cid] = int(pos)
            st.session_state.current_index += 1
            st.rerun()
    st.caption("Le curseur permet une réponse nuancée. La cotation interne n’est pas affichée pendant la passation.")


def results_screen(active, dims, params):
    payload = build_payload(active, dims, params, completed=True)
    scores_df = pd.DataFrame(payload["scores"])
    st.progress(1.0)
    st.success("Questionnaire terminé.")
    st.subheader("Première lecture de vos moteurs professionnels")
    st.caption("Ces résultats sont déclaratifs et servent de support d’échange avec votre consultant Clarté360.")
    st.dataframe(scores_df[["Moteur", "Pourcentage", "Lecture"]], hide_index=True, use_container_width=True)
    bar = create_bar_chart(scores_df)
    radar = create_radar_chart(scores_df)
    st.image(bar, caption="Scores par moteur")
    st.image(radar, caption="Radar des moteurs")
    top = scores_df.sort_values("Pourcentage", ascending=False).head(3)
    st.markdown("### Synthèse courte")
    st.markdown("Vos réponses mettent principalement en avant : " + ", ".join([f"**{r['Moteur']}** ({r['Pourcentage']:.0f} %)" for _, r in top.iterrows()]) + ".")
    json_data = payload_bytes(payload)
    pdf_data = create_pdf(scores_df, payload)
    json_filename = make_filename("moteurs_professionnels", "json")
    pdf_filename = make_filename("rapport_moteurs_professionnels", "pdf")
    if not st.session_state.get("final_email_sent"):
        ok, msg = send_email(
            subject=f"JSON final – Moteurs professionnels – {payload.get('passation_id')}",
            body=f"Questionnaire terminé pour {payload['beneficiaire'].get('prenom','')} {payload['beneficiaire'].get('nom','')}.\nID : {payload.get('passation_id')}",
            attachments=[(json_filename, json_data, "application/json")],
        )
        if ok:
            st.session_state.final_email_sent = True
            st.info("Le JSON final a été transmis à Clarté360.")
        else:
            st.warning("Le JSON final n'a pas pu être envoyé automatiquement : " + msg)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Télécharger mon JSON", data=json_data, file_name=json_filename, mime="application/json")
    with c2:
        st.download_button("Télécharger mon rapport PDF", data=pdf_data, file_name=pdf_filename, mime="application/pdf")


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
    st.sidebar.markdown("---")
    st.sidebar.caption(f"App v{APP_VERSION} · Questionnaire {get_param(params, 'version_questionnaire', '0.1')}")
    if st.sidebar.button("Réinitialiser la session"):
        reset_all()
    if not st.session_state.get("test_started"):
        identification_screen(active, dims, params)
    else:
        questionnaire_screen(active, dims, params)


if __name__ == "__main__":
    main()
