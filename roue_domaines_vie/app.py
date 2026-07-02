import io
import json
import secrets
import string
from copy import deepcopy
from datetime import datetime, date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak

APP_TITLE = "Clarté360 - Roue des domaines de vie"
APP_VERSION = "V1.0"
BRAND_COLOR = "#008080"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "logo_clarte360.png"

DOMAINES = {
    "Professionnel": "Tout ce qui concerne le monde du travail : emploi, recherche d'emploi, activité professionnelle, projet professionnel, formation liée au travail, responsabilités professionnelles.",
    "Personnel": "Le temps passé avec soi-même : repos, santé, loisirs personnels, sport individuel, réflexion, solitude choisie, relation à soi.",
    "Familial": "La famille au sens large : enfants, parents, frères et sœurs, famille élargie, belle-famille, obligations ou présences familiales.",
    "Couple / intimité": "La relation avec la personne qui partage l'intimité. Ce domaine est distinct de la famille. Il peut être absent aujourd'hui et ne doit pas être forcé.",
    "Social / amitié": "Les relations hors famille, couple et travail : amis, voisins, vie associative, communauté, rencontres, activités collectives."
}
DEFAULT_ORDER = list(DOMAINES.keys())
DEFAULT_COLORS = ["#008080", "#F2C94C", "#EB5757", "#2F80ED", "#9B51E0", "#27AE60", "#F2994A"]

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


def empty_data():
    return {
        "app": APP_TITLE,
        "version": APP_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "beneficiaire": {"prenom":"", "nom":"", "email":"", "consultant":"", "date_realisation": str(date.today())},
        "access_code": "",
        "phase": 1,
        "actuel": {"domaines_presents": [], "valeurs": {}, "notes": {}},
        "debrief_actuel_termine": False,
        "ideal": {"domaines_presents": [], "valeurs": {}, "notes": {}},
        "ideal_valide": False,
        "comparaison": {"constats":"", "actions": []}
    }


def init_state():
    if "data" not in st.session_state:
        st.session_state.data = empty_data()
    if "code_verified" not in st.session_state:
        st.session_state.code_verified = False
    if "generated_code" not in st.session_state:
        st.session_state.generated_code = ""


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
        story.append(RLImage(str(LOGO_PATH), width=2.2*cm, height=2.2*cm))
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
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def access_gate():
    data = st.session_state.data
    if st.session_state.code_verified:
        return True
    st.markdown("## Accès bénéficiaire")
    st.markdown("<div class='brand-box'>Cet espace permet de préparer l'exercice de la roue des domaines de vie avec votre accompagnateur. Vos réponses restent sous votre contrôle : vous pouvez exporter le fichier JSON pour le conserver ou le transmettre à votre consultant.</div>", unsafe_allow_html=True)
    with st.form("identite"):
        c1, c2 = st.columns(2)
        with c1:
            prenom = st.text_input("Prénom *", value=data["beneficiaire"].get("prenom", ""))
            nom = st.text_input("Nom *", value=data["beneficiaire"].get("nom", ""))
            email = st.text_input("Email", value=data["beneficiaire"].get("email", ""))
        with c2:
            consultant = st.text_input("Consultant", value=data["beneficiaire"].get("consultant", "Clarté360"))
            d = st.date_input("Date de réalisation", value=date.today())
        submitted = st.form_submit_button("Générer le code d'accès", type="primary")
    if submitted:
        if not prenom.strip() or not nom.strip():
            st.error("Merci de renseigner au minimum le prénom et le nom.")
        else:
            code = generate_access_code()
            st.session_state.generated_code = code
            data["access_code"] = code
            data["beneficiaire"] = {"prenom": prenom.strip(), "nom": nom.strip(), "email": email.strip(), "consultant": consultant.strip(), "date_realisation": str(d)}
            st.success(f"Code généré : {code}")
            st.info("Dans cette version locale, le code est affiché directement. Dans une version administrateur, il pourra être généré côté consultant et transmis au bénéficiaire.")
    if st.session_state.generated_code:
        code_in = st.text_input("Saisir le code d'accès pour commencer", type="password")
        if st.button("Valider le code", type="primary"):
            if code_in.strip().upper() == st.session_state.generated_code:
                st.session_state.code_verified = True
                st.rerun()
            else:
                st.error("Code incorrect.")
    return False


def sidebar_tools():
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
    st.markdown("<div class='info-box'><strong>Important :</strong> seuls les domaines réellement présents doivent être retenus. Un domaine peut être absent aujourd'hui ou ne pas être souhaité dans l'idéal. Il n'y a aucune obligation de faire apparaître les cinq domaines.</div>", unsafe_allow_html=True)
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
    selected = domain_selector("actuel", "Roue actuelle")
    st.markdown("### Questions d'aide à la réflexion")
    st.markdown("""
- Quels domaines occupent beaucoup de temps concret dans votre semaine ?
- Quels domaines occupent peu de temps mais beaucoup de charge mentale ?
- Quels domaines reviennent souvent dans vos pensées, vos obligations ou vos préoccupations ?
- Y a-t-il un domaine absent aujourd'hui ? Dans ce cas, ne le forcez pas dans la roue actuelle.
""")
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
    st.download_button("Télécharger les données JSON", data=json_bytes(), file_name=safe_filename("roue_domaines_vie", "json"), mime="application/json")


def main():
    init_state()
    header()
    if not access_gate():
        return
    sidebar_tools()
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
