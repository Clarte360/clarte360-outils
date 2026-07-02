import json
import secrets
import string
from copy import deepcopy
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

APP_TITLE = "Clarté360 — Boucle auto-validante"
APP_VERSION = "V1.0 — outil de séance accompagnateur"
BRAND_COLOR = "#008b8b"
ACCENT = "#e7f5f4"
WARN = "#fff4e6"
DATA_SCHEMA_VERSION = "1.0"

# === CLARTE360_CONSULTANT_CODES_START ===
CONSULTANT_CODES = {
    "C360-7KQ4-P9XM": "",
    "C360-D2HF-8LQA": "",
    "C360-M6TZ-3RVC": "",
    "C360-X9PA-5WGN": "",
    "C360-B4NY-2KRD": "",
    "C360-Q8LC-6FHS": "",
    "C360-V3ME-9TZA": "",
    "C360-H7RS-4JQP": "",
    "C360-L5WD-8CBN": "",
    "C360-P2GK-7XMF": "",
    "C360-T9AV-3LQH": "",
    "C360-N6CJ-5RWP": "",
    "C360-F4XM-9DKE": "",
    "C360-R8QB-2VLS": "",
    "C360-K3HN-6ZTA": "",
    "C360-W5LP-4GRC": "",
    "C360-A9TD-7MFX": "",
    "C360-J2RV-8QNB": "",
    "C360-S6KC-3WPH": "",
    "C360-Z4QL-5TMD": "",
}
# === CLARTE360_CONSULTANT_CODES_END ===

TYPE_CROYANCE = [
    "Sur soi / identité",
    "Sur les autres en général",
    "Sur le monde",
    "A vérifier",
]
STATUTS = ["Découverte", "Validée", "A travailler en phase 6", "Travaillée", "Archivée"]

st.set_page_config(page_title=APP_TITLE, page_icon="🔁", layout="wide")

st.markdown(
    f"""
<style>
    .main-title {{color:{BRAND_COLOR}; font-weight:800;}}
    .brand-box {{background:{ACCENT}; border-left:6px solid {BRAND_COLOR}; padding:1rem; border-radius:12px; margin:.6rem 0;}}
    .warn-box {{background:{WARN}; border-left:6px solid #f0a000; padding:1rem; border-radius:12px; margin:.6rem 0;}}
    .mini-note {{font-size:.9rem; color:#555;}}
    .loop-card {{border:2px solid {BRAND_COLOR}; border-radius:18px; padding:1rem; background:white; text-align:center; min-height:108px;}}
    .loop-label {{font-size:.85rem; text-transform:uppercase; color:{BRAND_COLOR}; font-weight:700;}}
    .loop-content {{font-size:1rem; margin-top:.5rem;}}
    .arrow {{font-size:2rem; color:{BRAND_COLOR}; text-align:center; padding-top:1.5rem;}}
    .danger {{color:#b00020; font-weight:700;}}
</style>
""",
    unsafe_allow_html=True,
)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def make_id(prefix):
    return prefix + "_" + datetime.now().strftime("%Y%m%d%H%M%S") + "_" + secrets.token_hex(3)


def empty_store():
    return {
        "app": APP_TITLE,
        "schema_version": DATA_SCHEMA_VERSION,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "beneficiaires": [],
    }


def init_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "consultant_code" not in st.session_state:
        st.session_state.consultant_code = ""
    if "store" not in st.session_state:
        st.session_state.store = empty_store()
    if "selected_beneficiaire_id" not in st.session_state:
        st.session_state.selected_beneficiaire_id = None
    if "selected_croyance_id" not in st.session_state:
        st.session_state.selected_croyance_id = None
    if "last_export_hint" not in st.session_state:
        st.session_state.last_export_hint = "Aucune sauvegarde téléchargée pendant cette session."


def touch():
    st.session_state.store["updated_at"] = now_iso()


def json_bytes():
    touch()
    return json.dumps(st.session_state.store, ensure_ascii=False, indent=2).encode("utf-8")


def safe_name(prefix, ext):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.{ext}"


def auth_gate():
    if st.session_state.authenticated:
        return True
    st.markdown(f"<h1 class='main-title'>{APP_TITLE}</h1>", unsafe_allow_html=True)
    st.markdown(f"<div class='mini-note'>{APP_VERSION}</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='brand-box'>Cet outil est réservé à l'accompagnateur. Il sert à repérer, formaliser puis travailler en séance une boucle auto-validante liée à une croyance. Il ne s'agit pas d'un outil bénéficiaire autonome.</div>",
        unsafe_allow_html=True,
    )
    code = st.text_input("Code accompagnateur", type="password")
    if st.button("Entrer", type="primary"):
        if code.strip().upper() in CONSULTANT_CODES:
            st.session_state.authenticated = True
            st.session_state.consultant_code = code.strip().upper()
            st.rerun()
        else:
            st.error("Code accompagnateur incorrect.")
    return False


def header():
    st.markdown(f"<h1 class='main-title'>{APP_TITLE}</h1>", unsafe_allow_html=True)
    st.caption(APP_VERSION)
    c1, c2 = st.columns([3, 2])
    with c1:
        st.info("Pensez à exporter le JSON général avant de quitter. Streamlit conserve les données pendant la session, mais le fichier JSON reste votre sauvegarde de référence.")
    with c2:
        st.download_button("💾 Sauvegarder / exporter le JSON général", data=json_bytes(), file_name=safe_name("clarte360_croyances_general", "json"), mime="application/json", type="primary")


def sidebar():
    st.sidebar.markdown("## Sauvegarde")
    st.sidebar.download_button("Exporter JSON général", data=json_bytes(), file_name=safe_name("clarte360_croyances_general", "json"), mime="application/json")
    uploaded = st.sidebar.file_uploader("Importer JSON général", type=["json"])
    if uploaded is not None:
        try:
            loaded = json.loads(uploaded.read().decode("utf-8"))
            if "beneficiaires" not in loaded:
                st.sidebar.error("Ce fichier ne ressemble pas à un JSON général Clarté360 croyances.")
            else:
                st.session_state.store = loaded
                st.session_state.selected_beneficiaire_id = None
                st.session_state.selected_croyance_id = None
                st.sidebar.success("JSON importé.")
                st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Import impossible : {exc}")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Code actif : {st.session_state.consultant_code}")
    if st.sidebar.button("Verrouiller l'accès"):
        st.session_state.authenticated = False
        st.session_state.consultant_code = ""
        st.rerun()


def beneficiaire_label(b):
    dob = b.get("date_naissance", "")
    return f"{b.get('nom','').upper()} {b.get('prenom','')} — {dob}"


def get_beneficiaire(bid):
    for b in st.session_state.store.get("beneficiaires", []):
        if b.get("id") == bid:
            return b
    return None


def get_croyance(b, cid):
    if not b:
        return None
    for c in b.get("croyances", []):
        if c.get("id") == cid:
            return c
    return None


def add_beneficiaire_form():
    with st.expander("Ajouter un bénéficiaire", expanded=False):
        with st.form("new_beneficiaire"):
            c1, c2, c3 = st.columns(3)
            with c1:
                prenom = st.text_input("Prénom *")
            with c2:
                nom = st.text_input("Nom *")
            with c3:
                dob = st.date_input("Date de naissance *", value=date(1990, 1, 1), min_value=date(1920,1,1), max_value=date.today())
            email = st.text_input("Email (facultatif)")
            submitted = st.form_submit_button("Créer le bénéficiaire", type="primary")
        if submitted:
            if not prenom.strip() or not nom.strip():
                st.error("Merci de renseigner prénom et nom.")
            else:
                b = {
                    "id": make_id("ben"),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                    "prenom": prenom.strip(),
                    "nom": nom.strip(),
                    "date_naissance": str(dob),
                    "email": email.strip(),
                    "croyances": [],
                }
                st.session_state.store["beneficiaires"].append(b)
                st.session_state.selected_beneficiaire_id = b["id"]
                touch()
                st.success("Bénéficiaire ajouté.")
                st.rerun()


def select_beneficiaire():
    st.markdown("## 1. Bénéficiaire")
    add_beneficiaire_form()
    bens = st.session_state.store.get("beneficiaires", [])
    if not bens:
        st.warning("Aucun bénéficiaire dans le JSON général.")
        return None
    labels = {beneficiaire_label(b): b["id"] for b in bens}
    current = st.session_state.selected_beneficiaire_id
    default_index = 0
    if current:
        for i, bid in enumerate(labels.values()):
            if bid == current:
                default_index = i
                break
    chosen = st.selectbox("Sélectionner un bénéficiaire", list(labels.keys()), index=default_index)
    st.session_state.selected_beneficiaire_id = labels[chosen]
    b = get_beneficiaire(st.session_state.selected_beneficiaire_id)
    c1, c2, c3 = st.columns(3)
    c1.metric("Croyances", len(b.get("croyances", [])))
    c2.metric("Validées", sum(1 for c in b.get("croyances", []) if c.get("statut") in ["Validée", "A travailler en phase 6", "Travaillée"]))
    c3.metric("Travaillées", sum(1 for c in b.get("croyances", []) if c.get("statut") == "Travaillée"))
    with st.expander("Supprimer l'historique complet de ce bénéficiaire", expanded=False):
        st.markdown("<span class='danger'>Action irréversible dans le JSON courant.</span>", unsafe_allow_html=True)
        confirm = st.text_input("Pour confirmer, tapez SUPPRIMER", key="confirm_delete_benef")
        if st.button("Supprimer ce bénéficiaire et toutes ses croyances"):
            if confirm == "SUPPRIMER":
                st.session_state.store["beneficiaires"] = [x for x in bens if x.get("id") != b.get("id")]
                st.session_state.selected_beneficiaire_id = None
                st.session_state.selected_croyance_id = None
                touch()
                st.success("Bénéficiaire supprimé du JSON courant. Exportez le JSON si vous voulez conserver cette modification.")
                st.rerun()
            else:
                st.error("Confirmation incorrecte.")
    return b


def default_croyance():
    return {
        "id": make_id("cr"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "statut": "Découverte",
        "phase_decouverte": {
            "date": str(date.today()),
            "formulation_exacte": "",
            "contexte": "",
            "emotion": "",
            "objectif_lie": "",
            "type_croyance": "A vérifier",
            "validation": {
                "sur_quoi_base": "",
                "autres_personnes_pensent_differemment": "",
                "avis_personnel": "",
                "freine_objectif": False,
                "concerne_tierce_personne": False,
                "commentaire_consultant": "",
            },
            "boucle": {
                "croyance": "",
                "comportement_actuel": "",
                "resultat_actuel": "",
                "renforcement": "",
            },
        },
        "phase_action": {
            "selectionnee_phase6": False,
            "date_travail": "",
            "pourquoi_utile": "",
            "resultat_souhaite": "",
            "nouveau_comportement": "",
            "actions": [],
            "suivi": "",
        },
    }


def add_croyance(b):
    st.markdown("## 2. Ajouter une croyance découverte")
    st.markdown(
        "<div class='brand-box'>Pendant la phase de découverte, l'accompagnateur peut ajouter une croyance à tout moment. À ce stade, on la repère et on la formalise ; on ne cherche pas encore à la modifier.</div>",
        unsafe_allow_html=True,
    )
    if st.button("➕ Ajouter une nouvelle croyance découverte", type="primary"):
        c = default_croyance()
        b.setdefault("croyances", []).append(c)
        b["updated_at"] = now_iso()
        st.session_state.selected_croyance_id = c["id"]
        touch()
        st.rerun()


def select_croyance(b):
    croyances = b.get("croyances", [])
    if not croyances:
        st.info("Aucune croyance enregistrée pour ce bénéficiaire.")
        return None
    st.markdown("## 3. Sélectionner une croyance")
    labels = []
    for c in croyances:
        txt = c.get("phase_decouverte", {}).get("formulation_exacte") or c.get("phase_decouverte", {}).get("boucle", {}).get("croyance") or "Croyance à compléter"
        labels.append(f"[{c.get('statut','')}] {txt[:90]}")
    ids = [c["id"] for c in croyances]
    default_index = 0
    if st.session_state.selected_croyance_id in ids:
        default_index = ids.index(st.session_state.selected_croyance_id)
    idx = st.selectbox("Croyance", range(len(labels)), format_func=lambda i: labels[i], index=default_index)
    st.session_state.selected_croyance_id = ids[idx]
    return get_croyance(b, ids[idx])


def flow_box(label, content):
    st.markdown(
        f"<div class='loop-card'><div class='loop-label'>{label}</div><div class='loop-content'>{content or 'À compléter'}</div></div>",
        unsafe_allow_html=True,
    )


def arrow(text="↓"):
    st.markdown(f"<div class='arrow'>{text}</div>", unsafe_allow_html=True)


def draw_current_loop(c):
    bcl = c.get("phase_decouverte", {}).get("boucle", {})
    st.markdown("### Boucle auto-validante actuelle")
    col1, col2, col3 = st.columns([1, 0.18, 1])
    with col1:
        flow_box("Croyance", bcl.get("croyance"))
    with col2:
        arrow("→")
    with col3:
        flow_box("Comportement actuel", bcl.get("comportement_actuel"))
    st.columns([0.44, 0.12, 0.44])[1].markdown("<div class='arrow'>↓</div>", unsafe_allow_html=True)
    col4, col5, col6 = st.columns([1, 0.18, 1])
    with col4:
        flow_box("Renforcement", bcl.get("renforcement") or "Le résultat semble confirmer la croyance")
    with col5:
        arrow("←")
    with col6:
        flow_box("Résultat actuel", bcl.get("resultat_actuel"))


def draw_exit_loop(c):
    act = c.get("phase_action", {})
    st.markdown("### Scénario de sortie de boucle")
    col1, col2, col3 = st.columns([1, 0.18, 1])
    with col1:
        flow_box("Résultat souhaité", act.get("resultat_souhaite"))
    with col2:
        arrow("←")
    with col3:
        flow_box("Nouveau comportement", act.get("nouveau_comportement"))
    st.markdown("<div class='brand-box'><strong>Logique HEC :</strong> pour agir sur la croyance, on travaille sur le comportement. Le nouveau comportement vise un résultat différent, capable de desserrer progressivement la boucle.</div>", unsafe_allow_html=True)


def edit_discovery(c):
    st.markdown("## Phase 3 — Repérer et formaliser la croyance")
    st.markdown(
        "<div class='brand-box'>Cette partie sert à clarifier une croyance apparue en séance. On vérifie qu'il s'agit bien d'une croyance sur soi, sur les autres en général ou sur le monde. Si la phrase concerne une tierce personne précise, elle ne relève pas de cet outil.</div>",
        unsafe_allow_html=True,
    )
    ph = c.setdefault("phase_decouverte", {})
    v = ph.setdefault("validation", {})
    bcl = ph.setdefault("boucle", {})

    ph["date"] = str(st.date_input("Date de découverte", value=date.fromisoformat(ph.get("date") or str(date.today())), key=f"date_{c['id']}"))
    ph["formulation_exacte"] = st.text_area("Formulation exacte entendue", value=ph.get("formulation_exacte", ""), height=80, key=f"form_{c['id']}")
    ph["contexte"] = st.text_area("Contexte dans lequel la croyance apparaît", value=ph.get("contexte", ""), height=80, key=f"ctx_{c['id']}")
    ph["emotion"] = st.text_input("Émotion / ressenti associé", value=ph.get("emotion", ""), key=f"emo_{c['id']}")
    ph["objectif_lie"] = st.text_input("Objectif ou demande auquel cela semble relié", value=ph.get("objectif_lie", ""), key=f"obj_{c['id']}")
    ph["type_croyance"] = st.selectbox("Type de croyance", TYPE_CROYANCE, index=TYPE_CROYANCE.index(ph.get("type_croyance", "A vérifier")) if ph.get("type_croyance") in TYPE_CROYANCE else 3, key=f"type_{c['id']}")

    st.markdown("### Questions fondamentales de validation")
    v["sur_quoi_base"] = st.text_area("Sur quoi vous basez-vous pour dire cela ?", value=v.get("sur_quoi_base", ""), key=f"base_{c['id']}")
    v["autres_personnes_pensent_differemment"] = st.text_area("D'après vous, est-ce que d'autres personnes pourraient penser différemment ?", value=v.get("autres_personnes_pensent_differemment", ""), key=f"diff_{c['id']}")
    v["avis_personnel"] = st.text_area("Et vous, qu'en pensez-vous vraiment ?", value=v.get("avis_personnel", ""), key=f"avis_{c['id']}")
    v["freine_objectif"] = st.checkbox("Cette croyance semble constituer un frein par rapport à l'objectif", value=bool(v.get("freine_objectif", False)), key=f"frein_{c['id']}")
    v["concerne_tierce_personne"] = st.checkbox("Attention : cette formulation concerne une tierce personne précise", value=bool(v.get("concerne_tierce_personne", False)), key=f"tierce_{c['id']}")
    if v.get("concerne_tierce_personne"):
        st.warning("Selon la logique HEC, la boucle auto-validante ne s'utilise pas si la croyance porte sur une tierce personne précise. Il faudra traiter ce cas avec un autre outil.")
    v["commentaire_consultant"] = st.text_area("Commentaire de l'accompagnateur", value=v.get("commentaire_consultant", ""), key=f"com_{c['id']}")

    st.markdown("### Construction de la boucle actuelle")
    bcl["croyance"] = st.text_area("Croyance", value=bcl.get("croyance") or ph.get("formulation_exacte", ""), height=70, key=f"croy_{c['id']}")
    bcl["comportement_actuel"] = st.text_area("Comportement actuel engendré par cette croyance", value=bcl.get("comportement_actuel", ""), height=80, key=f"comp_{c['id']}")
    bcl["resultat_actuel"] = st.text_area("Résultat actuel obtenu", value=bcl.get("resultat_actuel", ""), height=80, key=f"res_{c['id']}")
    bcl["renforcement"] = st.text_area("Comment le résultat renforce la croyance", value=bcl.get("renforcement", ""), height=80, key=f"renf_{c['id']}")
    draw_current_loop(c)

    c["statut"] = st.selectbox("Statut", STATUTS, index=STATUTS.index(c.get("statut", "Découverte")) if c.get("statut") in STATUTS else 0, key=f"stat_{c['id']}")
    if st.button("Enregistrer les modifications de cette croyance", type="primary", key=f"save_disc_{c['id']}"):
        c["updated_at"] = now_iso()
        touch()
        st.success("Croyance mise à jour dans le JSON courant. Pensez à exporter le JSON général.")


def action_table(c):
    act = c.setdefault("phase_action", {})
    actions = act.setdefault("actions", [])
    st.markdown("### Mini-plan d'action précis, factuel et daté")
    if st.button("Ajouter une action", key=f"addact_{c['id']}"):
        actions.append({"action":"", "date":"", "contexte":"", "indicateur":"", "obstacle":"", "solution":""})
        st.rerun()
    to_delete = None
    for i, a in enumerate(actions):
        with st.expander(f"Action {i+1} — {a.get('action') or 'à compléter'}", expanded=True):
            a["action"] = st.text_area("Action précise", value=a.get("action", ""), key=f"a_{c['id']}_{i}")
            col1, col2 = st.columns(2)
            with col1:
                a["date"] = st.text_input("Date / échéance", value=a.get("date", ""), key=f"d_{c['id']}_{i}")
                a["contexte"] = st.text_input("Où / avec qui / dans quel contexte ?", value=a.get("contexte", ""), key=f"ctxa_{c['id']}_{i}")
            with col2:
                a["indicateur"] = st.text_input("Comment saurai-je que c'est fait ?", value=a.get("indicateur", ""), key=f"ind_{c['id']}_{i}")
                a["obstacle"] = st.text_input("Obstacle possible", value=a.get("obstacle", ""), key=f"obs_{c['id']}_{i}")
            a["solution"] = st.text_input("Solution prévue si l'obstacle apparaît", value=a.get("solution", ""), key=f"sol_{c['id']}_{i}")
            if st.button("Supprimer cette action", key=f"del_{c['id']}_{i}"):
                to_delete = i
    if to_delete is not None:
        actions.pop(to_delete)
        st.rerun()


def edit_phase6(c):
    st.markdown("## Phase 6 — Sortir de la boucle par l'action")
    st.markdown(
        "<div class='brand-box'>Cette partie s'utilise lorsque l'accompagnateur décide qu'une croyance est utile à travailler parce qu'elle freine l'objectif. On ne cherche pas à convaincre le coaché que la croyance est fausse : on construit un comportement différent pour obtenir un résultat différent.</div>",
        unsafe_allow_html=True,
    )
    draw_current_loop(c)
    act = c.setdefault("phase_action", {})
    act["selectionnee_phase6"] = st.checkbox("Cette croyance est sélectionnée pour un travail en phase 6", value=bool(act.get("selectionnee_phase6", False)), key=f"sel6_{c['id']}")
    act["date_travail"] = str(st.date_input("Date du travail en phase 6", value=date.fromisoformat(act.get("date_travail") or str(date.today())), key=f"dt6_{c['id']}"))
    act["pourquoi_utile"] = st.text_area("Pourquoi cette croyance est utile à travailler maintenant ?", value=act.get("pourquoi_utile", ""), height=90, key=f"why6_{c['id']}")
    st.markdown("### Question centrale")
    st.markdown("<div class='warn-box'><strong>À votre avis, que pourriez-vous faire pour ne plus rester dans cette boucle ?</strong></div>", unsafe_allow_html=True)
    act["resultat_souhaite"] = st.text_area("Résultat souhaité en lieu et place du résultat actuel", value=act.get("resultat_souhaite", ""), height=90, key=f"rs6_{c['id']}")
    act["nouveau_comportement"] = st.text_area("Nouveau comportement à mettre en place immédiatement", value=act.get("nouveau_comportement", ""), height=90, key=f"nc6_{c['id']}")
    draw_exit_loop(c)
    action_table(c)
    act["suivi"] = st.text_area("Notes de suivi / débriefing ultérieur", value=act.get("suivi", ""), height=90, key=f"suivi_{c['id']}")
    if st.button("Enregistrer le travail de phase 6", type="primary", key=f"save6_{c['id']}"):
        c["statut"] = "Travaillée"
        c["updated_at"] = now_iso()
        touch()
        st.success("Travail enregistré dans le JSON courant. Pensez à exporter le JSON général.")


def paragraph_safe(txt):
    return (txt or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def build_pdf_for_croyance(b, c):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.3*cm, bottomMargin=1.3*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TealTitle", parent=styles["Title"], textColor=colors.HexColor(BRAND_COLOR), fontSize=20, leading=24))
    styles.add(ParagraphStyle(name="TealH2", parent=styles["Heading2"], textColor=colors.HexColor(BRAND_COLOR), fontSize=14))
    story = []
    story.append(Paragraph("Clarté360 — Boucle auto-validante", styles["TealTitle"]))
    story.append(Spacer(1, .2*cm))
    story.append(Paragraph(f"Bénéficiaire : {paragraph_safe(beneficiaire_label(b))}", styles["Normal"]))
    story.append(Paragraph(f"Date d'édition : {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, .4*cm))
    ph = c.get("phase_decouverte", {})
    bcl = ph.get("boucle", {})
    story.append(Paragraph("Phase 3 — Boucle actuelle", styles["TealH2"]))
    data = [
        ["Élément", "Contenu"],
        ["Croyance", paragraph_safe(bcl.get("croyance"))],
        ["Comportement actuel", paragraph_safe(bcl.get("comportement_actuel"))],
        ["Résultat actuel", paragraph_safe(bcl.get("resultat_actuel"))],
        ["Renforcement", paragraph_safe(bcl.get("renforcement"))],
    ]
    t = Table(data, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(BRAND_COLOR)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(t)
    story.append(Spacer(1, .4*cm))
    v = ph.get("validation", {})
    story.append(Paragraph("Questions de validation", styles["TealH2"]))
    for lab, key in [("Sur quoi vous basez-vous ?", "sur_quoi_base"),("D'autres pourraient penser différemment ?", "autres_personnes_pensent_differemment"),("Et vous, qu'en pensez-vous ?", "avis_personnel"),("Commentaire accompagnateur", "commentaire_consultant")]:
        story.append(Paragraph(f"<b>{lab}</b><br/>{paragraph_safe(v.get(key)) or 'Non renseigné'}", styles["Normal"]))
        story.append(Spacer(1, .15*cm))
    story.append(PageBreak())
    act = c.get("phase_action", {})
    story.append(Paragraph("Phase 6 — Scénario de sortie", styles["TealH2"]))
    data2 = [
        ["Élément", "Contenu"],
        ["Pourquoi travailler cette croyance", paragraph_safe(act.get("pourquoi_utile"))],
        ["Résultat souhaité", paragraph_safe(act.get("resultat_souhaite"))],
        ["Nouveau comportement", paragraph_safe(act.get("nouveau_comportement"))],
    ]
    t2 = Table(data2, colWidths=[5*cm, 11*cm])
    t2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(BRAND_COLOR)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(t2)
    story.append(Spacer(1, .4*cm))
    story.append(Paragraph("Plan d'action", styles["TealH2"]))
    actions = act.get("actions", [])
    if actions:
        tbl = [["Action", "Date", "Indicateur", "Obstacle / solution"]]
        for a in actions:
            tbl.append([paragraph_safe(a.get("action")), paragraph_safe(a.get("date")), paragraph_safe(a.get("indicateur")), paragraph_safe((a.get("obstacle") or "") + " / " + (a.get("solution") or ""))])
        tt = Table(tbl, colWidths=[5*cm, 2.5*cm, 4*cm, 4.5*cm])
        tt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(BRAND_COLOR)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.3,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP")]))
        story.append(tt)
    else:
        story.append(Paragraph("Aucune action renseignée.", styles["Normal"]))
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def exports_for_croyance(b, c):
    st.markdown("## 4. Exports")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Télécharger la fiche PDF de cette croyance", data=build_pdf_for_croyance(b, c), file_name=safe_name("clarte360_boucle_autovalidante", "pdf"), mime="application/pdf", type="primary")
    with col2:
        st.download_button("Exporter JSON général", data=json_bytes(), file_name=safe_name("clarte360_croyances_general", "json"), mime="application/json")


def croyance_list_table(b):
    rows = []
    for c in b.get("croyances", []):
        ph = c.get("phase_decouverte", {})
        rows.append({
            "Statut": c.get("statut", ""),
            "Date": ph.get("date", ""),
            "Croyance": ph.get("formulation_exacte") or ph.get("boucle", {}).get("croyance", ""),
            "Type": ph.get("type_croyance", ""),
            "Frein objectif": "Oui" if ph.get("validation", {}).get("freine_objectif") else "Non",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def main():
    init_state()
    if not auth_gate():
        return
    header()
    sidebar()
    b = select_beneficiaire()
    if not b:
        return
    croyance_list_table(b)
    add_croyance(b)
    c = select_croyance(b)
    if not c:
        return
    tabs = st.tabs(["Phase 3 — Découverte", "Phase 6 — Action", "PDF / JSON"])
    with tabs[0]:
        edit_discovery(c)
    with tabs[1]:
        edit_phase6(c)
    with tabs[2]:
        exports_for_croyance(b, c)


if __name__ == "__main__":
    main()
