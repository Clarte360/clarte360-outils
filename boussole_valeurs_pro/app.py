import csv
import io
import json
import math
import secrets
import uuid
import smtplib
import string
from copy import deepcopy
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Wedge
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

APP_TITLE = "Clarté360 - Boussole des valeurs professionnelles"
APP_VERSION = "V1.5-socle-clarte360"
SOCLE_CLARTE360_VERSION = "1.7"
RGPD_TEXT_VERSION = "RGPD-Clarte360-v1.0-2026-07"
BRAND_COLOR = "#008080"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo_clarte360.png"
DOMAINES = ["Travail / expérience professionnelle", "Engagements personnels / vie hors travail"]
FINAL_EMAIL_TO = "contact@clarte360.com"
ENERGY_ACCESS_CODE = "CLAENER360"
BENEFICIARY_TIMEOUT_MINUTES = 15
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

Le fichier JSON constitue le seul support de conservation de votre travail. Il peut contenir votre identité, votre adresse e-mail, le nom de votre accompagnateur si l'application le prévoit, les dates et heures de connexion, la durée des sessions, vos données saisies dans l'application, commentaires, exemples, cotations, résultats, historique des connexions, code d'accès généré, historique des régénérations, consentement RGPD, version de l'application et informations techniques disponibles.

Le fichier JSON appartient exclusivement au bénéficiaire. Vous choisissez librement de le conserver, de le supprimer ou de le transmettre à votre accompagnateur. Si vous le transmettez à votre accompagnateur, celui-ci l'utilise exclusivement dans le cadre du bilan de compétences ou de l'accompagnement Clarté360.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : {RGPD_TEXT_VERSION}.

### Nature des résultats

Les résultats fournis par les applications Clarté360 constituent des supports d'aide à la réflexion et à l'accompagnement. Ils ne constituent ni un diagnostic psychologique, ni un avis médical, ni une décision d'orientation automatique. Leur interprétation s'inscrit dans un dialogue avec le bénéficiaire et, lorsque cela est prévu, avec un professionnel de l'accompagnement.

### Propriété intellectuelle

Les applications, outils, questionnaires, méthodes, graphiques, rapports et contenus proposés par Clarté360 constituent des créations originales protégées. Toute reproduction, adaptation, diffusion ou réutilisation, totale ou partielle, sans autorisation écrite préalable de Clarté360, est interdite.
"""

DEFAULT_COLORS = [
    "#008080", "#F2C94C", "#EB5757", "#2F80ED", "#9B51E0", "#27AE60",
    "#F2994A", "#56CCF2", "#BB6BD9", "#219653", "#F67280", "#6C5CE7",
]

st.set_page_config(page_title=APP_TITLE, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🧭", layout="wide")

st.markdown(
    f"""
    <style>
        .main .block-container {{max-width: 1180px; padding-top: 2rem;}}
        h1, h2, h3 {{color: {BRAND_COLOR} !important;}}
        .brand-header {{margin-bottom: 1.25rem; padding-bottom: 0.75rem; border-bottom: 1px solid #E5E7EB;}}
        .small-note {{color:#6B7280; font-size:0.95rem; margin-top: -0.6rem;}}
        .privacy-box {{background:#F1F8F8; border-left:6px solid {BRAND_COLOR}; padding:16px 18px; border-radius:10px; line-height:1.55;}}
        .rule-box {{background:#F1F8F8; border-left:5px solid {BRAND_COLOR}; padding:16px; border-radius:8px; line-height:1.5;}}
        .warn-box {{background:#FFF7E6; border-left:5px solid #F2C94C; padding:12px; border-radius:8px; line-height:1.5;}}
        div.stButton > button:first-child {{border-radius:10px; border:1px solid {BRAND_COLOR}; color:{BRAND_COLOR}; background:white;}}
        div.stButton > button:first-child:hover {{border-color:{BRAND_COLOR}; color:{BRAND_COLOR}; background:#F1F8F8;}}
        div.stButton > button[kind="primary"] {{background:{BRAND_COLOR} !important; color:white !important; border:1px solid {BRAND_COLOR} !important;}}
        div.stButton > button[kind="primary"] * {{color:white !important;}}
        div.stDownloadButton > button:first-child {{border-radius:10px; border:1px solid {BRAND_COLOR}; color:{BRAND_COLOR}; background:white;}}
        div.stDownloadButton > button:first-child:hover {{border-color:{BRAND_COLOR}; color:{BRAND_COLOR}; background:#F1F8F8;}}
        .energy-box {{background:#F1F8F8; border-left:6px solid {BRAND_COLOR}; padding:16px 18px; border-radius:10px; line-height:1.55;}}
    </style>
    """,
    unsafe_allow_html=True,
)



def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def get_client_network() -> dict:
    """Récupère les informations techniques disponibles côté Streamlit.
    L'adresse IP réelle dépend de l'hébergement et des en-têtes transmis par le proxy.
    """
    headers = {}
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
    return {
        "ip": ip,
        "ip_source": "x-forwarded-for/x-real-ip/cf-connecting-ip" if ip else "non disponible via l'environnement Streamlit",
        "user_agent": h("user-agent"),
        "headers_available": bool(headers),
    }


def ensure_runtime_tracking(data: dict, user_activity: bool = True):
    data.setdefault("version", APP_VERSION)
    data.setdefault("version_application", APP_VERSION)
    data.setdefault("version_socle_clarte360", SOCLE_CLARTE360_VERSION)
    data.setdefault("outil", "boussole_valeurs_pro")
    data.setdefault("nom_outil", "Boussole des valeurs professionnelles")
    data.setdefault("passation_root_id", data.get("passation_id") or str(uuid.uuid4()))
    data.setdefault("access", {})
    access = data["access"]
    access.setdefault("timeout_minutes", BENEFICIARY_TIMEOUT_MINUTES)
    access.setdefault("code_generated", False)
    access.setdefault("code_sent", False)
    access.setdefault("code_sent_at", "")
    access.setdefault("code_regenerated_count", 0)
    access.setdefault("code_verified", False)
    access.setdefault("verified_at", "")
    access.setdefault("timed_out", False)
    access.setdefault("timed_out_at", "")
    access.setdefault("closed_at", "")
    access.setdefault("sessions", [])
    access.setdefault("sauvegardes", [])
    if "active_session_id" not in st.session_state:
        st.session_state.active_session_id = str(uuid.uuid4())
    sid = st.session_state.active_session_id
    network = get_client_network()
    now = now_iso()
    existing = None
    for sess in access["sessions"]:
        if sess.get("session_id") == sid:
            existing = sess
            break
    if existing is None:
        existing = {
            "session_id": sid,
            "motif_ouverture": st.session_state.get("session_open_reason", "premiere_connexion"),
            "started_at": now,
            "validation_code_at": access.get("verified_at", ""),
            "last_activity_at": now,
            "last_seen_at": now,
            "dernier_battement_technique": now,
            "ended_at": "",
            "duration_seconds": 0,
            "active_duration_seconds": 0,
            "app_version": APP_VERSION,
            "socle_version": SOCLE_CLARTE360_VERSION,
            "client_network": network,
            "page_history": [],
            "sauvegardes_associees": [],
        }
        access["sessions"].append(existing)
    else:
        existing["dernier_battement_technique"] = now
        existing["last_seen_at"] = now
        if user_activity:
            existing["last_activity_at"] = now
        if not existing.get("client_network", {}).get("ip") and network.get("ip"):
            existing["client_network"] = network
    start_dt = parse_iso(existing.get("started_at", ""))
    if start_dt:
        existing["duration_seconds"] = int((datetime.now() - start_dt).total_seconds())
    last_activity = parse_iso(existing.get("last_activity_at", "")) or start_dt
    if last_activity:
        existing["active_duration_seconds"] = int((last_activity - start_dt).total_seconds()) if start_dt else existing.get("duration_seconds",0)
    access["temps_total_cumule_secondes"] = total_session_seconds(data)
    access["nombre_sessions"] = len(access.get("sessions", []))


def total_session_seconds(data: dict | None = None) -> int:
    if data is None:
        data = st.session_state.get("data", {})
    return int(sum(int(s.get("duration_seconds", 0) or 0) for s in data.get("access", {}).get("sessions", [])))


def record_save_event(data: dict, motif: str):
    ensure_runtime_tracking(data, user_activity=False)
    access = data.setdefault("access", {})
    event = {"at": now_iso(), "motif": motif, "session_id": st.session_state.get("active_session_id", ""), "app_version": APP_VERSION}
    access.setdefault("sauvegardes", []).append(event)
    for sess in access.get("sessions", []):
        if sess.get("session_id") == event["session_id"]:
            sess.setdefault("sauvegardes_associees", []).append(event)
            break
    data["updated_at"] = now_iso()


def log_page_visit(page_name: str):
    data = st.session_state.get("data")
    if not isinstance(data, dict):
        return
    ensure_runtime_tracking(data, user_activity=True)
    sid = st.session_state.get("active_session_id", "")
    sessions = data.get("access", {}).get("sessions", [])
    for sess in sessions:
        if sess.get("session_id") == sid:
            hist = sess.setdefault("page_history", [])
            if not hist or hist[-1].get("page") != page_name:
                hist.append({"page": page_name, "entered_at": now_iso()})
            else:
                hist[-1]["last_seen_at"] = now_iso()
            break


def mark_current_session_closed(reason: str = ""):
    data = st.session_state.get("data")
    if not isinstance(data, dict):
        return
    access = data.setdefault("access", {})
    sid = st.session_state.get("active_session_id", "")
    for sess in access.get("sessions", []):
        if sess.get("session_id") == sid:
            sess["ended_at"] = now_iso()
            if reason:
                sess["end_reason"] = reason
                sess["motif_fermeture"] = reason
            start = parse_iso(sess.get("started_at", ""))
            if start:
                sess["duration_seconds"] = int((datetime.now() - start).total_seconds())
            break
    access["closed_at"] = access.get("closed_at") or now_iso()
    access["temps_total_cumule_secondes"] = total_session_seconds(data)


def _current_session(data: dict | None = None):
    if data is None:
        data = st.session_state.get("data", {})
    sid = st.session_state.get("active_session_id", "")
    for sess in data.get("access", {}).get("sessions", []):
        if sess.get("session_id") == sid:
            return sess
    return None


def beneficiary_has_timed_out() -> bool:
    """Timeout Socle 1.7 : 15 minutes sans activité réelle, pas 15 minutes de durée totale."""
    data = st.session_state.get("data")
    if not isinstance(data, dict):
        return False
    sess = _current_session(data)
    if not sess:
        return False
    last_activity = parse_iso(sess.get("last_activity_at", "")) or parse_iso(sess.get("started_at", ""))
    if not last_activity:
        return False
    inactive_seconds = int((datetime.now() - last_activity).total_seconds())
    sess["inactivite_secondes"] = inactive_seconds
    return inactive_seconds >= BENEFICIARY_TIMEOUT_MINUTES * 60


def timeout_watchdog():
    """Force une vérification automatique du timeout sans clic utilisateur, comme le socle 1.7."""
    if not st.session_state.get("code_verified") or not isinstance(st.session_state.get("data"), dict):
        return False
    auto_rerun = False
    if st_autorefresh is not None:
        count = st_autorefresh(interval=10000, key="clarte360_boussole_timeout_watchdog")
        previous = st.session_state.get("_watchdog_count")
        st.session_state["_watchdog_count"] = count
        auto_rerun = previous is not None and count != previous
    elif hasattr(st, "fragment"):
        @st.fragment(run_every="10s")
        def _watchdog_fragment():
            if beneficiary_has_timed_out():
                st.rerun()
        _watchdog_fragment()
    else:
        components.html("""<script>setTimeout(function(){try{window.parent.location.reload();}catch(e){window.location.reload();}},10000);</script>""", height=0)
    return auto_rerun


def timeout_screen():
    data = st.session_state.data
    ensure_runtime_tracking(data, user_activity=False)
    access = data.setdefault("access", {})
    access["timed_out"] = True
    access["timed_out_at"] = access.get("timed_out_at") or now_iso()
    mark_current_session_closed("timeout_inactivite")
    record_save_event(data, "timeout_inactivite")
    data["updated_at"] = now_iso()
    base = export_basename(data)
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    header()
    st.error("Votre session est fermée après 15 minutes sans activité.")
    st.markdown("""
        <div class='warn-box'>
        Votre travail a été préparé en sauvegarde JSON. Téléchargez le fichier ci-dessous avant de fermer l'onglet. Une reprise ultérieure créera une nouvelle session et conservera l'historique.
        </div>
        """, unsafe_allow_html=True)
    st.download_button("Télécharger mon JSON de sauvegarde", json_bytes, file_name=f"{base}_timeout_inactivite.json", mime="application/json", type="primary")
    st.caption("Le navigateur peut exiger un clic pour autoriser le téléchargement du fichier.")

def get_email_config() -> dict | None:
    """Lit la configuration SMTP Streamlit Secrets au format déjà utilisé par Clarté360."""
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
        return True, "Email envoyé."
    except Exception as exc:
        return False, f"Erreur d'envoi email : {exc}"


def generate_access_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    # évite les caractères ambigus
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def send_access_code_email(beneficiaire: dict, access_code: str) -> tuple[bool, str]:
    cfg = get_email_config()
    if not cfg:
        return False, "SMTP non configuré : impossible d'envoyer le code d'accès. Configurez les Secrets Streamlit."
    prenom = beneficiaire.get("prenom", "")
    nom = beneficiaire.get("nom", "")
    email = beneficiaire.get("email", "")
    admin_to = cfg.get("to_email", FINAL_EMAIL_TO)

    subject_admin = "Clarté360 - Nouveau code d'accès Boussole des valeurs professionnelles"
    body_admin = (
        "Une personne vient de demander un code d'accès pour réaliser l'outil Clarté360 - Boussole des valeurs professionnelles.\n\n"
        f"Prénom : {prenom}\n"
        f"Nom : {nom}\n"
        f"Email : {email}\n"
        f"Code généré : {access_code}\n"
        f"Date/heure : {datetime.now().isoformat(timespec='seconds')}\n\n"
        "Consentement RGPD : le bénéficiaire a confirmé avoir lu les informations relatives aux données conservées dans le JSON et a consenti à leur utilisation dans le cadre exclusif de son accompagnement.\n"
        "Rappel : aucune donnée n'est conservée sur un serveur Clarté360 ; le JSON reste sous le contrôle du bénéficiaire et, s'il est communiqué à l'accompagnateur, il sert uniquement au travail d'accompagnement.\n"
    )
    ok_admin, msg_admin = send_email(admin_to, subject_admin, body_admin)

    subject_user = "Votre code d'accès Clarté360"
    body_user = (
        f"Bonjour {prenom},\n\n"
        "Voici votre code d'accès pour démarrer l'outil Clarté360 - Boussole des valeurs professionnelles :\n\n"
        f"{access_code}\n\n"
        "Lors de cette demande, vous avez confirmé avoir lu les informations relatives à la protection de vos données et donné votre consentement à leur utilisation dans le cadre exclusif de votre accompagnement.\n\n"
        "Aucune donnée n'est conservée sur un serveur Clarté360. Vos informations sont enregistrées uniquement dans le fichier JSON que vous conservez. Si vous transmettez ce fichier à votre accompagnateur, il sera utilisé uniquement dans le cadre de votre bilan de compétences ou de votre accompagnement professionnel.\n\n"
        "Cordialement,\nClarté360\n"
    )
    ok_user, msg_user = send_email(email, subject_user, body_user)
    if ok_user:
        return True, "Code envoyé au bénéficiaire."
    return False, f"Notification consultant : {msg_admin} / Envoi bénéficiaire : {msg_user}"


def send_final_json_to_consultant(data: dict, json_bytes: bytes, file_name: str) -> tuple[bool, str]:
    cfg = get_email_config()
    destination = cfg.get("to_email", FINAL_EMAIL_TO) if cfg else FINAL_EMAIL_TO
    b = data.get("beneficiaire", {})
    subject = "Clarté360 - JSON final Boussole des valeurs professionnelles"
    body = (
        "Le bénéficiaire a terminé l'outil Clarté360 - Boussole des valeurs professionnelles.\n\n"
        f"Prénom : {b.get('prenom','')}\n"
        f"Nom : {b.get('nom','')}\n"
        f"Email : {b.get('email','')}\n"
        f"Date de réalisation : {b.get('date_realisation','')}\n"
        f"Date/heure d'envoi : {datetime.now().isoformat(timespec='seconds')}\n\n"
        "Le JSON joint permet de reprendre les données et de régénérer les sorties de l'outil.\n"
    )
    return send_email(destination, subject, body, attachment=json_bytes, attachment_name=file_name)


def ensure_access_state():
    for k, v in {
        "access_code": "",
        "code_sent": False,
        "code_verified": False,
        "pending_beneficiaire": None,
        "final_json_sent": False,
        "access_request_events": [],
        "welcome_done": False,
        "new_session_requested": False,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v



def record_import_event(data: dict):
    # Une reprise JSON doit ouvrir une nouvelle session de travail.
    # On ne réutilise pas la session précédente, sinon le timeout peut être
    # calculé à partir d'une ancienne date et bloquer immédiatement l'utilisateur.
    st.session_state.active_session_id = str(uuid.uuid4())
    st.session_state.session_open_reason = "reprise_depuis_json"
    ensure_runtime_tracking(data)
    access = data.setdefault("access", {})
    access.setdefault("import_events", [])
    access["import_events"].append({"event": "json_imported", "at": now_iso(), "client_network": get_client_network(), "app_version": APP_VERSION, "new_session_id": st.session_state.active_session_id})
    data["updated_at"] = now_iso()


def welcome_screen() -> bool:
    """Retourne True quand l'utilisateur a choisi d'importer un JSON ou de démarrer une nouvelle session."""
    if st.session_state.get("welcome_done"):
        return True
    header()
    st.markdown("## Bienvenue")
    st.markdown(
        """
        <div class='privacy-box'>
        <strong>Bonjour, avez-vous une sauvegarde JSON de votre dernière utilisation de l'application<br>
        “Boussole des valeurs professionnelles” ?</strong><br><br>
        Le fichier JSON permet de reprendre votre travail, de conserver les traces de connexion déjà enregistrées
        et d'éviter de demander un nouveau code si un code avait déjà été généré lors de votre précédente utilisation.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Oui, j'ai mon fichier JSON")
        uploaded = st.file_uploader("Importer ma sauvegarde JSON", type=["json"], key="welcome_json_upload")
        if uploaded is not None:
            try:
                loaded = json.loads(uploaded.getvalue().decode("utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError("Format JSON invalide")
                st.session_state.data = loaded
                record_import_event(st.session_state.data)
                # Si un code avait déjà été généré dans ce JSON, on redonne accès directement.
                access = st.session_state.data.setdefault("access", {})
                if access.get("code_generated") or access.get("code_sent") or access.get("code_verified"):
                    st.session_state.code_verified = True
                    access["code_verified"] = True
                    access.setdefault("verified_at", now_iso())
                st.session_state.welcome_done = True
                st.session_state.new_session_requested = False
                st.success("Sauvegarde JSON chargée. Votre session va reprendre.")
                st.rerun()
            except Exception as exc:
                st.error(f"Impossible de lire ce fichier JSON : {exc}")
    with c2:
        st.markdown("### Non, je commence une nouvelle session")
        st.write("Cliquez ici si vous n'avez pas encore de sauvegarde JSON, ou si vous souhaitez repartir de zéro.")
        if st.button("Continuer", type="primary"):
            st.session_state.data = empty_state()
            st.session_state.welcome_done = True
            st.session_state.new_session_requested = True
            st.rerun()
    return False


def rgpd_information_block():
    st.markdown(RGPD_TEXT)


def legal_mentions_block():
    l = CLARTE360_LEGAL
    st.markdown(f"""
    ### {l['raison_sociale']} {l.get('forme', 'SAS')}

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


def contact_form_main():
    st.markdown("""
    ### Contacter Clarté360
    **Vous avez besoin de contacter Clarté360 ?**  
    Vous pouvez nous adresser une question administrative, signaler un problème technique ou nous faire part d'une suggestion d'amélioration concernant cette application.  
    Pour toute question relative à votre bilan de compétences ou à l'interprétation des exercices, nous vous invitons à vous rapprocher de votre consultant ou accompagnateur.  
    Nous vous répondrons par e-mail et, si vous renseignez votre numéro de téléphone, nous pourrons vous rappeler lorsque cela facilitera le traitement de votre demande.
    """)
    data = st.session_state.get("data", {}) if isinstance(st.session_state.get("data"), dict) else {}
    ben = data.get("beneficiaire", {}) if isinstance(data, dict) else {}
    with st.form("contact_clarte360_form_main"):
        c1, c2 = st.columns(2)
        with c1:
            prenom = st.text_input("Prénom *", value=ben.get("prenom", ""))
        with c2:
            nom = st.text_input("Nom *", value=ben.get("nom", ""))
        email = st.text_input("Adresse e-mail *", value=ben.get("email", ""))
        telephone = st.text_input("Téléphone (facultatif, si vous souhaitez pouvoir être rappelé)")
        objet = st.text_input("Objet *", value=f"Demande depuis {APP_TITLE}")
        message = st.text_area("Message *", height=160)
        consent = st.checkbox("J'accepte que Clarté360 utilise les informations transmises uniquement pour traiter ma demande. Si je renseigne un numéro de téléphone, j'accepte de pouvoir être contacté par téléphone lorsque cela est utile pour résoudre ma demande.")
        submitted = st.form_submit_button("📩 Envoyer mon message", type="primary")
    if submitted:
        if not prenom.strip() or not nom.strip() or not email.strip() or "@" not in email or not objet.strip() or not message.strip():
            st.error("Merci de renseigner les champs obligatoires : prénom, nom, e-mail, objet et message.")
            return
        if not consent:
            st.error("Le consentement est nécessaire pour transmettre votre demande à Clarté360.")
            return
        sess = _current_session(data) if isinstance(data, dict) else {}
        support_id = f"SUP-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
        body = f"""Demande envoyée depuis une application Clarté360.

Identifiant support : {support_id}
Application : {APP_TITLE}
Version : {APP_VERSION}
Socle Clarté360 : {SOCLE_CLARTE360_VERSION}
Prénom : {prenom.strip()}
Nom : {nom.strip()}
Email : {email.strip()}
Téléphone : {telephone.strip() or 'non renseigné'}
Objet : {objet.strip()}

Message :
{message.strip()}

Consentement support : accepté.
Date/heure : {now_iso()}
Identifiant session : {st.session_state.get('active_session_id','')}
Temps session : {(sess or {}).get('duration_seconds','')} secondes
Temps cumulé : {total_session_seconds(data) if isinstance(data, dict) else ''} secondes
Client : {get_client_network()}
"""
        ok, info = send_email(FINAL_EMAIL_TO, f"Clarté360 - Support {support_id} - Boussole", body)
        if ok:
            st.success(f"Votre demande a bien été transmise à Clarté360. Référence : {support_id}")
        else:
            st.error("Le message n'a pas pu être envoyé automatiquement.")
            st.caption(info)


def rgpd_page():
    header()
    st.subheader("Informations légales et protection des données")
    tab_rgpd, tab_mentions, tab_contact = st.tabs(["Protection des données", "Mentions légales", "Nous contacter"])
    with tab_rgpd:
        rgpd_information_block()
        st.info("Le consentement RGPD est demandé avant la génération du code d'accès et avant toute nouvelle passation.")
    with tab_mentions:
        legal_mentions_block()
    with tab_contact:
        contact_form_main()


def contact_page():
    header()
    st.subheader("Contacter Clarté360")
    contact_form_main()


def access_gate() -> bool:
    """Retourne True lorsque le code est validé."""
    ensure_access_state()
    if not welcome_screen():
        return False
    if st.session_state.get("code_verified"):
        return True

    header()
    st.markdown("## Accès bénéficiaire")
    st.write("Cet outil n'est pas un test psychométrique. Il sert de support d'exploration et d'échange avec votre consultant Clarté360.")
    rgpd_information_block()
    st.write("")

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
                beneficiaire_tmp = {"prenom": prenom.strip(), "nom": nom.strip(), "email": email.strip(), "consultant": consultant.strip()}
                code = generate_access_code()
                event = {"event": "code_generated", "at": now_iso(), "beneficiaire": beneficiaire_tmp, "client_network": get_client_network(), "rgpd_consent_given": True, "rgpd_consent_at": now_iso(), "rgpd_consent_text_version": RGPD_TEXT_VERSION}
                st.session_state.access_request_events.append(event)
                ok, msg = send_access_code_email(beneficiaire_tmp, code)
                event["email_sent"] = bool(ok)
                event["email_message"] = msg
                st.session_state.pending_beneficiaire = beneficiaire_tmp
                st.session_state.access_code = code
                st.session_state.code_sent = ok
                if ok:
                    st.success("Un code d'accès vient d'être envoyé à l'adresse email indiquée.")
                    st.rerun()
                else:
                    st.error("Le code n'a pas pu être envoyé. Vérifiez la configuration SMTP dans Streamlit Secrets.")
                    st.caption(msg)
                    st.info(f"Mode test : code généré = {code}")
                    st.session_state.code_sent = True
    else:
        b = st.session_state.get("pending_beneficiaire") or {}
        st.success(f"Code généré pour : {b.get('prenom','')} {b.get('nom','')} - {b.get('email','')}")
        code_input = st.text_input("Saisir le code d'accès", max_chars=6, type="password")
        c1, c2 = st.columns([0.18, 0.82])
        with c1:
            if st.button("Entrer dans l'outil", type="primary"):
                if code_input.strip().upper() == str(st.session_state.get("access_code", "")).strip().upper():
                    st.session_state.code_verified = True
                    data = empty_state()
                    data["beneficiaire"].update({
                        "prenom": b.get("prenom", ""),
                        "nom": b.get("nom", ""),
                        "email": b.get("email", ""),
                        "consultant": b.get("consultant", "Clarté360"),
                        "date_realisation": date.today().isoformat(),
                    })
                    consent_event = st.session_state.access_request_events[0] if st.session_state.access_request_events else {}
                    data["rgpd"].update({
                        "consent_given": True,
                        "consent_at": consent_event.get("rgpd_consent_at", now_iso()),
                        "consent_text_version": consent_event.get("rgpd_consent_text_version", RGPD_TEXT_VERSION),
                        "no_server_storage_acknowledged": True,
                        "json_owner_acknowledged": True,
                        "consultant_use_only_acknowledged": True,
                    })
                    data["access"].update({
                        "code_verified": True,
                        "verified_at": now_iso(),
                        "code_generated": True,
                        "code_sent": True,
                        "code_sent_at": st.session_state.access_request_events[-1].get("at", "") if st.session_state.access_request_events else "",
                        "code_regenerated_count": max(0, len(st.session_state.access_request_events) - 1),
                        "code_request_events": st.session_state.access_request_events,
                        "timeout_minutes": BENEFICIARY_TIMEOUT_MINUTES,
                    })
                    # La validation du code ouvre la première vraie session de travail bénéficiaire.
                    st.session_state.active_session_id = str(uuid.uuid4())
                    st.session_state.session_open_reason = "premiere_connexion"
                    ensure_runtime_tracking(data)
                    st.session_state.data = data
                    st.rerun()
                else:
                    st.error("Code incorrect.")
        with c2:
            regen_col, edit_col = st.columns(2)
            with regen_col:
                if st.button("Je n'ai pas reçu le code : générer un nouveau code"):
                    code = generate_access_code()
                    st.session_state.access_code = code
                    event = {"event": "code_regenerated", "at": now_iso(), "beneficiaire": b, "client_network": get_client_network()}
                    st.session_state.access_request_events.append(event)
                    ok, msg = send_access_code_email(b, code)
                    event["email_sent"] = bool(ok)
                    event["email_message"] = msg
                    if ok:
                        st.success("Un nouveau code vient d'être envoyé.")
                    else:
                        st.warning("Le nouveau code n'a pas pu être envoyé par email. Mode test affiché ci-dessous.")
                        st.info(f"Mode test : nouveau code généré = {code}")
            with edit_col:
                if st.button("Modifier les informations"):
                    for k in ["access_code", "code_sent", "code_verified", "pending_beneficiaire", "access_request_events"]:
                        st.session_state.pop(k, None)
                    st.rerun()
    return False


def empty_state():
    return {
        "version": APP_VERSION,
        "version_application": APP_VERSION,
        "version_socle_clarte360": SOCLE_CLARTE360_VERSION,
        "outil": "boussole_valeurs_pro",
        "nom_outil": "Boussole des valeurs professionnelles",
        "passation_root_id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "beneficiaire": {"prenom": "", "nom": "", "email": "", "consultant": "Clarté360", "date_realisation": date.today().isoformat()},
        "rgpd": {
            "consent_given": False,
            "consent_at": "",
            "consent_text_version": RGPD_TEXT_VERSION,
            "no_server_storage_acknowledged": False,
            "json_owner_acknowledged": False,
            "consultant_use_only_acknowledged": False,
        },
        "access": {
            "started_at": now_iso(),
            "code_verified": False,
            "verified_at": "",
            "code_generated": False,
            "code_sent": False,
            "code_sent_at": "",
            "code_regenerated_count": 0,
            "timeout_minutes": BENEFICIARY_TIMEOUT_MINUTES,
            "timed_out": False,
            "timed_out_at": "",
            "closed_at": "",
            "sessions": [],
            "sauvegardes": [],
        },
        "valeurs": [],
        "valeurs_energies": {"access_granted": False, "selected": [], "entries": {}, "created_at": "", "updated_at": ""},
    }


def ensure_state():
    if "data" not in st.session_state:
        st.session_state.data = empty_state()
    ensure_runtime_tracking(st.session_state.data)
    ensure_energy_state()
    if "page" not in st.session_state:
        st.session_state.page = "1. Bénéficiaire"


def ensure_energy_state():
    data = st.session_state.data
    if "valeurs_energies" not in data or not isinstance(data.get("valeurs_energies"), dict):
        data["valeurs_energies"] = {"access_granted": False, "selected": [], "entries": {}, "created_at": "", "updated_at": ""}
    ve = data["valeurs_energies"]
    ve.setdefault("access_granted", False)
    ve.setdefault("selected", [])
    ve.setdefault("entries", {})
    ve.setdefault("created_at", "")
    ve.setdefault("updated_at", "")


def make_empty_value(index: int) -> dict:
    return {
        "nom": f"Valeur {index+1}",
        "definition": "",
        "couleur": DEFAULT_COLORS[index % len(DEFAULT_COLORS)],
        "domaines": [{"domaine": d, "periode": "", "exemple": "", "cote": 0} for d in DOMAINES],
    }


def delete_value_at(index: int):
    values = st.session_state.data.get("valeurs", [])
    if 0 <= index < len(values):
        values.pop(index)
        # Nettoyage des sélections énergie afin d'éviter des indices obsolètes
        ensure_energy_state()
        ve = st.session_state.data["valeurs_energies"]
        new_selected = []
        new_entries = {}
        for old_idx in ve.get("selected", []):
            try:
                old_idx = int(old_idx)
            except Exception:
                continue
            if old_idx == index:
                continue
            new_idx = old_idx - 1 if old_idx > index else old_idx
            new_selected.append(new_idx)
            if str(old_idx) in ve.get("entries", {}):
                new_entries[str(new_idx)] = ve["entries"][str(old_idx)]
        ve["selected"] = new_selected[:3]
        ve["entries"] = new_entries
        update_timestamp()


def appreciation_label(score: float) -> str:
    try:
        score = float(score)
    except Exception:
        score = 0
    if score >= 8:
        return "Très présente"
    if score >= 6:
        return "Présente"
    if score >= 4:
        return "À renforcer"
    return "Faiblement vécue aujourd'hui"


def update_timestamp():
    st.session_state.data["updated_at"] = now_iso()


def header():
    st.markdown("<div class='brand-header'>", unsafe_allow_html=True)
    col_logo, col_title = st.columns([0.16, 0.84])
    with col_logo:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=112)
        else:
            st.error("Logo Clarté360 introuvable : assets/logo_clarte360.png")
    with col_title:
        st.markdown(f"# {APP_TITLE}")
        st.markdown(f"<div class='small-note'>Application {APP_VERSION} - aide neutre à la construction de la boussole des valeurs professionnelles</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def clean_filename(text):
    text = (text or "beneficiaire").strip().replace(" ", "_")
    return "".join(c for c in text if c.isalnum() or c in "_-.")


def export_basename(data, outil="BoussoleValeursPro"):
    """Norme Clarté360 : AAAAMMJJ_HHMMSS_NOM_PRENOM_NomOutil.extension"""
    b = data.get("beneficiaire", {})
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nom = clean_filename((b.get("nom") or "NOM").upper())
    prenom_raw = b.get("prenom") or "PRENOM"
    prenom = clean_filename(prenom_raw[:1].upper() + prenom_raw[1:]) if prenom_raw else "PRENOM"
    return f"{timestamp}_{nom}_{prenom}_{outil}"


def moyenne_valeur(valeur):
    cotes = []
    for domaine in valeur.get("domaines", []):
        try:
            cotes.append(float(domaine.get("cote", 0)))
        except Exception:
            cotes.append(0)
    return round(sum(cotes) / len(cotes), 2) if cotes else 0


def build_rows(data):
    rows = []
    for v in data.get("valeurs", []):
        moy = moyenne_valeur(v)
        for d in v.get("domaines", []):
            rows.append({
                "Prenom": data["beneficiaire"].get("prenom", ""),
                "Nom": data["beneficiaire"].get("nom", ""),
                "Date_realisation": data["beneficiaire"].get("date_realisation", ""),
                "Valeur": v.get("nom", ""),
                "Definition": v.get("definition", ""),
                "Couleur": v.get("couleur", ""),
                "Moyenne_valeur": moy,
                "Point d'appui": d.get("domaine", ""),
                "Periode_ou_date": d.get("periode", ""),
                "Action_ou_reaction": d.get("exemple", ""),
                "Cote": d.get("cote", 0),
            })
    return rows


def create_wheel_figure(data, small=True):
    valeurs = data.get("valeurs", [])
    n = len(valeurs)
    size = 6.8 if small else 8.2
    fig, ax = plt.subplots(figsize=(size, size), subplot_kw={"aspect": "equal"})
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.axis("off")

    title_prenom = data["beneficiaire"].get("prenom", "").strip()
    title_nom = data["beneficiaire"].get("nom", "").strip()
    title_date = data["beneficiaire"].get("date_realisation", "")
    ax.set_title(f"Boussole des valeurs professionnelles - {title_prenom} {title_nom} - {title_date}".strip(), fontsize=13, fontweight="bold", color="#2D3142", pad=14)

    if n == 0:
        ax.text(0, 0, "Aucune valeur renseignée", ha="center", va="center", fontsize=12)
        return fig

    angle_width = 360 / n
    start = 90

    # Cercles de repere
    for r in [0.2, 0.4, 0.6, 0.8, 1.0]:
        circle = plt.Circle((0, 0), r, fill=False, color="#C9CDD2", lw=0.8, alpha=0.65)
        ax.add_artist(circle)
        ax.text(0.02, r, str(int(r * 10)), fontsize=8, color="#555", va="bottom")

    # Rayons de separation
    for i in range(n):
        theta = math.radians(start - i * angle_width)
        ax.plot([0, math.cos(theta)], [0, math.sin(theta)], color="#E5E7EB", lw=1)

    for i, val in enumerate(valeurs):
        theta1 = start - (i + 1) * angle_width
        theta2 = start - i * angle_width
        moy = max(0, min(10, moyenne_valeur(val)))
        radius = moy / 10
        couleur = val.get("couleur") or DEFAULT_COLORS[i % len(DEFAULT_COLORS)]

        # Fond de la part
        ax.add_patch(Wedge((0, 0), 1.0, theta1, theta2, facecolor="#F7F7F7", edgecolor="#444", linewidth=0.7))
        # Remplissage selon moyenne. Si 0, rien n'est colorie.
        if radius > 0:
            ax.add_patch(Wedge((0, 0), radius, theta1, theta2, facecolor=couleur, edgecolor="#444", linewidth=0.4, alpha=0.82))

        mid = math.radians((theta1 + theta2) / 2)
        label_r = 1.08
        x, y = label_r * math.cos(mid), label_r * math.sin(mid)
        rotation = (theta1 + theta2) / 2
        if rotation < -90 or rotation > 90:
            rotation += 180
        label = val.get("nom", "Valeur")
        ax.text(x, y, f"{label}\n{moy:g}/10", ha="center", va="center", fontsize=8.5, rotation=rotation, rotation_mode="anchor")

    plt.tight_layout()
    return fig


def fig_to_png_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=220, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    return buf.getvalue()



def add_clarte360_pdf_footer(fig):
    footer = "Clarté360 - 60 rue François 1er - 75008 Paris - 01 89 48 08 25 - contact@clarte360.com - www.clarte360.com - SIRET 10234983400014"
    try:
        fig.text(0.5, 0.012, footer, ha="center", va="bottom", fontsize=6.5, color="#666666")
    except Exception:
        pass
    return fig

def create_pdf_bytes(data, include_values=True, include_energy=True):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        if include_values:
            fig = create_wheel_figure(data, small=False)
            add_clarte360_pdf_footer(fig)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        rows = build_rows(data)
        if include_values and rows:
            fig2, ax = plt.subplots(figsize=(8.27, 11.69))
            ax.axis("off")
            b = data["beneficiaire"]
            ax.text(0.03, 0.97, "Clarté360 - Boussole des valeurs professionnelles", fontsize=16, fontweight="bold", color=BRAND_COLOR, va="top")
            ax.text(0.03, 0.935, f"Bénéficiaire : {b.get('prenom','')} {b.get('nom','')}", fontsize=11, va="top")
            ax.text(0.03, 0.91, f"Date de réalisation : {b.get('date_realisation','')}", fontsize=11, va="top")
            y = 0.86
            for val in data.get("valeurs", []):
                if y < 0.12:
                    add_clarte360_pdf_footer(fig2)
                    pdf.savefig(fig2, bbox_inches="tight")
                    plt.close(fig2)
                    fig2, ax = plt.subplots(figsize=(8.27, 11.69))
                    ax.axis("off")
                    y = 0.96
                ax.text(0.03, y, f"{val.get('nom','')} - moyenne : {moyenne_valeur(val):g}/10", fontsize=12, fontweight="bold", color=BRAND_COLOR, va="top")
                y -= 0.028
                for d in val.get("domaines", []):
                    txt = f"• {d.get('domaine','')} | cote {d.get('cote',0)}/10 | {d.get('periode','')} | {d.get('exemple','')}"
                    wrapped = []
                    line = ""
                    for word in txt.split():
                        if len(line) + len(word) > 105:
                            wrapped.append(line)
                            line = word
                        else:
                            line = (line + " " + word).strip()
                    if line:
                        wrapped.append(line)
                    for line in wrapped[:4]:
                        ax.text(0.05, y, line, fontsize=8.5, va="top")
                        y -= 0.018
                    y -= 0.006
            add_clarte360_pdf_footer(fig2)
            pdf.savefig(fig2, bbox_inches="tight")
            plt.close(fig2)

        # Page complémentaire Valeurs énergies si l'espace a été activé
        ve = data.get("valeurs_energies", {})
        if include_energy and ve.get("access_granted") and ve.get("selected"):
            fig3, ax3 = plt.subplots(figsize=(8.27, 11.69))
            ax3.axis("off")
            ax3.text(0.03, 0.97, "Clarté360 - Valeurs énergies", fontsize=16, fontweight="bold", color=BRAND_COLOR, va="top")
            ax3.text(0.03, 0.935, "Les valeurs énergie sont les valeurs retenues comme sources principales de mobilisation pour l'objectif ou le projet travaillé.", fontsize=10, va="top", wrap=True)
            y = 0.89
            for raw_idx in ve.get("selected", []):
                try:
                    idx = int(raw_idx)
                except Exception:
                    continue
                if idx < 0 or idx >= len(data.get("valeurs", [])):
                    continue
                val = data["valeurs"][idx]
                entry = ve.get("entries", {}).get(str(idx), {})
                if y < 0.18:
                    add_clarte360_pdf_footer(fig3)
                    pdf.savefig(fig3, bbox_inches="tight")
                    plt.close(fig3)
                    fig3, ax3 = plt.subplots(figsize=(8.27, 11.69))
                    ax3.axis("off")
                    y = 0.96
                ax3.text(0.03, y, f"{val.get('nom','')} - initial : {entry.get('score_initial', moyenne_valeur(val))}/10 - revisité : {entry.get('score_revise', moyenne_valeur(val))}/10", fontsize=12, fontweight="bold", color=BRAND_COLOR, va="top")
                y -= 0.03
                comment = entry.get("commentaire", "")
                if comment:
                    ax3.text(0.05, y, f"Énergie pour le projet : {comment[:190]}", fontsize=9, va="top")
                    y -= 0.035
                items = entry.get("maintien", []) if float(entry.get("score_revise", 0)) >= 10 else entry.get("actions", [])
                label = "Points d'appui à conserver" if float(entry.get("score_revise", 0)) >= 10 else "Actions à mettre en œuvre"
                ax3.text(0.05, y, label, fontsize=9.5, fontweight="bold", va="top")
                y -= 0.022
                for item in [x for x in items if str(x).strip()]:
                    ax3.text(0.07, y, f"• {str(item)[:180]}", fontsize=8.8, va="top")
                    y -= 0.02
                y -= 0.015
            add_clarte360_pdf_footer(fig3)
            pdf.savefig(fig3, bbox_inches="tight")
            plt.close(fig3)
            fig4 = create_energy_wheel_figure(data, small=False)
            add_clarte360_pdf_footer(fig4)
            pdf.savefig(fig4, bbox_inches="tight")
            plt.close(fig4)
        if not include_values and not (ve.get("access_granted") and ve.get("selected")):
            fig_empty, ax_empty = plt.subplots(figsize=(8.27, 11.69))
            ax_empty.axis("off")
            ax_empty.text(0.03, 0.97, "Clarté360 - Valeurs énergies", fontsize=16, fontweight="bold", color=BRAND_COLOR, va="top")
            ax_empty.text(0.03, 0.92, "Aucune valeur énergie n'a été renseignée. Cet espace est optionnel.", fontsize=11, va="top")
            add_clarte360_pdf_footer(fig_empty)
            pdf.savefig(fig_empty, bbox_inches="tight")
            plt.close(fig_empty)
    buf.seek(0)
    return buf.getvalue()


def add_default_values(nb):
    data = st.session_state.data
    current = len(data["valeurs"])
    if nb > current:
        for i in range(current, nb):
            data["valeurs"].append(make_empty_value(i))
    elif nb < current:
        data["valeurs"] = data["valeurs"][:nb]
    update_timestamp()



def legal_information_block():
    legal_mentions_block()


def mark_json_downloaded():
    """Marque le JSON comme téléchargé afin de ne plus déclencher l'alerte navigateur."""
    st.session_state.json_downloaded = True


def install_beforeunload_warning():
    """Alerte navigateur si l'utilisateur tente de quitter sans télécharger son JSON.

    Reprise du comportement du socle Clarté360 Moteurs Professionnels v1.7.0 :
    les navigateurs affichent leur propre dialogue standard, par exemple
    "Quitter le site ? Vos modifications risquent de ne pas être enregistrées.".
    """
    if isinstance(st.session_state.get("data"), dict) and not st.session_state.get("json_downloaded"):
        components.html(
            """
            <script>
            window.parent.onbeforeunload = function (e) {
                const message = "Avant de quitter, utilisez le bouton Clarté360 : Quitter et télécharger mon JSON.";
                e.preventDefault();
                e.returnValue = message;
                return message;
            };
            </script>
            """,
            height=0,
        )

def prepare_sidebar_json(close_session: bool = False, reason: str = "sauvegarde_manuelle_reprise"):
    data = st.session_state.get("data")
    if not isinstance(data, dict):
        return
    if close_session:
        mark_current_session_closed(reason)
    else:
        record_save_event(data, reason)
    base = export_basename(data)
    st.session_state.exit_json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    st.session_state.exit_json_filename = f"{base}.json"
    st.session_state.exit_json_ready = True
    st.session_state.json_downloaded = False


def sidebar():
    st.sidebar.markdown("### Session")
    st.sidebar.markdown("---")
    if isinstance(st.session_state.get("data"), dict):
        st.sidebar.caption("Votre progression est enregistrée dans votre fichier JSON.")
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
                file_name=st.session_state.get("exit_json_filename", "boussole_clarte360.json"),
                mime="application/json",
                use_container_width=True,
                on_click=mark_json_downloaded,
            )
            st.sidebar.caption("Conservez ce JSON : il est nécessaire pour reprendre votre travail et il contient le temps réellement enregistré.")
    st.sidebar.markdown("---")
    if st.sidebar.button("💬 Contacter Clarté360", use_container_width=True):
        st.session_state.show_contact_page = True
        st.session_state.show_rgpd_page = False
        st.rerun()
    if st.sidebar.button("RGPD et mentions légales", use_container_width=True):
        st.session_state.show_rgpd_page = True
        st.session_state.show_contact_page = False
        st.rerun()
    st.sidebar.caption("Clarté360 · contact@clarte360.com")
    st.sidebar.caption(f"App {APP_VERSION} · Socle {SOCLE_CLARTE360_VERSION}")
    if st.sidebar.button("Réinitialiser la session"):
        for key in ["data", "code_verified", "welcome_done", "code_sent", "access_code", "pending_beneficiaire", "show_contact_page", "show_rgpd_page"]:
            st.session_state.pop(key, None)
        st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Navigation")
    pages = ["1. Bénéficiaire", "2. Consignes", "3. Valeurs et points d'appui", "4. Boussole des valeurs professionnelles", "5. Valeurs énergies", "6. Export / Rapports", "7. RGPD"]
    st.session_state.page = st.sidebar.radio("", pages, index=pages.index(st.session_state.page), label_visibility="collapsed")
    uploaded = st.sidebar.file_uploader("Ouvrir un questionnaire JSON", type=["json"])
    if uploaded is not None:
        try:
            loaded = json.loads(uploaded.getvalue().decode("utf-8"))
            st.session_state.data = loaded
            record_import_event(st.session_state.data)
            st.sidebar.success("Questionnaire chargé avec nouvelle session.")
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Impossible de lire ce JSON : {exc}")
    if st.sidebar.button("Nouveau questionnaire vierge"):
        st.session_state.data = empty_state()
        st.session_state.active_session_id = str(uuid.uuid4())
        st.session_state.session_open_reason = "nouvelle_session_volontaire"
        st.session_state.page = "1. Bénéficiaire"
        st.rerun()


def page_beneficiaire():
    st.markdown("## 1. Identification du bénéficiaire")
    st.markdown(
        """
        <div class='privacy-box'>
        🔒 <strong>Confidentialité et maîtrise de vos données</strong><br>
        Aucune donnée personnelle ou sensible saisie dans cette application n'est sauvegardée sur un serveur Clarté360 ni transmise à un tiers.
        Vous restez le seul maître à bord de vos informations. Si votre travail n'est pas terminé et que vous souhaitez le reprendre plus tard,
        vous devez obligatoirement télécharger le fichier <strong>JSON</strong> : c'est le seul fichier qui permet de retrouver et modifier votre questionnaire.
        Cette absence de sauvegarde serveur est volontaire et répond à une logique de protection des données et de respect du RGPD.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    b = st.session_state.data["beneficiaire"]
    c1, c2, c3 = st.columns(3)
    with c1:
        b["prenom"] = st.text_input("Prénom du bénéficiaire", value=b.get("prenom", ""))
    with c2:
        b["nom"] = st.text_input("Nom du bénéficiaire", value=b.get("nom", ""))
    with c3:
        b["email"] = st.text_input("Adresse email", value=b.get("email", ""))
    c4, c5 = st.columns(2)
    with c4:
        b["consultant"] = st.text_input("Consultant", value=b.get("consultant", "Clarté360"))
    with c5:
        current_date = date.fromisoformat(b.get("date_realisation", date.today().isoformat())) if b.get("date_realisation") else date.today()
        b["date_realisation"] = st.date_input("Date de réalisation", value=current_date).isoformat()
    update_timestamp()

    st.markdown("## Nombre de valeurs")
    nb_current = max(1, len(st.session_state.data.get("valeurs", [])) or 8)
    nb = st.number_input("Combien de valeurs souhaitez-vous renseigner ?", min_value=1, max_value=30, value=nb_current, step=1)
    if st.button("Valider / ajuster le nombre de valeurs"):
        add_default_values(int(nb))
        st.success("Nombre de valeurs mis à jour.")
        st.session_state.page = "3. Valeurs et points d'appui"
        st.rerun()


def page_consignes():
    st.markdown("## 2. Consignes")
    st.markdown(
        """
        <div class='rule-box'>
        Cette boussole n'a pas pour objectif de suggérer des valeurs ou d'interpréter le profil de la personne. Elle aide uniquement à vérifier dans quelle mesure les valeurs déjà identifiées sont réellement incarnées dans les deux points d'appui.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown("### Définition d'une valeur")
    st.write("Une valeur est un principe profond qui donne du sens à vos choix, à vos comportements et à vos réactions. Elle ne se déclare pas seulement : elle se reconnaît à travers des situations concrètes vécues.")
    st.markdown("### Cotation")
    st.write("La cotation indique dans quelle mesure cette valeur est réellement vécue dans les deux points d'appui proposés. Plus les exemples sont précis, datés, répétés et significatifs, plus la cotation peut être élevée. Sans exemple concret, la cotation doit rester faible.")
    st.markdown("### Durée de session")
    st.markdown(
        f"""
        <div class='warn-box'>
        La session bénéficiaire est limitée à <strong>{BENEFICIARY_TIMEOUT_MINUTES} minutes</strong>. À l'issue de ce délai, l'écran se verrouille et le fichier JSON de session doit être téléchargé. Ce fichier permet de conserver les réponses et de tracer le temps passé dans le cadre de l'accompagnement.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### Règle centrale")
    st.write("Pour chaque valeur, le bénéficiaire doit décrire une action ou une réaction concrète, précise et située dans le temps dans chacun des deux points d'appui : vie professionnelle et engagements personnels / vie hors travail.")
    st.markdown(
        """
        #### Exemples recevables, rattachés à une valeur

        **Valeur : Honnêteté**
        - Vie professionnelle : « En février 2026, j'ai refusé de valider un document car je n'avais pas encore vérifié les chiffres demandés. »
        - Engagements personnels / vie hors travail : « La semaine dernière, la boulangère m'a rendu trop de monnaie ; je lui ai signalé l'erreur immédiatement. »

        **Valeur : Entraide**
        - Vie professionnelle : « Mardi dernier, j'ai terminé la préparation d'une salle à la place d'une collègue qui devait partir en urgence. »
        - Engagements personnels / vie hors travail : « Le week-end dernier, j'ai aidé un voisin âgé à porter ses courses jusqu'à son appartement. »

        **Valeur : Rigueur**
        - Vie professionnelle : « En mars 2026, j'ai repris mon contrôle de matériel ligne par ligne parce qu'il manquait une signature sur la fiche de suivi. »
        - Engagements personnels / vie hors travail : « Avant mon départ en vacances, j'ai préparé une liste précise des papiers, clés et médicaments pour éviter les oublis. »

        **Valeur : Liberté**
        - Vie professionnelle : « En avril 2026, j'ai demandé à organiser différemment ma tournée afin de travailler plus efficacement. »
        - Engagements personnels / vie hors travail : « Le mois dernier, j'ai choisi seul une activité du dimanche pour prendre un vrai temps à moi. »

        #### Exemples trop généraux
        - « Je suis quelqu'un d'honnête. »
        - « J'aime aider les autres. »
        - « La rigueur est importante pour moi. »
        - « J'aime être libre. »
        - « La famille compte beaucoup pour moi. »
        """
    )
    st.markdown("<div class='warn-box'>Si aucune action ou réaction concrète n'est identifiable dans un point d'appui, la valeur peut rester importante pour la personne, mais elle n'est pas réellement mise en œuvre dans ce contexte. La cote doit alors être faible, possiblement égale à 0.</div>", unsafe_allow_html=True)

def page_valeurs():
    st.markdown("## 3. Valeurs et points d'appui")
    st.write("Pour chaque valeur, renseignez les 2 points d'appui. Le programme ne suggère aucune valeur et ne réalise aucune interprétation.")
    if not st.session_state.data.get("valeurs"):
        st.info("Commencez par indiquer le nombre de valeurs dans la page 1, ou ajoutez directement une première valeur ci-dessous.")

    cadd, cinfo = st.columns([0.22, 0.78])
    with cadd:
        if st.button("+ Ajouter une valeur", type="primary"):
            st.session_state.data["valeurs"].append(make_empty_value(len(st.session_state.data.get("valeurs", []))))
            update_timestamp()
            st.rerun()
    with cinfo:
        st.caption("Vous pouvez ajouter ou supprimer une valeur directement ici, sans revenir à l'identification du bénéficiaire.")

    values = st.session_state.data.get("valeurs", [])
    for idx, val in enumerate(list(values)):
        titre = val.get('nom','') or f"Valeur {idx+1}"
        with st.expander(f"Valeur {idx+1} : {titre}", expanded=idx == 0):
            top1, top2 = st.columns([0.82, 0.18])
            with top2:
                if st.button("Supprimer cette valeur", key=f"delete_value_{idx}"):
                    st.session_state[f"confirm_delete_{idx}"] = True
            if st.session_state.get(f"confirm_delete_{idx}"):
                st.warning(f"Confirmer la suppression de la valeur : {titre} ?")
                cyes, cno = st.columns(2)
                with cyes:
                    if st.button("Oui, supprimer", key=f"delete_yes_{idx}"):
                        delete_value_at(idx)
                        st.session_state.pop(f"confirm_delete_{idx}", None)
                        st.rerun()
                with cno:
                    if st.button("Annuler", key=f"delete_no_{idx}"):
                        st.session_state.pop(f"confirm_delete_{idx}", None)
                        st.rerun()

            c1, c2, c3 = st.columns([0.55, 0.18, 0.27])
            with c1:
                val["nom"] = st.text_input("Nom de la valeur", value=val.get("nom", ""), key=f"nom_{idx}")
                val["definition"] = st.text_area("Définition personnelle de cette valeur (facultatif)", value=val.get("definition", ""), key=f"def_{idx}", height=80)
            with c2:
                val["couleur"] = st.color_picker("Couleur", value=val.get("couleur", DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]), key=f"col_{idx}")
            with c3:
                st.metric("Moyenne actuelle", f"{moyenne_valeur(val):g}/10")
                st.caption(appreciation_label(moyenne_valeur(val)))

            st.markdown("---")
            for d_idx, dom in enumerate(val.get("domaines", [])):
                st.markdown(f"### {dom.get('domaine', DOMAINES[d_idx])}")
                dom["domaine"] = dom.get("domaine", DOMAINES[d_idx])
                cdate, cscore = st.columns([0.65, 0.35])
                with cdate:
                    dom["periode"] = st.text_input("Date ou période précise", value=dom.get("periode", ""), key=f"periode_{idx}_{d_idx}", placeholder="Ex. 15 février 2026, mars 2026, la semaine dernière...")
                with cscore:
                    exemple_ok = bool(dom.get("exemple", "").strip()) and bool(dom.get("periode", "").strip())
                    max_score = 10 if exemple_ok else 2
                    current_cote = int(min(max(float(dom.get("cote", 0)), 0), max_score))
                    dom["cote"] = st.slider("Cote", min_value=0, max_value=max_score, value=current_cote, step=1, key=f"cote_{idx}_{d_idx}")
                dom["exemple"] = st.text_area(
                    "Action ou réaction concrète, précise et située dans le temps",
                    value=dom.get("exemple", ""),
                    key=f"ex_{idx}_{d_idx}",
                    height=95,
                    placeholder="Décrivez ce que vous avez fait, refusé, protégé, exprimé ou la manière dont vous avez réagi dans une situation réelle.",
                )
                if not dom.get("exemple", "").strip() or not dom.get("periode", "").strip():
                    st.caption("Sans action/réaction concrète ET date/période identifiable, la cote maximale est limitée à 2/10.")
                st.write("")
    update_timestamp()

def page_roue():
    st.markdown("## 4. Boussole des valeurs professionnelles")
    st.write("Cette étape permet de visualiser la roue principale. Les exports ci-dessous concernent uniquement la boussole des valeurs professionnelles, sans l'espace complémentaire Valeurs énergies.")
    fig = create_wheel_figure(st.session_state.data, small=True)
    st.pyplot(fig, use_container_width=False)
    png_bytes = fig_to_png_bytes(fig)
    plt.close(fig)
    data = st.session_state.data
    base = export_basename(data)
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    rows = build_rows(data)
    csv_buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(csv_buf, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    st.markdown("### Export / Import de la boussole des valeurs professionnelles")
    st.info("Vous pouvez télécharger ici le rapport complet de la roue principale, le JSON modifiable et les fichiers utiles. Le travail sur les Valeurs énergies reste optionnel et produit ses propres sorties uniquement s'il est activé.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("Télécharger le JSON modifiable", json_bytes, file_name=f"{base}.json", mime="application/json")
    with c2:
        st.download_button("Télécharger le rapport Boussole des valeurs professionnelles", data=create_pdf_bytes(data, include_values=True, include_energy=False), file_name=f"{base}_boussole_valeurs_professionnelles.pdf", mime="application/pdf")
    with c3:
        st.download_button("Télécharger la roue en PNG", data=png_bytes, file_name=f"{base}_boussole_valeurs_professionnelles.png", mime="image/png")
    c4, c5 = st.columns(2)
    with c4:
        st.download_button("Télécharger le CSV", csv_buf.getvalue().encode("utf-8-sig"), file_name=f"{base}.csv", mime="text/csv")
    with c5:
        st.caption("L'import d'un JSON se fait depuis la barre latérale gauche : Ouvrir un questionnaire JSON.")



def create_energy_wheel_figure(data, small=True):
    ensure_energy_state()
    selected = data.get("valeurs_energies", {}).get("selected", [])
    entries = data.get("valeurs_energies", {}).get("entries", {})
    source_values = data.get("valeurs", [])
    energy_values = []
    for idx in selected:
        try:
            idx = int(idx)
        except Exception:
            continue
        if 0 <= idx < len(source_values):
            val = deepcopy(source_values[idx])
            entry = entries.get(str(idx), {})
            val["nom"] = val.get("nom", f"Valeur {idx+1}")
            val["domaines"] = [{"domaine": "Valeur énergie", "periode": "", "exemple": "", "cote": float(entry.get("score_revise", moyenne_valeur(source_values[idx])))}]
            energy_values.append(val)
    tmp = deepcopy(data)
    tmp["valeurs"] = energy_values
    fig = create_wheel_figure(tmp, small=small)
    fig.axes[0].set_title("Boussole des valeurs professionnelles énergie", fontsize=13, fontweight="bold", color="#2D3142", pad=14)
    return fig


def page_valeurs_energies():
    ensure_energy_state()
    data = st.session_state.data
    ve = data["valeurs_energies"]
    st.markdown("## 5. Valeurs énergies")
    st.markdown(
        """
        <div class='energy-box'>
        <strong>Finalité du travail</strong><br>
        Cette étape permet d'identifier les trois valeurs qui peuvent devenir les principales sources d'énergie pour atteindre un objectif ou réussir un projet. Il ne s'agit pas forcément des trois valeurs les mieux cotées : il s'agit des valeurs les plus porteuses, motivantes et mobilisatrices pour la personne.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    if not ve.get("access_granted"):
        st.info("Cet espace complémentaire est activé uniquement lorsque le consultant le propose dans le cadre de l'accompagnement.")
        code = st.text_input("Code consultant", type="password")
        if st.button("Déverrouiller l'espace Valeurs énergies", type="primary"):
            if code == ENERGY_ACCESS_CODE:
                ve["access_granted"] = True
                ve["created_at"] = ve.get("created_at") or datetime.now().isoformat(timespec="seconds")
                ve["updated_at"] = datetime.now().isoformat(timespec="seconds")
                update_timestamp()
                st.success("Espace Valeurs énergies activé.")
                st.rerun()
            else:
                st.error("Code non valide.")
        return

    values = data.get("valeurs", [])
    if not values:
        st.warning("Aucune valeur n'est encore renseignée dans l'onglet Valeurs et points d'appui.")
        return

    st.markdown("### Sélection des valeurs énergie")
    st.write("Choisissez jusqu'à trois valeurs qui seront les plus porteuses pour l'objectif ou le projet travaillé.")
    options = list(range(len(values)))
    def fmt(i):
        return f"{values[i].get('nom', f'Valeur {i+1}')} — moyenne actuelle {moyenne_valeur(values[i]):g}/10"
    current = [int(i) for i in ve.get("selected", []) if str(i).isdigit() and int(i) < len(values)]
    selected = st.multiselect("Valeurs énergie retenues", options=options, default=current[:3], format_func=fmt, max_selections=3)
    ve["selected"] = selected
    ve.setdefault("entries", {})
    for idx in selected:
        key = str(idx)
        ve["entries"].setdefault(key, {"score_initial": moyenne_valeur(values[idx]), "score_revise": moyenne_valeur(values[idx]), "actions": ["", "", "", "", ""], "maintien": ["", "", "", "", ""], "commentaire": ""})

    st.markdown("---")
    for idx in selected:
        val = values[idx]
        key = str(idx)
        entry = ve["entries"][key]
        st.markdown(f"### {val.get('nom', f'Valeur {idx+1}')}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Cotation initiale", f"{moyenne_valeur(val):g}/10")
        with c2:
            entry["score_revise"] = st.slider("Cotation revisitée", 0, 10, int(round(float(entry.get("score_revise", moyenne_valeur(val))))), key=f"energy_score_{idx}")
        with c3:
            st.metric("Écart", f"{float(entry['score_revise']) - moyenne_valeur(val):+g}")
        entry["score_initial"] = moyenne_valeur(val)
        entry["commentaire"] = st.text_area("Ce qui rend cette valeur porteuse d'énergie pour le projet", value=entry.get("commentaire", ""), key=f"energy_comment_{idx}", height=80)

        if float(entry.get("score_revise", 0)) < 10:
            st.write("Définissez 3 à 5 actions concrètes et rapides pour vivre davantage cette valeur. L'objectif est de transformer la valeur en comportements observables.")
            actions = entry.get("actions", ["", "", "", "", ""])
            while len(actions) < 5:
                actions.append("")
            for a in range(5):
                actions[a] = st.text_input(f"Action concrète {a+1}", value=actions[a], key=f"energy_action_{idx}_{a}")
            entry["actions"] = actions
        else:
            st.write("Cette valeur est ressentie à 10/10. Indiquez les comportements déjà présents qui permettent de la maintenir dans la durée.")
            maintien = entry.get("maintien", ["", "", "", "", ""])
            while len(maintien) < 5:
                maintien.append("")
            for a in range(5):
                maintien[a] = st.text_input(f"Point d'appui à conserver {a+1}", value=maintien[a], key=f"energy_maintien_{idx}_{a}")
            entry["maintien"] = maintien
        st.write("")

    # Retire les entrées de valeurs non sélectionnées, sans effacer si l'utilisateur revient plus tard via JSON tant que l'onglet reste actif.
    ve["updated_at"] = datetime.now().isoformat(timespec="seconds")
    update_timestamp()

    if selected:
        st.markdown("### Seconde roue : valeurs énergies")
        fig = create_energy_wheel_figure(data, small=True)
        st.pyplot(fig, use_container_width=False)
        plt.close(fig)

def page_export():
    st.markdown("## 6. Export / Rapports")
    data = st.session_state.data
    base = export_basename(data)
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    rows = build_rows(data)
    csv_buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(csv_buf, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    st.markdown("### Exports principaux")
    st.info("La boussole des valeurs professionnelles peut être utilisée seule. Les Valeurs énergies sont un travail complémentaire optionnel : certaines personnes ne l'utiliseront pas, et c'est normal.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("JSON modifiable complet", json_bytes, file_name=f"{base}.json", mime="application/json")
    with c2:
        st.download_button("CSV boussole des valeurs professionnelles", csv_buf.getvalue().encode("utf-8-sig"), file_name=f"{base}.csv", mime="text/csv")
    with c3:
        fig = create_wheel_figure(data, small=True)
        st.download_button("PNG boussole des valeurs professionnelles", fig_to_png_bytes(fig), file_name=f"{base}_boussole_valeurs_professionnelles.png", mime="image/png")
        plt.close(fig)

    st.markdown("### Rapports PDF")
    r1, r2, r3 = st.columns(3)
    with r1:
        st.download_button("Rapport Boussole des valeurs professionnelles", create_pdf_bytes(data, include_values=True, include_energy=False), file_name=f"{base}_boussole_valeurs_professionnelles.pdf", mime="application/pdf")
    with r2:
        ve = data.get("valeurs_energies", {})
        if ve.get("access_granted") and ve.get("selected"):
            st.download_button("Rapport Valeurs énergies", create_pdf_bytes(data, include_values=False, include_energy=True), file_name=f"{base}_rapport_valeurs_energies.pdf", mime="application/pdf")
        else:
            st.caption("Rapport Valeurs énergies disponible uniquement si l'onglet optionnel a été activé et renseigné.")
    with r3:
        st.download_button("Rapport complet", create_pdf_bytes(data, include_values=True, include_energy=True), file_name=f"{base}_rapport_complet.pdf", mime="application/pdf")

    st.markdown("### Transmission au consultant")
    st.info("En cliquant sur le bouton ci-dessous, le fichier JSON complet est transmis à votre consultant Clarté360 afin de préparer l’analyse et la restitution. Vous conservez également la possibilité de télécharger votre propre JSON.")
    if st.button("Transmettre le JSON au consultant", type="primary"):
        ok, msg = send_final_json_to_consultant(data, json_bytes, f"{base}.json")
        if ok:
            st.session_state.final_json_sent = True
            st.success("JSON transmis au consultant Clarté360.")
        else:
            st.error("La transmission automatique n’a pas pu être effectuée.")
            st.caption(msg)

    if rows:
        st.markdown("### Aperçu des données de la boussole principale")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)



def page_traceability_rgpd():
    st.markdown("## 7. RGPD et traçabilité")
    rgpd_information_block()
    legal_information_block()
    data = st.session_state.data
    rgpd = data.get("rgpd", {})
    st.markdown("### Consentement enregistré dans le JSON")
    if rgpd.get("consent_given"):
        st.success(f"Consentement donné le : {rgpd.get('consent_at','')}")
    else:
        st.warning("Aucun consentement RGPD n'est enregistré dans ce JSON.")
    st.markdown("### Traçabilité enregistrée")
    st.write("Le JSON conserve notamment les générations de code, les reprises de session, les pages consultées et les durées de connexion. Ces informations servent à documenter l'utilisation de l'outil dans le cadre de l'accompagnement.")
    sessions = data.get("access", {}).get("sessions", [])
    if sessions:
        rows = []
        for s in sessions:
            rows.append({
                "Début": s.get("started_at", ""),
                "Dernière activité": s.get("last_seen_at", ""),
                "Fin": s.get("ended_at", ""),
                "Durée (min)": round(float(s.get("duration_seconds", 0))/60, 2),
                "IP": s.get("client_network", {}).get("ip", ""),
                "Fin raison": s.get("end_reason", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucune session n'est encore enregistrée.")

def main():
    ensure_state()
    ensure_access_state()
    if not access_gate():
        return
    auto_rerun = timeout_watchdog()
    ensure_runtime_tracking(st.session_state.data, user_activity=not auto_rerun)
    install_beforeunload_warning()
    if beneficiary_has_timed_out():
        timeout_screen()
        return
    sidebar()
    if st.session_state.get("show_contact_page"):
        contact_page()
        if st.button("Retour à l'application"):
            st.session_state.show_contact_page = False
            st.rerun()
        return
    if st.session_state.get("show_rgpd_page"):
        rgpd_page()
        if st.button("Retour à l'application"):
            st.session_state.show_rgpd_page = False
            st.rerun()
        return
    log_page_visit(st.session_state.page)
    header()
    if st.session_state.page.startswith("1"):
        page_beneficiaire()
    elif st.session_state.page.startswith("2"):
        page_consignes()
    elif st.session_state.page.startswith("3"):
        page_valeurs()
    elif st.session_state.page.startswith("4"):
        page_roue()
    elif st.session_state.page.startswith("5"):
        page_valeurs_energies()
    elif st.session_state.page.startswith("6"):
        page_export()
    else:
        page_traceability_rgpd()



if __name__ == "__main__":
    main()
