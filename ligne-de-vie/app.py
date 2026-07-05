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
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_VERSION = "3.4.1"
BRAND = "#008080"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo_clarte360.png"
TOOL_NAME = "LigneDeVie"
APP_DISPLAY_NAME = "Clarté360 - Ligne de vie"
SOCLE_VERSION = "Clarté360 socle v1.8.2"
FINAL_EMAIL_TO = "contact@clarte360.com"

st.set_page_config(page_title="Clarté360 - Ligne de vie", page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else None, layout="wide")

st.markdown(
    f"""
    <style>
        .main .block-container {{max-width: 1180px; padding-top: 2rem;}}
        h1, h2, h3 {{color: {BRAND} !important;}}
        .brand-header {{margin-bottom: 1.25rem; padding-bottom: 0.75rem; border-bottom: 1px solid #E5E7EB;}}
        .small-note, .small-muted {{color:#6B7280; font-size:0.95rem; margin-top: -0.6rem;}}
        .privacy-box, .c360-rgpd {{background:#F1F8F8; border-left:6px solid {BRAND}; padding:16px 18px; border-radius:10px; line-height:1.55; margin: 1rem 0;}}
        .rule-box, .c360-card {{background:#F1F8F8; border:0; border-left:5px solid {BRAND}; padding:16px; border-radius:8px; line-height:1.5; margin: 1rem 0;}}
        .warn-box {{background:#FFF7E6; border-left:5px solid #F2C94C; padding:12px; border-radius:8px; line-height:1.5;}}
        div.stButton > button:first-child {{border-radius:10px; border:1px solid {BRAND}; color:{BRAND}; background:white;}}
        div.stButton > button:first-child:hover {{border-color:{BRAND}; color:{BRAND}; background:#F1F8F8;}}
        div.stButton > button[kind="primary"] {{background:{BRAND} !important; color:white !important; border:1px solid {BRAND} !important;}}
        div.stButton > button[kind="primary"] * {{color:white !important;}}
        div.stDownloadButton > button:first-child {{border-radius:10px; border:1px solid {BRAND}; color:{BRAND}; background:white;}}
        div.stDownloadButton > button:first-child:hover {{border-color:{BRAND}; color:{BRAND}; background:#F1F8F8;}}
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
        "root_passage_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "session_started_at": datetime.now().isoformat(timespec="seconds"),
        "session_last_activity": datetime.now().isoformat(timespec="seconds"),
        "rgpd_consent": False,
        "rgpd_consent_at": "",
        "rgpd_text_version": "RGPD-Clarte360-2026-07",
        "institutional_page": None,
        "consultant": "",
        "access_sessions": [],
        "sauvegardes": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def load_payload(payload: dict[str, Any]) -> None:
    b = payload.get("beneficiaire", {})
    st.session_state.first_name = b.get("prenom", b.get("first_name", ""))
    st.session_state.last_name = b.get("nom", b.get("last_name", ""))
    st.session_state.email = b.get("email", st.session_state.get("email", ""))
    st.session_state.consultant = payload.get("consultant", st.session_state.get("consultant", ""))
    st.session_state.code_verified = True
    bd = b.get("date_naissance")
    st.session_state.birthdate = date.fromisoformat(bd) if bd else None
    st.session_state.start_age = int(payload.get("parametres", {}).get("age_depart", 10))
    st.session_state.projection_years = int(payload.get("parametres", {}).get("projection_annees", 0))
    st.session_state.events = payload.get("evenements", [])
    for e in st.session_state.events:
        e.setdefault("id", str(uuid.uuid4()))
    st.session_state.remontees = payload.get("remontees", {})
    st.session_state.root_passage_id = payload.get("identifiant_racine_passation", payload.get("session", {}).get("root_passage_id", st.session_state.get("root_passage_id", str(uuid.uuid4()))))
    st.session_state.session_id = str(uuid.uuid4())
    rgpd = payload.get("rgpd", {})
    st.session_state.rgpd_consent = bool(rgpd.get("consentement", payload.get("rgpd_consent", False)))
    st.session_state.rgpd_consent_at = rgpd.get("date_consentement", payload.get("rgpd_consent_at", ""))
    access = payload.get("access", {}) if isinstance(payload.get("access", {}), dict) else {}
    st.session_state.access_sessions = list(access.get("sessions", []))
    st.session_state.sauvegardes = list(access.get("sauvegardes", payload.get("sauvegardes", [])))


def build_payload() -> dict[str, Any]:
    return {
        "outil": TOOL_NAME,
        "nom_outil": APP_DISPLAY_NAME,
        "version_application": APP_VERSION,
        "version_socle_clarte360": SOCLE_VERSION,
        "identifiant_racine_passation": st.session_state.get("root_passage_id", ""),
        "identifiant_session": st.session_state.get("session_id", ""),
        "date_export": datetime.now().isoformat(timespec="seconds"),
        "session": {
            "code_acces_valide": bool(st.session_state.get("code_verified", False)),
            "json_transmis_consultant": bool(st.session_state.get("final_json_sent", False)),
            "session_started_at": st.session_state.get("session_started_at", ""),
            "session_last_activity": datetime.now().isoformat(timespec="seconds"),
        },
        "consultant": st.session_state.get("consultant", ""),
        "rgpd": {
            "consentement": bool(st.session_state.get("rgpd_consent", False)),
            "date_consentement": st.session_state.get("rgpd_consent_at", ""),
            "version_texte": st.session_state.get("rgpd_text_version", "RGPD-Clarte360-2026-07"),
            "rappel": "Aucune donnée n'est stockée automatiquement sur les serveurs Clarté360 ; le JSON appartient au bénéficiaire.",
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
        "access": {
            "timeout_minutes": 15,
            "sessions": merged_session_history(True),
            "sauvegardes": st.session_state.get("sauvegardes", []),
        },
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


def pdf_footer(canvas, doc):
    canvas.saveState()
    footer1 = "CLARTÉ360 - 60 rue François 1er - 75008 Paris - Tél. : 01 89 48 08 25 - E-mail : contact@clarte360.com - Web : www.clarte360.com"
    footer2 = "RCS : 102349834 - SIRET : 10234983400014 - NAF : 8559A - TVA intracommunautaire : FR88102349834"
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawCentredString(landscape(A4)[0] / 2, 0.42 * cm, footer1)
    canvas.drawCentredString(landscape(A4)[0] / 2, 0.22 * cm, footer2)
    canvas.drawRightString(landscape(A4)[0] - 1.2 * cm, 0.22 * cm, f"Page {doc.page}")
    canvas.restoreState()

def make_pdf_bytes(fig_png: bytes | None = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1.2*cm, leftMargin=1.2*cm, topMargin=0.8*cm, bottomMargin=1.15*cm)
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor(BRAND)
    styles["Heading2"].textColor = colors.HexColor(BRAND)
    story = []
    if LOGO_PATH.exists():
        story.append(Image(str(LOGO_PATH), width=3.8*cm, height=1.4*cm, kind="proportional"))
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
    doc.build(story, onFirstPage=pdf_footer, onLaterPages=pdf_footer)
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




def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def mark_activity() -> None:
    st.session_state.session_last_activity = now_iso()


def total_session_seconds() -> int:
    started = st.session_state.get("session_started_at")
    try:
        return int((datetime.now() - datetime.fromisoformat(started)).total_seconds())
    except Exception:
        return 0


def format_seconds(seconds: int | float | None) -> str:
    seconds = int(seconds or 0)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m:02d}min"
    return f"{m}min {s:02d}s"



def current_session_record() -> dict[str, Any]:
    started = st.session_state.get("session_started_at", now_iso())
    last_activity = st.session_state.get("session_last_activity", now_iso())
    return {
        "session_id": st.session_state.get("session_id", ""),
        "started_at": started,
        "last_activity_at": last_activity,
        "last_seen_at": now_iso(),
        "ended_at": "",
        "duration_seconds": total_session_seconds(),
        "client_network": {},
    }


def merged_session_history(include_current: bool = True) -> list[dict[str, Any]]:
    sessions = []
    for sess in st.session_state.get("access_sessions", []):
        if isinstance(sess, dict):
            sessions.append(dict(sess))
    if include_current and st.session_state.get("code_verified"):
        current = current_session_record()
        sid = current.get("session_id")
        replaced = False
        for i, sess in enumerate(sessions):
            if sess.get("session_id") == sid:
                sessions[i].update(current)
                replaced = True
                break
        if not replaced:
            sessions.append(current)
    return sessions


def total_tracked_seconds() -> int:
    total = 0
    for sess in merged_session_history(True):
        try:
            total += int(sess.get("duration_seconds", 0) or 0)
        except Exception:
            pass
    return total


def close_current_session(reason: str = "sortie_utilisateur") -> None:
    now = now_iso()
    current = current_session_record()
    current["ended_at"] = now
    current["close_reason"] = reason
    sid = current.get("session_id")
    sessions = merged_session_history(False)
    replaced = False
    for i, sess in enumerate(sessions):
        if sess.get("session_id") == sid:
            sessions[i].update(current)
            replaced = True
            break
    if not replaced:
        sessions.append(current)
    st.session_state.access_sessions = sessions


def header() -> None:
    col_logo, col_title = st.columns([0.13, 0.87])
    with col_logo:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=72)
    with col_title:
        st.markdown(
            f"<div class='brand-header'><h1>{APP_DISPLAY_NAME}</h1><div class='small-note'>Version {APP_VERSION} · {SOCLE_VERSION}</div></div>",
            unsafe_allow_html=True,
        )


def rgpd_information_block() -> None:
    st.markdown(f"""
### Protection des données personnelles (RGPD)

Cette application Clarté360 fonctionne sans base de données serveur propre à l'application. Aucune donnée n'est enregistrée durablement sur un serveur Clarté360 par l'application.

Le fichier JSON constitue le seul support de conservation de votre travail. Il peut contenir votre identité, votre adresse e-mail, le nom de votre accompagnateur, les dates et heures de connexion, la durée des sessions, les événements saisis, les commentaires facultatifs et les exports nécessaires au rapport.

Le fichier JSON appartient exclusivement au bénéficiaire. Vous choisissez librement de le conserver, de le supprimer ou de le transmettre à votre accompagnateur.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : {st.session_state.get('rgpd_text_version', 'RGPD-Clarte360-2026-07')}.

### Nature de l'outil

La ligne de vie est un support de réflexion et d'échange. Elle ne constitue ni un diagnostic psychologique, ni un avis médical, ni une décision d'orientation automatique.

### Propriété intellectuelle

Les applications, outils, méthodes, graphiques, rapports et contenus proposés par Clarté360 constituent des créations originales protégées. Toute reproduction, adaptation, diffusion ou réutilisation sans autorisation écrite préalable est interdite.
""")


def legal_mentions_block() -> None:
    st.markdown("""
### Clarté360 SAS

**Adresse :** 60 rue François 1er – 75008 Paris  
**Téléphone :** 01 89 48 08 25  
**E-mail :** contact@clarte360.com  
**Site internet :** www.clarte360.com  

**RCS :** 102349834  
**SIRET :** 10234983400014  
**Code NAF :** 8559 A  
**TVA intracommunautaire :** FR88102349834

### Responsabilité
Les résultats proposés constituent des supports de réflexion et d'échange avec le consultant ou l'accompagnateur. Ils ne remplacent pas un accompagnement professionnel lorsque celui-ci est prévu.
""")


def contact_form_main() -> None:
    st.markdown("""
### Contacter Clarté360
Vous pouvez nous adresser une question administrative, signaler un problème technique ou nous faire part d'une suggestion concernant cette application.

Pour toute question relative à l'interprétation des exercices ou des résultats, rapprochez-vous de votre consultant ou accompagnateur.
""")
    with st.form("contact_form_standard"):
        c1, c2 = st.columns(2)
        with c1:
            prenom = st.text_input("Prénom", value=st.session_state.get("first_name", ""))
            nom = st.text_input("Nom", value=st.session_state.get("last_name", ""))
        with c2:
            email = st.text_input("Adresse email", value=st.session_state.get("email", ""))
            telephone = st.text_input("Téléphone facultatif")
        objet = st.text_input("Objet")
        message = st.text_area("Message")
        consent = st.checkbox("Je consens au traitement de ma demande par Clarté360.")
        send = st.form_submit_button("Envoyer le message", type="primary")
    if send:
        if not email.strip() or not objet.strip() or not message.strip() or not consent:
            st.error("Merci de renseigner l'e-mail, l'objet, le message et le consentement.")
        else:
            body = (
                "Message envoyé depuis l'application Clarté360 - Ligne de vie.\n\n"
                f"Bénéficiaire : {prenom} {nom}\nEmail : {email}\nTéléphone : {telephone}\n"
                f"Application : {APP_DISPLAY_NAME}\nVersion : {APP_VERSION}\nSocle : {SOCLE_VERSION}\n"
                f"Date : {now_iso()}\nSession : {st.session_state.get('session_id','')}\nTemps session : {format_seconds(total_session_seconds())}\n\n"
                f"Objet : {objet}\n\nMessage :\n{message}\n"
            )
            ok, msg = send_email(FINAL_EMAIL_TO, f"Clarté360 Ligne de vie - {objet}", body)
            if ok:
                st.success("Votre message a été transmis à Clarté360.")
            else:
                st.error(msg)


def rgpd_page() -> None:
    header()
    if st.session_state.get("code_verified") and st.button("← Retour à l'application", key="rgpd_back_top"):
        st.session_state.show_rgpd_page = False
        st.rerun()
    st.subheader("Informations légales et protection des données")
    tabs = st.tabs(["Protection des données", "Mentions légales", "Nous contacter"])
    with tabs[0]:
        rgpd_information_block()
        st.markdown("### Traçabilité")
        st.write(f"Temps cumulé enregistré : **{format_seconds(total_tracked_seconds())}**")
        sessions = merged_session_history(True)
        if sessions:
            st.dataframe(pd.DataFrame(sessions), use_container_width=True)
        else:
            st.caption("La traçabilité sera alimentée après le démarrage d'une session.")
    with tabs[1]:
        legal_mentions_block()
    with tabs[2]:
        contact_form_main()


def contact_page() -> None:
    header()
    if st.session_state.get("code_verified") and st.button("← Retour à l'application", key="contact_back_top"):
        st.session_state.show_contact_page = False
        st.rerun()
    contact_form_main()


def welcome_screen() -> bool:
    if st.session_state.get("welcome_done"):
        return True
    choice = st.session_state.get("welcome_choice")
    if choice == "import":
        return import_json_screen()
    if choice == "new":
        st.session_state.welcome_done = True
        st.rerun()
    header()
    st.markdown("### Bienvenue dans l'application Clarté360 – Ligne de vie")
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
    return False


def import_json_screen() -> bool:
    header()
    st.subheader("Reprise d'une session")
    st.markdown("Importez le JSON conservé lors de votre dernière utilisation. Une nouvelle session de connexion sera créée.")
    uploaded = st.file_uploader("Importer mon fichier JSON", type=["json"], key="welcome_json_upload_standard")
    if uploaded is not None:
        try:
            loaded = json.loads(uploaded.getvalue().decode("utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("Format JSON invalide")
            load_payload(loaded)
            st.session_state.welcome_done = True
            st.session_state.code_verified = True
            st.success("JSON chargé. Votre progression a été reprise.")
            st.rerun()
        except Exception as exc:
            st.error(f"JSON non valide : {exc}")
    if st.button("Retour à l'accueil"):
        st.session_state.pop("welcome_choice", None)
        st.rerun()
    return False


def access_gate() -> bool:
    if not welcome_screen():
        return False
    if st.session_state.get("code_verified"):
        return True
    header()
    st.markdown("## Accès bénéficiaire")
    st.write("Cet outil sert de support d'exploration chronologique et d'échange avec votre consultant Clarté360.")
    rgpd_information_block()
    if not st.session_state.get("code_sent"):
        with st.form("access_request_form"):
            c1, c2 = st.columns(2)
            with c1:
                prenom = st.text_input("Prénom *")
                nom = st.text_input("Nom *")
            with c2:
                email = st.text_input("Adresse email *")
                consultant = st.text_input("Consultant", value="Clarté360")
            consent = st.checkbox("J'ai lu les informations RGPD ci-dessus et je consens à l'utilisation de ces données dans le cadre exclusif de mon accompagnement. Je comprends qu'aucune donnée n'est conservée sur un serveur Clarté360 et que le fichier JSON reste sous mon contrôle.")
            submit = st.form_submit_button("Recevoir / générer mon code d'accès", type="primary")
        if submit:
            if not prenom.strip() or not nom.strip() or not email.strip():
                st.error("Merci de renseigner le prénom, le nom et l'adresse email.")
            elif "@" not in email or "." not in email:
                st.error("Merci de renseigner une adresse email valide.")
            elif not consent:
                st.error("Merci de confirmer votre consentement pour poursuivre.")
            else:
                b = {"prenom": prenom.strip(), "nom": nom.strip(), "email": email.strip(), "consultant": consultant.strip()}
                code = generate_access_code()
                ok, msg = send_access_code_email(b, code)
                st.session_state.pending_beneficiaire = b
                st.session_state.access_code = code
                st.session_state.code_sent = True
                if ok:
                    st.success("Un code d'accès vient d'être envoyé à l'adresse email indiquée.")
                else:
                    st.warning("Le code n'a pas pu être envoyé par e-mail. Mode test affiché ci-dessous.")
                    st.caption(msg)
                    st.info(f"Mode test : code généré = {code}")
                st.rerun()
    else:
        b = st.session_state.get("pending_beneficiaire", {})
        st.success(f"Code généré pour : {b.get('prenom','')} {b.get('nom','')} - {b.get('email','')}")
        code_input = st.text_input("Saisir le code d'accès", max_chars=6, type="password")
        c1, c2 = st.columns([0.25, 0.75])
        with c1:
            if st.button("Entrer dans l'outil", type="primary"):
                if code_input.strip() == st.session_state.get("access_code", ""):
                    st.session_state.code_verified = True
                    st.session_state.first_name = b.get("prenom", "")
                    st.session_state.last_name = b.get("nom", "")
                    st.session_state.email = b.get("email", "")
                    st.session_state.consultant = b.get("consultant", "Clarté360")
                    st.session_state.rgpd_consent = True
                    st.session_state.rgpd_consent_at = now_iso()
                    st.session_state.session_started_at = now_iso()
                    st.session_state.session_last_activity = now_iso()
                    st.session_state.page = "1. Bénéficiaire"
                    st.rerun()
                else:
                    st.error("Code incorrect.")
        with c2:
            if st.button("Je n'ai pas reçu le code : générer un nouveau code"):
                code = generate_access_code()
                st.session_state.access_code = code
                ok, msg = send_access_code_email(b, code)
                if ok:
                    st.success("Un nouveau code vient d'être envoyé.")
                else:
                    st.warning("Le nouveau code n'a pas pu être envoyé. Mode test affiché ci-dessous.")
                    st.info(f"Mode test : nouveau code généré = {code}")
    return False


def mark_json_downloaded():
    st.session_state.json_downloaded = True


def prepare_sidebar_json(close_session: bool = False, reason: str = "sauvegarde_manuelle_reprise"):
    if close_session:
        close_current_session(reason)
    sauvegarde = {"date": now_iso(), "motif": reason, "close_session": bool(close_session), "session_id": st.session_state.get("session_id", "")}
    st.session_state.setdefault("sauvegardes", []).append(sauvegarde)
    payload = build_payload()
    base_name = export_name(st.session_state.get("last_name", ""), st.session_state.get("first_name", ""), "json")
    st.session_state.exit_json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    st.session_state.exit_json_filename = base_name
    st.session_state.exit_json_ready = True
    st.session_state.json_downloaded = False


def sidebar() -> None:
    data_active = bool(st.session_state.get("code_verified"))
    if data_active:
        st.sidebar.markdown("### Navigation")
        pages = [
            "1. Bénéficiaire",
            "2. Consignes",
            "3. Événements",
            "4. Ligne de vie",
            "5. Remontées",
            "6. Export / Rapports",
        ]
        if st.session_state.get("page") not in pages:
            st.session_state.page = pages[0]
        previous = st.session_state.page
        selected = st.sidebar.radio("", pages, index=pages.index(previous), label_visibility="collapsed")
        if selected != previous:
            st.session_state.show_contact_page = False
            st.session_state.show_rgpd_page = False
            mark_activity()
        st.session_state.page = selected
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Session")
        st.sidebar.markdown("Votre progression est enregistrée dans votre fichier JSON.")
        if st.sidebar.button("💾 Préparer mon JSON pour reprendre plus tard", use_container_width=True):
            prepare_sidebar_json(False, "sauvegarde_manuelle_reprise")
            st.rerun()
        if st.sidebar.button("🚪 Quitter et télécharger mon JSON", type="primary", use_container_width=True):
            prepare_sidebar_json(True, "sortie_utilisateur_par_bouton")
            st.rerun()
        if st.session_state.get("exit_json_ready"):
            st.sidebar.download_button(
                "⬇️ Télécharger le JSON préparé",
                data=st.session_state.get("exit_json_bytes", b""),
                file_name=st.session_state.get("exit_json_filename", "ligne_de_vie_clarte360.json"),
                mime="application/json",
                use_container_width=True,
                on_click=mark_json_downloaded,
            )
            st.sidebar.caption("Conservez ce JSON : il est nécessaire pour reprendre votre travail.")
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
    st.sidebar.caption(f"App v{APP_VERSION} · {SOCLE_VERSION} · Ligne de vie")
    if not data_active:
        if st.sidebar.button("Réinitialiser la session"):
            for key in ["code_verified", "welcome_done", "welcome_choice", "code_sent", "access_code", "pending_beneficiaire", "show_contact_page", "show_rgpd_page"]:
                st.session_state.pop(key, None)
            st.rerun()


def install_beforeunload_warning() -> None:
    if st.session_state.get("code_verified") and not st.session_state.get("json_downloaded"):
        components.html(
            """
            <script>
            window.parent.onbeforeunload = function (e) {
                const message = "Quitter le site ? Vos modifications risquent de ne pas être enregistrées.";
                e.preventDefault();
                e.returnValue = message;
                return message;
            };
            </script>
            """,
            height=0,
        )


def timeout_check() -> bool:
    if not st.session_state.get("code_verified"):
        return False
    try:
        last = datetime.fromisoformat(st.session_state.get("session_last_activity", now_iso()))
        return (datetime.now() - last).total_seconds() > 15 * 60
    except Exception:
        return False


def timeout_screen() -> None:
    close_current_session("timeout_inactivite")
    header()
    st.warning("Votre session semble inactive depuis plus de 15 minutes. Préparez et téléchargez votre JSON avant de quitter ou reprenez votre travail.")
    if st.button("Préparer mon JSON maintenant", type="primary"):
        prepare_sidebar_json(True, "timeout_utilisateur")
        st.rerun()
    if st.session_state.get("exit_json_ready"):
        st.download_button("Télécharger le JSON préparé", data=st.session_state.exit_json_bytes, file_name=st.session_state.exit_json_filename, mime="application/json", on_click=mark_json_downloaded)


def page_beneficiaire() -> None:
    st.markdown("## 1. Identification du bénéficiaire")
    st.markdown("""
    <div class='privacy-box'>
    🔒 <strong>Confidentialité et maîtrise de vos données</strong><br>
    Aucune donnée personnelle ou sensible saisie dans cette application n'est sauvegardée sur un serveur Clarté360.
    Vous devez télécharger le fichier <strong>JSON</strong> pour reprendre votre travail plus tard.
    </div>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.first_name = st.text_input("Prénom du bénéficiaire", value=st.session_state.get("first_name", ""))
    with c2:
        st.session_state.last_name = st.text_input("Nom du bénéficiaire", value=st.session_state.get("last_name", ""))
    with c3:
        st.session_state.email = st.text_input("Adresse email", value=st.session_state.get("email", ""))
    c4, c5 = st.columns(2)
    with c4:
        st.session_state.consultant = st.text_input("Consultant", value=st.session_state.get("consultant", "Clarté360"))
    with c5:
        st.session_state.birthdate = st.date_input(
            "Date de naissance",
            value=st.session_state.birthdate or date(1980, 1, 1),
            min_value=date(1920, 1, 1), max_value=date.today(),
        )
    if st.session_state.birthdate:
        current_age = decimal_age(st.session_state.birthdate, date.today())
        st.metric("Âge actuel", f"{current_age:.1f} ans")
    mark_activity()


def page_consignes() -> None:
    st.markdown("## 2. Consignes")
    st.markdown("""
    <div class='rule-box'>
    <strong>Objectif de l'outil</strong><br>
    La ligne de vie permet de représenter les événements marquants de votre parcours sur un axe chronologique exprimé en âge.
    Dans cette étape, il ne s'agit pas d'analyser votre histoire mais de la poser visuellement, avec vos propres repères.
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""
    - Vous saisissez les événements qui vous semblent importants.
    - Chaque événement reçoit une position libre entre -10 et +10.
    - Le jour 00 est accepté lorsque la date exacte n'est pas connue.
    - L'exploration des remontées est facultative et sert uniquement de support d'entretien.
    """)
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.start_age = st.number_input(
            "À partir de quel âge souhaitez-vous commencer ?",
            min_value=0, max_value=120, value=int(st.session_state.start_age), step=1,
        )
    with c2:
        st.session_state.projection_years = st.selectbox(
            "Afficher une zone de projection future ?",
            options=[0, 5, 10],
            index=[0, 5, 10].index(int(st.session_state.projection_years)) if int(st.session_state.projection_years) in [0, 5, 10] else 0,
            format_func=lambda x: "Non" if x == 0 else f"Oui, projection à {x} ans",
        )
    mark_activity()


def page_evenements() -> None:
    st.markdown("## 3. Événements")
    with st.form("event_form", clear_on_submit=True):
        st.markdown("**Ajouter un événement :** date, nom court affiché sur la ligne, position libre entre -10 et +10.")
        c1, c2, c3, c4 = st.columns([0.8, 0.9, 1, 1.3])
        with c1:
            day_text = st.text_input("Jour", value="01", max_chars=2, help="Si vous ne connaissez pas le jour exact, vous pouvez saisir 00.")
        with c2:
            month = st.selectbox("Mois", list(range(1, 13)), format_func=lambda m: f"{m:02d}")
        with c3:
            year = st.number_input("Année", min_value=1920, max_value=date.today().year + 10, value=date.today().year, step=1)
        with c4:
            position = st.slider("Position sur la ligne", -10, 10, 0)
        nom_court = st.text_input("Nom court de l'événement *", max_chars=35, placeholder="Ex. Bac, 1er emploi, création entreprise")
        nom_long = st.text_input("Nom long (facultatif)")
        description = st.text_area("Description libre (facultative)")
        submitted = st.form_submit_button("Ajouter l'événement", type="primary")
    if submitted:
        if not st.session_state.get("birthdate"):
            st.error("Merci de renseigner la date de naissance dans l'étape 1.")
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
                st.session_state.events.append({
                    "id": str(uuid.uuid4()),
                    "date_precision": "Date avec jour 00 possible",
                    "date_reference": ed.isoformat(),
                    "jour_saisi": int(day),
                    "mois_saisi": int(month),
                    "annee_saisie": int(year),
                    "periode_affichee": display_date(int(year), int(month), int(day)),
                    "age": age,
                    "nom_court": nom_court.strip(),
                    "nom_long": nom_long.strip(),
                    "description": description.strip(),
                    "position": int(position),
                })
                st.success("Événement ajouté et reclassé automatiquement.")
                mark_activity()
            except Exception as exc:
                st.error(f"Date invalide : {exc}")
    if st.session_state.events:
        st.markdown("### Événements saisis")
        st.dataframe(events_df(), use_container_width=True, hide_index=True)
        sorted_events = sorted(enumerate(st.session_state.events), key=lambda x: (float(x[1].get("age", 0)), x[1].get("date_reference", "")))
        labels = [f"{e.get('age')} ans - {e.get('nom_court')} ({e.get('periode_affichee')})" for _, e in sorted_events]
        idx_label = st.selectbox("Choisir l'événement à supprimer", labels)
        if st.button("Supprimer l'événement sélectionné"):
            original_index = sorted_events[labels.index(idx_label)][0]
            st.session_state.events.pop(original_index)
            mark_activity()
            st.rerun()
    else:
        st.info("Ajoutez au moins un événement pour visualiser votre ligne de vie.")


def page_ligne_de_vie() -> None:
    st.markdown("## 4. Ligne de vie")
    fig = make_figure()
    st.plotly_chart(fig, use_container_width=True)
    if st.session_state.events:
        st.dataframe(events_df(), use_container_width=True, hide_index=True)
    else:
        st.info("Ajoutez au moins un événement dans l'étape 3.")
    mark_activity()


def page_remontees() -> None:
    st.markdown("## 5. Explorer certaines remontées")
    st.markdown("""
    <div class='rule-box'>
    Cette étape est facultative. Elle sert uniquement de support d'entretien : le bénéficiaire choisit les remontées qu'il souhaite approfondir.
    Il peut aussi décider de ne rien écrire et d'en parler seulement oralement avec le consultant.
    </div>
    """, unsafe_allow_html=True)
    segments = upward_segments()
    if not segments:
        st.info("Aucune remontée n'est encore détectée. Une remontée apparaît lorsqu'un point suivant est placé plus haut que le point précédent.")
        return
    labels = [segment_label(seg) for seg in segments]
    chosen_label = st.selectbox("Choisir une remontée à approfondir", ["Ne pas approfondir maintenant"] + labels)
    if chosen_label != "Ne pas approfondir maintenant":
        seg = segments[labels.index(chosen_label)]
        key = seg["key"]
        current = st.session_state.remontees.get(key, {})
        keep_trace = st.checkbox("Je souhaite conserver une trace écrite de cette réflexion", value=bool(current.get("trace_ecrite_souhaitee", False)))
        if keep_trace:
            ressources = st.text_area("Ressources mobilisées", value=current.get("ressources", ""))
            actions = st.text_area("Actions qui ont aidé à remonter", value=current.get("actions", ""))
            apprentissages = st.text_area("Ce que j'en retiens aujourd'hui", value=current.get("apprentissages", ""))
            if st.button("Enregistrer cette réflexion", type="primary"):
                st.session_state.remontees[key] = {
                    "trace_ecrite_souhaitee": True,
                    "evenement_depart": seg["from"].get("id"),
                    "evenement_arrivee": seg["to"].get("id"),
                    "libelle": chosen_label,
                    "ressources": ressources.strip(),
                    "actions": actions.strip(),
                    "apprentissages": apprentissages.strip(),
                    "date_maj": now_iso(),
                }
                st.success("Réflexion enregistrée dans le JSON.")
                mark_activity()


def page_export() -> None:
    st.markdown("## 6. Export / Rapports")
    payload = build_payload()
    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    fig = make_figure()
    fig_png = get_fig_png(fig)
    json_file_name = export_name(st.session_state.last_name, st.session_state.first_name, "json")
    cjson, ccsv, cpdf = st.columns(3)
    with cjson:
        st.download_button("Télécharger le JSON", data=json_bytes, file_name=json_file_name, mime="application/json", on_click=mark_json_downloaded)
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
        st.caption("Export PNG indisponible si Kaleido n'est pas disponible. Le PDF et le JSON restent disponibles.")
    mark_activity()


def main() -> None:
    init_state()
    sidebar()
    if st.session_state.get("show_contact_page"):
        contact_page()
        return
    if st.session_state.get("show_rgpd_page"):
        rgpd_page()
        return
    if not access_gate():
        return
    install_beforeunload_warning()
    if timeout_check():
        timeout_screen()
        return
    header()
    page = st.session_state.get("page", "1. Bénéficiaire")
    if page.startswith("1"):
        page_beneficiaire()
    elif page.startswith("2"):
        page_consignes()
    elif page.startswith("3"):
        page_evenements()
    elif page.startswith("4"):
        page_ligne_de_vie()
    elif page.startswith("5"):
        page_remontees()
    elif page.startswith("6"):
        page_export()
    else:
        page_beneficiaire()


if __name__ == "__main__":
    main()
