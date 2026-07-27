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

APP_VERSION = "1.0.0-preproduction"
SOCLE_CLARTE360_VERSION = "1.8"
APP_NAME = "Recherche de mes valeurs"
APP_FULL_NAME = "Clarté360 - Recherche de mes valeurs"
FRAMEWORK_VERSION = "4.0"
RVC360_VERSION = "1.1"
RGPD_TEXT_VERSION = "RGPD-Clarte360-RVC360-v1.2-2026-07"
OFFICIAL_TEAL = "#008080"
LIGHT_TEAL = "#E6F4F4"
DARK_TEXT = "#243A3A"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "site_icon.png"
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
    "Racontez une situation, récente ou ancienne, dans laquelle vous vous êtes senti pleinement en accord avec vous-même. Qu'est-ce qui comptait particulièrement pour vous ?",
    "Décrivez une situation qui vous a fait réagir fortement. Qu'est-ce qui vous a dérangé ou touché précisément ?",
    "Pensez à un choix difficile que vous assumez encore aujourd'hui. Qu'avez-vous voulu préserver ou privilégier ?",
    "Quelles personnes admirez-vous, et pour quelles raisons concrètes ?",
    "Dans quelles situations vous sentez-vous le plus engagé, vivant ou à votre place ?",
    "Qu'est-ce que vous ne seriez pas prêt à sacrifier, même pour davantage d'argent, de confort ou de réussite ?",
]
FORBIDDEN_PATTERNS = [r"\bvous etes\b", r"\bvotre personnalite\b", r"\bcela revele\b", r"\bcela cache\b", r"\bau fond de vous\b", r"\ben realite vous\b", r"\binconsciemment\b", r"\bprobablement parce que\b", r"\bvotre vraie valeur\b", r"\bvous souffrez de\b", r"\bcela prouve que\b", r"\bvotre peur montre\b", r"\bvotre colere signifie\b", r"\bvous cherchez a compenser\b"]
SYSTEM_RVC360 = """
TU ES LE FACILITATEUR RVC360 DE CLARTE360.
MISSION UNIQUE : aider le bénéficiaire à rechercher ce qui compte fondamentalement pour lui, à clarifier ses propres mots et à examiner des termes du Référentiel des Valeurs Clarté360. Tu ne décides jamais de ses valeurs.
REGLE ABSOLUE : ZERO INTERPRETATION. Tu n'attribues jamais une cause, une intention, un besoin caché, un trait de personnalité, une émotion non déclarée ou une valeur non validée.
PERIMETRE : tu ne fais ni coaching, ni bilan de compétences, ni orientation, ni conseil, ni test de personnalité.
METHODE : une seule question ouverte à la fois ; appui exclusif sur les mots et faits exprimés ; demande de signification personnelle ; reformulation brève soumise à confirmation ; hypothèses multiples comparées ; preuve textuelle obligatoire ; insuffisance d'éléments explicitement dite ; liberté totale d'accepter, refuser, ajouter ou renommer ; aucune question contenant le nom d'une valeur attendue ; aucune répétition inutile.
LANGAGE INTERDIT : "Vous êtes...", "votre personnalité...", "cela révèle...", "cela cache...", "au fond...", "en réalité...", "inconsciemment...", "votre vraie valeur est...".
SORTIE : uniquement l'objet JSON conforme au schéma demandé. Aucun texte hors JSON.
"""

RGPD_TEXT = f"""
### Protection des données personnelles (RGPD)

Cette application Clarté360 fonctionne sans base de données serveur propre à l'application. Aucune donnée n'est enregistrée durablement sur un serveur Clarté360 par l'application.

Le fichier JSON constitue le seul support de conservation de votre travail. Il peut contenir votre identité, votre adresse e-mail, le nom de votre accompagnateur, les dates et heures de connexion, la durée des sessions, vos réponses, les mots proposés, vos validations, l'historique des connexions, les générations de codes d'accès, le consentement RGPD, la version de l'application et les informations techniques disponibles.

Le fichier JSON appartient exclusivement au bénéficiaire. Vous choisissez librement de le conserver, de le supprimer ou de le transmettre à votre accompagnateur.

Le consentement est obligatoire avant toute utilisation. Son acceptation est enregistrée dans le JSON avec la date, l'heure et la version du texte accepté : **{RGPD_TEXT_VERSION}**.

### Utilisation de l'intelligence artificielle

L'intelligence artificielle intervient uniquement pour formuler des hypothèses de mots à examiner à partir des réponses du bénéficiaire et d'un sous-ensemble contrôlé du référentiel RVC360. Elle ne valide aucune valeur, ne produit aucun diagnostic et ne prend aucune décision à la place du bénéficiaire.

Les réponses utiles à cette recherche sont transmises au fournisseur d'IA configuré par Clarté360. Il est demandé de ne pas saisir de noms complets, coordonnées ou informations sensibles inutiles. L'application demande au fournisseur de ne pas conserver la réponse comme état applicatif (`store=False`). Les traitements techniques et règles de conservation propres au fournisseur restent applicables.

### Nature des résultats

Les résultats constituent des supports d'aide à la réflexion. Ils ne constituent ni un diagnostic psychologique, ni un avis médical, ni une décision d'orientation automatique. Le bénéficiaire demeure seul décisionnaire des valeurs qu'il retient et valide.

### Propriété intellectuelle

Les applications, outils, questionnaires, méthodes, référentiels, rapports et contenus Clarté360 sont protégés. Toute reproduction, adaptation, diffusion ou réutilisation sans autorisation écrite préalable est interdite.
"""

st.set_page_config(page_title=APP_FULL_NAME, page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🧭", layout="centered")
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

def lexical_prefilter(texts:list[str],limit:int=36)->list[dict[str,str]]:
    text_norm=normalize(" ".join(texts)); terms=set(text_norm.split()); scored=[]
    for item in CATALOGUE:
        hay=normalize(" ".join([item["nom"],item["famille"],item["definition"]])); words=set(hay.split()); overlap=len(terms & words); phrase=2 if normalize(item["nom"]) in text_norm else 0; scored.append((overlap+phrase,item))
    selected=[item for score,item in sorted(scored,key=lambda x:(x[0],x[1]["nom"]),reverse=True) if score>0][:limit]
    if len(selected)<min(limit,len(CATALOGUE)):
        seen={x["nom"] for x in selected}
        for item in CATALOGUE:
            if item["nom"] not in seen: selected.append(item); seen.add(item["nom"])
            if len(selected)>=limit: break
    return selected

def response_json(instructions:str,payload:dict[str,Any],schema_name:str,schema:dict[str,Any])->dict[str,Any]:
    client=api_client(); model=get_secret("openai","model","gpt-5-mini")
    response=client.responses.create(model=model,instructions=instructions,input=json.dumps(payload,ensure_ascii=False),store=False,max_output_tokens=1200,text={"format":{"type":"json_schema","name":schema_name,"strict":True,"schema":schema}})
    if getattr(response,"status",None) not in (None,"completed"): raise RuntimeError(f"Réponse IA incomplète : {getattr(response,'status',None)}")
    st.session_state.ai_calls+=1; usage=getattr(response,"usage",None)
    if usage: st.session_state.ai_input_tokens+=int(getattr(usage,"input_tokens",0) or 0); st.session_state.ai_output_tokens+=int(getattr(usage,"output_tokens",0) or 0)
    txt=getattr(response,"output_text","")
    if not txt: raise RuntimeError("Réponse IA vide.")
    return json.loads(txt)

def has_forbidden_language(text:str)->bool:
    n=normalize(text); return any(re.search(p,n) for p in FORBIDDEN_PATTERNS)
def sanitize_engine_result(result:dict[str,Any],allowed_names:set[str])->dict[str,Any]:
    reform=str(result.get("reformulation","")).strip(); question=str(result.get("question_suivante","")).strip()
    if has_forbidden_language(reform): reform="Vous avez décrit une situation concrète. Est-ce fidèle à ce que vous souhaitez exprimer ?"
    if has_forbidden_language(question) or not question: question=FALLBACK_QUESTIONS[len(st.session_state.conversation)%len(FALLBACK_QUESTIONS)]
    hypotheses=[]
    for x in result.get("hypotheses",[]):
        name=str(x.get("nom","")).strip()
        if name in allowed_names:
            hypotheses.append({"nom":name,"raison":str(x.get("raison","")).strip(),"preuve":str(x.get("preuve","")).strip()})
    return {"reformulation":reform,"question_suivante":question,"hypotheses":hypotheses,"exploration_suffisante":bool(result.get("exploration_suffisante",False))}
def run_rvc360_engine(answer:str)->dict[str,Any]:
    texts=[t["answer"] for t in st.session_state.conversation]+[answer]; subset=lexical_prefilter(texts)
    allowed={x["nom"] for x in subset}; payload={"question_posee":st.session_state.current_question,"reponse_du_beneficiaire":answer,"historique":[{"question":x["question"],"reponse":x["answer"]} for x in st.session_state.conversation[-8:]],"valeurs_deja_validees":st.session_state.existing_values,"referentiel_autorise":subset}
    schema={"type":"object","additionalProperties":False,"properties":{"reformulation":{"type":"string"},"question_suivante":{"type":"string"},"hypotheses":{"type":"array","maxItems":6,"items":{"type":"object","additionalProperties":False,"properties":{"nom":{"type":"string","enum":sorted(allowed)},"raison":{"type":"string"},"preuve":{"type":"string"}},"required":["nom","raison","preuve"]}},"exploration_suffisante":{"type":"boolean"}},"required":["reformulation","question_suivante","hypotheses","exploration_suffisante"]}
    return sanitize_engine_result(response_json(SYSTEM_RVC360,payload,"rvc360_exploration",schema),allowed)
def merge_hypotheses(items:list[dict[str,str]])->None:
    for item in items:
        n=item["nom"]
        if n not in st.session_state.candidate_names and n not in st.session_state.existing_values: st.session_state.candidate_names.append(n)
        st.session_state.candidate_reasons[n]=item.get("raison",""); st.session_state.candidate_evidence[n]=item.get("preuve","")

def start_new_session(nom:str,prenom:str,email:str,consultant:str=""):
    st.session_state.passation_root_id=str(uuid.uuid4()); st.session_state.session_id=str(uuid.uuid4()); st.session_state.passation_id=f"CL360-RVC-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{st.session_state.session_id[:8].upper()}"; st.session_state.started_at=now_iso(); st.session_state.beneficiaire={"nom":nom.strip(),"prenom":prenom.strip(),"email":email.strip(),"consultant":consultant.strip()}; st.session_state.test_started=True; st.session_state.session_history=[]
    for k,v in default_business_state().items(): st.session_state[k]=deepcopy(v)
    init_runtime_session("premiere_connexion")

def build_payload(completed=False)->dict[str,Any]:
    names=list(dict.fromkeys(st.session_state.existing_values+st.session_state.candidate_names)); values=[]
    for name in names:
        values.append({"nom":name,"source":"seance" if name in st.session_state.existing_values else "application","famille":VALUE_MAP.get(name,{}).get("famille",""),"definition_clarte360":VALUE_MAP.get(name,{}).get("definition",""),"definition_personnelle":st.session_state.personal_defs.get(name,""),"commentaire":st.session_state.comments.get(name,""),"raison_hypothese":st.session_state.candidate_reasons.get(name,""),"preuve_textuelle":st.session_state.candidate_evidence.get(name,""),"validation":st.session_state.validation.get(name,{})})
    return {"application":APP_FULL_NAME,"version":APP_VERSION,"socle_clarte360":SOCLE_CLARTE360_VERSION,"framework_version":FRAMEWORK_VERSION,"rvc360_version":RVC360_VERSION,"rgpd_version":RGPD_TEXT_VERSION,"passation_root_id":st.session_state.get("passation_root_id"),"session_id":st.session_state.get("session_id"),"passation_id":st.session_state.get("passation_id"),"beneficiaire":st.session_state.get("beneficiaire",{}),"rgpd_acceptance":st.session_state.get("rgpd_acceptance",{}),"access_history":st.session_state.get("access_history",{}),"sessions":st.session_state.get("session_history",[]),"metier":{"page":st.session_state.page,"prerequis_premiere_valeur":st.session_state.prerequisite_confirmed,"existing_values":st.session_state.existing_values,"conversation":st.session_state.conversation,"current_question":st.session_state.current_question,"candidate_names":st.session_state.candidate_names,"candidate_reasons":st.session_state.candidate_reasons,"candidate_evidence":st.session_state.candidate_evidence,"validation":st.session_state.validation,"personal_defs":st.session_state.personal_defs,"comments":st.session_state.comments,"discarded":st.session_state.discarded,"trace":st.session_state.trace,"exploration_complete":st.session_state.exploration_complete},"ia":{"appels":st.session_state.ai_calls,"tokens_entree":st.session_state.ai_input_tokens,"tokens_sortie":st.session_state.ai_output_tokens,"statut":st.session_state.ai_engine_status,"modele":get_secret("openai","model","gpt-5-mini")},"completed":completed,"exporte_le":now_iso()}
def payload_bytes(completed=False)->bytes: return json.dumps(build_payload(completed),ensure_ascii=False,indent=2).encode("utf-8")
def make_filename(prefix="rvc360",ext="json"):
    b=st.session_state.get("beneficiaire",{}); return f"{prefix}_{sanitize_filename((b.get('prenom','')+'_'+b.get('nom','')).strip())}_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}"

def restore_from_progress(payload:dict):
    st.session_state.passation_root_id=payload.get("passation_root_id",str(uuid.uuid4())); st.session_state.session_id=str(uuid.uuid4()); st.session_state.passation_id=payload.get("passation_id") or f"CL360-RVC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"; st.session_state.beneficiaire=payload.get("beneficiaire",{}); st.session_state.rgpd_acceptance=payload.get("rgpd_acceptance",{}); st.session_state.access_history=payload.get("access_history",{}); st.session_state.session_history=deepcopy(payload.get("sessions",[])); m=payload.get("metier",{})
    for k,v in default_business_state().items(): st.session_state[k]=deepcopy(m.get(k,v))
    st.session_state.test_started=True; st.session_state.code_verified_at=now_iso(); init_runtime_session("reprise_json"); business_trace("reprise_json")

def create_pdf()->bytes:
    buffer=BytesIO(); styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name="Teal",parent=styles["Heading1"],textColor=colors.HexColor(OFFICIAL_TEAL)))
    def footer(canvas,doc): canvas.saveState(); canvas.setFont("Helvetica",8); canvas.setFillColor(colors.HexColor("#666666")); canvas.drawCentredString(A4[0]/2,.7*cm,"Clarté360 - Référentiel RVC360 - Document confidentiel"); canvas.drawRightString(A4[0]-1.5*cm,.7*cm,f"Page {doc.page}"); canvas.restoreState()
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=1.7*cm,leftMargin=1.7*cm,topMargin=1.7*cm,bottomMargin=1.5*cm); b=st.session_state.get("beneficiaire",{}); story=[Paragraph("RVC360 - Recherche de mes valeurs",styles["Teal"]),Paragraph("Rapport de recherche et de validation des valeurs fondamentales",styles["Normal"]),Spacer(1,12),Paragraph(f"Bénéficiaire : {b.get('prenom','')} {b.get('nom','')}",styles["Normal"]),Spacer(1,8)]
    names=list(dict.fromkeys(st.session_state.existing_values+st.session_state.candidate_names)); validated=[n for n in names if st.session_state.validation.get(n,{}).get("fondamentale")]; story += [Paragraph(f"Nombre de valeurs validées : {len(validated)}",styles["Heading2"]),Spacer(1,8)]
    for idx,name in enumerate(validated,1):
        info=VALUE_MAP.get(name,{}); source="Découverte avec l'accompagnateur" if name in st.session_state.existing_values else "Recherchée avec l'application"; story += [Paragraph(f"{idx}. {name}",styles["Heading2"]),Paragraph(f"Famille : {info.get('famille','')}",styles["Normal"]),Paragraph(f"Origine : {source}",styles["Normal"]),Paragraph(f"Définition Clarté360 : {info.get('definition','')}",styles["Normal"]),Paragraph(f"Définition personnelle : {st.session_state.personal_defs.get(name,'') or 'Non renseignée'}",styles["Normal"]),Paragraph("Validation : importante / très importante / fondamentale",styles["Normal"]),Paragraph(f"Commentaire : {st.session_state.comments.get(name,'') or 'Aucun'}",styles["Normal"]),Spacer(1,10)]
    story += [PageBreak(),Paragraph("Utilisation ultérieure",styles["Heading2"]),Paragraph("Les valeurs validées peuvent maintenant être utilisées dans la Boussole des valeurs professionnelles ou dans la Roue des valeurs Clarté360.",styles["Normal"]),Spacer(1,12),Paragraph("Ce document ne constitue ni un diagnostic psychologique, ni un test de personnalité, ni une décision d'orientation.",styles["Italic"])]; doc.build(story,onFirstPage=footer,onLaterPages=footer); return buffer.getvalue()

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
    with st.form("contact_clarte360_form"):
        c1,c2=st.columns(2)
        with c1: prenom=st.text_input("Prénom *",value=ben.get("prenom",""))
        with c2: nom=st.text_input("Nom *",value=ben.get("nom",""))
        email=st.text_input("Adresse e-mail *",value=ben.get("email","")); telephone=st.text_input("Téléphone (facultatif)"); objet=st.text_input("Objet *",value=f"Demande depuis {APP_FULL_NAME}"); message=st.text_area("Message *",height=160); consent=st.checkbox("J'accepte que Clarté360 utilise les informations transmises uniquement pour traiter ma demande."); submitted=st.form_submit_button("📩 Envoyer mon message",type="primary")
    if submitted:
        if not prenom.strip() or not nom.strip() or "@" not in email or not objet.strip() or not message.strip(): st.error("Merci de renseigner tous les champs obligatoires."); return
        if not consent: st.error("Le consentement est nécessaire."); return
        support_id=f"SUP-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"; body=f"Identifiant support : {support_id}\nApplication : {APP_FULL_NAME}\nVersion : {APP_VERSION}\nPrénom : {prenom}\nNom : {nom}\nEmail : {email}\nTéléphone : {telephone or 'non renseigné'}\nObjet : {objet}\n\nMessage :\n{message}\n"
        ok,msg=send_email(f"Clarté360 - Support {support_id} - {APP_NAME}",body,to_email=FINAL_EMAIL_TO); st.success(f"Votre demande a bien été transmise. Référence : {support_id}") if ok else st.error("Le message n'a pas pu être envoyé : "+msg)

def traceability_information_block():
    update_runtime_heartbeat("affichage_tracabilite"); sessions=st.session_state.get("session_history",[]); rgpd=st.session_state.get("rgpd_acceptance",{})
    st.markdown("### Traçabilité de la session"); c1,c2,c3=st.columns(3); c1.metric("Session en cours",(st.session_state.get("current_runtime_session_id") or "Non ouverte")[:8]); c2.metric("Nombre de sessions",len(sessions)); c3.metric("Temps cumulé",format_duration(total_session_seconds()))
    if rgpd.get("consentement"): st.success(f"Consentement RGPD enregistré le {rgpd.get('date','')} à {rgpd.get('heure','')} - version {rgpd.get('version_texte','')}")
    else: st.warning("Aucun consentement RGPD n'est encore enregistré.")
    if sessions:
        st.dataframe(pd.DataFrame([{"Début":s.get("debut",""),"Dernière activité":s.get("derniere_activite",""),"Fin":s.get("fin",""),"Durée":format_duration(s.get("duree_active_secondes",0)),"Motif ouverture":s.get("motif_ouverture",""),"Motif fermeture":s.get("motif_fermeture","")} for s in sessions]),use_container_width=True,hide_index=True)

def rgpd_page():
    display_header()
    if st.session_state.get("test_started") and st.button("← Retour à l'application",key="rgpd_back"): st.session_state.show_rgpd_page=False; st.rerun()
    st.subheader("Informations légales et protection des données"); t1,t2,t3=st.tabs(["Protection des données et traçabilité","Mentions légales","Nous contacter"])
    with t1: st.markdown(RGPD_TEXT); st.info("Le consentement RGPD est demandé avant la génération du code d'accès."); traceability_information_block()
    with t2:
        l=CLARTE360_LEGAL; st.markdown(f"### {l['raison_sociale']} {l['forme']}\n**Adresse :** {l['adresse']} - {l['code_postal_ville']}  \n**Téléphone :** {l['telephone']}  \n**E-mail :** {l['email']}  \n**Site :** {l['web']}  \n\n**RCS :** {l['rcs']}  \n**SIRET :** {l['siret']}  \n**Code NAF :** {l['naf']}  \n**TVA :** {l['tva']}")
    with t3: contact_form()
def contact_page():
    display_header()
    if st.session_state.get("test_started") and st.button("← Retour à l'application",key="contact_back"): st.session_state.show_contact_page=False; st.rerun()
    st.subheader("Contacter Clarté360"); contact_form()
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

def sidebar_progress():
    in_app=st.session_state.get("test_started",False)
    if LOGO_PATH.exists(): st.sidebar.image(str(LOGO_PATH),width=85)
    st.sidebar.markdown("### Clarté360")
    if in_app:
        steps=["Accueil","Prerequis","Exploration IA","Mots a examiner","Validation","Resultats"]; current=st.session_state.page; idx=steps.index(current) if current in steps else 0; st.sidebar.progress(idx/(len(steps)-1)); st.sidebar.caption(f"Étape {idx+1} sur {len(steps)} - {current}")
        st.sidebar.markdown("---"); st.sidebar.download_button("💾 Sauvegarder mon travail (JSON)",data=payload_bytes(False),file_name=make_filename("rvc360_sauvegarde","json"),mime="application/json",use_container_width=True,on_click=lambda:record_save_event("sauvegarde_manuelle"))
        if st.sidebar.button("🚪 Quitter et préparer mon JSON",use_container_width=True): record_save_event("sortie_preparee"); close_runtime_session("sortie_preparee"); st.session_state.exit_json_ready=True; st.session_state.exit_mode="quit"; st.rerun()
        st.sidebar.caption(f"Temps cumulé : {format_duration(total_session_seconds())}")
    else: st.sidebar.markdown("### Session")
    st.sidebar.markdown("---")
    if st.sidebar.button("💬 Contacter Clarté360",use_container_width=True): st.session_state.show_contact_page=True; st.session_state.show_rgpd_page=False; st.rerun()
    if st.sidebar.button("RGPD et mentions légales",use_container_width=True): st.session_state.show_rgpd_page=True; st.session_state.show_contact_page=False; st.rerun()
    st.sidebar.caption(f"App v{APP_VERSION} · Socle {SOCLE_CLARTE360_VERSION} · RVC360 {RVC360_VERSION}")
    if not in_app and st.sidebar.button("Réinitialiser la session"): st.session_state.clear(); st.rerun()

def render_business():
    page=st.session_state.page; display_header()
    if page=="Accueil":
        st.markdown('<div class="clarte-box"><b>Objectif unique : rechercher et valider vos valeurs fondamentales.</b><br>Cette application ne fait ni coaching, ni diagnostic, ni orientation.</div>',unsafe_allow_html=True); st.write("Le parcours commence obligatoirement après l'identification d'au moins une première valeur avec votre accompagnateur. L'application vous aide ensuite à rechercher les autres valeurs, puis à les valider une par une.")
        if not CATALOGUE: st.error("Le référentiel RVC360 n'a pas pu être chargé.")
        if ai_ready(): st.success("Moteur IA RVC360 configuré et disponible.")
        else: st.error("Le moteur IA RVC360 n'est pas configuré.")
        if st.button("Commencer",type="primary",disabled=not(CATALOGUE and ai_ready())): st.session_state.page="Prerequis"; business_trace("debut_metier"); st.rerun()
    elif page=="Prerequis":
        st.title("1. Prérequis obligatoire"); st.warning("La première valeur doit avoir été recherchée et validée avec votre accompagnateur avant d'utiliser cette application."); confirmed=st.radio("Avez-vous déjà identifié et validé au moins une valeur avec votre accompagnateur ?",["Choisissez une réponse","Oui","Non"],index=0)
        if confirmed=="Non": st.error("Le parcours ne peut pas commencer. Reprenez d'abord cette première étape avec votre accompagnateur."); business_trace("prerequis_refuse"); return
        if confirmed=="Oui":
            st.session_state.prerequisite_confirmed=True; count=st.number_input("Combien de valeurs avez-vous déjà identifiées ?",min_value=1,max_value=20,value=max(1,len(st.session_state.existing_values))); selected=[]
            for idx in range(int(count)):
                default=st.session_state.existing_values[idx] if idx<len(st.session_state.existing_values) else None; options=[""]+VALUE_NAMES; selected.append(st.selectbox(f"Valeur déjà identifiée n°{idx+1}",options,index=options.index(default) if default in options else 0,key=f"existing_{idx}"))
            selected=[n for n in selected if n]
            if st.button("Valider mes valeurs déjà identifiées",type="primary",disabled=not selected):
                st.session_state.existing_values=list(dict.fromkeys(selected))
                for n in st.session_state.existing_values: st.session_state.validation[n]={"importante":True,"tres_importante":True,"fondamentale":True}
                business_trace("prerequis_valide",", ".join(st.session_state.existing_values)); st.session_state.page="Exploration IA"; st.rerun()
    elif page=="Exploration IA":
        st.title("2. Recherche guidée des autres valeurs"); st.caption("Une seule question à la fois. L'IA travaille sur vos mots, sans vous expliquer ni décider à votre place."); st.progress(min(.9,len(st.session_state.conversation)/8),text=f"{len(st.session_state.conversation)} réponse(s) explorée(s)")
        for turn in st.session_state.conversation:
            with st.chat_message("assistant"):
                if turn.get("reformulation"): st.write(turn["reformulation"])
                st.write(turn["question"])
            with st.chat_message("user"): st.write(turn["answer"])
        with st.chat_message("assistant"): st.write(st.session_state.current_question)
        answer=st.chat_input("Écrivez votre réponse ici")
        if answer:
            if len(answer.strip())<10: st.warning("Votre réponse est très brève. Ajoutez si possible un exemple ou un fait concret.")
            else:
                with st.spinner("Le moteur RVC360 examine uniquement vos mots et le référentiel autorisé..."):
                    try: result=run_rvc360_engine(answer.strip()); st.session_state.ai_engine_status="operationnel"
                    except Exception as exc: business_trace("erreur_ia",f"{type(exc).__name__}: {str(exc)[:120]}"); st.error("Le moteur IA n'a pas pu répondre. Votre réponse n'a pas été perdue. Réessayez dans quelques instants."); return
                st.session_state.conversation.append({"question":st.session_state.current_question,"answer":answer.strip(),"reformulation":result["reformulation"],"date":now_iso()}); merge_hypotheses(result["hypotheses"]); st.session_state.current_question=result["question_suivante"]; st.session_state.exploration_complete=result["exploration_suffisante"]; business_trace("tour_ia",f"hypotheses={len(result['hypotheses'])}"); st.rerun()
        if st.session_state.candidate_names: st.info(f"{len(st.session_state.candidate_names)} hypothèse(s) de mots sont maintenant disponibles à l'examen.")
        if st.button("Examiner les mots proposés",type="primary",disabled=len(st.session_state.candidate_names)<3,use_container_width=True): st.session_state.page="Mots a examiner"; st.rerun()
    elif page=="Mots a examiner":
        st.title("3. Hypothèses de mots à examiner"); st.markdown('<div class="clarte-box">Une proposition n\'est jamais une valeur validée. Vous pouvez la conserver, l\'écarter ou ajouter un autre mot du référentiel.</div>',unsafe_allow_html=True); proposed=[n for n in st.session_state.candidate_names if n not in st.session_state.discarded]; chosen=st.multiselect("Sélectionnez les mots que vous souhaitez examiner",VALUE_NAMES,default=proposed)
        for name in chosen:
            info=VALUE_MAP[name]
            with st.expander(f"{name} - {info['famille']}"):
                st.write(info["definition"])
                if st.session_state.candidate_reasons.get(name): st.caption(f"Rapprochement proposé : {st.session_state.candidate_reasons[name]}")
                if st.session_state.candidate_evidence.get(name): st.caption(f"Élément de votre réponse : {st.session_state.candidate_evidence[name]}")
        if st.button("Examiner ces valeurs",type="primary",disabled=not chosen): st.session_state.discarded=list(dict.fromkeys(st.session_state.discarded+[n for n in proposed if n not in chosen])); st.session_state.candidate_names=list(dict.fromkeys(chosen)); business_trace("hypotheses_selectionnees",str(len(chosen))); st.session_state.page="Validation"; st.rerun()
    elif page=="Validation":
        st.title("4. Clarification et validation"); st.write("Chaque nouvelle valeur doit passer successivement par les trois niveaux : importante, très importante, puis fondamentale."); names=list(dict.fromkeys(st.session_state.existing_values+st.session_state.candidate_names))
        for name in names:
            info=VALUE_MAP.get(name,{}); source="Déjà identifiée avec l'accompagnateur" if name in st.session_state.existing_values else "Recherchée avec l'application"; st.markdown(f"### {name}"); st.caption(f"{source} - Famille : {info.get('famille','')}"); st.write(info.get("definition","")); st.session_state.personal_defs[name]=st.text_area("Que signifie cette valeur pour vous ?",value=st.session_state.personal_defs.get(name,""),key=f"definition_{name}"); current=st.session_state.validation.get(name,{}); important=st.checkbox("Cette valeur est importante pour moi",value=bool(current.get("importante",name in st.session_state.existing_values)),key=f"important_{name}"); very=st.checkbox("Cette valeur est très importante pour moi",value=bool(current.get("tres_importante",name in st.session_state.existing_values)),disabled=not important,key=f"very_{name}"); fundamental=st.checkbox("Cette valeur est fondamentale pour moi",value=bool(current.get("fondamentale",name in st.session_state.existing_values)),disabled=not very,key=f"fundamental_{name}"); st.session_state.comments[name]=st.text_input("Commentaire facultatif",value=st.session_state.comments.get(name,""),key=f"comment_{name}"); st.session_state.validation[name]={"importante":important,"tres_importante":very,"fondamentale":fundamental}; st.divider()
        if st.button("Enregistrer ma validation",type="primary"): business_trace("validation_finale",str(sum(1 for n in names if st.session_state.validation.get(n,{}).get("fondamentale")))); st.session_state.page="Resultats"; st.rerun()
    elif page=="Resultats":
        if not st.session_state.get("result_session_closed"): close_runtime_session("parcours_termine"); st.session_state.result_session_closed=True
        st.title("5. Mes valeurs validées"); names=list(dict.fromkeys(st.session_state.existing_values+st.session_state.candidate_names)); validated=[n for n in names if st.session_state.validation.get(n,{}).get("fondamentale")]; st.metric("Nombre de valeurs fondamentales validées",len(validated))
        if not validated: st.warning("Aucune valeur n'est encore validée comme fondamentale. Revenez à l'étape Validation.")
        for idx,name in enumerate(validated,1):
            info=VALUE_MAP.get(name,{}); source="Séance avec l'accompagnateur" if name in st.session_state.existing_values else "Application"; st.markdown(f"### {idx}. {name}"); st.caption(f"{info.get('famille','')} - Origine : {source}"); st.write(info.get("definition",""));
            if st.session_state.personal_defs.get(name): st.write(f"**Votre définition :** {st.session_state.personal_defs[name]}")
        st.markdown('<div class="clarte-box">Ces valeurs peuvent maintenant être utilisées dans la Boussole des valeurs professionnelles ou dans la Roue des valeurs Clarté360.</div>',unsafe_allow_html=True); c1,c2=st.columns(2)
        with c1: st.download_button("Télécharger le rapport PDF",create_pdf(),file_name=make_filename("RVC360_valeurs","pdf"),mime="application/pdf",use_container_width=True)
        with c2: st.download_button("Télécharger les données JSON",payload_bytes(True),file_name=make_filename("RVC360_valeurs","json"),mime="application/json",use_container_width=True,on_click=lambda:record_save_event("telechargement_json_final"))

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
