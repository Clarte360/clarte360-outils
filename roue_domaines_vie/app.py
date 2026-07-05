import io
import json
import secrets
import uuid
import smtplib
import string
from copy import deepcopy
from datetime import datetime, date, timedelta
from email.message import EmailMessage
from pathlib import Path

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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak

APP_TITLE = "Clarté360 - Roue des domaines de vie"
APP_VERSION = "1.4.0-socle-clarte360"
SOCLE_CLARTE360_VERSION = "3.0"
RGPD_TEXT_VERSION = "RGPD-Clarte360-v1.0-2026-07"
BENEFICIARY_TIMEOUT_MINUTES = 15
BRAND_COLOR = "#008080"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo_clarte360.png"

DOMAINES = {
    "Professionnel": "Tout ce qui concerne le monde du travail : emploi, recherche d'emploi, activité professionnelle, projet professionnel, formation liée au travail, responsabilités professionnelles.",
    "Personnel": "Le temps passé avec soi-même : repos, santé, loisirs personnels, sport individuel, réflexion, solitude choisie, relation à soi.",
    "Familial": "La famille au sens large : enfants, parents, frères et sœurs, famille élargie, belle-famille, obligations ou présences familiales.",
    "Couple / intimité": "La relation avec la personne qui partage l'intimité. Ce domaine est distinct de la famille. Il peut naturellement ne pas exister dans votre vie actuelle.",
    "Social / amitié": "Les relations hors famille, couple et travail : amis, voisins, vie associative, communauté, rencontres, activités collectives."
}
DEFAULT_ORDER = list(DOMAINES.keys())
DEFAULT_COLORS = ["#008080", "#F2C94C", "#EB5757", "#2F80ED", "#9B51E0", "#27AE60", "#F2994A"]
FINAL_EMAIL_TO = "contact@clarte360.com"
ACCESS_CODE_VALIDITY_MINUTES = 30

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

Le fichier JSON constitue le seul support de conservation de votre travail. Il peut contenir votre identité, votre adresse e-mail, le nom de votre accompagnateur, les dates et heures de connexion, la durée des sessions, vos données saisies dans l'application, commentaires, résultats, historique des connexions, code d'accès généré, consentement RGPD, version de l'application et informations techniques disponibles.

Le fichier JSON appartient exclusivement au bénéficiaire. Vous choisissez librement de le conserver, de le supprimer ou de le transmettre à votre accompagnateur.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : {RGPD_TEXT_VERSION}.

Les résultats fournis par les applications Clarté360 constituent des supports d'aide à la réflexion et à l'accompagnement. Ils ne constituent ni un diagnostic psychologique, ni un avis médical, ni une décision d'orientation automatique.

Les applications, outils, questionnaires, méthodes, graphiques, rapports et contenus proposés par Clarté360 constituent des créations originales protégées. Toute reproduction, adaptation, diffusion ou réutilisation sans autorisation écrite préalable est interdite.
"""

st.set_page_config(page_title=APP_TITLE, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🧭", layout="wide")

st.markdown(f"""
<style>
.main .block-container {{max-width: 1180px; padding-top: 1.6rem;}}
h1, h2, h3 {{color: {BRAND_COLOR} !important;}}
.brand-box {{background:#F1F8F8; border-left:6px solid {BRAND_COLOR}; padding:16px 18px; border-radius:10px; line-height:1.55;}}
.info-box {{background:#F8FAFC; border:1px solid #E5E7EB; padding:14px 16px; border-radius:10px; line-height:1.55;}}
.warn-box {{background:#FFF7E6; border-left:5px solid #F2C94C; padding:12px 14px; border-radius:8px; line-height:1.5;}}
.ok-box {{background:#ECFDF5; border-left:5px solid #10B981; padding:12px 14px; border-radius:8px; line-height:1.5;}}
.small-note {{color:#6B7280; font-size:0.92rem;}}
div.stButton > button:first-child {{border-radius:10px; border:1px solid {BRAND_COLOR}; color:{BRAND_COLOR}; background:white;}}
div.stButton > button:first-child:hover {{background:#F1F8F8; color:{BRAND_COLOR}; border-color:{BRAND_COLOR};}}
div.stButton > button[kind="primary"] {{background:{BRAND_COLOR} !important; color:white !important; border:1px solid {BRAND_COLOR} !important;}}
div.stButton > button[kind="primary"] * {{color:white !important;}}
div.stDownloadButton > button:first-child {{border-radius:10px; border:1px solid {BRAND_COLOR}; color:{BRAND_COLOR}; background:white;}}
</style>
""", unsafe_allow_html=True)


def generate_access_code(length=6):
    alphabet = (string.ascii_uppercase + string.digits).replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_email_config() -> dict | None:
    """Lit la configuration SMTP Streamlit Secrets, section [email]."""
    try:
        cfg = st.secrets.get("email", {})
        required = ["smtp_server", "smtp_port", "smtp_user", "smtp_password", "from_email", "to_email"]
        if all(k in cfg and str(cfg[k]).strip() for k in required):
            return {k: str(cfg[k]).strip() for k in required}
    except Exception:
        pass
    return None


def send_email(to_email: str, subject: str, body: str, attachment: bytes | None = None, attachment_name: str | None = None) -> tuple[bool, str]:
    cfg = get_email_config()
    if not cfg:
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


def send_access_code_email(beneficiaire: dict, access_code: str, expires_at: datetime) -> tuple[bool, str]:
    cfg = get_email_config()
    if not cfg:
        return False, "SMTP non configuré : impossible d'envoyer le code d'accès. Configurez les Secrets Streamlit."

    prenom = beneficiaire.get("prenom", "")
    nom = beneficiaire.get("nom", "")
    email = beneficiaire.get("email", "")
    consultant = beneficiaire.get("consultant", "")
    date_realisation = beneficiaire.get("date_realisation", "")
    admin_to = cfg.get("to_email", FINAL_EMAIL_TO)
    now_txt = datetime.now().isoformat(timespec="seconds")
    expires_txt = expires_at.strftime("%H:%M")

    subject_admin = "Clarté360 - Nouveau code d'accès Roue des domaines de vie"
    body_admin = (
        "Une personne vient de demander un code d'accès pour réaliser l'outil Clarté360 - Roue des domaines de vie.\n\n"
        f"Prénom : {prenom}\n"
        f"Nom : {nom}\n"
        f"Email : {email}\n"
        f"Consultant : {consultant}\n"
        f"Date de réalisation : {date_realisation}\n"
        f"Code généré : {access_code}\n"
        f"Durée de validité : {ACCESS_CODE_VALIDITY_MINUTES} minutes, jusqu'à {expires_txt} environ.\n"
        f"Date/heure : {now_txt}\n"
    )
    ok_admin, msg_admin = send_email(admin_to, subject_admin, body_admin)

    subject_user = "Votre code d'accès Clarté360"
    body_user = (
        f"Bonjour {prenom},\n\n"
        "Voici votre code d'accès pour démarrer l'outil Clarté360 - Roue des domaines de vie :\n\n"
        f"{access_code}\n\n"
        f"Ce code est valable {ACCESS_CODE_VALIDITY_MINUTES} minutes.\n\n"
        "Vos réponses restent sous votre contrôle. Le fichier JSON final pourra être transmis à votre consultant Clarté360 afin de préparer l'analyse et la restitution.\n\n"
        "Cordialement,\nClarté360\n"
    )
    ok_user, msg_user = send_email(email, subject_user, body_user)
    if ok_user:
        return True, "Code envoyé au bénéficiaire."
    return False, f"Notification consultant : {msg_admin} / Envoi bénéficiaire : {msg_user}"


def send_final_json_to_consultant(data: dict, json_bytes_data: bytes, file_name: str) -> tuple[bool, str]:
    cfg = get_email_config()
    destination = cfg.get("to_email", FINAL_EMAIL_TO) if cfg else FINAL_EMAIL_TO
    b = data.get("beneficiaire", {})
    subject = "Clarté360 - JSON final Roue des domaines de vie"
    body = (
        "Le bénéficiaire a généré le JSON final de l'outil Clarté360 - Roue des domaines de vie.\n\n"
        f"Prénom : {b.get('prenom','')}\n"
        f"Nom : {b.get('nom','')}\n"
        f"Email : {b.get('email','')}\n"
        f"Consultant : {b.get('consultant','')}\n"
        f"Date de réalisation : {b.get('date_realisation','')}\n"
        f"Date/heure d'envoi : {datetime.now().isoformat(timespec='seconds')}\n\n"
        "Le JSON joint permet de reprendre les données et de régénérer les sorties de l'outil.\n"
    )
    return send_email(destination, subject, body, attachment=json_bytes_data, attachment_name=file_name)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def get_client_network():
    headers = {}
    try:
        headers = dict(st.context.headers)
    except Exception:
        pass
    def h(name):
        for k, v in headers.items():
            if str(k).lower() == name.lower():
                return str(v)
        return ""
    forwarded = h("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (h("x-real-ip") or h("cf-connecting-ip"))
    return {"ip": ip, "user_agent": h("user-agent"), "headers_available": bool(headers)}


def empty_data():
    root_id = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    now = now_iso()
    return {
        "app": APP_TITLE,
        "outil": "roue_domaines_vie",
        "nom_outil": "Roue des domaines de vie",
        "version": APP_VERSION,
        "version_application": APP_VERSION,
        "version_socle_clarte360": SOCLE_CLARTE360_VERSION,
        "created_at": now,
        "updated_at": now,
        "passation_root_id": root_id,
        "session_id": sid,
        "beneficiaire": {"prenom":"", "nom":"", "email":"", "consultant":"", "date_realisation": str(date.today())},
        "rgpd": {"consentement": False, "accepted_at": "", "texte_version": RGPD_TEXT_VERSION},
        "access": {"timeout_minutes": BENEFICIARY_TIMEOUT_MINUTES, "code_history": [], "sessions": [], "sauvegardes": [], "code_verified": False},
        "access_code": "",
        "phase": 1,
        "actuel": {"domaines_presents": [], "valeurs": {}, "notes": {}},
        "debrief_actuel_termine": False,
        "ideal": {"domaines_presents": [], "valeurs": {}, "notes": {}},
        "ideal_valide": False,
        "comparaison": {"constats":"", "actions": []}
    }


def ensure_runtime_tracking(user_activity=True):
    data = st.session_state.get("data")
    if not isinstance(data, dict):
        return
    data.setdefault("version_application", APP_VERSION)
    data.setdefault("version_socle_clarte360", SOCLE_CLARTE360_VERSION)
    data.setdefault("passation_root_id", str(uuid.uuid4()))
    data.setdefault("access", {})
    access = data["access"]
    access.setdefault("timeout_minutes", BENEFICIARY_TIMEOUT_MINUTES)
    access.setdefault("sessions", [])
    access.setdefault("sauvegardes", [])
    if "active_session_id" not in st.session_state:
        st.session_state.active_session_id = data.get("session_id") or str(uuid.uuid4())
    sid = st.session_state.active_session_id
    now = now_iso()
    sess = next((x for x in access["sessions"] if x.get("session_id") == sid), None)
    if sess is None:
        sess = {"session_id": sid, "started_at": now, "last_activity_at": now, "last_seen_at": now, "ended_at": "", "duration_seconds": 0, "client_network": get_client_network()}
        access["sessions"].append(sess)
    last = sess.get("last_activity_at") or sess.get("started_at") or now
    try:
        seconds = int((datetime.fromisoformat(now) - datetime.fromisoformat(last)).total_seconds())
    except Exception:
        seconds = 0
    if user_activity:
        sess["last_activity_at"] = now
    sess["last_seen_at"] = now
    try:
        sess["duration_seconds"] = int((datetime.fromisoformat(now) - datetime.fromisoformat(sess.get("started_at", now))).total_seconds())
    except Exception:
        pass
    data["updated_at"] = now


def total_duration_seconds(data):
    return int(sum(int(s.get("duration_seconds", 0) or 0) for s in data.get("access", {}).get("sessions", [])))


def format_duration(seconds):
    seconds = int(seconds or 0)
    h, r = divmod(seconds, 3600)
    m, sec = divmod(r, 60)
    if h:
        return f"{h} h {m:02d} min"
    return f"{m} min {sec:02d} s"


def record_save_event(reason):
    data = st.session_state.get("data")
    if isinstance(data, dict):
        data.setdefault("access", {}).setdefault("sauvegardes", []).append({"at": now_iso(), "reason": reason, "session_id": st.session_state.get("active_session_id", data.get("session_id", ""))})
        data["updated_at"] = now_iso()


def mark_current_session_closed(reason):
    data = st.session_state.get("data")
    if not isinstance(data, dict):
        return
    sid = st.session_state.get("active_session_id")
    for sess in data.setdefault("access", {}).setdefault("sessions", []):
        if sess.get("session_id") == sid and not sess.get("ended_at"):
            sess["ended_at"] = now_iso()
            sess["close_reason"] = reason
    record_save_event(reason)


def is_timed_out():
    if not st.session_state.get("code_verified"):
        return False
    data = st.session_state.get("data", {})
    sid = st.session_state.get("active_session_id")
    sess = next((x for x in data.get("access", {}).get("sessions", []) if x.get("session_id") == sid), None)
    if not sess:
        return False
    last = sess.get("last_activity_at") or sess.get("started_at")
    try:
        inactive = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
    except Exception:
        return False
    return inactive >= BENEFICIARY_TIMEOUT_MINUTES * 60


def timeout_watchdog():
    if st_autorefresh is not None and st.session_state.get("code_verified"):
        st_autorefresh(interval=10000, key="clarte360_roue_timeout_watchdog")


def timeout_screen():
    mark_current_session_closed("timeout_inactivite")
    st.error("Votre session a été interrompue après une période d'inactivité. Téléchargez votre JSON de sauvegarde avant de quitter.")
    st.download_button("Télécharger mon JSON de sauvegarde", data=json_bytes(), file_name=safe_filename("roue_domaines_vie_timeout", "json"), mime="application/json", type="primary", on_click=mark_json_downloaded)


def init_state():
    if "data" not in st.session_state:
        st.session_state.data = empty_data()
    if "code_verified" not in st.session_state:
        st.session_state.code_verified = False
    defaults = {
        "access_code": "",
        "code_sent": False,
        "code_expires_at": None,
        "pending_beneficiaire": None,
        "final_json_sent": False,
        "welcome_done": False,
        "welcome_choice": None,
        "show_rgpd_page": False,
        "show_contact_page": False,
        "exit_json_ready": False,
        "json_downloaded": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def header():
    cols = st.columns([1, 8])
    with cols[0]:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=70)
    with cols[1]:
        st.markdown(f"# {APP_TITLE}")
        st.markdown(f"<div class='small-note'>{APP_VERSION} - outil d'exploration accompagné</div>", unsafe_allow_html=True)


def norm_values(values, selected):
    out = {d: float(values.get(d, 0)) for d in selected}
    total = sum(max(0, v) for v in out.values())
    if total <= 0:
        return out, 0
    return {d: round(max(0, v) * 100 / total, 1) for d, v in out.items()}, total


def pie_png(values, title):
    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    labels = [k for k, v in values.items() if v > 0]
    sizes = [v for v in values.values() if v > 0]
    if not labels:
        ax.text(0.5, 0.5, "Aucune donnée", ha="center", va="center")
        ax.axis("off")
    else:
        colors_list = DEFAULT_COLORS[:len(labels)]
        ax.pie(sizes, labels=[f"{l}\n{v:g}%" for l, v in zip(labels, sizes)], startangle=90, colors=colors_list, wedgeprops={"linewidth": 1, "edgecolor": "white"})
        ax.axis("equal")
    ax.set_title(title, color=BRAND_COLOR, fontsize=14, fontweight="bold")
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def display_pie(values, title):
    st.image(pie_png(values, title), use_container_width=True)


def json_bytes():
    return json.dumps(st.session_state.data, ensure_ascii=False, indent=2).encode("utf-8")


def safe_filename(prefix, ext):
    b = st.session_state.data.get("beneficiaire", {})
    name = f"{b.get('nom','')}_{b.get('prenom','')}".strip("_").replace(" ", "_") or "beneficiaire"
    return f"{prefix}_{name}_{date.today().isoformat()}.{ext}"



def pdf_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#666666"))
    footer = "CLARTÉ360 – 60 rue François 1er – 75008 Paris – Tél. : 01 89 48 08 25 – Email : contact@clarte360.com – Web : www.clarte360.com – RCS : 102349834 – SIRET : 10234983400014 – NAF : 8559 A – TVA : FR88102349834"
    canvas.drawCentredString(A4[0] / 2, 0.8 * cm, footer[:180])
    canvas.drawRightString(A4[0] - 1.5 * cm, 0.45 * cm, f"Page {doc.page}")
    canvas.restoreState()

def build_pdf():
    data = st.session_state.data
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TealTitle", parent=styles["Title"], textColor=colors.HexColor(BRAND_COLOR), fontSize=22, leading=26))
    styles.add(ParagraphStyle(name="TealH2", parent=styles["Heading2"], textColor=colors.HexColor(BRAND_COLOR), fontSize=15, leading=18))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=9, leading=11))
    story = []
    if LOGO_PATH.exists():
        logo = RLImage(str(LOGO_PATH), width=2.4*cm, height=2.4*cm)
        logo.hAlign = "CENTER"
        story.append(logo)
    story.append(Paragraph("Roue des domaines de vie", styles["TealTitle"]))
    b = data.get("beneficiaire", {})
    story.append(Paragraph(f"Bénéficiaire : {b.get('prenom','')} {b.get('nom','')}<br/>Consultant : {b.get('consultant','')}<br/>Date : {b.get('date_realisation','')}", styles["Normal"]))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Principe de l'exercice", styles["TealH2"]))
    story.append(Paragraph("L'exercice met en regard la roue actuelle et la roue idéale sans contrainte. Les parts représentent la présence ressentie de chaque domaine dans la vie de la personne, en tenant compte du temps occupé, de la charge mentale, de l'attention mobilisée et de l'énergie prise ou investie.", styles["Normal"]))
    story.append(Spacer(1, 0.5*cm))
    actuel_vals, _ = norm_values(data.get("actuel", {}).get("valeurs", {}), data.get("actuel", {}).get("domaines_presents", []))
    ideal_vals, _ = norm_values(data.get("ideal", {}).get("valeurs", {}), data.get("ideal", {}).get("domaines_presents", []))
    story.append(Paragraph("Roue actuelle", styles["TealH2"]))
    img1 = io.BytesIO(pie_png(actuel_vals, "Aujourd'hui"))
    story.append(RLImage(img1, width=14*cm, height=9*cm))
    story.append(Paragraph("Notes du débriefing actuel", styles["TealH2"]))
    notes = data.get("actuel", {}).get("notes", {})
    if notes:
        tbl = [["Domaine", "Note"]] + [[k, v or ""] for k, v in notes.items() if k in actuel_vals]
        t = Table(tbl, colWidths=[4*cm, 12*cm])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(BRAND_COLOR)),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
        story.append(t)
    else:
        story.append(Paragraph("Aucune note renseignée.", styles["Normal"]))
    story.append(PageBreak())
    story.append(Paragraph("Roue idéale sans contrainte", styles["TealH2"]))
    img2 = io.BytesIO(pie_png(ideal_vals, "Idéal sans contrainte"))
    story.append(RLImage(img2, width=14*cm, height=9*cm))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Comparaison", styles["TealH2"]))
    all_domains = list(dict.fromkeys(list(actuel_vals.keys()) + list(ideal_vals.keys())))
    comp_tbl = [["Domaine", "Aujourd'hui", "Idéal", "Écart"]]
    for d in all_domains:
        a = actuel_vals.get(d, 0)
        i = ideal_vals.get(d, 0)
        comp_tbl.append([d, f"{a:g}%", f"{i:g}%", f"{i-a:+g} pts"])
    t = Table(comp_tbl, colWidths=[5.5*cm, 3*cm, 3*cm, 3*cm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(BRAND_COLOR)),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey),('ALIGN',(1,1),(-1,-1),'CENTER')]))
    story.append(t)
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Constats", styles["TealH2"]))
    story.append(Paragraph(data.get("comparaison", {}).get("constats", "") or "Aucun constat renseigné.", styles["Normal"]))
    actions = data.get("comparaison", {}).get("actions", [])
    story.append(Paragraph("Actions imaginables", styles["TealH2"]))
    if actions:
        tbl = [["Domaine", "Action", "Premier pas", "Échéance"]]
        for a in actions:
            tbl.append([a.get("domaine", ""), a.get("action", ""), a.get("premier_pas", ""), a.get("echeance", "")])
        t = Table(tbl, colWidths=[3.2*cm, 5.5*cm, 4.2*cm, 2.5*cm])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(BRAND_COLOR)),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.25,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP')]))
        story.append(t)
    else:
        story.append(Paragraph("Aucune action renseignée.", styles["Normal"]))
    doc.build(story, onFirstPage=pdf_footer, onLaterPages=pdf_footer)
    buf.seek(0)
    return buf.getvalue()



def mark_json_downloaded():
    st.session_state.json_downloaded = True


def install_beforeunload_warning():
    if isinstance(st.session_state.get("data"), dict) and st.session_state.get("code_verified") and not st.session_state.get("json_downloaded"):
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


def legal_mentions_block():
    l = CLARTE360_LEGAL
    st.markdown(f"""
**{l['raison_sociale']}** – {l['forme']}  
{l['adresse']} – {l['code_postal_ville']}  
Tél. : {l['telephone']} – E-mail : {l['email']} – Web : {l['web']}  
RCS : {l['rcs']} – SIRET : {l['siret']} – NAF : {l['naf']} – TVA intracommunautaire : {l['tva']}

Les contenus, méthodes, rapports, graphiques et outils Clarté360 sont protégés par le droit de la propriété intellectuelle.
""")


def rgpd_information_block():
    st.markdown(RGPD_TEXT)


def contact_form_main():
    st.markdown("Vous pouvez nous adresser une question administrative, signaler un problème technique ou nous faire part d’une suggestion concernant cette application. Pour toute question relative à l’interprétation des exercices ou des résultats, rapprochez-vous de votre consultant ou accompagnateur.")
    b = st.session_state.get("data", {}).get("beneficiaire", {}) if isinstance(st.session_state.get("data"), dict) else {}
    with st.form("contact_clarte360_form"):
        c1, c2 = st.columns(2)
        with c1:
            prenom = st.text_input("Prénom", value=b.get("prenom", ""))
            nom = st.text_input("Nom", value=b.get("nom", ""))
            email = st.text_input("E-mail", value=b.get("email", ""))
        with c2:
            telephone = st.text_input("Téléphone facultatif")
            objet = st.text_input("Objet")
        message = st.text_area("Message", height=150)
        consent = st.checkbox("Je consens au traitement de ce message pour permettre à Clarté360 de me répondre.")
        submit = st.form_submit_button("Envoyer à Clarté360", type="primary")
    if submit:
        if not email or "@" not in email or not objet or not message:
            st.error("Merci de renseigner au minimum un e-mail valide, un objet et un message.")
        elif not consent:
            st.error("Merci de confirmer le consentement spécifique au traitement de votre demande.")
        else:
            data = st.session_state.get("data", {}) if isinstance(st.session_state.get("data"), dict) else {}
            body = f"""Message depuis l'application Clarté360.

Application : {APP_TITLE}
Version : {APP_VERSION}
Socle : {SOCLE_CLARTE360_VERSION}
Date/heure : {now_iso()}
Session : {st.session_state.get('active_session_id', data.get('session_id', ''))}
Temps cumulé : {format_duration(total_duration_seconds(data))}

Nom : {nom}
Prénom : {prenom}
E-mail : {email}
Téléphone : {telephone}
Objet : {objet}

Message :
{message}

Infos techniques : {json.dumps(get_client_network(), ensure_ascii=False)}
"""
            ok, msg = send_email(FINAL_EMAIL_TO, f"Clarté360 - Contact - {objet}", body)
            if ok:
                st.success("Votre message a été transmis à Clarté360.")
            else:
                st.error(msg)


def rgpd_page():
    header()
    if st.button("← Retour à l'application", key="rgpd_back"):
        st.session_state.show_rgpd_page = False
        st.rerun()
    st.subheader("Informations légales et protection des données")
    tab_rgpd, tab_mentions, tab_contact = st.tabs(["Protection des données", "Mentions légales", "Nous contacter"])
    with tab_rgpd:
        rgpd_information_block()
        data = st.session_state.get("data", {})
        if isinstance(data, dict):
            st.markdown("### Traçabilité")
            st.write(f"Temps cumulé enregistré : **{format_duration(total_duration_seconds(data))}**")
            sessions = data.get("access", {}).get("sessions", [])
            if sessions:
                st.dataframe(pd.DataFrame(sessions), use_container_width=True)
    with tab_mentions:
        legal_mentions_block()
    with tab_contact:
        contact_form_main()


def contact_page():
    header()
    if st.button("← Retour à l'application", key="contact_back"):
        st.session_state.show_contact_page = False
        st.rerun()
    st.subheader("Contacter Clarté360")
    contact_form_main()


def import_json_screen():
    header()
    st.markdown("### Reprendre une session avec mon fichier JSON")
    uploaded = st.file_uploader("Importer mon fichier JSON Clarté360", type=["json"], key="welcome_import_json")
    if uploaded is not None:
        try:
            loaded = json.loads(uploaded.read().decode("utf-8"))
            st.session_state.data = loaded
            st.session_state.active_session_id = str(uuid.uuid4())
            st.session_state.code_verified = True
            st.session_state.welcome_done = True
            st.session_state.welcome_choice = None
            ensure_runtime_tracking(True)
            record_save_event("reprise_depuis_json")
            st.success("JSON importé. Vous pouvez reprendre votre travail.")
            st.rerun()
        except Exception as exc:
            st.error(f"Import impossible : {exc}")
    if st.button("← Retour à l'accueil"):
        st.session_state.welcome_choice = None
        st.rerun()
    return False


def welcome_screen():
    if st.session_state.get("welcome_done"):
        return True
    if st.session_state.get("welcome_choice") == "import":
        return import_json_screen()
    if st.session_state.get("welcome_choice") == "new":
        st.session_state.data = empty_data()
        st.session_state.welcome_done = True
        st.session_state.welcome_choice = None
        st.rerun()
    header()
    st.markdown("### Bienvenue dans l'application Clarté360 – Roue des domaines de vie")
    st.markdown("Avez-vous conservé le fichier JSON de votre dernière utilisation ?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Oui → Importer mon fichier JSON", use_container_width=True):
            st.session_state.welcome_choice = "import"
            st.rerun()
    with c2:
        if st.button("Non → Commencer une nouvelle session", type="primary", use_container_width=True):
            st.session_state.welcome_choice = "new"
            st.rerun()
    st.info("Le fichier JSON est la mémoire unique de votre travail. Aucune donnée n'est sauvegardée durablement par l'application sur un serveur Clarté360.")
    return False


def prepare_sidebar_json(close_session=False, reason="sauvegarde_manuelle_reprise"):
    if close_session:
        mark_current_session_closed(reason)
    else:
        record_save_event(reason)
    st.session_state.exit_json_bytes = json_bytes()
    st.session_state.exit_json_filename = safe_filename("roue_domaines_vie", "json")
    st.session_state.exit_json_ready = True
    st.session_state.json_downloaded = False


def sidebar_tools():
    data_active = isinstance(st.session_state.get("data"), dict) and st.session_state.get("code_verified")
    st.sidebar.markdown("## Clarté360")
    st.sidebar.caption(f"App v{APP_VERSION} · Socle {SOCLE_CLARTE360_VERSION}")
    if data_active:
        st.sidebar.markdown("### Session")
        st.sidebar.caption("Votre progression est enregistrée dans votre fichier JSON.")
        if st.sidebar.button("💾 Préparer mon JSON pour reprendre plus tard", use_container_width=True):
            prepare_sidebar_json(False, "sauvegarde_manuelle_reprise")
            st.rerun()
        if st.sidebar.button("🚪 Quitter et télécharger mon JSON", type="primary", use_container_width=True):
            prepare_sidebar_json(True, "sortie_utilisateur_par_bouton")
            st.rerun()
        if st.session_state.get("exit_json_ready"):
            st.sidebar.download_button("⬇️ Télécharger le JSON préparé", data=st.session_state.get("exit_json_bytes", b""), file_name=st.session_state.get("exit_json_filename", "roue_domaines_vie.json"), mime="application/json", use_container_width=True, on_click=mark_json_downloaded)
            st.sidebar.caption("Conservez ce JSON : il est nécessaire pour reprendre votre travail.")
    st.sidebar.markdown("---")
    if st.sidebar.button("💬 Contacter Clarté360", use_container_width=True):
        st.session_state.show_contact_page = True
        st.session_state.show_rgpd_page = False
        st.rerun()
    if st.sidebar.button("RGPD et mentions légales", use_container_width=True):
        st.session_state.show_rgpd_page = True
        st.session_state.show_contact_page = False
        st.rerun()
    if not data_active and st.sidebar.button("Réinitialiser la session"):
        st.session_state.clear()
        st.rerun()
def access_gate():
    if not welcome_screen():
        return False
    header()
    data = st.session_state.data
    if st.session_state.code_verified:
        return True

    st.markdown("## Accès bénéficiaire")
    st.markdown(
        "<div class='brand-box'>"
        "Cet espace permet de préparer l'exercice de la roue des domaines de vie avec votre accompagnateur. "
        "Pour commencer, renseignez votre identité et votre adresse email. Un code d'accès à durée limitée vous sera envoyé par email. "
        "Un message automatique informe également Clarté360 qu'une personne utilise le programme."
        "</div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.get("code_sent", False):
        with st.form("access_code_form"):
            c1, c2 = st.columns(2)
            with c1:
                prenom = st.text_input("Prénom *", value=data["beneficiaire"].get("prenom", ""))
                nom = st.text_input("Nom *", value=data["beneficiaire"].get("nom", ""))
                email = st.text_input("Adresse email *", value=data["beneficiaire"].get("email", ""))
            with c2:
                consultant = st.text_input("Consultant", value=data["beneficiaire"].get("consultant", "Clarté360"))
                d = st.date_input("Date de réalisation", value=date.today())
            consent = st.checkbox("J’ai lu les informations RGPD et je consens à l’utilisation de ces données dans le cadre exclusif de mon accompagnement.")
            send_code = st.form_submit_button("Recevoir mon code d'accès", type="primary")

        if send_code:
            if not prenom.strip() or not nom.strip() or not email.strip():
                st.error("Merci de renseigner le prénom, le nom et l'adresse email.")
            elif "@" not in email or "." not in email:
                st.error("Merci de renseigner une adresse email valide.")
            elif not consent:
                st.error("Merci de confirmer votre consentement RGPD pour poursuivre.")
            else:
                beneficiaire_tmp = {
                    "prenom": prenom.strip(),
                    "nom": nom.strip(),
                    "email": email.strip(),
                    "consultant": consultant.strip(),
                    "date_realisation": str(d),
                }
                code = generate_access_code()
                expires_at = datetime.now() + timedelta(minutes=ACCESS_CODE_VALIDITY_MINUTES)
                ok, msg = send_access_code_email(beneficiaire_tmp, code, expires_at)
                if ok:
                    st.session_state.access_code = code
                    st.session_state.code_sent = True
                    st.session_state.code_expires_at = expires_at.isoformat(timespec="seconds")
                    st.session_state.pending_beneficiaire = beneficiaire_tmp
                    data["access_code"] = code
                    data["access_code_created_at"] = datetime.now().isoformat(timespec="seconds")
                    data["access_code_expires_at"] = st.session_state.code_expires_at
                    data["beneficiaire"] = beneficiaire_tmp
                    data.setdefault("rgpd", {})["consentement"] = True
                    data.setdefault("rgpd", {})["accepted_at"] = now_iso()
                    data.setdefault("rgpd", {})["texte_version"] = RGPD_TEXT_VERSION
                    data.setdefault("access", {}).setdefault("code_history", []).append({"code": code, "generated_at": data["access_code_created_at"], "expires_at": st.session_state.code_expires_at, "status": "sent"})
                    st.success("Un code d'accès vient d'être envoyé à l'adresse email indiquée.")
                    st.rerun()
                else:
                    st.error(msg)
                    st.caption("En ligne, configurez les Secrets SMTP Streamlit avec les paramètres OVH pour activer l'envoi du code.")
    else:
        b = st.session_state.get("pending_beneficiaire") or data.get("beneficiaire", {})
        st.success(f"Code envoyé à : {b.get('email','')}")
        expires_raw = st.session_state.get("code_expires_at")
        expired = False
        if expires_raw:
            try:
                expires_at = datetime.fromisoformat(expires_raw)
                remaining = int((expires_at - datetime.now()).total_seconds() // 60)
                if remaining >= 0:
                    st.info(f"Ce code est encore valable environ {remaining + 1} minute(s).")
                else:
                    expired = True
            except Exception:
                pass
        if expired:
            st.error("Le code a expiré. Merci de demander un nouveau code.")
            if st.button("Demander un nouveau code"):
                st.session_state.code_sent = False
                st.session_state.access_code = ""
                st.session_state.code_expires_at = None
                st.rerun()
            return False

        code_in = st.text_input("Saisissez le code d'accès reçu par email *", max_chars=6, type="password")
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("Valider le code et démarrer", type="primary"):
                if code_in.strip().upper() == st.session_state.get("access_code", ""):
                    st.session_state.code_verified = True
                    st.session_state.data["beneficiaire"] = b
                    st.session_state.data.setdefault("access", {})["code_verified"] = True
                    st.session_state.data.setdefault("access", {})["verified_at"] = now_iso()
                    ensure_runtime_tracking(True)
                    st.rerun()
                else:
                    st.error("Code incorrect.")
        with c2:
            if st.button("Modifier l'adresse email"):
                st.session_state.code_sent = False
                st.session_state.access_code = ""
                st.session_state.code_expires_at = None
                st.session_state.pending_beneficiaire = None
                st.rerun()
    return False

def old_sidebar_tools_unused():
    st.sidebar.markdown("## Clarté360")
    st.sidebar.write(APP_VERSION)
    st.sidebar.download_button("Télécharger le JSON", data=json_bytes(), file_name=safe_filename("roue_domaines_vie", "json"), mime="application/json")
    uploaded = st.sidebar.file_uploader("Importer un JSON", type=["json"])
    if uploaded is not None:
        try:
            loaded = json.loads(uploaded.read().decode("utf-8"))
            st.session_state.data = loaded
            st.session_state.code_verified = True
            st.sidebar.success("JSON importé.")
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Import impossible : {exc}")
    if st.sidebar.button("Réinitialiser l'exercice"):
        st.session_state.clear()
        st.rerun()


def progress_bar():
    phase = st.session_state.data.get("phase", 1)
    labels = ["1. Roue actuelle", "2. Débriefing", "3. Roue idéale", "4. Comparaison / actions"]
    cols = st.columns(4)
    for i, lab in enumerate(labels, start=1):
        with cols[i-1]:
            if phase == i:
                st.markdown(f"<div class='brand-box'><strong>{lab}</strong></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='info-box'>{lab}</div>", unsafe_allow_html=True)


def domain_selector(section_key, title, include_existing=True):
    data = st.session_state.data
    sec = data[section_key]
    st.markdown(f"### {title}")
    
    selected = st.multiselect("Domaines à faire apparaître dans la roue", options=DEFAULT_ORDER, default=sec.get("domaines_presents", []) if include_existing else [], key=f"{section_key}_domains")
    sec["domaines_presents"] = selected
    if selected:
        with st.expander("Définition des domaines", expanded=True):
            for d in selected:
                st.markdown(f"**{d}** — {DOMAINES[d]}")
        st.markdown("#### Répartition")
        st.markdown("La valeur ne mesure pas uniquement le temps passé. Elle doit tenir compte de la place globale du domaine : temps concret, charge mentale, préoccupations, énergie mobilisée, contraintes ressenties, attention disponible. La roue sera recalculée en pourcentage pour remplir 100 % du cercle.")
        cols = st.columns(2)
        for idx, d in enumerate(selected):
            with cols[idx % 2]:
                current = float(sec.get("valeurs", {}).get(d, 10))
                val = st.slider(d, 0, 100, int(current), 1, key=f"{section_key}_val_{d}")
                sec.setdefault("valeurs", {})[d] = val
        values, total = norm_values(sec.get("valeurs", {}), selected)
        if total <= 0:
            st.warning("La somme des valeurs est à zéro. Donnez une valeur à au moins un domaine présent.")
        else:
            st.markdown("#### Aperçu de la roue")
            display_pie(values, title)
            st.dataframe(pd.DataFrame([{"Domaine": k, "Part recalculée": f"{v:g}%", "Valeur saisie": sec['valeurs'].get(k, 0)} for k, v in values.items()]), use_container_width=True, hide_index=True)
    else:
        st.warning("Sélectionnez au moins un domaine présent pour construire la roue.")
    return selected


def phase_1():
    st.markdown("## Phase 1 — Construire la roue des domaines de vie aujourd'hui")
    st.markdown("<div class='brand-box'>Dans cette première phase, représentez votre vie telle qu'elle est aujourd'hui. Ne cherchez pas à obtenir une roue équilibrée ou agréable : l'intérêt est de montrer ce qui prend réellement de la place dans votre vie actuelle.</div>", unsafe_allow_html=True)

    st.markdown("### Questions d'aide à la réflexion")
    st.markdown("""
- Quels domaines occupent beaucoup de temps concret dans votre semaine ?
- Quels domaines occupent peu de temps mais beaucoup de charge mentale ?
- Quels domaines reviennent souvent dans vos pensées, vos obligations ou vos préoccupations ?
- Y a-t-il un domaine absent aujourd'hui ? Dans ce cas, ne le forcez pas dans la roue actuelle.
""")
    st.info("Déplacez progressivement les réglettes et observez la roue se dessiner. Les pourcentages sont calculés automatiquement : ne cherchez pas à faire un calcul, fiez-vous à votre ressenti global.")

    selected = domain_selector("actuel", "Roue actuelle")
    if selected and st.button("Valider ma roue actuelle", type="primary"):
        vals, total = norm_values(st.session_state.data["actuel"].get("valeurs", {}), selected)
        if total <= 0:
            st.error("Merci de donner une valeur à au moins un domaine.")
        else:
            st.session_state.data["phase"] = 2
            st.rerun()


def phase_2():
    data = st.session_state.data
    st.markdown("## Phase 2 — Débriefing de la roue actuelle")
    st.markdown("<div class='brand-box'>Prenez le temps d'observer la roue avec votre accompagnateur. L'objectif est d'écouter ce que ce schéma évoque : étonnement, confirmation, tensions, absences, envies de changement, points à approfondir.</div>", unsafe_allow_html=True)
    selected = data["actuel"].get("domaines_presents", [])
    values, _ = norm_values(data["actuel"].get("valeurs", {}), selected)
    display_pie(values, "Roue actuelle - aujourd'hui")
    st.markdown("### Notes par domaine")
    for d in selected:
        data["actuel"].setdefault("notes", {})[d] = st.text_area(f"Ce que je retiens pour : {d}", value=data["actuel"].get("notes", {}).get(d, ""), key=f"note_actuel_{d}")
    data["actuel"]["note_generale"] = st.text_area("Note générale sur la roue actuelle", value=data["actuel"].get("note_generale", ""))
    st.markdown("<div class='warn-box'>Lorsque le débriefing est terminé, la roue actuelle sera masquée pour permettre de construire la roue idéale sans être influencé par le premier schéma.</div>", unsafe_allow_html=True)
    confirm = st.checkbox("Je confirme que le débriefing de la roue actuelle est terminé.")
    if confirm and st.button("Passer à la roue idéale sans contrainte", type="primary"):
        data["debrief_actuel_termine"] = True
        data["phase"] = 3
        st.rerun()


def phase_3():
    st.markdown("## Phase 3 — Imaginer la roue idéale sans contrainte")
    st.markdown("<div class='brand-box'>Pour cette étape, mettez de côté la première roue. Imaginez une vie idéale et sans contrainte. Tout vous est possible. Ne repartez pas de ce que vous avez aujourd'hui : repartez de ce que vous aimeriez vivre si les contraintes matérielles, professionnelles, familiales, sociales ou intérieures étaient levées.</div>", unsafe_allow_html=True)
    st.markdown("### Consignes")
    st.markdown("""
- Vous pouvez faire apparaître un domaine absent aujourd'hui si vous souhaitez qu'il ait une place dans votre vie idéale.
- Vous pouvez retirer un domaine qui existe aujourd'hui si, dans cette projection, vous ne souhaitez pas lui donner de place.
- La roue idéale n'est pas un engagement immédiat : c'est une projection pour ouvrir la réflexion.
- Pensez en termes de présence souhaitée, de qualité de vie, d'énergie disponible et de charge mentale apaisée.
""")
    selected = domain_selector("ideal", "Roue idéale sans contrainte")
    st.session_state.data["ideal"]["projection_libre"] = st.text_area("Ce que j'aimerais dans cette vie idéale", value=st.session_state.data["ideal"].get("projection_libre", ""))
    if selected and st.button("Valider ma roue idéale", type="primary"):
        vals, total = norm_values(st.session_state.data["ideal"].get("valeurs", {}), selected)
        if total <= 0:
            st.error("Merci de donner une valeur à au moins un domaine.")
        else:
            st.session_state.data["ideal_valide"] = True
            st.session_state.data["phase"] = 4
            st.rerun()


def action_editor(all_domains):
    data = st.session_state.data
    actions = data["comparaison"].setdefault("actions", [])
    st.markdown("### Actions imaginables")
    st.markdown("L'objectif n'est pas de tout transformer immédiatement. Notez des actions possibles, même petites, qui pourraient faire évoluer progressivement la roue actuelle vers la roue souhaitée.")
    if st.button("Ajouter une action"):
        actions.append({"domaine": all_domains[0] if all_domains else "", "action": "", "premier_pas": "", "echeance": ""})
        st.rerun()
    to_delete = None
    for i, act in enumerate(actions):
        with st.expander(f"Action {i+1} - {act.get('domaine','') or 'à compléter'}", expanded=True):
            c1, c2 = st.columns([1, 2])
            with c1:
                act["domaine"] = st.selectbox("Domaine", options=all_domains or DEFAULT_ORDER, index=(all_domains or DEFAULT_ORDER).index(act.get("domaine")) if act.get("domaine") in (all_domains or DEFAULT_ORDER) else 0, key=f"act_dom_{i}")
                act["echeance"] = st.text_input("Échéance / moment possible", value=act.get("echeance", ""), key=f"act_ech_{i}")
            with c2:
                act["action"] = st.text_area("Action imaginable", value=act.get("action", ""), key=f"act_action_{i}")
                act["premier_pas"] = st.text_area("Premier petit pas concret", value=act.get("premier_pas", ""), key=f"act_pas_{i}")
            if st.button("Supprimer cette action", key=f"del_action_{i}"):
                to_delete = i
    if to_delete is not None:
        actions.pop(to_delete)
        st.rerun()


def phase_4():
    data = st.session_state.data
    st.markdown("## Phase 4 — Comparer les deux roues et ouvrir les pistes d'action")
    st.markdown("<div class='brand-box'>Les deux roues reviennent maintenant ensemble. Le débriefing porte sur les écarts, les absences, les domaines qui prennent trop ou pas assez de place, et les mouvements réalistes ou désirables pour aller vers une vie plus alignée.</div>", unsafe_allow_html=True)
    actuel_vals, _ = norm_values(data["actuel"].get("valeurs", {}), data["actuel"].get("domaines_presents", []))
    ideal_vals, _ = norm_values(data["ideal"].get("valeurs", {}), data["ideal"].get("domaines_presents", []))
    c1, c2 = st.columns(2)
    with c1:
        display_pie(actuel_vals, "Aujourd'hui")
    with c2:
        display_pie(ideal_vals, "Idéal sans contrainte")
    all_domains = list(dict.fromkeys(list(actuel_vals.keys()) + list(ideal_vals.keys())))
    rows = []
    for d in all_domains:
        a = actuel_vals.get(d, 0)
        i = ideal_vals.get(d, 0)
        rows.append({"Domaine": d, "Aujourd'hui": f"{a:g}%", "Idéal": f"{i:g}%", "Écart": f"{i-a:+g} pts"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown("### Débriefing final")
    data["comparaison"]["constats"] = st.text_area("Ce que la comparaison me fait comprendre", value=data["comparaison"].get("constats", ""), height=140)
    data["comparaison"]["questions"] = st.text_area("Questions à approfondir avec l'accompagnateur", value=data["comparaison"].get("questions", ""), height=100)
    action_editor(all_domains)
    st.markdown("### Exports")
    st.download_button("Télécharger le rapport PDF", data=build_pdf(), file_name=safe_filename("rapport_roue_domaines_vie", "pdf"), mime="application/pdf", type="primary")
    final_json = json_bytes()
    json_name = safe_filename("roue_domaines_vie", "json")
    st.download_button("Télécharger les données JSON", data=final_json, file_name=json_name, mime="application/json")
    if st.button("Transmettre le JSON au consultant Clarté360", type="primary"):
        ok, msg = send_final_json_to_consultant(data, final_json, json_name)
        if ok:
            st.session_state.final_json_sent = True
            st.success("JSON transmis au consultant Clarté360.")
        else:
            st.error(msg)


def main():
    init_state()
    sidebar_tools()
    timeout_watchdog()
    if st.session_state.get("show_rgpd_page"):
        rgpd_page()
        return
    if st.session_state.get("show_contact_page"):
        contact_page()
        return
    if st.session_state.get("code_verified"):
        ensure_runtime_tracking(user_activity=False)
        if is_timed_out():
            timeout_screen()
            return
        ensure_runtime_tracking(user_activity=True)
        install_beforeunload_warning()
    if not access_gate():
        return
    progress_bar()
    phase = st.session_state.data.get("phase", 1)
    if phase == 1:
        phase_1()
    elif phase == 2:
        phase_2()
    elif phase == 3:
        phase_3()
    else:
        phase_4()

if __name__ == "__main__":
    main()
