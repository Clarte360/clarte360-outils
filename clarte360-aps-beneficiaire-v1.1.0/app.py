import json
import re
import secrets as pysecrets
import smtplib
import uuid
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

APP_VERSION = "1.1.2"
FRAMEWORK_VERSION = "4.0"
APP_NAME = "APS – Grille d'analyse partagee de situation"
APP_FULL_NAME = "Clarte360 – APS – Phase preliminaire"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "site_icon.png"
FINAL_RECIPIENT_DEFAULT = "contact@clarte360.com"
RGPD_TEXT_VERSION = "RGPD-Clarte360-APS-v1.0-2026-09"

CLARTE360_LEGAL = {
    "raison_sociale": "Clarte360",
    "forme": "SAS",
    "adresse": "60 rue Francois 1er",
    "code_postal_ville": "75008 Paris",
    "telephone": "01 89 48 08 25",
    "email": "contact@clarte360.com",
    "web": "www.clarte360.com",
    "siret": "10234983400014",
}

RGPD_PREACCESS_TEXT = f"""
### Protection des données personnelles (RGPD)

**Responsable du traitement :** Clarté360 SAS, 60 rue François 1er, 75008 Paris — contact@clarte360.com.

**Finalités :** les données recueillies servent exclusivement à sécuriser votre accès personnel, formaliser la grille d'analyse partagée de situation (APS) issue de votre entretien préalable, préparer la mise en place de votre bilan de compétences et, après votre validation finale, transmettre à Clarté360 le PDF de l'APS et le JSON structuré nécessaires au traitement de votre dossier.

**Données concernées :** identité et coordonnées, situation professionnelle, demande et attentes, objectifs, modalités envisagées, informations utiles à la future convention, consentements, traces d'accès et de validation.

**Conservation :** les données sont conservées uniquement pendant la durée nécessaire à la gestion de votre dossier et au respect des obligations légales et réglementaires applicables. La sauvegarde JSON téléchargée depuis l'application reste également sous votre responsabilité.

**Destinataires :** les informations sont destinées à Clarté360 et aux personnes habilitées intervenant dans la gestion ou l'accompagnement de votre bilan. Elles ne sont pas utilisées à des fins commerciales sans consentement explicite.

**Vos droits :** vous pouvez demander l'accès, la rectification, l'effacement ou la limitation du traitement de vos données, ainsi que l'exercice des autres droits prévus par le RGPD, en écrivant à **contact@clarte360.com**.

**Sécurité et traçabilité :** votre consentement est recueilli avant l'envoi du code d'accès. Son acceptation est tracée avec la date, l'heure, la version de l'application, la version du texte RGPD et un identifiant technique de session.

Version du texte RGPD : **{RGPD_TEXT_VERSION}**.
"""

SECTIONS = [
    "Accueil",
    "1. Votre identite",
    "2. Votre situation professionnelle",
    "3. Votre demande et vos attentes",
    "4. Vos objectifs",
    "5. Organisation et modalites",
    "6. Informations pour la future convention",
    "7. Informations et consentements",
    "8. Verification et validation",
]

TOOLS = [
    "Roue des valeurs",
    "Recherche de mes valeurs",
    "Preferences professionnelles",
    "Moteurs professionnels",
    "Ligne de vie",
    "Competences et Projets professionnels",
    "Roue des domaines de vie",
    "Boucle autovalidante / croyances",
    "Tableau des limites",
    "DIAGORIENTE (RIASEC / BRILLO / centres d'interet / metiers)",
]

st.set_page_config(
    page_title=APP_FULL_NAME,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🟢",
    layout="centered",
)

st.markdown(
    f"""
<style>
:root {{ --clarte-teal: {OFFICIAL_TEAL}; }}
h1, h2, h3 {{ color: {OFFICIAL_TEAL}; }}
.stProgress > div > div > div > div {{ background-color: {OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"] {{ background-color: {OFFICIAL_TEAL}; border-color: {OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"]:hover {{ background-color: #006f6f; border-color: #006f6f; }}
.clarte-box {{ border-left: 6px solid {OFFICIAL_TEAL}; background: {LIGHT_TEAL}; padding: 1rem 1.1rem; border-radius: .55rem; margin: 1rem 0; color: {DARK_TEXT}; }}
.clarte-warning {{ border-left: 6px solid #d9a300; background: #fff9df; padding: 1rem 1.1rem; border-radius: .55rem; margin: 1rem 0; color: #564400; }}
.small-muted {{ color:#666; font-size:.9rem; }}
</style>
""",
    unsafe_allow_html=True,
)


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean_text(value):
    return str(value or "").strip()


def valid_email(value):
    value = clean_text(value)
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", value)) if value else False


def secret(section, key, default=""):
    try:
        return st.secrets.get(section, {}).get(key, default)
    except Exception:
        return default


def get_email_config():
    """Lit la messagerie au format officiel Clarte360 : section [email]."""
    try:
        cfg = st.secrets.get("email", {})
        required = ["smtp_server", "smtp_port", "smtp_user", "smtp_password", "from_email", "to_email"]
        if all(k in cfg and clean_text(cfg[k]) for k in required):
            out = {k: clean_text(cfg[k]) for k in required}
            out["from_name"] = clean_text(cfg.get("from_name", "Clarte360")) or "Clarte360"
            return out
    except Exception:
        pass
    return None


def smtp_ready():
    return get_email_config() is not None


def send_email(to_addr, subject, body, attachments=None):
    cfg = get_email_config()
    if not cfg:
        return False, "Le service d'envoi d'e-mails n'est pas configure."
    msg = EmailMessage()
    from_name = cfg.get("from_name", "Clarte360")
    msg["From"] = f'{from_name} <{cfg["from_email"]}>' if from_name else cfg["from_email"]
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    for filename, data, maintype, subtype in attachments or []:
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    try:
        port = int(cfg["smtp_port"])
        server = cfg["smtp_server"]
        user = cfg["smtp_user"]
        password = cfg["smtp_password"]
        if port == 465:
            with smtplib.SMTP_SSL(server, port, timeout=20) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, port, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(user, password)
                smtp.send_message(msg)
        return True, ""
    except Exception:
        return False, "L'envoi de l'e-mail n'a pas pu aboutir. Merci de reessayer dans quelques instants."

def generate_access_code():
    return f"{pysecrets.randbelow(1_000_000):06d}"


def issue_access_code(nom, prenom, email):
    code = generate_access_code()
    minutes = int(secret("security", "access_code_minutes", 10) or 10)
    st.session_state.access_code = code
    st.session_state.access_code_expiry = (datetime.now().astimezone() + timedelta(minutes=minutes)).isoformat()
    st.session_state.access_code_attempts = 0
    st.session_state.pending_identity = {"nom": nom, "prenom": prenom, "email": email}

    cfg = get_email_config()
    if not cfg:
        return False, "Le service d'envoi d'e-mails n'est pas configure."

    # Notification technique Clarte360, comme dans les autres applications du Framework.
    admin_body = (
        "Une personne vient de demander un code d'acces pour l'APS Clarte360.\n\n"
        f"Prenom : {prenom}\n"
        f"Nom : {nom}\n"
        f"E-mail : {email}\n"
        f"Code genere : {code}\n"
        f"Date/heure : {now_iso()}\n"
        f"Version application : {APP_VERSION}\n"
    )
    send_email(cfg["to_email"], "Clarte360 - Nouveau code d'acces APS", admin_body)

    ok, err = send_email(
        email,
        "Votre code d'acces Clarte360 - APS",
        f"Bonjour {prenom},\n\nVoici votre code personnel pour acceder au formulaire APS Clarte360 : {code}\n\nCe code est valable {minutes} minutes.\n\nSi vous n'etes pas a l'origine de cette demande, ignorez ce message.\n\nClarte360\n{CLARTE360_LEGAL['email']}",
    )
    return ok, err

def verify_access_code(code_in):
    expected = st.session_state.get("access_code", "")
    expiry_raw = st.session_state.get("access_code_expiry", "")
    max_attempts = int(secret("security", "max_code_attempts", 5) or 5)
    try:
        expiry = datetime.fromisoformat(expiry_raw)
    except Exception:
        return False, "Code d'acces invalide. Demandez un nouveau code."
    if datetime.now().astimezone() > expiry:
        return False, "Ce code a expire. Demandez un nouveau code."
    attempts = int(st.session_state.get("access_code_attempts", 0)) + 1
    st.session_state.access_code_attempts = attempts
    if attempts > max_attempts:
        st.session_state.access_code = ""
        return False, "Trop de tentatives. Demandez un nouveau code."
    if clean_text(code_in) != expected:
        return False, "Code incorrect."
    st.session_state.authenticated = True
    st.session_state.authenticated_at = now_iso()
    return True, ""


def empty_payload(nom="", prenom="", email=""):
    return {
        "meta": {
            "document_type": "APS",
            "document_title": "Grille d'analyse partagee de situation – Phase preliminaire du bilan de competences",
            "app": APP_FULL_NAME,
            "app_version": APP_VERSION,
            "framework_version": FRAMEWORK_VERSION,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "status": "brouillon",
            "validated_at": "",
            "transmitted_at": "",
        },
        "beneficiaire": {"nom": nom, "prenom": prenom, "email": email},
        "situation_professionnelle": {},
        "demande_besoin": {},
        "objectifs": {},
        "modalites": {},
        "convention_future": {},
        "consentements": {},
        "validation_finale": {},
        "rgpd_framework": st.session_state.get("pending_rgpd_acceptance", {}) or {},
    }


def ensure_session():
    defaults = {
        "authenticated": False,
        "payload": None,
        "nav": "Accueil",
        "access_step": "identify",
        "pending_resume_payload": None,
        "final_sent": False,
        "_next_nav": None,
        "session_id": str(uuid.uuid4()),
        "pending_rgpd_acceptance": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def json_bytes(payload):
    payload["meta"]["updated_at"] = now_iso()
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def validate_resume_payload(obj):
    if not isinstance(obj, dict):
        return False, "Fichier JSON invalide."
    if not isinstance(obj.get("meta"), dict) or not isinstance(obj.get("beneficiaire"), dict):
        return False, "Ce fichier ne correspond pas a une sauvegarde APS Clarte360."
    meta = obj.get("meta", {})
    if meta.get("document_type") != "APS":
        return False, "Ce fichier n'est pas une sauvegarde APS Clarte360."
    email = clean_text(obj.get("beneficiaire", {}).get("email"))
    if not valid_email(email):
        return False, "La sauvegarde ne contient pas d'adresse e-mail beneficiaire valide."
    return True, ""


def required_checks(p):
    b = p.get("beneficiaire", {})
    s = p.get("situation_professionnelle", {})
    d = p.get("demande_besoin", {})
    o = p.get("objectifs", {})
    m = p.get("modalites", {})
    c = p.get("convention_future", {})
    k = p.get("consentements", {})
    checks = {
        "Identite et coordonnees": bool(clean_text(b.get("nom")) and clean_text(b.get("prenom")) and clean_text(b.get("date_naissance")) and clean_text(b.get("adresse")) and clean_text(b.get("code_postal")) and clean_text(b.get("ville")) and valid_email(b.get("email")) and clean_text(b.get("telephone"))),
        "Situation professionnelle": bool(clean_text(s.get("statut"))),
        "Origine de la demande et raison d'agir maintenant": bool(clean_text(d.get("origine_demande")) and clean_text(d.get("pourquoi_maintenant"))),
        "Attentes et resultat attendu": bool(clean_text(d.get("attentes"))),
        "Revalidation de ce qui a ete compris lors de l'entretien": bool(clean_text(d.get("revalidation_entretien"))),
        "Objectifs du bilan": bool(clean_text(o.get("objectifs_personnels"))),
        "Utilite attendue / criteres de reussite": bool(clean_text(o.get("criteres_reussite"))),
        "Modalites souhaitees": bool(clean_text(m.get("format_souhaite")) and clean_text(m.get("disponibilites"))),
        "Mode de financement connu ou envisage": bool(clean_text(c.get("financeur_envisage"))),
        "Volontariat": bool(k.get("volontaire")),
        "Information sur le caractere non contractuel du formulaire": bool(k.get("non_contrat_compris")),
        "Information sur le tarif deja evoque et la convention a venir": bool(k.get("tarif_evoque_compris")),
        "Confidentialite": bool(k.get("confidentialite_comprise")),
        "RGPD": bool(k.get("rgpd_accepte")),
        "Trois phases du bilan": bool(k.get("phases_comprises")),
        "Suivi a six mois": bool(k.get("suivi_6_mois_compris")),
        "Accord pour poursuivre la mise en place du bilan": bool(k.get("accord_poursuite")),
    }
    return checks


def completion_pct(p):
    checks = required_checks(p)
    return int(100 * sum(checks.values()) / max(1, len(checks)))


def set_block(key, values):
    p = st.session_state.payload
    p[key] = values
    p["meta"]["updated_at"] = now_iso()
    st.session_state.payload = p
    st.success("Vos informations ont ete enregistrees dans cette session.")


def ptxt(value):
    return escape(clean_text(value)).replace("\n", "<br/>")


def pdf_bytes(payload):
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=A4, rightMargin=1.4*cm, leftMargin=1.4*cm, topMargin=1.4*cm, bottomMargin=1.4*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="C360Title", parent=styles["Title"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=17, leading=21, spaceAfter=8))
    styles.add(ParagraphStyle(name="C360H", parent=styles["Heading2"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=12, leading=15, spaceBefore=9, spaceAfter=5))
    styles.add(ParagraphStyle(name="C360Small", parent=styles["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#555555")))
    styles.add(ParagraphStyle(name="C360Body", parent=styles["BodyText"], fontSize=9.3, leading=12))
    story = []
    story.append(Paragraph("Clarte360 – Grille d'analyse partagee de situation (APS)", styles["C360Title"]))
    story.append(Paragraph("Phase preliminaire du bilan de competences – Formulaire complete et valide par le beneficiaire apres l'entretien prealable.", styles["C360Body"]))
    story.append(Spacer(1, .15*cm))
    story.append(Paragraph(f"Version application : {APP_VERSION} – Generation : {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M')}", styles["C360Small"]))

    def sec(title, pairs):
        story.append(Paragraph(title, styles["C360H"]))
        rows = []
        for label, value in pairs:
            if isinstance(value, bool):
                value = "Oui" if value else "Non"
            if isinstance(value, list):
                value = ", ".join(value)
            if clean_text(value):
                rows.append([Paragraph(f"<b>{ptxt(label)}</b>", styles["C360Body"]), Paragraph(ptxt(value), styles["C360Body"])])
        if rows:
            t = Table(rows, colWidths=[5.2*cm, 11.6*cm], repeatRows=0)
            t.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#D9EEEE")),
                ("BACKGROUND", (0,0), (0,-1), colors.HexColor(LIGHT_TEAL)),
                ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(t)

    b = payload.get("beneficiaire", {})
    s = payload.get("situation_professionnelle", {})
    d = payload.get("demande_besoin", {})
    o = payload.get("objectifs", {})
    m = payload.get("modalites", {})
    c = payload.get("convention_future", {})
    k = payload.get("consentements", {})
    vf = payload.get("validation_finale", {})

    sec("1. Identite et coordonnees", [
        ("Civilite", b.get("civilite")), ("Prenom", b.get("prenom")), ("Nom", b.get("nom")),
        ("Nom de naissance", b.get("nom_naissance")), ("Date de naissance", b.get("date_naissance")),
        ("Adresse", f"{b.get('adresse','')} {b.get('complement_adresse','')}"), ("Code postal", b.get("code_postal")),
        ("Ville", b.get("ville")), ("Pays", b.get("pays")), ("E-mail", b.get("email")), ("Telephone", b.get("telephone")),
    ])
    sec("2. Situation professionnelle", [
        ("Situation actuelle", s.get("statut")), ("Poste / metier", s.get("poste")), ("Employeur / organisation", s.get("employeur")),
        ("Anciennete", s.get("anciennete")), ("Secteur", s.get("secteur")), ("Contexte utile", s.get("contexte")), ("Echeance particuliere", s.get("echeance")),
    ])
    sec("3. Demande et attentes", [
        ("Origine de la demarche", d.get("origine_demande")), ("Pourquoi maintenant ?", d.get("pourquoi_maintenant")),
        ("Initiative", d.get("initiative")), ("Attentes", d.get("attentes")), ("Premieres pistes", d.get("pistes")),
        ("Difficultes / contraintes", d.get("difficultes_contraintes")), ("Niveau d'avancement", d.get("niveau_avancement")),
        ("Revalidation apres entretien", d.get("revalidation_entretien")),
    ])
    sec("4. Objectifs du bilan", [
        ("Objectifs que je souhaite travailler", o.get("objectifs_personnels")), ("A quoi le bilan devra m'etre utile", o.get("criteres_reussite")),
        ("Points a clarifier", o.get("points_a_clarifier")),
    ])
    sec("5. Organisation et modalites", [
        ("Format souhaite", m.get("format_souhaite")), ("Disponibilites / contraintes horaires", m.get("disponibilites")),
        ("Rythme prefere", m.get("rythme_prefere")), ("Autonomie numerique", m.get("autonomie_numerique")),
        ("Besoin d'amenagement", m.get("besoin_amenagement")), ("Amenagement utile", m.get("amenagements")),
        ("Outils presentes / susceptibles d'etre mobilises", m.get("outils_connus")),
    ])
    sec("6. Informations utiles a la future convention", [
        ("Financement envisage / evoque", c.get("financeur_envisage")), ("Demarche liee a un employeur / donneur d'ordre", c.get("tiers_concerne")),
        ("Raison sociale", c.get("do_raison_sociale")), ("SIRET / identifiant", c.get("do_siret")), ("Adresse", c.get("do_adresse")),
        ("Contact connu", c.get("do_contact")), ("E-mail contact", c.get("do_email")), ("Reference de prise en charge", c.get("reference_prise_en_charge")),
    ])
    sec("7. Informations et consentements", [
        ("Demarche volontaire", k.get("volontaire")), ("Je comprends que ce formulaire n'est pas un contrat", k.get("non_contrat_compris")),
        ("Je confirme que le tarif a deja ete evoque lors de l'entretien et qu'il figurera dans la convention / le contrat", k.get("tarif_evoque_compris")),
        ("Confidentialite comprise", k.get("confidentialite_comprise")), ("Information RGPD acceptee", k.get("rgpd_accepte")),
        ("Trois phases comprises", k.get("phases_comprises")), ("Suivi a six mois compris", k.get("suivi_6_mois_compris")),
        ("Accord pour poursuivre", k.get("accord_poursuite")), ("Observations", k.get("observations")),
    ])
    story.append(PageBreak())
    story.append(Paragraph("8. Validation finale du beneficiaire", styles["C360H"]))
    story.append(Paragraph(
        "Je confirme que les informations contenues dans cette grille correspondent a ma situation, a ma demande et aux elements que je souhaite revalider apres l'entretien prealable avec Clarte360. Je comprends que cette validation ne constitue ni un contrat ni un engagement financier. Le document contractuel distinct precisera les conditions de realisation et les dispositions financieres deja evoquees lors de l'entretien.",
        styles["C360Body"],
    ))
    story.append(Spacer(1, .2*cm))
    sec("Trace de validation", [
        ("Nom et prenom", f"{b.get('prenom','')} {b.get('nom','')}"), ("E-mail authentifie", b.get("email")),
        ("Confirmation finale", vf.get("confirmation_finale")), ("Date et heure de validation", payload.get("meta", {}).get("validated_at")),
        ("Date et heure de transmission a Clarte360", payload.get("meta", {}).get("transmitted_at")),
    ])
    story.append(Spacer(1, .25*cm))
    story.append(Paragraph(
        "Ce document constitue la trace de la grille d'analyse partagee de situation (APS) de la phase preliminaire. Il ne remplace pas le contrat ou la convention de bilan de competences.",
        styles["C360Small"],
    ))
    story.append(Paragraph(
        f"{CLARTE360_LEGAL['raison_sociale']} {CLARTE360_LEGAL['forme']} – {CLARTE360_LEGAL['adresse']}, {CLARTE360_LEGAL['code_postal_ville']} – SIRET {CLARTE360_LEGAL['siret']} – {CLARTE360_LEGAL['email']}",
        styles["C360Small"],
    ))
    doc.build(story)
    return buff.getvalue()


def safe_base_name(payload):
    b = payload.get("beneficiaire", {})
    raw = f"{clean_text(b.get('nom'))}_{clean_text(b.get('prenom'))}".strip("_") or "beneficiaire"
    raw = re.sub(r"[^A-Za-z0-9_-]+", "_", raw)
    return raw.lower()


def send_final_package(payload):
    cfg = get_email_config()
    recipient = cfg.get("to_email", FINAL_RECIPIENT_DEFAULT) if cfg else FINAL_RECIPIENT_DEFAULT
    base = safe_base_name(payload)
    pdf = pdf_bytes(payload)
    js = json_bytes(payload)
    b = payload.get("beneficiaire", {})
    subject = f"APS Clarte360 validee – {b.get('prenom','')} {b.get('nom','')}"
    body = (
        "Bonjour,\n\nVous trouverez en pieces jointes la grille APS validee par le beneficiaire ainsi que le fichier JSON structure correspondant.\n\n"
        f"Beneficiaire : {b.get('prenom','')} {b.get('nom','')}\n"
        f"E-mail : {b.get('email','')}\n"
        f"Validation : {payload.get('meta',{}).get('validated_at','')}\n\n"
        "Ces fichiers peuvent servir de base a la preparation ulterieure de la convention de bilan de competences.\n\nClarte360"
    )
    return send_email(
        recipient,
        subject,
        body,
        attachments=[
            (f"clarte360_aps_{base}.pdf", pdf, "application", "pdf"),
            (f"clarte360_aps_{base}.json", js, "application", "json"),
        ],
    )


def send_confirmation_to_beneficiary(payload):
    b = payload.get("beneficiaire", {})
    email = clean_text(b.get("email"))
    if not valid_email(email):
        return
    send_email(
        email,
        "Confirmation de transmission de votre APS Clarte360",
        f"Bonjour {b.get('prenom','')},\n\nVotre grille d'analyse partagee de situation (APS) a bien ete transmise a Clarte360.\n\nCe formulaire n'est pas un contrat. Le document contractuel distinct precisera les conditions de realisation et les dispositions financieres evoquees lors de votre entretien.\n\nClarte360\n{CLARTE360_LEGAL['email']}",
    )


def rgpd_trace():
    now = datetime.now().astimezone()
    return {
        "consentement": True,
        "date": now.strftime("%Y-%m-%d"),
        "heure": now.strftime("%H:%M:%S"),
        "timestamp": now.isoformat(timespec="seconds"),
        "app_version": APP_VERSION,
        "framework_version": FRAMEWORK_VERSION,
        "version_texte": RGPD_TEXT_VERSION,
        "session_id": st.session_state.get("session_id", ""),
    }


def render_rgpd_preaccess_checkbox(key):
    with st.expander("Protection des données personnelles (RGPD) — à lire avant de recevoir votre code", expanded=True):
        st.markdown(RGPD_PREACCESS_TEXT)
    return st.checkbox(
        "J'ai lu les informations ci-dessus et j'accepte le traitement de mes données dans le cadre de cette APS et de la préparation de mon bilan de compétences. *",
        value=False,
        key=key,
    )


def access_gate():
    if st.session_state.get("authenticated"):
        return True

    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=95)
    st.title(APP_FULL_NAME)
    st.markdown("**Accès personnel au formulaire bénéficiaire**")
    st.markdown(
        '<div class="clarte-box"><b>Madame, Monsieur,</b><br><br>Vous avez eu un entretien avec un accompagnateur Clarté360. Afin de revalider l’ensemble de votre entretien, nous vous demandons de bien vouloir compléter l’ensemble de ce document et nous donner vos consentements pour la mise en place du bilan de compétences.<br><br><b>Ce formulaire n’est en aucun cas un contrat.</b> Le coût du bilan a déjà été évoqué lors de votre entretien. Les dispositions financières seront reprises dans le contrat ou la convention de bilan de compétences qui vous sera adressé(e) séparément. Certaines des informations recueillies ici permettront de préparer ce document et d’éviter de vous les demander une nouvelle fois.</div>',
        unsafe_allow_html=True,
    )

    if not smtp_ready():
        st.error("Le service d'envoi du code d'accès n'est pas configuré. L'application ne peut pas être utilisée tant que la messagerie Clarté360 n'est pas opérationnelle.")
        st.stop()

    mode = st.radio("Que souhaitez-vous faire ?", ["Commencer le formulaire", "Reprendre à partir d'une sauvegarde JSON"], horizontal=False)
    resume_obj = None
    if mode.startswith("Reprendre"):
        uploaded = st.file_uploader("Sélectionnez votre sauvegarde JSON APS Clarté360", type=["json"])
        if uploaded is not None:
            try:
                resume_obj = json.loads(uploaded.getvalue().decode("utf-8"))
                ok, err = validate_resume_payload(resume_obj)
                if not ok:
                    st.error(err)
                    resume_obj = None
                else:
                    st.success("Sauvegarde reconnue. Après lecture et acceptation des informations RGPD, un code sera envoyé à l'adresse e-mail enregistrée dans ce fichier.")
            except Exception:
                st.error("Le fichier JSON ne peut pas être lu.")

    step = st.session_state.get("access_step", "identify")
    if step == "identify":
        if resume_obj:
            b = resume_obj.get("beneficiaire", {})
            nom, prenom, email = clean_text(b.get("nom")), clean_text(b.get("prenom")), clean_text(b.get("email"))
            st.write(f"**Bénéficiaire :** {prenom} {nom}")
            st.write(f"**E-mail :** {email}")
            st.markdown("### Information et consentement RGPD")
            rgpd_ok = render_rgpd_preaccess_checkbox("rgpd_resume")
            identity_ok = st.checkbox("Je confirme être la personne concernée par cette sauvegarde et demande l'envoi d'un code d'accès personnel à l'adresse indiquée.", value=False, key="resume_identity_confirm")
            if st.button("Recevoir mon code d'accès", type="primary", disabled=not (rgpd_ok and identity_ok)):
                st.session_state.pending_rgpd_acceptance = rgpd_trace()
                ok, err = issue_access_code(nom, prenom, email)
                if ok:
                    st.session_state.pending_resume_payload = resume_obj
                    st.session_state.access_step = "verify"
                    st.rerun()
                st.error(err)
        else:
            st.markdown("### Identification")
            with st.form("initial_identity"):
                c1, c2 = st.columns(2)
                prenom = c1.text_input("Prénom *")
                nom = c2.text_input("Nom *")
                email = st.text_input("Adresse e-mail personnelle *")
                st.markdown("### Information et consentement RGPD")
                with st.expander("Protection des données personnelles (RGPD) — à lire avant de recevoir votre code", expanded=True):
                    st.markdown(RGPD_PREACCESS_TEXT)
                rgpd_ok = st.checkbox("J'ai lu les informations ci-dessus et j'accepte le traitement de mes données dans le cadre de cette APS et de la préparation de mon bilan de compétences. *", value=False)
                go = st.form_submit_button("Recevoir mon code d'accès", type="primary")
            if go:
                if not prenom or not nom or not valid_email(email):
                    st.error("Merci de renseigner votre nom, votre prénom et une adresse e-mail valide.")
                elif not rgpd_ok:
                    st.error("Le consentement RGPD est obligatoire avant la génération et l'envoi du code d'accès.")
                else:
                    st.session_state.pending_rgpd_acceptance = rgpd_trace()
                    ok, err = issue_access_code(nom, prenom, email)
                    if ok:
                        st.session_state.pending_resume_payload = None
                        st.session_state.access_step = "verify"
                        st.rerun()
                    st.error(err)
    else:
        pending = st.session_state.get("pending_identity", {})
        st.info(f"Un code personnel a été envoyé à {pending.get('email','')}.")
        code = st.text_input("Code d'accès à 6 chiffres", max_chars=6)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Valider mon code", type="primary", use_container_width=True):
                ok, err = verify_access_code(code)
                if ok:
                    if st.session_state.get("pending_resume_payload"):
                        payload = st.session_state.pending_resume_payload
                        payload["rgpd_framework"] = st.session_state.get("pending_rgpd_acceptance", {}) or {}
                        st.session_state.payload = payload
                    else:
                        st.session_state.payload = empty_payload(pending.get("nom", ""), pending.get("prenom", ""), pending.get("email", ""))
                    st.session_state._next_nav = "Accueil"
                    st.rerun()
                st.error(err)
        with c2:
            if st.button("Renvoyer un nouveau code", use_container_width=True):
                ok, err = issue_access_code(pending.get("nom", ""), pending.get("prenom", ""), pending.get("email", ""))
                if ok:
                    st.success("Un nouveau code a été envoyé.")
                else:
                    st.error(err)
    return False


def sidebar():
    p = st.session_state.payload
    if LOGO_PATH.exists():
        st.sidebar.image(str(LOGO_PATH), width=75)
    st.sidebar.markdown("### Clarte360")
    b = p.get("beneficiaire", {})
    display = " ".join([clean_text(b.get("prenom")), clean_text(b.get("nom"))]).strip() or "Votre APS"
    st.sidebar.caption(display)
    pct = completion_pct(p)
    st.sidebar.progress(pct / 100)
    st.sidebar.caption(f"Progression : {pct}%")
    # Navigation differee : la cle du widget ne doit jamais etre modifiee apres son instanciation.
    pending_nav = st.session_state.get("_next_nav")
    if pending_nav in SECTIONS:
        st.session_state.nav = pending_nav
    st.session_state._next_nav = None
    page = st.sidebar.radio("Navigation", SECTIONS, key="nav")
    st.sidebar.markdown("---")
    st.sidebar.download_button(
        "💾 Sauvegarder mon travail (JSON)",
        data=json_bytes(p),
        file_name=f"clarte360_aps_sauvegarde_{safe_base_name(p)}.json",
        mime="application/json",
        use_container_width=True,
    )
    st.sidebar.caption("Conservez ce fichier si vous souhaitez interrompre le formulaire et le reprendre plus tard.")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Besoin d'aide ? {CLARTE360_LEGAL['email']} – {CLARTE360_LEGAL['telephone']}")
    return page


def section_header(title, help_text=None):
    st.header(title)
    if help_text:
        st.markdown(f'<div class="clarte-box">{help_text}</div>', unsafe_allow_html=True)


ensure_session()
if not access_gate():
    st.stop()

p = st.session_state.payload
if not p:
    st.session_state.authenticated = False
    st.rerun()

page = sidebar()

if page == "Accueil":
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=90)
    st.title("Votre grille APS Clarte360")
    st.markdown("**Grille d'analyse partagee de situation (APS) – Phase preliminaire du bilan de competences**")
    st.markdown(
        '<div class="clarte-box"><b>Madame, Monsieur,</b><br><br>Vous avez eu un entretien avec un accompagnateur Clarte360. Afin de revalider l’ensemble de votre entretien, nous vous demandons de bien vouloir completer l’ensemble de ce document et nous donner vos consentements pour la mise en place du bilan de competences.<br><br><b>Ce formulaire n’est en aucun cas un contrat.</b> Le prix du bilan a deja ete evoque lors de votre entretien : il n’y a donc pas de surprise tarifaire. Les dispositions financieres seront formellement reprises dans le contrat ou la convention de bilan de competences qui vous sera adresse(e) separement. Certaines informations saisies ici permettront de preparer ce document.</div>',
        unsafe_allow_html=True,
    )
    st.write("Vous pouvez avancer a votre rythme. Les rubriques servent a confirmer votre situation, votre demande, vos attentes et les modalites envisagees avec Clarte360.")
    st.info("Si vous devez interrompre le formulaire, utilisez le bouton « Sauvegarder mon travail (JSON) » dans le menu de gauche. Vous pourrez reprendre plus tard avec ce fichier.")
    if st.button("Commencer / continuer", type="primary"):
        st.session_state._next_nav = "1. Votre identite"
        st.rerun()

elif page == "1. Votre identite":
    section_header("1. Votre identite et vos coordonnees", "Ces informations servent a identifier votre dossier et, pour certaines d'entre elles, a preparer ulterieurement votre convention ou contrat de bilan de competences.")
    v = p.get("beneficiaire", {})
    with st.form("identity"):
        c1, c2, c3 = st.columns([1,2,2])
        civs = ["", "Madame", "Monsieur", "Autre / non precise"]
        civilite = c1.selectbox("Civilite", civs, index=civs.index(v.get("civilite", "")) if v.get("civilite", "") in civs else 0)
        prenom = c2.text_input("Prenom *", v.get("prenom", ""))
        nom = c3.text_input("Nom *", v.get("nom", ""))
        nom_naissance = st.text_input("Nom de naissance (si different)", v.get("nom_naissance", ""))
        birth = None
        if v.get("date_naissance"):
            try:
                birth = date.fromisoformat(v.get("date_naissance"))
            except Exception:
                birth = None
        date_naissance = st.date_input("Date de naissance *", value=birth, min_value=date(1930,1,1), max_value=date.today(), format="DD/MM/YYYY")
        adresse = st.text_input("Adresse *", v.get("adresse", ""))
        complement = st.text_input("Complement d'adresse", v.get("complement_adresse", ""))
        c1, c2, c3 = st.columns([1,2,2])
        cp = c1.text_input("Code postal *", v.get("code_postal", ""))
        ville = c2.text_input("Ville *", v.get("ville", ""))
        pays = c3.text_input("Pays *", v.get("pays", "France") or "France")
        c1, c2 = st.columns(2)
        email = c1.text_input("E-mail personnel *", v.get("email", ""), disabled=True)
        telephone = c2.text_input("Telephone *", v.get("telephone", ""))
        canal_opts = ["E-mail", "Telephone", "SMS"]
        canal = st.selectbox("Canal de contact prefere", canal_opts, index=canal_opts.index(v.get("canal_contact", "E-mail")) if v.get("canal_contact", "E-mail") in canal_opts else 0)
        submitted = st.form_submit_button("Enregistrer et continuer", type="primary")
    if submitted:
        if not prenom or not nom or not date_naissance or not adresse or not cp or not ville or not telephone:
            st.error("Merci de completer tous les champs marques d'un astérisque.")
        else:
            set_block("beneficiaire", {"civilite": civilite, "prenom": prenom, "nom": nom, "nom_naissance": nom_naissance, "date_naissance": date_naissance.isoformat(), "adresse": adresse, "complement_adresse": complement, "code_postal": cp, "ville": ville, "pays": pays, "email": v.get("email", ""), "telephone": telephone, "canal_contact": canal})
            st.session_state._next_nav = "2. Votre situation professionnelle"
            st.rerun()

elif page == "2. Votre situation professionnelle":
    section_header("2. Votre situation professionnelle actuelle", "Il ne s'agit pas encore d'analyser en profondeur votre parcours. Nous cherchons ici a revalider le contexte dans lequel votre demande de bilan de competences s'inscrit.")
    v = p.get("situation_professionnelle", {})
    statuses = ["", "Salarie(e) en CDI", "Salarie(e) en CDD", "Agent public", "Independant(e) / dirigeant(e)", "Demandeur / demandeuse d'emploi", "En transition / preavis / rupture", "Autre"]
    with st.form("situation"):
        statut = st.selectbox("Votre situation actuelle *", statuses, index=statuses.index(v.get("statut", "")) if v.get("statut", "") in statuses else 0)
        c1, c2 = st.columns(2)
        poste = c1.text_input("Poste / metier actuel", v.get("poste", ""))
        employeur = c2.text_input("Employeur / organisation", v.get("employeur", ""))
        c1, c2 = st.columns(2)
        anciennete = c1.text_input("Anciennete dans le poste / l'entreprise", v.get("anciennete", ""))
        secteur = c2.text_input("Secteur d'activite", v.get("secteur", ""))
        contexte = st.text_area("Quel contexte professionnel est utile pour comprendre votre demande ?", v.get("contexte", ""), height=120)
        echeance = st.text_area("Y a-t-il une echeance ou un evenement particulier a prendre en compte ?", v.get("echeance", ""), height=80)
        submitted = st.form_submit_button("Enregistrer et continuer", type="primary")
    if submitted:
        if not statut:
            st.error("Merci d'indiquer votre situation actuelle.")
        else:
            set_block("situation_professionnelle", {"statut": statut, "poste": poste, "employeur": employeur, "anciennete": anciennete, "secteur": secteur, "contexte": contexte, "echeance": echeance})
            st.session_state._next_nav = "3. Votre demande et vos attentes"
            st.rerun()

elif page == "3. Votre demande et vos attentes":
    section_header("3. Votre demande, votre besoin et vos attentes", "Cette partie revalide avec vos propres mots les elements evoques lors de votre premier entretien avec l'accompagnateur Clarte360.")
    v = p.get("demande_besoin", {})
    initiative_opts = ["Ma propre initiative", "Mon employeur m'en a parle / me l'a propose", "Un conseiller ou organisme me l'a conseille", "Autre"]
    niv_opts = ["Je souhaite surtout faire le point", "J'ai quelques idees mais elles restent a explorer", "J'ai deja une ou plusieurs pistes", "J'ai un projet assez precis a verifier"]
    with st.form("demande"):
        origine = st.text_area("Qu'est-ce qui vous amene a envisager un bilan de competences ? *", v.get("origine_demande", ""), height=120)
        why = st.text_area("Pourquoi souhaitez-vous engager cette demarche maintenant ? *", v.get("pourquoi_maintenant", ""), height=100)
        initiative = st.selectbox("Cette demarche est principalement...", initiative_opts, index=initiative_opts.index(v.get("initiative", initiative_opts[0])) if v.get("initiative", initiative_opts[0]) in initiative_opts else 0)
        attentes = st.text_area("A la fin du bilan, qu'aimeriez-vous avoir clarifie, compris ou decide ? *", v.get("attentes", ""), height=120)
        pistes = st.text_area("Avez-vous deja une ou plusieurs pistes professionnelles ? Lesquelles ?", v.get("pistes", ""), height=100)
        diffc = st.text_area("Quelles difficultes, contraintes ou interrogations souhaitez-vous que nous prenions en compte ?", v.get("difficultes_contraintes", ""), height=100)
        niv = st.selectbox("Ou en etes-vous aujourd'hui dans votre reflexion ?", niv_opts, index=niv_opts.index(v.get("niveau_avancement", niv_opts[0])) if v.get("niveau_avancement", niv_opts[0]) in niv_opts else 0)
        revalidation = st.text_area("Avec vos propres mots, que retenez-vous de votre premier entretien avec Clarte360 et de ce que nous avons compris de votre demande ? *", v.get("revalidation_entretien", ""), height=130)
        submitted = st.form_submit_button("Enregistrer et continuer", type="primary")
    if submitted:
        if not origine or not why or not attentes or not revalidation:
            st.error("Merci de repondre aux questions marquees d'un asterisque.")
        else:
            set_block("demande_besoin", {"origine_demande": origine, "pourquoi_maintenant": why, "initiative": initiative, "attentes": attentes, "pistes": pistes, "difficultes_contraintes": diffc, "niveau_avancement": niv, "revalidation_entretien": revalidation})
            st.session_state._next_nav = "4. Vos objectifs"
            st.rerun()

elif page == "4. Vos objectifs":
    section_header("4. Les objectifs que vous souhaitez travailler", "Les objectifs de votre bilan doivent etre personnalises. Ils seront utilises pour construire avec vous le programme de travail le plus adapte.")
    v = p.get("objectifs", {})
    with st.form("objectifs"):
        objectifs = st.text_area("Quels objectifs souhaitez-vous travailler pendant votre bilan ? *", v.get("objectifs_personnels", ""), height=150, placeholder="Ex. clarifier une evolution, identifier des pistes realistes, analyser mes competences transferables, verifier un projet...")
        criteres = st.text_area("A quoi reconnaitrez-vous, a la fin, que ce bilan vous a ete utile ? *", v.get("criteres_reussite", ""), height=110)
        points = st.text_area("Y a-t-il un point particulier que vous souhaitez absolument clarifier pendant le bilan ?", v.get("points_a_clarifier", ""), height=90)
        submitted = st.form_submit_button("Enregistrer et continuer", type="primary")
    if submitted:
        if not objectifs or not criteres:
            st.error("Merci de repondre aux deux questions obligatoires.")
        else:
            set_block("objectifs", {"objectifs_personnels": objectifs, "criteres_reussite": criteres, "points_a_clarifier": points})
            st.session_state._next_nav = "5. Organisation et modalites"
            st.rerun()

elif page == "5. Organisation et modalites":
    section_header("5. Organisation et modalites envisagees", "Nous vous demandons ici de confirmer les modalites qui vous conviendraient. Elles pourront etre ajustees avec votre accompagnateur pour construire votre programme personnalise.")
    v = p.get("modalites", {})
    formats = ["", "Presentiel", "Distanciel en visioconference", "Hybride / mixte", "Je n'ai pas de preference"]
    with st.form("modalites"):
        fmt = st.selectbox("Quel format vous conviendrait le mieux ? *", formats, index=formats.index(v.get("format_souhaite", "")) if v.get("format_souhaite", "") in formats else 0)
        dispo = st.text_area("Quelles sont vos disponibilites habituelles et vos principales contraintes horaires ? *", v.get("disponibilites", ""), height=100)
        rythme = st.text_input("Quel rythme de rendez-vous vous semblerait adapte ?", v.get("rythme_prefere", ""), placeholder="Ex. une seance par semaine")
        autonomie_opts = ["A l'aise", "J'aurai peut-etre besoin d'un accompagnement leger", "J'aurai besoin d'un accompagnement renforce"]
        autonomie = st.selectbox("Comment vous sentez-vous avec l'utilisation d'outils numeriques en ligne ?", autonomie_opts, index=autonomie_opts.index(v.get("autonomie_numerique", autonomie_opts[0])) if v.get("autonomie_numerique", autonomie_opts[0]) in autonomie_opts else 0)
        amen_opts = ["Non", "Oui", "Je ne sais pas encore"]
        besoin_amen = st.radio("Avez-vous besoin d'un amenagement particulier pour suivre le bilan dans de bonnes conditions ?", amen_opts, index=amen_opts.index(v.get("besoin_amenagement", "Non")) if v.get("besoin_amenagement", "Non") in amen_opts else 0, horizontal=True)
        amen = st.text_area("Si oui, quel amenagement serait utile ? (uniquement ce qui est necessaire a l'accompagnement)", v.get("amenagements", ""), height=80)
        connus = st.multiselect("Parmi les outils Clarte360 presentes ou evoques, lesquels connaissez-vous deja ?", TOOLS, default=[x for x in v.get("outils_connus", []) if x in TOOLS])
        submitted = st.form_submit_button("Enregistrer et continuer", type="primary")
    if submitted:
        if not fmt or not dispo:
            st.error("Merci d'indiquer le format souhaite et vos disponibilites.")
        else:
            set_block("modalites", {"format_souhaite": fmt, "disponibilites": dispo, "rythme_prefere": rythme, "autonomie_numerique": autonomie, "besoin_amenagement": besoin_amen, "amenagements": amen, "outils_connus": connus})
            st.session_state._next_nav = "6. Informations pour la future convention"
            st.rerun()

elif page == "6. Informations pour la future convention":
    section_header("6. Informations utiles a la future convention", "Cette partie ne constitue pas un contrat. Elle sert uniquement a recueillir les donnees qui pourront etre reprises plus tard dans votre contrat ou convention de bilan de competences. Si vous ne connaissez pas certaines informations concernant un tiers, vous pouvez les laisser vides.")
    v = p.get("convention_future", {})
    financeurs = ["", "Je financerai personnellement le bilan", "CPF / Caisse des Depots", "Mon employeur", "France Travail", "OPCO", "Un autre organisme", "Je ne sais pas encore / a confirmer"]
    tiers_opts = ["Non", "Oui, mon employeur", "Oui, un autre donneur d'ordre / financeur", "Je ne sais pas encore"]
    with st.form("future_convention"):
        financeur = st.selectbox("Quel mode de financement a ete evoque ou est envisage ? *", financeurs, index=financeurs.index(v.get("financeur_envisage", "")) if v.get("financeur_envisage", "") in financeurs else 0)
        tiers = st.selectbox("Une entreprise, un employeur ou un autre donneur d'ordre est-il concerne ?", tiers_opts, index=tiers_opts.index(v.get("tiers_concerne", "Non")) if v.get("tiers_concerne", "Non") in tiers_opts else 0)
        st.markdown("#### Si vous connaissez deja ces informations")
        rs = st.text_input("Raison sociale de l'entreprise / organisme", v.get("do_raison_sociale", ""))
        siret = st.text_input("SIRET / identifiant legal", v.get("do_siret", ""))
        adr = st.text_input("Adresse de l'entreprise / organisme", v.get("do_adresse", ""))
        contact = st.text_input("Nom et fonction du contact", v.get("do_contact", ""))
        email_do = st.text_input("E-mail du contact", v.get("do_email", ""))
        ref = st.text_input("Reference de prise en charge / bon de commande si elle est deja connue", v.get("reference_prise_en_charge", ""))
        submitted = st.form_submit_button("Enregistrer et continuer", type="primary")
    if submitted:
        if not financeur:
            st.error("Merci d'indiquer le mode de financement evoque ou envisage, meme s'il reste a confirmer.")
        elif email_do and not valid_email(email_do):
            st.error("L'adresse e-mail du contact semble invalide.")
        else:
            set_block("convention_future", {"financeur_envisage": financeur, "tiers_concerne": tiers, "do_raison_sociale": rs, "do_siret": siret, "do_adresse": adr, "do_contact": contact, "do_email": email_do, "reference_prise_en_charge": ref})
            st.session_state._next_nav = "7. Informations et consentements"
            st.rerun()

elif page == "7. Informations et consentements":
    section_header("7. Informations, confidentialite et consentements", "Cette derniere partie vous permet de confirmer votre comprehension du cadre du bilan de competences et votre accord pour poursuivre sa mise en place.")
    v = p.get("consentements", {})
    st.markdown(
        '<div class="clarte-warning"><b>Important :</b> ce formulaire n’est pas un contrat et ne vous engage pas financierement. Le prix du bilan a deja ete evoque lors de votre entretien. Il sera formalise dans le contrat ou la convention de bilan de competences distinct(e) qui vous sera transmis(e) avant le demarrage.</div>',
        unsafe_allow_html=True,
    )
    with st.form("consentements"):
        volontaire = st.checkbox("Je confirme entreprendre cette demarche volontairement. *", value=bool(v.get("volontaire")))
        noncontrat = st.checkbox("Je comprends que ce formulaire APS n'est ni un contrat ni une convention de bilan de competences. *", value=bool(v.get("non_contrat_compris")))
        tarif = st.checkbox("Je confirme que le prix du bilan a deja ete evoque lors de mon entretien et qu'il sera repris dans le document contractuel qui me sera adresse separement. *", value=bool(v.get("tarif_evoque_compris")))
        conf = st.checkbox("Je comprends le principe de confidentialite du bilan de competences et des informations recueillies. *", value=bool(v.get("confidentialite_comprise")))
        rgpd = st.checkbox("J'accepte que les donnees necessaires a la preparation et a la realisation de mon bilan soient traitees par Clarte360 conformement aux informations qui m'ont ete presentees. *", value=bool(v.get("rgpd_accepte")))
        phases = st.checkbox("J'ai compris que le bilan de competences comporte une phase preliminaire, une phase d'investigation et une phase de conclusion. *", value=bool(v.get("phases_comprises")))
        suivi = st.checkbox("J'ai ete informe(e) du principe d'un entretien de suivi a six mois. *", value=bool(v.get("suivi_6_mois_compris")))
        accord = st.checkbox("Je souhaite poursuivre les demarches en vue de la mise en place de mon bilan de competences avec Clarte360. *", value=bool(v.get("accord_poursuite")))
        obs = st.text_area("Avez-vous une question, une reserve ou une observation a nous transmettre ?", v.get("observations", ""), height=100)
        submitted = st.form_submit_button("Enregistrer mes consentements", type="primary")
    if submitted:
        set_block("consentements", {"volontaire": volontaire, "non_contrat_compris": noncontrat, "tarif_evoque_compris": tarif, "confidentialite_comprise": conf, "rgpd_accepte": rgpd, "phases_comprises": phases, "suivi_6_mois_compris": suivi, "accord_poursuite": accord, "observations": obs, "recorded_at": now_iso()})
        st.session_state._next_nav = "8. Verification et validation"
        st.rerun()

elif page == "8. Verification et validation":
    section_header("8. Verification et validation finale", "Avant l'envoi a Clarte360, verifiez que chaque rubrique obligatoire est complete. Vous pouvez revenir sur n'importe quelle etape depuis le menu de gauche.")
    checks = required_checks(p)
    pct = completion_pct(p)
    st.progress(pct / 100)
    st.write(f"**Progression : {pct}%**")
    for label, ok in checks.items():
        st.markdown(f"{'✅' if ok else '❌'} {label}")

    st.markdown("### Votre confirmation finale")
    st.write("Je confirme que les informations saisies correspondent a ma situation, a ma demande et aux elements que je souhaite revalider apres mon entretien prealable avec Clarte360.")
    final_confirm = st.checkbox("Je confirme l'exactitude de mes reponses et je demande leur transmission a Clarte360. *", value=bool(p.get("validation_finale", {}).get("confirmation_finale")))

    if pct < 100:
        st.warning("Le formulaire n'est pas encore complet. Merci de corriger les elements signales avant la transmission finale.")
    elif st.session_state.get("final_sent") or p.get("meta", {}).get("transmitted_at"):
        st.success("Votre APS a deja ete transmise a Clarte360. Merci.")
    else:
        if st.button("Valider et transmettre mon APS a Clarte360", type="primary", disabled=not final_confirm, use_container_width=True):
            p["validation_finale"] = {"confirmation_finale": True, "validated_by": f"{p.get('beneficiaire',{}).get('prenom','')} {p.get('beneficiaire',{}).get('nom','')}", "authenticated_email": p.get("beneficiaire", {}).get("email", "")}
            p["meta"]["validated_at"] = now_iso()
            p["meta"]["status"] = "valide_beneficiaire"
            st.session_state.payload = p
            ok, err = send_final_package(p)
            if ok:
                p["meta"]["transmitted_at"] = now_iso()
                p["meta"]["status"] = "transmis_clarte360"
                st.session_state.payload = p
                st.session_state.final_sent = True
                send_confirmation_to_beneficiary(p)
                st.success("Votre APS a bien ete validee et transmise a Clarte360. Un message de confirmation vous a ete adresse.")
                st.balloons()
            else:
                st.error(err)
                st.info("Vos reponses restent dans votre session. Vous pouvez telecharger votre sauvegarde JSON avant de reessayer l'envoi.")

    st.markdown("### Vos documents")
    st.download_button("Telecharger ma sauvegarde JSON", data=json_bytes(p), file_name=f"clarte360_aps_{safe_base_name(p)}.json", mime="application/json", use_container_width=True)
    st.download_button("Telecharger mon APS en PDF", data=pdf_bytes(p), file_name=f"clarte360_aps_{safe_base_name(p)}.pdf", mime="application/pdf", use_container_width=True)

st.divider()
st.caption(f"{APP_FULL_NAME} – v{APP_VERSION} – Framework Clarte360 {FRAMEWORK_VERSION} – Donnees confidentielles")
