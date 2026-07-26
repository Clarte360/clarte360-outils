import json
import random
import re
import smtplib
import uuid
from copy import deepcopy
from datetime import date, datetime
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_VERSION = "1.0.0-socle-clarte360"
SOCLE_CLARTE360_VERSION = "4.0"
APP_NAME = "Tableau des limites"
APP_FULL_NAME = "Clarté360 – Tableau des limites"
TOOL_CODE = "clarte360_tableau_limites"
RGPD_TEXT_VERSION = "RGPD-Clarte360-v1.0-2026-07"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "site_icon.png"
FINAL_EMAIL_TO = "contact@clarte360.com"
DEFAULT_SESSION_LIMIT_MINUTES = 15

CLARTE360_LEGAL = {
    "raison_sociale": "Clarté360", "forme": "SAS", "adresse": "60 rue François 1er",
    "code_postal_ville": "75008 Paris", "telephone": "01 89 48 08 25",
    "email": "contact@clarte360.com", "web": "www.clarte360.com",
    "rcs": "102349834", "siret": "10234983400014", "naf": "8559 A", "tva": "FR88102349834",
}

st.set_page_config(page_title=APP_FULL_NAME, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🟢", layout="centered")
st.markdown(f"""
<style>
:root {{ --clarte-teal:{OFFICIAL_TEAL}; }}
h1,h2,h3 {{color:{OFFICIAL_TEAL};}}
.stProgress > div > div > div > div {{background-color:{OFFICIAL_TEAL};}}
div.stButton > button[kind="primary"] {{background-color:{OFFICIAL_TEAL};border-color:{OFFICIAL_TEAL};}}
.clarte-box {{border-left:6px solid {OFFICIAL_TEAL};background:{LIGHT_TEAL};padding:1rem 1.1rem;border-radius:.55rem;margin:1rem 0;color:{DARK_TEXT};}}
.clarte-card {{border:1px solid #d9eeee;border-radius:.8rem;padding:1rem;background:#fff;box-shadow:0 1px 8px rgba(0,128,128,.08);margin-bottom:1rem;}}
.small-muted {{color:#666;font-size:.9rem;}}
.limit-title {{font-weight:750;font-size:1.1rem;color:{DARK_TEXT};}}
</style>
""", unsafe_allow_html=True)

RGPD_TEXT = f"""
### Protection des données personnelles (RGPD)

Cette application Clarté360 fonctionne sans base de données serveur propre à l'application. Aucune donnée n'est enregistrée durablement sur un serveur Clarté360 par l'application.

Le fichier JSON constitue le support de conservation et de reprise du travail. Il peut contenir l'identité du bénéficiaire, son adresse e-mail, le nom de son accompagnateur, les limites saisies, leurs causes, conséquences, actions, dates de réalisation, commentaires, statuts, dates de création et de modification, l'historique des connexions et des sessions, le consentement RGPD, ainsi que les informations techniques nécessaires à la traçabilité.

Le fichier JSON appartient exclusivement au bénéficiaire. Il choisit librement de le conserver, de le supprimer ou de le transmettre à son accompagnateur.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : **{RGPD_TEXT_VERSION}**.

### Nature de l'outil

Le Tableau des limites est un support de réflexion et de passage à l'action. Il ne constitue ni un diagnostic psychologique, ni un avis médical, ni une décision automatique. Le travail sur les causes et les actions s'inscrit dans le cadre des entretiens avec le professionnel de l'accompagnement.

### Propriété intellectuelle

L'application, la structure de travail, les documents et contenus proposés par Clarté360 sont protégés. Toute reproduction ou diffusion sans autorisation écrite préalable est interdite.
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^a-z0-9àâäéèêëîïôöùûüçñ\- ]+", "", value.strip().lower(), flags=re.IGNORECASE)
    return re.sub(r"\s+", "_", value) or "beneficiaire"


def generate_code() -> str:
    return f"{random.randint(100000, 999999)}"


def smtp_configured() -> bool:
    try:
        e = st.secrets.get("email", {})
        return all(e.get(k) for k in ["smtp_server", "smtp_port", "smtp_user", "smtp_password", "from_email", "to_email"])
    except Exception:
        return False


def send_email(subject: str, body: str, to_email: str | None = None, attachments=None):
    if not smtp_configured():
        return False, "SMTP non configuré dans les Secrets Streamlit."
    try:
        e = st.secrets["email"]
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = subject, e["from_email"], to_email or e["to_email"]
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
    now = datetime.now()
    st.session_state.runtime_session = {
        "session_id": str(uuid.uuid4()), "debut": now.isoformat(timespec="seconds"),
        "derniere_activite": now.isoformat(timespec="seconds"), "fin": None,
        "duree_secondes": 0, "motif_ouverture": reason, "motif_fermeture": None,
        "evenements": [{"date_heure": now.isoformat(timespec="seconds"), "type": reason}],
    }


def update_activity(event="activite"):
    s = st.session_state.get("runtime_session")
    if not s or s.get("fin"):
        return
    s["derniere_activite"] = now_iso()
    s.setdefault("evenements", []).append({"date_heure": now_iso(), "type": event})


def close_runtime_session(reason: str):
    s = st.session_state.get("runtime_session")
    if not s or s.get("fin"):
        return
    end = datetime.now()
    start = datetime.fromisoformat(s["debut"])
    s["fin"] = end.isoformat(timespec="seconds")
    s["duree_secondes"] = max(0, int((end - start).total_seconds()))
    s["motif_fermeture"] = reason
    st.session_state.setdefault("session_history", []).append(deepcopy(s))


def total_session_seconds() -> int:
    total = sum(int(s.get("duree_secondes", 0)) for s in st.session_state.get("session_history", []))
    current = st.session_state.get("runtime_session")
    if current and not current.get("fin"):
        total += max(0, int((datetime.now() - datetime.fromisoformat(current["debut"])).total_seconds()))
    return total


def format_duration(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min {s:02d} s"


def check_session_limit():
    if not st.session_state.get("work_started") or st.session_state.get("session_expired"):
        return
    current = st.session_state.get("runtime_session")
    if not current:
        return
    last = datetime.fromisoformat(current.get("derniere_activite", current["debut"]))
    if (datetime.now() - last).total_seconds() >= get_session_limit_minutes() * 60:
        close_runtime_session("timeout_inactivite")
        st.session_state.session_expired = True
        st.rerun()


def timeout_watchdog():
    if st_autorefresh is not None:
        st_autorefresh(interval=10_000, key="clarte360_timeout_watchdog")
    else:
        components.html("<script>setTimeout(function(){window.parent.location.reload();},10000);</script>", height=0)


def reset_all():
    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)
    st.rerun()


def start_new_session(nom, prenom, email, consultant):
    st.session_state.passation_root_id = str(uuid.uuid4())
    st.session_state.passation_id = f"CL360-LIM-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{st.session_state.passation_root_id[:8].upper()}"
    st.session_state.beneficiaire = {"nom": nom.strip(), "prenom": prenom.strip(), "email": email.strip(), "consultant": consultant.strip()}
    st.session_state.limits = []
    st.session_state.work_started = True
    st.session_state.started_at = now_iso()
    st.session_state.session_history = []
    st.session_state.final_email_sent = False
    st.session_state.edit_limit_id = None
    init_runtime_session("premiere_connexion")


def restore_from_progress(payload: dict):
    st.session_state.passation_root_id = payload.get("passation_root_id", str(uuid.uuid4()))
    st.session_state.passation_id = payload.get("passation_id", f"CL360-LIM-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    st.session_state.beneficiaire = payload.get("beneficiaire", {})
    st.session_state.limits = payload.get("limites", [])
    st.session_state.work_started = True
    st.session_state.started_at = payload.get("started_at", now_iso())
    st.session_state.session_history = payload.get("sessions", []) if isinstance(payload.get("sessions", []), list) else []
    st.session_state.rgpd_acceptance = payload.get("rgpd_acceptance", {})
    st.session_state.access_history = payload.get("access_history", {})
    st.session_state.code_verified = True
    st.session_state.code_verified_at = now_iso()
    st.session_state.final_email_sent = bool(payload.get("final_email_sent", False))
    st.session_state.edit_limit_id = None
    init_runtime_session("reprise_depuis_json")


def build_payload(completed=False) -> dict:
    update_activity("construction_json")
    return {
        "outil": TOOL_CODE, "outil_nom": APP_FULL_NAME,
        "app_version": APP_VERSION, "socle_clarte360_version": SOCLE_CLARTE360_VERSION,
        "passation_root_id": st.session_state.get("passation_root_id", ""),
        "passation_id": st.session_state.get("passation_id", ""),
        "beneficiaire": st.session_state.get("beneficiaire", {}),
        "started_at": st.session_state.get("started_at", ""),
        "completed_at": now_iso() if completed else None,
        "code_verified_at": st.session_state.get("code_verified_at", ""),
        "limites": st.session_state.get("limits", []),
        "nombre_limites": len(st.session_state.get("limits", [])),
        "sessions": st.session_state.get("session_history", []),
        "temps_total_cumule_secondes": total_session_seconds(),
        "temps_total_cumule_minutes": round(total_session_seconds() / 60, 2),
        "temps_total_cumule_lisible": format_duration(total_session_seconds()),
        "rgpd_acceptance": st.session_state.get("rgpd_acceptance", {}),
        "access_history": st.session_state.get("access_history", {}),
        "final_email_sent": st.session_state.get("final_email_sent", False),
        "notice": "Support de réflexion et de passage à l'action, à exploiter dans le cadre de l'accompagnement.",
    }


def payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def make_filename(prefix="tableau_limites", ext="json"):
    b = st.session_state.get("beneficiaire", {})
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"clarte360_{prefix}_{sanitize_filename(b.get('prenom',''))}_{sanitize_filename(b.get('nom',''))}_{stamp}.{ext}"


def legal_footer_text() -> str:
    return f"{CLARTE360_LEGAL['raison_sociale']} – {CLARTE360_LEGAL['adresse']} – {CLARTE360_LEGAL['code_postal_ville']} – {CLARTE360_LEGAL['telephone']} – {CLARTE360_LEGAL['email']}"


def draw_pdf_footer(canvas, doc):
    canvas.saveState()
    width, _ = doc.pagesize
    canvas.setStrokeColor(colors.HexColor("#CCCCCC")); canvas.setLineWidth(0.3)
    canvas.line(1.5*cm, 1.05*cm, width-1.5*cm, 1.05*cm)
    canvas.setFillColor(colors.HexColor("#666666")); canvas.setFont("Helvetica", 6.5)
    canvas.drawCentredString(width/2, 0.68*cm, legal_footer_text())
    canvas.drawCentredString(width/2, 0.42*cm, f"SIRET {CLARTE360_LEGAL['siret']} • RCS {CLARTE360_LEGAL['rcs']} • TVA {CLARTE360_LEGAL['tva']}")
    canvas.restoreState()


def create_pdf(payload: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.4*cm, bottomMargin=1.35*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ClarteTitle", parent=styles["Title"], textColor=colors.HexColor(OFFICIAL_TEAL), alignment=TA_CENTER, fontSize=19, leading=23))
    styles.add(ParagraphStyle(name="ClarteH2", parent=styles["Heading2"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=13, leading=16, spaceBefore=8, spaceAfter=6))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8.5, leading=11))
    story = []
    if LOGO_PATH.exists():
        img = Image(str(LOGO_PATH), width=1.7*cm, height=1.7*cm); img.hAlign = "CENTER"; story += [img, Spacer(1, .15*cm)]
    story += [Paragraph(APP_FULL_NAME, styles["ClarteTitle"]), Spacer(1, .3*cm)]
    b = payload.get("beneficiaire", {})
    story += [Paragraph(f"<b>Bénéficiaire :</b> {b.get('prenom','')} {b.get('nom','')}<br/><b>Accompagnateur :</b> {b.get('consultant','') or 'Non renseigné'}<br/><b>Date d'édition :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}<br/><b>Référence :</b> {payload.get('passation_id','')}", styles["BodyText"]), Spacer(1, .35*cm)]
    limits = payload.get("limites", [])
    story += [Paragraph(f"Tableau de synthèse – {len(limits)} limite(s)", styles["ClarteH2"])]
    if limits:
        data = [[Paragraph("N°", styles["Small"]), Paragraph("Limite", styles["Small"]), Paragraph("Cause", styles["Small"]), Paragraph("Conséquences", styles["Small"]), Paragraph("Actions", styles["Small"]), Paragraph("Échéance", styles["Small"])]]
        for i, item in enumerate(limits, 1):
            data.append([str(i), Paragraph(item.get("limite", ""), styles["Small"]), Paragraph(item.get("cause", ""), styles["Small"]), Paragraph(item.get("consequences", ""), styles["Small"]), Paragraph(item.get("actions", ""), styles["Small"]), Paragraph(item.get("date_realisation", ""), styles["Small"])])
        table = Table(data, colWidths=[.6*cm, 3.1*cm, 3.1*cm, 3.5*cm, 3.8*cm, 2.2*cm], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(OFFICIAL_TEAL)), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#B7CCCC")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F5FAFA")]), ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
        story.append(table)
        story.append(PageBreak())
        story.append(Paragraph("Détail des limites", styles["ClarteH2"]))
        for i, item in enumerate(limits, 1):
            story += [Paragraph(f"{i}. {item.get('limite','')}", styles["ClarteH2"]), Paragraph(f"<b>Cause :</b> {item.get('cause','') or 'Non renseignée'}", styles["BodyText"]), Paragraph(f"<b>Conséquences :</b> {item.get('consequences','') or 'Non renseignées'}", styles["BodyText"]), Paragraph(f"<b>Actions décidées :</b> {item.get('actions','') or 'Non renseignées'}", styles["BodyText"]), Paragraph(f"<b>Date de réalisation :</b> {item.get('date_realisation','') or 'Non renseignée'}", styles["BodyText"]), Paragraph(f"<b>Statut :</b> {item.get('statut','À traiter')}", styles["BodyText"])]
            if item.get("commentaire"):
                story.append(Paragraph(f"<b>Commentaire :</b> {item.get('commentaire')}", styles["BodyText"]))
            story.append(Spacer(1, .25*cm))
    else:
        story.append(Paragraph("Aucune limite n'a été enregistrée.", styles["BodyText"]))
    story += [Spacer(1, .3*cm), Paragraph("Ce document reprend les éléments saisis par le bénéficiaire dans le cadre de son accompagnement. Il ne constitue pas un diagnostic.", styles["Small"])]
    doc.build(story, onFirstPage=draw_pdf_footer, onLaterPages=draw_pdf_footer)
    return buffer.getvalue()


def display_header():
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=82)
    st.title(APP_FULL_NAME)


def traceability_information_block():
    st.markdown("### Traçabilité")
    st.info("Le consentement, les générations de code, les accès, les sessions, les sauvegardes et les modifications des limites sont conservés dans le JSON du bénéficiaire.")


def rgpd_page():
    display_header(); st.markdown(RGPD_TEXT); traceability_information_block()


def contact_form():
    with st.form("contact_form"):
        nom = st.text_input("Nom et prénom")
        email = st.text_input("Adresse e-mail")
        message = st.text_area("Votre message", height=150)
        sent = st.form_submit_button("Envoyer", type="primary", use_container_width=True)
    if sent:
        if not nom or not email or not message:
            st.error("Merci de renseigner tous les champs.")
        else:
            ok, msg = send_email(f"Contact – {APP_NAME}", f"Nom : {nom}\nEmail : {email}\n\n{message}")
            st.success("Votre message a été envoyé.") if ok else st.error(msg)


def contact_page():
    display_header(); st.markdown("### Contact Clarté360"); contact_form()


def welcome_screen():
    display_header()
    st.markdown("<div class='clarte-box'><b>Objectif :</b> transformer les limites identifiées pendant les entretiens en décisions et actions concrètes.</div>", unsafe_allow_html=True)
    st.markdown("L'application permet de traiter <b>plusieurs limites</b> pour un même bénéficiaire et d'en conserver l'intégralité dans un fichier JSON réutilisable pour les rapports Clarté360.", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Commencer un nouveau tableau", type="primary", use_container_width=True):
            st.session_state.welcome_choice = "new"; st.rerun()
    with c2:
        if st.button("Reprendre depuis un JSON", use_container_width=True):
            st.session_state.welcome_choice = "import"; st.rerun()


def import_json_screen():
    display_header(); st.subheader("Reprendre un tableau existant")
    uploaded = st.file_uploader("Sélectionnez le JSON Clarté360", type=["json"])
    if uploaded:
        try:
            payload = json.loads(uploaded.getvalue().decode("utf-8"))
            if payload.get("outil") != TOOL_CODE:
                st.error("Ce fichier ne provient pas de l'application Tableau des limites.")
            elif st.button("Reprendre ce tableau", type="primary", use_container_width=True):
                restore_from_progress(payload); st.rerun()
        except Exception as exc:
            st.error(f"Fichier JSON illisible : {exc}")
    if st.button("Retour"):
        st.session_state.welcome_choice = None; st.rerun()


def issue_access_code(email: str, pending: dict, regeneration=False):
    code = generate_code()
    st.session_state.access_code = code
    st.session_state.access_code_created_at = now_iso()
    history = st.session_state.get("access_history", {"generations": [], "validations": []})
    history["generations"].append({"date_heure": now_iso(), "type": "regeneration" if regeneration else "initiale", "email": email})
    st.session_state.access_history = history
    ok_user, msg_user = send_email(f"Votre code d'accès – {APP_NAME}", f"Bonjour {pending.get('prenom','')},\n\nVotre code d'accès Clarté360 est : {code}\n\nCe code permet de poursuivre votre tableau des limites.", to_email=email)
    send_email(f"Traçabilité accès – {APP_NAME}", f"Bénéficiaire : {pending.get('prenom','')} {pending.get('nom','')}\nEmail : {email}\nAccompagnateur : {pending.get('consultant','')}\nType : {'régénération' if regeneration else 'initiale'}\nDate : {now_iso()}\nConsentement RGPD : accepté.")
    if ok_user:
        st.success("Un code d'accès vient de vous être envoyé par e-mail.")
    else:
        st.error("Impossible d'envoyer le code : " + msg_user)


def identification_screen():
    display_header(); st.subheader("Identification du bénéficiaire")
    if not st.session_state.get("pending_identity"):
        with st.form("identity_form"):
            nom = st.text_input("Nom *")
            prenom = st.text_input("Prénom *")
            email = st.text_input("Adresse e-mail *")
            consultant = st.text_input("Consultant / accompagnateur")
            consent = st.checkbox("J'ai lu les informations RGPD et je consens à l'utilisation de mes données dans le cadre de cet accompagnement.")
            c1, c2 = st.columns(2)
            with c1: show_rgpd = st.form_submit_button("Lire le RGPD")
            with c2: submit = st.form_submit_button("Recevoir mon code", type="primary")
        if show_rgpd:
            st.session_state.show_rgpd_page = True; st.rerun()
        if submit:
            if not nom.strip() or not prenom.strip() or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
                st.error("Merci de renseigner un nom, un prénom et une adresse e-mail valide.")
            elif not consent:
                st.error("Le consentement RGPD est obligatoire.")
            else:
                pending = {"nom": nom, "prenom": prenom, "email": email, "consultant": consultant}
                st.session_state.pending_identity = pending
                st.session_state.rgpd_acceptance = {"accepted": True, "date_heure": now_iso(), "version": RGPD_TEXT_VERSION}
                issue_access_code(email.strip(), pending)
                st.rerun()
    else:
        p = st.session_state.pending_identity
        st.info(f"Code envoyé à {p.get('email','')}.")
        code_entered = st.text_input("Code à 6 chiffres", max_chars=6)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Valider le code", type="primary", use_container_width=True):
                if code_entered.strip() == st.session_state.get("access_code"):
                    st.session_state.code_verified = True; st.session_state.code_verified_at = now_iso()
                    h = st.session_state.get("access_history", {"generations": [], "validations": []})
                    h["validations"].append({"date_heure": now_iso(), "resultat": "valide"}); st.session_state.access_history = h
                    start_new_session(p["nom"], p["prenom"], p["email"], p.get("consultant", "")); st.rerun()
                else:
                    st.error("Code incorrect.")
        with c2:
            if st.button("Renvoyer un code", use_container_width=True):
                issue_access_code(p["email"], p, regeneration=True); st.rerun()
        if st.button("Modifier mes informations"):
            st.session_state.pending_identity = None; st.rerun()


def add_or_edit_limit_form():
    limits = st.session_state.get("limits", [])
    edit_id = st.session_state.get("edit_limit_id")
    existing = next((x for x in limits if x.get("id") == edit_id), None) if edit_id else None
    st.subheader("Modifier la limite" if existing else "Ajouter une limite")
    with st.form("limit_form", clear_on_submit=not bool(existing)):
        limite = st.text_area("La limite *", value=existing.get("limite", "") if existing else "", placeholder="Exemple : Je n'arrive pas à dire non.")
        cause = st.text_area("La cause *", value=existing.get("cause", "") if existing else "", placeholder="Exemple : J'ai peur de blesser ou de décevoir.")
        consequences = st.text_area("Les conséquences *", value=existing.get("consequences", "") if existing else "", placeholder="Exemple : J'accepte trop de demandes et je m'épuise.")
        actions = st.text_area("Les actions décidées *", value=existing.get("actions", "") if existing else "", placeholder="Exemple : Refuser une demande non prioritaire cette semaine.")
        current_date = existing.get("date_realisation") if existing else ""
        d = st.date_input("Date de réalisation", value=datetime.strptime(current_date, "%Y-%m-%d").date() if current_date else None, format="DD/MM/YYYY")
        statut_options = ["À traiter", "Action planifiée", "En cours", "Réalisée", "À réévaluer"]
        current_status = existing.get("statut", "À traiter") if existing else "À traiter"
        statut = st.selectbox("Statut", statut_options, index=statut_options.index(current_status) if current_status in statut_options else 0)
        commentaire = st.text_area("Commentaire complémentaire", value=existing.get("commentaire", "") if existing else "")
        submitted = st.form_submit_button("Enregistrer la limite", type="primary", use_container_width=True)
    if submitted:
        if not all([limite.strip(), cause.strip(), consequences.strip(), actions.strip()]):
            st.error("Les cinq éléments fondamentaux doivent être renseignés : limite, cause, conséquences, actions et date.")
            return
        if d is None:
            st.error("Merci de choisir une date de réalisation.")
            return
        now = now_iso()
        item = {
            "id": existing.get("id") if existing else str(uuid.uuid4()),
            "ordre": existing.get("ordre") if existing else len(limits) + 1,
            "limite": limite.strip(), "cause": cause.strip(), "consequences": consequences.strip(),
            "actions": actions.strip(), "date_realisation": d.isoformat(), "statut": statut,
            "commentaire": commentaire.strip(), "created_at": existing.get("created_at", now) if existing else now,
            "updated_at": now,
        }
        if existing:
            st.session_state.limits = [item if x.get("id") == edit_id else x for x in limits]
            st.session_state.edit_limit_id = None
        else:
            st.session_state.limits.append(item)
        update_activity("modification_limite" if existing else "ajout_limite")
        st.success("Limite enregistrée."); st.rerun()
    if existing and st.button("Annuler la modification"):
        st.session_state.edit_limit_id = None; st.rerun()


def limits_table_screen():
    display_header()
    b = st.session_state.get("beneficiaire", {})
    st.caption(f"Bénéficiaire : {b.get('prenom','')} {b.get('nom','')} — {len(st.session_state.get('limits', []))} limite(s) enregistrée(s)")
    st.markdown("<div class='clarte-box'>Le tableau reprend uniquement les éléments opérationnels issus des entretiens : <b>limite, cause, conséquences, actions et date de réalisation</b>.</div>", unsafe_allow_html=True)
    add_or_edit_limit_form()
    limits = st.session_state.get("limits", [])
    if limits:
        st.markdown("### Limites enregistrées")
        for i, item in enumerate(limits, 1):
            with st.expander(f"{i}. {item.get('limite','')}", expanded=False):
                st.markdown(f"**Cause :** {item.get('cause','')}")
                st.markdown(f"**Conséquences :** {item.get('consequences','')}")
                st.markdown(f"**Actions :** {item.get('actions','')}")
                st.markdown(f"**Date de réalisation :** {item.get('date_realisation','')}  \n**Statut :** {item.get('statut','')}")
                if item.get("commentaire"): st.markdown(f"**Commentaire :** {item.get('commentaire')}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Modifier", key=f"edit_{item['id']}", use_container_width=True):
                        st.session_state.edit_limit_id = item["id"]; st.rerun()
                with c2:
                    if st.button("Supprimer", key=f"del_{item['id']}", use_container_width=True):
                        st.session_state.limits = [x for x in limits if x.get("id") != item["id"]]
                        for pos, x in enumerate(st.session_state.limits, 1): x["ordre"] = pos
                        update_activity("suppression_limite"); st.rerun()
    else:
        st.info("Aucune limite n'a encore été enregistrée.")


def prepare_sidebar_json(reason: str):
    close_runtime_session(reason)
    payload = build_payload(completed=False)
    st.session_state.prepared_json = payload_bytes(payload)
    st.session_state.prepared_json_name = make_filename("tableau_limites_reprise", "json")
    st.session_state.exit_json_ready = True


def sidebar():
    with st.sidebar:
        if LOGO_PATH.exists(): st.image(str(LOGO_PATH), width=70)
        st.markdown(f"### {APP_NAME}")
        if st.session_state.get("work_started"):
            b = st.session_state.get("beneficiaire", {})
            st.caption(f"{b.get('prenom','')} {b.get('nom','')}")
            st.metric("Limites enregistrées", len(st.session_state.get("limits", [])))
            st.caption(f"Temps cumulé : {format_duration(total_session_seconds())}")
            if st.button("Sauvegarder / quitter", type="primary", use_container_width=True):
                prepare_sidebar_json("sortie_volontaire"); st.rerun()
            if st.button("Finaliser et produire les rapports", use_container_width=True):
                close_runtime_session("travail_finalise"); st.session_state.show_results = True; st.rerun()
            st.divider()
        if st.button("RGPD", use_container_width=True): st.session_state.show_rgpd_page = True; st.rerun()
        if st.button("Contact", use_container_width=True): st.session_state.show_contact_page = True; st.rerun()
        if not st.session_state.get("work_started") and st.button("Réinitialiser la session", use_container_width=True): reset_all()


def exit_prepared_screen():
    display_header(); st.success("Votre JSON de reprise est prêt.")
    st.download_button("Télécharger mon JSON", data=st.session_state.get("prepared_json", b""), file_name=st.session_state.get("prepared_json_name", "clarte360_tableau_limites.json"), mime="application/json", type="primary", use_container_width=True)
    st.info("Après téléchargement, vous pouvez fermer l'onglet. Ce fichier permet de reprendre toutes les limites et l'historique des sessions.")


def expired_screen():
    display_header(); st.warning(f"La session a été arrêtée après {get_session_limit_minutes()} minutes sans activité.")
    payload = build_payload(completed=False)
    st.download_button("Télécharger mon JSON de reprise", data=payload_bytes(payload), file_name=make_filename("tableau_limites_timeout", "json"), mime="application/json", type="primary", use_container_width=True)


def results_screen():
    display_header(); st.success("Tableau finalisé.")
    payload = build_payload(completed=True)
    json_data = payload_bytes(payload); pdf_data = create_pdf(payload)
    json_name = make_filename("tableau_limites_final", "json"); pdf_name = make_filename("rapport_tableau_limites", "pdf")
    st.markdown(f"### Synthèse : {len(payload.get('limites', []))} limite(s)")
    if payload.get("limites"):
        rows = [{"N°": i, "Limite": x.get("limite"), "Cause": x.get("cause"), "Actions": x.get("actions"), "Date": x.get("date_realisation"), "Statut": x.get("statut")} for i, x in enumerate(payload["limites"], 1)]
        st.dataframe(rows, hide_index=True, use_container_width=True)
    if not st.session_state.get("final_email_sent"):
        ok, msg = send_email(f"JSON final – {APP_NAME} – {payload.get('passation_id')}", f"Tableau finalisé pour {payload['beneficiaire'].get('prenom','')} {payload['beneficiaire'].get('nom','')}.\nNombre de limites : {payload.get('nombre_limites',0)}", attachments=[(json_name, json_data, "application/json")])
        if ok:
            st.session_state.final_email_sent = True; st.info("Le JSON final a été transmis à Clarté360.")
        else:
            st.warning("Le JSON final n'a pas pu être envoyé automatiquement : " + msg)
    c1, c2 = st.columns(2)
    with c1: st.download_button("Télécharger le JSON final", data=json_data, file_name=json_name, mime="application/json", use_container_width=True)
    with c2: st.download_button("Télécharger le rapport PDF", data=pdf_data, file_name=pdf_name, mime="application/pdf", use_container_width=True)
    if st.button("Revenir au tableau", use_container_width=True):
        st.session_state.show_results = False; init_runtime_session("reouverture_apres_finalisation"); st.rerun()


def install_beforeunload_warning():
    if st.session_state.get("work_started") and not st.session_state.get("exit_json_ready"):
        components.html("""<script>window.parent.onbeforeunload=function(e){const m='Avant de quitter, utilisez le bouton Sauvegarder / quitter.';e.preventDefault();e.returnValue=m;return m;};</script>""", height=0)


def main():
    sidebar(); install_beforeunload_warning()
    if st.session_state.get("show_contact_page"):
        contact_page()
        if st.button("Retour à l'application"): st.session_state.show_contact_page = False; st.rerun()
        return
    if st.session_state.get("show_rgpd_page"):
        rgpd_page()
        if st.button("Retour à l'application"): st.session_state.show_rgpd_page = False; st.rerun()
        return
    if st.session_state.get("session_expired"):
        expired_screen(); return
    if st.session_state.get("exit_json_ready"):
        exit_prepared_screen(); return
    if st.session_state.get("show_results"):
        results_screen(); return
    if st.session_state.get("work_started"):
        timeout_watchdog(); check_session_limit(); limits_table_screen(); return
    choice = st.session_state.get("welcome_choice")
    if choice == "new": identification_screen()
    elif choice == "import": import_json_screen()
    else: welcome_screen()


if __name__ == "__main__":
    main()
