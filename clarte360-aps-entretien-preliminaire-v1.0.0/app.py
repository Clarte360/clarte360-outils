import json
import re
import sqlite3
import uuid
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_VERSION = "1.0.0"
SOCLE_CLARTE360_VERSION = "4.0-compatible"
APP_NAME = "APS – Entretien préliminaire"
APP_FULL_NAME = "Clarté360 – APS – Entretien préliminaire"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "site_icon.png"
DEFAULT_DB_PATH = BASE_DIR / "data" / "clarte360_aps.db"

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

st.set_page_config(page_title=APP_FULL_NAME, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🟢", layout="centered")
st.markdown(
    f"""
<style>
:root {{ --clarte-teal: {OFFICIAL_TEAL}; }}
h1, h2, h3 {{ color: {OFFICIAL_TEAL}; }}
.stProgress > div > div > div > div {{ background-color: {OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"] {{ background-color: {OFFICIAL_TEAL}; border-color: {OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"]:hover {{ background-color: #006f6f; border-color: #006f6f; }}
.clarte-box {{ border-left: 6px solid {OFFICIAL_TEAL}; background: {LIGHT_TEAL}; padding: 1rem 1.1rem; border-radius: .55rem; margin: 1rem 0; color: {DARK_TEXT}; }}
.clarte-card {{ border: 1px solid #d9eeee; border-radius: .8rem; padding: 1rem; background: #fff; box-shadow: 0 1px 8px rgba(0,128,128,.08); margin-bottom: 1rem; }}
.small-muted {{ color:#666; font-size:.9rem; }}
.required-note {{ color:#8a4f00; font-size:.9rem; }}
.status-ok {{ color:#1c6b42; font-weight:700; }}
.status-ko {{ color:#a33a2b; font-weight:700; }}
</style>
""",
    unsafe_allow_html=True,
)

SECTIONS = [
    "Accueil",
    "1. Identité",
    "2. Cadre contractuel",
    "3. Situation professionnelle",
    "4. Demande et besoin",
    "5. Objectifs du bilan",
    "6. Format et modalités",
    "7. Consentement et confidentialité",
    "8. Synthèse et export",
]

TOOLS = [
    "Roue des valeurs",
    "Recherche de mes valeurs",
    "Préférences professionnelles",
    "Moteurs professionnels",
    "Ligne de vie",
    "Compétences et Projets professionnels",
    "Roue des domaines de vie",
    "Boucle autovalidante / croyances",
    "Tableau des limites",
    "DIAGORIENTE (RIASEC / BRILLO / centres d’intérêt / métiers)",
]


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def secret(section, key, default=""):
    try:
        return st.secrets.get(section, {}).get(key, default)
    except Exception:
        return default


def db_path() -> Path:
    raw = str(secret("database", "path", "") or "").strip()
    p = Path(raw) if raw else DEFAULT_DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def db_connect():
    con = sqlite3.connect(db_path(), timeout=20)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db_connect() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS dossiers (
                dossier_id TEXT PRIMARY KEY,
                beneficiary_name TEXT NOT NULL DEFAULT '',
                beneficiary_email TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'brouillon',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dossier_id TEXT NOT NULL,
                event_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT ''
            )
            """
        )


def empty_payload(dossier_id: str):
    return {
        "meta": {
            "dossier_id": dossier_id,
            "app": APP_FULL_NAME,
            "app_version": APP_VERSION,
            "framework_version": SOCLE_CLARTE360_VERSION,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "status": "brouillon",
        },
        "beneficiaire": {},
        "contractualisation": {},
        "situation_professionnelle": {},
        "demande_besoin": {},
        "objectifs": {},
        "modalites": {},
        "consentements": {},
        "synthese": {},
    }


def save_payload(payload, event="sauvegarde"):
    payload["meta"]["updated_at"] = now_iso()
    b = payload.get("beneficiaire", {})
    name = " ".join([str(b.get("prenom", "")).strip(), str(b.get("nom", "")).strip()]).strip()
    email = str(b.get("email", "")).strip()
    with db_connect() as con:
        con.execute(
            """
            INSERT INTO dossiers(dossier_id, beneficiary_name, beneficiary_email, status, created_at, updated_at, payload_json)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(dossier_id) DO UPDATE SET
                beneficiary_name=excluded.beneficiary_name,
                beneficiary_email=excluded.beneficiary_email,
                status=excluded.status,
                updated_at=excluded.updated_at,
                payload_json=excluded.payload_json
            """,
            (
                payload["meta"]["dossier_id"], name, email, payload["meta"].get("status", "brouillon"),
                payload["meta"].get("created_at", now_iso()), payload["meta"]["updated_at"],
                json.dumps(payload, ensure_ascii=False, default=str),
            ),
        )
        con.execute(
            "INSERT INTO events(dossier_id,event_at,event_type,details) VALUES(?,?,?,?)",
            (payload["meta"]["dossier_id"], now_iso(), event, ""),
        )


def list_dossiers():
    with db_connect() as con:
        return con.execute("SELECT dossier_id, beneficiary_name, beneficiary_email, status, updated_at FROM dossiers ORDER BY updated_at DESC").fetchall()


def load_payload(dossier_id):
    with db_connect() as con:
        row = con.execute("SELECT payload_json FROM dossiers WHERE dossier_id=?", (dossier_id,)).fetchone()
    return json.loads(row["payload_json"]) if row else None


def delete_dossier(dossier_id):
    with db_connect() as con:
        con.execute("DELETE FROM events WHERE dossier_id=?", (dossier_id,))
        con.execute("DELETE FROM dossiers WHERE dossier_id=?", (dossier_id,))


def clean_text(v):
    return str(v or "").strip()


def valid_email(v):
    v = clean_text(v)
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v)) if v else False


def valid_siret(v):
    digits = re.sub(r"\D", "", clean_text(v))
    return len(digits) == 14


def required_checks(p):
    b = p.get("beneficiaire", {})
    c = p.get("contractualisation", {})
    s = p.get("situation_professionnelle", {})
    d = p.get("demande_besoin", {})
    o = p.get("objectifs", {})
    m = p.get("modalites", {})
    k = p.get("consentements", {})
    checks = {
        "Nom et prénom": bool(clean_text(b.get("nom")) and clean_text(b.get("prenom"))),
        "Date de naissance": bool(clean_text(b.get("date_naissance"))),
        "Adresse complète": bool(clean_text(b.get("adresse")) and clean_text(b.get("code_postal")) and clean_text(b.get("ville"))),
        "E-mail bénéficiaire": valid_email(b.get("email")),
        "Téléphone": bool(clean_text(b.get("telephone"))),
        "Cadre contractuel choisi": bool(clean_text(c.get("type_contrat"))),
        "Financeur / payeur identifié": bool(clean_text(c.get("financeur"))),
        "Situation professionnelle renseignée": bool(clean_text(s.get("statut"))),
        "Origine et raison de la demande": bool(clean_text(d.get("origine_demande")) and clean_text(d.get("pourquoi_maintenant"))),
        "Attentes / résultat attendu": bool(clean_text(d.get("attentes"))),
        "Objectifs co-définis": bool(clean_text(o.get("objectifs_codefinis"))),
        "Format et calendrier": bool(clean_text(m.get("format")) and clean_text(m.get("periode_previsionnelle"))),
        "Volontariat confirmé": bool(k.get("volontaire")),
        "Confidentialité expliquée": bool(k.get("confidentialite_expliquee")),
        "RGPD expliqué": bool(k.get("rgpd_explique")),
        "Modalités comprises": bool(k.get("modalites_comprises")),
        "Accord pour poursuivre": bool(k.get("accord_poursuite")),
    }
    third_party = c.get("type_contrat") in [
        "Convention avec entreprise / donneur d’ordre",
        "Convention tripartite Clarté360 / donneur d’ordre / bénéficiaire",
        "Financeur institutionnel / autre donneur d’ordre",
    ]
    if third_party:
        checks.update({
            "Raison sociale donneur d’ordre": bool(clean_text(c.get("do_raison_sociale"))),
            "Adresse donneur d’ordre": bool(clean_text(c.get("do_adresse")) and clean_text(c.get("do_ville"))),
            "Signataire donneur d’ordre": bool(clean_text(c.get("do_signataire_nom")) and valid_email(c.get("do_signataire_email"))),
            "Consentement séparé du bénéficiaire prévu": bool(k.get("consentement_separe_si_tiers")),
        })
    return checks


def completion_pct(p):
    checks = required_checks(p)
    return int(100 * sum(checks.values()) / max(1, len(checks)))


def json_bytes(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def pdf_bytes(payload):
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="C360Title", parent=styles["Title"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=18, leading=22))
    styles.add(ParagraphStyle(name="C360H", parent=styles["Heading2"], textColor=colors.HexColor(OFFICIAL_TEAL), fontSize=12, leading=15, spaceBefore=8, spaceAfter=5))
    styles.add(ParagraphStyle(name="C360Small", parent=styles["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#555555")))
    story = [Paragraph("Clarté360 – Fiche APS / Entretien préliminaire", styles["C360Title"]), Spacer(1, 0.2*cm)]
    story.append(Paragraph(f"Référence dossier : {payload['meta']['dossier_id']} – généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["C360Small"]))

    def sec(title, pairs):
        story.append(Paragraph(title, styles["C360H"]))
        data = []
        for label, value in pairs:
            txt = clean_text(value)
            if txt:
                data.append([Paragraph(f"<b>{label}</b>", styles["BodyText"]), Paragraph(txt.replace("\n", "<br/>"), styles["BodyText"])])
        if data:
            t = Table(data, colWidths=[5.3*cm, 11.2*cm])
            t.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#D9EEEE")),
                ("BACKGROUND", (0,0), (0,-1), colors.HexColor(LIGHT_TEAL)),
                ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            story.append(t)

    b = payload.get("beneficiaire", {})
    c = payload.get("contractualisation", {})
    s = payload.get("situation_professionnelle", {})
    d = payload.get("demande_besoin", {})
    o = payload.get("objectifs", {})
    m = payload.get("modalites", {})
    k = payload.get("consentements", {})
    sec("1. Bénéficiaire", [
        ("Identité", f"{b.get('civilite','')} {b.get('prenom','')} {b.get('nom','')}"),
        ("Nom de naissance", b.get("nom_naissance")), ("Date de naissance", b.get("date_naissance")),
        ("Adresse", f"{b.get('adresse','')} {b.get('complement_adresse','')} – {b.get('code_postal','')} {b.get('ville','')} – {b.get('pays','')}"),
        ("E-mail", b.get("email")), ("Téléphone", b.get("telephone")),
    ])
    sec("2. Cadre contractuel", [
        ("Type", c.get("type_contrat")), ("Financeur / payeur", c.get("financeur")), ("Référence / bon de commande", c.get("reference_commande")),
        ("Donneur d’ordre", c.get("do_raison_sociale")), ("SIRET / identifiant", c.get("do_siret")),
        ("Adresse donneur d’ordre", f"{c.get('do_adresse','')} {c.get('do_cp','')} {c.get('do_ville','')}"),
        ("Signataire", f"{c.get('do_signataire_civilite','')} {c.get('do_signataire_prenom','')} {c.get('do_signataire_nom','')} – {c.get('do_signataire_fonction','')} – {c.get('do_signataire_email','')}"),
        ("Facturation", c.get("facturation_details")),
    ])
    sec("3. Situation professionnelle", [("Statut", s.get("statut")), ("Poste", s.get("poste")), ("Employeur", s.get("employeur")), ("Ancienneté", s.get("anciennete")), ("Contexte", s.get("contexte"))])
    sec("4. Demande et besoin", [("Origine de la demande", d.get("origine_demande")), ("Pourquoi maintenant", d.get("pourquoi_maintenant")), ("Attentes", d.get("attentes")), ("Premières pistes", d.get("pistes")), ("Difficultés / contraintes", d.get("difficultes_contraintes")), ("Niveau d’avancement", d.get("niveau_avancement")), ("Reformulation partagée", d.get("reformulation_partagee"))])
    sec("5. Objectifs co-définis", [("Objectifs", o.get("objectifs_codefinis")), ("Critères de réussite", o.get("criteres_reussite")), ("Bilan adapté ?", o.get("bilan_adapte")), ("Réorientation éventuelle", o.get("reorientation"))])
    sec("6. Modalités", [("Format", m.get("format")), ("Période", m.get("periode_previsionnelle")), ("Volume total", m.get("volume_total")), ("Rythme", m.get("rythme")), ("Outils envisagés", ", ".join(m.get("outils_envisages", []))), ("Aménagements", m.get("amenagements"))])
    sec("7. Consentement", [
        ("Volontariat", "Oui" if k.get("volontaire") else "Non"), ("Confidentialité expliquée", "Oui" if k.get("confidentialite_expliquee") else "Non"),
        ("RGPD expliqué", "Oui" if k.get("rgpd_explique") else "Non"), ("Modalités comprises", "Oui" if k.get("modalites_comprises") else "Non"),
        ("Accord pour poursuivre", "Oui" if k.get("accord_poursuite") else "Non"), ("Observations", k.get("observations")),
    ])
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("Document de travail interne et confidentiel. Les informations recueillies doivent présenter un lien direct et nécessaire avec l’objet du bilan de compétences. Cette fiche prépare la contractualisation ; elle ne remplace pas le contrat ou la convention applicable.", styles["C360Small"]))
    story.append(Paragraph(f"{CLARTE360_LEGAL['raison_sociale']} {CLARTE360_LEGAL['forme']} – {CLARTE360_LEGAL['adresse']}, {CLARTE360_LEGAL['code_postal_ville']} – SIRET {CLARTE360_LEGAL['siret']}", styles["C360Small"]))
    doc.build(story)
    return buff.getvalue()


def auth_gate():
    configured = clean_text(secret("security", "admin_password", ""))
    if not configured:
        st.warning("Mode développement : aucun mot de passe consultant n’est configuré. Sur le VPS, renseigner [security].admin_password dans le fichier central de Secrets.")
        return True
    if st.session_state.get("consultant_authenticated"):
        return True
    st.image(str(LOGO_PATH), width=88) if LOGO_PATH.exists() else None
    st.title(APP_FULL_NAME)
    st.markdown("Accès réservé au consultant Clarté360.")
    pwd = st.text_input("Mot de passe consultant", type="password")
    if st.button("Se connecter", type="primary"):
        if pwd == configured:
            st.session_state.consultant_authenticated = True
            st.rerun()
        st.error("Mot de passe incorrect.")
    return False


def current_payload():
    return st.session_state.get("payload")


def ensure_current():
    if "payload" not in st.session_state:
        st.session_state.payload = None


def section_header(title, help_text=None):
    st.header(title)
    if help_text:
        st.markdown(f'<div class="clarte-box">{help_text}</div>', unsafe_allow_html=True)


def save_form(section_key, values, message="Informations enregistrées."):
    p = current_payload()
    p[section_key] = values
    save_payload(p, event=f"maj_{section_key}")
    st.success(message)


def sidebar(p):
    if LOGO_PATH.exists():
        st.sidebar.image(str(LOGO_PATH), width=75)
    st.sidebar.markdown("### Clarté360")
    if p:
        b = p.get("beneficiaire", {})
        display = " ".join([clean_text(b.get("prenom")), clean_text(b.get("nom"))]).strip() or "Dossier sans nom"
        st.sidebar.caption(display)
        pct = completion_pct(p)
        st.sidebar.progress(pct / 100)
        st.sidebar.caption(f"Complétude contractuelle : {pct}%")
        page = st.sidebar.radio("Navigation", SECTIONS, key="nav")
        if st.sidebar.button("Fermer le dossier"):
            st.session_state.payload = None
            st.session_state.nav = "Accueil"
            st.rerun()
        return page
    return "Accueil"


init_db()
ensure_current()
if not auth_gate():
    st.stop()

page = sidebar(current_payload())
p = current_payload()

if page == "Accueil":
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=95)
    st.title(APP_FULL_NAME)
    st.markdown("**Grille d’analyse partagée de la situation (APS) – Phase préliminaire du bilan de compétences.**")
    st.markdown(
        '<div class="clarte-box">Cette application sert à conduire et tracer le premier entretien : analyser la demande et le besoin, vérifier l’adéquation du bilan, préparer un programme personnalisé, définir les modalités et réunir les données nécessaires à la contractualisation.</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Nouveau dossier", type="primary", use_container_width=True):
            did = str(uuid.uuid4())
            st.session_state.payload = empty_payload(did)
            save_payload(st.session_state.payload, event="creation_dossier")
            st.session_state.nav = "1. Identité"
            st.rerun()
    rows = list_dossiers()
    with c2:
        st.metric("Dossiers enregistrés", len(rows))
    st.subheader("Reprendre un dossier")
    if not rows:
        st.info("Aucun dossier enregistré.")
    else:
        labels = [f"{r['beneficiary_name'] or 'Sans nom'} — {r['beneficiary_email'] or 'sans e-mail'} — {r['updated_at'][:16].replace('T',' ')} — {r['dossier_id'][:8]}" for r in rows]
        selected = st.selectbox("Dossier", range(len(rows)), format_func=lambda i: labels[i])
        a, b = st.columns([3,1])
        with a:
            if st.button("Ouvrir le dossier", use_container_width=True):
                st.session_state.payload = load_payload(rows[selected]["dossier_id"])
                st.session_state.nav = "1. Identité"
                st.rerun()
        with b:
            if st.button("Supprimer", use_container_width=True):
                st.session_state.confirm_delete = rows[selected]["dossier_id"]
        if st.session_state.get("confirm_delete"):
            st.error("La suppression est définitive.")
            if st.button("Confirmer la suppression"):
                delete_dossier(st.session_state.confirm_delete)
                st.session_state.confirm_delete = None
                st.rerun()
    st.caption(f"Stockage : {db_path()}")
    st.stop()

if not p:
    st.warning("Aucun dossier ouvert.")
    st.stop()

if page == "1. Identité":
    section_header("1. Identité et coordonnées du bénéficiaire", "Recueillir uniquement les données utiles à la prestation et à la contractualisation. Les questions personnelles sans lien direct et nécessaire avec le bilan sont exclues.")
    v = p.get("beneficiaire", {})
    with st.form("identity"):
        c1,c2,c3 = st.columns([1,2,2])
        civilite = c1.selectbox("Civilité", ["", "Madame", "Monsieur", "Autre / non précisé"], index=max(0,["", "Madame", "Monsieur", "Autre / non précisé"].index(v.get("civilite","")) if v.get("civilite","") in ["", "Madame", "Monsieur", "Autre / non précisé"] else 0))
        prenom = c2.text_input("Prénom *", v.get("prenom",""))
        nom = c3.text_input("Nom *", v.get("nom",""))
        nom_naissance = st.text_input("Nom de naissance (si nécessaire pour le contrat)", v.get("nom_naissance",""))
        c1,c2 = st.columns(2)
        date_naissance = c1.date_input("Date de naissance *", value=date.fromisoformat(v["date_naissance"]) if v.get("date_naissance") else None, format="DD/MM/YYYY")
        nationalite = c2.text_input("Nationalité (facultatif, uniquement si nécessaire au dossier)", v.get("nationalite",""))
        adresse = st.text_input("Adresse *", v.get("adresse",""))
        complement = st.text_input("Complément d’adresse", v.get("complement_adresse",""))
        c1,c2,c3 = st.columns([1,2,2])
        cp = c1.text_input("Code postal *", v.get("code_postal",""))
        ville = c2.text_input("Ville *", v.get("ville",""))
        pays = c3.text_input("Pays *", v.get("pays","France"))
        c1,c2 = st.columns(2)
        email = c1.text_input("E-mail personnel *", v.get("email",""))
        telephone = c2.text_input("Téléphone *", v.get("telephone",""))
        preferred = st.selectbox("Canal de contact préféré", ["E-mail", "Téléphone", "SMS"], index=["E-mail", "Téléphone", "SMS"].index(v.get("canal_contact","E-mail")) if v.get("canal_contact","E-mail") in ["E-mail", "Téléphone", "SMS"] else 0)
        submitted = st.form_submit_button("Enregistrer l’identité", type="primary")
    if submitted:
        if email and not valid_email(email): st.error("L’adresse e-mail semble invalide.")
        else:
            save_form("beneficiaire", {"civilite":civilite,"prenom":prenom,"nom":nom,"nom_naissance":nom_naissance,"date_naissance":date_naissance.isoformat() if date_naissance else "","nationalite":nationalite,"adresse":adresse,"complement_adresse":complement,"code_postal":cp,"ville":ville,"pays":pays,"email":email,"telephone":telephone,"canal_contact":preferred})

elif page == "2. Cadre contractuel":
    section_header("2. Cadre contractuel et donneur d’ordre", "Cette partie rassemble les informations administratives nécessaires pour préparer ensuite le bon document : contrat avec le bénéficiaire, convention avec un donneur d’ordre ou convention tripartite.")
    v = p.get("contractualisation", {})
    options = ["", "Contrat individuel avec le bénéficiaire", "Convention avec entreprise / donneur d’ordre", "Convention tripartite Clarté360 / donneur d’ordre / bénéficiaire", "Financeur institutionnel / autre donneur d’ordre"]
    with st.form("contract"):
        tc = st.selectbox("Cadre envisagé *", options, index=options.index(v.get("type_contrat","")) if v.get("type_contrat","") in options else 0)
        financeur = st.selectbox("Financeur / payeur principal *", ["", "Bénéficiaire", "Employeur", "CPF / Caisse des Dépôts", "France Travail", "OPCO", "Autre financeur"], index=(["", "Bénéficiaire", "Employeur", "CPF / Caisse des Dépôts", "France Travail", "OPCO", "Autre financeur"].index(v.get("financeur","")) if v.get("financeur","") in ["", "Bénéficiaire", "Employeur", "CPF / Caisse des Dépôts", "France Travail", "OPCO", "Autre financeur"] else 0))
        ref = st.text_input("Référence dossier / bon de commande / prise en charge", v.get("reference_commande",""))
        st.markdown("#### Donneur d’ordre / entreprise / financeur (si applicable)")
        c1,c2 = st.columns(2)
        rs = c1.text_input("Raison sociale", v.get("do_raison_sociale",""))
        forme = c2.text_input("Forme juridique", v.get("do_forme_juridique",""))
        c1,c2 = st.columns(2)
        siret = c1.text_input("SIRET / identifiant légal", v.get("do_siret",""))
        tva = c2.text_input("N° TVA intracommunautaire", v.get("do_tva",""))
        do_adresse = st.text_input("Adresse du donneur d’ordre", v.get("do_adresse",""))
        c1,c2,c3 = st.columns([1,2,2])
        do_cp = c1.text_input("Code postal", v.get("do_cp",""))
        do_ville = c2.text_input("Ville", v.get("do_ville",""))
        do_pays = c3.text_input("Pays", v.get("do_pays","France"))
        st.markdown("#### Personne habilitée à signer")
        c1,c2,c3 = st.columns([1,2,2])
        sc = c1.selectbox("Civilité signataire", ["", "Madame", "Monsieur"], index=["", "Madame", "Monsieur"].index(v.get("do_signataire_civilite","")) if v.get("do_signataire_civilite","") in ["", "Madame", "Monsieur"] else 0)
        sp = c2.text_input("Prénom", v.get("do_signataire_prenom",""))
        sn = c3.text_input("Nom", v.get("do_signataire_nom",""))
        sf = st.text_input("Fonction du signataire", v.get("do_signataire_fonction",""))
        c1,c2 = st.columns(2)
        se = c1.text_input("E-mail du signataire", v.get("do_signataire_email",""))
        stp = c2.text_input("Téléphone du signataire", v.get("do_signataire_telephone",""))
        st.markdown("#### Facturation")
        fact_contact = st.text_input("Contact facturation / comptabilité", v.get("facturation_contact",""))
        fact_email = st.text_input("E-mail facturation", v.get("facturation_email",""))
        fact_details = st.text_area("Consignes particulières de facturation", v.get("facturation_details",""), height=80)
        submitted = st.form_submit_button("Enregistrer le cadre contractuel", type="primary")
    if submitted:
        third = tc in options[2:]
        errs=[]
        if third and not rs: errs.append("Raison sociale du donneur d’ordre manquante.")
        if siret and do_pays.lower() == "france" and not valid_siret(siret): errs.append("Le SIRET français doit comporter 14 chiffres.")
        if se and not valid_email(se): errs.append("E-mail du signataire invalide.")
        if fact_email and not valid_email(fact_email): errs.append("E-mail de facturation invalide.")
        if errs:
            for e in errs: st.error(e)
        else:
            save_form("contractualisation", {"type_contrat":tc,"financeur":financeur,"reference_commande":ref,"do_raison_sociale":rs,"do_forme_juridique":forme,"do_siret":siret,"do_tva":tva,"do_adresse":do_adresse,"do_cp":do_cp,"do_ville":do_ville,"do_pays":do_pays,"do_signataire_civilite":sc,"do_signataire_prenom":sp,"do_signataire_nom":sn,"do_signataire_fonction":sf,"do_signataire_email":se,"do_signataire_telephone":stp,"facturation_contact":fact_contact,"facturation_email":fact_email,"facturation_details":fact_details})

elif page == "3. Situation professionnelle":
    section_header("3. Situation professionnelle actuelle", "L’objectif est de comprendre le contexte de la demande sans commencer prématurément la phase d’investigation.")
    v=p.get("situation_professionnelle",{})
    statuses=["", "Salarié(e) CDI", "Salarié(e) CDD", "Agent public", "Indépendant(e) / dirigeant(e)", "Demandeur / demandeuse d’emploi", "En transition / préavis / rupture", "Autre"]
    with st.form("situation"):
        statut=st.selectbox("Situation actuelle *",statuses,index=statuses.index(v.get("statut","")) if v.get("statut","") in statuses else 0)
        c1,c2=st.columns(2)
        poste=c1.text_input("Poste / métier actuel",v.get("poste",""))
        employeur=c2.text_input("Employeur / organisation",v.get("employeur",""))
        c1,c2=st.columns(2)
        anciennete=c1.text_input("Ancienneté dans le poste / l’entreprise",v.get("anciennete",""))
        secteur=c2.text_input("Secteur d’activité",v.get("secteur",""))
        contexte=st.text_area("Contexte professionnel utile à la compréhension de la demande",v.get("contexte",""),height=120)
        echeance=st.text_area("Échéance ou événement particulier à prendre en compte (facultatif)",v.get("echeance",""),height=80)
        submitted=st.form_submit_button("Enregistrer la situation",type="primary")
    if submitted: save_form("situation_professionnelle",{"statut":statut,"poste":poste,"employeur":employeur,"anciennete":anciennete,"secteur":secteur,"contexte":contexte,"echeance":echeance})

elif page == "4. Demande et besoin":
    section_header("4. Analyse de la demande et du besoin", "Questionnement ouvert, reformulation, neutralité et absence de conseil prématuré. La grille doit permettre de vérifier que le bilan constitue une réponse adaptée.")
    v=p.get("demande_besoin",{})
    with st.form("need"):
        origine=st.text_area("Qu’est-ce qui vous amène à envisager un bilan de compétences aujourd’hui ? *",v.get("origine_demande",""),height=100)
        why=st.text_area("Pourquoi maintenant ? *",v.get("pourquoi_maintenant",""),height=90)
        initiative=st.selectbox("À l’initiative de qui ?",["Bénéficiaire", "Employeur", "Conseil d’un tiers", "France Travail / CEP", "Autre"],index=["Bénéficiaire", "Employeur", "Conseil d’un tiers", "France Travail / CEP", "Autre"].index(v.get("initiative","Bénéficiaire")) if v.get("initiative","Bénéficiaire") in ["Bénéficiaire", "Employeur", "Conseil d’un tiers", "France Travail / CEP", "Autre"] else 0)
        attentes=st.text_area("À la fin du bilan, qu’aimeriez-vous avoir clarifié, décidé ou construit ? *",v.get("attentes",""),height=100)
        pistes=st.text_area("Avez-vous déjà une ou plusieurs pistes professionnelles ?",v.get("pistes",""),height=90)
        diffc=st.text_area("Quelles difficultés, contraintes ou incertitudes souhaitez-vous prendre en compte ?",v.get("difficultes_contraintes",""),height=100)
        niv=st.select_slider("Où en êtes-vous aujourd’hui dans votre réflexion ?",options=["Je commence à me questionner","J’ai quelques idées","J’ai plusieurs pistes","J’ai un projet à vérifier","J’ai un projet déjà avancé"],value=v.get("niveau_avancement","J’ai quelques idées") if v.get("niveau_avancement") in ["Je commence à me questionner","J’ai quelques idées","J’ai plusieurs pistes","J’ai un projet à vérifier","J’ai un projet déjà avancé"] else "J’ai quelques idées")
        reform=st.text_area("Reformulation partagée de la demande (à valider avec le bénéficiaire)",v.get("reformulation_partagee",""),height=110,help="Formuler avec les mots du bénéficiaire ce qu’il attend du bilan.")
        submitted=st.form_submit_button("Enregistrer l’analyse",type="primary")
    if submitted: save_form("demande_besoin",{"origine_demande":origine,"pourquoi_maintenant":why,"initiative":initiative,"attentes":attentes,"pistes":pistes,"difficultes_contraintes":diffc,"niveau_avancement":niv,"reformulation_partagee":reform})

elif page == "5. Objectifs du bilan":
    section_header("5. Co-définition des objectifs et adéquation du bilan", "Les objectifs doivent être opérationnels, personnalisés et issus de l’analyse partagée. L’outil ne doit pas imposer un parcours standard.")
    v=p.get("objectifs",{})
    with st.form("obj"):
        objs=st.text_area("Objectifs co-définis du bilan *",v.get("objectifs_codefinis",""),height=150,placeholder="Ex. clarifier un projet d’évolution, identifier des scénarios réalistes, analyser les compétences transférables...")
        crit=st.text_area("Comment saurons-nous, à la fin, que le bilan vous a été utile ?",v.get("criteres_reussite",""),height=100)
        adapted=st.radio("Le bilan de compétences paraît-il adapté à la demande ?",["Oui", "Oui, sous réserve d’ajustements", "Non / réorientation nécessaire"],index=["Oui", "Oui, sous réserve d’ajustements", "Non / réorientation nécessaire"].index(v.get("bilan_adapte","Oui")) if v.get("bilan_adapte","Oui") in ["Oui", "Oui, sous réserve d’ajustements", "Non / réorientation nécessaire"] else 0)
        reorient=st.text_area("Réorientation, réserve ou point à clarifier",v.get("reorientation",""),height=90)
        submitted=st.form_submit_button("Enregistrer les objectifs",type="primary")
    if submitted: save_form("objectifs",{"objectifs_codefinis":objs,"criteres_reussite":crit,"bilan_adapte":adapted,"reorientation":reorient})

elif page == "6. Format et modalités":
    section_header("6. Format, rythme et programme personnalisé", "Déterminer conjointement les modalités : présentiel, distanciel ou hybride ; rythme ; période ; moyens ; éventuels aménagements. Les outils sont proposés comme des moyens au service du projet.")
    v=p.get("modalites",{})
    with st.form("modal"):
        fmt=st.selectbox("Format *",["", "Présentiel", "Distanciel synchrone", "Hybride"],index=["", "Présentiel", "Distanciel synchrone", "Hybride"].index(v.get("format","")) if v.get("format","") in ["", "Présentiel", "Distanciel synchrone", "Hybride"] else 0)
        lieu=st.text_input("Lieu / adresse ou outil de visioconférence",v.get("lieu",""))
        periode=st.text_input("Période prévisionnelle de réalisation *",v.get("periode_previsionnelle",""),placeholder="Ex. septembre à novembre 2026")
        c1,c2=st.columns(2)
        volume=c1.text_input("Volume total envisagé",v.get("volume_total",""),placeholder="Ex. 18 h")
        rythme=c2.text_input("Rythme des entretiens",v.get("rythme",""),placeholder="Ex. 1 entretien / semaine")
        dispo=st.text_area("Disponibilités / contraintes horaires",v.get("disponibilites",""),height=80)
        autonomie=st.selectbox("Autonomie numérique",["À l’aise", "Besoin d’un accompagnement léger", "Besoin d’un accompagnement renforcé"],index=["À l’aise", "Besoin d’un accompagnement léger", "Besoin d’un accompagnement renforcé"].index(v.get("autonomie_numerique","À l’aise")) if v.get("autonomie_numerique","À l’aise") in ["À l’aise", "Besoin d’un accompagnement léger", "Besoin d’un accompagnement renforcé"] else 0)
        besoin_amenagement=st.radio("Un aménagement d’accessibilité est-il à prévoir ?",["Non", "Oui", "À préciser"],index=["Non", "Oui", "À préciser"].index(v.get("besoin_amenagement","Non")) if v.get("besoin_amenagement","Non") in ["Non", "Oui", "À préciser"] else 0,horizontal=True)
        amen=st.text_area("Aménagements utiles à la prestation (uniquement ce qui est nécessaire)",v.get("amenagements",""),height=80)
        selected=st.multiselect("Outils susceptibles d’être mobilisés",TOOLS,default=[x for x in v.get("outils_envisages",[]) if x in TOOLS])
        consultant=st.text_input("Consultant / accompagnateur pressenti",v.get("consultant",""))
        submitted=st.form_submit_button("Enregistrer les modalités",type="primary")
    if submitted: save_form("modalites",{"format":fmt,"lieu":lieu,"periode_previsionnelle":periode,"volume_total":volume,"rythme":rythme,"disponibilites":dispo,"autonomie_numerique":autonomie,"besoin_amenagement":besoin_amenagement,"amenagements":amen,"outils_envisages":selected,"consultant":consultant})

elif page == "7. Consentement et confidentialité":
    section_header("7. Volontariat, information et consentement", "Avant contractualisation, vérifier la compréhension réelle du bénéficiaire : démarche volontaire, confidentialité, RGPD, trois phases, modalités de suivi et possibilité de suivi à six mois.")
    v=p.get("consentements",{})
    with st.form("consent"):
        volontaire=st.checkbox("Le bénéficiaire confirme entreprendre cette démarche volontairement. *",value=bool(v.get("volontaire")))
        conf=st.checkbox("La confidentialité des échanges, résultats détaillés et synthèse a été expliquée. *",value=bool(v.get("confidentialite_expliquee")))
        rgpd=st.checkbox("Les informations RGPD, les finalités du traitement et les règles de conservation ont été expliquées. *",value=bool(v.get("rgpd_explique")))
        phases=st.checkbox("Les trois phases du bilan et l’articulation entre temps synchrones, asynchrones et travail personnel ont été présentées.",value=bool(v.get("phases_expliquees")))
        suivi=st.checkbox("Le principe du suivi à six mois a été présenté.",value=bool(v.get("suivi_6_mois_explique")))
        rec=st.checkbox("Les modalités de réclamation / signalement d’une difficulté ont été présentées.",value=bool(v.get("reclamations_expliquees")))
        comp=st.checkbox("Le bénéficiaire indique avoir compris les modalités proposées. *",value=bool(v.get("modalites_comprises")))
        third=p.get("contractualisation",{}).get("type_contrat") in ["Convention avec entreprise / donneur d’ordre", "Convention tripartite Clarté360 / donneur d’ordre / bénéficiaire", "Financeur institutionnel / autre donneur d’ordre"]
        sep=st.checkbox("En présence d’un tiers, un consentement spécifique du bénéficiaire sera formalisé séparément.",value=bool(v.get("consentement_separe_si_tiers")),disabled=not third)
        accord=st.checkbox("Le bénéficiaire souhaite poursuivre et engager le bilan de compétences. *",value=bool(v.get("accord_poursuite")))
        obs=st.text_area("Questions, réserves ou observations du bénéficiaire",v.get("observations",""),height=100)
        datec=st.text_input("Date / heure de recueil",v.get("date_recueil",datetime.now().strftime("%d/%m/%Y %H:%M")))
        submitted=st.form_submit_button("Enregistrer les consentements",type="primary")
    if submitted:
        save_form("consentements",{"volontaire":volontaire,"confidentialite_expliquee":conf,"rgpd_explique":rgpd,"phases_expliquees":phases,"suivi_6_mois_explique":suivi,"reclamations_expliquees":rec,"modalites_comprises":comp,"consentement_separe_si_tiers":sep if third else False,"accord_poursuite":accord,"observations":obs,"date_recueil":datec})

elif page == "8. Synthèse et export":
    section_header("8. Synthèse de l’entretien et préparation de la contractualisation", "Cette page vérifie la complétude du dossier, permet de formaliser une synthèse interne et d’exporter les données nécessaires à la préparation du contrat ou de la convention.")
    checks=required_checks(p)
    pct=completion_pct(p)
    st.progress(pct/100)
    st.write(f"**Complétude : {pct}%**")
    for label, ok in checks.items():
        st.markdown(f"{'✅' if ok else '❌'} {label}")
    v=p.get("synthese",{})
    with st.form("summary"):
        resume=st.text_area("Synthèse interne de l’entretien",v.get("resume",""),height=160,placeholder="Synthèse factuelle : demande, besoin, objectifs, contraintes, modalités retenues, points de vigilance.")
        next_step=st.selectbox("Décision / prochaine étape",["Préparer le contrat / la convention", "Compléter l’analyse avant contractualisation", "Réorienter vers une autre prestation", "Ne pas poursuivre"],index=["Préparer le contrat / la convention", "Compléter l’analyse avant contractualisation", "Réorienter vers une autre prestation", "Ne pas poursuivre"].index(v.get("prochaine_etape","Préparer le contrat / la convention")) if v.get("prochaine_etape","Préparer le contrat / la convention") in ["Préparer le contrat / la convention", "Compléter l’analyse avant contractualisation", "Réorienter vers une autre prestation", "Ne pas poursuivre"] else 0)
        notes=st.text_area("Actions à réaliser avant démarrage",v.get("actions_avant_demarrage",""),height=100)
        submitted=st.form_submit_button("Enregistrer la synthèse",type="primary")
    if submitted:
        save_form("synthese",{"resume":resume,"prochaine_etape":next_step,"actions_avant_demarrage":notes})
        p["meta"]["status"]="pret_contractualisation" if next_step=="Préparer le contrat / la convention" and completion_pct(p)==100 else "brouillon"
        save_payload(p,event="statut_synthese")
    st.markdown("### Exports")
    b=p.get("beneficiaire",{})
    base=(clean_text(b.get("nom")) or "beneficiaire").lower().replace(" ","_")
    st.download_button("Télécharger le dossier JSON",data=json_bytes(p),file_name=f"clarte360_aps_{base}_{p['meta']['dossier_id'][:8]}.json",mime="application/json",use_container_width=True)
    st.download_button("Télécharger la fiche APS PDF",data=pdf_bytes(p),file_name=f"clarte360_aps_{base}_{p['meta']['dossier_id'][:8]}.pdf",mime="application/pdf",use_container_width=True)
    if pct<100:
        st.warning("Le dossier n’est pas encore complet pour la contractualisation. Les éléments manquants sont indiqués ci-dessus.")
    else:
        st.success("Le dossier contient les éléments administratifs et de phase préliminaire nécessaires pour préparer le document contractuel adapté.")

st.divider()
st.caption(f"{APP_FULL_NAME} — v{APP_VERSION} — Réf. dossier {p['meta']['dossier_id'][:8]} — Données confidentielles")
