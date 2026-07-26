"""
APPLICATION CLARTE360 - RECHERCHE DES VALEURS

================================================================================
COMMENTAIRE IMPORTANT - REGLE FONDAMENTALE A CONSERVER DANS TOUTES LES VERSIONS
================================================================================
Cette application a un objectif unique : aider le beneficiaire a rechercher,
clarifier et valider ses valeurs fondamentales selon le referentiel RVC360.

Elle n'est pas un outil de coaching, un bilan de competences, un test de
personnalite, un outil d'orientation, ni un dispositif de conseil. Elle ne doit
jamais remplacer le consultant. Toute fonctionnalite qui ne contribue pas
strictement a la recherche des valeurs est hors perimetre et ne doit pas etre
integree.

La premiere valeur doit obligatoirement avoir ete identifiee et validee avec
l'accompagnateur avant l'utilisation de cette application. Si ce prerequis n'est
pas rempli, le parcours s'arrete.
================================================================================
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import smtplib
import ssl
import unicodedata
import uuid
from collections import Counter
from datetime import datetime, timedelta
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

APP_VERSION = "0.3.1"
APP_NAME = "Recherche de mes valeurs"
APP_FULL_NAME = f"Clarte360 - {APP_NAME}"
FRAMEWORK_VERSION = "4.0"
RVC360_VERSION = "1.1"
RGPD_VERSION = "RGPD-Clarte360-RVC360-v1.1-2026-07"
TEAL = "#008080"
LIGHT = "#E6F4F4"
TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
LOGO = BASE_DIR / "assets" / "site_icon.png"
REFERENTIEL_PATH = BASE_DIR / "data" / "referentiel_rvc360.xlsx"

FALLBACK_QUESTIONS = [
    "Racontez une situation, recente ou ancienne, dans laquelle vous vous etes senti pleinement en accord avec vous-meme. Qu'est-ce qui comptait particulierement pour vous ?",
    "Decrivez une situation qui vous a fait reagir fortement. Qu'est-ce qui vous a derange ou touche precisement ?",
    "Pensez a un choix difficile que vous assumez encore aujourd'hui. Qu'avez-vous voulu preserver ou privilegier ?",
    "Quelles personnes admirez-vous, et pour quelles raisons concretes ?",
    "Dans quelles situations vous sentez-vous le plus engage, vivant ou a votre place ?",
    "Qu'est-ce que vous ne seriez pas pret a sacrifier, meme pour davantage d'argent, de confort ou de reussite ?",
]

FORBIDDEN_PATTERNS = [
    r"\bvous etes\b",
    r"\bvotre personnalite\b",
    r"\bcela revele\b",
    r"\bcela cache\b",
    r"\bau fond de vous\b",
    r"\ben realite vous\b",
    r"\binconsciemment\b",
    r"\bprobablement parce que\b",
    r"\bvotre vraie valeur\b",
    r"\bvous souffrez de\b",
    r"\bcela prouve que\b",
    r"\bvotre peur montre\b",
    r"\bvotre colere signifie\b",
    r"\bvous cherchez a compenser\b",
]

SYSTEM_RVC360 = """
TU ES LE FACILITATEUR RVC360 DE CLARTE360.

MISSION UNIQUE
Aider le beneficiaire a rechercher ce qui compte fondamentalement pour lui, a clarifier ses propres mots et a examiner des termes du Referentiel des Valeurs Clarte360. Tu ne decides jamais de ses valeurs.

REGLE ABSOLUE : ZERO INTERPRETATION
Tu n'attribues jamais une cause, une intention, un besoin cache, un trait de personnalite, une emotion non declaree ou une valeur non validee. Tu ne transformes jamais un propos en diagnostic ou en verite sur la personne.

PERIMETRE
Tu ne fais ni coaching, ni bilan de competences, ni orientation, ni conseil, ni test de personnalite. Tu travailles exclusivement a la recherche des valeurs fondamentales.

METHODE
1. Pose une seule question ouverte a la fois.
2. Appuie-toi exclusivement sur les mots et faits explicitement exprimes.
3. Demande la signification personnelle des mots importants.
4. Reformule brievement puis demande confirmation.
5. Lorsque plusieurs termes RVC360 sont plausibles, presente-les ensemble avec leurs differences.
6. Justifie chaque hypothese par un extrait ou une reformulation factuelle de la reponse.
7. Dis clairement lorsque les informations sont insuffisantes.
8. Laisse le beneficiaire accepter, refuser, ajouter ou renommer librement.
9. Toute proposition reste une hypothese de mot a examiner.
10. Ne pose aucune question qui contienne le nom d'une valeur attendue.
11. Ne repete pas une question deja posee. Fais progresser l'exploration.
12. Si plusieurs situations suffisamment concretes ont ete explorees et plusieurs hypotheses etayees, indique que l'examen des mots peut commencer.

LANGAGE INTERDIT
"Vous etes...", "votre personnalite...", "cela revele...", "cela cache...", "au fond...", "en realite...", "inconsciemment...", "parce que vous avez probablement...", "votre vraie valeur est...".

LANGAGE AUTORISE
"Vous avez indique...", "est-ce fidele a ce que vous souhaitez dire ?", "plusieurs termes peuvent etre examines", "lequel correspond le mieux a votre sens personnel ?", "je ne dispose pas d'assez d'elements".

SORTIE
Retourne uniquement l'objet JSON conforme au schema demande. Aucun texte hors JSON.
"""

st.set_page_config(page_title=APP_FULL_NAME, page_icon=str(LOGO) if LOGO.exists() else "🧭", layout="centered")
st.markdown(
    f"""
<style>
h1,h2,h3{{color:{TEAL}}}
.stProgress>div>div>div>div{{background:{TEAL}}}
.clarte-box{{border-left:6px solid {TEAL};background:{LIGHT};padding:1rem 1.1rem;border-radius:.7rem;margin:.8rem 0;color:{TEXT}}}
.card{{border:1px solid #d5eaea;padding:1rem;border-radius:.8rem;background:white;margin:.6rem 0;box-shadow:0 1px 7px rgba(0,128,128,.07)}}
.muted{{color:#667;font-size:.92rem}}
div.stButton>button[kind="primary"]{{background:{TEAL};border-color:{TEAL}}}
</style>
""",
    unsafe_allow_html=True,
)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def clean_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()) or "beneficiaire"


@st.cache_data
def load_referentiel() -> list[dict[str, str]]:
    if not REFERENTIEL_PATH.exists():
        return []
    df = pd.read_excel(REFERENTIEL_PATH, sheet_name="Référentiel 240")
    df = df.rename(columns={"Code": "code", "Valeur": "nom", "Famille": "famille", "Définition Clarté360 - base de travail": "definition"})
    records: list[dict[str, str]] = []
    for _, row in df.iterrows():
        if pd.isna(row.get("nom")):
            continue
        records.append({
            "code": str(row.get("code", "")).strip(),
            "nom": str(row["nom"]).strip(),
            "famille": str(row.get("famille", "")).strip(),
            "definition": str(row.get("definition", "")).strip(),
        })
    return records


CATALOGUE = load_referentiel()
VALUE_MAP = {item["nom"]: item for item in CATALOGUE}
VALUE_NAMES = list(VALUE_MAP)


def init_state() -> None:
    defaults: dict[str, Any] = {
        "page": "Accueil", "consent": False, "verified": False, "code_hash": None,
        "code_expires": None, "identity": {}, "prerequisite_confirmed": False,
        "existing_values": [], "conversation": [], "current_question": FALLBACK_QUESTIONS[0],
        "candidate_names": [], "candidate_reasons": {}, "candidate_evidence": {},
        "validation": {}, "personal_defs": {}, "comments": {}, "discarded": [],
        "session_id": str(uuid.uuid4()), "started": now(), "last_activity": now(), "trace": [],
        "ai_calls": 0, "ai_input_tokens": 0, "ai_output_tokens": 0, "ai_engine_status": "non_verifie", "exploration_complete": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def trace(action: str, details: str = "") -> None:
    st.session_state.trace.append({"date": now(), "action": action, "details": details})
    st.session_state.last_activity = now()


def get_secret(section: str, key: str, default: Any = "") -> Any:
    try:
        return st.secrets.get(section, {}).get(key, default)
    except Exception:
        return default


def ai_ready() -> bool:
    return OpenAI is not None and bool(get_secret("openai", "api_key", os.environ.get("OPENAI_API_KEY", "")))


def api_client() -> OpenAI:
    key = get_secret("openai", "api_key", os.environ.get("OPENAI_API_KEY", ""))
    if OpenAI is None or not key:
        raise RuntimeError("La cle API OpenAI n'est pas configuree.")
    return OpenAI(api_key=key, timeout=35.0, max_retries=2)


def generate_code() -> str:
    return str(random.randint(100000, 999999))


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def local_master_ok(code: str) -> bool:
    return os.environ.get("CLARTE360_LOCAL") == "1" and bool(get_secret("security", "local_master_code", "")) and code == get_secret("security", "local_master_code", "")


def send_access_code(recipient: str, code: str) -> bool:
    host = get_secret("smtp", "host")
    port = int(get_secret("smtp", "port", 587))
    user = get_secret("smtp", "user")
    password = get_secret("smtp", "password")
    sender = get_secret("smtp", "sender", user)
    if not all([host, user, password, sender, recipient]):
        return False
    msg = EmailMessage()
    msg["Subject"] = f"Votre code d'acces {APP_NAME}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(f"Votre code d'acces temporaire est : {code}\n\nCe code expire dans 15 minutes.\nClarte360")
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls(context=context)
        server.login(user, password)
        server.send_message(msg)
    return True


def lexical_prefilter(texts: list[str], limit: int = 36) -> list[dict[str, str]]:
    """Selection locale deterministe : l'IA ne recoit qu'un sous-ensemble pertinent du referentiel."""
    corpus = normalize(" ".join(texts))
    tokens = [t for t in corpus.split() if len(t) >= 4]
    frequencies = Counter(tokens)
    scored: list[tuple[float, dict[str, str]]] = []
    for item in CATALOGUE:
        item_tokens = set(normalize(f"{item['nom']} {item['famille']} {item['definition']}").split())
        overlap = sum(frequencies[t] for t in item_tokens if t in frequencies)
        phrase_bonus = 4 if normalize(item["nom"]) in corpus else 0
        scored.append((overlap + phrase_bonus, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["nom"]))
    positive = [item for score, item in scored if score > 0][:limit]
    if len(positive) < 18:
        families_seen = {x["famille"] for x in positive}
        for _, item in scored:
            if item in positive:
                continue
            if item["famille"] not in families_seen or len(positive) < 18:
                positive.append(item)
                families_seen.add(item["famille"])
            if len(positive) >= limit:
                break
    return positive[:limit]


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reformulation": {"type": "string"},
        "question_suivante": {"type": "string"},
        "exploration_suffisante": {"type": "boolean"},
        "informations_insuffisantes": {"type": "boolean"},
        "hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string"},
                    "raison": {"type": "string"},
                    "preuve_textuelle": {"type": "string"},
                },
                "required": ["nom", "raison", "preuve_textuelle"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reformulation", "question_suivante", "exploration_suffisante", "informations_insuffisantes", "hypotheses"],
    "additionalProperties": False,
}


def response_json(instructions: str, payload: dict[str, Any], schema_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    client = api_client()
    model = get_secret("openai", "model", "gpt-5-mini")
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=json.dumps(payload, ensure_ascii=False),
        text={"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
        max_output_tokens=1200,
        store=False,
    )
    st.session_state.ai_calls += 1
    usage = getattr(response, "usage", None)
    if usage is not None:
        st.session_state.ai_input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
        st.session_state.ai_output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
    if getattr(response, "status", "completed") != "completed":
        raise RuntimeError("La reponse IA n'a pas ete terminee correctement.")
    output_text = (getattr(response, "output_text", "") or "").strip()
    if not output_text:
        raise RuntimeError("La reponse IA est vide.")
    return json.loads(output_text)


def has_forbidden_language(text: str) -> bool:
    normalized = normalize(text)
    return any(re.search(pattern, normalized) for pattern in FORBIDDEN_PATTERNS)


def sanitize_engine_result(result: dict[str, Any], allowed_names: set[str]) -> dict[str, Any]:
    clean = {
        "reformulation": str(result.get("reformulation", "")).strip(),
        "question_suivante": str(result.get("question_suivante", "")).strip(),
        "exploration_suffisante": bool(result.get("exploration_suffisante", False)),
        "informations_insuffisantes": bool(result.get("informations_insuffisantes", False)),
        "hypotheses": [],
    }
    for item in result.get("hypotheses", []):
        name = str(item.get("nom", "")).strip()
        if name not in allowed_names or name in st.session_state.existing_values:
            continue
        reason = str(item.get("raison", "")).strip()
        evidence = str(item.get("preuve_textuelle", "")).strip()
        if reason and evidence and not has_forbidden_language(reason + " " + evidence):
            clean["hypotheses"].append({"nom": name, "raison": reason, "preuve_textuelle": evidence})
    if has_forbidden_language(clean["reformulation"]):
        clean["reformulation"] = "Vous avez apporte de nouveaux elements. Verifiez ci-dessous les mots proposes et poursuivez l'exploration avec la question suivante."
    if has_forbidden_language(clean["question_suivante"]) or not clean["question_suivante"]:
        idx = min(len(st.session_state.conversation), len(FALLBACK_QUESTIONS) - 1)
        clean["question_suivante"] = FALLBACK_QUESTIONS[idx]
    return clean


def run_rvc360_engine(answer: str) -> dict[str, Any]:
    history = st.session_state.conversation[-10:]
    texts = [turn.get("answer", "") for turn in history] + [answer]
    shortlist = lexical_prefilter(texts)
    payload = {
        "valeurs_deja_identifiees_avec_accompagnateur": st.session_state.existing_values,
        "historique": history,
        "question_actuelle": st.session_state.current_question,
        "reponse_actuelle": answer,
        "catalogue_autorise": shortlist,
        "hypotheses_deja_proposees": st.session_state.candidate_names,
        "consigne": "Produire une reformulation factuelle courte, une seule question ouverte non suggestive, et au maximum 6 hypotheses lexicales etayees. Ne proposer que des noms presents dans catalogue_autorise.",
    }
    raw = response_json(SYSTEM_RVC360, payload, "rvc360_turn", RESPONSE_SCHEMA)
    return sanitize_engine_result(raw, {item["nom"] for item in shortlist})


def merge_hypotheses(items: list[dict[str, str]]) -> None:
    for item in items:
        name = item["nom"]
        if name not in st.session_state.candidate_names and name not in st.session_state.discarded:
            st.session_state.candidate_names.append(name)
        st.session_state.candidate_reasons[name] = item["raison"]
        st.session_state.candidate_evidence[name] = item["preuve_textuelle"]


def validate_value_record(name: str, source: str) -> dict[str, Any]:
    current = st.session_state.validation.get(name, {})
    return {
        "nom": name, "source": source,
        "importante": bool(current.get("importante", False)),
        "tres_importante": bool(current.get("tres_importante", False)),
        "fondamentale": bool(current.get("fondamentale", False)),
        "validee": bool(current.get("fondamentale", False)),
    }


def export_json() -> bytes:
    all_names = list(dict.fromkeys(st.session_state.existing_values + st.session_state.candidate_names))
    values = []
    for name in all_names:
        source = "seance" if name in st.session_state.existing_values else "application"
        values.append({
            **validate_value_record(name, source),
            "famille": VALUE_MAP.get(name, {}).get("famille", ""),
            "definition_clarte360": VALUE_MAP.get(name, {}).get("definition", ""),
            "definition_personnelle": st.session_state.personal_defs.get(name, ""),
            "commentaire": st.session_state.comments.get(name, ""),
            "raison_hypothese": st.session_state.candidate_reasons.get(name, ""),
            "preuve_textuelle": st.session_state.candidate_evidence.get(name, ""),
        })
    payload = {
        "application": APP_FULL_NAME, "version": APP_VERSION, "framework_version": FRAMEWORK_VERSION,
        "rvc360_version": RVC360_VERSION, "rgpd_version": RGPD_VERSION,
        "session_id": st.session_state.session_id, "identite": st.session_state.identity,
        "prerequis_premiere_valeur": st.session_state.prerequisite_confirmed,
        "conversation": st.session_state.conversation, "valeurs": values,
        "mots_ecartes": st.session_state.discarded, "trace": st.session_state.trace,
        "appels_ia": st.session_state.ai_calls, "tokens_entree_ia": st.session_state.ai_input_tokens, "tokens_sortie_ia": st.session_state.ai_output_tokens, "exporte_le": now(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def make_pdf() -> bytes:
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Teal", parent=styles["Heading1"], textColor=colors.HexColor(TEAL)))

    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(A4[0] / 2, 0.7 * cm, "Clarte360 - Referentiel RVC360 - Document confidentiel")
        canvas.drawRightString(A4[0] - 1.5 * cm, 0.7 * cm, f"Page {doc.page}"); canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.7 * cm, leftMargin=1.7 * cm, topMargin=1.7 * cm, bottomMargin=1.5 * cm)
    story = [Paragraph("RVC360 - Recherche de mes valeurs", styles["Teal"]), Paragraph("Rapport de recherche et de validation des valeurs fondamentales", styles["Normal"]), Spacer(1, 12)]
    if st.session_state.identity.get("nom"):
        story += [Paragraph(f"Beneficiaire : {st.session_state.identity['nom']}", styles["Normal"]), Spacer(1, 8)]
    names = list(dict.fromkeys(st.session_state.existing_values + st.session_state.candidate_names))
    validated = [n for n in names if st.session_state.validation.get(n, {}).get("fondamentale")]
    story += [Paragraph(f"Nombre de valeurs validees : {len(validated)}", styles["Heading2"]), Spacer(1, 8)]
    for idx, name in enumerate(validated, 1):
        info = VALUE_MAP.get(name, {})
        source = "Decouverte avec l'accompagnateur" if name in st.session_state.existing_values else "Recherchee avec l'application"
        story += [
            Paragraph(f"{idx}. {name}", styles["Heading2"]),
            Paragraph(f"Famille : {info.get('famille', '')}", styles["Normal"]),
            Paragraph(f"Origine : {source}", styles["Normal"]),
            Paragraph(f"Definition Clarte360 : {info.get('definition', '')}", styles["Normal"]),
            Paragraph(f"Definition personnelle : {st.session_state.personal_defs.get(name, '') or 'Non renseignee'}", styles["Normal"]),
            Paragraph("Validation : importante / tres importante / fondamentale", styles["Normal"]),
            Paragraph(f"Commentaire : {st.session_state.comments.get(name, '') or 'Aucun'}", styles["Normal"]), Spacer(1, 10),
        ]
    story += [PageBreak(), Paragraph("Utilisation ulterieure", styles["Heading2"]), Paragraph("Les valeurs validees peuvent maintenant etre utilisees dans la Boussole des valeurs professionnelles ou dans la Roue des valeurs Clarte360, selon le parcours d'accompagnement.", styles["Normal"]), Spacer(1, 12), Paragraph("Ce document ne constitue ni un diagnostic psychologique, ni un test de personnalite, ni une decision d'orientation. Les valeurs ont ete retenues et validees par le beneficiaire.", styles["Italic"])]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


init_state()
if st_autorefresh:
    st_autorefresh(interval=60000, key="heartbeat")

session_limit = int(get_secret("security", "session_limit_minutes", 15))
if st.session_state.verified:
    last = datetime.fromisoformat(st.session_state.last_activity)
    if datetime.now() - last > timedelta(minutes=session_limit):
        st.session_state.verified = False
        st.warning("La session a expire. Vous pouvez reprendre votre travail a partir de votre fichier JSON.")

with st.sidebar:
    if LOGO.exists(): st.image(str(LOGO), width=90)
    st.markdown("### Clarte360")
    if st.session_state.verified:
        for page_name in ["Accueil", "Prerequis", "Exploration IA", "Mots a examiner", "Validation", "Resultats"]:
            if st.button(page_name, use_container_width=True): st.session_state.page = page_name; st.rerun()
        st.divider()
        st.download_button("Sauvegarder mon travail (JSON)", export_json(), file_name=f"rvc360_{clean_name(st.session_state.identity.get('nom', 'beneficiaire'))}.json", mime="application/json", use_container_width=True)
    else:
        st.caption("Acces securise a l'outil")
    st.divider()
    if st.button("Contact", use_container_width=True): st.session_state.page = "Contact"; st.rerun()
    if st.button("Mentions legales", use_container_width=True): st.session_state.page = "Mentions"; st.rerun()
    st.caption(f"Version {APP_VERSION} - RVC360 {RVC360_VERSION}")

page = st.session_state.page
if page == "Contact":
    st.title("Contact"); st.write("Clarte360 - 60 rue Francois 1er - 75008 Paris"); st.write("contact@clarte360.com - 01 89 48 08 25"); st.stop()
if page == "Mentions":
    st.title("Mentions legales"); st.write("Clarte360 SAS - Capital social : 10 000 EUR - RCS Paris 102 349 834 - SIRET 102 349 834 00014 - TVA FR88102349834."); st.write("Les contenus, methodes, referentiels, applications et documents Clarte360 sont proteges."); st.stop()

if not st.session_state.verified:
    st.title(APP_NAME)
    st.markdown('<div class="clarte-box"><b>Objectif unique : rechercher et valider vos valeurs fondamentales.</b><br>Cette application ne fait ni coaching, ni diagnostic, ni orientation.</div>', unsafe_allow_html=True)
    with st.expander("Protection des donnees et place de l'intelligence artificielle", expanded=True):
        st.markdown("""Cette application est utilisee dans le cadre d'un accompagnement professionnel. Elle ne produit aucun diagnostic et ne prend aucune decision a votre place.\n\nLorsque l'intelligence artificielle est activee, les reponses utiles a la recherche de mots possibles sont transmises au service configure par Clarte360. Evitez de saisir des noms complets, coordonnees ou informations sensibles inutiles. L'application utilise `store=False`, afin de ne pas conserver la reponse comme etat applicatif OpenAI. Les traitements techniques et regles de conservation du fournisseur restent applicables.\n\nLes propositions de l'IA restent de simples hypotheses de mots a examiner. Vous seul pouvez retenir et valider une valeur.""")
    consent = st.checkbox("J'ai lu ces informations et j'accepte de poursuivre.")
    name = st.text_input("Votre prenom ou identifiant de travail")
    email = st.text_input("Votre adresse e-mail")
    if st.button("Recevoir mon code d'acces", type="primary", disabled=not (consent and name.strip() and email.strip())):
        code = generate_code(); st.session_state.code_hash = hash_code(code); st.session_state.code_expires = (datetime.now() + timedelta(minutes=15)).isoformat()
        st.session_state.consent = True; st.session_state.identity = {"nom": name.strip(), "email": email.strip()}; trace("consentement", RGPD_VERSION)
        try:
            sent = send_access_code(email.strip(), code)
        except Exception as exc:
            sent = False; trace("erreur_smtp", type(exc).__name__)
        if sent: st.success("Le code d'acces a ete envoye par e-mail.")
        elif os.environ.get("CLARTE360_LOCAL") == "1": st.success(f"Mode local : code temporaire {code}")
        else: st.error("L'envoi du code n'est pas configure. Verifiez les parametres SMTP dans les Secrets.")
    if st.session_state.code_hash:
        code_input = st.text_input("Code d'acces", type="password")
        if st.button("Entrer dans l'application", type="primary"):
            expired = not st.session_state.code_expires or datetime.now() > datetime.fromisoformat(st.session_state.code_expires)
            if local_master_ok(code_input) or (not expired and hash_code(code_input) == st.session_state.code_hash):
                st.session_state.verified = True; st.session_state.page = "Accueil"; trace("connexion"); st.rerun()
            st.error("Code incorrect ou expire.")
    st.stop()

if page == "Accueil":
    st.title(APP_NAME)
    st.markdown('<div class="clarte-box"><b>Les valeurs constituent votre colonne vertebrale psychique.</b><br>L\'application vous aide uniquement a rechercher les mots qui correspondent a ce qui compte fondamentalement pour vous.</div>', unsafe_allow_html=True)
    st.write("Le parcours commence obligatoirement apres l'identification d'au moins une premiere valeur avec votre accompagnateur. L'application vous aide ensuite a rechercher les autres valeurs, puis a les valider une par une.")
    if not CATALOGUE: st.error("Le referentiel RVC360 n'a pas pu etre charge.")
    if ai_ready(): st.success("Moteur IA RVC360 configure et disponible.")
    else: st.error("Le moteur IA RVC360 n'est pas configure. Cette version complete necessite une cle API OpenAI dans les Secrets.")
    if st.button("Commencer", type="primary", disabled=not (CATALOGUE and ai_ready())): st.session_state.page = "Prerequis"; st.rerun()

elif page == "Prerequis":
    st.title("1. Prerequis obligatoire")
    st.warning("La premiere valeur doit avoir ete recherchee et validee avec votre accompagnateur avant d'utiliser cette application.")
    confirmed = st.radio("Avez-vous deja identifie et valide au moins une valeur avec votre accompagnateur ?", ["Choisissez une reponse", "Oui", "Non"], index=0)
    if confirmed == "Non": st.error("Le parcours ne peut pas commencer. Reprenez d'abord cette premiere etape avec votre accompagnateur."); trace("prerequis_refuse"); st.stop()
    if confirmed == "Oui":
        st.session_state.prerequisite_confirmed = True
        count = st.number_input("Combien de valeurs avez-vous deja identifiees ?", min_value=1, max_value=20, value=max(1, len(st.session_state.existing_values)))
        selected = []
        for idx in range(int(count)):
            default = st.session_state.existing_values[idx] if idx < len(st.session_state.existing_values) else None
            options = [""] + VALUE_NAMES
            selected.append(st.selectbox(f"Valeur deja identifiee n°{idx + 1}", options, index=options.index(default) if default in options else 0, key=f"existing_{idx}"))
        selected = [name for name in selected if name]
        if st.button("Valider mes valeurs deja identifiees", type="primary", disabled=not selected):
            st.session_state.existing_values = list(dict.fromkeys(selected))
            for name in st.session_state.existing_values: st.session_state.validation[name] = {"importante": True, "tres_importante": True, "fondamentale": True}
            trace("prerequis_valide", ", ".join(st.session_state.existing_values)); st.session_state.page = "Exploration IA"; st.rerun()

elif page == "Exploration IA":
    st.title("2. Recherche guidee des autres valeurs")
    st.caption("Une seule question a la fois. L'IA travaille sur vos mots, sans vous expliquer ni decider a votre place.")
    progress = min(0.9, len(st.session_state.conversation) / 8)
    st.progress(progress, text=f"{len(st.session_state.conversation)} reponse(s) exploree(s)")
    for turn in st.session_state.conversation:
        with st.chat_message("assistant"):
            if turn.get("reformulation"): st.write(turn["reformulation"])
            st.write(turn["question"])
        with st.chat_message("user"): st.write(turn["answer"])
    with st.chat_message("assistant"):
        st.write(st.session_state.current_question)
    answer = st.chat_input("Ecrivez votre reponse ici")
    if answer:
        if len(answer.strip()) < 10:
            st.warning("Votre reponse est tres breve. Ajoutez si possible un exemple ou un fait concret.")
        else:
            with st.spinner("Le moteur RVC360 examine uniquement vos mots et le referentiel autorise..."):
                try:
                    result = run_rvc360_engine(answer.strip())
                    st.session_state.ai_engine_status = "operationnel"
                except Exception as exc:
                    trace("erreur_ia", f"{type(exc).__name__}: {str(exc)[:120]}")
                    st.error("Le moteur IA n'a pas pu repondre. Votre reponse n'a pas ete perdue. Reessayez dans quelques instants.")
                    st.stop()
            st.session_state.conversation.append({
                "question": st.session_state.current_question, "answer": answer.strip(),
                "reformulation": result["reformulation"], "date": now(),
            })
            merge_hypotheses(result["hypotheses"])
            st.session_state.current_question = result["question_suivante"]
            st.session_state.exploration_complete = result["exploration_suffisante"]
            trace("tour_ia", f"hypotheses={len(result['hypotheses'])}")
            st.rerun()
    if st.session_state.candidate_names:
        st.info(f"{len(st.session_state.candidate_names)} hypothese(s) de mots sont maintenant disponibles a l'examen.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Examiner les mots proposes", type="primary", disabled=len(st.session_state.candidate_names) < 3, use_container_width=True): st.session_state.page = "Mots a examiner"; st.rerun()
    with c2:
        if st.button("Poursuivre encore l'exploration", use_container_width=True): st.rerun()

elif page == "Mots a examiner":
    st.title("3. Hypotheses de mots a examiner")
    st.markdown('<div class="clarte-box">Une proposition n\'est jamais une valeur validee. Vous pouvez la conserver, l\'ecarter ou ajouter un autre mot du referentiel.</div>', unsafe_allow_html=True)
    proposed = [n for n in st.session_state.candidate_names if n not in st.session_state.discarded]
    chosen = st.multiselect("Selectionnez les mots que vous souhaitez examiner", VALUE_NAMES, default=proposed)
    for name in chosen:
        info = VALUE_MAP[name]
        with st.expander(f"{name} - {info['famille']}"):
            st.write(info["definition"])
            if st.session_state.candidate_reasons.get(name): st.caption(f"Rapprochement propose : {st.session_state.candidate_reasons[name]}")
            if st.session_state.candidate_evidence.get(name): st.caption(f"Element de votre reponse : {st.session_state.candidate_evidence[name]}")
    if st.button("Examiner ces valeurs", type="primary", disabled=not chosen):
        st.session_state.discarded = list(dict.fromkeys(st.session_state.discarded + [n for n in proposed if n not in chosen]))
        st.session_state.candidate_names = list(dict.fromkeys(chosen)); trace("hypotheses_selectionnees", str(len(chosen))); st.session_state.page = "Validation"; st.rerun()

elif page == "Validation":
    st.title("4. Clarification et validation")
    st.write("Chaque nouvelle valeur doit passer successivement par les trois niveaux : importante, tres importante, puis fondamentale.")
    names = list(dict.fromkeys(st.session_state.existing_values + st.session_state.candidate_names))
    for name in names:
        info = VALUE_MAP.get(name, {}); source = "Deja identifiee avec l'accompagnateur" if name in st.session_state.existing_values else "Recherchee avec l'application"
        st.markdown(f"### {name}"); st.caption(f"{source} - Famille : {info.get('famille', '')}"); st.write(info.get("definition", ""))
        st.session_state.personal_defs[name] = st.text_area("Que signifie cette valeur pour vous ?", value=st.session_state.personal_defs.get(name, ""), key=f"definition_{name}")
        current = st.session_state.validation.get(name, {})
        important = st.checkbox("Cette valeur est importante pour moi", value=bool(current.get("importante", name in st.session_state.existing_values)), key=f"important_{name}")
        very = st.checkbox("Cette valeur est tres importante pour moi", value=bool(current.get("tres_importante", name in st.session_state.existing_values)), disabled=not important, key=f"very_{name}")
        fundamental = st.checkbox("Cette valeur est fondamentale pour moi", value=bool(current.get("fondamentale", name in st.session_state.existing_values)), disabled=not very, key=f"fundamental_{name}")
        st.session_state.comments[name] = st.text_input("Commentaire facultatif", value=st.session_state.comments.get(name, ""), key=f"comment_{name}")
        st.session_state.validation[name] = {"importante": important, "tres_importante": very, "fondamentale": fundamental}; st.divider()
    if st.button("Enregistrer ma validation", type="primary"):
        validated_count = sum(1 for name in names if st.session_state.validation.get(name, {}).get("fondamentale")); trace("validation_finale", str(validated_count)); st.session_state.page = "Resultats"; st.rerun()

elif page == "Resultats":
    st.title("5. Mes valeurs validees")
    names = list(dict.fromkeys(st.session_state.existing_values + st.session_state.candidate_names)); validated = [name for name in names if st.session_state.validation.get(name, {}).get("fondamentale")]
    st.metric("Nombre de valeurs fondamentales validees", len(validated))
    if not validated: st.warning("Aucune valeur n'est encore validee comme fondamentale. Revenez a l'etape Validation.")
    for idx, name in enumerate(validated, 1):
        info = VALUE_MAP.get(name, {}); source = "Seance avec l'accompagnateur" if name in st.session_state.existing_values else "Application"
        st.markdown(f"### {idx}. {name}"); st.caption(f"{info.get('famille', '')} - Origine : {source}"); st.write(info.get("definition", ""))
        if st.session_state.personal_defs.get(name): st.write(f"**Votre definition :** {st.session_state.personal_defs[name]}")
    st.markdown('<div class="clarte-box">Ces valeurs peuvent maintenant etre utilisees dans la Boussole des valeurs professionnelles ou dans la Roue des valeurs Clarte360.</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1: st.download_button("Telecharger le rapport PDF", make_pdf(), file_name=f"RVC360_valeurs_{clean_name(st.session_state.identity.get('nom', 'beneficiaire'))}.pdf", mime="application/pdf", use_container_width=True)
    with col2: st.download_button("Telecharger les donnees JSON", export_json(), file_name=f"RVC360_valeurs_{clean_name(st.session_state.identity.get('nom', 'beneficiaire'))}.json", mime="application/json", use_container_width=True)
