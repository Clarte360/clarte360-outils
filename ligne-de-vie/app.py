from __future__ import annotations

import base64
import csv
import io
import json
import random
import re
import smtplib
import uuid
from email.message import EmailMessage
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_VERSION = "3.2"
BRAND = "#008080"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo_clarte360.png"
TOOL_NAME = "LigneDeVie"
FINAL_EMAIL_TO = "contact@clarte360.com"

st.set_page_config(page_title="Clarté360 - Ligne de vie", page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else None, layout="wide")

st.markdown(
    f"""
    <style>
    .main .block-container {{ padding-top: 1.2rem; max-width: 1180px; }}
    h1, h2, h3,
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {{ color: {BRAND} !important; }}
    .c360-card {{
        border: 1px solid #dbe7e7; border-radius: 14px; padding: 1rem 1.15rem;
        background: #f7fbfb; margin: 0.6rem 0 1rem 0;
    }}
    .c360-rgpd {{
        border-left: 5px solid {BRAND}; border-radius: 12px; padding: 1rem 1.15rem;
        background: #eefafa; margin: 1rem 0;
    }}
    .small-muted {{ color: #667; font-size: 0.92rem; }}
    div.stButton > button:first-child {{ border-color: {BRAND}; color: {BRAND}; }}
    div.stDownloadButton > button:first-child {{ border-color: {BRAND}; color: {BRAND}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def safe_slug(text: str) -> str:
    text = (text or "").strip().upper()
    text = re.sub(r"[^A-Z0-9À-ÖØ-Ý]+", "_", text)
    return text.strip("_") or "SANS_NOM"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def export_name(last: str, first: str, ext: str) -> str:
    return f"{now_stamp()}_{safe_slug(last)}_{safe_slug(first).title()}_{TOOL_NAME}.{ext}"


def parse_event_date(year: int, month: int, day: int) -> date:
    # Le jour 00 est accepté comme convention : date approximative dans le mois.
    # Pour le calcul de l'âge et le classement, on utilise le 1er jour du mois.
    safe_day = 1 if int(day) == 0 else int(day)
    return date(int(year), int(month), safe_day)


def display_date(year: int, month: int, day: int) -> str:
    return f"{int(day):02d}/{int(month):02d}/{int(year)}"


def decimal_age(birth: date, event_date: date) -> float:
    return round((event_date - birth).days / 365.2425, 2)


def init_state() -> None:
    defaults = {
        "first_name": "",
        "last_name": "",
        "email": "",
        "access_code": "",
        "code_sent": False,
        "code_verified": False,
        "pending_beneficiaire": {},
        "final_json_sent": False,
        "birthdate": None,
        "start_age": 10,
        "projection_years": 0,
        "events": [],
        "remontees": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def load_payload(payload: dict[str, Any]) -> None:
    b = payload.get("beneficiaire", {})
    st.session_state.first_name = b.get("prenom", "")
    st.session_state.last_name = b.get("nom", "")
    st.session_state.email = b.get("email", st.session_state.get("email", ""))
    st.session_state.code_verified = True
    bd = b.get("date_naissance")
    st.session_state.birthdate = date.fromisoformat(bd) if bd else None
    st.session_state.start_age = int(payload.get("parametres", {}).get("age_depart", 10))
    st.session_state.projection_years = int(payload.get("parametres", {}).get("projection_annees", 0))
    st.session_state.events = payload.get("evenements", [])
    for e in st.session_state.events:
        e.setdefault("id", str(uuid.uuid4()))
    st.session_state.remontees = payload.get("remontees", {})


def build_payload() -> dict[str, Any]:
    return {
        "outil": "Clarté360 - Ligne de vie",
        "version": APP_VERSION,
        "date_export": datetime.now().isoformat(timespec="seconds"),
        "session": {
            "code_acces_valide": bool(st.session_state.get("code_verified", False)),
            "json_transmis_consultant": bool(st.session_state.get("final_json_sent", False)),
        },
        "beneficiaire": {
            "prenom": st.session_state.first_name,
            "nom": st.session_state.last_name,
            "email": st.session_state.get("email", ""),
            "date_naissance": st.session_state.birthdate.isoformat() if st.session_state.birthdate else None,
        },
        "parametres": {
            "age_depart": st.session_state.start_age,
            "projection_annees": st.session_state.projection_years,
        },
        "evenements": sorted(st.session_state.events, key=lambda e: (float(e.get("age", 0)), e.get("date_reference", ""))),
        "remontees": st.session_state.get("remontees", {}),
    }


def events_df() -> pd.DataFrame:
    rows = []
    for i, e in enumerate(sorted(st.session_state.events, key=lambda x: (float(x.get("age", 0)), x.get("date_reference", "")))):
        rows.append({
            "#": i + 1,
            "Âge": e.get("age"),
            "Date / période": e.get("periode_affichee"),
            "Nom court": e.get("nom_court"),
            "Position": e.get("position"),
            "Nom long": e.get("nom_long", ""),
            "Description": e.get("description", ""),
        })
    return pd.DataFrame(rows)



def label_positions_for_events(evts: list[dict[str, Any]]) -> list[str]:
    """Place labels so close events and edge values remain readable in screen and PDF exports."""
    positions: list[str] = []
    # Cycle used when several points are close together.
    near_cycle = ["top left", "top right", "bottom left", "bottom right", "middle left", "middle right"]
    cluster_index = 0
    previous_x = None
    previous_y = None
    for e in evts:
        x = float(e.get("age", 0))
        y = float(e.get("position", 0))
        if y >= 9:
            # Never put text above a +10/+9 point: it is often clipped in the PDF.
            pos = "bottom center"
        elif y <= -9:
            # Never put text below a -10/-9 point.
            pos = "top center"
        else:
            close = previous_x is not None and abs(x - previous_x) < 0.9 and abs(y - previous_y) < 2.2
            if close:
                cluster_index += 1
                pos = near_cycle[cluster_index % len(near_cycle)]
            else:
                cluster_index = 0
                pos = "top center" if y < 8 else "bottom center"
        positions.append(pos)
        previous_x, previous_y = x, y
    return positions


def remontees_for_pdf() -> list[dict[str, Any]]:
    data = []
    for value in st.session_state.get("remontees", {}).values():
        if value.get("trace_ecrite_souhaitee"):
            if any((value.get(k) or "").strip() for k in ["ressources", "actions", "apprentissages"]):
                data.append(value)
    return data

def make_figure() -> go.Figure:
    evts = sorted(st.session_state.events, key=lambda e: (float(e.get("age", 0)), e.get("date_reference", "")))
    if not evts:
        fig = go.Figure()
        fig.update_layout(height=430, margin=dict(l=65, r=80, t=45, b=55), plot_bgcolor="white", paper_bgcolor="white")
        fig.update_yaxes(range=[-11.5, 11.5], tickvals=list(range(-10, 11, 2)), title="Position", zeroline=True, zerolinewidth=2, zerolinecolor="#666")
        fig.update_xaxes(title="Âge")
        return fig

    x = [float(e["age"]) for e in evts]
    y = [float(e["position"]) for e in evts]
    text = [str(e.get("nom_court", "")) for e in evts]
    textpositions = label_positions_for_events(evts)
    hover = [
        f"<b>{e.get('nom_court')}</b><br>Âge : {e.get('age')} ans<br>Date : {e.get('periode_affichee')}<br>Position : {e.get('position')}<br>{e.get('nom_long','')}"
        for e in evts
    ]

    fig = go.Figure()
    # Ligne reliant les points, puis points + textes. Les deux traces évitent que le texte soit écrasé par la ligne.
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines",
        line=dict(width=2.8, color=BRAND),
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers+text", text=text,
        textposition=textpositions,
        textfont=dict(size=12, color="#263238"),
        hovertext=hover, hoverinfo="text",
        marker=dict(size=12, color=BRAND, line=dict(width=1.5, color="white")),
    ))

    start = max(0, int(st.session_state.start_age) - 1)
    current_age = decimal_age(st.session_state.birthdate, date.today()) if st.session_state.birthdate else max(x)
    end = max(max(x) + 1.5, current_age + int(st.session_state.projection_years) + 1.5)

    fig.add_vline(x=current_age, line_width=2, line_dash="dash", line_color="#777",
                  annotation_text="Aujourd'hui", annotation_position="top")
    if st.session_state.projection_years:
        fig.add_vrect(x0=current_age, x1=current_age + st.session_state.projection_years,
                      fillcolor="#008080", opacity=0.06, line_width=0,
                      annotation_text=f"Projection {st.session_state.projection_years} ans", annotation_position="top left")

    fig.update_layout(
        height=540,
        margin=dict(l=65, r=90, t=55, b=60),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        title=dict(text="Ligne de vie", x=0.02, xanchor="left"),
        font=dict(size=12),
    )
    fig.update_xaxes(title="Âge", range=[start, end], showgrid=True, gridcolor="#e6e6e6")
    fig.update_yaxes(
        title="Position libre (-10 à +10)",
        range=[-11.5, 11.5],
        tickvals=list(range(-10, 11, 2)),
        showgrid=True,
        gridcolor="#e6e6e6",
        zeroline=True,
        zerolinewidth=2,
        zerolinecolor="#666",
    )
    return fig

def upward_segments() -> list[dict[str, Any]]:
    evts = sorted(st.session_state.events, key=lambda e: (float(e.get("age", 0)), e.get("date_reference", "")))
    segments = []
    for a, b in zip(evts, evts[1:]):
        delta = int(b.get("position", 0)) - int(a.get("position", 0))
        if delta > 0:
            key = f"{a.get('id','')}_TO_{b.get('id','')}"
            segments.append({"key": key, "from": a, "to": b, "delta": delta})
    return segments


def segment_label(seg: dict[str, Any]) -> str:
    a, b = seg["from"], seg["to"]
    return f"{a.get('nom_court')} ({a.get('position')}) → {b.get('nom_court')} ({b.get('position')}) | +{seg.get('delta')}"


def make_csv_bytes() -> bytes:
    df = events_df()
    return df.to_csv(index=False, sep=";").encode("utf-8-sig")


def make_pdf_bytes(fig_png: bytes | None = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1.2*cm, leftMargin=1.2*cm, topMargin=0.8*cm, bottomMargin=0.8*cm)
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor(BRAND)
    styles["Heading2"].textColor = colors.HexColor(BRAND)
    story = []
    if LOGO_PATH.exists():
        story.append(Image(str(LOGO_PATH), width=3.0*cm, height=1.1*cm, kind="proportional"))
    story.append(Paragraph("<b>Ligne de vie</b>", styles["Title"]))
    story.append(Paragraph(f"Bénéficiaire : {st.session_state.first_name} {st.session_state.last_name}", styles["Normal"]))
    story.append(Paragraph(f"Date d'édition : {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, 0.25*cm))
    if fig_png:
        img = Image(io.BytesIO(fig_png), width=24.5*cm, height=12.8*cm, kind="proportional")
        story.append(img)
        story.append(Spacer(1, 0.15*cm))
    df = events_df()
    if not df.empty:
        table_data = [list(df[["Âge", "Date / période", "Nom court", "Position"]].columns)] + df[["Âge", "Date / période", "Nom court", "Position"]].astype(str).values.tolist()
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor(BRAND)),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
        ]))
        story.append(t)

    written = remontees_for_pdf()
    if written:
        story.append(Spacer(1, 0.35*cm))
        story.append(Paragraph("<b>Exploration des remontées</b>", styles["Heading2"]))
        for item in written:
            story.append(Paragraph(f"<b>{item.get('libelle','Remontée sélectionnée')}</b>", styles["Normal"]))
            rows = [[Paragraph("<b>Ressources mobilisées</b>", styles["Normal"]), Paragraph((item.get("ressources") or "").replace("\n", "<br/>"), styles["Normal"])],
                    [Paragraph("<b>Actions qui ont aidé à remonter</b>", styles["Normal"]), Paragraph((item.get("actions") or "").replace("\n", "<br/>"), styles["Normal"])],
                    [Paragraph("<b>Ce que j'en retiens aujourd'hui</b>", styles["Normal"]), Paragraph((item.get("apprentissages") or "").replace("\n", "<br/>"), styles["Normal"])]]
            rt = Table(rows, colWidths=[6.2*cm, 17.0*cm])
            rt.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#a7cfcf")),
                ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#eefafa")),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("LEFTPADDING", (0,0), (-1,-1), 6),
                ("RIGHTPADDING", (0,0), (-1,-1), 6),
                ("TOPPADDING", (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ]))
            story.append(rt)
            story.append(Spacer(1, 0.2*cm))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def get_email_config() -> dict | None:
    """Lit la configuration SMTP depuis Streamlit Secrets, section [email]."""
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
        if port == 465:
            with smtplib.SMTP_SSL(str(cfg["smtp_server"]), port, timeout=20) as smtp:
                smtp.login(str(cfg["smtp_user"]), str(cfg["smtp_password"]))
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(str(cfg["smtp_server"]), port, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(str(cfg["smtp_user"]), str(cfg["smtp_password"]))
                smtp.send_message(msg)
        return True, "Email envoyé."
    except Exception as exc:
        return False, f"Erreur d'envoi email : {exc}"


def generate_access_code() -> str:
    return f"{random.randint(100000, 999999)}"


def send_access_code_email(beneficiaire: dict, access_code: str) -> tuple[bool, str]:
    cfg = get_email_config()
    if cfg is None:
        return False, "SMTP non configuré : impossible d'envoyer le code d'accès. Configurez les Secrets Streamlit."
    prenom = beneficiaire.get("prenom", "")
    nom = beneficiaire.get("nom", "")
    email = beneficiaire.get("email", "")
    admin_to = cfg.get("to_email", FINAL_EMAIL_TO)
    now_txt = datetime.now().isoformat(timespec="seconds")
    subject_admin = "Clarté360 - Nouveau code d'accès Ligne de vie"
    body_admin = (
        "Une personne vient de demander un code d'accès pour réaliser l'outil Clarté360 - Ligne de vie.\n\n"
        f"Bénéficiaire : {prenom} {nom}\n"
        f"Email : {email}\n"
        f"Date de demande : {now_txt}\n\n"
        "Le JSON final pourra être transmis automatiquement à Clarté360 en fin d'utilisation.\n\n"
        "Message automatique Clarté360."
    )
    ok_admin, msg_admin = send_email(admin_to, subject_admin, body_admin)
    if not ok_admin:
        return False, "Notification Clarté360 non envoyée : " + msg_admin
    subject_user = "Votre code d'accès Clarté360"
    body_user = (
        f"Bonjour {prenom},\n\n"
        "Voici votre code d'accès pour démarrer l'outil Clarté360 - Ligne de vie :\n\n"
        f"{access_code}\n\n"
        "Ce code permet de sécuriser le démarrage de votre travail.\n\n"
        "À la fin, vous pourrez télécharger votre PDF, votre image, votre CSV et votre fichier JSON. "
        "Le fichier JSON pourra être transmis au consultant Clarté360 afin de préparer la restitution du bilan.\n\n"
        "Clarté360"
    )
    ok_user, msg_user = send_email(email, subject_user, body_user)
    if not ok_user:
        return False, "Code bénéficiaire non envoyé : " + msg_user
    return True, "Code envoyé au bénéficiaire et notification transmise à Clarté360."


def send_final_json_to_consultant(json_bytes: bytes, file_name: str) -> tuple[bool, str]:
    cfg = get_email_config()
    destination = cfg.get("to_email", FINAL_EMAIL_TO) if cfg else FINAL_EMAIL_TO
    prenom = st.session_state.get("first_name", "")
    nom = st.session_state.get("last_name", "")
    email = st.session_state.get("email", "")
    subject = "Clarté360 - JSON final Ligne de vie"
    body = (
        "Le bénéficiaire vient de générer un JSON Ligne de vie.\n\n"
        f"Bénéficiaire : {prenom} {nom}\n"
        f"Email : {email}\n"
        f"Date : {datetime.now().isoformat(timespec='seconds')}\n\n"
        "Le JSON est joint à ce message.\n\n"
        "Message automatique Clarté360."
    )
    return send_email(destination, subject, body, attachment=json_bytes, attachment_name=file_name)


def get_fig_png(fig: go.Figure) -> bytes | None:
    try:
        return fig.to_image(format="png", width=1600, height=850, scale=2)
    except Exception:
        return None

init_state()

if not st.session_state.get("code_verified", False):
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=95)
    with col_title:
        st.markdown(f"<h1>Clarté360 - Ligne de vie</h1><div class='small-muted'>Version {APP_VERSION} - accès sécurisé</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class='c360-card'>
    <b>Objectif de l'outil</b><br>
    La ligne de vie permet de représenter les événements marquants de votre parcours sur un axe chronologique.
    Elle sert de support d'échange avec votre consultant Clarté360 pour repérer les périodes importantes,
    les ressources mobilisées et les éléments utiles à la construction de votre projet professionnel.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='c360-rgpd'>
    🔒 <b>Confidentialité et transmission</b><br>
    Le code d'accès sécurise le démarrage de l'outil. À la fin du travail, vous pourrez télécharger vos fichiers.
    Le JSON final peut être transmis au consultant Clarté360 afin de préparer l'accompagnement et la restitution.
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.get("code_sent"):
        with st.form("access_code_form"):
            prenom = st.text_input("Prénom *")
            nom = st.text_input("Nom *")
            email = st.text_input("Adresse email *")
            send_code = st.form_submit_button("Recevoir mon code d'accès", type="primary")
        if send_code:
            if not prenom.strip() or not nom.strip() or not email.strip():
                st.error("Merci de renseigner le prénom, le nom et l'adresse email.")
            elif "@" not in email or "." not in email:
                st.error("Merci de renseigner une adresse email valide.")
            else:
                beneficiaire_tmp = {"prenom": prenom.strip(), "nom": nom.strip(), "email": email.strip()}
                code = generate_access_code()
                ok, msg = send_access_code_email(beneficiaire_tmp, code)
                st.session_state.pending_beneficiaire = beneficiaire_tmp
                st.session_state.access_code = code
                st.session_state.code_sent = ok
                if ok:
                    st.success("Un code d'accès vient d'être envoyé à l'adresse email indiquée.")
                    st.rerun()
                else:
                    st.error(msg)
                    st.caption("En ligne, configurez les Secrets SMTP Streamlit pour activer l'envoi du code.")
    else:
        b = st.session_state.get("pending_beneficiaire", {})
        st.success(f"Code envoyé à : {b.get('email','')}")
        code_input = st.text_input("Saisissez le code d'accès reçu par email *", max_chars=6)
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Valider le code et démarrer", type="primary"):
                if code_input.strip() == st.session_state.get("access_code", ""):
                    st.session_state.code_verified = True
                    st.session_state.first_name = b.get("prenom", "")
                    st.session_state.last_name = b.get("nom", "")
                    st.session_state.email = b.get("email", "")
                    st.rerun()
                else:
                    st.error("Code incorrect.")
        with c2:
            if st.button("Modifier l'adresse email"):
                st.session_state.code_sent = False
                st.session_state.access_code = ""
                st.session_state.pending_beneficiaire = {}
                st.rerun()
    st.stop()

# Header
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=95)
with col_title:
    st.markdown(f"<h1>Clarté360 - Ligne de vie</h1><div class='small-muted'>Version {APP_VERSION} - construction chronologique du parcours</div>", unsafe_allow_html=True)

st.markdown(
    """
    <div class="c360-card">
    <b>Objectif de l'outil</b><br>
    La ligne de vie permet de représenter les événements marquants de votre parcours sur un axe chronologique exprimé en âge.
    Dans cette première étape, il ne s'agit pas d'analyser votre histoire mais de la poser visuellement, avec vos propres repères.
    Les événements pourront ensuite servir de support d'échange avec votre consultant, notamment pour identifier les ressources mobilisées lors de certaines périodes de remontée.
    </div>
    """, unsafe_allow_html=True
)

st.markdown(
    """
    <div class="c360-rgpd">
    🔒 <b>Confidentialité et maîtrise de vos données</b><br>
    Aucune donnée personnelle ou sensible saisie dans cet outil n'est enregistrée automatiquement sur un serveur Clarté360.
    Pour reprendre votre travail plus tard, vous devez télécharger le fichier JSON et le conserver. En fin de travail, vous pouvez transmettre ce JSON au consultant Clarté360 afin de préparer l'accompagnement.
    </div>
    """, unsafe_allow_html=True
)

with st.sidebar:
    st.header("Navigation")
    uploaded = st.file_uploader("Reprendre depuis un JSON", type=["json"])
    if uploaded is not None:
        try:
            load_payload(json.loads(uploaded.read().decode("utf-8")))
            st.success("JSON chargé.")
        except Exception as exc:
            st.error(f"Impossible de lire le JSON : {exc}")
    st.divider()
    st.caption("Étapes")
    st.write("1. Paramétrer")
    st.write("2. Ajouter les événements")
    st.write("3. Visualiser")
    st.write("4. Explorer certaines remontées")
    st.write("5. Exporter")

# Parameters
st.subheader("1. Paramétrage")
col1, col2, col3, col4 = st.columns([1.2, 1.2, 1.3, 1])
with col1:
    st.session_state.first_name = st.text_input("Prénom", value=st.session_state.first_name)
with col2:
    st.session_state.last_name = st.text_input("Nom", value=st.session_state.last_name)
    st.session_state.email = st.text_input("Email", value=st.session_state.get("email", ""), help="Adresse utilisée pour le code d'accès et la transmission du JSON au consultant.")
with col3:
    st.session_state.birthdate = st.date_input(
        "Date de naissance (obligatoire pour calculer les âges)",
        value=st.session_state.birthdate or date(1980, 1, 1),
        min_value=date(1920, 1, 1), max_value=date.today(),
    )
with col4:
    current_age = decimal_age(st.session_state.birthdate, date.today())
    st.metric("Âge actuel", f"{current_age:.1f} ans")

col5, col6 = st.columns([1, 1])
with col5:
    st.session_state.start_age = st.number_input(
        "À partir de quel âge souhaitez-vous commencer ?",
        min_value=0, max_value=int(max(current_age, 1)), value=int(st.session_state.start_age), step=1,
        help="Conseil : commencez à partir d'un âge où vous avez conscience des événements et où vous pouvez vous représenter votre capacité d'action."
    )
with col6:
    st.session_state.projection_years = st.selectbox(
        "Souhaitez-vous afficher une zone de projection future ?",
        options=[0, 5, 10],
        index=[0, 5, 10].index(int(st.session_state.projection_years)) if int(st.session_state.projection_years) in [0, 5, 10] else 0,
        format_func=lambda x: "Non" if x == 0 else f"Oui, projection à {x} ans",
    )

st.subheader("2. Ajouter un événement")
with st.form("event_form", clear_on_submit=True):
    st.markdown("**Contenu d'un événement :** date, nom court affiché sur la ligne, position libre entre -10 et +10. Si le jour exact est inconnu, le jour 00 est accepté ; le mois et l'année restent nécessaires pour classer correctement la ligne de vie. Le nom long et la description sont facultatifs.")
    c1, c2, c3, c4 = st.columns([0.8, 0.9, 1, 1.3])
    with c1:
        day_text = st.text_input("Jour", value="01", max_chars=2, help="Si vous ne connaissez pas le jour exact, vous pouvez saisir 00.")
    with c2:
        month = st.selectbox("Mois", list(range(1, 13)), format_func=lambda m: f"{m:02d}", help="Le mois est nécessaire pour classer l'événement. Choisissez le mois le plus probable si la date est approximative.")
    with c3:
        year = st.number_input("Année", min_value=1920, max_value=date.today().year + 10, value=date.today().year, step=1)
    with c4:
        position = st.slider("Position sur la ligne", -10, 10, 0, help="Le bénéficiaire choisit librement la place de l'événement sur la ligne.")

    nom_court = st.text_input("Nom court de l'événement (obligatoire - affiché à côté du point)", max_chars=35, placeholder="Ex. Bac, 1er emploi, création entreprise")
    nom_long = st.text_input("Nom long (facultatif)", placeholder="Ex. Obtention du baccalauréat / création de ma première entreprise")
    description = st.text_area("Description libre (facultative)", placeholder="Quelques mots si vous souhaitez préciser le contexte.")

    submitted = st.form_submit_button("Ajouter l'événement")
    if submitted:
        if not st.session_state.first_name.strip() or not st.session_state.last_name.strip():
            st.error("Merci de renseigner le prénom et le nom avant d'ajouter un événement.")
        elif not nom_court.strip():
            st.error("Le nom court est obligatoire.")
        else:
            try:
                if not re.fullmatch(r"\d{1,2}", day_text.strip()):
                    raise ValueError("Le jour doit être compris entre 00 et 31.")
                day = int(day_text.strip())
                if day < 0 or day > 31:
                    raise ValueError("Le jour doit être compris entre 00 et 31.")
                ed = parse_event_date(int(year), int(month), int(day))
                age = decimal_age(st.session_state.birthdate, ed)
                if age < st.session_state.start_age:
                    st.warning("Cet événement est antérieur à l'âge de départ choisi. Il est ajouté, mais il se situera avant le début conseillé de la ligne.")
                periode = display_date(int(year), int(month), int(day))
                st.session_state.events.append({
                    "id": str(uuid.uuid4()),
                    "date_precision": "Date avec jour 00 possible",
                    "date_reference": ed.isoformat(),
                    "jour_saisi": int(day),
                    "mois_saisi": int(month),
                    "annee_saisie": int(year),
                    "periode_affichee": periode,
                    "age": age,
                    "nom_court": nom_court.strip(),
                    "nom_long": nom_long.strip(),
                    "description": description.strip(),
                    "position": int(position),
                })
                st.success("Événement ajouté et reclassé automatiquement.")
            except Exception as exc:
                st.error(f"Date invalide : {exc}")

st.subheader("3. Ligne de vie")
fig = make_figure()
st.plotly_chart(fig, use_container_width=True)

if st.session_state.events:
    st.markdown("### Événements saisis")
    df = events_df()
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### Supprimer un événement")
    sorted_events = sorted(enumerate(st.session_state.events), key=lambda x: (float(x[1].get("age", 0)), x[1].get("date_reference", "")))
    labels = [f"{e.get('age')} ans - {e.get('nom_court')} ({e.get('periode_affichee')})" for _, e in sorted_events]
    idx_label = st.selectbox("Choisir l'événement à supprimer", labels)
    if st.button("Supprimer l'événement sélectionné"):
        original_index = sorted_events[labels.index(idx_label)][0]
        st.session_state.events.pop(original_index)
        st.rerun()
else:
    st.info("Ajoutez au moins un événement pour visualiser votre ligne de vie.")

st.subheader("4. Explorer certaines remontées")
st.markdown("""
<div class='c360-card'>
Cette étape est facultative. Elle sert uniquement de support d'entretien : le bénéficiaire choisit les remontées qu'il souhaite approfondir.
Il peut aussi décider de ne rien écrire et d'en parler seulement oralement avec le consultant.
</div>
""", unsafe_allow_html=True)
segments = upward_segments()
if not segments:
    st.info("Aucune remontée n'est encore détectée. Une remontée apparaît lorsqu'un point suivant est placé plus haut que le point précédent.")
else:
    labels = [segment_label(seg) for seg in segments]
    chosen_label = st.selectbox("Choisir une remontée à approfondir, si vous le souhaitez", ["Ne pas approfondir maintenant"] + labels)
    if chosen_label != "Ne pas approfondir maintenant":
        seg = segments[labels.index(chosen_label)]
        key = seg["key"]
        current = st.session_state.remontees.get(key, {})
        st.markdown(f"**Remontée sélectionnée :** {chosen_label}")
        keep_trace = st.checkbox("Je souhaite conserver une trace écrite de cette réflexion", value=bool(current.get("trace_ecrite_souhaitee", False)))
        if keep_trace:
            ressources = st.text_area("Ressources mobilisées", value=current.get("ressources", ""), placeholder="Ex. soutien, courage, méthode, réseau, décision personnelle...")
            actions = st.text_area("Actions qui ont aidé à remonter", value=current.get("actions", ""), placeholder="Ex. reprise de contact, formation, changement d'organisation, demande d'aide...")
            apprentissages = st.text_area("Ce que j'en retiens aujourd'hui", value=current.get("apprentissages", ""), placeholder="Ce que cette période m'a appris sur moi, mes ressources ou ma façon d'agir.")
            if st.button("Enregistrer cette réflexion"):
                st.session_state.remontees[key] = {
                    "trace_ecrite_souhaitee": True,
                    "evenement_depart": seg["from"].get("id"),
                    "evenement_arrivee": seg["to"].get("id"),
                    "libelle": chosen_label,
                    "ressources": ressources.strip(),
                    "actions": actions.strip(),
                    "apprentissages": apprentissages.strip(),
                    "date_maj": datetime.now().isoformat(timespec="seconds"),
                }
                st.success("Réflexion enregistrée dans le JSON.")
        else:
            if key in st.session_state.remontees and st.button("Supprimer la trace écrite déjà enregistrée pour cette remontée"):
                del st.session_state.remontees[key]
                st.success("Trace écrite supprimée.")

st.subheader("5. Exports")
payload = build_payload()
json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
fig_png = get_fig_png(fig)

cjson, ccsv, cpdf = st.columns(3)
with cjson:
    json_file_name = export_name(st.session_state.last_name, st.session_state.first_name, "json")
    st.download_button("Télécharger le JSON", data=json_bytes, file_name=json_file_name, mime="application/json")
    if not st.session_state.get("final_json_sent", False):
        if st.button("Transmettre le JSON au consultant Clarté360"):
            ok, msg = send_final_json_to_consultant(json_bytes, json_file_name)
            if ok:
                st.session_state.final_json_sent = True
                st.success("JSON transmis au consultant Clarté360.")
            else:
                st.error(msg)
    else:
        st.success("JSON déjà transmis au consultant Clarté360.")
with ccsv:
    st.download_button("Télécharger le CSV", data=make_csv_bytes(), file_name=export_name(st.session_state.last_name, st.session_state.first_name, "csv"), mime="text/csv")
with cpdf:
    pdf_bytes = make_pdf_bytes(fig_png)
    st.download_button("Télécharger le PDF", data=pdf_bytes, file_name=export_name(st.session_state.last_name, st.session_state.first_name, "pdf"), mime="application/pdf")

if fig_png:
    st.download_button("Télécharger l'image PNG de la ligne", data=fig_png, file_name=export_name(st.session_state.last_name, st.session_state.first_name, "png"), mime="image/png")
else:
    st.caption("Export PNG indisponible si le moteur graphique Kaleido n'est pas disponible sur l'hébergement. Le PDF et le JSON restent disponibles.")

st.markdown("<div class='small-muted'>Clarté360 - Ligne de vie. Les analyses de ressources liées aux remontées seront traitées dans un écran séparé ultérieurement, uniquement si le bénéficiaire souhaite conserver une trace écrite.</div>", unsafe_allow_html=True)
