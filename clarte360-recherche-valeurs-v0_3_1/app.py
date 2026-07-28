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

import html
import json
import os
import random
import re
import smtplib
import unicodedata
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from typing import Any
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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

APP_VERSION = "2.0.0"
SOCLE_CLARTE360_VERSION = "1.8"
APP_NAME = "Recherche de mes valeurs"
APP_FULL_NAME = "Clarté360 - Recherche de mes valeurs"
FRAMEWORK_VERSION = "4.0"
RVC360_VERSION = "2.0"
RGPD_TEXT_VERSION = "RGPD-Clarte360-RVC360-v2.0-2026-07"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "site_icon.png"
CHATBOT_PATH = BASE_DIR / "assets" / "chatbot_clarte360.webp"
REFERENTIEL_PATH = BASE_DIR / "data" / "referentiel_rvc360.xlsx"
FINAL_EMAIL_TO = "contact@clarte360.com"
DEFAULT_SESSION_LIMIT_MINUTES = 60

CLARTE360_LEGAL = {
    "raison_sociale": "Clarté360", "forme": "SAS", "adresse": "60 rue François 1er",
    "code_postal_ville": "75008 Paris", "telephone": "01 89 48 08 25",
    "email": "contact@clarte360.com", "web": "www.clarte360.com",
    "rcs": "102349834", "siret": "10234983400014", "naf": "8559 A", "tva": "FR88102349834",
}

FALLBACK_QUESTIONS = [
    "Racontez une situation, récente ou ancienne, qui vous a procuré une forte satisfaction ou, au contraire, qui vous a vivement contrarié. Que s’est-il passé concrètement ?",
    "Dans la situation que vous venez de raconter, qu’est-ce qui comptait particulièrement pour vous ?",
    "Qu’auriez-vous souhaité voir respecté, préservé ou rendu possible dans cette situation ?",
    "Pensez maintenant à un moment, dans une autre période de votre vie, où vous vous êtes senti particulièrement satisfait de votre manière d’agir. Qu’est-ce qui comptait pour vous ?",
    "Racontez un choix important que vous avez fait et que vous assumez encore aujourd’hui. Qu’avez-vous voulu privilégier ?",
    "Pensez à une personne que vous admirez. Quels actes ou quelles attitudes concrètes appréciez-vous chez elle ?",
    "Lors d’un week-end, d’un voyage, d’un projet ou d’un moment simple du quotidien, quand vous êtes-vous senti particulièrement à votre place ? Qu’est-ce qui rendait ce moment important ?",
    "Qu’est-ce que vous ne souhaiteriez pas sacrifier durablement, même en échange de davantage d’argent, de confort ou de réussite ?",
]

EXPLORATION_DOMAINS = {
    "famille": "la famille, la transmission, les responsabilités ou les relations familiales",
    "travail": "le travail, les réussites, les choix, l’autonomie, la reconnaissance ou les injustices",
    "relations": "les amitiés, la confiance, la loyauté, l’entraide ou les déceptions",
    "loisirs": "les loisirs, passions, voyages, créations ou moments où vous vous sentez pleinement à votre place",
    "emotions": "les joies, fiertés, colères, frustrations, admirations ou apaisements",
    "histoire": "l’enfance, les changements de vie, les périodes difficiles ou les personnes déterminantes",
    "projections": "les projets, rêves, transmissions, protections ou ce que vous refusez de perdre",
    "conflits": "les situations inacceptables, injustes ou celles qui vous obligent à agir",
}
FORBIDDEN_PATTERNS = [r"\bvous etes\b", r"\bvotre personnalite\b", r"\bcela revele\b", r"\bcela cache\b", r"\bau fond de vous\b", r"\ben realite vous\b", r"\binconsciemment\b", r"\bprobablement parce que\b", r"\bvotre vraie valeur\b", r"\bvous souffrez de\b", r"\bcela prouve que\b", r"\bvotre peur montre\b", r"\bvotre colere signifie\b", r"\bvous cherchez a compenser\b"]
SYSTEM_PROJECTION_RVC360 = """
TU ES L’ASSISTANT CONVERSATIONNEL RVC360 V2 DE CLARTE360.
Ta mission exclusive est d’aider une personne à explorer, vérifier et consolider ses valeurs personnelles, en complément de son accompagnateur humain.
Tu suis la personne, pas uniquement le dernier sujet. Tu utilises sa présentation, les valeurs déjà travaillées, les domaines déjà explorés, les sujets saturés, les hypothèses en cours et l’historique récent.
Tu ne réalises ni diagnostic psychologique, ni analyse de personnalité, ni coaching général. Tu ne déduis aucune cause cachée.
Tu proposes uniquement des hypothèses lexicales présentes dans le sous-ensemble contrôlé du référentiel transmis. Chaque hypothèse doit être reliée à une preuve textuelle explicite.
Une hypothèse n’est jamais une valeur validée. Seul le bénéficiaire peut valider.
Tu poses UNE seule question ouverte à la fois. Après deux approfondissements utiles maximum sur un même épisode, change réellement d’angle ou de domaine, sauf demande explicite du bénéficiaire.
Évite les répétitions, l’interrogatoire, les félicitations artificielles et les réponses longues. Tu peux reconnaître que tu peux te tromper.
La question suivante doit contribuer à l’un de ces objectifs : recueillir une autre situation, vérifier la transversalité, explorer un domaine peu couvert, distinguer deux valeurs proches, ou tester une hypothèse.
SORTIE : uniquement un objet JSON conforme au schéma demandé.
"""

RGPD_TEXT = f"""
### Protection des données personnelles (RGPD)

Cette application Clarté360 fonctionne sans base de données serveur propre à l'application. Aucune donnée n'est enregistrée durablement sur un serveur Clarté360 par l'application.

Le fichier JSON constitue le seul support de conservation de votre travail. Il peut contenir votre identité, votre adresse e-mail, le nom de votre accompagnateur, les dates et heures de connexion, la durée des sessions, vos réponses, les mots proposés, vos validations, l'historique des connexions, les générations de codes d'accès, le consentement RGPD, la version de l'application et les informations techniques disponibles.

Le fichier JSON appartient exclusivement au bénéficiaire. Vous choisissez librement de le conserver, de le supprimer ou de le transmettre à votre accompagnateur.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : **{RGPD_TEXT_VERSION}**.

### Utilisation de l'intelligence artificielle

Le moteur RVC360 intervient en deux niveaux : il structure d'abord localement les propos sans rechercher de valeur, puis l'intelligence artificielle rapproche cette fiche d'analyse d'un sous-ensemble contrôlé du référentiel RVC360 afin de formuler des hypothèses lexicales à examiner. Elle ne valide aucune valeur, ne produit aucun diagnostic et ne prend aucune décision à la place du bénéficiaire.

Les réponses utiles à cette recherche sont transmises au fournisseur d'IA configuré par Clarté360. Il est demandé de ne pas saisir de noms complets, coordonnées ou informations sensibles inutiles. L'application demande au fournisseur de ne pas conserver la réponse comme état applicatif (`store=False`). Les traitements techniques et règles de conservation propres au fournisseur restent applicables.

### Nature des résultats

Les résultats constituent des supports d'aide à la réflexion. Ils ne constituent ni un diagnostic psychologique, ni un avis médical, ni une décision d'orientation automatique. Le bénéficiaire demeure seul décisionnaire des valeurs qu'il retient et valide.

### Propriété intellectuelle

Les applications, outils, questionnaires, méthodes, référentiels, rapports et contenus Clarté360 sont protégés. Toute reproduction, adaptation, diffusion ou réutilisation sans autorisation écrite préalable est interdite.
"""

st.set_page_config(page_title=APP_FULL_NAME, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🧭", layout="wide")
st.markdown(f"""
<style>
:root {{ --clarte-teal: {OFFICIAL_TEAL}; }}
h1,h2,h3 {{ color:{OFFICIAL_TEAL}; }}
.stProgress > div > div > div > div {{ background-color:{OFFICIAL_TEAL}; }}
div.stButton > button[kind="primary"] {{ background-color:{OFFICIAL_TEAL}; border-color:{OFFICIAL_TEAL}; }}
.clarte-title-accent {{ color:{OFFICIAL_TEAL}; }}
.clarte-box {{ border-left:6px solid {OFFICIAL_TEAL}; background:{LIGHT_TEAL}; padding:1rem 1.1rem; border-radius:.55rem; margin:1rem 0; color:{DARK_TEXT}; }}
.objectif-box {{ border:1px solid #cfe6e6; background:#f8fbfb; padding:1.2rem 1.4rem; border-radius:.9rem; margin:1rem 0 1.4rem; color:{DARK_TEXT}; }}
.clarte-card {{ border:1px solid #d9eeee; border-radius:.8rem; padding:1rem; background:#fff; box-shadow:0 1px 8px rgba(0,128,128,.08); margin-bottom:1rem; }}
.small-muted {{ color:#666; font-size:.9rem; }}
.clarte-values-panel {{ position:fixed; right:1rem; top:6.6rem; width:190px; z-index:50; background:#ffffff; border:1px solid #cfe6e6; border-radius:12px; padding:10px; box-shadow:0 3px 14px rgba(0,80,80,.12); }}
.clarte-values-panel img {{ width:46px; height:46px; object-fit:cover; border-radius:50%; display:block; margin:0 auto 5px; }}
.clarte-values-panel h4 {{ color:#008080; text-align:center; margin:.1rem 0 .45rem; font-size:1.05rem; line-height:1.2; }}
.clarte-values-panel .value-pill {{ background:#E6F4F4; color:#243A3A; border-radius:999px; padding:4px 8px; margin:4px 0; font-size:.82rem; text-align:center; }}
@media (max-width: 1200px) {{ .clarte-values-panel {{ position:static; width:auto; margin:0 0 1rem 0; }} }}
</style>
""", unsafe_allow_html=True)

def now_iso() -> str: return datetime.now().isoformat(timespec="seconds")
def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()
def sanitize_filename(value: str) -> str:
    value = normalize(value).replace(" ", "_")
    return value or "beneficiaire"
def get_secret(section: str, key: str, default: Any = "") -> Any:
    try: return st.secrets.get(section, {}).get(key, default)
    except Exception: return default

@st.cache_data(show_spinner=False)
def load_referentiel() -> list[dict[str, str]]:
    if not REFERENTIEL_PATH.exists(): return []
    df = pd.read_excel(REFERENTIEL_PATH, sheet_name="Référentiel 240")
    df = df.rename(columns={"Code":"code", "Valeur":"nom", "Famille":"famille", "Définition Clarté360 - base de travail":"definition"})
    out=[]
    for _, row in df.iterrows():
        if pd.isna(row.get("nom")): continue
        out.append({"code":str(row.get("code","")).strip(), "nom":str(row["nom"]).strip(), "famille":str(row.get("famille","")).strip(), "definition":str(row.get("definition","")).strip()})
    return out
CATALOGUE = load_referentiel()
VALUE_MAP = {x["nom"]:x for x in CATALOGUE}
VALUE_NAMES = list(VALUE_MAP)

def default_business_state() -> dict[str, Any]:
    return {
        "page":"Accueil", "prerequisite_confirmed":False, "existing_values":[], "conversation":[],
        "current_question":FALLBACK_QUESTIONS[0], "candidate_names":[], "candidate_reasons":{},
        "candidate_evidence":{}, "validation":{}, "personal_defs":{}, "comments":{}, "discarded":[],
        "trace":[], "ai_calls":0, "ai_input_tokens":0, "ai_output_tokens":0,
        "ai_engine_status":"non_verifie", "exploration_complete":False,
        "prerequisite_entries":[], "prerequisite_pending":[], "prerequisite_index":0,
        "exploration_summary":"", "hypothesis_decisions":{}, "validation_index":0,
        "validation_stage":{}, "custom_values":{}, "voice_transcripts":[],
        "audio_widget_version":0, "prerequisite_count":1,
        "exploration_question_index":0, "hypothesis_index":0, "hypothesis_queue":[],
        "completed_hypotheses":[], "abandoned_hypotheses":[],
        "validated_app_values":[], "hypothesis_history":[], "hypothesis_status":{},
        "turns_since_hypothesis":0, "last_presented_hypotheses":[],
        "analysis_card":{}, "analysis_history":[], "analysis_no_novelty_count":0,
        "pipeline_status":"idle", "pipeline_error":"",
        "pending_pipeline_answer":"", "pending_analysis_card":{},
        "pending_submission":{}, "last_processed_submission_id":"",
        "beneficiary_profile":{}, "profile_conversation":[], "profile_complete":False,
        "assistant_presented":False, "interaction_preferences":{"mode":"ecrit_ou_voix"},
        "inter_session_values":[], "inter_session_pending":[], "exploration_wanted":None,
        "domains_explored":{}, "domains_not_explored":list(EXPLORATION_DOMAINS.keys()),
        "current_domain":"", "subject_depth":0, "saturated_subjects":[],
        "completion_check":{}, "closure_decision":"", "resume_message":"",
        "value_records":{}, "rejected_values":[],
    }

def init_state() -> None:
    defaults = {
        "welcome_choice":None, "test_started":False, "pending_beneficiaire":{}, "beneficiaire":{},
        "rgpd_acceptance":{}, "access_code":None, "code_expires_at":None, "access_history":{"generations":[],"nombre_regenerations":0},
        "code_verified_at":None, "show_contact_page":False, "show_rgpd_page":False, "session_expired":False,
        "session_history":[], "current_runtime_session_id":None, "exit_json_ready":False, "exit_mode":None,
        "json_downloaded":False, "final_email_sent":False, "passation_root_id":None, "session_id":None,
        "passation_id":None, "started_at":None,
    }
    defaults.update(default_business_state())
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=deepcopy(v)

def business_trace(action: str, details: str="") -> None:
    st.session_state.trace.append({"date":now_iso(),"action":action,"details":details})
    update_runtime_activity(action, user_activity=True)

def smtp_configured() -> bool:
    try:
        e=st.secrets.get("email",{})
        return all(e.get(k) for k in ["smtp_server","smtp_port","smtp_user","smtp_password","from_email","to_email"])
    except Exception: return False

def send_email(subject: str, body: str, to_email: str|None=None, attachments: list[tuple[str,bytes,str]]|None=None) -> tuple[bool,str]:
    if not smtp_configured(): return False,"SMTP non configuré dans les Secrets Streamlit."
    try:
        e=st.secrets["email"]; msg=EmailMessage(); msg["Subject"]=subject; msg["From"]=e["from_email"]; msg["To"]=to_email or e["to_email"]; msg.set_content(body)
        for filename,content,mime in attachments or []:
            maintype,subtype=mime.split("/",1); msg.add_attachment(content,maintype=maintype,subtype=subtype,filename=filename)
        with smtplib.SMTP_SSL(e["smtp_server"],int(e["smtp_port"]),timeout=25) as server:
            server.login(e["smtp_user"],e["smtp_password"]); server.send_message(msg)
        return True,"Email envoyé."
    except Exception as exc: return False,f"Erreur email : {exc}"

def get_session_limit_minutes() -> int:
    try: return int(st.secrets.get("security",{}).get("session_limit_minutes",DEFAULT_SESSION_LIMIT_MINUTES))
    except Exception: return DEFAULT_SESSION_LIMIT_MINUTES

def init_runtime_session(reason="nouvelle_session"):
    sid=str(uuid.uuid4()); now=now_iso(); st.session_state.current_runtime_session_id=sid; st.session_state.session_started_at=now; st.session_state.session_last_activity=now; st.session_state.session_last_heartbeat=now; st.session_state.session_expired=False; st.session_state.exit_json_ready=False
    h=st.session_state.get("session_history",[]); h.append({"session_uid":sid,"debut":now,"validation_code_at":st.session_state.get("code_verified_at",now),"derniere_activite":now,"dernier_battement":now,"fin":None,"duree_secondes":0,"duree_active_secondes":0,"motif_fermeture":None,"version_application":APP_VERSION,"motif_ouverture":reason,"sauvegardes":[]}); st.session_state.session_history=h

def _current_session_record():
    sid=st.session_state.get("current_runtime_session_id")
    for sess in st.session_state.get("session_history",[]):
        if sess.get("session_uid")==sid: return sess
    return None

def update_runtime_activity(event="heartbeat",user_activity=True):
    sess=_current_session_record()
    if not sess or sess.get("fin"): return
    now_dt=datetime.now(); raw=st.session_state.get("session_last_heartbeat") or sess.get("dernier_battement") or sess.get("debut")
    try: last=datetime.fromisoformat(raw)
    except Exception: last=now_dt
    delta=min(30,max(0,int((now_dt-last).total_seconds()))); sess["duree_active_secondes"]=int(sess.get("duree_active_secondes",0) or 0)+delta; sess["duree_secondes"]=sess["duree_active_secondes"]
    txt=now_dt.isoformat(timespec="seconds"); sess["dernier_battement"]=txt; sess["dernier_evenement"]=event; st.session_state.session_last_heartbeat=txt
    if user_activity: sess["derniere_activite"]=txt; st.session_state.session_last_activity=txt

def update_runtime_heartbeat(event="heartbeat"): update_runtime_activity(event,user_activity=False)
def record_save_event(kind: str):
    update_runtime_activity(kind,True); sess=_current_session_record()
    if sess: sess.setdefault("sauvegardes",[]).append({"type":kind,"date_heure":now_iso(),"duree_active_secondes":int(sess.get("duree_active_secondes",0) or 0)})
def close_runtime_session(reason: str):
    sess=_current_session_record()
    if not sess:return
    update_runtime_activity(reason,user_activity=(reason!="timeout_inactivite")); sess=_current_session_record()
    if sess: sess["fin"]=now_iso(); sess["motif_fermeture"]=reason
def total_session_seconds() -> int: return sum(int(s.get("duree_active_secondes",0) or 0) for s in st.session_state.get("session_history",[]))
def format_duration(seconds:int)->str:
    h,rem=divmod(max(0,int(seconds or 0)),3600); m,s=divmod(rem,60)
    return f"{h} h {m:02d} min {s:02d} s" if h else (f"{m} min {s:02d} s" if m else f"{s} s")
def check_session_limit():
    if not st.session_state.get("test_started") or st.session_state.get("session_expired"): return
    update_runtime_heartbeat("watchdog"); current=_current_session_record(); raw=st.session_state.get("session_last_activity") or (current or {}).get("derniere_activite") or (current or {}).get("debut")
    try: last=datetime.fromisoformat(raw)
    except Exception: last=datetime.now()
    if (datetime.now()-last).total_seconds() >= get_session_limit_minutes()*60:
        close_runtime_session("timeout_inactivite"); st.session_state.session_expired=True; st.rerun()
def timeout_watchdog():
    if not st.session_state.get("test_started") or st.session_state.get("session_expired"): return
    if st_autorefresh is not None: st_autorefresh(interval=10000,key="clarte360_timeout_watchdog")

def ai_ready()->bool: return OpenAI is not None and bool(get_secret("openai","api_key",os.environ.get("OPENAI_API_KEY","")))
def api_client()->OpenAI:
    key=get_secret("openai","api_key",os.environ.get("OPENAI_API_KEY",""))
    if OpenAI is None or not key: raise RuntimeError("La clé API OpenAI n'est pas configurée.")
    return OpenAI(api_key=key,timeout=35.0,max_retries=2)

def _flatten_analysis_text(card:dict[str,Any])->str:
    parts=[]
    for key in ("situation","reformulation","information_manquante"):
        v=card.get(key,"")
        if isinstance(v,str): parts.append(v)
    for key in ("faits","emotions_declarees","attentes_exprimees","actions_choix","expressions_fortes","criteres_personnels","contradictions_explicites","themes_descriptifs"):
        v=card.get(key,[])
        if isinstance(v,list): parts.extend(str(x) for x in v)
    return " ".join(parts)

def lexical_prefilter(texts:list[str],limit:int=30)->list[dict[str,str]]:
    """Préfiltrage générique du référentiel, sans règle métier du type mot X = valeur Y."""
    text_norm=normalize(" ".join(texts))
    terms={w for w in text_norm.split() if len(w)>=3}
    scored=[]
    for item in CATALOGUE:
        name_norm=normalize(item["nom"]); family_norm=normalize(item["famille"]); def_norm=normalize(item["definition"])
        words=set((name_norm+" "+family_norm+" "+def_norm).split())
        overlap=len(terms & words)
        exact_name=10 if name_norm and re.search(r"(?:^| )"+re.escape(name_norm)+r"(?: |$)", text_norm) else 0
        name_word_overlap=3*len(set(name_norm.split()) & terms)
        score=exact_name+name_word_overlap+overlap
        if score>0: scored.append((score,item))
    return [item for _,item in sorted(scored,key=lambda x:(x[0],x[1]["nom"]),reverse=True)[:limit]]

def explicit_catalogue_mentions(text:str)->list[str]:
    """Repère uniquement les noms exacts du référentiel effectivement prononcés."""
    n=normalize(text); found=[]
    for name in VALUE_NAMES:
        nn=normalize(name)
        if len(nn)>=4 and re.search(r"(?:^| )"+re.escape(nn)+r"(?: |$)",n): found.append(name)
    return sorted(found,key=lambda x:(len(normalize(x).split()),len(x)))

def response_json(instructions:str,payload:dict[str,Any],schema_name:str,schema:dict[str,Any],max_tokens:int=700)->dict[str,Any]:
    client=api_client(); model=get_secret("openai","model","gpt-5-mini")
    response=client.responses.create(model=model,instructions=instructions,input=json.dumps(payload,ensure_ascii=False),store=False,max_output_tokens=max_tokens,text={"format":{"type":"json_schema","name":schema_name,"strict":True,"schema":schema}})
    if getattr(response,"status",None) not in (None,"completed"): raise RuntimeError(f"Réponse IA incomplète : {getattr(response,'status',None)}")
    st.session_state.ai_calls+=1; usage=getattr(response,"usage",None)
    if usage:
        st.session_state.ai_input_tokens+=int(getattr(usage,"input_tokens",0) or 0)
        st.session_state.ai_output_tokens+=int(getattr(usage,"output_tokens",0) or 0)
    txt=getattr(response,"output_text","")
    if not txt: raise RuntimeError("Réponse IA vide.")
    return json.loads(txt)

def has_forbidden_language(text:str)->bool:
    n=normalize(text); return any(re.search(p,n) for p in FORBIDDEN_PATTERNS)

def _sentences(text:str)->list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|[\n\r]+", str(text)) if x.strip()]


def _clauses_matching(text:str, patterns:list[str], limit:int=6)->list[str]:
    out=[]
    for sentence in _sentences(text):
        n=normalize(sentence)
        if any(re.search(p,n) for p in patterns):
            out.append(sentence)
    return out[:limit]


def build_structured_analysis_local(answer:str)->dict[str,Any]:
    """IA-550 local et déterministe : structure les mots sans chercher de valeur.

    Aucune entrée du référentiel n'est consultée ici et aucun appel API n'est réalisé.
    """
    answer=str(answer).strip()
    previous=st.session_state.get("analysis_card",{}) or {}
    facts=_sentences(answer)[:8]
    emotions=_clauses_matching(answer,[r"\bje (?:me )?sens\b",r"\bj ai ressenti\b",r"\btriste\b",r"\bheureux\b",r"\bcontent\b",r"\bcontrarie\b",r"\benerve\b",r"\bcolere\b",r"\bpeur\b",r"\bdecu\b"])
    expectations=_clauses_matching(answer,[r"\bje (?:veux|voudrais|souhaite|attends)\b",r"\bj aurais voulu\b",r"\bil (?:faut|faudrait|devrait)\b",r"\bau moins\b"])
    actions=_clauses_matching(answer,[r"\bj ai (?:dit|fait|choisi|decide|refuse|accepte|demande)\b",r"\bje (?:dis|fais|choisis|decide|refuse|accepte|demande)\b"])
    criteria=_clauses_matching(answer,[r"\bimportant\b",r"\bcompte\b",r"\bessentiel\b",r"\bnormal\b",r"\bacceptable\b",r"\bjuste\b"])
    strong=[]
    for sentence in facts:
        if any(ch in sentence for ch in ("!", "?")) or any(w in normalize(sentence) for w in ("vraiment","pas du tout","toujours","jamais","au moins")):
            strong.append(sentence)
    # Thèmes descriptifs = mots fréquents du discours, sans projection sur le référentiel.
    stop={"alors","avec","avoir","cette","comme","dans","deux","elle","elles","etait","faire","fait","faut","hier","mais","moins","nous","pour","pourquoi","quand","sans","cela","cette","personnes","personne","passe","passer","devant","vraiment","vous","votre","leurs","leur","plus","tout","tous","une","des","les","que","qui","quoi","est","sont","j ai","je","ils"}
    words=[w for w in normalize(answer).split() if len(w)>=5 and w not in stop]
    freq={w:words.count(w) for w in set(words)}
    themes=[w for w,_ in sorted(freq.items(),key=lambda kv:(-kv[1],kv[0]))[:8]]
    previous_text=_flatten_analysis_text(previous) if previous else ""
    novelty=normalize(answer) not in normalize(previous_text) if previous_text else True
    return {
        "reformulation":"Vous décrivez : "+answer,
        "situation":answer,
        "faits":facts,
        "emotions_declarees":emotions,
        "attentes_exprimees":expectations,
        "actions_choix":actions,
        "expressions_fortes":strong[:8],
        "criteres_personnels":criteria,
        "contradictions_explicites":[],
        "themes_descriptifs":themes,
        "information_manquante":"",
        "question_suivante":"",
        "analyse_suffisante":bool(len(answer)>=35),
        "apport_nouveau":novelty,
    }


def project_hypotheses(card:dict[str,Any],answer:str)->dict[str,Any]:
    analysis_text=_flatten_analysis_text(card)
    context_answers=[x["answer"] for x in st.session_state.conversation[-4:]]+[answer,analysis_text]
    subset=lexical_prefilter(context_answers,limit=30)
    by_name={x["nom"]:x for x in subset}
    for name in explicit_catalogue_mentions(answer+" "+analysis_text):
        by_name[name]=VALUE_MAP[name]
    subset=list(by_name.values())[:30]
    if not subset:
        return {"hypotheses":[],"reformulation":"Vous avez décrit une situation concrète.","question_suivante":FALLBACK_QUESTIONS[(len(st.session_state.conversation)+1)%len(FALLBACK_QUESTIONS)],"elements_insuffisants":True}
    allowed={x["nom"] for x in subset}
    payload={
        "question_posee":st.session_state.current_question,
        "fiche_analyse_structuree":card,
        "valeurs_deja_validees":validated_names(),
        "hypotheses_deja_examinees":[{"nom":e.get("nom"),"statut":st.session_state.hypothesis_status.get(e.get("nom"),e.get("statut"))} for e in st.session_state.get("hypothesis_history",[])[-10:]],
        "presentation_beneficiaire":st.session_state.get("beneficiary_profile",{}),
        "valeurs_deja_travaillees":st.session_state.get("value_records",{}),
        "domaines_explores":st.session_state.get("domains_explored",{}),
        "domaines_non_explores":st.session_state.get("domains_not_explored",[]),
        "sujets_satures":st.session_state.get("saturated_subjects",[]),
        "domaine_actuel":st.session_state.get("current_domain",""),
        "referentiel_autorise":subset,
    }
    schema={"type":"object","additionalProperties":False,"properties":{
        "hypotheses":{"type":"array","maxItems":5,"items":{"type":"object","additionalProperties":False,"properties":{"nom":{"type":"string","enum":sorted(allowed)},"raison":{"type":"string"},"preuve":{"type":"string"},"priorite_interne":{"type":"integer","minimum":1,"maximum":5}},"required":["nom","raison","preuve","priorite_interne"]}},
        "elements_insuffisants":{"type":"boolean"},"reformulation":{"type":"string"},"question_suivante":{"type":"string"}
    },"required":["hypotheses","elements_insuffisants","reformulation","question_suivante"]}
    result=response_json(SYSTEM_PROJECTION_RVC360,payload,"rvc360_projection_referentiel",schema,750)
    cleaned=[]
    for x in result.get("hypotheses",[]):
        name=str(x.get("nom","")).strip()
        if name in allowed and name not in validated_names():
            cleaned.append({"nom":name,"raison":str(x.get("raison","")).strip(),"preuve":str(x.get("preuve","")).strip(),"priorite_interne":int(x.get("priorite_interne",5))})
    cleaned.sort(key=lambda x:x["priorite_interne"])
    q=str(result.get("question_suivante","")).strip()
    if has_forbidden_language(q): q=""
    if not q: q=FALLBACK_QUESTIONS[(len(st.session_state.conversation)+1)%len(FALLBACK_QUESTIONS)]
    reformulation=str(result.get("reformulation","")).strip()
    if has_forbidden_language(reformulation): reformulation="Vous avez décrit une situation concrète."
    return {"hypotheses":cleaned,"reformulation":reformulation,"question_suivante":q,"elements_insuffisants":bool(result.get("elements_insuffisants",False))}


def run_rvc360_pipeline(answer:str)->dict[str,Any]:
    """Architecture V1.3 avec un seul appel API par réponse validée.

    Niveau 1 : structuration locale, déterministe et sans référentiel.
    Niveau 2 : un unique appel IA pour la projection et la prochaine question.
    """
    card=build_structured_analysis_local(answer)
    projection=project_hypotheses(card,answer)
    card["reformulation"]=projection.get("reformulation",card.get("reformulation",""))
    card["question_suivante"]=projection.get("question_suivante","")
    return {"analysis_card":card,"hypotheses":projection.get("hypotheses",[]),"reformulation":card.get("reformulation",""),"question_suivante":card.get("question_suivante","")}


def merge_hypotheses(items:list[dict[str,str]])->list[str]:
    presented=[]
    for item in items:
        n=item["nom"]
        if n in validated_names():
            continue
        # Une hypothèse abandonnée peut être reproposée si une nouvelle preuve explicite apparaît.
        if n in st.session_state.abandoned_hypotheses:
            st.session_state.abandoned_hypotheses.remove(n)
        if n in st.session_state.discarded:
            st.session_state.discarded.remove(n)
        if n not in st.session_state.candidate_names:
            st.session_state.candidate_names.append(n)
        st.session_state.candidate_reasons[n]=item.get("raison","")
        st.session_state.candidate_evidence[n]=item.get("preuve","")
        previous=st.session_state.hypothesis_status.get(n)
        status="reproposee" if previous in ("abandonnee","ecartee") else "a_examiner"
        st.session_state.hypothesis_status[n]=status
        event={
            "nom":n,"raison":item.get("raison",""),"preuve":item.get("preuve",""),
            "statut":status,"date":now_iso(),"tour":len(st.session_state.conversation)+1,
        }
        st.session_state.hypothesis_history.append(event)
        presented.append(n)
    st.session_state.last_presented_hypotheses=presented
    st.session_state.turns_since_hypothesis=0 if presented else int(st.session_state.get("turns_since_hypothesis",0))+1
    return presented


def value_info(name:str)->dict[str,str]:
    if name in VALUE_MAP: return VALUE_MAP[name]
    custom=st.session_state.get("custom_values",{}).get(name,{})
    return {"nom":name,"famille":custom.get("famille","Valeur personnelle"),"definition":custom.get("definition","")}

def local_value_matches(raw:str, limit:int=5)->list[str]:
    n=normalize(raw)
    scored=[]
    for name in VALUE_NAMES:
        nn=normalize(name)
        score=SequenceMatcher(None,n,nn).ratio()
        if n==nn: score=1.0
        elif n in nn or nn in n: score=max(score,.88)
        scored.append((score,name))
    return [name for score,name in sorted(scored, reverse=True)[:limit] if score>=.48]

def resolve_prerequisite(raw:str)->dict[str,Any]:
    matches=local_value_matches(raw)
    exact=next((n for n in matches if normalize(n)==normalize(raw)),None)
    if exact: return {"raw":raw,"status":"exact","propositions":[exact]}
    return {"raw":raw,"status":"propositions" if matches else "nouvelle","propositions":matches}

def notify_new_value(name:str,definition:str)->None:
    if not smtp_configured(): return
    ben=st.session_state.get("beneficiaire",{})
    body=(f"Une valeur personnelle non présente dans le référentiel a été validée.\n\n"
          f"Valeur proposée : {name}\nDéfinition validée : {definition}\n"
          f"Référence de passation : {st.session_state.get('passation_id','')}\n"
          f"Application : {APP_FULL_NAME} {APP_VERSION}\n\n"
          "Aucune réponse détaillée ni identité du bénéficiaire n'est transmise dans cette notification.")
    send_email(f"Clarté360 - Proposition de valeur à examiner : {name}",body,to_email=FINAL_EMAIL_TO)

def transcribe_audio(audio_file)->str:
    """Transcrit un enregistrement ponctuel sans conserver le fichier audio."""
    client=api_client()
    model=get_secret("openai","transcription_model","gpt-4o-mini-transcribe")
    data=audio_file.getvalue()
    if not data or len(data) < 256:
        raise ValueError("Aucun enregistrement exploitable n’a été reçu. Arrêtez l’enregistrement avec le carré puis recommencez.")
    import io
    mime=str(getattr(audio_file,"type","") or "").lower()
    suffix=".webm" if "webm" in mime else ".mp3" if "mpeg" in mime or "mp3" in mime else ".m4a" if "mp4" in mime or "m4a" in mime else ".wav"
    f=io.BytesIO(data)
    f.name=f"reponse{suffix}"
    result=client.audio.transcriptions.create(model=model,file=f,language="fr")
    transcript=str(getattr(result,"text","") or "").strip()
    # Les octets ne sont jamais placés dans le JSON ni dans un stockage applicatif.
    del data
    f.close()
    if not transcript:
        raise ValueError("La transcription est vide. Vous pouvez réessayer ou recommencer votre enregistrement.")
    return transcript

def reset_voice_capture(*, clear_text: bool=True)->None:
    """Invalide tout ancien enregistrement et recrée réellement le composant audio."""
    st.session_state["audio_widget_version"]=int(st.session_state.get("audio_widget_version",0))+1
    if clear_text:
        st.session_state["voice_draft"]=""
        st.session_state.pop("voice_edit",None)
    st.session_state.pop("voice_last_error",None)

def speak_button(text:str,key:str)->None:
    """Lecture navigateur strictement ponctuelle : un clic, une lecture, puis arrêt."""
    safe=json.dumps(text,ensure_ascii=False)
    safe_key=re.sub(r"[^a-zA-Z0-9_-]","_",str(key))
    components.html(f"""
    <button id="speak_{safe_key}" style="border:1px solid #008080;border-radius:8px;padding:8px 12px;background:white;cursor:pointer">🔊 Écouter la question</button>
    <script>
    (() => {{
      const synth = window.speechSynthesis;
      const btn = document.getElementById("speak_{safe_key}");
      let playing = false;
      let utterance = null;
      const chooseVoice = () => {{
        const voices = synth.getVoices() || [];
        return voices.find(v => v.lang === 'fr-FR' && /Microsoft|Google|Natural|Neural/i.test(v.name))
          || voices.find(v => (v.lang || '').toLowerCase().startsWith('fr'))
          || null;
      }};
      btn.addEventListener('click', () => {{
        if (playing) return;
        synth.cancel();
        playing = true;
        btn.disabled = true;
        btn.textContent = '🔊 Lecture en cours…';
        utterance = new SpeechSynthesisUtterance({safe});
        utterance.lang = 'fr-FR';
        utterance.rate = 0.92;
        utterance.pitch = 1.0;
        const voice = chooseVoice();
        if (voice) utterance.voice = voice;
        const finish = () => {{
          playing = false;
          btn.disabled = false;
          btn.textContent = '🔊 Écouter la question';
          utterance = null;
        }};
        utterance.onend = finish;
        utterance.onerror = finish;
        synth.speak(utterance);
      }}, {{ once: false }});
      window.addEventListener('beforeunload', () => synth.cancel(), {{ once: true }});
    }})();
    </script>""",height=48)

def value_reminder()->None:
    st.info("Une valeur est un principe profondément important qui oriente vos choix et votre manière de vivre. Ce n'est ni une simple préférence, ni une qualité, ni un objectif. Le mot retenu doit avoir pour vous un sens personnel précis.")

def validated_names()->list[str]:
    names=list(dict.fromkeys(st.session_state.existing_values+st.session_state.get("validated_app_values",[])))
    return [n for n in names if st.session_state.validation.get(n,{}).get("fondamentale")]

def start_new_session(nom:str,prenom:str,email:str,consultant:str=""):
    st.session_state.passation_root_id=str(uuid.uuid4()); st.session_state.session_id=str(uuid.uuid4()); st.session_state.passation_id=f"CL360-RVC-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{st.session_state.session_id[:8].upper()}"; st.session_state.started_at=now_iso(); st.session_state.beneficiaire={"nom":nom.strip(),"prenom":prenom.strip(),"email":email.strip(),"consultant":consultant.strip()}; st.session_state.test_started=True; st.session_state.session_history=[]
    for k,v in default_business_state().items(): st.session_state[k]=deepcopy(v)
    init_runtime_session("premiere_connexion")

def build_payload(completed=False)->dict[str,Any]:
    validated=validated_names()
    values=[]
    for name in validated:
        info=value_info(name)
        values.append({
            "nom":name,"famille":info.get("famille",""),
            "origine":"seance" if name in st.session_state.existing_values else "application",
            "definition_clarte360":info.get("definition",""),
            "definition_personnelle":st.session_state.personal_defs.get(name,""),
            "validation":st.session_state.validation.get(name,{}),
            "commentaire":st.session_state.comments.get(name,""),
        })
    metier_common={
        "page":st.session_state.page,
        "prerequis_premiere_valeur":st.session_state.prerequisite_confirmed,
        "valeurs_validees":values,
        "nombre_total_valeurs_validees":len(values),
        "nombre_valeurs_seance":sum(1 for v in values if v["origine"]=="seance"),
        "nombre_valeurs_application":sum(1 for v in values if v["origine"]=="application"),
        "exploration_complete":bool(completed or st.session_state.exploration_complete),
        "presentation_beneficiaire":st.session_state.get("beneficiary_profile",{}),
        "presentation_assistant":{"effectuee":st.session_state.get("assistant_presented",False)},
        "preferences_interaction":st.session_state.get("interaction_preferences",{}),
        "valeurs_accompagnateur":[v for v in st.session_state.get("value_records",{}).values() if v.get("source")=="accompagnateur"],
        "valeurs_observations_personnelles":st.session_state.get("inter_session_values",[]),
        "valeurs_entourage":[v for v in st.session_state.get("inter_session_values",[]) if "proche" in normalize(v.get("source",""))],
        "valeurs_ia":[v for v in values if v.get("origine")=="application"],
        "hypotheses":st.session_state.get("hypothesis_history",[]),
        "valeurs_rejetees":st.session_state.get("rejected_values",[])+st.session_state.get("discarded",[]),
        "domaines_explores":st.session_state.get("domains_explored",{}),
        "domaines_non_explores":st.session_state.get("domains_not_explored",[]),
        "questions_posees":[t.get("question") for t in st.session_state.get("conversation",[])],
        "sujets_satures":st.session_state.get("saturated_subjects",[]),
        "etat_exploration":{"souhaitee":st.session_state.get("exploration_wanted"),"page":st.session_state.page},
        "controle_completude":st.session_state.get("completion_check",{}),
        "decision_cloture":st.session_state.get("closure_decision",""),
        "historique":st.session_state.get("trace",[]),
    }
    if not completed:
        # Le JSON de reprise conserve l'état nécessaire à la continuité du travail.
        metier_common.update({
            "existing_values":st.session_state.existing_values,
            "validated_app_values":st.session_state.get("validated_app_values",[]),
            "conversation":st.session_state.conversation,
            "current_question":st.session_state.current_question,
            "candidate_names":st.session_state.candidate_names,
            "candidate_reasons":st.session_state.candidate_reasons,
            "candidate_evidence":st.session_state.candidate_evidence,
            "validation":st.session_state.validation,
            "personal_defs":st.session_state.personal_defs,
            "comments":st.session_state.comments,
            "discarded":st.session_state.discarded,
            "hypothesis_history":st.session_state.get("hypothesis_history",[]),
            "hypothesis_status":st.session_state.get("hypothesis_status",{}),
            "trace":st.session_state.trace,
            "prerequisite_entries":st.session_state.prerequisite_entries,
            "hypothesis_decisions":st.session_state.hypothesis_decisions,
            "custom_values":st.session_state.custom_values,
            "exploration_summary":st.session_state.exploration_summary,
            "analysis_card":st.session_state.get("analysis_card",{}),
            "analysis_history":st.session_state.get("analysis_history",[]),
        })
    return {
        "application":APP_FULL_NAME,"version":APP_VERSION,"socle_clarte360":SOCLE_CLARTE360_VERSION,
        "framework_version":FRAMEWORK_VERSION,"rvc360_version":RVC360_VERSION,"rgpd_version":RGPD_TEXT_VERSION,
        "passation_root_id":st.session_state.get("passation_root_id"),"session_id":st.session_state.get("session_id"),
        "passation_id":st.session_state.get("passation_id"),"beneficiaire":st.session_state.get("beneficiaire",{}),
        "rgpd_acceptance":st.session_state.get("rgpd_acceptance",{}),"access_history":st.session_state.get("access_history",{}),
        "sessions":st.session_state.get("session_history",[]),"metier":metier_common,
        "ia":{"appels":st.session_state.ai_calls,"tokens_entree":st.session_state.ai_input_tokens,"tokens_sortie":st.session_state.ai_output_tokens,"statut":st.session_state.ai_engine_status,"modele":get_secret("openai","model","gpt-5-mini")},
        "completed":completed,"exporte_le":now_iso(),
    }

def payload_bytes(completed=False)->bytes: return json.dumps(build_payload(completed),ensure_ascii=False,indent=2).encode("utf-8")
def make_filename(prefix="rvc360",ext="json"):
    b=st.session_state.get("beneficiaire",{}); return f"{prefix}_{sanitize_filename((b.get('prenom','')+'_'+b.get('nom','')).strip())}_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}"

def restore_from_progress(payload:dict):
    st.session_state.passation_root_id=payload.get("passation_root_id",str(uuid.uuid4())); st.session_state.session_id=str(uuid.uuid4()); st.session_state.passation_id=payload.get("passation_id") or f"CL360-RVC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"; st.session_state.beneficiaire=payload.get("beneficiaire",{}); st.session_state.rgpd_acceptance=payload.get("rgpd_acceptance",{}); st.session_state.access_history=payload.get("access_history",{}); st.session_state.session_history=deepcopy(payload.get("sessions",[])); m=payload.get("metier",{})
    for k,v in default_business_state().items(): st.session_state[k]=deepcopy(m.get(k,v))
    # Compatibilité avec les JSON 1.3.0 et antérieurs : reconstruire les valeurs application déjà fondamentales.
    if not st.session_state.get("validated_app_values"):
        st.session_state.validated_app_values=[
            n for n,val in st.session_state.get("validation",{}).items()
            if val.get("fondamentale") and n not in st.session_state.get("existing_values",[])
        ]
    st.session_state.test_started=True; st.session_state.code_verified_at=now_iso(); init_runtime_session("reprise_json"); business_trace("reprise_json")

def create_pdf()->bytes:
    from reportlab.platypus import Image, Table, TableStyle, KeepTogether
    buffer=BytesIO(); styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Teal",parent=styles["Heading1"],textColor=colors.HexColor(OFFICIAL_TEAL),spaceAfter=12))
    styles.add(ParagraphStyle(name="Teal2",parent=styles["Heading2"],textColor=colors.HexColor(OFFICIAL_TEAL),spaceBefore=10,spaceAfter=6))
    styles.add(ParagraphStyle(name="Small",parent=styles["Normal"],fontSize=8,leading=10,textColor=colors.HexColor("#666666")))
    styles.add(ParagraphStyle(name="Cover",parent=styles["Title"],fontSize=24,leading=29,textColor=colors.HexColor(OFFICIAL_TEAL),alignment=1,spaceAfter=18))
    def footer(canvas,doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#D7EAEA")); canvas.line(1.5*cm,1.05*cm,A4[0]-1.5*cm,1.05*cm)
        canvas.setFont("Helvetica",7.5); canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(1.5*cm,.65*cm,"Clarté360 - 60 rue François 1er - 75008 Paris - Document confidentiel")
        canvas.drawRightString(A4[0]-1.5*cm,.65*cm,f"Page {doc.page}")
        canvas.restoreState()
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=1.7*cm,leftMargin=1.7*cm,topMargin=1.5*cm,bottomMargin=1.4*cm,title="Rapport RVC360 - Recherche de mes valeurs")
    b=st.session_state.get("beneficiaire",{}); validated=validated_names(); records=st.session_state.get("value_records",{})
    story=[]
    if LOGO_PATH.exists():
        story += [Spacer(1,1.2*cm),Image(str(LOGO_PATH),width=3.2*cm,height=3.2*cm),Spacer(1,.5*cm)]
    story += [Paragraph("CLARTÉ360",styles["Cover"]),Paragraph("Recherche de mes valeurs - Rapport de parcours",styles["Cover"]),Spacer(1,.5*cm),
              Paragraph(f"<b>Bénéficiaire :</b> {html.escape((b.get('prenom','')+' '+b.get('nom','')).strip())}",styles["Normal"]),
              Paragraph(f"<b>Date :</b> {datetime.now().strftime('%d/%m/%Y')}",styles["Normal"]),
              Paragraph(f"<b>Application :</b> {APP_VERSION} - <b>RVC360 :</b> {RVC360_VERSION} - <b>Framework :</b> {FRAMEWORK_VERSION}",styles["Normal"]),
              Spacer(1,1.2*cm),Paragraph("Ce document restitue les éléments exprimés et validés par le bénéficiaire. Il complète le travail réalisé avec l’accompagnateur et ne constitue ni un diagnostic, ni une analyse de personnalité, ni une décision d’orientation.",styles["Italic"]),PageBreak()]
    story += [Paragraph("1. Contexte et finalité",styles["Teal"]),
              Paragraph("L’application aide à identifier, vérifier et consolider les valeurs personnelles. Elle ne remplace jamais l’accompagnateur. Les hypothèses proposées par l’IA restent des mots à examiner ; seules les validations du bénéficiaire sont retenues comme valeurs.",styles["Normal"])]
    profile=st.session_state.get("beneficiary_profile",{})
    if profile:
        story += [Paragraph("2. Présentation du bénéficiaire",styles["Teal"]),Paragraph(html.escape(profile.get("presentation_libre","")),styles["Normal"])]
        if profile.get("objectif_demarche"): story += [Paragraph(f"<b>Attente exprimée :</b> {html.escape(profile['objectif_demarche'])}",styles["Normal"])]
    story += [Paragraph("3. Synthèse du parcours",styles["Teal"])]
    data=[["Élément","État"],["Valeurs validées",str(len(validated))],["Domaines explorés",", ".join(st.session_state.get("domains_explored",{}).keys()) or "Non renseigné"],["Hypothèses examinées",str(len(st.session_state.get("hypothesis_history",[])))]]
    t=Table(data,colWidths=[6*cm,10*cm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(LIGHT_TEAL)),('TEXTCOLOR',(0,0),(-1,0),colors.HexColor(DARK_TEXT)),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#CFE6E6')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)])); story += [t,Spacer(1,10)]
    sections=[("4. Valeurs déjà identifiées avec l’accompagnateur",[r for r in records.values() if r.get("source")=="accompagnateur"]),("5. Valeurs repérées entre les séances",st.session_state.get("inter_session_values",[])),("6. Valeurs explorées avec l’application",[records.get(n,{"nom_propose":n,"source":"application","statut":"validee"}) for n in validated if n not in st.session_state.existing_values])]
    for title,items in sections:
        story += [Paragraph(title,styles["Teal"])]
        if not items: story += [Paragraph("Aucun élément enregistré.",styles["Normal"])]
        for r in items:
            name=r.get("nom_propose") or r.get("nom") or "Valeur"
            definition=r.get("definition_personnelle") or r.get("definition") or st.session_state.personal_defs.get(name,"") or value_info(name).get("definition","")
            situations=r.get("situations_associees") or r.get("situations") or []
            emotions=r.get("emotions_associees") or r.get("emotions") or []
            block=[Paragraph(html.escape(name),styles["Teal2"]),Paragraph(f"<b>Source :</b> {html.escape(str(r.get('source','')))} - <b>Statut :</b> {html.escape(str(r.get('statut','')))}",styles["Normal"]),Paragraph(f"<b>Définition personnelle :</b> {html.escape(definition or 'Non renseignée')}",styles["Normal"])]
            if situations: block.append(Paragraph(f"<b>Situations associées :</b> {html.escape(' ; '.join(map(str,situations)))}",styles["Normal"]))
            if emotions: block.append(Paragraph(f"<b>Émotions ou réactions :</b> {html.escape(' ; '.join(map(str,emotions)))}",styles["Normal"]))
            story += [KeepTogether(block),Spacer(1,5)]
    story += [Paragraph("7. Liste finale des valeurs validées",styles["Teal"])]
    if validated:
        for i,name in enumerate(validated,1): story += [Paragraph(f"{i}. <b>{html.escape(name)}</b> - {html.escape(st.session_state.personal_defs.get(name,'') or value_info(name).get('definition',''))}",styles["Normal"])]
    else: story += [Paragraph("Aucune valeur n’a encore été validée.",styles["Normal"])]
    rejected=list(dict.fromkeys(st.session_state.get("discarded",[])+st.session_state.get("abandoned_hypotheses",[])))
    story += [Paragraph("8. Hypothèses non retenues ou à revoir",styles["Teal"]),Paragraph(html.escape(", ".join(rejected) if rejected else "Aucune."),styles["Normal"])]
    comp=st.session_state.get("completion_check",{})
    story += [Paragraph("9. Contrôle de complétude",styles["Teal"]),Paragraph(f"<b>Appréciation du bénéficiaire :</b> {html.escape(str(comp.get('representation','Non réalisé')))}",styles["Normal"]),Paragraph(f"<b>Domaines non explorés :</b> {html.escape(', '.join(comp.get('domaines_non_explores',[])) or 'Aucun identifié')}",styles["Normal"]),Paragraph(f"<b>Points à reprendre avec l’accompagnateur :</b> {html.escape(comp.get('angles_a_reprendre','') or 'Aucun point particulier renseigné')}",styles["Normal"])]
    story += [Paragraph("10. Conclusion",styles["Teal"]),Paragraph("Les valeurs présentées dans ce rapport sont celles que le bénéficiaire a validées. Elles pourront être relues, différenciées ou consolidées avec l’accompagnateur. Le fichier JSON permet de reprendre ultérieurement le parcours sans recommencer les étapes déjà réalisées.",styles["Normal"]),Spacer(1,12),Paragraph("Document confidentiel - diffusion réservée au bénéficiaire et, avec son accord, à son accompagnateur.",styles["Small"])]
    doc.build(story,onFirstPage=footer,onLaterPages=footer); return buffer.getvalue()

def display_header():
    c1,c2=st.columns([1,5])
    with c1:
        if LOGO_PATH.exists(): st.image(str(LOGO_PATH),width=80)
    with c2:
        st.markdown(f"# <span class='clarte-title-accent'>{APP_FULL_NAME}</span>",unsafe_allow_html=True); st.caption("Outil propriétaire de recherche et de validation des valeurs fondamentales")

def contact_form():
    ben=st.session_state.get("beneficiaire") or st.session_state.get("pending_beneficiaire") or {}
    st.markdown("""### Contacter Clarté360
Vous pouvez adresser une question administrative, signaler un problème technique ou proposer une amélioration. Pour une question relative à votre accompagnement, contactez votre consultant.""")
    with st.form("contact_clarte360_form", clear_on_submit=False):
        c1,c2=st.columns(2)
        with c1: prenom=st.text_input("Prénom *",value=ben.get("prenom",""))
        with c2: nom=st.text_input("Nom *",value=ben.get("nom",""))
        email=st.text_input("Adresse e-mail *",value=ben.get("email",""))
        telephone=st.text_input("Téléphone (facultatif)")
        objet=st.text_input("Objet *",value=f"Demande depuis {APP_FULL_NAME}")
        message=st.text_area("Message *",height=160)
        consent=st.checkbox("J'accepte que Clarté360 utilise les informations transmises uniquement pour traiter ma demande.")
        submitted=st.form_submit_button("📩 Envoyer mon message",type="primary")
    if not submitted: return
    if not prenom.strip() or not nom.strip() or "@" not in email or not objet.strip() or not message.strip():
        st.error("Merci de renseigner tous les champs obligatoires."); return
    if not consent:
        st.error("Le consentement est nécessaire."); return
    support_id=f"SUP-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"
    body=(f"Identifiant support : {support_id}\nApplication : {APP_FULL_NAME}\nVersion : {APP_VERSION}\n"
          f"Prénom : {prenom}\nNom : {nom}\nEmail : {email}\nTéléphone : {telephone or 'non renseigné'}\n"
          f"Objet : {objet}\n\nMessage :\n{message}\n")
    ok,mail_status=send_email(f"Clarté360 - Support {support_id} - {APP_NAME}",body,to_email=FINAL_EMAIL_TO)
    if ok: st.success(f"Votre demande a bien été transmise. Référence : {support_id}")
    else: st.error(f"Le message n'a pas pu être envoyé : {mail_status}")

def traceability_information_block():
    update_runtime_heartbeat("affichage_tracabilite"); sessions=st.session_state.get("session_history",[]); rgpd=st.session_state.get("rgpd_acceptance",{})
    st.markdown("### Traçabilité de la session"); c1,c2,c3=st.columns(3); c1.metric("Session en cours",(st.session_state.get("current_runtime_session_id") or "Non ouverte")[:8]); c2.metric("Nombre de sessions",len(sessions)); c3.metric("Temps cumulé",format_duration(total_session_seconds()))
    if rgpd.get("consentement"): st.success(f"Consentement RGPD enregistré le {rgpd.get('date','')} à {rgpd.get('heure','')} - version {rgpd.get('version_texte','')}")
    else: st.warning("Aucun consentement RGPD n'est encore enregistré.")
    if sessions:
        st.dataframe(pd.DataFrame([{"Début":s.get("debut",""),"Dernière activité":s.get("derniere_activite",""),"Fin":s.get("fin",""),"Durée":format_duration(s.get("duree_active_secondes",0)),"Motif ouverture":s.get("motif_ouverture",""),"Motif fermeture":s.get("motif_fermeture","")} for s in sessions]),use_container_width=True,hide_index=True)

def rgpd_page():
    display_header()
    auxiliary_back_button("rgpd_back_top")
    st.subheader("Informations légales et protection des données"); t1,t2,t3=st.tabs(["Protection des données et traçabilité","Mentions légales","Nous contacter"])
    with t1: st.markdown(RGPD_TEXT); st.info("Le consentement RGPD est demandé avant la génération du code d'accès."); traceability_information_block()
    with t2:
        l=CLARTE360_LEGAL; st.markdown(f"### {l['raison_sociale']} {l['forme']}\n**Adresse :** {l['adresse']} - {l['code_postal_ville']}  \n**Téléphone :** {l['telephone']}  \n**E-mail :** {l['email']}  \n**Site :** {l['web']}  \n\n**RCS :** {l['rcs']}  \n**SIRET :** {l['siret']}  \n**Code NAF :** {l['naf']}  \n**TVA :** {l['tva']}")
    with t3: contact_form()
    auxiliary_back_button("rgpd_back_bottom")
def contact_page():
    display_header()
    auxiliary_back_button("contact_back_top")
    st.subheader("Contacter Clarté360"); contact_form()
    auxiliary_back_button("contact_back_bottom")
def welcome_screen():
    display_header(); st.markdown(f"### Bienvenue dans l'application Clarté360 - {APP_NAME}"); st.markdown("Avez-vous conservé le fichier JSON de votre dernière utilisation de cette application ?"); c1,c2=st.columns(2)
    with c1:
        if st.button("Oui → Importer mon fichier JSON",type="primary",use_container_width=True): st.session_state.welcome_choice="import"; st.rerun()
    with c2:
        if st.button("Non → Commencer une nouvelle session",use_container_width=True): st.session_state.welcome_choice="new"; st.rerun()
def import_json_screen():
    display_header(); st.subheader("Reprise d'une session"); st.markdown("Importez le fichier JSON téléchargé lors de votre dernière utilisation."); f=st.file_uploader("Fichier JSON Clarté360",type=["json"])
    if f and st.button("Reprendre ma session",type="primary"):
        try:
            payload=json.load(f)
            if payload.get("application")!=APP_FULL_NAME: st.error("Ce fichier ne correspond pas à cette application.")
            else: restore_from_progress(payload); st.rerun()
        except Exception as exc: st.error(f"Fichier JSON invalide : {exc}")

def issue_access_code(email:str,prenom:str,is_regeneration:bool):
    code=f"{random.randint(100000,999999)}"; minutes=int(get_secret("security","code_expiration_minutes",15)); st.session_state.access_code=code; st.session_state.code_expires_at=(datetime.now()+timedelta(minutes=minutes)).isoformat(timespec="seconds"); h=st.session_state.get("access_history",{"generations":[],"nombre_regenerations":0})
    if is_regeneration: h["nombre_regenerations"]=int(h.get("nombre_regenerations",0))+1
    h.setdefault("generations",[]).append({"date":datetime.now().strftime("%Y-%m-%d"),"heure":datetime.now().strftime("%H:%M:%S"),"generation":"regeneration" if is_regeneration else "initiale","envoi":"email","version_application":APP_VERSION}); st.session_state.access_history=h
    pending=st.session_state.get("pending_beneficiaire",{}); body_user=f"Bonjour {prenom},\n\nVotre code d'accès à {APP_FULL_NAME} est : {code}\n\nCe code est valable {minutes} minutes.\n\nClarté360"; body_admin=f"Demande de code d'accès pour {APP_FULL_NAME}.\n\nPrénom : {pending.get('prenom',prenom)}\nNom : {pending.get('nom','')}\nEmail : {email}\nConsultant : {pending.get('consultant','')}\nCode : {code}\nType : {'régénération' if is_regeneration else 'initiale'}\nDate/heure : {now_iso()}\nVersion : {APP_VERSION}\nConsentement RGPD : accepté ({RGPD_TEXT_VERSION})."
    ok_admin,msg_admin=send_email(f"Clarté360 - Nouveau code d'accès {APP_NAME}",body_admin); ok_user,msg_user=send_email(f"Votre code d'accès {APP_FULL_NAME}",body_user,to_email=email); h["generations"][-1]["envoi_beneficiaire"]="ok" if ok_user else msg_user; h["generations"][-1]["notification_admin"]="ok" if ok_admin else msg_admin
    if ok_user: st.success("Un code d'accès vient de vous être envoyé par e-mail.")
    else: st.error("Impossible d'envoyer le code : "+msg_user)
def identification_screen():
    display_header(); st.markdown('<div class="objectif-box"><h3>Objectif de l’outil</h3><p>Cette application a pour objectif unique d’aider le bénéficiaire à rechercher, clarifier et valider ses valeurs fondamentales. Elle ne fait ni coaching, ni bilan de compétences, ni orientation, ni test de personnalité.</p></div>',unsafe_allow_html=True)
    with st.expander("Protection des données personnelles, traçabilité et utilisation de l'IA",expanded=True): st.markdown(RGPD_TEXT)
    st.subheader("Identification")
    with st.form("identification"):
        c1,c2=st.columns(2)
        with c1: prenom=st.text_input("Prénom *")
        with c2: nom=st.text_input("Nom *")
        email=st.text_input("Adresse e-mail *"); consultant=st.text_input("Consultant / accompagnateur"); consent=st.checkbox("J'ai lu et j'accepte les conditions RGPD et les informations relatives à l'utilisation de l'intelligence artificielle."); submitted=st.form_submit_button("Recevoir mon code d'accès",type="primary")
    if submitted:
        if not prenom.strip() or not nom.strip() or "@" not in email: st.error("Merci de renseigner prénom, nom et une adresse e-mail valide.")
        elif not consent: st.error("Le consentement est obligatoire avant toute utilisation.")
        else:
            st.session_state.rgpd_acceptance={"consentement":True,"date":datetime.now().strftime("%Y-%m-%d"),"heure":datetime.now().strftime("%H:%M:%S"),"version_texte":RGPD_TEXT_VERSION}; st.session_state.pending_beneficiaire={"prenom":prenom.strip(),"nom":nom.strip(),"email":email.strip(),"consultant":consultant.strip()}; issue_access_code(email.strip(),prenom.strip(),False)
    if st.session_state.get("access_code"):
        st.subheader("Code d'accès"); code_in=st.text_input("Saisissez le code reçu par e-mail",max_chars=6); c1,c2=st.columns(2)
        with c1:
            if st.button("Valider le code et commencer",type="primary"):
                exp=datetime.fromisoformat(st.session_state.code_expires_at)
                if datetime.now()>exp: st.error("Le code a expiré. Demandez un nouveau code.")
                elif code_in.strip()==st.session_state.access_code:
                    b=st.session_state.pending_beneficiaire; st.session_state.code_verified_at=now_iso(); st.session_state.access_history["validation_code"]={"date_heure":now_iso(),"code_valide":True,"version_application":APP_VERSION}; start_new_session(b["nom"],b["prenom"],b["email"],b.get("consultant","")); st.rerun()
                else: st.error("Code incorrect.")
        with c2:
            if st.button("Je n'ai pas reçu mon code → Générer un nouveau code"):
                b=st.session_state.pending_beneficiaire; issue_access_code(b["email"],b["prenom"],True)


def sidebar_progress_label(page: str) -> str:
    labels={
        "Accueil":"Étape 1 sur 6 - Accueil",
        "Prerequis":"Étape 2 sur 6 - Prérequis",
        "Presentation beneficiaire":"Étape 3 - Faisons connaissance",
        "Presentation assistant":"Étape 4 - Présentation de l’assistant",
        "Valeurs interseances":"Étape 5 - Valeurs repérées entre les séances",
        "Decision exploration":"Étape 6 - Choix de poursuivre",
        "Exploration IA":"Étape 7 - Exploration",
        "Mots a examiner":"Étape 8 - Hypothèse en cours",
        "Validation":"Étape 9 - Validation",
        "Controle completude":"Étape 10 - Contrôle de complétude",
        "Resultats":"Étape 11 - État actuel",
    }
    return labels.get(page, str(page))

def sidebar_progress():
    in_app=st.session_state.get("test_started",False)
    if LOGO_PATH.exists(): st.sidebar.image(str(LOGO_PATH),width=85)
    st.sidebar.markdown("### Clarté360")
    if in_app:
        steps=["Accueil","Prerequis","Presentation beneficiaire","Presentation assistant","Valeurs interseances","Decision exploration","Exploration IA","Mots a examiner","Validation","Controle completude","Resultats"]; current=st.session_state.page; idx=steps.index(current) if current in steps else 0; st.sidebar.progress(idx/(len(steps)-1)); st.sidebar.caption(f"Étape {idx+1} sur {len(steps)} - {current}")
        st.sidebar.markdown("---"); st.sidebar.download_button("💾 Sauvegarder mon travail (JSON)",data=payload_bytes(False),file_name=make_filename("rvc360_sauvegarde","json"),mime="application/json",use_container_width=True,on_click=lambda:record_save_event("sauvegarde_manuelle"))
        if st.sidebar.button("🚪 Quitter et préparer mon JSON",use_container_width=True): record_save_event("sortie_preparee"); close_runtime_session("sortie_preparee"); st.session_state.exit_json_ready=True; st.session_state.exit_mode="quit"; st.rerun()
        st.sidebar.caption(f"Temps cumulé : {format_duration(total_session_seconds())}")
    else: st.sidebar.markdown("### Session")
    st.sidebar.markdown("---")
    if st.sidebar.button("💬 Contacter Clarté360",use_container_width=True): st.session_state.show_contact_page=True; st.session_state.show_rgpd_page=False; st.rerun()
    if st.sidebar.button("RGPD et mentions légales",use_container_width=True): st.session_state.show_rgpd_page=True; st.session_state.show_contact_page=False; st.rerun()
    st.sidebar.caption(f"App v{APP_VERSION} · Socle {SOCLE_CLARTE360_VERSION} · RVC360 {RVC360_VERSION}")
    if not in_app and st.sidebar.button("Réinitialiser la session"): st.session_state.clear(); st.rerun()

def update_domain_memory(question: str, answer: str) -> None:
    text=normalize(f"{question} {answer}")
    keywords={
        "famille":["famille","parent","enfant","couple","frere","soeur","transmission"],
        "travail":["travail","metier","collegue","client","manager","entreprise","profession"],
        "relations":["ami","confiance","loyaute","relation","entraide"],
        "loisirs":["loisir","sport","cinema","musique","voyage","cuisine","nature","creation"],
        "emotions":["joie","fierte","colere","frustration","admiration","peur","tristesse","apaisement"],
        "histoire":["enfance","adolescence","passe","changement","periode","epoque"],
        "projections":["projet","avenir","reve","transmettre","proteger","heritage"],
        "conflits":["injustice","inacceptable","conflit","blesse","refuse","colere"],
    }
    hits=[d for d,words in keywords.items() if any(w in text for w in words)]
    domain=hits[0] if hits else st.session_state.get("current_domain") or "emotions"
    st.session_state.current_domain=domain
    st.session_state.domains_explored[domain]=int(st.session_state.domains_explored.get(domain,0))+1
    st.session_state.domains_not_explored=[d for d in EXPLORATION_DOMAINS if d not in st.session_state.domains_explored]

def choose_wide_question() -> str:
    unexplored=st.session_state.get("domains_not_explored",[])
    if unexplored:
        d=unexplored[0]
    else:
        d=min(EXPLORATION_DOMAINS, key=lambda x:int(st.session_state.domains_explored.get(x,0)))
    st.session_state.current_domain=d
    return f"J’aimerais maintenant changer d’angle. En pensant à {EXPLORATION_DOMAINS[d]}, quelle situation vous a récemment donné une forte satisfaction, une fierté, une colère ou une frustration ? Qu’est-ce qui comptait particulièrement pour vous ?"

def register_value_record(name: str, source: str, status: str, definition: str="", situations=None, emotions=None, certainty:int=0, alternatives=None) -> None:
    rec=st.session_state.value_records.get(name,{})
    rec.update({
        "nom_propose":name, "source":source, "statut":status,
        "definition_personnelle":definition or rec.get("definition_personnelle",""),
        "situations_associees":situations or rec.get("situations_associees",[]),
        "emotions_associees":emotions or rec.get("emotions_associees",[]),
        "degre_certitude":certainty, "date_decouverte":rec.get("date_decouverte") or now_iso(),
        "formulations_alternatives":alternatives or rec.get("formulations_alternatives",[]),
        "validation_finale":status=="validee",
    })
    st.session_state.value_records[name]=rec

def next_exploration_question() -> str:
    """Return a new prompt, never the same initial question after a completed value cycle."""
    idx = int(st.session_state.get("exploration_question_index", 0))
    if idx == 0 and not st.session_state.conversation:
        question = FALLBACK_QUESTIONS[0]
    else:
        alternatives = FALLBACK_QUESTIONS[1:]
        question = alternatives[(max(1, idx)-1) % len(alternatives)]
    st.session_state.exploration_question_index = idx + 1
    return question


def reset_for_new_exploration() -> None:
    # On conserve l'historique des hypothèses et les valeurs déjà validées.
    st.session_state.candidate_names=[]
    st.session_state.candidate_reasons={}
    st.session_state.candidate_evidence={}
    st.session_state.hypothesis_decisions={}
    st.session_state.validation_index=0
    st.session_state.validation_stage={}
    st.session_state.hypothesis_index=0
    st.session_state.hypothesis_queue=[]
    st.session_state.last_presented_hypotheses=[]
    st.session_state.turns_since_hypothesis=0
    st.session_state.current_question=next_exploration_question()
    st.session_state.page="Exploration IA"


def values_side_panel() -> None:
    values=validated_names()
    if not st.session_state.get("test_started"):
        return
    import base64
    avatar=""
    if CHATBOT_PATH.exists():
        avatar=base64.b64encode(CHATBOT_PATH.read_bytes()).decode("ascii")
    pills="".join(f'<div class="value-pill">{html.escape(v)}</div>' for v in values) or '<div class="small-muted" style="text-align:center">Aucune valeur validée pour le moment</div>'
    image=f'<img src="data:image/webp;base64,{avatar}" alt="Assistant Clarté360">' if avatar else ''
    st.markdown(f'<aside class="clarte-values-panel">{image}<h4>Mes valeurs fondamentales</h4>{pills}</aside>',unsafe_allow_html=True)


def auxiliary_back_button(key: str) -> None:
    if st.session_state.get("test_started"):
        st.info(f"Votre travail est conservé. Étape en cours : {sidebar_progress_label(st.session_state.page)}")
        if st.button("← Revenir à mon travail en cours", key=key, type="primary", use_container_width=True):
            st.session_state.show_contact_page=False
            st.session_state.show_rgpd_page=False
            st.rerun()

def _submission_id(question:str, answer:str)->str:
    import hashlib
    raw=f"{len(st.session_state.get('conversation',[]))}|{question}|{answer}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def queue_exploration_submission(answer:str) -> None:
    question=str(st.session_state.current_question)
    sid=_submission_id(question,answer)
    if sid==st.session_state.get("last_processed_submission_id"):
        return
    st.session_state.pending_submission={"id":sid,"question":question,"answer":answer,"created_at":now_iso()}
    st.session_state.pipeline_status="queued"
    st.session_state.pipeline_error=""


def process_pending_exploration_submission() -> bool:
    pending=st.session_state.get("pending_submission") or {}
    if st.session_state.get("pipeline_status")!="queued" or not pending:
        return False
    sid=str(pending.get("id",""))
    if sid and sid==st.session_state.get("last_processed_submission_id"):
        st.session_state.pipeline_status="completed"
        st.session_state.pending_submission={}
        return False
    st.session_state.pipeline_status="running"
    answer=str(pending.get("answer","")).strip()
    previous_question=str(pending.get("question",st.session_state.current_question))
    with st.spinner("Le moteur RVC360 examine votre réponse une seule fois..."):
        try:
            result=run_rvc360_pipeline(answer)
            st.session_state.ai_engine_status="operationnel"
        except Exception as exc:
            st.session_state.pipeline_status="error"
            st.session_state.pipeline_error=str(exc)
            business_trace("erreur_ia",f"{type(exc).__name__}: {str(exc)[:120]}")
            return True
    card=result["analysis_card"]
    st.session_state.analysis_card=card
    st.session_state.analysis_history.append({"date":now_iso(),"question":previous_question,"reponse":answer,"fiche":card})
    if card.get("apport_nouveau",True): st.session_state.analysis_no_novelty_count=0
    else: st.session_state.analysis_no_novelty_count=int(st.session_state.get("analysis_no_novelty_count",0))+1
    presented=merge_hypotheses(result["hypotheses"])
    st.session_state.conversation.append({"question":previous_question,"answer":answer,"reformulation":result["reformulation"],"hypotheses_proposees":presented,"date":now_iso(),"domaine":st.session_state.get("current_domain","")})
    update_domain_memory(previous_question,answer)
    st.session_state.exploration_summary=_flatten_analysis_text(card)[-1600:]
    next_question=result["question_suivante"].strip()
    same_domain_turns=sum(1 for t in st.session_state.conversation[-3:] if t.get("domaine")==st.session_state.get("current_domain"))
    if normalize(next_question)==normalize(previous_question) or same_domain_turns>=2 or st.session_state.get("analysis_no_novelty_count",0)>=1:
        if st.session_state.get("current_domain") and st.session_state.current_domain not in st.session_state.saturated_subjects:
            st.session_state.saturated_subjects.append(st.session_state.current_domain)
        next_question=choose_wide_question()
    st.session_state.current_question=next_question
    st.session_state.exploration_complete=False
    st.session_state.pipeline_status="completed"
    st.session_state.last_processed_submission_id=sid
    st.session_state.pending_submission={}
    reset_voice_capture(clear_text=True)
    st.session_state.pop("explore_text",None)
    st.session_state["last_turn_completed"]=True
    business_trace("tour_ia",f"hypotheses={len(presented)}")
    if presented:
        st.session_state.hypothesis_queue=[n for n in st.session_state.candidate_names if n not in st.session_state.completed_hypotheses]
        st.session_state.hypothesis_index=0
        st.session_state.page="Mots a examiner"
    st.rerun()
    return True


def render_business():
    page=st.session_state.page; display_header(); values_side_panel()
    if page=="Accueil":
        st.markdown('<div class="clarte-box"><b>Objectif unique : rechercher et valider vos valeurs fondamentales.</b><br>Cette application prolonge l’exercice inter-séance engagé avec votre accompagnateur. Elle ne fait ni coaching, ni diagnostic, ni orientation.</div>',unsafe_allow_html=True)
        value_reminder()
        if not CATALOGUE: st.error("Le référentiel RVC360 n'a pas pu être chargé.")
        if ai_ready(): st.success("Moteur IA RVC360 configuré et disponible.")
        else: st.error("Le moteur IA RVC360 n'est pas configuré.")
        if st.button("Commencer",type="primary",disabled=not(CATALOGUE and ai_ready())):
            st.session_state.page="Prerequis"; business_trace("debut_metier"); st.rerun()

    elif page=="Prerequis":
        st.title("1. Prérequis obligatoire")
        st.warning("La première valeur doit avoir été recherchée et validée avec votre accompagnateur avant d'utiliser cette application.")
        value_reminder()
        confirmed=st.radio("Avez-vous déjà identifié et validé au moins une valeur avec votre accompagnateur ?",["Choisissez une réponse","Oui","Non"],index=0,key="prereq_yesno")
        if confirmed=="Non":
            st.error("Le parcours ne peut pas commencer. Reprenez d'abord cette première étape avec votre accompagnateur.")
            return
        if confirmed!="Oui": return
        st.session_state.prerequisite_confirmed=True
        st.info("Votre accompagnateur a pu valider avec vous une ou plusieurs valeurs. Indiquez-les toutes, une par champ.")
        count=int(st.number_input("Combien de valeurs avez-vous déjà identifiées et validées avec votre accompagnateur ?",min_value=1,max_value=15,value=int(st.session_state.get("prerequisite_count",1)),step=1))
        st.session_state.prerequisite_count=count
        entries=[]
        for i in range(count):
            val=st.text_input(f"Valeur déjà identifiée n°{i+1}",key=f"prereq_free_{i}",placeholder="Écrivez librement le mot ou l'expression retenue")
            if val.strip(): entries.append(val.strip())
        if st.button("Examiner mes formulations",type="primary",disabled=len(entries)!=count):
            st.session_state.prerequisite_pending=[resolve_prerequisite(x) for x in entries]
            st.rerun()
        confirmed_values=[]
        for i,item in enumerate(st.session_state.get("prerequisite_pending",[])):
            st.markdown(f"### Formulation : {item['raw']}")
            props=item.get("propositions",[])
            if item["status"]=="exact":
                name=props[0]; info=value_info(name); st.write(f"**Valeur trouvée : {name}**"); st.write(info.get("definition",""))
                agree=st.radio("Êtes-vous d'accord avec cette définition ?",["Choisissez","Oui","Non, je donne ma propre définition"],key=f"defagree_{i}")
                own=""
                if agree.startswith("Non"): own=st.text_area("Votre définition personnelle",key=f"owndef_{i}")
                if agree!="Choisissez" and (agree=="Oui" or own.strip()): confirmed_values.append((name,own.strip() or info.get("definition",""),False))
            elif props:
                st.write("Votre formulation semble proche de plusieurs noms de valeurs. Rien n'est imposé.")
                choice=st.radio("Quel nom correspond le mieux à ce que vous avez validé avec votre accompagnateur ?",["Aucune de ces propositions"]+props,key=f"prop_{i}")
                if choice!="Aucune de ces propositions":
                    info=value_info(choice); st.write(info.get("definition","")); own=st.text_area("Conservez cette définition ou écrivez la vôtre",value=info.get("definition",""),key=f"propdef_{i}")
                    if own.strip(): confirmed_values.append((choice,own.strip(),False))
                else:
                    custom_name=st.text_input("Nom de votre valeur",value=item['raw'],key=f"customname_{i}")
                    custom_def=st.text_area("Que signifie cette valeur pour vous ?",key=f"customdef_{i}")
                    if custom_name.strip() and custom_def.strip(): confirmed_values.append((custom_name.strip(),custom_def.strip(),True))
            else:
                st.write("Cette formulation n'existe pas telle quelle dans le référentiel. Elle peut néanmoins être retenue pour vous.")
                custom_name=st.text_input("Nom de votre valeur",value=item['raw'],key=f"newname_{i}")
                custom_def=st.text_area("Que signifie cette valeur pour vous ?",key=f"newdef_{i}")
                if custom_name.strip() and custom_def.strip(): confirmed_values.append((custom_name.strip(),custom_def.strip(),True))
        pending_count=len(st.session_state.get("prerequisite_pending",[]))
        if pending_count and st.button("Valider toutes mes valeurs déjà identifiées",type="primary",disabled=len(confirmed_values)!=pending_count):
            st.session_state.existing_values=[]
            for name,definition,is_custom in confirmed_values:
                st.session_state.existing_values.append(name); st.session_state.personal_defs[name]=definition
                st.session_state.validation[name]={"importante":True,"tres_importante":True,"fondamentale":True,"origine_validation":"accompagnateur"}
                if is_custom:
                    st.session_state.custom_values[name]={"definition":definition,"famille":"Valeur personnelle","notified":False}
            st.session_state.existing_values=list(dict.fromkeys(st.session_state.existing_values))
            for name,definition,is_custom in confirmed_values:
                register_value_record(name,"accompagnateur","validee",definition,certainty=100)
            business_trace("prerequis_valide",", ".join(st.session_state.existing_values)); st.session_state.page="Presentation beneficiaire"; st.rerun()

    elif page=="Presentation beneficiaire":
        st.title("2. Faisons connaissance")
        st.markdown('<div class="clarte-box">Vous vous êtes déjà présenté à votre accompagnateur. Accepteriez-vous de m’en dire un peu sur vous afin que je puisse mieux vous accompagner dans cette recherche de valeurs ? Vous restez libre de ne pas répondre à une question.</div>',unsafe_allow_html=True)
        profile=st.session_state.get("beneficiary_profile",{})
        preferred=st.text_input("Comment souhaitez-vous que je vous appelle ?",value=profile.get("prenom_usage",st.session_state.beneficiaire.get("prenom","")))
        intro=st.text_area("Parlez-moi librement de vous : votre situation actuelle, votre parcours, les personnes ou activités importantes, vos passions, vos projets ou ce qui compte particulièrement aujourd’hui.",value=profile.get("presentation_libre",""),height=190)
        goal=st.text_area("Qu’aimeriez-vous mieux comprendre ou vérifier grâce à cette recherche de valeurs ?",value=profile.get("objectif_demarche",""),height=100)
        st.caption("Il ne s’agit pas d’un formulaire administratif. Quelques éléments sincères suffisent.")
        if st.button("Poursuivre",type="primary",disabled=not intro.strip()):
            st.session_state.beneficiary_profile={"prenom_usage":preferred.strip(),"presentation_libre":intro.strip(),"objectif_demarche":goal.strip(),"date":now_iso()}
            st.session_state.profile_complete=True
            business_trace("presentation_beneficiaire")
            st.session_state.page="Presentation assistant"; st.rerun()

    elif page=="Presentation assistant":
        st.title("3. Comment je vais vous accompagner")
        text=("Je suis l’assistant Clarté360 dédié à la recherche de vos valeurs. Je complète le travail réalisé avec votre accompagnateur, sans le remplacer. "
              "Je vais alterner les sujets pour mieux comprendre ce qui vous pousse régulièrement à agir ou à réagir. Je pourrai proposer des hypothèses, mais je peux me tromper et vous seul pourrez valider une valeur. "
              "Une valeur solide se retrouve généralement dans plusieurs situations ou domaines de vie. L’objectif indicatif est souvent d’en identifier environ 8 à 12, mais ce n’est jamais un quota : votre liste peut être plus courte ou plus longue.")
        st.markdown(f'<div class="clarte-box">{text}</div>',unsafe_allow_html=True)
        speak_button(text,"assistant_intro")
        mode=st.radio("Comment souhaitez-vous répondre pendant l’exploration ?",["Écrit ou voix, selon les moments","Principalement à l’écrit","Principalement à la voix"],index=0)
        if st.button("J’ai compris, continuer",type="primary"):
            st.session_state.assistant_presented=True; st.session_state.interaction_preferences={"mode":mode}; business_trace("presentation_assistant"); st.session_state.page="Valeurs interseances"; st.rerun()

    elif page=="Valeurs interseances":
        st.title("4. Valeurs découvertes depuis votre dernière séance")
        answer=st.radio("Depuis votre dernière séance, avez-vous découvert une ou plusieurs valeurs personnelles ?",["Choisissez une réponse","Non","Oui"],key="inter_yes")
        if answer=="Non":
            if st.button("Continuer",type="primary"):
                st.session_state.page="Decision exploration"; business_trace("aucune_valeur_interseance"); st.rerun()
        elif answer=="Oui":
            count=int(st.number_input("Combien ?",1,10,1,key="inter_count"))
            records=[]
            sources=["Observation personnelle ou cahier","Émotion ou réaction forte","Événement vécu","Échange avec un proche","Autre"]
            for i in range(count):
                st.markdown(f"### Valeur repérée n°{i+1}")
                name=st.text_input("Nom proposé",key=f"inter_name_{i}")
                source=st.selectbox("Comment l’avez-vous découverte ?",sources,key=f"inter_source_{i}")
                meaning=st.text_area("Que signifie ce mot pour vous ?",key=f"inter_meaning_{i}")
                situations=st.text_area("Dans quelles situations l’avez-vous reconnue ?",key=f"inter_situations_{i}")
                reactions=st.text_area("Que ressentez-vous lorsqu’elle est respectée ou bafouée ?",key=f"inter_reactions_{i}")
                certainty=st.slider("À quel point êtes-vous certain qu’il s’agit d’une valeur importante pour vous ?",0,100,50,key=f"inter_cert_{i}")
                if name.strip() and meaning.strip() and situations.strip(): records.append({"nom":name.strip(),"source":source,"definition":meaning.strip(),"situations":[situations.strip()],"emotions":[reactions.strip()] if reactions.strip() else [],"certitude":certainty})
            if st.button("Enregistrer ces valeurs et continuer",type="primary",disabled=len(records)!=count):
                st.session_state.inter_session_values=records
                for r in records:
                    register_value_record(r["nom"],r["source"],"hypothese",r["definition"],r["situations"],r["emotions"],r["certitude"])
                    if r["nom"] not in st.session_state.candidate_names: st.session_state.candidate_names.append(r["nom"])
                    st.session_state.personal_defs[r["nom"]]=r["definition"]
                    st.session_state.hypothesis_status[r["nom"]]="a_examiner"
                business_trace("valeurs_interseances",str(len(records))); st.session_state.page="Decision exploration"; st.rerun()

    elif page=="Decision exploration":
        st.title("5. Souhaitez-vous rechercher d’autres valeurs ?")
        decision=st.radio("Souhaitez-vous que je vous aide à rechercher d’autres valeurs ?",["Choisissez une réponse","Oui","Non, je préfère contrôler ce que j’ai déjà"],key="decision_explore")
        if decision.startswith("Oui") and st.button("Ouvrir l’exploration",type="primary"):
            st.session_state.exploration_wanted=True
            st.session_state.current_question=choose_wide_question()
            st.session_state.page="Exploration IA"; business_trace("exploration_acceptee"); st.rerun()
        if decision.startswith("Non") and st.button("Contrôler la complétude",type="primary"):
            st.session_state.exploration_wanted=False; st.session_state.page="Controle completude"; business_trace("exploration_refusee"); st.rerun()

    elif page=="Exploration IA":
        st.title("2. Recherche guidée des autres valeurs"); value_reminder()
        if st.session_state.get("pipeline_status")=="queued":
            process_pending_exploration_submission()
        elif st.session_state.get("pipeline_status")=="running":
            st.warning("Une analyse a été interrompue avant sa fin. Aucun nouvel appel n'est lancé automatiquement.")
            if st.button("Relancer cette analyse une seule fois",type="primary"):
                st.session_state.pipeline_status="queued"
                st.rerun()
            return
        st.caption("Une seule question à la fois. Vous pouvez écrire ou enregistrer votre réponse. L'IA travaille uniquement sur vos mots et ne décide jamais à votre place.")
        for turn_no,turn in enumerate(st.session_state.conversation[-8:], start=max(1,len(st.session_state.conversation)-7)):
            with st.chat_message("assistant"):
                if turn.get("reformulation"): st.write(turn["reformulation"])
                if turn.get("hypotheses_proposees"):
                    names=turn["hypotheses_proposees"]
                    st.markdown("**Hypothèse(s) de mot repérée(s) à ce moment :** " + ", ".join(f"`{n}`" for n in names))
                    st.caption("Ces mots restent des hypothèses. Ils doivent être examinés un par un avant toute validation.")
                st.write(turn["question"])
            with st.chat_message("user"): st.write(turn["answer"])
        with st.chat_message("assistant"): st.write(st.session_state.current_question)
        speak_button(st.session_state.current_question,"q")
        st.markdown("**Deux façons de répondre :** écrivez dans la zone ci-dessous, ou utilisez l’enregistreur. Pour la voix : cliquez sur le micro, parlez, puis cliquez sur le **carré d’arrêt**. Cliquez ensuite sur **Transcrire** et relisez le texte avant de le valider.")
        st.caption("Confidentialité : le fichier audio sert uniquement à la transcription. Il n'est ni ajouté au JSON, ni sauvegardé dans l'application. Seul le texte que vous validez est conservé.")
        typed=st.text_area("Votre réponse écrite",height=130,key="explore_text",placeholder="Écrivez librement, sans limite de longueur.")
        audio=None
        audio_key=f"explore_audio_{st.session_state.get('audio_widget_version',0)}"
        rec_col,_=st.columns([1.15,1.85])
        with rec_col:
            if hasattr(st,"audio_input"):
                audio=st.audio_input("Enregistrer ma réponse",key=audio_key)
            else:
                st.warning("L’enregistreur vocal n’est pas disponible dans cette version de Streamlit.")
        if audio:
            st.success("Enregistrement arrêté et prêt à être transcrit.")
            b1,b2,_=st.columns([1.15,1.25,1.6])
            with b1:
                do_transcribe=st.button("Transcrire",type="primary",key=f"transcribe_{st.session_state.get('audio_widget_version',0)}",use_container_width=True)
            with b2:
                do_rerecord=st.button("Réenregistrer",key=f"rerecord_audio_{st.session_state.get('audio_widget_version',0)}",use_container_width=True)
            if do_rerecord:
                reset_voice_capture(clear_text=True)
                st.session_state.pop("explore_text",None)
                st.rerun()
            if do_transcribe:
                with st.spinner("Transcription en cours..."):
                    try:
                        transcript=transcribe_audio(audio)
                        st.session_state["voice_draft"]=transcript
                        st.session_state.pop("voice_edit",None)
                        st.session_state.pop("voice_last_error",None)
                        # Le composant est renouvelé : l’audio temporaire n’est plus réutilisable.
                        st.session_state["audio_widget_version"]+=1
                        st.rerun()
                    except Exception as exc:
                        st.session_state["voice_last_error"]=str(exc)
                        st.error(f"La transcription n’a pas pu être réalisée : {exc}")
                        st.info("Vous pouvez cliquer sur Réenregistrer puis refaire une prise. Vérifiez que vous avez bien arrêté avec le carré.")
        elif st.session_state.get("voice_last_error"):
            st.error(f"Dernier échec de transcription : {st.session_state.voice_last_error}")
            if st.button("Recommencer mon enregistrement",key="restart_after_voice_error"):
                reset_voice_capture(clear_text=True)
                st.rerun()
        if st.session_state.get("voice_draft"):
            st.info("Transcription proposée. Relisez-la, corrigez-la si nécessaire, puis validez-la. L’audio n’est pas conservé.")
            typed=st.text_area("Texte transcrit à valider",value=st.session_state.voice_draft,height=160,key="voice_edit")
            v1,v2,_=st.columns([1.2,1.5,1.3])
            with v1:
                if st.button("Réenregistrer ma réponse",key="redo_after_transcript",use_container_width=True):
                    reset_voice_capture(clear_text=True)
                    st.session_state.pop("explore_text",None)
                    st.rerun()
            with v2:
                st.caption("Seul le texte que vous validerez sera transmis au moteur RVC360 et conservé dans le JSON.")
        processing=st.session_state.get("pipeline_status") in ("queued","running")
        if st.button("Valider ma réponse et afficher la question suivante",type="primary",disabled=(not str(typed).strip()) or processing):
            queue_exploration_submission(str(typed).strip())
            st.rerun()
        if st.session_state.get("pipeline_status")=="error":
            st.error("Le moteur RVC360 n'a pas pu terminer l'analyse. Aucun nouvel appel ne sera lancé sans votre action.")
            st.caption(st.session_state.get("pipeline_error",""))
            e1,e2=st.columns(2)
            with e1:
                if st.button("Relancer une seule fois l'analyse",type="primary",use_container_width=True):
                    st.session_state.pipeline_status="queued"
                    st.session_state.pipeline_error=""
                    st.rerun()
            with e2:
                if st.button("Annuler et modifier ma réponse",use_container_width=True):
                    st.session_state.pipeline_status="idle"
                    st.session_state.pipeline_error=""
                    st.session_state.pending_submission={}
                    st.rerun()
        if st.session_state.pop("last_turn_completed",False):
            st.success("Votre réponse a bien été prise en compte. La nouvelle question est affichée ci-dessus.")
        if st.session_state.candidate_names:
            st.info(f"{len(st.session_state.candidate_names)} hypothèse(s) sont disponibles. Elles doivent d'abord être triées et clarifiées.")
            if st.button("Trier et clarifier les hypothèses",type="primary",use_container_width=True): st.session_state.page="Mots a examiner"; st.rerun()
        if st.session_state.get("hypothesis_history"):
            with st.expander("Historique des hypothèses évoquées", expanded=False):
                latest={}
                for event in st.session_state.hypothesis_history:
                    latest[event["nom"]]=event
                for name,event in latest.items():
                    status=st.session_state.hypothesis_status.get(name,event.get("statut","a_examiner"))
                    st.markdown(f"**{name}** — statut : `{status}`")
                    if event.get("preuve"): st.caption(f"Appui dans vos mots : {event['preuve']}")
                    if status in ("abandonnee","ecartee") and st.button(f"Réexaminer {name}",key=f"reopen_{normalize(name)}"):
                        if name in st.session_state.abandoned_hypotheses: st.session_state.abandoned_hypotheses.remove(name)
                        if name in st.session_state.discarded: st.session_state.discarded.remove(name)
                        if name not in st.session_state.candidate_names: st.session_state.candidate_names.append(name)
                        st.session_state.hypothesis_status[name]="a_examiner"
                        st.session_state.hypothesis_queue=[name]
                        st.session_state.hypothesis_index=0
                        st.session_state.page="Mots a examiner"
                        st.rerun()
        if st.button("Continuer l'exploration avant d'examiner les hypothèses",use_container_width=True):
            st.session_state.current_question=next_exploration_question()
            reset_voice_capture(clear_text=True)
            st.session_state.pop("explore_text",None); st.rerun()

    elif page=="Mots a examiner":
        st.title("3. Examiner une hypothèse à la fois"); value_reminder()
        st.markdown('<div class="clarte-box">Nous examinons une seule hypothèse jusqu’à sa validation ou son abandon. Les autres restent en attente et seront proposées ensuite.</div>',unsafe_allow_html=True)
        if not st.session_state.hypothesis_queue:
            st.session_state.hypothesis_queue=[n for n in st.session_state.candidate_names if n not in st.session_state.completed_hypotheses and n not in st.session_state.abandoned_hypotheses]
            st.session_state.hypothesis_index=0
        queue=st.session_state.hypothesis_queue
        if not queue:
            st.info("Il ne reste aucune hypothèse à examiner.")
            if st.button("Relancer la recherche avec une autre question",type="primary"):
                reset_for_new_exploration(); st.rerun()
            return
        idx=min(int(st.session_state.hypothesis_index),len(queue)-1)
        name=queue[idx]; info=value_info(name)
        st.progress((idx+1)/len(queue),text=f"Hypothèse {idx+1} sur {len(queue)}")
        st.markdown(f"## {name}")
        st.write(info.get("definition", ""))
        if st.session_state.candidate_evidence.get(name):
            st.caption(f"Élément provenant de vos mots : {st.session_state.candidate_evidence[name]}")
        decision=st.radio("Ce mot est-il vraiment dans l’idée de ce que vous vouliez exprimer ?",["Choisissez une réponse","Non, pas du tout","Peut-être, je veux le clarifier","Oui, ce mot semble juste"],key=f"hyp_one_{name}")
        if decision=="Non, pas du tout":
            if st.button("Abandonner cette hypothèse et passer à la suivante",type="primary"):
                if name not in st.session_state.discarded: st.session_state.discarded.append(name)
                if name not in st.session_state.abandoned_hypotheses: st.session_state.abandoned_hypotheses.append(name)
                st.session_state.hypothesis_status[name]="abandonnee"
                st.session_state.hypothesis_index=idx+1
                if idx+1>=len(queue):
                    reset_for_new_exploration()
                st.rerun()
        elif decision in ("Peut-être, je veux le clarifier","Oui, ce mot semble juste"):
            proposed=st.session_state.personal_defs.get(name) or info.get("definition","")
            st.session_state.personal_defs[name]=st.text_area("Que signifie précisément ce mot pour vous ? Vous pouvez accepter, compléter ou remplacer la définition.",value=proposed,key=f"one_def_{name}")
            c1,c2=st.columns(2)
            with c1:
                if st.button("Ce mot ne convient finalement pas",use_container_width=True):
                    if name not in st.session_state.discarded: st.session_state.discarded.append(name)
                    if name not in st.session_state.abandoned_hypotheses: st.session_state.abandoned_hypotheses.append(name)
                    st.session_state.hypothesis_status[name]="abandonnee"
                    st.session_state.hypothesis_index=idx+1
                    if idx+1>=len(queue): reset_for_new_exploration()
                    st.rerun()
            with c2:
                if st.button("Passer au questionnaire spécifique pour cette valeur",type="primary",disabled=not st.session_state.personal_defs[name].strip(),use_container_width=True):
                    st.session_state.candidate_names=[name]
                    st.session_state.hypothesis_status[name]="examinee"
                    st.session_state.validation_index=0
                    st.session_state.validation_stage[name]=0
                    st.session_state.page="Validation"
                    business_trace("hypothese_clarifiee",name)
                    st.rerun()
        else:
            st.caption("Commencez par indiquer si cette hypothèse correspond réellement à votre idée.")

    elif page=="Validation":
        st.title("4. Questionnaire spécifique HEC"); value_reminder()
        names=list(dict.fromkeys(st.session_state.candidate_names))
        if not names: st.warning("Aucune hypothèse n'est prête à être validée."); return
        idx=min(st.session_state.validation_index,len(names)-1); name=names[idx]; info=value_info(name)
        st.progress((idx)/max(1,len(names)),text=f"Valeur {idx+1} sur {len(names)}")
        st.markdown(f"## {name}"); st.write(st.session_state.personal_defs.get(name) or info.get("definition",""))
        stage=st.session_state.validation_stage.get(name,0); current=st.session_state.validation.get(name,{"importante":False,"tres_importante":False,"fondamentale":False})
        questions=[("importante","Cette valeur est-elle importante pour vous ?"),("tres_importante","Cette valeur est-elle très importante pour vous ?"),("fondamentale","Cette valeur est-elle fondamentale pour vous ?")]
        if stage<3:
            field,q=questions[stage]; speak_button(q,f"val_{stage}"); answer=st.radio(q,["Choisissez une réponse","Oui","Non"],key=f"valradio_{name}_{stage}")
            if st.button("Valider cette réponse",type="primary",disabled=answer=="Choisissez une réponse"):
                current[field]=(answer=="Oui"); st.session_state.validation[name]=current
                if field=="fondamentale" and answer=="Oui":
                    if name not in st.session_state.validated_app_values:
                        st.session_state.validated_app_values.append(name)
                    st.session_state.hypothesis_status[name]="validee"
                    register_value_record(name,"application","validee",st.session_state.personal_defs.get(name) or value_info(name).get("definition",""),certainty=100)
                    if name in st.session_state.custom_values and not st.session_state.custom_values[name].get("notified"):
                        notify_new_value(name,st.session_state.personal_defs.get(name) or value_info(name).get("definition",""))
                        st.session_state.custom_values[name]["notified"]=True
                if answer=="Oui": st.session_state.validation_stage[name]=stage+1
                else:
                    st.session_state.validation_stage[name]=3; current["fondamentale"]=False
                    st.session_state.hypothesis_status[name]="a_revoir"
                    register_value_record(name,"application","a_revoir",st.session_state.personal_defs.get(name,""),certainty=40)
                st.rerun()
        else:
            if current.get("fondamentale"): st.success("Cette valeur a franchi successivement les trois niveaux et est validée comme fondamentale.")
            else: st.info("Cette hypothèse n'est pas validée comme valeur fondamentale à ce stade. Elle pourra être reprise avec l'accompagnateur.")
            st.session_state.comments[name]=st.text_area("Commentaire facultatif",value=st.session_state.comments.get(name,""),key=f"comment_{name}")
            if st.button("Continuer",type="primary"):
                if name not in st.session_state.completed_hypotheses:
                    st.session_state.completed_hypotheses.append(name)
                queue=st.session_state.get("hypothesis_queue",[])
                next_idx=int(st.session_state.get("hypothesis_index",0))+1
                st.session_state.hypothesis_index=next_idx
                if next_idx < len(queue):
                    st.session_state.candidate_names=queue
                    st.session_state.page="Mots a examiner"
                else:
                    st.session_state.page="Controle completude"
                st.rerun()

    elif page=="Controle completude":
        st.title("10. Contrôle de complétude")
        vals=validated_names()
        explored=list(st.session_state.get("domains_explored",{}).keys())
        missing=[d for d in EXPLORATION_DOMAINS if d not in explored]
        close_values=[]
        for i,a in enumerate(vals):
            for b in vals[i+1:]:
                if SequenceMatcher(None,normalize(a),normalize(b)).ratio()>.72: close_values.append((a,b))
        st.markdown(f"**Valeurs actuellement validées : {len(vals)}**")
        if len(vals)<8: st.info("Votre liste contient moins de 8 valeurs. Ce n’est pas un problème : 8 à 12 est un repère indicatif, jamais un quota.")
        if missing: st.warning("Domaines encore peu ou pas explorés : "+", ".join(missing))
        else: st.success("Les principaux domaines d’exploration ont été abordés.")
        if close_values: st.warning("Certaines valeurs semblent proches et méritent peut-être d’être différenciées : "+" ; ".join(f"{a} / {b}" for a,b in close_values))
        represented=st.radio("Cette liste représente-t-elle suffisamment ce qui vous pousse à agir, choisir, accepter, refuser, vous engager, vous protéger ou réagir ?",["Choisissez","Oui","Partiellement","Non"],key="complete_rep")
        blind=st.text_area("Y a-t-il un angle, une situation ou une valeur que vous souhaiteriez encore explorer ?",key="complete_blind")
        if st.button("Enregistrer ce contrôle",type="primary",disabled=represented=="Choisissez"):
            st.session_state.completion_check={"nombre_valeurs":len(vals),"domaines_explores":explored,"domaines_non_explores":missing,"valeurs_proches":close_values,"representation":represented,"angles_a_reprendre":blind.strip(),"date":now_iso()}
            st.session_state.page="Resultats"; business_trace("controle_completude",represented); st.rerun()
        if st.button("Reprendre l’exploration"):
            st.session_state.current_question=choose_wide_question(); st.session_state.page="Exploration IA"; st.rerun()

    elif page=="Resultats":
        st.title("5. État actuel de ma recherche"); value_reminder()
        validated=validated_names(); st.metric("Nombre de valeurs fondamentales validées",len(validated))
        for idx,name in enumerate(validated,1):
            info=value_info(name); source="Séance avec l'accompagnateur" if name in st.session_state.existing_values else "Application"
            st.markdown(f"### {idx}. {name}"); st.caption(f"{info.get('famille','')} - Origine : {source}"); st.write(st.session_state.personal_defs.get(name) or info.get("definition",""))
        st.markdown('<div class="clarte-box">Cette page n’est pas une fin imposée. Vous pouvez rechercher une autre valeur, revoir une hypothèse ou terminer volontairement votre exercice inter-séance.</div>',unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1:
            if st.button("🔄 Rechercher une autre valeur",type="primary",use_container_width=True):
                reset_for_new_exploration(); st.rerun()
        with c2:
            if st.button("↩️ Revoir mes hypothèses",use_container_width=True):
                latest=[]
                for event in st.session_state.get("hypothesis_history",[]):
                    if event["nom"] not in latest and event["nom"] not in validated: latest.append(event["nom"])
                st.session_state.hypothesis_queue=latest
                st.session_state.hypothesis_index=0
                st.session_state.page="Mots a examiner"
                st.rerun()
        st.divider(); st.subheader("Documents")
        c1,c2=st.columns(2)
        with c1: st.download_button("Télécharger le rapport PDF",create_pdf(),file_name=make_filename("RVC360_valeurs","pdf"),mime="application/pdf",use_container_width=True)
        with c2: st.download_button("Télécharger les données JSON",payload_bytes(bool(st.session_state.exploration_complete)),file_name=make_filename("RVC360_valeurs","json"),mime="application/json",use_container_width=True,on_click=lambda:record_save_event("telechargement_json"))
        st.divider()
        finish=st.radio("Pensez-vous avoir identifié l’ensemble des valeurs qui vous font agir et réagir ?",["Je souhaite encore poursuivre ma recherche","Oui, je pense avoir suffisamment identifié mes valeurs"],key="finish_consent")
        if finish.startswith("Oui"):
            st.warning("La fin de la recherche dépend uniquement de votre décision. Vous pourrez toujours reprendre ultérieurement avec votre fichier JSON.")
            if st.button("Confirmer la fin de mon exercice inter-séance",type="primary",use_container_width=True):
                st.session_state.exploration_complete=True; st.session_state.closure_decision="cloture_volontaire"; close_runtime_session("parcours_termine_volontaire"); business_trace("fin_volontaire_consentie"); st.success("Votre exercice est marqué comme terminé. Téléchargez votre PDF et votre JSON avant de quitter.")

def exit_prepared_screen():
    display_header(); st.success("Votre JSON de sortie est prêt à être téléchargé."); st.markdown("Téléchargez le fichier dans la colonne de gauche. Il permettra de reprendre l'application.")
def expired_screen():
    display_header(); st.warning(f"La session a été arrêtée automatiquement après {get_session_limit_minutes()} minutes sans activité."); st.markdown("Téléchargez ce JSON pour reprendre le travail lors de la prochaine connexion."); record_save_event("sauvegarde_automatique_expiration"); st.download_button("Télécharger mon JSON de reprise",data=payload_bytes(False),file_name=make_filename("rvc360_reprise_timeout","json"),mime="application/json",type="primary")
def install_beforeunload_warning():
    if st.session_state.get("test_started") and not st.session_state.get("json_downloaded"):
        components.html("""<script>window.parent.onbeforeunload=function(e){const m='Avant de quitter, utilisez le bouton Clarté360 : Quitter et préparer mon JSON.';e.preventDefault();e.returnValue=m;return m;};</script>""",height=0)

def main():
    init_state(); sidebar_progress(); install_beforeunload_warning()
    if st.session_state.get("show_contact_page"): contact_page(); return
    if st.session_state.get("show_rgpd_page"): rgpd_page(); return
    if st.session_state.get("session_expired"): expired_screen(); return
    if st.session_state.get("test_started"):
        if st.session_state.get("exit_json_ready"): exit_prepared_screen(); return
        timeout_watchdog(); check_session_limit(); render_business(); return
    choice=st.session_state.get("welcome_choice")
    if choice=="import": import_json_screen()
    elif choice=="new": identification_screen()
    else: welcome_screen()

if __name__=="__main__": main()
