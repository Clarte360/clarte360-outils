import csv
import io
import json
import math
import secrets
import smtplib
import string
from copy import deepcopy
from datetime import date, datetime
from email.message import EmailMessage
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Wedge
import pandas as pd
import streamlit as st

APP_TITLE = "Clarté360 - Roue des valeurs"
APP_VERSION = "V2.2"
BRAND_COLOR = "#008080"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo_clarte360.png"
DOMAINES = ["Personnel", "Travail", "Famille", "Social", "Couple / intimité"]
FINAL_EMAIL_TO = "contact@clarte360.com"
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
        div.stButton > button:first-child {{border-radius:10px; border:1px solid {BRAND_COLOR}; color:{BRAND_COLOR};}}
        div.stDownloadButton > button:first-child {{border-radius:10px; border:1px solid {BRAND_COLOR}; color:{BRAND_COLOR};}}
    </style>
    """,
    unsafe_allow_html=True,
)


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

    subject_admin = "Clarté360 - Nouveau code d'accès Roue des valeurs"
    body_admin = (
        "Une personne vient de demander un code d'accès pour réaliser l'outil Clarté360 - Roue des valeurs.\n\n"
        f"Prénom : {prenom}\n"
        f"Nom : {nom}\n"
        f"Email : {email}\n"
        f"Code généré : {access_code}\n"
        f"Date/heure : {datetime.now().isoformat(timespec='seconds')}\n"
    )
    ok_admin, msg_admin = send_email(admin_to, subject_admin, body_admin)

    subject_user = "Votre code d'accès Clarté360"
    body_user = (
        f"Bonjour {prenom},\n\n"
        "Voici votre code d'accès pour démarrer l'outil Clarté360 - Roue des valeurs :\n\n"
        f"{access_code}\n\n"
        "Ce code permet de sécuriser le démarrage de votre passation.\n\n"
        "Vos réponses seront utilisées uniquement dans le cadre de votre accompagnement. "
        "Le fichier JSON pourra être transmis à votre consultant Clarté360 afin de préparer la restitution.\n\n"
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
    subject = "Clarté360 - JSON final Roue des valeurs"
    body = (
        "Le bénéficiaire a terminé l'outil Clarté360 - Roue des valeurs.\n\n"
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
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v


def access_gate() -> bool:
    """Retourne True lorsque le code est validé."""
    ensure_access_state()
    if st.session_state.get("code_verified"):
        return True

    header()
    st.markdown("## Accès bénéficiaire")
    st.write("Cet outil n'est pas un test psychométrique. Il sert de support d'exploration et d'échange avec votre consultant Clarté360.")
    st.markdown(
        """
        <div class='privacy-box'>
        🔒 <strong>Confidentialité et transmission</strong><br>
        Vos réponses restent sous votre contrôle. Le fichier JSON final pourra être transmis à votre consultant Clarté360 afin de préparer l'analyse et la restitution. Aucune donnée n'est exploitée hors du cadre de votre accompagnement.
        </div>
        """,
        unsafe_allow_html=True,
    )
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
            consent = st.checkbox("Je comprends que mes réponses seront utilisées uniquement dans le cadre de mon accompagnement et que le JSON pourra être transmis à mon consultant.")
            submit = st.form_submit_button("Recevoir / générer mon code d'accès", type="primary")
        if submit:
            if not prenom.strip() or not nom.strip() or not email.strip():
                st.error("Merci de renseigner le prénom, le nom et l'adresse email.")
            elif "@" not in email or "." not in email:
                st.error("Merci de renseigner une adresse email valide.")
            elif not consent:
                st.error("Merci de confirmer la compréhension de l'utilisation des données.")
            else:
                beneficiaire_tmp = {"prenom": prenom.strip(), "nom": nom.strip(), "email": email.strip(), "consultant": consultant.strip()}
                code = generate_access_code()
                ok, msg = send_access_code_email(beneficiaire_tmp, code)
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
                    st.session_state.data = data
                    st.rerun()
                else:
                    st.error("Code incorrect.")
        with c2:
            if st.button("Modifier les informations"):
                for k in ["access_code", "code_sent", "code_verified", "pending_beneficiaire"]:
                    st.session_state.pop(k, None)
                st.rerun()
    return False


def empty_state():
    return {
        "version": APP_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "beneficiaire": {"prenom": "", "nom": "", "email": "", "consultant": "Clarté360", "date_realisation": date.today().isoformat()},
        "access": {"started_at": datetime.now().isoformat(timespec="seconds"), "code_verified": False},
        "valeurs": [],
    }


def ensure_state():
    if "data" not in st.session_state:
        st.session_state.data = empty_state()
    if "page" not in st.session_state:
        st.session_state.page = "1. Bénéficiaire"


def update_timestamp():
    st.session_state.data["updated_at"] = datetime.now().isoformat(timespec="seconds")


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
        st.markdown(f"<div class='small-note'>Application {APP_VERSION} - aide neutre à la construction de la roue des valeurs</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def clean_filename(text):
    text = (text or "beneficiaire").strip().replace(" ", "_")
    return "".join(c for c in text if c.isalnum() or c in "_-.")


def export_basename(data, outil="RoueValeurs"):
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
                "Domaine": d.get("domaine", ""),
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
    ax.set_title(f"Roue des valeurs - {title_prenom} {title_nom} - {title_date}".strip(), fontsize=13, fontweight="bold", color="#2D3142", pad=14)

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


def create_pdf_bytes(data):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        fig = create_wheel_figure(data, small=False)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        rows = build_rows(data)
        if rows:
            fig2, ax = plt.subplots(figsize=(8.27, 11.69))
            ax.axis("off")
            b = data["beneficiaire"]
            ax.text(0.03, 0.97, "Clarté360 - Roue des valeurs", fontsize=16, fontweight="bold", color=BRAND_COLOR, va="top")
            ax.text(0.03, 0.935, f"Bénéficiaire : {b.get('prenom','')} {b.get('nom','')}", fontsize=11, va="top")
            ax.text(0.03, 0.91, f"Date de réalisation : {b.get('date_realisation','')}", fontsize=11, va="top")
            y = 0.86
            for val in data.get("valeurs", []):
                if y < 0.12:
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
            pdf.savefig(fig2, bbox_inches="tight")
            plt.close(fig2)
    buf.seek(0)
    return buf.getvalue()


def add_default_values(nb):
    data = st.session_state.data
    current = len(data["valeurs"])
    if nb > current:
        for i in range(current, nb):
            data["valeurs"].append({
                "nom": f"Valeur {i+1}",
                "definition": "",
                "couleur": DEFAULT_COLORS[i % len(DEFAULT_COLORS)],
                "domaines": [{"domaine": d, "periode": "", "exemple": "", "cote": 0} for d in DOMAINES],
            })
    elif nb < current:
        data["valeurs"] = data["valeurs"][:nb]
    update_timestamp()


def sidebar():
    st.sidebar.markdown("## Navigation")
    pages = ["1. Bénéficiaire", "2. Consignes", "3. Valeurs et domaines", "4. Roue", "5. Export / Import"]
    st.session_state.page = st.sidebar.radio("", pages, index=pages.index(st.session_state.page), label_visibility="collapsed")
    st.sidebar.markdown("---")
    uploaded = st.sidebar.file_uploader("Ouvrir un questionnaire JSON", type=["json"])
    if uploaded is not None:
        try:
            loaded = json.loads(uploaded.getvalue().decode("utf-8"))
            st.session_state.data = loaded
            st.sidebar.success("Questionnaire chargé.")
        except Exception as exc:
            st.sidebar.error(f"Impossible de lire ce JSON : {exc}")
    if st.sidebar.button("Nouveau questionnaire vierge"):
        st.session_state.data = empty_state()
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
    nb = st.number_input("Combien de valeurs souhaitez-vous renseigner ?", min_value=1, max_value=24, value=nb_current, step=1)
    if st.button("Valider / ajuster le nombre de valeurs"):
        add_default_values(int(nb))
        st.success("Nombre de valeurs mis à jour.")
        st.session_state.page = "3. Valeurs et domaines"
        st.rerun()


def page_consignes():
    st.markdown("## 2. Consignes")
    st.markdown(
        """
        <div class='rule-box'>
        Cette roue n'a pas pour objectif de suggérer des valeurs ou d'interpréter le profil de la personne. Elle aide uniquement à vérifier dans quelle mesure les valeurs déjà identifiées sont réellement incarnées dans les domaines de vie.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown("### Règle centrale")
    st.write("Pour chaque valeur et pour chaque domaine de vie, le bénéficiaire doit décrire une action ou une réaction concrète, précise et située dans le temps.")
    st.markdown(
        """
        Exemples recevables :
        - "Le 15 février, je suis sorti de la pièce lorsque j'ai vu une personne boire au-delà des limites, car la sobriété est une valeur importante pour moi."
        - "En mars 2026, j'ai refusé une mission qui ne respectait pas mon équilibre de vie."
        - "La semaine dernière, j'ai consacré deux heures à aider mon fils à préparer son exposé."

        Exemples trop généraux :
        - "Je suis quelqu'un d'autonome."
        - "La famille est importante pour moi."
        - "Je respecte les autres."
        """
    )
    st.markdown("<div class='warn-box'>Si aucune action ou réaction concrète n'est identifiable dans un domaine de vie, la valeur peut rester importante pour la personne, mais elle n'est pas réellement mise en œuvre dans ce domaine. La cote doit alors être faible, possiblement égale à 0.</div>", unsafe_allow_html=True)


def page_valeurs():
    st.markdown("## 3. Valeurs et domaines de vie")
    st.write("Pour chaque valeur, renseignez les 5 domaines de vie. Le programme ne suggère aucune valeur et ne réalise aucune interprétation.")
    if not st.session_state.data.get("valeurs"):
        st.info("Commencez par indiquer le nombre de valeurs dans la page 1.")
        return
    for idx, val in enumerate(st.session_state.data["valeurs"]):
        with st.expander(f"Valeur {idx+1} : {val.get('nom','')}", expanded=idx == 0):
            c1, c2, c3 = st.columns([0.55, 0.18, 0.27])
            with c1:
                val["nom"] = st.text_input("Nom de la valeur", value=val.get("nom", ""), key=f"nom_{idx}")
                val["definition"] = st.text_area("Définition personnelle de cette valeur (facultatif)", value=val.get("definition", ""), key=f"def_{idx}", height=80)
            with c2:
                val["couleur"] = st.color_picker("Couleur", value=val.get("couleur", DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]), key=f"col_{idx}")
            with c3:
                st.metric("Moyenne actuelle", f"{moyenne_valeur(val):g}/10")

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
    st.markdown("## 4. Roue des valeurs")
    fig = create_wheel_figure(st.session_state.data, small=True)
    st.pyplot(fig, use_container_width=False)
    png_bytes = fig_to_png_bytes(fig)
    plt.close(fig)
    b = st.session_state.data["beneficiaire"]
    base = export_basename(st.session_state.data)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Télécharger la roue en PNG", data=png_bytes, file_name=f"{base}.png", mime="image/png")
    with c2:
        pdf_bytes = create_pdf_bytes(st.session_state.data)
        st.download_button("Télécharger le PDF", data=pdf_bytes, file_name=f"{base}.pdf", mime="application/pdf")


def page_export():
    st.markdown("## 5. Export / Import")
    data = st.session_state.data
    b = data["beneficiaire"]
    base = export_basename(st.session_state.data)
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    rows = build_rows(data)
    csv_buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(csv_buf, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    st.download_button("Télécharger le JSON modifiable", json_bytes, file_name=f"{base}.json", mime="application/json")
    st.markdown("### Transmission au consultant")
    st.info("En cliquant sur le bouton ci-dessous, le fichier JSON est transmis à votre consultant Clarté360 afin de préparer l’analyse et la restitution. Vous conservez également la possibilité de télécharger votre propre JSON.")
    if st.button("Transmettre le JSON au consultant", type="primary"):
        ok, msg = send_final_json_to_consultant(data, json_bytes, f"{base}.json")
        if ok:
            st.session_state.final_json_sent = True
            st.success("JSON transmis au consultant Clarté360.")
        else:
            st.error("La transmission automatique n’a pas pu être effectuée.")
            st.caption(msg)
    st.download_button("Télécharger le CSV", csv_buf.getvalue().encode("utf-8-sig"), file_name=f"{base}.csv", mime="text/csv")
    fig = create_wheel_figure(data, small=True)
    st.download_button("Télécharger le PNG", fig_to_png_bytes(fig), file_name=f"{base}.png", mime="image/png")
    plt.close(fig)
    st.download_button("Télécharger le PDF", create_pdf_bytes(data), file_name=f"{base}.pdf", mime="application/pdf")
    if rows:
        st.markdown("### Aperçu des données")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def main():
    ensure_state()
    ensure_access_state()
    if not access_gate():
        return
    sidebar()
    header()
    if st.session_state.page.startswith("1"):
        page_beneficiaire()
    elif st.session_state.page.startswith("2"):
        page_consignes()
    elif st.session_state.page.startswith("3"):
        page_valeurs()
    elif st.session_state.page.startswith("4"):
        page_roue()
    else:
        page_export()


if __name__ == "__main__":
    main()
