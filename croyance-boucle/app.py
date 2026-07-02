import json
import html
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
APP_VERSION = "V1.1 — outil de séance accompagnateur"
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

    div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] {{
        background-color: #008b8b !important;
        border-color: #008b8b !important;
        color: white !important;
    }}
    div.stButton > button:hover, div.stDownloadButton > button:hover {{
        border-color: #006f6f !important;
        color: white !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: #008b8b !important;
        border-bottom-color: #008b8b !important;
    }}
    .loop-wrap {{position:relative; width:100%; max-width:920px; height:560px; margin:1rem auto 1.5rem auto;}}
    .loop-svg {{position:absolute; inset:0; width:100%; height:100%; z-index:1;}}
    .loop-node {{position:absolute; z-index:2; width:250px; min-height:105px; background:#ffffff; border:3px solid #008b8b; border-radius:18px; padding:14px; box-shadow:0 4px 14px rgba(0,0,0,.08);}}
    .loop-node-top {{left:50%; top:12px; transform:translateX(-50%);}}
    .loop-node-right {{right:5px; top:205px;}}
    .loop-node-bottom {{left:50%; bottom:15px; transform:translateX(-50%);}}
    .loop-node-left {{left:5px; top:205px;}}
    .loop-node-title {{font-size:.78rem; color:#008b8b; font-weight:800; text-transform:uppercase; letter-spacing:.03em; margin-bottom:8px;}}
    .loop-node-text {{font-size:1rem; line-height:1.25; color:#1f2937; white-space:pre-wrap;}}
    .loop-node-empty {{color:#6b7280; font-style:italic;}}
    .loop-center {{position:absolute; z-index:2; left:50%; top:49%; transform:translate(-50%,-50%); background:#e7f5f4; border:2px dashed #008b8b; color:#006f6f; border-radius:999px; padding:10px 18px; font-weight:700; text-align:center;}}

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
            "boucle": {
                "croyance": "",
                "comportement_actuel": "",
                "resultat_actuel": "",
                "renforcement": "",
            },
            "commentaire_seance": "",
            "concerne_tierce_personne": False,
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
        txt = c.get("phase_decouverte", {}).get("boucle", {}).get("croyance") or c.get("phase_decouverte", {}).get("formulation_exacte") or "Croyance à compléter"
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



def e(txt):
    return html.escape(str(txt or ""))


def loop_text(value):
    if value:
        return e(value)
    return "<span class='loop-node-empty'>À compléter</span>"


def render_current_loop_html(bcl):
    croyance = loop_text(bcl.get("croyance"))
    comportement = loop_text(bcl.get("comportement_actuel"))
    resultat = loop_text(bcl.get("resultat_actuel"))
    renforcement = loop_text(bcl.get("renforcement") or "Le résultat semble confirmer la croyance")
    return f"""
<div class="loop-wrap">
  <svg class="loop-svg" viewBox="0 0 920 560" preserveAspectRatio="none">
    <defs>
      <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,6 L9,3 z" fill="#008b8b" />
      </marker>
    </defs>
    <path d="M575 90 C735 95 805 145 798 217" fill="none" stroke="#008b8b" stroke-width="5" marker-end="url(#arrowhead)"/>
    <path d="M790 318 C760 445 650 500 575 493" fill="none" stroke="#008b8b" stroke-width="5" marker-end="url(#arrowhead)"/>
    <path d="M345 492 C190 492 110 430 125 318" fill="none" stroke="#008b8b" stroke-width="5" marker-end="url(#arrowhead)"/>
    <path d="M125 215 C115 105 270 76 345 88" fill="none" stroke="#008b8b" stroke-width="5" marker-end="url(#arrowhead)"/>
  </svg>
  <div class="loop-node loop-node-top"><div class="loop-node-title">1. Croyance</div><div class="loop-node-text">{croyance}</div></div>
  <div class="loop-node loop-node-right"><div class="loop-node-title">2. Comportement induit</div><div class="loop-node-text">{comportement}</div></div>
  <div class="loop-node loop-node-bottom"><div class="loop-node-title">3. Résultat actuel</div><div class="loop-node-text">{resultat}</div></div>
  <div class="loop-node loop-node-left"><div class="loop-node-title">4. Renforcement</div><div class="loop-node-text">{renforcement}</div></div>
  <div class="loop-center">La boucle se referme<br/>et se valide elle-même</div>
</div>
"""


def draw_current_loop(c):
    bcl = c.get("phase_decouverte", {}).get("boucle", {})
    st.markdown("### Boucle auto-validante actuelle")
    st.markdown(render_current_loop_html(bcl), unsafe_allow_html=True)


def draw_example_loop():
    example = {
        "croyance": "Je suis incapable de me faire de nouveaux amis.",
        "comportement_actuel": "Je reste souvent seul chez moi.",
        "resultat_actuel": "Solitude, tristesse, mauvaise estime personnelle.",
        "renforcement": "Je me dis : tu vois bien, je suis incapable de créer de nouveaux liens.",
    }
    with st.expander("Voir un exemple de boucle auto-validante", expanded=False):
        st.markdown(render_current_loop_html(example), unsafe_allow_html=True)
        st.caption("Exemple inspiré du support HEC : croyance → comportement → résultat → renforcement de la croyance.")

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
    st.markdown("## Phase 3 — Construire la boucle auto-validante")
    st.markdown(
        "<div class='brand-box'>En phase 3, l'objectif n'est pas de résoudre la croyance ni de la relier à un objectif de coaching. L'objectif est simplement de faire apparaître la boucle : la croyance exprimée, le comportement qu'elle provoque, le résultat obtenu, puis la manière dont ce résultat vient renforcer la croyance.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("### Consignes de réalisation")
    st.markdown("""
1. Notez la croyance exprimée par le coaché, avec ses mots.
2. Identifiez le comportement que cette croyance provoque ou entretient.
3. Notez le résultat actuel obtenu à cause de ce comportement.
4. Faites apparaître comment ce résultat confirme ou renforce la croyance de départ.

À ce stade, on reste dans la découverte. Le travail de sortie de boucle se fera plus tard, en phase 6, uniquement si l'accompagnateur décide que cette croyance est utile à travailler.
""")
    draw_example_loop()

    ph = c.setdefault("phase_decouverte", {})
    bcl = ph.setdefault("boucle", {})
    # Compatibilité avec les anciens JSON V1.0
    if not bcl.get("croyance") and ph.get("formulation_exacte"):
        bcl["croyance"] = ph.get("formulation_exacte", "")

    ph["date"] = str(st.date_input("Date de découverte", value=date.fromisoformat(ph.get("date") or str(date.today())), key=f"date_{c['id']}"))

    st.markdown("### Remplir la boucle")
    col1, col2 = st.columns(2)
    with col1:
        bcl["croyance"] = st.text_area("1. Croyance exprimée", value=bcl.get("croyance", ""), height=90, key=f"croy_{c['id']}", help="Écrire la phrase entendue, avec les mots du coaché.")
        bcl["resultat_actuel"] = st.text_area("3. Résultat actuel", value=bcl.get("resultat_actuel", ""), height=90, key=f"res_{c['id']}", help="Quel résultat ce comportement produit-il concrètement ?")
    with col2:
        bcl["comportement_actuel"] = st.text_area("2. Comportement induit par la croyance", value=bcl.get("comportement_actuel", ""), height=90, key=f"comp_{c['id']}", help="Que fait ou ne fait pas la personne à cause de cette croyance ?")
        bcl["renforcement"] = st.text_area("4. Renforcement de la croyance", value=bcl.get("renforcement", ""), height=90, key=f"renf_{c['id']}", help="En quoi le résultat obtenu donne-t-il raison à la croyance ?")

    draw_current_loop(c)

    with st.expander("Point d'attention accompagnateur", expanded=False):
        st.markdown("La boucle auto-validante convient aux croyances sur soi, sur les autres en général ou sur le monde. Si la croyance vise une personne précise, elle relève d'un autre outil HEC.")
        ph["concerne_tierce_personne"] = st.checkbox("Cette croyance vise une personne précise", value=bool(ph.get("concerne_tierce_personne", ph.get("validation", {}).get("concerne_tierce_personne", False))), key=f"tierce_{c['id']}")
        if ph.get("concerne_tierce_personne"):
            st.warning("Ne pas utiliser la boucle auto-validante pour une croyance portant sur une personne identifiée.")

    ph["commentaire_seance"] = st.text_area("Notes très brèves de séance (facultatif)", value=ph.get("commentaire_seance", ph.get("validation", {}).get("commentaire_consultant", "")), height=70, key=f"com_{c['id']}")
    c["statut"] = st.selectbox("Statut", STATUTS, index=STATUTS.index(c.get("statut", "Découverte")) if c.get("statut") in STATUTS else 0, key=f"stat_{c['id']}")
    if st.button("Enregistrer cette boucle", type="primary", key=f"save_disc_{c['id']}"):
        c["updated_at"] = now_iso()
        touch()
        st.success("Boucle enregistrée dans le JSON courant. Pensez à exporter le JSON général.")

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
    story.append(Paragraph("Notes de séance", styles["TealH2"]))
    story.append(Paragraph(paragraph_safe(ph.get("commentaire_seance", "")) or "Aucune note renseignée.", styles["Normal"]))
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
        bcl = ph.get("boucle", {})
        rows.append({
            "Statut": c.get("statut", ""),
            "Date": ph.get("date", ""),
            "Croyance": bcl.get("croyance") or ph.get("formulation_exacte", ""),
            "Comportement": bcl.get("comportement_actuel", ""),
            "Résultat actuel": bcl.get("resultat_actuel", ""),
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
