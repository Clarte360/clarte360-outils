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

APP_VERSION = "1.2.1-preproduction"
SOCLE_CLARTE360_VERSION = "1.8"
APP_NAME = "Recherche de mes valeurs"
APP_FULL_NAME = "Clarté360 - Recherche de mes valeurs"
FRAMEWORK_VERSION = "4.0"
RVC360_VERSION = "1.3.1"
RGPD_TEXT_VERSION = "RGPD-Clarte360-RVC360-v1.2-2026-07"
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
    "Racontez une situation, récente ou ancienne, qui vous a procuré une forte satisfaction ou, au contraire, qui vous a vivement contrarié. Que s’est-il passé et qu’est-ce qui était particulièrement important pour vous dans cette situation ?",
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

def lexical_prefilter(texts:list[str],limit:int=18)->list[dict[str,str]]:
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
    response=client.responses.create(model=model,instructions=instructions,input=json.dumps(payload,ensure_ascii=False),store=False,max_output_tokens=600,text={"format":{"type":"json_schema","name":schema_name,"strict":True,"schema":schema}})
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
    allowed={x["nom"] for x in subset}; payload={"question_posee":st.session_state.current_question,"reponse_du_beneficiaire":answer,"memoire_synthetique":st.session_state.get("exploration_summary", ""),"historique_recent":[{"question":x["question"],"reponse":x["answer"]} for x in st.session_state.conversation[-3:]],"valeurs_deja_validees":st.session_state.existing_values,"referentiel_autorise":subset}
    schema={"type":"object","additionalProperties":False,"properties":{"reformulation":{"type":"string"},"question_suivante":{"type":"string"},"hypotheses":{"type":"array","maxItems":6,"items":{"type":"object","additionalProperties":False,"properties":{"nom":{"type":"string","enum":sorted(allowed)},"raison":{"type":"string"},"preuve":{"type":"string"}},"required":["nom","raison","preuve"]}},"exploration_suffisante":{"type":"boolean"}},"required":["reformulation","question_suivante","hypotheses","exploration_suffisante"]}
    return sanitize_engine_result(response_json(SYSTEM_RVC360,payload,"rvc360_exploration",schema),allowed)
def merge_hypotheses(items:list[dict[str,str]])->None:
    for item in items:
        n=item["nom"]
        if n not in st.session_state.candidate_names and n not in st.session_state.existing_values: st.session_state.candidate_names.append(n)
        st.session_state.candidate_reasons[n]=item.get("raison",""); st.session_state.candidate_evidence[n]=item.get("preuve","")


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
    client=api_client()
    model=get_secret("openai","transcription_model","gpt-4o-mini-transcribe")
    data=audio_file.getvalue()
    import io
    f=io.BytesIO(data); f.name="reponse.wav"
    result=client.audio.transcriptions.create(model=model,file=f,language="fr")
    return str(getattr(result,"text","") or "").strip()

def speak_button(text:str,key:str)->None:
    safe=json.dumps(text,ensure_ascii=False)
    components.html(f"""
    <button id="speak_{key}" style="border:1px solid #008080;border-radius:8px;padding:8px 12px;background:white;cursor:pointer">🔊 Écouter la question</button>
    <script>
    const btn=document.getElementById("speak_{key}");
    btn.onclick=()=>{{
      window.speechSynthesis.cancel();
      const u=new SpeechSynthesisUtterance({safe});
      u.lang='fr-FR'; u.rate=0.92; u.pitch=1.0;
      const speakNow=()=>{{
        const voices=window.speechSynthesis.getVoices();
        const preferred=voices.find(v=>v.lang==='fr-FR' && /Microsoft|Google|Natural|Neural/i.test(v.name)) || voices.find(v=>v.lang.startsWith('fr'));
        if(preferred) u.voice=preferred;
        window.speechSynthesis.speak(u);
      }};
      if(window.speechSynthesis.getVoices().length) speakNow();
      else {{ window.speechSynthesis.onvoiceschanged=speakNow; setTimeout(speakNow,500); }}
    }};
    </script>""",height=48)

def value_reminder()->None:
    st.info("Une valeur est un principe profondément important qui oriente vos choix et votre manière de vivre. Ce n'est ni une simple préférence, ni une qualité, ni un objectif. Le mot retenu doit avoir pour vous un sens personnel précis.")

def validated_names()->list[str]:
    names=list(dict.fromkeys(st.session_state.existing_values+st.session_state.candidate_names))
    return [n for n in names if st.session_state.validation.get(n,{}).get("fondamentale")]

def start_new_session(nom:str,prenom:str,email:str,consultant:str=""):
    st.session_state.passation_root_id=str(uuid.uuid4()); st.session_state.session_id=str(uuid.uuid4()); st.session_state.passation_id=f"CL360-RVC-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{st.session_state.session_id[:8].upper()}"; st.session_state.started_at=now_iso(); st.session_state.beneficiaire={"nom":nom.strip(),"prenom":prenom.strip(),"email":email.strip(),"consultant":consultant.strip()}; st.session_state.test_started=True; st.session_state.session_history=[]
    for k,v in default_business_state().items(): st.session_state[k]=deepcopy(v)
    init_runtime_session("premiere_connexion")

def build_payload(completed=False)->dict[str,Any]:
    names=list(dict.fromkeys(st.session_state.existing_values+st.session_state.candidate_names)); values=[]
    for name in names:
        values.append({"nom":name,"source":"seance" if name in st.session_state.existing_values else "application","famille":value_info(name).get("famille",""),"definition_clarte360":value_info(name).get("definition",""),"definition_personnelle":st.session_state.personal_defs.get(name,""),"commentaire":st.session_state.comments.get(name,""),"raison_hypothese":st.session_state.candidate_reasons.get(name,""),"preuve_textuelle":st.session_state.candidate_evidence.get(name,""),"validation":st.session_state.validation.get(name,{})})
    return {"application":APP_FULL_NAME,"version":APP_VERSION,"socle_clarte360":SOCLE_CLARTE360_VERSION,"framework_version":FRAMEWORK_VERSION,"rvc360_version":RVC360_VERSION,"rgpd_version":RGPD_TEXT_VERSION,"passation_root_id":st.session_state.get("passation_root_id"),"session_id":st.session_state.get("session_id"),"passation_id":st.session_state.get("passation_id"),"beneficiaire":st.session_state.get("beneficiaire",{}),"rgpd_acceptance":st.session_state.get("rgpd_acceptance",{}),"access_history":st.session_state.get("access_history",{}),"sessions":st.session_state.get("session_history",[]),"metier":{"page":st.session_state.page,"prerequis_premiere_valeur":st.session_state.prerequisite_confirmed,"existing_values":st.session_state.existing_values,"conversation":st.session_state.conversation,"current_question":st.session_state.current_question,"candidate_names":st.session_state.candidate_names,"candidate_reasons":st.session_state.candidate_reasons,"candidate_evidence":st.session_state.candidate_evidence,"validation":st.session_state.validation,"personal_defs":st.session_state.personal_defs,"comments":st.session_state.comments,"discarded":st.session_state.discarded,"trace":st.session_state.trace,"exploration_complete":st.session_state.exploration_complete,"prerequisite_entries":st.session_state.prerequisite_entries,"hypothesis_decisions":st.session_state.hypothesis_decisions,"custom_values":st.session_state.custom_values,"exploration_summary":st.session_state.exploration_summary},"ia":{"appels":st.session_state.ai_calls,"tokens_entree":st.session_state.ai_input_tokens,"tokens_sortie":st.session_state.ai_output_tokens,"statut":st.session_state.ai_engine_status,"modele":get_secret("openai","model","gpt-5-mini")},"completed":completed,"exporte_le":now_iso()}
def payload_bytes(completed=False)->bytes: return json.dumps(build_payload(completed),ensure_ascii=False,indent=2).encode("utf-8")
def make_filename(prefix="rvc360",ext="json"):
    b=st.session_state.get("beneficiaire",{}); return f"{prefix}_{sanitize_filename((b.get('prenom','')+'_'+b.get('nom','')).strip())}_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}"

def restore_from_progress(payload:dict):
    st.session_state.passation_root_id=payload.get("passation_root_id",str(uuid.uuid4())); st.session_state.session_id=str(uuid.uuid4()); st.session_state.passation_id=payload.get("passation_id") or f"CL360-RVC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"; st.session_state.beneficiaire=payload.get("beneficiaire",{}); st.session_state.rgpd_acceptance=payload.get("rgpd_acceptance",{}); st.session_state.access_history=payload.get("access_history",{}); st.session_state.session_history=deepcopy(payload.get("sessions",[])); m=payload.get("metier",{})
    for k,v in default_business_state().items(): st.session_state[k]=deepcopy(m.get(k,v))
    st.session_state.test_started=True; st.session_state.code_verified_at=now_iso(); init_runtime_session("reprise_json"); business_trace("reprise_json")

def create_pdf()->bytes:
    buffer=BytesIO(); styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Teal",parent=styles["Heading1"],textColor=colors.HexColor(OFFICIAL_TEAL),spaceAfter=10))
    styles.add(ParagraphStyle(name="Small",parent=styles["Normal"],fontSize=8,leading=10,textColor=colors.HexColor("#666666")))
    def footer(canvas,doc):
        canvas.saveState(); canvas.setFont("Helvetica",8); canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(1.5*cm,.7*cm,"Clarté360 - RVC360 - Document confidentiel")
        canvas.drawCentredString(A4[0]/2,.7*cm,st.session_state.get("passation_id","") or "")
        canvas.drawRightString(A4[0]-1.5*cm,.7*cm,f"Page {doc.page}"); canvas.restoreState()
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=1.7*cm,leftMargin=1.7*cm,topMargin=1.5*cm,bottomMargin=1.5*cm)
    b=st.session_state.get("beneficiaire",{}); sessions=st.session_state.get("session_history",[])
    validated=validated_names(); app_values=[n for n in validated if n not in st.session_state.existing_values]
    story=[Paragraph("RVC360 - Recherche de mes valeurs",styles["Teal"]),Paragraph("Rapport de recherche, clarification et validation des valeurs fondamentales",styles["Normal"]),Spacer(1,10)]
    story += [Paragraph(f"<b>Bénéficiaire :</b> {b.get('prenom','')} {b.get('nom','')}",styles["Normal"]),Paragraph(f"<b>Accompagnateur :</b> {b.get('consultant','') or 'Non renseigné'}",styles["Normal"]),Paragraph(f"<b>Référence :</b> {st.session_state.get('passation_id','')}",styles["Normal"]),Paragraph(f"<b>Rapport généré le :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}",styles["Normal"]),Paragraph(f"<b>Temps actif cumulé :</b> {format_duration(total_session_seconds())}",styles["Normal"]),Spacer(1,12)]
    story += [Paragraph("Synthèse du parcours",styles["Heading2"]),Paragraph(f"Valeurs fondamentales validées : {len(validated)}",styles["Normal"]),Paragraph(f"Déjà identifiées avec l'accompagnateur : {len([n for n in validated if n in st.session_state.existing_values])}",styles["Normal"]),Paragraph(f"Complémentaires recherchées avec l'application : {len(app_values)}",styles["Normal"]),Spacer(1,10)]
    for idx,name in enumerate(validated,1):
        info=value_info(name); source="Découverte et validée avec l'accompagnateur" if name in st.session_state.existing_values else "Recherchée avec l'application"
        v=st.session_state.validation.get(name,{})
        story += [Paragraph(f"{idx}. {name}",styles["Heading2"]),Paragraph(f"<b>Famille :</b> {info.get('famille','')}",styles["Normal"]),Paragraph(f"<b>Origine :</b> {source}",styles["Normal"]),Paragraph(f"<b>Définition Clarté360 / retenue :</b> {info.get('definition','') or 'Valeur personnelle'}",styles["Normal"]),Paragraph(f"<b>Définition personnelle validée :</b> {st.session_state.personal_defs.get(name,'') or 'La définition proposée a été acceptée.'}",styles["Normal"]),Paragraph(f"<b>Questionnaire spécifique HEC :</b> importante : {'Oui' if v.get('importante') else 'Non'} ; très importante : {'Oui' if v.get('tres_importante') else 'Non'} ; fondamentale : {'Oui' if v.get('fondamentale') else 'Non'}",styles["Normal"]),Paragraph(f"<b>Commentaire :</b> {st.session_state.comments.get(name,'') or 'Aucun'}",styles["Normal"]),Spacer(1,10)]
    story += [PageBreak(),Paragraph("Retour en séance avec l'accompagnateur",styles["Heading2"]),Paragraph("Ce rapport restitue l'état du travail inter-séance. Les valeurs et définitions personnelles peuvent être repris avec l'accompagnateur.",styles["Normal"]),Spacer(1,10),Paragraph("Une valeur n'est validée comme fondamentale qu'après le questionnaire spécifique successif : importante, très importante, fondamentale.",styles["Normal"]),Spacer(1,12),Paragraph("Ce document ne constitue ni un diagnostic psychologique, ni un test de personnalité, ni une décision d'orientation. L'application ne remplace pas l'accompagnateur.",styles["Italic"]),Spacer(1,12),Paragraph(f"Application {APP_VERSION} - Socle Clarté360 {SOCLE_CLARTE360_VERSION} - RVC360 {RVC360_VERSION}",styles["Small"])]
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
        "Exploration IA":"Étape 3 sur 6 - Exploration IA",
        "Mots a examiner":"Étape 4 sur 6 - Hypothèse en cours",
        "Validation":"Étape 5 sur 6 - Validation",
        "Resultats":"Étape 6 sur 6 - État actuel",
    }
    return labels.get(page, str(page))

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
    st.session_state.candidate_names=[]
    st.session_state.candidate_reasons={}
    st.session_state.candidate_evidence={}
    st.session_state.hypothesis_decisions={}
    st.session_state.validation_index=0
    st.session_state.validation_stage={}
    st.session_state.hypothesis_index=0
    st.session_state.hypothesis_queue=[]
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
            business_trace("prerequis_valide",", ".join(st.session_state.existing_values)); st.session_state.page="Exploration IA"; st.rerun()

    elif page=="Exploration IA":
        st.title("2. Recherche guidée des autres valeurs"); value_reminder()
        st.caption("Une seule question à la fois. Vous pouvez écrire ou enregistrer votre réponse. L'IA travaille uniquement sur vos mots et ne décide jamais à votre place.")
        for turn in st.session_state.conversation[-6:]:
            with st.chat_message("assistant"):
                if turn.get("reformulation"): st.write(turn["reformulation"])
                st.write(turn["question"])
            with st.chat_message("user"): st.write(turn["answer"])
        with st.chat_message("assistant"): st.write(st.session_state.current_question)
        speak_button(st.session_state.current_question,"q")
        st.markdown("**Deux façons de répondre :** écrivez dans la zone ci-dessous, ou utilisez l'enregistreur. Pour la voix : cliquez sur le micro, parlez, arrêtez l'enregistrement, puis cliquez sur **Transcrire mon enregistrement**. Relisez enfin le texte obtenu avant de le valider.")
        st.caption("Confidentialité : le fichier audio sert uniquement à la transcription. Il n'est ni ajouté au JSON, ni sauvegardé dans l'application. Seul le texte que vous validez est conservé.")
        typed=st.text_area("Votre réponse écrite",height=130,key="explore_text",placeholder="Écrivez librement, sans limite de longueur.")
        audio=None
        audio_key=f"explore_audio_{st.session_state.get('audio_widget_version',0)}"
        if hasattr(st,"audio_input"): audio=st.audio_input("Ou enregistrez votre réponse",key=audio_key)
        if audio and st.button("Transcrire mon enregistrement",key=f"transcribe_{st.session_state.get('audio_widget_version',0)}"):
            with st.spinner("Transcription en cours..."):
                try:
                    transcript=transcribe_audio(audio)
                    st.session_state.voice_transcripts.append({"date":now_iso(),"texte":transcript})
                    st.session_state["voice_draft"]=transcript
                    st.session_state["audio_widget_version"]+=1
                    st.session_state.pop("voice_edit",None)
                    st.rerun()
                except Exception as exc: st.error(f"La transcription n'a pas pu être réalisée : {exc}")
        if st.session_state.get("voice_draft"):
            st.info("Transcription proposée. Relisez-la, corrigez-la si nécessaire, puis validez-la.")
            typed=st.text_area("Texte transcrit à valider",value=st.session_state.voice_draft,height=160,key="voice_edit")
        if st.button("Valider ma réponse et afficher la question suivante",type="primary",disabled=not str(typed).strip()):
            answer=str(typed).strip()
            previous_question=st.session_state.current_question
            with st.spinner("Le moteur RVC360 examine vos mots..."):
                try: result=run_rvc360_engine(answer); st.session_state.ai_engine_status="operationnel"
                except Exception as exc: business_trace("erreur_ia",f"{type(exc).__name__}: {str(exc)[:120]}"); st.error("Le moteur IA n'a pas pu répondre. Votre réponse n'a pas été perdue."); return
            st.session_state.conversation.append({"question":previous_question,"answer":answer,"reformulation":result["reformulation"],"date":now_iso()})
            st.session_state.exploration_summary=(st.session_state.exploration_summary+" | "+answer[:240]).strip(" |")[-1200:]
            merge_hypotheses(result["hypotheses"])
            next_question=result["question_suivante"].strip()
            if normalize(next_question)==normalize(previous_question):
                next_question=FALLBACK_QUESTIONS[(len(st.session_state.conversation))%len(FALLBACK_QUESTIONS)]
            st.session_state.current_question=next_question
            st.session_state.exploration_complete=result["exploration_suffisante"]
            st.session_state.voice_draft=""
            st.session_state["audio_widget_version"]+=1
            st.session_state.pop("voice_edit",None)
            st.session_state.pop("explore_text",None)
            st.session_state["last_turn_completed"]=True
            business_trace("tour_ia",f"hypotheses={len(result['hypotheses'])}")
            st.rerun()
        if st.session_state.pop("last_turn_completed",False):
            st.success("Votre réponse a bien été prise en compte. La nouvelle question est affichée ci-dessus.")
        if st.session_state.candidate_names:
            st.info(f"{len(st.session_state.candidate_names)} hypothèse(s) sont disponibles. Elles doivent d'abord être triées et clarifiées.")
            if st.button("Trier et clarifier les hypothèses",type="primary",use_container_width=True): st.session_state.page="Mots a examiner"; st.rerun()
        if st.button("Continuer l'exploration avant d'examiner les hypothèses",use_container_width=True):
            st.session_state.current_question=next_exploration_question()
            st.session_state.voice_draft=""; st.session_state["audio_widget_version"]+=1
            st.session_state.pop("voice_edit",None); st.session_state.pop("explore_text",None); st.rerun()

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
                    st.session_state.hypothesis_index=idx+1
                    if idx+1>=len(queue): reset_for_new_exploration()
                    st.rerun()
            with c2:
                if st.button("Passer au questionnaire spécifique pour cette valeur",type="primary",disabled=not st.session_state.personal_defs[name].strip(),use_container_width=True):
                    st.session_state.candidate_names=[name]
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
                if field=="fondamentale" and answer=="Oui" and name in st.session_state.custom_values and not st.session_state.custom_values[name].get("notified"):
                    notify_new_value(name,st.session_state.personal_defs.get(name) or value_info(name).get("definition",""))
                    st.session_state.custom_values[name]["notified"]=True
                if answer=="Oui": st.session_state.validation_stage[name]=stage+1
                else:
                    st.session_state.validation_stage[name]=3; current["fondamentale"]=False
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
                    st.session_state.page="Resultats"
                st.rerun()

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
            if st.button("↩️ Revoir mes hypothèses",use_container_width=True): st.session_state.page="Mots a examiner"; st.rerun()
        st.divider(); st.subheader("Documents")
        c1,c2=st.columns(2)
        with c1: st.download_button("Télécharger le rapport PDF",create_pdf(),file_name=make_filename("RVC360_valeurs","pdf"),mime="application/pdf",use_container_width=True)
        with c2: st.download_button("Télécharger les données JSON",payload_bytes(False),file_name=make_filename("RVC360_valeurs","json"),mime="application/json",use_container_width=True,on_click=lambda:record_save_event("telechargement_json"))
        st.divider()
        finish=st.radio("Pensez-vous avoir identifié l’ensemble des valeurs qui vous font agir et réagir ?",["Je souhaite encore poursuivre ma recherche","Oui, je pense avoir suffisamment identifié mes valeurs"],key="finish_consent")
        if finish.startswith("Oui"):
            st.warning("La fin de la recherche dépend uniquement de votre décision. Vous pourrez toujours reprendre ultérieurement avec votre fichier JSON.")
            if st.button("Confirmer la fin de mon exercice inter-séance",type="primary",use_container_width=True):
                st.session_state.exploration_complete=True; close_runtime_session("parcours_termine_volontaire"); business_trace("fin_volontaire_consentie"); st.success("Votre exercice est marqué comme terminé. Téléchargez votre PDF et votre JSON avant de quitter.")

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
