import json, secrets, smtplib, socket, platform, html
from copy import deepcopy
from datetime import datetime, date, timedelta
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

APP_TITLE = "Clarté360 — Boucle auto-validante"
APP_VERSION = "2.0.4-socle-clarte360"
SOCLE_CLARTE360_VERSION = "3.0"
RGPD_TEXT_VERSION = "RGPD-Clarte360-v1.0-2026-07"
BRAND_COLOR = "#008b8b"
ACCENT = "#e7f5f4"
WARN = "#fff4e6"
ADMIN_EMAIL = "contact@clarte360.com"
BENEFICIARY_TIMEOUT_MINUTES = 15
ACCESS_CODE_VALIDITY_MINUTES = 15
LOGO_PATH = Path(__file__).parent / "assets" / "logo_clarte360.png"

CLARTE_LEGAL = """Clarté360\n60 rue François 1er\n75008 Paris\nTél. : 01 89 48 08 25\nE-mail : contact@clarte360.com\nWeb : www.clarte360.com\nRCS : 102349834\nSIRET : 10234983400014\nNAF : 8559A\nTVA intracommunautaire : FR88102349834"""

RGPD_TEXT = f"""
### Protection des données personnelles (RGPD)

Cette application Clarté360 fonctionne sans base de données serveur propre à l'application. Aucune donnée n'est enregistrée durablement sur un serveur Clarté360 par l'application.

Le fichier JSON constitue le seul support de conservation de votre travail. Il peut contenir votre identité, votre adresse e-mail, le nom de votre accompagnateur, les dates et heures de connexion, la durée des sessions, vos données saisies dans l'application, commentaires, résultats, historique des connexions, code d'accès généré, consentement RGPD, version de l'application et informations techniques disponibles.

Le fichier JSON appartient exclusivement au bénéficiaire. Vous choisissez librement de le conserver, de le supprimer ou de le transmettre à votre accompagnateur.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : {RGPD_TEXT_VERSION}.

Les résultats fournis par les applications Clarté360 constituent des supports d'aide à la réflexion et à l'accompagnement. Ils ne constituent ni un diagnostic psychologique, ni un avis médical, ni une décision d'orientation automatique.

Les applications, outils, questionnaires, méthodes, graphiques, rapports et contenus proposés par Clarté360 constituent des créations originales protégées. Toute reproduction, adaptation, diffusion ou réutilisation sans autorisation écrite préalable est interdite.
"""

TYPE_CROYANCE = ["Sur soi / identité", "Sur les autres en général", "Sur le monde", "A vérifier"]
STATUTS = ["Découverte", "Validée", "A travailler en phase 6", "Travaillée", "Archivée"]

st.set_page_config(page_title=APP_TITLE, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🔁", layout="wide")

st.markdown(f"""
<style>
.main .block-container{{max-width:1180px;padding-top:1.6rem}}
h1,h2,h3{{color:{BRAND_COLOR}!important}}
.main-title{{color:{BRAND_COLOR};font-weight:800}}.brand-box{{background:{ACCENT};border-left:6px solid {BRAND_COLOR};padding:1rem;border-radius:12px;margin:.6rem 0}}.warn-box{{background:{WARN};border-left:6px solid #f0a000;padding:1rem;border-radius:12px;margin:.6rem 0}}.mini-note{{font-size:.9rem;color:#555}}.danger{{color:#b00020;font-weight:700}}
div.stButton>button[kind="primary"],div.stDownloadButton>button[kind="primary"]{{background-color:{BRAND_COLOR}!important;border-color:{BRAND_COLOR}!important;color:white!important}}
div.stButton>button:hover,div.stDownloadButton>button:hover{{border-color:#006f6f!important;color:white!important}}
.stTabs [aria-selected="true"]{{color:{BRAND_COLOR}!important;border-bottom-color:{BRAND_COLOR}!important}}
.loop-wrap{{position:relative;width:100%;max-width:920px;height:560px;margin:1rem auto 1.5rem auto}}.loop-svg{{position:absolute;inset:0;width:100%;height:100%;z-index:1}}.loop-node{{position:absolute;z-index:2;width:250px;min-height:105px;background:#fff;border:3px solid {BRAND_COLOR};border-radius:18px;padding:14px;box-shadow:0 4px 14px rgba(0,0,0,.08)}}.loop-node-top{{left:50%;top:12px;transform:translateX(-50%)}}.loop-node-right{{right:5px;top:205px}}.loop-node-bottom{{left:50%;bottom:15px;transform:translateX(-50%)}}.loop-node-left{{left:5px;top:205px}}.loop-node-title{{font-size:.78rem;color:{BRAND_COLOR};font-weight:800;text-transform:uppercase;letter-spacing:.03em;margin-bottom:8px}}.loop-node-text{{font-size:1rem;line-height:1.25;color:#1f2937;white-space:pre-wrap}}.loop-node-empty{{color:#6b7280;font-style:italic}}.loop-center{{position:absolute;z-index:2;left:50%;top:49%;transform:translate(-50%,-50%);background:{ACCENT};border:2px dashed {BRAND_COLOR};color:#006f6f;border-radius:999px;padding:10px 18px;font-weight:700;text-align:center}}
</style>""", unsafe_allow_html=True)

def now_iso(): return datetime.now().isoformat(timespec="seconds")
def make_id(prefix): return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(3)}"
def safe_name(prefix, ext): return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
def esc(x): return html.escape(str(x or ""))
def get_client_network(): return {"hostname": socket.gethostname(), "platform": platform.platform(), "python": platform.python_version()}

def empty_data():
    return {"outil":"boucle_auto_validante","nom_outil":APP_TITLE,"version":APP_VERSION,"version_application":APP_VERSION,"socle_clarte360_version":SOCLE_CLARTE360_VERSION,"root_passation_id":make_id("pass"),"active_session_id":"","created_at":now_iso(),"updated_at":now_iso(),"beneficiaire":{"nom":"","prenom":"","email":"","telephone":""},"consultant":"","progression":{"current_tab":"Phase 3 — Découverte"},"croyances":[],"rgpd":{"consent_given":False,"consent_at":"","consent_text_version":RGPD_TEXT_VERSION},"access":{"code_access":"","code_generated_at":"","code_history":[],"admin_notifications":[],"sessions":[],"save_events":[],"timeout_minutes":BENEFICIARY_TIMEOUT_MINUTES},"technical":{"client_network":get_client_network()},"reports":[]}

def normalize_data(d):
    base = empty_data()
    if not isinstance(d, dict): return base
    # reprise des anciens JSON accompagnateur
    if "beneficiaires" in d:
        bens = d.get("beneficiaires") or []
        b = bens[0] if bens else {}
        base["beneficiaire"] = {"nom":b.get("nom",""),"prenom":b.get("prenom",""),"email":b.get("email",""),"telephone":b.get("telephone","")}
        base["croyances"] = b.get("croyances", [])
        base["created_at"] = d.get("created_at", base["created_at"])
        base["updated_at"] = now_iso()
        return base
    for k,v in d.items(): base[k]=v
    base.setdefault("beneficiaire", {"nom":"","prenom":"","email":"","telephone":""})
    base.setdefault("croyances", [])
    base.setdefault("rgpd", {"consent_given":False,"consent_at":"","consent_text_version":RGPD_TEXT_VERSION})
    base.setdefault("access", {})
    for k,v in empty_data()["access"].items(): base["access"].setdefault(k,v)
    base.setdefault("technical", {"client_network":get_client_network()})
    return base

def init_state():
    st.session_state.setdefault("data", empty_data())
    st.session_state.setdefault("screen", "home")
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("pending_code", "")
    st.session_state.setdefault("code_sent", False)
    st.session_state.setdefault("code_expires_at", None)
    st.session_state.setdefault("selected_croyance_id", None)
    st.session_state.setdefault("nav_back", "app")
    st.session_state.setdefault("home_choice", None)
    st.session_state.setdefault("timed_out", False)
    st.session_state.setdefault("last_activity", datetime.now().timestamp())
    if not st.session_state.data.get("active_session_id"):
        st.session_state.data["active_session_id"] = make_id("sess")
        st.session_state.data["access"]["sessions"].append({"session_id":st.session_state.data["active_session_id"],"started_at":now_iso(),"status":"active"})

def touch():
    st.session_state.data["updated_at"] = now_iso(); st.session_state.last_activity = datetime.now().timestamp()

def json_bytes():
    touch(); return json.dumps(st.session_state.data, ensure_ascii=False, indent=2).encode("utf-8")

def get_email_config():
    """Lit la configuration SMTP Streamlit Secrets au format validé par les apps de référence : [email]."""
    try:
        cfg = st.secrets.get("email", {})
        required = ["smtp_server", "smtp_port", "smtp_user", "smtp_password", "from_email", "to_email"]
        if all(k in cfg and str(cfg[k]).strip() for k in required):
            return {k: str(cfg[k]).strip() for k in required}
    except Exception:
        pass
    # Compatibilité avec d'anciens secrets éventuels [smtp]
    try:
        cfg = st.secrets.get("smtp", {})
        mapping = {
            "smtp_server": cfg.get("server"),
            "smtp_port": cfg.get("port", 587),
            "smtp_user": cfg.get("username"),
            "smtp_password": cfg.get("password"),
            "from_email": cfg.get("from_email", cfg.get("username", ADMIN_EMAIL)),
            "to_email": cfg.get("to_email", ADMIN_EMAIL),
        }
        if all(str(v or "").strip() for v in mapping.values()):
            return {k: str(v).strip() for k, v in mapping.items()}
    except Exception:
        pass
    return None

def send_mail(to, subject, body):
    cfg = get_email_config()
    if not cfg:
        return False, "SMTP non configuré. Aucun email n'a été envoyé."
    try:
        msg = EmailMessage()
        msg["From"] = cfg["from_email"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        port = int(cfg["smtp_port"])
        if port == 465:
            with smtplib.SMTP_SSL(cfg["smtp_server"], port, timeout=20) as smtp:
                smtp.login(cfg["smtp_user"], cfg["smtp_password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg["smtp_server"], port, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(cfg["smtp_user"], cfg["smtp_password"])
                smtp.send_message(msg)
        return True, "Email envoyé."
    except Exception as e:
        return False, f"Erreur d'envoi email : {e}"

def send_code(email):
    code = f"{secrets.randbelow(1000000):06d}"
    st.session_state.pending_code = code
    expires_at = datetime.now() + timedelta(minutes=ACCESS_CODE_VALIDITY_MINUTES)
    ok, msg = send_mail(email, f"Votre code d'accès Clarté360", f"Voici votre code d'accès pour démarrer l'outil Clarté360 - Boucle auto-validante :\n\n{code}\n\nCe code est valable {ACCESS_CODE_VALIDITY_MINUTES} minutes.\n\nConservez votre JSON : il reste votre sauvegarde principale.")
    if ok:
        ev={"event":"code_generated","at":now_iso(),"email":email,"expires_at":expires_at.isoformat(timespec="seconds"),"status":"sent","smtp_message":msg}
        st.session_state.data["access"]["code_access"] = code
        st.session_state.data["access"]["code_generated_at"] = ev["at"]
        st.session_state.data["access"]["code_expires_at"] = ev["expires_at"]
        st.session_state.data["access"]["code_history"].append(ev)
        st.session_state.code_sent = True
        st.session_state.code_expires_at = ev["expires_at"]
    return ok, msg

def notify_admin(first=False):
    b=st.session_state.data.get("beneficiaire",{})
    body=f"Création/accès dossier Clarté360\nApplication: {APP_TITLE}\nVersion: {APP_VERSION}\nSocle: {SOCLE_CLARTE360_VERSION}\nNom: {b.get('nom')}\nPrénom: {b.get('prenom')}\nEmail: {b.get('email')}\nDate: {now_iso()}\nSession: {st.session_state.data.get('active_session_id')}\nPremière création: {first}"
    ok,msg=send_mail(ADMIN_EMAIL, f"Clarté360 - ouverture dossier - {APP_TITLE}", body)
    st.session_state.data["access"]["admin_notifications"].append({"at":now_iso(),"status":"sent" if ok else "not_sent","smtp_message":msg})

def install_beforeunload_warning():
    st.components.v1.html("""<script>window.parent.onbeforeunload=function(e){e.preventDefault();e.returnValue='';return '';};</script>""", height=0)

def timeout_watchdog():
    if st_autorefresh: st_autorefresh(interval=10000, key="timeout_watchdog")
    if st.session_state.authenticated and not st.session_state.timed_out:
        elapsed=(datetime.now().timestamp()-st.session_state.last_activity)/60
        if elapsed > BENEFICIARY_TIMEOUT_MINUTES:
            st.session_state.timed_out=True; st.session_state.screen="timeout"; st.rerun()


def header():
    cols = st.columns([1, 8])
    with cols[0]:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=70)
    with cols[1]:
        st.markdown(f"# {APP_TITLE}")
        st.markdown(f"<div class='mini-note'>{APP_VERSION} - outil d'exploration accompagné · Socle {SOCLE_CLARTE360_VERSION}</div>", unsafe_allow_html=True)

def sidebar_public():
    st.sidebar.markdown("## Clarté360")
    st.sidebar.caption(f"App v{APP_VERSION} · Socle {SOCLE_CLARTE360_VERSION}")
    st.sidebar.markdown("---")
    if st.sidebar.button("💬 Contacter Clarté360", use_container_width=True, key="public_contact"):
        st.session_state.nav_back = st.session_state.get("screen", "home")
        st.session_state.screen = "contact"
        st.rerun()
    if st.sidebar.button("RGPD et mentions légales", use_container_width=True, key="public_legal"):
        st.session_state.nav_back = st.session_state.get("screen", "home")
        st.session_state.screen = "legal"
        st.rerun()
    if st.sidebar.button("Réinitialiser la session", use_container_width=True, key="public_reset"):
        st.session_state.clear()
        st.rerun()

def render_traceability_block():
    data = st.session_state.get("data", {}) if isinstance(st.session_state.get("data"), dict) else {}
    rgpd = data.get("rgpd", {}) if isinstance(data.get("rgpd", {}), dict) else {}
    access = data.get("access", {}) if isinstance(data.get("access", {}), dict) else {}
    sessions = access.get("sessions", []) if isinstance(access.get("sessions", []), list) else []
    code_history = access.get("code_history", []) if isinstance(access.get("code_history", []), list) else []
    save_events = access.get("save_events", []) if isinstance(access.get("save_events", []), list) else []

    st.markdown("### Traçabilité")
    c1, c2, c3 = st.columns(3)
    c1.metric("Consentement RGPD", "Oui" if rgpd.get("consent_given") else "Non")
    c2.metric("Sessions enregistrées", len(sessions))
    c3.metric("Temps cumulé", format_duration(total_duration_seconds(data)))

    if rgpd.get("consent_given"):
        st.success(f"Consentement enregistré le {rgpd.get('consent_at', 'date non disponible')} — version {rgpd.get('consent_text_version', RGPD_TEXT_VERSION)}")
    else:
        st.info("Aucun consentement RGPD validé dans la session active.")

    if sessions:
        st.markdown("#### Historique des sessions")
        st.dataframe(pd.DataFrame(sessions), use_container_width=True, hide_index=True)
    else:
        st.caption("Aucun historique de session disponible pour le moment.")

    if code_history:
        st.markdown("#### Historique des codes d'accès")
        safe_rows = []
        for row in code_history:
            if isinstance(row, dict):
                safe_rows.append({
                    "date": row.get("at", ""),
                    "e-mail": row.get("email", ""),
                    "statut": row.get("status", ""),
                    "expiration": row.get("expires_at", ""),
                    "message": row.get("smtp_message", ""),
                })
        if safe_rows:
            st.dataframe(pd.DataFrame(safe_rows), use_container_width=True, hide_index=True)

    if save_events:
        st.markdown("#### Sauvegardes JSON")
        st.dataframe(pd.DataFrame(save_events), use_container_width=True, hide_index=True)


def legal_page():
    sidebar_public()
    header()
    if st.button("← Retour à l'application", key="rgpd_back_top"):
        st.session_state.screen=st.session_state.nav_back
        st.rerun()
    st.markdown("## Informations légales et protection des données")
    tabs=st.tabs(["Protection des données", "Mentions légales", "Nous contacter"])
    with tabs[0]:
        st.markdown(RGPD_TEXT)
        render_traceability_block()
    with tabs[1]:
        st.markdown("### Mentions légales")
        st.markdown(CLARTE_LEGAL.replace("\n", "  \n"))
        st.markdown("Les contenus, méthodes, rapports, graphiques et outils Clarté360 sont protégés par le droit de la propriété intellectuelle.")
    with tabs[2]:
        st.markdown("### Contacter Clarté360")
        contact_form()

def contact_page():
    sidebar_public()
    header()
    if st.button("← Retour à l'application", key="contact_back_top"):
        st.session_state.screen = st.session_state.nav_back
        st.rerun()
    st.markdown("## Contacter Clarté360")
    contact_form()

def contact_form():
    b = st.session_state.data.get("beneficiaire", {}) if isinstance(st.session_state.get("data"), dict) else {}
    st.markdown("<div class='brand-box'>Vous pouvez nous adresser une question administrative, signaler un problème technique ou nous faire part d'une suggestion concernant cette application. Pour toute question relative à l'interprétation des exercices ou des résultats, rapprochez-vous de votre consultant ou accompagnateur.</div>", unsafe_allow_html=True)
    with st.form("contact_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom", value=b.get("nom", ""))
            prenom = st.text_input("Prénom", value=b.get("prenom", ""))
            email = st.text_input("E-mail", value=b.get("email", ""))
        with c2:
            tel = st.text_input("Téléphone facultatif", value=b.get("telephone", ""))
            objet = st.text_input("Objet")
        message = st.text_area("Message", height=150)
        consent = st.checkbox("Je consens au traitement de ce message pour permettre à Clarté360 de me répondre.")
        submitted = st.form_submit_button("Envoyer à Clarté360", type="primary")
    if submitted:
        if not email or "@" not in email or not objet or not message:
            st.error("Merci de renseigner au minimum un e-mail valide, un objet et un message.")
        elif not consent:
            st.error("Merci de confirmer le consentement spécifique au traitement de votre demande.")
        else:
            body = f"""Message depuis l'application Clarté360.

Application : {APP_TITLE}
Version : {APP_VERSION}
Socle : {SOCLE_CLARTE360_VERSION}
Date/heure : {now_iso()}
Session : {st.session_state.data.get('active_session_id', '')}

Nom : {nom}
Prénom : {prenom}
E-mail : {email}
Téléphone : {tel}
Objet : {objet}

Message :
{message}

Infos techniques : {json.dumps(get_client_network(), ensure_ascii=False)}
"""
            ok, msg = send_mail(ADMIN_EMAIL, f"Clarté360 - Contact - {objet}", body)
            if ok:
                st.success("Votre message a été transmis à Clarté360.")
            else:
                st.error(msg)

def sidebar():
    st.sidebar.markdown("## Clarté360")
    st.sidebar.caption(f"App v{APP_VERSION} · Socle {SOCLE_CLARTE360_VERSION}")
    if st.session_state.get("authenticated"):
        st.sidebar.markdown("### Session")
        b = st.session_state.data.get("beneficiaire", {})
        st.sidebar.caption(f"{b.get('prenom','')} {b.get('nom','')}")
        st.sidebar.caption("Votre progression est enregistrée dans votre fichier JSON.")
        st.sidebar.download_button("💾 Préparer mon JSON pour reprendre plus tard", data=json_bytes(), file_name=safe_name("clarte360_boucle_autovalidante", "json"), mime="application/json", use_container_width=True)
        st.sidebar.download_button("🚪 Quitter et télécharger mon JSON", data=json_bytes(), file_name=safe_name("clarte360_boucle_autovalidante_sortie", "json"), mime="application/json", type="primary", use_container_width=True)
    st.sidebar.markdown("---")
    if st.sidebar.button("💬 Contacter Clarté360", use_container_width=True): st.session_state.nav_back="app"; st.session_state.screen="contact"; st.rerun()
    if st.sidebar.button("RGPD et mentions légales", use_container_width=True): st.session_state.nav_back="app"; st.session_state.screen="legal"; st.rerun()
    if st.sidebar.button("Réinitialiser la session", use_container_width=True):
        st.session_state.clear()
        st.rerun()

def home():
    sidebar_public()
    if st.session_state.get("home_choice") == "import":
        header()
        st.markdown("### Reprendre une session avec mon fichier JSON")
        up = st.file_uploader("Importer mon fichier JSON Clarté360", type=["json"], key="home_import_json")
        if up is not None:
            try:
                st.session_state.data = normalize_data(json.loads(up.read().decode("utf-8")))
                st.session_state.authenticated = True
                st.session_state.screen = "app"
                st.session_state.home_choice = None
                st.rerun()
            except Exception as e:
                st.error(f"Import impossible : {e}")
        if st.button("← Retour à l'accueil"):
            st.session_state.home_choice = None
            st.rerun()
        return

    if st.session_state.get("home_choice") != "new":
        header()
        st.markdown(f"### Bienvenue dans l'application Clarté360 – Boucle auto-validante")
        st.markdown("Avez-vous conservé le fichier JSON de votre dernière utilisation ?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Oui → Importer mon fichier JSON", use_container_width=True):
                st.session_state.home_choice = "import"
                st.rerun()
        with c2:
            if st.button("Non → Commencer une nouvelle session", type="primary", use_container_width=True):
                st.session_state.home_choice = "new"
                st.session_state.code_sent = False
                st.session_state.pending_code = ""
                st.session_state.code_expires_at = None
                st.session_state.data = empty_data()
                st.rerun()
        st.info("Le fichier JSON est la mémoire unique de votre travail. Aucune donnée n'est sauvegardée durablement par l'application sur un serveur Clarté360.")
        return

    header()
    st.markdown("## Accès bénéficiaire")
    st.markdown("<div class='brand-box'>Pour commencer, renseignez votre identité et votre adresse e-mail. Un code d'accès à durée limitée vous sera envoyé par e-mail. Le consentement RGPD est obligatoire avant toute utilisation.</div>", unsafe_allow_html=True)

    if not st.session_state.get("code_sent", False):
        with st.form("new_session"):
            c1, c2 = st.columns(2)
            with c1:
                prenom=st.text_input("Prénom *", value=st.session_state.data.get("beneficiaire",{}).get("prenom",""))
                nom=st.text_input("Nom *", value=st.session_state.data.get("beneficiaire",{}).get("nom",""))
                email=st.text_input("Adresse e-mail *", value=st.session_state.data.get("beneficiaire",{}).get("email",""))
            with c2:
                consultant=st.text_input("Consultant / accompagnateur", value=st.session_state.data.get("consultant") or "Clarté360")
                tel=st.text_input("Téléphone facultatif", value=st.session_state.data.get("beneficiaire",{}).get("telephone",""))
            st.markdown("### Protection des données")
            st.markdown("Le fichier JSON reste la mémoire unique de votre travail. Aucune donnée n'est sauvegardée durablement par l'application sur un serveur Clarté360.")
            consent=st.checkbox("J'ai lu les informations RGPD et je consens à l'utilisation de ces données dans le cadre exclusif de mon accompagnement.")
            submitted=st.form_submit_button("Recevoir mon code d'accès", type="primary")
        if submitted:
            if not prenom.strip() or not nom.strip() or not email.strip():
                st.error("Merci de compléter le prénom, le nom et l'adresse e-mail.")
            elif "@" not in email or "." not in email:
                st.error("Merci de renseigner une adresse e-mail valide.")
            elif not consent:
                st.error("Merci de confirmer votre consentement RGPD pour poursuivre.")
            else:
                st.session_state.data=empty_data()
                st.session_state.data["beneficiaire"]={"prenom":prenom.strip(),"nom":nom.strip(),"email":email.strip(),"telephone":tel.strip()}
                st.session_state.data["consultant"]=consultant.strip()
                st.session_state.data["rgpd"]={"consent_given":True,"consent_at":now_iso(),"consent_text_version":RGPD_TEXT_VERSION}
                ok,msg=send_code(email.strip())
                notify_admin(first=True)
                if ok:
                    st.success("Un code d'accès vient d'être envoyé à l'adresse e-mail indiquée.")
                    st.rerun()
                else:
                    st.error(msg)
                    st.caption("Vérifiez que les Secrets Streamlit sont configurés dans la section [email], comme dans l'application Roue des domaines de vie.")
    else:
        b = st.session_state.data.get("beneficiaire", {})
        st.success(f"Code envoyé à : {b.get('email','')}")
        expires_raw = st.session_state.get("code_expires_at") or st.session_state.data.get("access",{}).get("code_expires_at")
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
                st.session_state.pending_code = ""
                st.session_state.code_expires_at = None
                st.rerun()
            return
        code=st.text_input("Saisissez le code d'accès reçu par e-mail *", max_chars=6, type="password")
        c1,c2=st.columns([1,2])
        with c1:
            if st.button("Valider le code et démarrer", type="primary"):
                if code and code == st.session_state.data.get("access",{}).get("code_access"):
                    st.session_state.authenticated=True
                    st.session_state.screen="app"
                    st.session_state.data.setdefault("access",{})["code_verified"] = True
                    st.session_state.data.setdefault("access",{})["verified_at"] = now_iso()
                    st.rerun()
                else:
                    st.error("Code incorrect.")
        with c2:
            if st.button("Je n'ai pas reçu mon code / Renvoyer un code"):
                ok, msg = send_code(b.get("email", ""))
                if ok:
                    st.success("Un nouveau code vient d'être envoyé.")
                else:
                    st.error(msg)
                st.rerun()

    if st.button("← Retour à l'accueil"):
        st.session_state.home_choice = None
        st.session_state.code_sent = False
        st.session_state.pending_code = ""
        st.session_state.code_expires_at = None
        st.rerun()

def code_screen():
    # Conservé uniquement pour compatibilité avec un ancien état de session : retour à l'écran d'accès intégré.
    st.session_state.home_choice = "new"
    st.session_state.screen = "home"
    st.rerun()

def default_croyance():
    return {"id":make_id("cr"),"created_at":now_iso(),"updated_at":now_iso(),"statut":"Découverte","phase_decouverte":{"date":str(date.today()),"boucle":{"croyance":"","comportement_actuel":"","resultat_actuel":"","renforcement":""},"commentaire_seance":"","concerne_tierce_personne":False},"phase_action":{"selectionnee_phase6":False,"date_travail":"","pourquoi_utile":"","resultat_souhaite":"","nouveau_comportement":"","actions":[],"suivi":""}}

def loop_text(v): return esc(v) if v else "<span class='loop-node-empty'>À compléter</span>"
def render_loop(bcl):
    return f"""<div class="loop-wrap"><svg class="loop-svg" viewBox="0 0 920 560" preserveAspectRatio="none"><defs><marker id="arrowhead" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="{BRAND_COLOR}" /></marker></defs><path d="M575 90 C735 95 805 145 798 217" fill="none" stroke="{BRAND_COLOR}" stroke-width="5" marker-end="url(#arrowhead)"/><path d="M790 318 C760 445 650 500 575 493" fill="none" stroke="{BRAND_COLOR}" stroke-width="5" marker-end="url(#arrowhead)"/><path d="M345 492 C190 492 110 430 125 318" fill="none" stroke="{BRAND_COLOR}" stroke-width="5" marker-end="url(#arrowhead)"/><path d="M125 215 C115 105 270 76 345 88" fill="none" stroke="{BRAND_COLOR}" stroke-width="5" marker-end="url(#arrowhead)"/></svg><div class="loop-node loop-node-top"><div class="loop-node-title">1. Croyance</div><div class="loop-node-text">{loop_text(bcl.get('croyance'))}</div></div><div class="loop-node loop-node-right"><div class="loop-node-title">2. Comportement induit</div><div class="loop-node-text">{loop_text(bcl.get('comportement_actuel'))}</div></div><div class="loop-node loop-node-bottom"><div class="loop-node-title">3. Résultat actuel</div><div class="loop-node-text">{loop_text(bcl.get('resultat_actuel'))}</div></div><div class="loop-node loop-node-left"><div class="loop-node-title">4. Renforcement</div><div class="loop-node-text">{loop_text(bcl.get('renforcement') or 'Le résultat semble confirmer la croyance')}</div></div><div class="loop-center">La boucle se referme<br/>et se valide elle-même</div></div>"""

def edit_discovery(c):
    st.markdown("## Phase 3 — Construire la boucle auto-validante")
    st.markdown("<div class='brand-box'>Objectif : faire apparaître la boucle sans chercher encore à la résoudre.</div>", unsafe_allow_html=True)
    ph=c.setdefault("phase_decouverte",{}); bcl=ph.setdefault("boucle",{})
    ph["date"]=str(st.date_input("Date de découverte", value=date.fromisoformat(ph.get("date") or str(date.today())), key=f"date_{c['id']}"))
    col1,col2=st.columns(2)
    with col1:
        bcl["croyance"]=st.text_area("1. Croyance exprimée", value=bcl.get("croyance",""), height=90, key=f"croy_{c['id']}")
        bcl["resultat_actuel"]=st.text_area("3. Résultat actuel", value=bcl.get("resultat_actuel",""), height=90, key=f"res_{c['id']}")
    with col2:
        bcl["comportement_actuel"]=st.text_area("2. Comportement induit", value=bcl.get("comportement_actuel",""), height=90, key=f"comp_{c['id']}")
        bcl["renforcement"]=st.text_area("4. Renforcement", value=bcl.get("renforcement",""), height=90, key=f"renf_{c['id']}")
    st.markdown(render_loop(bcl), unsafe_allow_html=True)
    with st.expander("Point d'attention accompagnateur"):
        ph["concerne_tierce_personne"]=st.checkbox("Cette croyance vise une personne précise", value=bool(ph.get("concerne_tierce_personne",False)), key=f"tierce_{c['id']}")
        if ph.get("concerne_tierce_personne"): st.warning("Ne pas utiliser cet outil pour une croyance portant sur une personne identifiée.")
    ph["commentaire_seance"]=st.text_area("Notes de séance facultatives", value=ph.get("commentaire_seance",""), height=80, key=f"com_{c['id']}")
    c["statut"]=st.selectbox("Statut", STATUTS, index=STATUTS.index(c.get("statut","Découverte")) if c.get("statut") in STATUTS else 0, key=f"stat_{c['id']}")
    if st.button("Enregistrer cette boucle", type="primary", key=f"save_disc_{c['id']}"):
        c["updated_at"]=now_iso(); touch(); st.success("Boucle enregistrée dans le JSON courant. Pensez à télécharger le JSON.")

def edit_phase6(c):
    st.markdown("## Phase 6 — Sortir de la boucle par l'action")
    st.markdown(render_loop(c.get("phase_decouverte",{}).get("boucle",{})), unsafe_allow_html=True)
    act=c.setdefault("phase_action",{})
    act["selectionnee_phase6"]=st.checkbox("Cette croyance est sélectionnée pour un travail en phase 6", value=bool(act.get("selectionnee_phase6",False)), key=f"sel6_{c['id']}")
    act["date_travail"]=str(st.date_input("Date du travail", value=date.fromisoformat(act.get("date_travail") or str(date.today())), key=f"dt6_{c['id']}"))
    act["pourquoi_utile"]=st.text_area("Pourquoi cette croyance est utile à travailler maintenant ?", value=act.get("pourquoi_utile",""), height=90, key=f"why6_{c['id']}")
    st.markdown("<div class='warn-box'><strong>À votre avis, que pourriez-vous faire pour ne plus rester dans cette boucle ?</strong></div>", unsafe_allow_html=True)
    act["resultat_souhaite"]=st.text_area("Résultat souhaité", value=act.get("resultat_souhaite",""), height=90, key=f"rs6_{c['id']}")
    act["nouveau_comportement"]=st.text_area("Nouveau comportement", value=act.get("nouveau_comportement",""), height=90, key=f"nc6_{c['id']}")
    actions=act.setdefault("actions",[])
    if st.button("Ajouter une action", key=f"addact_{c['id']}"): actions.append({"action":"","date":"","contexte":"","indicateur":"","obstacle":"","solution":""}); st.rerun()
    for i,a in enumerate(actions):
        with st.expander(f"Action {i+1} — {a.get('action') or 'à compléter'}", expanded=True):
            a["action"]=st.text_area("Action précise", value=a.get("action",""), key=f"a_{c['id']}_{i}")
            a["date"]=st.text_input("Date / échéance", value=a.get("date",""), key=f"d_{c['id']}_{i}")
            a["indicateur"]=st.text_input("Indicateur", value=a.get("indicateur",""), key=f"ind_{c['id']}_{i}")
            a["obstacle"]=st.text_input("Obstacle possible", value=a.get("obstacle",""), key=f"obs_{c['id']}_{i}")
            a["solution"]=st.text_input("Solution prévue", value=a.get("solution",""), key=f"sol_{c['id']}_{i}")
    act["suivi"]=st.text_area("Notes de suivi", value=act.get("suivi",""), height=90, key=f"suivi_{c['id']}")
    if st.button("Enregistrer le travail de phase 6", type="primary", key=f"save6_{c['id']}"):
        c["statut"]="Travaillée"; c["updated_at"]=now_iso(); touch(); st.success("Travail enregistré.")

def footer(canvas, doc):
    canvas.saveState(); canvas.setFont("Helvetica",7); canvas.setFillColor(colors.grey); text="CLARTÉ360 - 60 rue François 1er - 75008 Paris - Tél. : 01 89 48 08 25 - contact@clarte360.com - www.clarte360.com - RCS 102349834 - SIRET 10234983400014"; canvas.drawCentredString(A4[0]/2, .65*cm, text); canvas.restoreState()

def pdf_bytes(c):
    b=st.session_state.data.get("beneficiaire",{}); buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=1.5*cm,leftMargin=1.5*cm,topMargin=1.3*cm,bottomMargin=1.4*cm); styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name="TealTitle",parent=styles["Title"],textColor=colors.HexColor(BRAND_COLOR),fontSize=20,leading=24)); styles.add(ParagraphStyle(name="TealH2",parent=styles["Heading2"],textColor=colors.HexColor(BRAND_COLOR),fontSize=14)); story=[]
    if LOGO_PATH.exists(): story.append(Image(str(LOGO_PATH), width=4*cm, height=4*cm, kind="proportional")); story.append(Spacer(1,.2*cm))
    story.append(Paragraph(APP_TITLE, styles["TealTitle"])); story.append(Paragraph(f"Bénéficiaire : {esc(b.get('prenom'))} {esc(b.get('nom'))}", styles["Normal"])); story.append(Paragraph(f"Date d'édition : {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"])); story.append(Spacer(1,.4*cm))
    ph=c.get("phase_decouverte",{}); bcl=ph.get("boucle",{})
    story.append(Paragraph("Phase 3 — Boucle actuelle", styles["TealH2"])); data=[["Élément","Contenu"],["Croyance",esc(bcl.get("croyance"))],["Comportement actuel",esc(bcl.get("comportement_actuel"))],["Résultat actuel",esc(bcl.get("resultat_actuel"))],["Renforcement",esc(bcl.get("renforcement"))]]; t=Table(data,colWidths=[4*cm,12*cm]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(BRAND_COLOR)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")])); story.append(t); story.append(Spacer(1,.4*cm)); story.append(Paragraph("Notes",styles["TealH2"])); story.append(Paragraph(esc(ph.get("commentaire_seance")) or "Aucune note renseignée.", styles["Normal"])); story.append(PageBreak())
    act=c.get("phase_action",{}); story.append(Paragraph("Phase 6 — Scénario de sortie", styles["TealH2"])); data2=[["Élément","Contenu"],["Pourquoi travailler cette croyance",esc(act.get("pourquoi_utile"))],["Résultat souhaité",esc(act.get("resultat_souhaite"))],["Nouveau comportement",esc(act.get("nouveau_comportement"))]]; t2=Table(data2,colWidths=[5*cm,11*cm]); t2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(BRAND_COLOR)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")])); story.append(t2); story.append(Spacer(1,.4*cm)); story.append(Paragraph("Plan d'action", styles["TealH2"])); acts=act.get("actions",[])
    if acts:
        tbl=[["Action","Date","Indicateur","Obstacle / solution"]]+[[esc(a.get("action")),esc(a.get("date")),esc(a.get("indicateur")),esc((a.get("obstacle") or "")+" / "+(a.get("solution") or ""))] for a in acts]; tt=Table(tbl,colWidths=[5*cm,2.5*cm,4*cm,4.5*cm]); tt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(BRAND_COLOR)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")])); story.append(tt)
    else: story.append(Paragraph("Aucune action renseignée.", styles["Normal"]))
    doc.build(story,onFirstPage=footer,onLaterPages=footer); buf.seek(0); return buf.getvalue()

def app_screen():
    sidebar(); header()
    if st.button("➕ Ajouter une nouvelle croyance découverte", type="primary"):
        c=default_croyance(); st.session_state.data["croyances"].append(c); st.session_state.selected_croyance_id=c["id"]; touch(); st.rerun()
    croyances=st.session_state.data.get("croyances",[])
    if not croyances: st.info("Ajoutez une première croyance pour commencer."); return
    labels=[f"[{c.get('statut','')}] {(c.get('phase_decouverte',{}).get('boucle',{}).get('croyance') or 'Croyance à compléter')[:90]}" for c in croyances]; ids=[c["id"] for c in croyances]; idx=ids.index(st.session_state.selected_croyance_id) if st.session_state.selected_croyance_id in ids else 0; idx=st.selectbox("Croyance", range(len(labels)), format_func=lambda i:labels[i], index=idx); c=croyances[idx]; st.session_state.selected_croyance_id=c["id"]
    tabs=st.tabs(["Phase 3 — Découverte", "Phase 6 — Action", "PDF / JSON", "RGPD / Traçabilité"])
    with tabs[0]: edit_discovery(c)
    with tabs[1]: edit_phase6(c)
    with tabs[2]:
        st.download_button("Télécharger la fiche PDF", data=pdf_bytes(c), file_name=safe_name("clarte360_boucle_autovalidante", "pdf"), mime="application/pdf", type="primary")
        st.download_button("Télécharger le JSON complet", data=json_bytes(), file_name=safe_name("clarte360_boucle_autovalidante", "json"), mime="application/json")
    with tabs[3]:
        st.json({"rgpd":st.session_state.data.get("rgpd",{}),"access":st.session_state.data.get("access",{})})

def timeout_screen():
    st.warning("La session a été interrompue après une période d'inactivité. Téléchargez votre JSON avant de quitter ou de reprendre.")
    st.download_button("Télécharger mon JSON de sauvegarde", data=json_bytes(), file_name=safe_name("clarte360_boucle_autovalidante_timeout", "json"), mime="application/json", type="primary")
    if st.button("Reprendre la session"):
        st.session_state.timed_out=False; st.session_state.last_activity=datetime.now().timestamp(); st.session_state.screen="app"; st.rerun()

def main():
    init_state(); install_beforeunload_warning(); timeout_watchdog()
    if st.session_state.screen == "timeout": timeout_screen()
    elif st.session_state.screen == "legal": legal_page()
    elif st.session_state.screen == "contact": contact_page()
    elif st.session_state.screen == "code": code_screen()
    elif st.session_state.authenticated and st.session_state.screen == "app": app_screen()
    else: home()

if __name__ == "__main__": main()
