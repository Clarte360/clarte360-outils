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

APP_VERSION = "2.1.3.8E-preproduction"
SOCLE_CLARTE360_VERSION = "1.8"
APP_NAME = "Recherche de mes valeurs"
APP_FULL_NAME = "Clarté360 - Recherche de mes valeurs"
FRAMEWORK_VERSION = "4.0"
RVC360_VERSION = "2.1"
RGPD_TEXT_VERSION = "RGPD-Clarte360-RVC360-v2.1.2-2026-07"
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

Cette application Clarté360 fonctionne sans base de données serveur propre à l’application. Elle n’enregistre pas durablement, sur un serveur Clarté360, les réponses, fichiers JSON, rapports PDF ou fichiers audio du bénéficiaire.

Le bénéficiaire reste responsable des fichiers qu’il choisit de télécharger, de conserver, de supprimer ou de transmettre. Le consentement à l’utilisation de l’application est obligatoire. Son acceptation est inscrite dans le JSON avec la date, l’heure et la version du texte accepté : **{RGPD_TEXT_VERSION}**.

### Données traitées et finalité

L’application peut traiter les informations nécessaires à la recherche et à la validation des valeurs : identité et coordonnées saisies, nom de l’accompagnateur, réponses validées, valeurs proposées ou retenues, étapes du parcours, validations, dates et durées de session, éléments de traçabilité, version de l’application et informations techniques strictement nécessaires à la reprise ou à la restitution.

Ces données sont utilisées uniquement pour permettre au bénéficiaire de réaliser son parcours, de reprendre son travail, de consulter ses résultats, de produire ses documents et, lorsqu’il le choisit, de transmettre ses résultats à son accompagnateur.

### Réponse vocale et transcription

La réponse vocale est facultative. Le bénéficiaire peut toujours répondre par écrit.

Lorsqu’il choisit de répondre à l’oral, l’enregistrement est transmis au prestataire technique OpenAI, via son API de transcription afin de produire une version textuelle. Le fichier audio est utilisé uniquement le temps nécessaire à cette opération par l’application : il n’est pas intégré au JSON, n’est pas conservé dans les documents produits et n’est pas enregistré durablement par l’application Clarté360.

L’application affiche la transcription initiale et une proposition rédigée par Clarté360. Cette proposition transforme l’expression orale en un texte écrit naturel, fluide et fidèle, en supprimant les hésitations, faux départs et répétitions inutiles, sans ajouter de fait ni modifier le sens. Le bénéficiaire peut conserver la transcription initiale, choisir la proposition Clarté360, la modifier ou réenregistrer sa réponse.

Aucune transcription ne devient une réponse officielle et aucune analyse de valeurs n’est lancée à partir de cette réponse tant que le bénéficiaire n’a pas explicitement validé la version textuelle qu’il souhaite conserver. Seule cette version validée est enregistrée dans le parcours.

### Utilisation de l’intelligence artificielle

Certaines données textuelles validées peuvent être transmises au prestataire technique OpenAI, via l’API OpenAI et non le service grand public ChatGPT, uniquement lorsqu’elles sont utiles à la fonction demandée, afin de :

- proposer une reformulation fidèle ;
- structurer ou exploiter une réponse dans la recherche guidée ;
- proposer une question suivante ;
- faire émerger des hypothèses de valeurs à examiner.

Seules les informations utiles à l’étape en cours doivent être transmises. Il est demandé au bénéficiaire de ne pas saisir de noms complets, coordonnées ou informations sensibles qui ne seraient pas nécessaires à la recherche de ses valeurs.

L’intelligence artificielle ne valide aucune valeur, ne prend aucune décision à la place du bénéficiaire, ne réalise aucun diagnostic psychologique et ne remplace jamais l’accompagnateur. Toute hypothèse doit être examinée et validée par le bénéficiaire.

Par défaut, les données transmises par les clients de l’API OpenAI ne sont pas utilisées pour entraîner les modèles, sauf choix explicite de partage de données. Lorsque la Responses API est utilisée, l’application conserve `store=False` lorsque cette option est disponible et adaptée. Ce réglage évite la conservation comme état applicatif, mais ne garantit pas l’absence absolue de toute trace technique. OpenAI peut conserver pendant une durée limitée certains journaux techniques ou de surveillance des abus, selon les règles applicables à l’organisation et au service utilisé. Les règles propres à OpenAI restent applicables.

### JSON de travail

Le JSON de travail permet de sauvegarder et de reprendre le parcours. Il peut contenir les informations nécessaires à cette reprise, notamment les réponses validées, les valeurs, les hypothèses, les validations, les étapes déjà réalisées, les états de navigation, les contrôles de cohérence et les éléments de traçabilité.

Ce fichier reste sous la responsabilité du bénéficiaire. Il peut permettre de reprendre et de modifier le parcours tant que celui-ci n’a pas été clôturé définitivement.

### JSON final et rapport final

Le JSON final est généré uniquement lors d’une clôture définitive. Il est épuré et ne conserve pas les questionnaires détaillés, les dialogues complets, les transcriptions initiales, les fichiers audio, les hypothèses techniques successives ni les états internes nécessaires au travail en cours.

Il contient uniquement les résultats validés et les informations nécessaires à la restitution, à la consultation et à la réimpression du rapport final. Il ne permet plus de reprendre ou de modifier le parcours clôturé.

Le rapport PDF final restitue les éléments validés par le bénéficiaire. Il ne constitue ni un diagnostic, ni un avis médical, ni une décision d’orientation automatique.

### Transmission à l’accompagnateur

Le bénéficiaire peut transmettre son JSON final à l’accompagnateur chargé de son bilan ou de son accompagnement :

- soit automatiquement par l’application, lorsqu’un service d’envoi est configuré ;
- soit manuellement, après téléchargement du fichier.

La finalité de cette transmission est de permettre à l’accompagnateur d’intégrer les résultats validés dans la continuité de l’accompagnement et, le cas échéant, dans les documents de synthèse.

L’envoi automatique porte uniquement sur le JSON final épuré et, si le bénéficiaire le choisit, sur le rapport PDF final. Aucun fichier audio, questionnaire brut, transcription initiale, dialogue complet ou historique technique détaillé n’est transmis dans cet envoi.

Le choix du mode de transmission est libre. L’envoi automatique nécessite un consentement spécifique, distinct du consentement général à l’utilisation de l’application. Le bénéficiaire peut toujours préférer télécharger les documents et les remettre lui-même à son accompagnateur.

### Conservation et traces techniques

Clarté360 ne conserve pas durablement, par cette application, les fichiers audio, JSON ou PDF du bénéficiaire. Le bénéficiaire choisit la durée pendant laquelle il conserve les fichiers téléchargés.

Lorsque l’envoi automatique est utilisé, seules les traces techniques strictement nécessaires au suivi de l’envoi peuvent être enregistrées dans le parcours, par exemple la date, le choix du mode de transmission et le résultat de l’envoi. Elles ne doivent pas contenir le secret technique d’accès ni le contenu détaillé des questionnaires.

Les durées et règles de conservation propres aux prestataires techniques utilisés pour la transcription, l’intelligence artificielle ou l’envoi d’e-mails restent applicables selon leurs propres politiques.

### Code de déblocage et sécurité

L’accès initial à l’application est contrôlé par un code de déblocage stocké dans les paramètres sécurisés de l’application.

Le code secret réel n’est jamais enregistré dans le JSON de travail, le JSON final ou le rapport PDF. Seule une information d’autorisation d’accès, telle que `acces_autorise: true`, et les éléments de traçabilité nécessaires peuvent être conservés. Aucun secret technique ne doit être transmis au bénéficiaire ou à l’accompagnateur.

### Droits et maîtrise des fichiers

Le bénéficiaire peut choisir de ne pas utiliser la voix, de ne pas demander de reformulation, de télécharger ou non ses fichiers et de choisir le mode de transmission de ses résultats. Il peut supprimer les fichiers qu’il conserve sur son propre équipement.

Pour toute question relative à la protection des données ou à l’exercice de ses droits, le bénéficiaire peut utiliser l’onglet **Nous contacter** de l’application ou écrire à Clarté360 à l’adresse indiquée dans les mentions légales.

### Nature des résultats

Les résultats constituent des supports d’aide à la réflexion. Ils ne constituent ni un diagnostic psychologique, ni un avis médical, ni une décision d’orientation automatique. Le bénéficiaire demeure seul décisionnaire des valeurs qu’il retient et valide.

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
.question-card {{ border-left:8px solid #008080; background:linear-gradient(135deg,#E6F4F4 0%,#F8FCFC 100%); padding:1.15rem 1.3rem; border-radius:14px; margin:1.2rem 0 .65rem; box-shadow:0 3px 12px rgba(0,128,128,.10); }}
.question-card .question-kicker {{ color:#007575; font-size:.82rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; margin-bottom:.35rem; }}
.question-card .question-text {{ color:#173838; font-size:1.42rem; line-height:1.38; font-weight:750; }}
.answer-card {{ border:2px solid #74C9A7; background:#EFFAF4; padding:1rem 1.15rem; border-radius:14px; margin:.65rem 0 1rem; box-shadow:0 2px 9px rgba(50,140,100,.10); }}
.answer-card .answer-title {{ color:#18794E; font-size:.9rem; font-weight:800; text-transform:uppercase; letter-spacing:.03em; margin-bottom:.4rem; }}
.answer-card .answer-text {{ color:#17352A; font-size:1.08rem; line-height:1.55; white-space:pre-wrap; }}
/* V2.1.3.8c - navigation plus compacte et professionnelle */
section[data-testid="stSidebar"] div[data-testid="stButton"] > button {{
  min-height:2.7rem; padding:.45rem .6rem; border-radius:10px; font-weight:650;
  text-align:center; justify-content:center; line-height:1.2;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button p {{
  width:100%; text-align:center; margin:0;
}}
.module-status-card {{ border:1px solid #D7EAEA; border-radius:14px; padding:1rem 1.15rem; margin:.7rem 0; background:#FBFEFE; }}
.module-status-title {{ color:#135E5E; font-size:1.06rem; font-weight:750; margin-bottom:.25rem; }}
.module-status-label {{ color:#617575; font-size:.88rem; }}
.qr-review-card {{ border:1px solid #D7EAEA; border-radius:14px; padding:1rem 1.15rem; margin:.8rem 0; background:#FFFFFF; }}
.qr-review-question {{ color:#135E5E; font-weight:750; font-size:1.06rem; margin-bottom:.55rem; }}
.qr-review-answer {{ white-space:pre-wrap; line-height:1.52; color:#263A3A; }}
.transcript-card {{ border:1px solid #AFCACA; background:#F7FBFB; padding:.9rem 1rem; border-radius:12px; margin:.5rem 0; }}
.transcript-card.corrected {{ border-color:#F0C36A; background:#FFF9E9; }}
.response-mode {{ color:#667; font-size:.82rem; margin-top:.45rem; }}
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
    xls = pd.ExcelFile(REFERENTIEL_PATH)
    candidates = [name for name in xls.sheet_names if normalize(name).startswith("referentiel")]
    sheet = candidates[0] if candidates else xls.sheet_names[0]
    df = pd.read_excel(REFERENTIEL_PATH, sheet_name=sheet)
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
        "trace":[], "ai_calls":0, "ai_input_tokens":0, "ai_output_tokens":0, "ai_request_log":[],
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
        "access_authorized":False, "resume_welcome_pending":False, "resume_target_page":"",
        "final_mode":False, "final_payload":{}, "final_pdf_download_offered":False, "final_json_download_offered":False,
        "final_transmission_choice":"", "final_transmission_status":{}, "closure_confirm_step":0,
        "navigation_history":[], "answer_metadata":{}, "reasoning_evolution":[], "resume_new_values_done":False,
        "voice_enabled":True, "data_revision":0, "stale_sections":[], "return_after_personal_values":"",
        "dependency_events":[], "last_consistent_revision":0, "closure_audit":{},
        "json_schema_version":"2.1.3.8E",
        "active_module":"accueil_modules",
        "module_states":{
            "module_1":{"status":"non_commence","step":"intro"},
            "module_2":{"status":"non_commence","step":"questionnaire"},
            "module_3":{"status":"disponible","step":"accueil"},
            "module_4":{"status":"disponible","step":"attente_v2139"},
            "module_5":{"status":"indisponible","step":"accueil"},
        },
        "central_validated_values":[], "values_to_examine":[], "session_review_items":[],
        "current_value_work":{}, "module1_count":0, "module1_index":0,
        "module2_question_index":0, "module2_answers":{},
        "module3_declared_count":0, "module3_index":0, "module3_queue":[],
        "followup_panel_open":True, "report_history":[], "answer_history":{},
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

def mark_user_activity(event: str="interaction_utilisateur") -> None:
    """Réinitialise le délai d'inactivité uniquement lors d'une action réelle."""
    update_runtime_activity(event,user_activity=True)
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
    return OpenAI(api_key=key,timeout=35.0,max_retries=0)

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

def _ai_request_id(call_type:str, payload:Any)->str:
    import hashlib
    raw=json.dumps({"type":call_type,"payload":payload},ensure_ascii=False,sort_keys=True,default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]

def _ai_trace(call_type:str, request_id:str, status:str, *, model:str="", attempts:int=1, error:str="", usage:Any=None)->None:
    registry=st.session_state.setdefault("ai_request_log",[])
    item={"type":call_type,"date_heure":now_iso(),"identifiant":request_id,"statut":status,"tentatives":attempts,"modele":model,"erreur":str(error or "")[:500]}
    if usage is not None:
        item["tokens_entree"]=int(getattr(usage,"input_tokens",0) or 0)
        item["tokens_sortie"]=int(getattr(usage,"output_tokens",0) or 0)
    registry.append(item)

def response_json(instructions:str,payload:dict[str,Any],schema_name:str,schema:dict[str,Any],max_tokens:int=700)->dict[str,Any]:
    model=get_secret("openai","model","gpt-5-mini")
    request_id=_ai_request_id(schema_name,payload)
    cache=st.session_state.setdefault("ai_result_cache",{})
    if request_id in cache:
        _ai_trace(schema_name,request_id,"reussi_cache",model=model,attempts=0)
        return deepcopy(cache[request_id])
    _ai_trace(schema_name,request_id,"en_cours",model=model,attempts=1)
    try:
        client=api_client()
        response=client.responses.create(model=model,instructions=instructions,input=json.dumps(payload,ensure_ascii=False),store=False,max_output_tokens=max_tokens,text={"format":{"type":"json_schema","name":schema_name,"strict":True,"schema":schema}})
        if getattr(response,"status",None) not in (None,"completed"):
            raise RuntimeError(f"Réponse IA incomplète : {getattr(response,'status',None)}")
        usage=getattr(response,"usage",None)
        st.session_state.ai_calls+=1
        if usage:
            st.session_state.ai_input_tokens+=int(getattr(usage,"input_tokens",0) or 0)
            st.session_state.ai_output_tokens+=int(getattr(usage,"output_tokens",0) or 0)
        txt=getattr(response,"output_text","")
        if not txt: raise RuntimeError("Réponse IA vide.")
        result=json.loads(txt)
        cache[request_id]=deepcopy(result)
        _ai_trace(schema_name,request_id,"reussi",model=model,attempts=1,usage=usage)
        return result
    except Exception as exc:
        _ai_trace(schema_name,request_id,"echoue",model=model,attempts=1,error=exc)
        raise RuntimeError(f"L’analyse n’a pas pu aboutir. Votre travail est conservé. Détail : {exc}") from exc

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


def _referential_value_info(name: str) -> dict[str, str]:
    """Retourne uniquement une valeur réellement présente dans le référentiel.

    La comparaison est tolérante à la casse et aux accents, mais n'effectue jamais
    de rapprochement sémantique ou phonétique. Ainsi, « Perfectionnisme » ne peut
    jamais être remplacé automatiquement par « Professionnalisme ».
    """
    target=normalize(name)
    if not target:
        return {}
    for canonical, info in VALUE_MAP.items():
        if normalize(canonical)==target:
            return info
    return {}


def value_info(name:str)->dict[str,str]:
    info=_referential_value_info(name)
    if info:
        return info
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

def _audio_fingerprint(audio_file)->str:
    import hashlib
    data=audio_file.getvalue()
    return hashlib.sha256(data).hexdigest()[:32]

def transcribe_audio(audio_file)->str:
    """Transcrit une seule fois un audio donné, sans conserver ses octets dans les exports."""
    model=get_secret("openai","transcription_model","gpt-4o-mini-transcribe")
    data=audio_file.getvalue()
    if not data or len(data) < 256:
        raise ValueError("Aucun enregistrement exploitable n’a été reçu. Arrêtez l’enregistrement avec le carré puis recommencez.")
    request_id=_audio_fingerprint(audio_file)
    cache=st.session_state.setdefault("audio_transcript_cache",{})
    if request_id in cache:
        _ai_trace("transcription_vocale",request_id,"reussi_cache",model=model,attempts=0)
        return str(cache[request_id])
    _ai_trace("transcription_vocale",request_id,"en_cours",model=model,attempts=1)
    try:
        client=api_client()
        import io
        mime=str(getattr(audio_file,"type","") or "").lower()
        suffix=".webm" if "webm" in mime else ".mp3" if "mpeg" in mime or "mp3" in mime else ".m4a" if "mp4" in mime or "m4a" in mime else ".wav"
        f=io.BytesIO(data); f.name=f"reponse{suffix}"
        result=client.audio.transcriptions.create(model=model,file=f,language="fr",prompt="Transcription verbatim en français. Conservez les hésitations comme euh, heu, hum, les répétitions, les faux départs et les reprises de phrase. Ne corrigez pas et ne reformulez pas.")
        transcript=str(getattr(result,"text","") or "").strip()
        f.close(); del data
        if not transcript: raise ValueError("La transcription est vide. Vous pouvez réessayer ou recommencer votre enregistrement.")
        cache[request_id]=transcript
        st.session_state.ai_calls+=1
        _ai_trace("transcription_vocale",request_id,"reussi",model=model,attempts=1)
        return transcript
    except Exception as exc:
        _ai_trace("transcription_vocale",request_id,"echoue",model=model,attempts=1,error=exc)
        raise

def reset_voice_capture(*, clear_text: bool=True)->None:
    """Invalide tout ancien enregistrement et recrée réellement le composant audio."""
    st.session_state["audio_widget_version"]=int(st.session_state.get("audio_widget_version",0))+1
    if clear_text:
        st.session_state["voice_draft"]=""
        st.session_state.pop("voice_edit",None)
    st.session_state.pop("voice_last_error",None)

def speak_button(text:str,key:str)->None:
    """Lecture navigateur strictement ponctuelle : un clic, une lecture, puis arrêt."""
    if not st.session_state.get("voice_enabled",True):
        return
    safe=json.dumps(text,ensure_ascii=False)
    safe_key=re.sub(r"[^a-zA-Z0-9_-]","_",str(key))
    components.html(f"""
    <button id="speak_{safe_key}" style="border:1px solid #008080;border-radius:8px;padding:8px 12px;background:white;cursor:pointer">🔊 Écouter</button>
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
          btn.textContent = '🔊 Écouter';
          utterance = null;
        }};
        utterance.onend = finish;
        utterance.onerror = finish;
        synth.speak(utterance);
      }}, {{ once: false }});
      window.addEventListener('beforeunload', () => synth.cancel(), {{ once: true }});
    }})();
    </script>""",height=48)

def _safe_widget_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(value))[:90]


def _contains_oral_hesitations(text: str) -> bool:
    """Détecte une proposition encore manifestement trop proche de l'oral brut."""
    return bool(re.search(r"(?i)(^|[\s,;:.!?])(?:euh+|heu+|hum+|bah|ben)(?=[\s,;:.!?]|$)", str(text or "")))


def _official_answer_from_meta(meta: dict[str, Any]) -> str:
    """Retourne uniquement une réponse explicitement validée.

    Les transcriptions et propositions en cours ne deviennent jamais officielles avant
    le choix explicite du bénéficiaire. Les anciens JSON sont réparés séparément par
    ``_repair_answer_metadata_entry`` lorsque ``validee_le`` prouve une validation.
    """
    return str(meta.get("version_officielle", "") or "").strip()

def _repair_answer_metadata_entry(meta: dict[str, Any]) -> bool:
    """Répare les anciens JSON où une réponse validée existe mais version_officielle est vide."""
    if not isinstance(meta, dict):
        return False
    if str(meta.get("version_officielle", "") or "").strip():
        return False
    if not str(meta.get("validee_le", "") or "").strip():
        return False
    recovered=_official_answer_from_meta(meta)
    if not recovered:
        return False
    meta["version_officielle"]=recovered
    if not str(meta.get("mode_saisie", "") or "").strip():
        meta["mode_saisie"]="reprise"
    return True


def repair_all_answer_metadata() -> int:
    """Répare uniformément toutes les réponses des questionnaires chargées en mémoire."""
    repaired=0
    metadata=st.session_state.setdefault("answer_metadata", {})
    for base, meta in metadata.items():
        if _repair_answer_metadata_entry(meta):
            st.session_state[f"{base}_official"]=meta["version_officielle"]
            repaired+=1
    return repaired


def _reset_response_voice_state(base: str) -> None:
    """Réinitialise intégralement le brouillon vocal d'une question sans toucher à sa réponse officielle."""
    current_version=int(st.session_state.get(f"{base}_audio_version",0) or 0)
    keys=[
        f"{base}_audio_{current_version}", f"{base}_audio_id",
        f"{base}_transcript_raw", f"{base}_transcript_clean",
        f"{base}_processing_audio", f"{base}_transcription_error",
        f"{base}_voice_choice", f"{base}_clean_edit",
    ]
    for key in keys:
        st.session_state.pop(key,None)
    st.session_state[f"{base}_audio_version"]=current_version+1


def _clear_response_answer(key: str) -> None:
    """Efface un brouillon invalide sans toucher aux autres réponses du parcours."""
    base=_safe_widget_key(key)
    st.session_state.answer_metadata.pop(base,None)
    st.session_state.pop(f"{base}_official",None)
    st.session_state[f"{base}_editing"]=True
    st.session_state[f"{base}_edit_mode"]=""
    _reset_response_voice_state(base)


def _local_spoken_cleanup(text: str) -> str:
    """Nettoyage conservateur de secours : hésitations et répétitions immédiates."""
    out=str(text or "").strip()
    out=re.sub(r"(?i)(^|[\s,;:.!?])(?:euh+|heu+|hum+|ben|bah)(?=[\s,;:.!?]|$)", r"\1", out)
    out=re.sub(r"\s+([,;:.!?])", r"\1", out)
    out=re.sub(r"\s{2,}", " ", out)
    # Répétitions immédiates de 1 à 4 mots, sans toucher aux répétitions éloignées porteuses de sens.
    out=re.sub(r"(?i)\b([\wÀ-ÖØ-öø-ÿ'-]+(?:\s+[\wÀ-ÖØ-öø-ÿ'-]+){0,3})\s+\1\b", r"\1", out)
    if out and out[0].islower(): out=out[0].upper()+out[1:]
    return out.strip()


def clean_spoken_text(text: str) -> str:
    """Corrige systématiquement la langue, puis reformule seulement si cela aide.

    La correction orthographique, grammaticale et typographique est obligatoire.
    Une proposition peut donc être très proche de l'original lorsqu'elle corrige une
    faute réelle. La fonction retourne une chaîne vide uniquement lorsque le texte est
    déjà correct et qu'aucune amélioration fidèle n'est nécessaire.
    """
    original=str(text or "").strip()
    local=_local_spoken_cleanup(original)
    if not original:
        return ""
    if not ai_ready():
        candidate=local
    else:
        instructions="""Mettez au propre la réponse française fournie.

Ordre obligatoire :
1. Corrigez toujours les fautes d'orthographe, d'accord, de conjugaison, de ponctuation et de typographie.
2. Supprimez les hésitations, répétitions accidentelles et faux départs.
3. Ne reformulez le style que si cela améliore réellement la clarté ou la fluidité.

Règles impératives :
- conservez exactement le sens, la première personne, les faits, nuances et réserves ;
- n'ajoutez aucune idée, valeur, interprétation, diagnostic ou conseil ;
- ne résumez pas et ne rendez pas la phrase plus générale ;
- si le texte est déjà correct et ne nécessite aucune modification, retournez exactement AUCUNE_REFORMULATION ;
- une correction purement orthographique ou grammaticale doit être retournée, même si elle est très proche de l'original.

Retournez uniquement un objet JSON avec la clé texte_corrige."""
        schema={"type":"object","properties":{"texte_corrige":{"type":"string"}},"required":["texte_corrige"],"additionalProperties":False}
        try:
            result=response_json(instructions,{"reponse":original},"reformulation_clarte360",schema,max_tokens=650)
            candidate=str(result.get("texte_corrige","") or "").strip()
        except Exception:
            candidate=local
    if not candidate or candidate.upper()=="AUCUNE_REFORMULATION" or _contains_oral_hesitations(candidate):
        return ""
    # Ne pas éliminer une correction au seul motif qu'elle est très proche du texte initial.
    # Seule une proposition strictement identique après nettoyage des espaces est ignorée.
    compact_original=re.sub(r"\s+", " ", original).strip()
    compact_candidate=re.sub(r"\s+", " ", candidate).strip()
    if compact_candidate==compact_original:
        return ""
    return candidate

def analyse_concept_nature(term: str, definition: str, clarification: str="") -> dict[str, str]:
    """Conclut obligatoirement par l'une des quatre décisions métier de la 8E.

    - valeur_reconnue
    - clarification_requise (une seule question)
    - valeur_absente_possible
    - formulation_non_valeur
    """
    term=str(term or "").strip(); definition=str(definition or "").strip(); clarification=str(clarification or "").strip()
    present=bool(_referential_value_info(_normalise_value_name(term)))
    if not _looks_like_value_label(term):
        return {"decision":"formulation_non_valeur","explication":"Cette proposition ressemble davantage à une phrase, un constat, un ressenti, une aspiration ou un concept important qu'au nom d'une valeur.","question":""}
    fallback={"decision":"valeur_reconnue" if present else "valeur_absente_possible","explication":("Le terme figure dans le référentiel Clarté360 et peut poursuivre son examen." if present else "Le terme ne figure pas dans le référentiel Clarté360, mais il peut néanmoins constituer une valeur personnelle selon le sens que vous lui donnez."),"question":""}
    if not term or not definition:
        return fallback
    low=normalize(term+" "+definition+" "+clarification)
    if not clarification and any(x in low for x in ["peur", "manque", "rassur", "besoin", "protection", "securite financ"]):
        fallback={"decision":"clarification_requise","explication":"Votre formulation peut renvoyer à une valeur, mais aussi à un besoin de sécurité ou à une crainte liée au manque. Une seule clarification est utile avant de poursuivre.","question":"Au-delà du besoin d'être rassuré ou protégé, quel principe souhaitez-vous respecter durablement dans vos propres choix et comportements ?"}
    if not ai_ready():
        return fallback
    instructions="""Analysez avec prudence un terme présenté comme valeur, sa définition personnelle et, s'il existe, l'unique réponse de clarification.
Vous devez conclure par UNE décision parmi exactement quatre :
1. valeur_reconnue : terme présent au référentiel et cohérence suffisante ;
2. clarification_requise : doute réel et significatif, uniquement si aucune clarification n'a encore été donnée ;
3. valeur_absente_possible : terme absent du référentiel mais pouvant constituer une valeur personnelle ;
4. formulation_non_valeur : la saisie est une phrase, un constat, un ressenti, une aspiration ou un concept qui ne constitue pas un nom de valeur.
Distinguez prudemment valeur, besoin, croyance, limite, objectif, qualité, compétence ou comportement.
Une valeur est un principe durable qui oriente les choix et comportements. Ne diagnostiquez pas, n'imposez rien.
Si une clarification a déjà été fournie, vous ne devez jamais demander une seconde question : choisissez l'une des trois autres décisions.
Retournez un JSON strict avec decision, explication et question. La question est vide sauf pour clarification_requise."""
    schema={"type":"object","properties":{"decision":{"type":"string","enum":["valeur_reconnue","clarification_requise","valeur_absente_possible","formulation_non_valeur"]},"explication":{"type":"string"},"question":{"type":"string"}},"required":["decision","explication","question"],"additionalProperties":False}
    try:
        out=response_json(instructions,{"terme":term,"definition_personnelle":definition,"present_referentiel":present,"clarification_deja_donnee":clarification},"analyse_nature_concept",schema,max_tokens=500)
        decision=str(out.get("decision") or fallback["decision"])
        if clarification and decision=="clarification_requise":
            decision="valeur_reconnue" if present else "valeur_absente_possible"
        return {"decision":decision,"explication":str(out.get("explication") or fallback["explication"]),"question":str(out.get("question") or "") if decision=="clarification_requise" else ""}
    except Exception:
        return fallback

def _clear_application_exploration() -> None:
    """Supprime uniquement les productions dépendantes de l'exploration, jamais les valeurs source."""
    generated={n for n,r in st.session_state.get("value_records",{}).items() if (r or {}).get("source") in ("application","exploration_application")}
    for name in generated:
        st.session_state.validation.pop(name,None)
        st.session_state.personal_defs.pop(name,None)
        st.session_state.hypothesis_status.pop(name,None)
        st.session_state.value_records.pop(name,None)
        st.session_state.comments.pop(name,None)
    st.session_state.validated_app_values=[n for n in st.session_state.get("validated_app_values",[]) if n not in generated]
    for key,default in {
        "conversation":[],"candidate_names":[],"candidate_reasons":{},"candidate_evidence":{},
        "hypothesis_history":[],"hypothesis_queue":[],"completed_hypotheses":[],
        "abandoned_hypotheses":[],"discarded":[],"reasoning_evolution":[],
        "analysis_history":[],"analysis_card":{},"completion_check":{},"last_presented_hypotheses":[],
    }.items(): st.session_state[key]=deepcopy(default)
    st.session_state.hypothesis_index=0; st.session_state.validation_index=0
    st.session_state.pipeline_status="idle"; st.session_state.pending_submission={}
    st.session_state.exploration_complete=False


def invalidate_dependencies(scope: str, *, value_name: str="", reason: str="") -> None:
    """Recalcul déterministe des seuls éléments dépendants d'une modification."""
    scope=str(scope or "").strip()
    if not scope: return
    if scope in ("profile","prerequisites","personal_values"):
        _clear_application_exploration()
    elif scope=="exploration":
        _clear_application_exploration()
    elif scope=="value_definition" and value_name:
        st.session_state.validation.pop(value_name,None)
        st.session_state.validation_stage[value_name]=0
        if value_name in st.session_state.validated_app_values: st.session_state.validated_app_values.remove(value_name)
        rec=st.session_state.value_records.get(value_name,{}) or {}
        if rec:
            rec["statut"]="en_cours_analyse"; rec["definition_personnelle"]=st.session_state.personal_defs.get(value_name,rec.get("definition_personnelle","")); st.session_state.value_records[value_name]=rec
        st.session_state.hypothesis_status[value_name]="en_cours_analyse"
        st.session_state.completion_check={}; st.session_state.exploration_complete=False
    elif scope=="validation":
        st.session_state.completion_check={}; st.session_state.exploration_complete=False
    st.session_state.data_revision=int(st.session_state.get("data_revision",0))+1
    for item in ("controle_completude","rapport_final"):
        if item not in st.session_state.stale_sections: st.session_state.stale_sections.append(item)
    st.session_state.dependency_events.append({"date":now_iso(),"scope":scope,"valeur":value_name,"raison":reason,"revision":st.session_state.data_revision})
    business_trace("recalcul_dependances",f"{scope}; valeur={value_name}; {reason}")
    synchronize_value_state()


def open_response_widget(label: str, key: str, *, value: str="", height: int=110,
                         allow_reformulation: bool=True, help_text: str="",
                         listen: bool=True, dependency_scope: str="", value_name: str="") -> str:
    """Moteur unique texte/voix/modification avec validation explicite.

    Aucune transcription ou proposition ne devient officielle avant le choix du
    bénéficiaire. Lors d'une modification, trois intentions sont distinguées :
    nouvelle réponse, correction manuelle de l'actuelle, reformulation directe.
    """
    base=_safe_widget_key(key)
    meta=st.session_state.answer_metadata.setdefault(base,{"mode_saisie":"","texte_brut":"","transcription":"","transcription_corrigee":"","reformulation_proposee":"","reformulation_retenue":"","version_officielle":"","validee_le":""})
    _repair_answer_metadata_entry(meta)
    if value and not _official_answer_from_meta(meta):
        meta.update({"mode_saisie":"reprise","texte_brut":str(value),"version_officielle":str(value),"validee_le":meta.get("validee_le") or now_iso()})
        st.session_state[f"{base}_official"]=str(value)

    st.markdown(f'<div class="question-card"><div class="question-kicker">Question</div><div class="question-text">{html.escape(str(label))}</div></div>',unsafe_allow_html=True)
    if listen: speak_button(label,f"listen_{base}")
    if help_text: st.caption(help_text)

    official=_official_answer_from_meta(meta) or str(st.session_state.get(f"{base}_official") or "").strip()
    editing_key=f"{base}_editing"
    mode_key=f"{base}_edit_mode"
    if editing_key not in st.session_state: st.session_state[editing_key]=not bool(official)

    if official:
        mode_label={"voix":"Réponse orale validée","clavier":"Réponse écrite validée","reprise":"Réponse déjà enregistrée"}.get(str(meta.get("mode_saisie","")),"Réponse validée")
        st.markdown(f'<div class="answer-card"><div class="answer-title">✓ {html.escape(mode_label)}</div><div class="answer-text">{html.escape(official)}</div><div class="response-mode">Enregistrée le {html.escape(str(meta.get("validee_le","") or ""))}</div></div>',unsafe_allow_html=True)
        if not st.session_state.get(editing_key):
            if allow_reformulation and str(meta.get("reformulation_retenue","") or "") in {"","original","Conserver la transcription initiale"}:
                st.info("Votre réponse enregistrée correspond à votre formulation initiale. Vous pouvez la conserver, la corriger ou demander une reformulation Clarté360.")
            if st.button("✏️ Modifier cette réponse",key=f"{base}_edit_btn",use_container_width=True):
                _reset_response_voice_state(base); st.session_state[editing_key]=True; st.session_state[mode_key]=""; st.rerun()

    if not st.session_state.get(editing_key,True): return official

    # Pour une réponse existante, demander l'intention avant d'ouvrir un champ.
    if official and not st.session_state.get(mode_key):
        st.markdown("#### Que souhaitez-vous faire ?")
        c1,c2,c3=st.columns(3)
        with c1:
            if st.button("Saisir une nouvelle réponse",key=f"{base}_mode_new",use_container_width=True): st.session_state[mode_key]="new"; st.rerun()
        with c2:
            if st.button("Corriger ma réponse actuelle",key=f"{base}_mode_correct",use_container_width=True): st.session_state[mode_key]="correct"; st.rerun()
        with c3:
            if st.button("✨ Reformulation Clarté360",key=f"{base}_mode_ai",use_container_width=True,disabled=not allow_reformulation):
                st.session_state[mode_key]="ai"; st.rerun()
        if st.button("Annuler",key=f"{base}_mode_cancel",use_container_width=True): st.session_state[editing_key]=False; st.rerun()
        return official

    edit_mode=st.session_state.get(mode_key) or "new"
    if edit_mode=="ai":
        proposal_key=f"{base}_direct_proposal"
        if proposal_key not in st.session_state:
            with st.spinner("Préparation d’une reformulation fidèle…"):
                st.session_state[proposal_key]=clean_spoken_text(official)
        proposal=str(st.session_state.get(proposal_key) or "").strip()
        if not proposal:
            st.success("Votre réponse est déjà suffisamment claire. Aucune reformulation supplémentaire n’est nécessaire.")
            if st.button("Conserver ma réponse actuelle",key=f"{base}_keep_clear",type="primary",use_container_width=True): st.session_state[editing_key]=False; st.session_state[mode_key]=""; st.rerun()
        else:
            st.markdown(f'<div class="transcript-card"><b>Réponse actuelle</b><br><br>{html.escape(official)}</div>',unsafe_allow_html=True)
            st.markdown(f'<div class="transcript-card corrected"><b>Proposition corrigée Clarté360</b><br><br>{html.escape(proposal)}</div>',unsafe_allow_html=True)
            choice=st.radio("Quelle version souhaitez-vous conserver ?",["Choisissez une option","Conserver ma réponse actuelle","Utiliser la proposition Clarté360"],key=f"{base}_direct_choice")
            if st.button("✓ Valider mon choix",key=f"{base}_direct_validate",type="primary",use_container_width=True,disabled=choice=="Choisissez une option"):
                new_value=official if choice.startswith("Conserver") else proposal
                meta.setdefault("historique_versions",[]); meta["historique_versions"].append({"version":official,"remplacee_le":now_iso(),"motif":"reformulation demandée"})
                meta.update({"mode_saisie":meta.get("mode_saisie") or "reprise","reformulation_proposee":proposal,"reformulation_retenue":"original" if choice.startswith("Conserver") else "clarte360","version_officielle":new_value,"validee_le":now_iso()})
                st.session_state[f"{base}_official"]=new_value; st.session_state[editing_key]=False; st.session_state[mode_key]=""; st.session_state.pop(proposal_key,None)
                if new_value!=official: invalidate_dependencies(dependency_scope,value_name=value_name,reason=f"réponse {base} reformulée")
                st.rerun()
        if st.button("← Retour",key=f"{base}_ai_back",use_container_width=True): st.session_state[mode_key]=""; st.session_state.pop(proposal_key,None); st.rerun()
        return official

    st.markdown("#### Votre nouvelle réponse" if edit_mode=="new" else "#### Corriger votre réponse actuelle")
    initial_text="" if edit_mode=="new" else official
    typed=st.text_area("Votre réponse écrite",value=initial_text,height=height,key=f"{base}_typed_{edit_mode}",label_visibility="collapsed",placeholder="Écrivez ou collez votre réponse ici…",on_change=mark_user_activity,args=(f"saisie_{base}",))
    proposal_key=f"{base}_typed_proposal_{edit_mode}"; source_key=f"{base}_typed_source_{edit_mode}"
    if typed.strip():
        if not allow_reformulation:
            if st.button("✓ Valider ma réponse écrite",key=f"{base}_validate_typed_{edit_mode}",type="primary",use_container_width=True):
                new_value=typed.strip(); meta.setdefault("historique_versions",[])
                if official: meta["historique_versions"].append({"version":official,"remplacee_le":now_iso(),"motif":"modification bénéficiaire"})
                meta.update({"mode_saisie":"clavier","texte_brut":new_value,"reformulation_proposee":"","reformulation_retenue":"original","transcription":"","transcription_corrigee":"","version_officielle":new_value,"validee_le":now_iso()})
                st.session_state[f"{base}_official"]=new_value; st.session_state[editing_key]=False; st.session_state[mode_key]=""; st.rerun()
        else:
            if st.session_state.get(source_key)!=typed.strip(): st.session_state.pop(proposal_key,None)
            if st.button("Préparer et comparer",key=f"{base}_prepare_typed_{edit_mode}",type="primary",use_container_width=True):
                st.session_state[source_key]=typed.strip(); st.session_state[proposal_key]=clean_spoken_text(typed.strip()); st.rerun()
            if source_key in st.session_state:
                proposal=str(st.session_state.get(proposal_key) or "").strip()
                st.markdown(f'<div class="transcript-card"><b>Réponse initiale</b><br><br>{html.escape(typed.strip())}</div>',unsafe_allow_html=True)
                options=["Choisissez une option","Conserver ma réponse initiale"]
                if proposal:
                    st.markdown(f'<div class="transcript-card corrected"><b>Proposition corrigée Clarté360</b><br><br>{html.escape(proposal)}</div>',unsafe_allow_html=True); options.append("Utiliser la proposition Clarté360")
                else: st.success("Votre réponse est déjà suffisamment claire. Aucune reformulation supplémentaire n’est nécessaire.")
                choice=st.radio("Quelle version souhaitez-vous valider ?",options,key=f"{base}_typed_choice_{edit_mode}")
                if st.button("✓ Valider ma réponse écrite",key=f"{base}_validate_typed_{edit_mode}",type="primary",use_container_width=True,disabled=choice=="Choisissez une option"):
                    new_value=proposal if choice.startswith("Utiliser") else typed.strip(); meta.setdefault("historique_versions",[])
                    if official: meta["historique_versions"].append({"version":official,"remplacee_le":now_iso(),"motif":"modification bénéficiaire"})
                    meta.update({"mode_saisie":"clavier","texte_brut":typed.strip(),"reformulation_proposee":proposal,"reformulation_retenue":"clarte360" if choice.startswith("Utiliser") else "original","transcription":"","transcription_corrigee":"","version_officielle":new_value,"validee_le":now_iso()})
                    st.session_state[f"{base}_official"]=new_value; st.session_state[editing_key]=False; st.session_state[mode_key]=""; st.session_state.pop(proposal_key,None); st.session_state.pop(source_key,None)
                    if official and official!=new_value: invalidate_dependencies(dependency_scope,value_name=value_name,reason=f"réponse {base} modifiée")
                    st.rerun()

    st.markdown("#### 🎤 Répondre à l’oral")
    audio=None
    if st.session_state.get("voice_enabled",True) and hasattr(st,"audio_input"):
        audio=st.audio_input("Enregistrer ma réponse",key=f"{base}_audio_{st.session_state.get(base+'_audio_version',0)}",label_visibility="collapsed")
    already_done=False
    if audio:
        audio_id=_audio_fingerprint(audio)
        already_done=(st.session_state.get(f"{base}_audio_id")==audio_id and bool(st.session_state.get(f"{base}_transcript_raw")))
    if audio and st.button("Transcrire et comparer",key=f"{base}_transcribe",type="primary",use_container_width=True,disabled=already_done):
        mark_user_activity(f"transcription_{base}")
        try:
            audio_id=_audio_fingerprint(audio)
            st.session_state[f"{base}_audio_id"]=audio_id
            with st.spinner("Transcription en cours…"):
                raw=transcribe_audio(audio); proposal=clean_spoken_text(raw)
                st.session_state[f"{base}_transcript_raw"]=raw; st.session_state[f"{base}_transcript_clean"]=proposal
        except Exception as exc: st.session_state[f"{base}_transcription_error"]=str(exc)
        st.rerun()
    err=str(st.session_state.pop(f"{base}_transcription_error","") or "")
    if err: st.error(f"La transcription n’a pas pu être réalisée : {err}")
    raw=str(st.session_state.get(f"{base}_transcript_raw","") or ""); proposal=str(st.session_state.get(f"{base}_transcript_clean","") or "")
    if raw:
        st.markdown(f'<div class="transcript-card"><b>Transcription initiale</b><br><br>{html.escape(raw)}</div>',unsafe_allow_html=True)
        options=["Choisissez une option","Conserver la transcription initiale"]
        if proposal:
            st.markdown(f'<div class="transcript-card corrected"><b>Proposition corrigée Clarté360</b><br><br>{html.escape(proposal)}</div>',unsafe_allow_html=True); options.append("Utiliser la proposition Clarté360")
        else: st.success("Votre transcription est déjà suffisamment claire. Aucune reformulation supplémentaire n’est nécessaire.")
        options += ["Corriger manuellement","Réenregistrer"]
        choice=st.radio("Quelle version souhaitez-vous valider ?",options,key=f"{base}_voice_choice")
        manual=""
        if choice=="Corriger manuellement": manual=st.text_area("Votre correction",value=raw,height=height,key=f"{base}_manual_voice")
        if choice=="Réenregistrer":
            if st.button("Ouvrir un nouvel enregistrement",key=f"{base}_voice_redo",use_container_width=True): _reset_response_voice_state(base); st.rerun()
        elif st.button("✓ Valider cette réponse orale",key=f"{base}_validate_voice",type="primary",use_container_width=True,disabled=choice=="Choisissez une option"):
            mark_user_activity(f"validation_orale_{base}")
            retained=proposal if choice.startswith("Utiliser") else manual.strip() if choice=="Corriger manuellement" else raw
            if not retained.strip(): st.error("La version choisie est vide.")
            else:
                meta.setdefault("historique_versions",[])
                if official: meta["historique_versions"].append({"version":official,"remplacee_le":now_iso(),"motif":"modification bénéficiaire"})
                meta.update({"mode_saisie":"voix","texte_brut":raw,"transcription":raw,"transcription_corrigee":proposal,"reformulation_proposee":proposal,"reformulation_retenue":"clarte360" if choice.startswith("Utiliser") else "manuel" if choice=="Corriger manuellement" else "original","version_officielle":retained.strip(),"validee_le":now_iso()})
                st.session_state[f"{base}_official"]=retained.strip(); _reset_response_voice_state(base); st.session_state[editing_key]=False; st.session_state[mode_key]=""
                if official and official!=retained.strip(): invalidate_dependencies(dependency_scope,value_name=value_name,reason=f"réponse vocale {base} modifiée")
                st.rerun()

    if official and st.button("Annuler la modification",key=f"{base}_cancel_edit",use_container_width=True):
        _reset_response_voice_state(base); st.session_state[editing_key]=False; st.session_state[mode_key]=""; st.rerun()
    return official

def mark_data_change(section: str, affects: list[str]|None=None) -> None:
    st.session_state.data_revision=int(st.session_state.get("data_revision",0))+1
    for item in affects or []:
        if item not in st.session_state.stale_sections: st.session_state.stale_sections.append(item)
    business_trace("donnees_modifiees",f"{section}; impacts={','.join(affects or [])}")


def synchronize_value_state() -> None:
    """Réconcilie les structures métier après chaque validation/modification."""
    valid=[]
    for name,val in list(st.session_state.get("validation",{}).items()):
        if bool(val.get("fondamentale")):
            valid.append(name)
            rec=st.session_state.value_records.get(name,{})
            register_value_record(name,rec.get("source","accompagnateur" if name in st.session_state.existing_values else "exploration_application"),"validee",st.session_state.personal_defs.get(name,rec.get("definition_personnelle","")),rec.get("situations_associees",[]),rec.get("emotions_associees",[]),100)
            st.session_state.hypothesis_status[name]="validee"
        elif name in st.session_state.value_records and st.session_state.value_records[name].get("statut")=="validee":
            st.session_state.value_records[name]["statut"]="a_confirmer"
    st.session_state.validated_app_values=[n for n in valid if n not in st.session_state.existing_values]
    # Enlève toute valeur supprimée des listes et files dépendantes.
    known=set(st.session_state.existing_values)|set(st.session_state.value_records)
    st.session_state.candidate_names=[n for n in st.session_state.get("candidate_names",[]) if n in known or n in VALUE_MAP]
    st.session_state.hypothesis_queue=[n for n in st.session_state.get("hypothesis_queue",[]) if n in known or n in VALUE_MAP]
    st.session_state.exploration_complete=False if st.session_state.get("stale_sections") else st.session_state.exploration_complete


def revise_exploration_turn(turn_index: int, new_answer: str) -> None:
    """Repart exactement de la question modifiée et recalcule tout l'aval."""
    turns=list(st.session_state.get("conversation",[]))
    if turn_index<0 or turn_index>=len(turns): return
    question=str(turns[turn_index].get("question","") or "")
    prefix=turns[:turn_index]
    invalidate_dependencies("exploration",reason=f"réponse d'exploration n°{turn_index+1} modifiée")
    st.session_state.conversation=prefix
    st.session_state.current_question=question
    queue_exploration_submission(new_answer.strip())


def closure_consistency_audit() -> tuple[bool,list[str]]:
    """Bloque la clôture tant qu'une dépendance ou restitution n'est pas cohérente."""
    issues=[]; synchronize_value_state()
    if st.session_state.get("stale_sections"): issues.append("Le contrôle de complétude ou le rapport doit être recalculé après une modification.")
    if not st.session_state.get("completion_check"): issues.append("Le contrôle de complétude n'a pas été enregistré.")
    for name in validated_names():
        if not (st.session_state.validation.get(name,{}) or {}).get("fondamentale"): issues.append(f"La valeur {name} est affichée comme validée sans validation fondamentale cohérente.")
    expected=set(validated_names()); recorded={n for n,r in st.session_state.get("value_records",{}).items() if (r or {}).get("statut")=="validee"}
    if expected!=recorded: issues.append("Le panneau des valeurs et les enregistrements métier ne sont pas synchronisés.")
    st.session_state.closure_audit={"date":now_iso(),"revision":st.session_state.get("data_revision",0),"conforme":not issues,"anomalies":issues}
    return not issues,issues

def final_pdf_from_payload(payload: dict[str,Any]) -> bytes:
    """Rapport autonome régénérable depuis le seul JSON final."""
    from reportlab.platypus import Image, Table, TableStyle
    buffer=BytesIO(); styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="FinalTitle",parent=styles["Title"],fontSize=22,leading=27,textColor=colors.HexColor(OFFICIAL_TEAL),alignment=1,spaceAfter=16))
    styles.add(ParagraphStyle(name="FinalH2",parent=styles["Heading2"],textColor=colors.HexColor(OFFICIAL_TEAL),spaceBefore=10,spaceAfter=6))
    def footer(canvas,doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#D7EAEA")); canvas.line(1.5*cm,1.05*cm,A4[0]-1.5*cm,1.05*cm); canvas.setFont("Helvetica",7.5); canvas.setFillColor(colors.HexColor("#666666")); canvas.drawString(1.5*cm,.65*cm,"Clarté360 - Document confidentiel"); canvas.drawRightString(A4[0]-1.5*cm,.65*cm,f"Page {doc.page}"); canvas.restoreState()
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=1.7*cm,leftMargin=1.7*cm,topMargin=1.5*cm,bottomMargin=1.4*cm,title="Rapport final RVC360")
    ident=payload.get("identite",{}); vals=payload.get("valeurs_fondamentales",[]); story=[]
    if LOGO_PATH.exists(): story += [Image(str(LOGO_PATH),width=2.6*cm,height=2.6*cm),Spacer(1,.35*cm)]
    story += [Paragraph("Recherche de mes valeurs",styles["FinalTitle"]),Paragraph(f"<b>Bénéficiaire :</b> {html.escape((ident.get('prenom','')+' '+ident.get('nom','')).strip())}",styles["Normal"]),Paragraph(f"<b>Parcours :</b> {html.escape(str(payload.get('passation_id','')))}",styles["Normal"]),Paragraph(f"<b>Clôture :</b> {html.escape(str(payload.get('date_cloture','')))}",styles["Normal"]),Spacer(1,.35*cm),Paragraph("Synthèse finale",styles["FinalH2"])]
    summary=payload.get("synthese_finale",{})
    story.append(Paragraph(html.escape(str(summary.get("texte","Les valeurs ci-dessous ont été validées par le bénéficiaire."))),styles["Normal"]))
    for i,v in enumerate(vals,1):
        story += [Paragraph(f"{i}. {html.escape(str(v.get('nom','')))}",styles["FinalH2"]),Paragraph(f"<b>Origine :</b> {html.escape(str(v.get('origine','')))}",styles["Normal"]),Paragraph(html.escape(str(v.get('definition_personnelle','') or 'Définition personnelle non renseignée.')),styles["Normal"])]
        sits=v.get("situations_significatives",[]) or []
        if sits: story.append(Paragraph("<b>Situation(s) significative(s) :</b> "+html.escape(" ; ".join(map(str,sits))),styles["Normal"]))
    elements=payload.get("elements_a_reprendre_avec_accompagnateur","")
    if elements: story += [Paragraph("À reprendre avec l’accompagnateur",styles["FinalH2"]),Paragraph(html.escape(str(elements)),styles["Normal"])]
    doc.build(story,onFirstPage=footer,onLaterPages=footer); return buffer.getvalue()

def value_reminder()->None:
    text="Une valeur est un principe profondément important qui oriente vos choix et votre manière de vivre. Ce n'est ni une simple préférence, ni une qualité, ni un objectif. Le mot retenu doit avoir pour vous un sens personnel précis."
    speak_button(text,"listen_value_reminder")
    st.info(text)

def validated_names()->list[str]:
    central = st.session_state.get("central_validated_values", [])
    if central:
        return [str(v.get("nom_final") or v.get("nom") or "").strip() for v in central if v.get("statut") == "validee" and not v.get("en_reexamen") and str(v.get("nom_final") or v.get("nom") or "").strip()]
    names=list(dict.fromkeys(st.session_state.existing_values+st.session_state.get("validated_app_values",[])))
    return [n for n in names if st.session_state.validation.get(n,{}).get("fondamentale")]


MODULE_LABELS = {
    "module_1":"1. Prérequis", "module_2":"2. Faisons connaissance",
    "module_3":"3. Valider ou revoir une valeur", "module_4":"4. Rechercher une nouvelle valeur",
    "module_5":"5. Mes rapports",
}
MODULE2_QUESTIONS = [
    {"id":"M2-IDENTITE-001","rubrique":"Votre situation","text":"Quelle est votre situation actuelle ? Vous pouvez préciser, si vous le souhaitez, votre âge, votre situation familiale, votre métier et vos principales activités."},
    {"id":"M2-PARCOURS-001","rubrique":"Votre parcours","text":"Quels éléments de votre parcours vous semblent importants ?"},
    {"id":"M2-ENTOURAGE-001","rubrique":"Votre environnement","text":"Quelles personnes ou activités occupent une place importante dans votre vie ?"},
    {"id":"M2-INTERETS-001","rubrique":"Vos centres d’intérêt","text":"Quelles sont vos passions ou vos centres d’intérêt ?"},
    {"id":"M2-PROJETS-001","rubrique":"Vos projets","text":"Quels projets ou changements envisagez-vous ?"},
    {"id":"M2-OBJECTIF-001","rubrique":"Votre démarche","text":"Qu’aimeriez-vous mieux comprendre ou vérifier grâce à cette recherche de valeurs ?"},
]

def _module_state(module_id: str) -> dict[str, Any]:
    return st.session_state.module_states.setdefault(module_id,{"status":"non_commence","step":"accueil"})

def _set_module_status(module_id: str, status: str, step: str|None=None) -> None:
    state=_module_state(module_id); state["status"]=status
    if step is not None: state["step"]=step

def _find_central_value(name: str) -> dict[str,Any]|None:
    n=normalize(name)
    for item in st.session_state.get("central_validated_values",[]):
        if normalize(item.get("nom_final") or item.get("nom") or "")==n: return item
    return None

def _upsert_central_value(name: str, definition_personnelle: str, source: str, *, definition_clarte360: str="", questionnaire: dict[str,Any]|None=None, protected: bool=False, work: dict[str,Any]|None=None) -> None:
    canonical=_normalise_value_name(name)
    item=_find_central_value(canonical)
    work=work or {}
    payload={"nom_final":canonical,"definition_personnelle":definition_personnelle.strip(),"definition_clarte360":definition_clarte360.strip(),"source":source,"statut":"validee","questionnaire":questionnaire or {},"protected":protected,"en_reexamen":False,"validee_le":now_iso(),"mode_decouverte":work.get("mode_decouverte",""),"analyse_coherence":work.get("analyse",""),"nature_decision":work.get("nature_decision",""),"clarifications":deepcopy(work.get("clarifications",[]))}
    old_name=str(work.get("original_name") or "").strip()
    if not item and old_name:
        item=_find_central_value(old_name)
    if item:
        item.setdefault("historique",[]).append({"date":now_iso(),"etat_precedent":deepcopy(item),"motif":"mise_a_jour"}); item.update(payload)
    else:
        st.session_state.central_validated_values.append(payload)
    # Nettoyage atomique des autres listes et des anciens alias.
    _remove_value_from_active_lists(canonical,keep="validee")
    if old_name and normalize(old_name)!=normalize(canonical):
        _remove_value_from_active_lists(old_name,keep="validee")
        st.session_state.personal_defs.pop(old_name,None); st.session_state.validation.pop(old_name,None)
        if old_name in st.session_state.validated_app_values: st.session_state.validated_app_values.remove(old_name)
    st.session_state.personal_defs[canonical]=definition_personnelle.strip()
    st.session_state.validation[canonical]={"importante":True,"tres_importante":True,"fondamentale":True,"origine_validation":source}
    if source=="accompagnateur" and canonical not in st.session_state.existing_values: st.session_state.existing_values.append(canonical)
    if source!="accompagnateur" and canonical not in st.session_state.validated_app_values: st.session_state.validated_app_values.append(canonical)
    register_value_record(canonical,source,"validee",definition_personnelle,certainty=100)
    _set_module_status("module_5","disponible","accueil")

def _add_review_item(work: dict[str,Any], reason: str) -> bool:
    terme=(work.get("nom_final") or work.get("nom_initial") or work.get("nom") or "").strip()
    if not terme:
        return False
    existing=st.session_state.get("session_review_items",[])
    if any(normalize(x.get("terme", "")) == normalize(terme) and x.get("statut") == "a_revoir_en_seance" for x in existing):
        return False
    item={"id":str(uuid.uuid4()),"terme":_normalise_value_name(terme),"definition":work.get("definition_personnelle","") or work.get("definition", ""),"analyse":work.get("analyse","") or work.get("hypothese", ""),"motif":reason,"statut":"a_revoir_en_seance","date":now_iso(),"source":work.get("source", ""),"clarifications":deepcopy(work.get("clarifications",[]))}
    _remove_value_from_active_lists(terme,keep="a_revoir")
    st.session_state.session_review_items.append(item)
    return True

def _new_value_work(source: str="manuel") -> dict[str,Any]:
    return {"id":str(uuid.uuid4()),"source":source,"stage":"nom","nom_initial":"","nom_normalise":"","nom_final":"","mode_decouverte":"","definition_personnelle":"","definition_clarte360":"","present_referentiel":False,"analyse":"","clarification":"","clarifications":[],"nature_decision":"","questionnaire":{},"created_at":now_iso()}

def _normalise_value_name(raw: str) -> str:
    """Normalise un nom de valeur sans en changer le sens.

    Retire les articles purement linguistiques, la ponctuation terminale, harmonise
    espaces/casse/accents via le référentiel puis renvoie la forme canonique.
    """
    text=" ".join(str(raw or "").strip().split())
    text=re.sub(r"[\s.,;:!?]+$", "", text).strip()
    text=re.sub(r"(?i)^(?:l['’]|le\s+|la\s+|les\s+|un\s+|une\s+)", "", text).strip()
    if not text:
        return ""
    # Une normalisation ne doit jamais substituer une valeur par une autre.
    # On adopte la forme canonique du référentiel uniquement en cas d'équivalence
    # stricte après retrait des articles, espaces, casse et accents.
    info=_referential_value_info(text)
    if info:
        return info["nom"]
    return text[:1].upper()+text[1:]

def _looks_like_value_label(raw: str) -> bool:
    """Contrôle de forme : un nom de valeur est un mot ou groupe nominal court, pas une phrase."""
    text=" ".join(str(raw or "").strip().split())
    if not text:
        return False
    words=re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+",text)
    if len(words)>6:
        return False
    low=normalize(text)
    phrase_markers=(" je "," j "," nous "," on "," parce que "," afin de "," pour que "," lorsque "," quand "," qui "," que ")
    padded=f" {low} "
    return not any(m in padded for m in phrase_markers)

def _active_value_location(name: str, *, exclude_work_id: str="") -> tuple[str,dict[str,Any]|None]:
    """Retourne l'unique emplacement actif d'un terme déjà connu après normalisation."""
    n=normalize(_normalise_value_name(name))
    if not n:
        return "",None
    for item in st.session_state.get("central_validated_values",[]):
        if normalize(_normalise_value_name(item.get("nom_final") or item.get("nom") or ""))==n:
            return "validee",item
    for item in st.session_state.get("values_to_examine",[]):
        if item.get("id")==exclude_work_id:
            continue
        if normalize(_normalise_value_name(item.get("nom_final") or item.get("nom_initial") or item.get("nom") or ""))==n:
            return "a_examiner",item
    for item in st.session_state.get("session_review_items",[]):
        if normalize(_normalise_value_name(item.get("terme") or ""))==n and item.get("statut")=="a_revoir_en_seance":
            return "a_revoir",item
    return "",None

def _remove_value_from_active_lists(name: str, *, keep: str="validee") -> None:
    """Garantit : une valeur = un état actuel = une seule liste active."""
    n=normalize(_normalise_value_name(name))
    if keep!="a_examiner":
        st.session_state.values_to_examine=[x for x in st.session_state.get("values_to_examine",[]) if normalize(_normalise_value_name(x.get("nom_final") or x.get("nom_initial") or x.get("nom") or ""))!=n]
    if keep!="a_revoir":
        st.session_state.session_review_items=[x for x in st.session_state.get("session_review_items",[]) if normalize(_normalise_value_name(x.get("terme") or ""))!=n]
    if keep!="validee":
        st.session_state.central_validated_values=[x for x in st.session_state.get("central_validated_values",[]) if normalize(_normalise_value_name(x.get("nom_final") or x.get("nom") or ""))!=n]

def _ensure_migrated_state() -> None:
    # Migration non destructive des JSON V2.1.3.7 et états historiques.
    if not st.session_state.get("central_validated_values"):
        for name in list(dict.fromkeys(st.session_state.get("existing_values",[])+st.session_state.get("validated_app_values",[]))):
            if st.session_state.get("validation",{}).get(name,{}).get("fondamentale"):
                info=value_info(name)
                st.session_state.central_validated_values.append({"nom_final":name,"definition_personnelle":st.session_state.get("personal_defs",{}).get(name,"") or info.get("definition",""),"definition_clarte360":info.get("definition",""),"source":"accompagnateur" if name in st.session_state.get("existing_values",[]) else "application","statut":"validee","questionnaire":st.session_state.get("validation",{}).get(name,{}),"protected":name in st.session_state.get("existing_values",[]),"en_reexamen":False,"validee_le":now_iso()})

    # Priorité à l'état métier détaillé : une valeur restée « en cours d'analyse » dans un ancien JSON
    # devient une valeur à examiner, même si une ancienne liste technique la marquait aussi abandonnée.
    pending_names={normalize(v) for x in st.session_state.get("values_to_examine",[]) for v in (x.get("nom_final"),x.get("nom_initial"),x.get("nom")) if v}
    validated_norm={normalize(x.get("nom_final") or x.get("nom") or "") for x in st.session_state.get("central_validated_values",[])}
    for name,record in (st.session_state.get("value_records",{}) or {}).items():
        status=str(record.get("statut", "")).lower()
        if status not in {"en_cours_analyse","a_confirmer","a_examiner","terme_a_confirmer","questionnaire_a_realiser"}:
            continue
        candidate_variants={normalize(name), normalize(record.get("nom_propose") or name), normalize(_normalise_value_name(record.get("nom_propose") or name))}
        if candidate_variants & validated_norm or candidate_variants & pending_names:
            continue
        info=value_info(name)
        work=_new_value_work("migration_v2137")
        final_name=_normalise_value_name(record.get("nom_propose") or name)
        work.update({"nom_initial":record.get("nom_propose") or name,"nom_normalise":final_name,"nom_final":final_name,"definition_personnelle":record.get("definition_personnelle") or st.session_state.get("personal_defs",{}).get(name,""),"definition_clarte360":info.get("definition", ""),"present_referentiel":bool(info),"mode_decouverte":"À partir d’une situation vécue" if record.get("situations_associees") else "Par introspection","stage":"nom","migration_status_initial":status})
        st.session_state.values_to_examine.append(work)
        pending_names.add(normalize(name))

    if st.session_state.get("prerequisite_confirmed"):
        _set_module_status("module_1","termine","termine")
    if st.session_state.get("profile_complete"):
        _set_module_status("module_2","termine","consultation")
    if st.session_state.get("values_to_examine"):
        _set_module_status("module_3","disponible","valeurs_a_examiner")
    # Une valeur validée ne peut rester simultanément dans « À examiner ».
    validated_now=[x.get("nom_final","") for x in st.session_state.get("central_validated_values",[])]
    for validated_name in validated_now:
        _remove_value_from_active_lists(validated_name,keep="validee")
    if validated_names(): _set_module_status("module_5","disponible","accueil")

def render_module_menu() -> None:
    with st.sidebar:
        st.markdown("<h3 style='text-align:center;margin:.2rem 0 .8rem'>Mon parcours</h3>",unsafe_allow_html=True)
        if st.button("🏠  Accueil du parcours",key="menu_accueil_modules",use_container_width=True):
            st.session_state.active_module="accueil_modules"; st.session_state.page="Modules"; st.rerun()
        active=st.session_state.get("active_module","")
        for mid,label in MODULE_LABELS.items():
            state=_module_state(mid); status=state.get("status","non_commence")
            icon={"termine":"✅","en_cours":"▶","disponible":"○","indisponible":"🔒","non_commence":"○"}.get(status,"○")
            active_mark="  •" if active==mid else ""
            if st.button(f"{icon}  {label}{active_mark}",key=f"menu_{mid}",use_container_width=True,disabled=status=="indisponible"):
                st.session_state.active_module=mid; st.session_state.page="Modules"; st.rerun()
        st.markdown("<div style='text-align:center;color:#6B7D7D;font-size:.78rem;margin-top:.5rem'>✅ Terminé &nbsp;·&nbsp; ▶ En cours &nbsp;·&nbsp; ○ Disponible</div>",unsafe_allow_html=True)

def render_followup_panel() -> None:
    vals=validated_names(); pending=st.session_state.get("values_to_examine",[]); review=st.session_state.get("session_review_items",[])
    opened=st.toggle(f"Afficher le suivi de mes valeurs ({len(vals)})",value=bool(st.session_state.get("followup_panel_open",True)),key="followup_panel_toggle")
    st.session_state.followup_panel_open=bool(opened)
    if not opened:
        st.caption(f"Mes valeurs ({len(vals)}) ▶")
        return
    with st.container(border=True):
        st.markdown("**✅ Valeurs validées**")
        st.write(", ".join(vals) if vals else "Aucune pour le moment.")
        st.markdown("**🔎 Valeurs à examiner**")
        st.write(", ".join(str(x.get("nom_final") or x.get("nom") or x.get("nom_initial") or "") for x in pending) if pending else "Aucune.")
        st.markdown("**📋 À revoir en séance**")
        st.write(", ".join(str(x.get("terme") or "") for x in review) if review else "Aucun sujet.")

def _value_definition_choices(work: dict[str,Any], prefix: str) -> tuple[str,str]:
    personal=work.get("definition_personnelle",""); official=work.get("definition_clarte360","")
    st.markdown("**Votre définition personnelle**"); st.info(personal or "Non renseignée")
    if official:
        st.markdown("**Définition Clarté360**"); st.info(official)
        choice=st.radio("Quelle définition souhaitez-vous retenir ?",["Ma définition personnelle","La définition Clarté360","Une formulation combinée"],key=f"{prefix}_def_choice")
        combined=""
        if choice=="Une formulation combinée": combined=st.text_area("Formulation combinée fidèle",value=personal,key=f"{prefix}_combined")
        return choice, (personal if choice=="Ma définition personnelle" else official if choice=="La définition Clarté360" else combined.strip())
    return "Ma définition personnelle", personal

def render_modules_home() -> None:
    st.title("Mon parcours de recherche de valeurs")
    st.info("Choisissez librement le module dans lequel vous souhaitez travailler. Une reprise exacte peut être proposée, mais elle n'est jamais imposée.")
    labels={"module_1":"Prérequis — valeurs validées avec l’accompagnateur","module_2":"Faisons connaissance","module_3":"Valider ou revoir une valeur","module_4":"Rechercher une nouvelle valeur avec Clarté360","module_5":"Mes rapports"}
    for mid in MODULE_LABELS:
        state=_module_state(mid); status=state.get("status","non_commence")
        status_label={"termine":"Terminé","en_cours":"En cours","disponible":"Disponible","indisponible":"Indisponible","non_commence":"Non commencé"}.get(status,status)
        with st.container(border=True):
            c1,c2=st.columns([4,1])
            with c1:
                st.markdown(f"### {labels[mid]}")
                st.caption(status_label)
            with c2:
                if st.button("Ouvrir",key=f"home_open_{mid}",use_container_width=True,disabled=status=="indisponible"):
                    st.session_state.active_module=mid; st.session_state.page="Modules"; st.rerun()

def render_module_1() -> None:
    st.title("Prérequis — valeurs déjà validées avec l’accompagnateur")
    state=_module_state("module_1")
    if state.get("status")=="termine":
        st.success("Ce prérequis est clôturé. Il reste consultable et ne sera pas rejoué automatiquement.")
        items=[x for x in st.session_state.central_validated_values if x.get("source")=="accompagnateur"]
        if not items:
            st.info("Aucune valeur validée avec l’accompagnateur n’est enregistrée.")
        for item in items:
            with st.container(border=True):
                st.markdown(f"### {item.get('nom_final','')}")
                st.markdown("**Votre définition retenue**")
                st.write(item.get("definition_personnelle") or "Non renseignée")
                if item.get("definition_clarte360"):
                    st.markdown("**Définition Clarté360**")
                    st.write(item.get("definition_clarte360"))
                st.caption("Source : validée avec l’accompagnateur")
        st.divider()
        if st.button("← Retour à l’accueil du parcours",use_container_width=True,key="m1_back_home"):
            st.session_state.active_module="accueil_modules"; st.session_state.page="Modules"; st.rerun()
        return
    _set_module_status("module_1","en_cours",state.get("step","intro"))
    if not st.session_state.get("module1_count"):
        st.warning("Ce module concerne uniquement les valeurs déjà identifiées et validées humainement avec votre accompagnateur.")
        count=int(st.number_input("Combien de valeurs avez-vous déjà identifiées et validées avec votre accompagnateur ?",min_value=1,max_value=15,value=1))
        c1,c2=st.columns(2)
        with c1:
            if st.button("← Retour au parcours",use_container_width=True,key="m1_intro_back"):
                st.session_state.active_module="accueil_modules"; st.rerun()
        with c2:
            if st.button("Commencer",type="primary",use_container_width=True):
                st.session_state.module1_count=count; st.session_state.module1_index=0; st.session_state.current_value_work=_new_value_work("accompagnateur"); st.rerun()
        return
    idx=int(st.session_state.module1_index); total=int(st.session_state.module1_count)
    st.progress(min(1.0,idx/max(1,total))); st.caption(f"Valeur {idx+1} sur {total}")
    work=st.session_state.current_value_work or _new_value_work("accompagnateur")
    name=open_response_widget("Quelle valeur avez-vous identifiée et validée avec votre accompagnateur ?",f"m1_name_{idx}",value=work.get("nom_initial",""),height=70,allow_reformulation=False)
    definition=open_response_widget("Que signifie précisément cette valeur pour vous ?",f"m1_def_{idx}",value=work.get("definition_personnelle",""),height=110,dependency_scope="prerequisites",value_name=name)
    if name and definition:
        work["nom_initial"]=name; work["nom_normalise"]=_normalise_value_name(name); work["nom_final"]=work["nom_normalise"]; work["definition_personnelle"]=definition
        info=value_info(work["nom_final"]); work["present_referentiel"]=bool(info); work["definition_clarte360"]=info.get("definition","")
        if work["nom_final"]!=name: st.info(f"Formulation normalisée proposée : **{work['nom_final']}**")
        choice,final_def=_value_definition_choices(work,f"m1_{idx}")
        confirm=st.checkbox("Je confirme que le mot et la définition retenus correspondent à la valeur déjà validée avec mon accompagnateur.",key=f"m1_confirm_{idx}")
        c1,c2=st.columns(2)
        with c1:
            if st.button("← Retour au parcours",use_container_width=True,key=f"m1_work_back_{idx}"):
                st.session_state.active_module="accueil_modules"; st.rerun()
        with c2:
            if st.button("Valider cette valeur",type="primary",disabled=not(confirm and final_def),key=f"m1_save_{idx}",use_container_width=True):
                _upsert_central_value(work["nom_final"],final_def,"accompagnateur",definition_clarte360=work.get("definition_clarte360",""),protected=True)
                if not work["present_referentiel"]: notify_new_value(work["nom_final"],final_def)
                st.session_state.module1_index=idx+1; st.session_state.current_value_work=_new_value_work("accompagnateur")
                if idx+1>=total: _set_module_status("module_1","termine","termine"); st.session_state.prerequisite_confirmed=True; st.session_state.active_module="accueil_modules"
                st.rerun()

def _hydrate_module2_answers() -> None:
    answers=st.session_state.setdefault("module2_answers",{})
    profile=st.session_state.get("beneficiary_profile",{}) or {}
    legacy=st.session_state.get("presentation_beneficiaire",{}) or {}
    stored_questions=profile.get("questions",{}) if isinstance(profile,dict) else {}
    mapping={
        "M2-IDENTITE-001": legacy.get("situation_actuelle") or profile.get("situation_actuelle"),
        "M2-PARCOURS-001": legacy.get("parcours") or profile.get("parcours"),
        "M2-ENTOURAGE-001": legacy.get("activites_importantes") or profile.get("activites_importantes"),
        "M2-INTERETS-001": legacy.get("passions") or profile.get("passions"),
        "M2-PROJETS-001": legacy.get("projets") or profile.get("projets"),
        "M2-OBJECTIF-001": legacy.get("objectif_demarche") or profile.get("objectif_demarche"),
    }
    for q in MODULE2_QUESTIONS:
        qid=q["id"]
        if not str(answers.get(qid,"") or "").strip():
            value=stored_questions.get(qid) or mapping.get(qid) or ""
            if value: answers[qid]=str(value)


def render_module_2() -> None:
    st.title("Faisons connaissance")
    _hydrate_module2_answers()
    state=_module_state("module_2"); answers=st.session_state.module2_answers
    if state.get("status")=="termine":
        st.success("Vos réponses sont enregistrées. Elles restent visibles et vous pouvez modifier uniquement celle que vous choisissez.")
        for index,q in enumerate(MODULE2_QUESTIONS,1):
            qid=q["id"]; value=str(answers.get(qid,"") or "").strip()
            st.markdown(f"#### Question {index} — {q['rubrique']}")
            # open_response_widget affiche la réponse officielle puis n'ouvre l'édition qu'après clic.
            new_value=open_response_widget(q["text"],f"m2_{qid}",value=value,height=110,dependency_scope="profile")
            if new_value: answers[qid]=new_value
            st.divider()
        st.session_state.beneficiary_profile={"questions":deepcopy(answers),"presentation_libre":"\n\n".join(v for v in answers.values() if v),"date":now_iso()}
        if st.button("← Retour à l’accueil du parcours",use_container_width=True,key="m2_back_home"):
            st.session_state.active_module="accueil_modules"; st.session_state.page="Modules"; st.rerun()
        return
    _set_module_status("module_2","en_cours","questionnaire")
    idx=int(st.session_state.module2_question_index)
    q=MODULE2_QUESTIONS[idx]
    st.progress(idx/len(MODULE2_QUESTIONS)); st.caption(f"Question {idx+1} sur {len(MODULE2_QUESTIONS)} — {q['rubrique']}")
    val=open_response_widget(q["text"],f"m2_{q['id']}",value=answers.get(q["id"],""),height=110,dependency_scope="profile")
    if val:
        answers[q["id"]]=val
        c1,c2=st.columns(2)
        with c1:
            if st.button("← Retour au parcours",use_container_width=True,key=f"m2_back_{idx}"):
                st.session_state.active_module="accueil_modules"; st.rerun()
        with c2:
            if st.button("Continuer",type="primary",key=f"m2_next_{idx}",use_container_width=True):
                st.session_state.module2_question_index=idx+1
                if idx+1>=len(MODULE2_QUESTIONS):
                    _set_module_status("module_2","termine","consultation"); st.session_state.profile_complete=True
                    st.session_state.beneficiary_profile={"questions":deepcopy(answers),"presentation_libre":"\n\n".join(v for v in answers.values() if v),"date":now_iso()}; st.session_state.active_module="accueil_modules"
                st.rerun()

def _module3_current_work() -> dict[str,Any]:
    if not st.session_state.current_value_work or st.session_state.current_value_work.get("source")=="accompagnateur": st.session_state.current_value_work=_new_value_work("manuel")
    return st.session_state.current_value_work

def _pending_value_summary(work: dict[str,Any]) -> None:
    with st.container(border=True):
        st.markdown(f"### {work.get('nom_final') or work.get('nom_initial') or work.get('nom') or 'Valeur à examiner'}")
        if work.get("nom_initial") and work.get("nom_final") and normalize(work.get("nom_initial"))!=normalize(work.get("nom_final")):
            st.write(f"**Terme initial :** {work.get('nom_initial')}")
        st.write(f"**Définition personnelle :** {work.get('definition_personnelle') or work.get('definition') or 'Non renseignée'}")
        if work.get("mode_decouverte"): st.write(f"**Mode de découverte :** {work.get('mode_decouverte')}")
        record=st.session_state.get("value_records",{}).get(work.get("nom_initial"),{}) or st.session_state.get("value_records",{}).get(work.get("nom_final"),{}) or {}
        situations=record.get("situations_associees",[]) or []
        emotions=record.get("emotions_associees",[]) or []
        if situations: st.write("**Situation déjà enregistrée :** "+" ; ".join(map(str,situations)))
        if emotions: st.write("**Réaction ou ressenti déjà enregistré :** "+" ; ".join(map(str,emotions)))
        if work.get("definition_clarte360"): st.write(f"**Définition Clarté360 :** {work.get('definition_clarte360')}")
        st.caption("Ces informations seront préremplies. Elles ne vous seront pas redemandées.")


def _abandon_current_module3_value() -> None:
    """Abandonne seulement la valeur courante ; les valeurs déjà validées restent acquises."""
    work=st.session_state.get("current_value_work",{}) or {}
    if work.get("source")=="reexamen":
        original=_find_central_value(work.get("original_name") or work.get("nom_initial") or work.get("nom_final") or "")
        if original: original["en_reexamen"]=False
    business_trace("abandon_valeur_courante",work.get("nom_final") or work.get("nom_initial") or "")
    _advance_module3()

def _stop_module3_series() -> None:
    """Arrête les valeurs restantes sans supprimer celles déjà complètement validées."""
    work=st.session_state.get("current_value_work",{}) or {}
    if work.get("source")=="reexamen":
        original=_find_central_value(work.get("original_name") or work.get("nom_initial") or work.get("nom_final") or "")
        if original: original["en_reexamen"]=False
    business_trace("arret_valeurs_restantes",f"à partir de {int(st.session_state.get('module3_index',0))+1}")
    st.session_state.module3_queue=[]; st.session_state.current_value_work={}; st.session_state.module3_index=0
    _set_module_status("module_3","disponible","accueil")

def _cancel_module3_work() -> None:
    """Compatibilité historique : retour sans modifier lors d'un réexamen isolé."""
    _stop_module3_series()

def render_module_3() -> None:
    st.title("Valider ou revoir une valeur")
    _set_module_status("module_3","en_cours","travail")
    if not st.session_state.module3_queue:
        pending=st.session_state.get("values_to_examine",[])
        options=["Saisir une nouvelle valeur"]+(["Examiner une valeur en attente"] if pending else [])+(["Réexaminer une valeur déjà validée dans Clarté360"] if any(v.get('source')!='accompagnateur' for v in st.session_state.central_validated_values) else [])
        mode=st.radio("Que souhaitez-vous faire ?",options,key="m3_entry_mode")
        if mode=="Saisir une nouvelle valeur":
            count=int(st.number_input("Combien de valeurs souhaitez-vous explorer ?",1,15,1,key="m3_count"))
            c1,c2=st.columns(2)
            with c1:
                if st.button("← Retour au parcours",use_container_width=True,key="m3_new_back"):
                    st.session_state.active_module="accueil_modules"; st.rerun()
            with c2:
                if st.button("Commencer",type="primary",use_container_width=True):
                    st.session_state.module3_declared_count=count; st.session_state.module3_queue=[_new_value_work("manuel") for _ in range(count)]; st.session_state.module3_index=0; st.session_state.current_value_work=st.session_state.module3_queue[0]; st.rerun()
        elif mode=="Examiner une valeur en attente":
            selected=st.selectbox("Valeur à examiner",range(len(pending)),format_func=lambda i:pending[i].get("nom_final") or pending[i].get("nom_initial") or "Valeur")
            chosen=pending[selected]
            _pending_value_summary(chosen)
            c1,c2=st.columns(2)
            with c1:
                if st.button("← Retour sans modifier",use_container_width=True,key="m3_pending_back"):
                    st.session_state.active_module="accueil_modules"; st.rerun()
            with c2:
                if st.button("Poursuivre l’examen de cette valeur",type="primary",use_container_width=True,key="m3_pending_open"):
                    work=deepcopy(chosen); st.session_state.values_to_examine=[x for i,x in enumerate(pending) if i!=selected]
                    st.session_state.module3_queue=[work]; st.session_state.module3_index=0; st.session_state.current_value_work=work; st.rerun()
        else:
            candidates=[v for v in st.session_state.central_validated_values if v.get("source")!="accompagnateur"]
            selected=st.selectbox("Valeur à réexaminer",range(len(candidates)),format_func=lambda i:candidates[i]["nom_final"])
            original=candidates[selected]
            with st.container(border=True):
                st.markdown(f"### {original.get('nom_final','')}")
                st.write(f"**Définition personnelle actuelle :** {original.get('definition_personnelle') or 'Non renseignée'}")
                if original.get("definition_clarte360"): st.write(f"**Définition Clarté360 :** {original.get('definition_clarte360')}")
            st.warning("Réexaminer cette valeur signifie reprendre sa définition et répondre de nouveau au questionnaire spécifique, même si vous ne changez rien. Vous pourrez annuler à tout moment avant la décision finale : la valeur restera alors inchangée.")
            c1,c2=st.columns(2)
            with c1:
                if st.button("← Annuler",use_container_width=True,key="m3_reex_back"):
                    st.session_state.active_module="accueil_modules"; st.rerun()
            with c2:
                if st.button("Commencer le réexamen",type="primary",use_container_width=True,key="m3_reex_start"):
                    original["en_reexamen"]=True
                    w=_new_value_work("reexamen"); w.update({"original_name":original["nom_final"],"nom_initial":original["nom_final"],"nom_final":original["nom_final"],"mode_decouverte":original.get("mode_decouverte") or "Par introspection","definition_personnelle":original.get("definition_personnelle",""),"definition_clarte360":original.get("definition_clarte360","")})
                    st.session_state.module3_queue=[w]; st.session_state.module3_index=0; st.session_state.current_value_work=w; st.rerun()
        return
    idx=int(st.session_state.module3_index); total=len(st.session_state.module3_queue); work=_module3_current_work()
    st.markdown(f"<div style='background:#EAF7F6;border:2px solid #0E7774;border-radius:12px;padding:.75rem 1rem;text-align:center;margin-bottom:1rem'><strong style='font-size:1.45rem;color:#0E7774'>Valeur {idx+1} / {total}</strong></div>",unsafe_allow_html=True)
    if work.get("source") in {"migration_v2137","module_4","recherche_guidee"}: _pending_value_summary(work)
    name=open_response_widget("Quelle valeur avez-vous identifiée ?",f"m3_name_{work['id']}",value=work.get("nom_initial",work.get("nom_final","")),height=70,allow_reformulation=False)
    if not name:
        c1,c2=st.columns(2)
        with c1:
            if st.button("Abandonner la valeur en cours",use_container_width=True,key=f"m3_abandon_empty_{work['id']}"):
                _abandon_current_module3_value(); st.rerun()
        with c2:
            if st.button("Arrêter la saisie des valeurs restantes",use_container_width=True,key=f"m3_stop_empty_{work['id']}"):
                _stop_module3_series(); st.rerun()
        return
    if not _looks_like_value_label(name):
        # La réponse technique du widget est effacée : aucune donnée métier n'est enregistrée.
        _clear_response_answer(f"m3_name_{work['id']}")
        st.error("Cette proposition ne semble pas correspondre directement au nom d’une valeur. Elle paraît plutôt exprimer une phrase, un constat, un ressenti, une aspiration ou un concept important pour vous. Aucune donnée n’a été enregistrée. Pour approfondir ce sujet, vous pourrez utiliser le module 4 « Rechercher une nouvelle valeur avec Clarté360 ». Saisissez ici une valeur déjà identifiée, sous la forme d’un mot ou d’une expression courte.")
        return
    canonical=_normalise_value_name(name)
    location,_existing=_active_value_location(canonical,exclude_work_id=work.get("id",""))
    # Un réexamen de sa propre valeur est autorisé ; toute autre duplication est bloquée.
    own_reexam=work.get("source")=="reexamen" and normalize(canonical)==normalize(_normalise_value_name(work.get("original_name","")))
    if location and not own_reexam:
        labels={"validee":"vos valeurs validées","a_examiner":"vos valeurs à examiner","a_revoir":"votre liste À revoir en séance"}
        st.error(f"La valeur **{canonical}** figure déjà dans {labels.get(location,'votre parcours')}. Elle ne peut pas être ajoutée une seconde fois. Aucune nouvelle valeur n’a été enregistrée.")
        if location=="validee": st.info("Vous pouvez la consulter ou la réexaminer depuis l’accueil du module 3.")
        return
    if canonical!=name.strip():
        st.info(f"Formulation normalisée : **{canonical}**")
    modes=["Par introspection","En observant mes réactions ou mes choix","À partir d’une situation vécue","À partir d’un événement marquant","Grâce à un exercice Clarté360","Avec l’aide de la recherche guidée Clarté360","Au cours d’une discussion","À travers une lecture","À travers un film ou une série","À travers un podcast ou une émission","En observant une personne que j’admire","Autre"]
    default_index=modes.index(work.get("mode_decouverte")) if work.get("mode_decouverte") in modes else 0
    mode=st.selectbox("Comment avez-vous identifié cette valeur ?",modes,index=default_index,key=f"m3_mode_{work['id']}",on_change=mark_user_activity,args=("mode_decouverte",))
    definition=open_response_widget("Que signifie cette valeur pour vous ?",f"m3_def_{work['id']}",value=work.get("definition_personnelle",""),height=110,dependency_scope="validation",value_name=canonical)
    if not definition: return
    work.update({"nom_initial":name,"nom_normalise":canonical,"nom_final":canonical,"mode_decouverte":mode,"definition_personnelle":definition})
    info=_referential_value_info(canonical); work["present_referentiel"]=bool(info); work["definition_clarte360"]=info.get("definition","")
    st.info(f"Terme retenu pour l’examen : **{canonical}**")
    if info: st.write(f"**Définition Clarté360 :** {info.get('definition','')}")
    analysis_key=f"m3_analysis_{work['id']}"
    analysis_sig_key=f"{analysis_key}_signature"
    current_clarification=str(work.get("clarification","") or "")
    analysis_signature=normalize(canonical+" | "+definition+" | "+current_clarification)
    if st.session_state.get(analysis_sig_key)!=analysis_signature:
        st.session_state[analysis_key]=analyse_concept_nature(canonical,definition,current_clarification)
        st.session_state[analysis_sig_key]=analysis_signature
    nature=st.session_state[analysis_key]
    decision=nature.get("decision",""); work["analyse"]=nature.get("explication",""); work["nature_decision"]=decision
    if decision=="formulation_non_valeur":
        st.error((nature.get("explication") or "Cette formulation ne correspond pas au nom d'une valeur.")+" Aucune donnée n’a été enregistrée. Vous pourrez approfondir ce sujet dans le module 4 « Rechercher une nouvelle valeur avec Clarté360 ».")
        return
    if decision=="clarification_requise":
        st.warning(nature.get("explication") or "Cette formulation mérite une clarification prudente.")
        question=nature.get("question") or "Quel principe durable souhaitez-vous respecter dans vos choix et comportements ?"
        clarification=open_response_widget(question,f"m3_clar_{work['id']}",value=current_clarification,height=100)
        if not clarification: return
        work["clarification"]=clarification
        if not work.get("clarifications") or work["clarifications"][-1].get("reponse")!=clarification:
            meta=deepcopy(st.session_state.answer_metadata.get(f"m3_clar_{work['id']}",{}))
            work.setdefault("clarifications",[]).append({"question":question,"reponse":clarification,"reponse_originale":meta.get("texte_brut") or meta.get("transcription") or clarification,"reformulation_proposee":meta.get("reformulation_proposee",""),"version_retenue":meta.get("version_officielle") or clarification,"date":now_iso(),"contexte":nature.get("explication","")})
        # Deuxième analyse obligatoire, sans possibilité de deuxième question.
        nature=analyse_concept_nature(canonical,definition,clarification)
        st.session_state[analysis_key]=nature; decision=nature.get("decision",""); work["analyse"]=nature.get("explication",""); work["nature_decision"]=decision
    if decision=="valeur_absente_possible":
        st.info((nature.get("explication") or "Cette valeur ne figure pas dans le référentiel Clarté360, mais elle peut constituer une valeur personnelle.")+" Vous pouvez poursuivre son examen ; son absence du catalogue n'est pas une erreur.")
    elif decision=="valeur_reconnue":
        st.success(nature.get("explication") or "Le mot et votre définition paraissent cohérents pour poursuivre l’examen comme valeur.")
    elif decision=="formulation_non_valeur":
        st.error((nature.get("explication") or "Cette formulation ne correspond pas à une valeur.")+" Aucune donnée n’a été enregistrée. Le module 4 pourra vous aider à approfondir ce sujet.")
        return
    conceptual=st.radio("Comment souhaitez-vous poursuivre ?",["Poursuivre l’examen comme valeur","Placer ce sujet À revoir en séance"],key=f"m3_concept_{work['id']}",on_change=mark_user_activity,args=("choix_orientation_valeur",))
    if conceptual.startswith("Placer"):
        if st.button("Ajouter à À revoir en séance",type="primary",key=f"m3_review_{work['id']}"):
            _add_review_item(work,"Doute sur la nature du concept après analyse et clarification"); business_trace("valeur_a_revoir_en_seance",canonical); _advance_module3(); st.rerun()
        return
    choice,final_def=_value_definition_choices(work,f"m3_{work['id']}")
    work["definition_finale"]=final_def
    st.markdown("### Questionnaire spécifique Clarté360")
    important=st.radio("Cette valeur est-elle importante pour vous dans plusieurs domaines ou situations ?",["Choisissez","Oui","Non"],key=f"m3_q1_{work['id']}",on_change=mark_user_activity,args=("questionnaire_valeur_q1",))
    very=st.radio("Seriez-vous durablement insatisfait si cette valeur était régulièrement bafouée ?",["Choisissez","Oui","Non"],key=f"m3_q2_{work['id']}",on_change=mark_user_activity,args=("questionnaire_valeur_q2",)) if important=="Oui" else "Non"
    fundamental=st.radio("Cette valeur influence-t-elle réellement vos choix, vos engagements ou vos refus importants ?",["Choisissez","Oui","Non"],key=f"m3_q3_{work['id']}",on_change=mark_user_activity,args=("questionnaire_valeur_q3",)) if very=="Oui" else "Non"
    if important=="Choisissez" or (important=="Oui" and very=="Choisissez") or (very=="Oui" and fundamental=="Choisissez"):
        return
    final_decision="validee" if important==very==fundamental=="Oui" else "non_retenue"
    st.write(f"Décision proposée selon vos réponses : **{'Valeur validée' if final_decision=='validee' else 'Valeur non retenue'}**")
    c1,c2=st.columns(2)
    with c1:
        if st.button("Abandonner la valeur en cours",use_container_width=True,key=f"m3_abandon_{work['id']}"):
            _abandon_current_module3_value(); st.rerun()
    with c2:
        if st.button("Confirmer cette décision",type="primary",key=f"m3_decide_{work['id']}",use_container_width=True):
            work["questionnaire"]={"importante":important=="Oui","tres_importante":very=="Oui","fondamentale":fundamental=="Oui"}; work["decision_finale"]=final_decision
            if final_decision=="validee":
                _upsert_central_value(canonical,final_def,"application" if work.get("source")=="reexamen" else work.get("source","manuel"),definition_clarte360=work.get("definition_clarte360",""),questionnaire=work["questionnaire"],work=work)
            else:
                _remove_value_from_active_lists(canonical,keep="non_retenue")
                st.session_state.rejected_values.append({"nom":canonical,"definition":final_def,"date":now_iso(),"source":work.get("source"),"analyse":work.get("analyse",""),"clarifications":deepcopy(work.get("clarifications",[])),"questionnaire":deepcopy(work.get("questionnaire",{}))})
            _advance_module3(); st.rerun()

def _advance_module3() -> None:
    idx=int(st.session_state.module3_index)+1
    st.session_state.module3_index=idx
    if idx<len(st.session_state.module3_queue): st.session_state.current_value_work=st.session_state.module3_queue[idx]
    else:
        st.session_state.module3_queue=[]; st.session_state.current_value_work={}; _set_module_status("module_3","termine","accueil")

def render_module_4_placeholder() -> None:
    st.title("Rechercher une nouvelle valeur avec Clarté360")
    st.info("La nouvelle recherche assistée sera intégrée dans la V2.1.3.9 après validation réelle de la V2.1.3.8. Cette version prépare déjà les listes, la reprise et le transfert vers le module 3.")
    if st.session_state.get("values_to_examine"):
        st.success(f"{len(st.session_state.values_to_examine)} valeur(s) sont déjà en attente d’examen dans le module 3.")
    if st.button("← Retour à l’accueil du parcours",use_container_width=True,key="m4_back_home"):
        st.session_state.active_module="accueil_modules"; st.rerun()

def render_module_5() -> None:
    st.title("Mes rapports")
    vals=validated_names()
    if not vals:
        st.warning("Un rapport provisoire sera disponible dès qu’au moins une valeur sera validée.")
        if st.button("← Retour à l’accueil du parcours",use_container_width=True,key="m5_back_empty"):
            st.session_state.active_module="accueil_modules"; st.rerun()
        return
    st.success(f"{len(vals)} valeur(s) validée(s) peuvent être restituées.")
    st.download_button("Télécharger le rapport provisoire",create_pdf("provisoire"),file_name=make_filename("RVC360_rapport_provisoire","pdf"),mime="application/pdf",use_container_width=True,on_click=lambda:st.session_state.report_history.append({"type":"provisoire","date":now_iso(),"valeurs":deepcopy(vals)}))
    st.download_button("Télécharger le JSON de reprise",payload_bytes(False),file_name=make_filename("RVC360_reprise","json"),mime="application/json",use_container_width=True)
    st.divider(); confirm=st.checkbox("Je confirme avoir terminé ma recherche et la validation de mes valeurs.")
    if st.button("Préparer le rapport définitif",type="primary",disabled=not confirm):
        st.session_state.exploration_complete=True; st.session_state.closure_decision="cloture_volontaire"; st.session_state.page="Cloture definitive"; st.rerun()
    if st.button("← Retour à l’accueil du parcours",use_container_width=True,key="m5_back_home"):
        st.session_state.active_module="accueil_modules"; st.rerun()

def render_business_v218() -> None:
    _ensure_migrated_state()
    if st.session_state.page=="Consultation finale" or st.session_state.get("final_mode"): render_final_consultation(); return
    if st.session_state.page=="Cloture definitive": render_closure_screen(); return
    display_header()
    if st.session_state.page=="Accueil reprise": render_resume_welcome(); return
    render_followup_panel()
    module=st.session_state.get("active_module","accueil_modules")
    {"accueil_modules":render_modules_home,"module_1":render_module_1,"module_2":render_module_2,"module_3":render_module_3,"module_4":render_module_4_placeholder,"module_5":render_module_5}.get(module,render_modules_home)()

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
        "reponses_structurees":st.session_state.get("answer_metadata",{}),
        "revision_donnees":st.session_state.get("data_revision",0),
        "sections_a_recalculer":st.session_state.get("stale_sections",[]),
        "evenements_dependances":st.session_state.get("dependency_events",[]),
        "derniere_revision_coherente":st.session_state.get("last_consistent_revision",0),
        "audit_cloture":st.session_state.get("closure_audit",{}),
        "schema_metier":"2.1.3.8E",
        "modules":deepcopy(st.session_state.get("module_states",{})),
        "module_actif":st.session_state.get("active_module","module_1"),
        "valeurs_validees_centrales":deepcopy(st.session_state.get("central_validated_values",[])),
        "valeurs_a_examiner":deepcopy(st.session_state.get("values_to_examine",[])),
        "a_revoir_en_seance":deepcopy(st.session_state.get("session_review_items",[])),
        "etat_panneau":{"ouvert":bool(st.session_state.get("followup_panel_open",True))},
        "historique_rapports":deepcopy(st.session_state.get("report_history",[])),
    }
    if not completed:
        # Copie complète et versionnée de l'état métier pour une reprise exacte de la page,
        # des files de validation, de la navigation et des dépendances.
        resume_state={k:deepcopy(st.session_state.get(k,v)) for k,v in default_business_state().items()}
        # Aucun audio binaire ni secret n'appartient à cet état.
        metier_common["etat_reprise"]=resume_state
        # Le JSON de reprise conserve aussi les champs historiques explicites pour compatibilité.
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
        "completed":completed,"acces_autorise":bool(st.session_state.get("access_authorized")),"exporte_le":now_iso(),
    }

def payload_bytes(completed=False)->bytes: return json.dumps(build_payload(completed),ensure_ascii=False,indent=2).encode("utf-8")
def make_filename(prefix="rvc360",ext="json"):
    b=st.session_state.get("beneficiaire",{}); return f"{prefix}_{sanitize_filename((b.get('prenom','')+'_'+b.get('nom','')).strip())}_{datetime.now().strftime('%Y%m%d_%H%M')}.{ext}"

def restore_from_progress(payload:dict):
    st.session_state.passation_root_id=payload.get("passation_root_id",str(uuid.uuid4())); st.session_state.session_id=str(uuid.uuid4()); st.session_state.passation_id=payload.get("passation_id") or f"CL360-RVC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"; st.session_state.beneficiaire=payload.get("beneficiaire",{}); st.session_state.rgpd_acceptance=payload.get("rgpd_acceptance",{}); st.session_state.access_history=payload.get("access_history",{}); st.session_state.session_history=deepcopy(payload.get("sessions",[])); m=payload.get("metier",{})
    resume_state=m.get("etat_reprise",m)
    for k,v in default_business_state().items(): st.session_state[k]=deepcopy(resume_state.get(k,m.get(k,v)))
    if m.get("modules"): st.session_state.module_states=deepcopy(m.get("modules"))
    if m.get("module_actif"): st.session_state.active_module=m.get("module_actif")
    if m.get("valeurs_validees_centrales"): st.session_state.central_validated_values=deepcopy(m.get("valeurs_validees_centrales"))
    if m.get("valeurs_a_examiner"): st.session_state.values_to_examine=deepcopy(m.get("valeurs_a_examiner"))
    if m.get("a_revoir_en_seance"): st.session_state.session_review_items=deepcopy(m.get("a_revoir_en_seance"))
    if m.get("etat_panneau"): st.session_state.followup_panel_open=bool(m.get("etat_panneau",{}).get("ouvert",True))
    if m.get("historique_rapports"): st.session_state.report_history=deepcopy(m.get("historique_rapports"))
    repair_all_answer_metadata()
    # Compatibilité avec les JSON 1.3.0 et antérieurs : reconstruire les valeurs application déjà fondamentales.
    if not st.session_state.get("validated_app_values"):
        st.session_state.validated_app_values=[
            n for n,val in st.session_state.get("validation",{}).items()
            if val.get("fondamentale") and n not in st.session_state.get("existing_values",[])
        ]
    authorized=bool(payload.get("acces_autorise") or payload.get("access_authorized") or (payload.get("access_history") or {}).get("autorise") or (payload.get("rgpd_acceptance") and payload.get("passation_id")))
    if not authorized:
        raise ValueError("Ce fichier ne contient pas de preuve d’autorisation d’accès Clarté360.")
    st.session_state.test_started=True; st.session_state.code_verified_at=now_iso(); st.session_state.access_authorized=True
    synchronize_value_state()
    _ensure_migrated_state()
    if not m.get("module_actif"):
        st.session_state.active_module="accueil_modules"
    if payload.get("statut")=="parcours_cloture" or payload.get("completed") is True and payload.get("type_export")=="final":
        st.session_state.final_mode=True; st.session_state.final_payload=deepcopy(payload); st.session_state.page="Consultation finale"
    else:
        st.session_state.resume_target_page=st.session_state.page; st.session_state.resume_welcome_pending=True; st.session_state.page="Accueil reprise"
    init_runtime_session("reprise_json"); business_trace("reprise_json")

def create_pdf(report_type: str="provisoire")->bytes:
    from reportlab.platypus import Image, Table, TableStyle, KeepTogether
    buffer=BytesIO(); styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Teal",parent=styles["Heading1"],textColor=colors.HexColor(OFFICIAL_TEAL),spaceAfter=12))
    styles.add(ParagraphStyle(name="Teal2",parent=styles["Heading2"],textColor=colors.HexColor(OFFICIAL_TEAL),spaceBefore=10,spaceAfter=6))
    styles.add(ParagraphStyle(name="Small",parent=styles["Normal"],fontSize=8,leading=10,textColor=colors.HexColor("#666666")))
    styles.add(ParagraphStyle(name="Cover",parent=styles["Title"],fontSize=24,leading=29,textColor=colors.HexColor(OFFICIAL_TEAL),alignment=1,spaceAfter=18))
    def footer(canvas,doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#D7EAEA")); canvas.line(1.5*cm,1.05*cm,A4[0]-1.5*cm,1.05*cm); canvas.setFont("Helvetica",7.5); canvas.setFillColor(colors.HexColor("#666666")); canvas.drawString(1.5*cm,.65*cm,"Clarté360 - 60 rue François 1er - 75008 Paris - Document confidentiel"); canvas.drawRightString(A4[0]-1.5*cm,.65*cm,f"Page {doc.page}"); canvas.restoreState()
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=1.7*cm,leftMargin=1.7*cm,topMargin=1.5*cm,bottomMargin=1.4*cm,title="Rapport RVC360 - Recherche de mes valeurs")
    b=st.session_state.get("beneficiaire",{}); values=[v for v in st.session_state.get("central_validated_values",[]) if v.get("statut")=="validee" and not v.get("en_reexamen")]
    story=[]
    if LOGO_PATH.exists(): story += [Spacer(1,1.2*cm),Image(str(LOGO_PATH),width=3.2*cm,height=3.2*cm),Spacer(1,.5*cm)]
    title_type="provisoire" if report_type=="provisoire" else "définitif"
    story += [Paragraph("CLARTÉ360",styles["Cover"]),Paragraph(f"Recherche de mes valeurs - Rapport {title_type}",styles["Cover"]),Spacer(1,.5*cm),Paragraph(f"<b>Bénéficiaire :</b> {html.escape((b.get('prenom','')+' '+b.get('nom','')).strip())}",styles["Normal"]),Paragraph(f"<b>Date :</b> {datetime.now().strftime('%d/%m/%Y')}",styles["Normal"]),Paragraph(f"<b>Application :</b> {APP_VERSION} - <b>RVC360 :</b> {RVC360_VERSION} - <b>Framework :</b> {FRAMEWORK_VERSION}",styles["Normal"]),Spacer(1,1.2*cm),Paragraph("Ce document restitue uniquement les valeurs actuellement validées. Il ne constitue ni un diagnostic, ni une analyse de personnalité, ni une décision d’orientation.",styles["Italic"]),PageBreak()]
    profile=st.session_state.get("beneficiary_profile",{})
    story += [Paragraph("1. Présentation du bénéficiaire",styles["Teal"])]
    presentation=profile.get("presentation_libre","") or "Aucune présentation enregistrée."
    story += [Paragraph(html.escape(presentation),styles["Normal"])]
    if profile.get("objectif_demarche"): story += [Paragraph(f"<b>Attente exprimée :</b> {html.escape(profile['objectif_demarche'])}",styles["Normal"])]
    story += [Paragraph("2. Synthèse",styles["Teal"])]
    data=[["Élément","État"],["Valeurs validées",str(len(values))],["Type de rapport",title_type.capitalize()],["Date de génération",datetime.now().strftime('%d/%m/%Y %H:%M')]]
    t=Table(data,colWidths=[6*cm,10*cm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(LIGHT_TEAL)),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#CFE6E6')),('VALIGN',(0,0),(-1,-1),'TOP')])); story += [t,Spacer(1,10)]
    accompagnateur=[v for v in values if v.get("source")=="accompagnateur"]
    application=[v for v in values if v.get("source")!="accompagnateur"]
    for number,title,items in [(3,"Valeurs validées avec l’accompagnateur",accompagnateur),(4,"Valeurs découvertes et validées dans Clarté360",application)]:
        story += [Paragraph(f"{number}. {title}",styles["Teal"])]
        if not items: story += [Paragraph("Aucune.",styles["Normal"])]
        for v in items:
            name=_normalise_value_name(v.get("nom_final") or v.get("nom") or "Valeur")
            personal=v.get("definition_personnelle") or "Non renseignée"
            official=v.get("definition_clarte360") or value_info(name).get("definition","")
            source="Validée avec l’accompagnateur" if v.get("source")=="accompagnateur" else (v.get("mode_decouverte") or v.get("source") or "Clarté360")
            q=v.get("questionnaire") or {}
            q_result="Questionnaire spécifique validé" if q.get("fondamentale") else "Validation issue du prérequis" if v.get("source")=="accompagnateur" else "Validée"
            block=[Paragraph(html.escape(name),styles["Teal2"]),Paragraph(f"<b>Statut :</b> Validée",styles["Normal"]),Paragraph(f"<b>Source / mode de découverte :</b> {html.escape(str(source))}",styles["Normal"]),Paragraph(f"<b>Définition personnelle retenue :</b> {html.escape(personal)}",styles["Normal"])]
            if official: block.append(Paragraph(f"<b>Définition Clarté360 :</b> {html.escape(official)}",styles["Normal"]))
            block += [Paragraph(f"<b>Résultat :</b> {html.escape(q_result)}",styles["Normal"]),Paragraph(f"<b>Date de validation :</b> {html.escape(str(v.get('validee_le','') or 'Non renseignée'))}",styles["Normal"])]
            story += [KeepTogether(block),Spacer(1,6)]
    story += [Paragraph("5. Liste centrale des valeurs validées",styles["Teal"])]
    if values:
        for i,v in enumerate(values,1): story += [Paragraph(f"{i}. <b>{html.escape(_normalise_value_name(v.get('nom_final') or ''))}</b> - {html.escape(v.get('definition_personnelle') or '')}",styles["Normal"])]
    else: story += [Paragraph("Aucune valeur validée.",styles["Normal"])]
    story += [Paragraph("6. Suite du parcours Clarté360",styles["Teal"]),Paragraph("Cette liste centrale peut servir de base à la Boussole des valeurs professionnelles pour hiérarchiser les valeurs dans le contexte professionnel, ou à la Roue des valeurs pour évaluer leur niveau de satisfaction et leur cohérence dans la vie actuelle.",styles["Normal"]),Paragraph("7. Conclusion",styles["Teal"]),Paragraph("Les valeurs présentées sont uniquement celles actuellement validées. Les valeurs à examiner, non retenues ou à revoir en séance ne sont pas présentées comme des valeurs du bénéficiaire.",styles["Normal"]),Spacer(1,12),Paragraph("Document confidentiel - diffusion réservée au bénéficiaire et, avec son accord, à son accompagnateur.",styles["Small"])]
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
    return PAGE_LABELS.get(page,str(page))

def sidebar_progress():
    in_app=st.session_state.get("test_started",False)
    if LOGO_PATH.exists(): st.sidebar.image(str(LOGO_PATH),width=85)
    st.sidebar.markdown("### Clarté360")
    if in_app:
        _ensure_migrated_state()
        render_module_menu()
        st.sidebar.markdown("---")
        st.sidebar.download_button("💾 Sauvegarder mon travail (JSON)",data=payload_bytes(False),file_name=make_filename("rvc360_sauvegarde","json"),mime="application/json",use_container_width=True,on_click=lambda:record_save_event("sauvegarde_manuelle"))
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
    st.session_state.voice_enabled=st.toggle("🔊 Lecture vocale",value=bool(st.session_state.get("voice_enabled",True)),key="global_voice_toggle")
    visited=[p for p in PAGE_ORDER if p in st.session_state.get("navigation_history",[]) or p==st.session_state.get("page")]
    if visited:
        selected=st.selectbox("Accéder à une étape déjà réalisée",visited,index=max(0,visited.index(st.session_state.page) if st.session_state.page in visited else 0),format_func=lambda p:PAGE_LABELS.get(p,p),key="direct_navigation")
        if selected!=st.session_state.page and st.button("Ouvrir cette étape",use_container_width=True):
            st.session_state.page=selected; st.rerun()


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
            if not result or not str(result.get("question_suivante","")).strip():
                raise ValueError("Réponse d’analyse incomplète")
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
    previous_hyp=(st.session_state.get("last_presented_hypotheses") or [""])[0] if st.session_state.get("last_presented_hypotheses") else ""
    if previous_hyp and presented and normalize(previous_hyp)!=normalize(presented[0]):
        st.session_state.reasoning_evolution.append({"date":now_iso(),"premiere_hypothese":previous_hyp,"hypothese_revisee":presented[0],"explication":"Vos précisions ont permis d’affiner progressivement la compréhension de ce qui compte réellement pour vous."})
    if presented: st.session_state.last_presented_hypotheses=presented
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



PAGE_ORDER=["Accueil","Prerequis","Presentation beneficiaire","Presentation assistant","Valeurs interseances","Decision exploration","Exploration IA","Mots a examiner","Validation","Controle completude","Resultats"]
PAGE_LABELS={"Accueil":"Accueil","Prerequis":"Prérequis","Presentation beneficiaire":"Faisons connaissance","Presentation assistant":"Présentation de l’assistant","Valeurs interseances":"Découvertes personnelles","Decision exploration":"Choix de l’exploration","Exploration IA":"Recherche guidée","Mots a examiner":"Hypothèses","Validation":"Validation HEC","Controle completude":"Contrôle de complétude","Resultats":"Résultats"}

def navigation_controls():
    page=st.session_state.page
    if page not in PAGE_ORDER or page=="Accueil": return
    history=st.session_state.setdefault("navigation_history",[])
    if page not in history: history.append(page)
    accessible=[p for p in PAGE_ORDER if p in history or p==page]
    idx=accessible.index(page)
    st.caption("Vous pouvez revenir sur toute étape déjà ouverte. Une modification recalcule ou invalide automatiquement les éléments dépendants.")
    c1,c2=st.columns(2)
    with c1:
        if idx>0 and st.button("← Étape précédente",key=f"nav_prev_{page}",use_container_width=True): st.session_state.page=accessible[idx-1]; st.rerun()
    with c2:
        if idx<len(accessible)-1 and st.button("Étape suivante →",key=f"nav_next_{page}",use_container_width=True): st.session_state.page=accessible[idx+1]; st.rerun()
    if st.session_state.get("stale_sections"):
        st.warning("Une modification antérieure a rendu certaines restitutions obsolètes. Le contrôle de complétude doit être refait avant la clôture.")

def access_gate_screen():
    display_header(); st.title("Bienvenue sur Clarté360")
    text="Cette application est réservée aux bénéficiaires accompagnés. Merci de saisir le code de déblocage communiqué par votre accompagnateur."
    st.markdown(f'<div class="clarte-box">{text}</div>',unsafe_allow_html=True); speak_button(text,"access_gate")
    code=st.text_input("Code de déblocage",type="password")
    expected=str(get_secret("security","activation_code",os.environ.get("CLARTE360_ACTIVATION_CODE","")) or "")
    if st.button("J’ai déjà un fichier JSON de reprise ou final",use_container_width=True): st.session_state.welcome_choice="import"; st.rerun()
    if not expected: st.error("Le code de déblocage n’est pas configuré dans les paramètres sécurisés."); return
    if st.button("Débloquer l’application",type="primary",disabled=not code):
        if str(code).strip()==expected:
            st.session_state.access_authorized=True; st.session_state.code_verified_at=now_iso(); st.success("Accès autorisé."); st.rerun()
        else: st.error("Code incorrect.")

def build_final_payload()->dict[str,Any]:
    synchronize_value_state()
    vals=[]
    for n in validated_names():
        rec=deepcopy(st.session_state.value_records.get(n,{})); info=value_info(n)
        vals.append({"nom":n,"famille":info.get("famille",""),"definition_personnelle":st.session_state.personal_defs.get(n,rec.get("definition_personnelle","")),"origine":rec.get("source","accompagnateur" if n in st.session_state.existing_values else "exploration_application"),"situations_significatives":rec.get("situations_associees",[]),"date_decouverte":rec.get("date_decouverte","")})
    profile=deepcopy(st.session_state.get("beneficiary_profile",{}))
    summary_text=f"Le bénéficiaire a validé {len(vals)} valeur(s) fondamentale(s) : {', '.join(v['nom'] for v in vals) if vals else 'aucune valeur validée'}."
    payload={"application":APP_FULL_NAME,"version":APP_VERSION,"framework_version":FRAMEWORK_VERSION,"rvc360_version":RVC360_VERSION,"type_export":"final","statut":"parcours_cloture","completed":True,"passation_id":st.session_state.get("passation_id"),"identite":deepcopy(st.session_state.get("beneficiaire",{})),"date_debut":st.session_state.get("started_at"),"date_cloture":now_iso(),"contexte_et_attente":profile,"valeurs_fondamentales":vals,"domaines_explores":list(st.session_state.get("domains_explored",{}).keys()),"appreciation_finale":deepcopy(st.session_state.get("completion_check",{})),"elements_a_reprendre_avec_accompagnateur":st.session_state.get("completion_check",{}).get("angles_a_reprendre",""),"synthese_finale":{"texte":summary_text},"rapport_regenerable":True,"acces_autorise":True,"transmission":deepcopy(st.session_state.get("final_transmission_status",{}))}
    return payload

def render_final_consultation():
    display_header(); st.title("Consultation du parcours finalisé")
    final_info="Ce parcours a été clôturé définitivement. Il est disponible en lecture seule ; aucun appel à l’intelligence artificielle ne sera effectué."
    speak_button(final_info,"listen_final_mode"); st.success(final_info)
    payload=st.session_state.get("final_payload") or build_final_payload()
    vals=payload.get("valeurs_fondamentales",[])
    st.subheader("Synthèse finale")
    st.write((payload.get("synthese_finale") or {}).get("texte",""))
    for i,v in enumerate(vals,1): st.markdown(f"### {i}. {v.get('nom','')}"); st.caption(f"Origine : {v.get('origine','')}"); st.write(v.get("definition_personnelle",''))
    st.download_button("Télécharger à nouveau le rapport PDF",final_pdf_from_payload(payload),file_name=make_filename("RVC360_rapport_final","pdf"),mime="application/pdf",use_container_width=True)
    st.download_button("Télécharger une copie du JSON final",json.dumps(payload,ensure_ascii=False,indent=2).encode(),file_name=make_filename("RVC360_final","json"),mime="application/json",use_container_width=True)
    st.divider(); st.subheader("Transmission à l’accompagnateur")
    if st.button("Transmettre ce JSON final à mon accompagnateur",use_container_width=True):
        ident=payload.get("identite",{}); body=f"Le bénéficiaire {ident.get('prenom','')} {ident.get('nom','')} demande la transmission de son JSON final Clarté360."
        ok,msg=send_email("Clarté360 - JSON final du bénéficiaire",body,attachments=[(make_filename("RVC360_final","json"),json.dumps(payload,ensure_ascii=False,indent=2).encode(),"application/json")])
        if ok: st.success("Votre JSON final a bien été transmis à votre accompagnateur.")
        else: st.error(msg)

def _resume_can_offer_new_values() -> bool:
    """Ne propose les nouvelles valeurs que si cette étape avait déjà été atteinte auparavant."""
    target=str(st.session_state.get("resume_target_page") or "")
    visited=set(st.session_state.get("navigation_history",[]) or [])
    if "Valeurs interseances" in visited:
        return True
    try:
        return target in PAGE_ORDER and PAGE_ORDER.index(target) >= PAGE_ORDER.index("Valeurs interseances")
    except ValueError:
        return False


def render_resume_welcome():
    vals=validated_names()
    prenom=st.session_state.get("beneficiary_profile",{}).get("prenom_usage") or st.session_state.get("beneficiaire",{}).get("prenom","")
    target=st.session_state.get("resume_target_page") or ""
    target_label=PAGE_LABELS.get(target,target) if target else "votre parcours"
    pending=st.session_state.get("values_to_examine",[])
    summary=(f"Bonjour {prenom}, je suis heureux de vous retrouver. Votre travail a bien été retrouvé. Vous vous étiez arrêté à l’étape « {target_label} ». {len(vals)} valeur(s) étaient déjà validée(s)" + (f" et {len(pending)} valeur(s) restent à examiner." if pending else "."))
    st.markdown(f'<div class="clarte-box">{summary}</div>',unsafe_allow_html=True)
    speak_button(summary,"resume_welcome")
    st.markdown("### Que souhaitez-vous faire maintenant ?")
    target_module={"Prerequis":"module_1","Presentation beneficiaire":"module_2","Presentation assistant":"module_2","Valeurs interseances":"module_3","Validation":"module_3","Mots a examiner":"module_3","Exploration IA":"module_4","Decision exploration":"module_4","Controle completude":"module_5","Resultats":"module_5"}.get(target,"accueil_modules")
    # Une valeur inachevée est prioritaire sur l'ancienne page générique d'exploration.
    if pending:
        target_module="module_3"
    if target_module=="module_1" and _module_state("module_1").get("status")=="termine": target_module="accueil_modules"
    if target_module!="accueil_modules" and st.button("Reprendre le travail interrompu",type="primary",use_container_width=True):
        st.session_state.resume_welcome_pending=False; st.session_state.active_module=target_module; st.session_state.page="Modules"; st.rerun()
    if st.button("Choisir librement un module",use_container_width=True):
        st.session_state.resume_welcome_pending=False; st.session_state.active_module="accueil_modules"; st.session_state.page="Modules"; st.rerun()
    st.divider()
    st.caption("Vous pouvez aussi ouvrir directement l’un des cinq modules depuis le menu permanent à gauche.")
    if st.button("J’ai découvert une nouvelle valeur depuis ma dernière utilisation",use_container_width=True):
        st.session_state.resume_welcome_pending=False; st.session_state.active_module="module_3"; st.session_state.page="Modules"; st.rerun()

def render_closure_screen():
    display_header(); st.title("Clôture définitive du parcours")
    message="Après cette clôture, vous ne pourrez plus modifier vos réponses ni poursuivre l’exploration à partir du JSON final. Vous pourrez consulter les résultats et réimprimer le rapport."
    st.warning(message); speak_button(message,"closure_warning")
    st.download_button("Sauvegarder une dernière copie de mon JSON de travail",payload_bytes(False),file_name=make_filename("RVC360_travail_avant_cloture","json"),mime="application/json")
    preview=build_final_payload(); pdf=final_pdf_from_payload(preview)
    st.subheader("Documents finaux obligatoires")
    st.download_button("Télécharger mon rapport final PDF",pdf,file_name=make_filename("RVC360_rapport_final","pdf"),mime="application/pdf",use_container_width=True,on_click=lambda:st.session_state.update(final_pdf_download_offered=True))
    st.download_button("Télécharger mon JSON final",json.dumps(preview,ensure_ascii=False,indent=2).encode(),file_name=make_filename("RVC360_final","json"),mime="application/json",use_container_width=True,on_click=lambda:st.session_state.update(final_json_download_offered=True))
    docs_info="Conservez soigneusement ces deux documents. Le rapport présente vos résultats. Le JSON final permet leur consultation et la réimpression du rapport, sans reprendre les questionnaires."
    speak_button(docs_info,"listen_final_docs"); st.info(docs_info)
    choice=st.radio("Souhaitez-vous transmettre votre JSON final à votre accompagnateur ?",["Oui, transmettre mon JSON final automatiquement","Je préfère le lui remettre moi-même"],key="final_send_choice")
    if choice.startswith("Oui"):
        st.caption("Votre consentement porte uniquement sur l’envoi automatique. Votre accompagnateur a besoin des résultats validés pour assurer la continuité du bilan.")
        include_pdf=st.checkbox("Joindre également le rapport PDF final (facultatif).")
        consent=st.checkbox("J’autorise l’envoi automatique de mon JSON final épuré à mon accompagnateur.")
        if consent and st.button("Transmettre maintenant",type="primary"):
            ben=st.session_state.get("beneficiaire",{}); consultant=ben.get("consultant","")
            body=f"Le bénéficiaire {ben.get('prenom','')} {ben.get('nom','')} a demandé la transmission de son JSON final Clarté360 le {now_iso()}."
            attachments=[(make_filename("RVC360_final","json"),json.dumps(preview,ensure_ascii=False,indent=2).encode(),"application/json")]
            if include_pdf: attachments.append((make_filename("RVC360_rapport_final","pdf"),pdf,"application/pdf"))
            ok,msg=send_email("Clarté360 - JSON final du bénéficiaire",body,attachments=attachments)
            st.session_state.final_transmission_status={"choix":"envoi_automatique","date":now_iso(),"resultat":"ok" if ok else "echec","detail":msg}
            if ok: st.success("Votre JSON final a bien été transmis à votre accompagnateur.")
            else: st.error(f"L’envoi automatique n’a pas abouti : {msg}. Téléchargez le fichier pour le transmettre vous-même.")
    else: st.session_state.final_transmission_status={"choix":"remise_manuelle","date":now_iso()}
    confirm1=st.checkbox("Je comprends que la clôture est irréversible.")
    confirm2=st.checkbox("Je confirme vouloir figer mes résultats.")
    ready=bool(st.session_state.get("final_pdf_download_offered") and st.session_state.get("final_json_download_offered"))
    if not ready: st.caption("Les deux documents finaux doivent avoir été proposés avant la clôture.")
    if confirm1 and confirm2 and ready and st.button("Clôturer définitivement mon parcours",type="primary"):
        ok,issues=closure_consistency_audit()
        if not ok:
            st.error("La clôture est impossible tant que les incohérences suivantes subsistent :")
            for issue in issues: st.write("• "+issue)
            return
        st.session_state.final_payload=build_final_payload(); st.session_state.final_mode=True; st.session_state.page="Consultation finale"; st.session_state.exploration_complete=True; close_runtime_session("cloture_definitive"); business_trace("cloture_definitive"); st.rerun()

def render_business():
    page=st.session_state.page
    if page=="Accueil reprise": render_resume_welcome(); return
    if page=="Consultation finale" or st.session_state.get("final_mode"): render_final_consultation(); return
    if page=="Cloture definitive": render_closure_screen(); return
    display_header(); values_side_panel(); navigation_controls()
    if page=="Accueil":
        speak_button("Objectif unique : rechercher et valider vos valeurs fondamentales. Cette application prolonge l’exercice inter-séance engagé avec votre accompagnateur. Elle ne fait ni coaching, ni diagnostic, ni orientation.","listen_home_intro")
        st.markdown('<div class="clarte-box"><b>Objectif unique : rechercher et valider vos valeurs fondamentales.</b><br>Cette application prolonge l’exercice inter-séance engagé avec votre accompagnateur. Elle ne fait ni coaching, ni diagnostic, ni orientation.</div>',unsafe_allow_html=True)
        value_reminder()
        if not CATALOGUE: st.error("Le référentiel RVC360 n'a pas pu être chargé.")
        if ai_ready(): st.success("Moteur IA RVC360 configuré et disponible.")
        else: st.error("Le moteur IA RVC360 n'est pas configuré.")
        if st.button("Commencer",type="primary",disabled=not(CATALOGUE and ai_ready())):
            st.session_state.page="Prerequis"; business_trace("debut_metier"); st.rerun()

    elif page=="Prerequis":
        st.title("Prérequis obligatoire")
        prereq_warning="La première valeur doit avoir été recherchée et validée avec votre accompagnateur avant d'utiliser cette application."
        speak_button(prereq_warning,"listen_prereq_warning"); st.warning(prereq_warning)
        value_reminder()
        confirmed=st.radio("Avez-vous déjà identifié et validé au moins une valeur avec votre accompagnateur ?",["Choisissez une réponse","Oui","Non"],index=0,key="prereq_yesno")
        if confirmed=="Non":
            st.error("Le parcours ne peut pas commencer. Reprenez d'abord cette première étape avec votre accompagnateur.")
            return
        if confirmed!="Oui": return
        st.session_state.prerequisite_confirmed=True
        prereq_info="Votre accompagnateur a pu valider avec vous une ou plusieurs valeurs. Indiquez-les toutes, une par champ."
        speak_button(prereq_info,"listen_prereq_info"); st.info(prereq_info)
        count=int(st.number_input("Combien de valeurs avez-vous déjà identifiées et validées avec votre accompagnateur ?",min_value=1,max_value=15,value=int(st.session_state.get("prerequisite_count",1)),step=1))
        st.session_state.prerequisite_count=count
        entries=[]
        for i in range(count):
            val=open_response_widget(f"Valeur déjà identifiée n°{i+1}",f"prereq_free_{i}",height=70,allow_reformulation=False,dependency_scope="prerequisites")
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
                if agree.startswith("Non"): own=open_response_widget("Votre définition personnelle",f"owndef_{i}",height=110,dependency_scope="prerequisites",value_name=name)
                if agree!="Choisissez" and (agree=="Oui" or own.strip()): confirmed_values.append((name,own.strip() or info.get("definition",""),False))
            elif props:
                st.write("Votre formulation semble proche de plusieurs noms de valeurs. Rien n'est imposé.")
                choice=st.radio("Quel nom correspond le mieux à ce que vous avez validé avec votre accompagnateur ?",["Aucune de ces propositions"]+props,key=f"prop_{i}")
                if choice!="Aucune de ces propositions":
                    info=value_info(choice); st.write(info.get("definition","")); own=open_response_widget("Conservez cette définition ou écrivez la vôtre",f"propdef_{i}",value=info.get("definition",""),height=110,dependency_scope="prerequisites",value_name=choice)
                    if own.strip(): confirmed_values.append((choice,own.strip(),False))
                else:
                    custom_name=open_response_widget("Nom de votre valeur",f"customname_{i}",value=item['raw'],height=70,allow_reformulation=False,dependency_scope="prerequisites")
                    custom_def=open_response_widget("Que signifie cette valeur pour vous ?",f"customdef_{i}",height=110,dependency_scope="prerequisites",value_name=custom_name.strip())
                    if custom_name.strip() and custom_def.strip(): confirmed_values.append((custom_name.strip(),custom_def.strip(),True))
            else:
                st.write("Cette formulation n'existe pas telle quelle dans le référentiel. Elle peut néanmoins être retenue pour vous.")
                custom_name=open_response_widget("Nom de votre valeur",f"newname_{i}",value=item['raw'],height=70,allow_reformulation=False,dependency_scope="prerequisites")
                custom_def=open_response_widget("Que signifie cette valeur pour vous ?",f"newdef_{i}",height=110,dependency_scope="prerequisites",value_name=custom_name.strip())
                if custom_name.strip() and custom_def.strip(): confirmed_values.append((custom_name.strip(),custom_def.strip(),True))
        pending_count=len(st.session_state.get("prerequisite_pending",[]))
        if pending_count and st.button("Valider toutes mes valeurs déjà identifiées",type="primary",disabled=len(confirmed_values)!=pending_count):
            previous_values=list(st.session_state.get("existing_values",[]))
            new_names=[x[0] for x in confirmed_values]
            if previous_values and previous_values!=new_names: invalidate_dependencies("prerequisites",reason="valeurs accompagnateur modifiées")
            for removed in set(previous_values)-set(new_names):
                st.session_state.validation.pop(removed,None); st.session_state.personal_defs.pop(removed,None); st.session_state.value_records.pop(removed,None); st.session_state.hypothesis_status.pop(removed,None)
            st.session_state.existing_values=[]
            for name,definition,is_custom in confirmed_values:
                st.session_state.existing_values.append(name); st.session_state.personal_defs[name]=definition
                st.session_state.validation[name]={"importante":True,"tres_importante":True,"fondamentale":True,"origine_validation":"accompagnateur"}
                if is_custom:
                    st.session_state.custom_values[name]={"definition":definition,"famille":"Valeur personnelle","notified":False}
            st.session_state.existing_values=list(dict.fromkeys(st.session_state.existing_values))
            for name,definition,is_custom in confirmed_values:
                register_value_record(name,"accompagnateur","validee",definition,certainty=100)
            synchronize_value_state(); business_trace("prerequis_valide",", ".join(st.session_state.existing_values)); st.session_state.page="Presentation beneficiaire"; st.rerun()

    elif page=="Presentation beneficiaire":
        st.title("Faisons connaissance")
        intro_profile="Vous vous êtes déjà présenté à votre accompagnateur. Accepteriez-vous de m’en dire un peu sur vous afin que je puisse mieux vous accompagner dans cette recherche de valeurs ? Vous restez libre de ne pas répondre à une question."
        speak_button(intro_profile,"listen_profile_intro")
        st.markdown('<div class="clarte-box">Vous vous êtes déjà présenté à votre accompagnateur. Accepteriez-vous de m’en dire un peu sur vous afin que je puisse mieux vous accompagner dans cette recherche de valeurs ? Vous restez libre de ne pas répondre à une question.</div>',unsafe_allow_html=True)
        profile=st.session_state.get("beneficiary_profile",{})
        preferred=open_response_widget("Comment souhaitez-vous que je vous appelle ?","profile_preferred_name",value=profile.get("prenom_usage",st.session_state.beneficiaire.get("prenom","")),height=70,allow_reformulation=False)
        intro_parts=[]
        for fld,label in [("situation_actuelle","Quelle est votre situation actuelle ?\n(Si vous le voulez bien, vous pouvez me préciser rapidement votre âge, votre situation familiale, votre métier et vos principales activités.)"),("parcours","Quels éléments de votre parcours vous semblent importants ?"),("activites_importantes","Quelles personnes ou activités occupent une place importante ?"),("passions","Quelles sont vos passions ou centres d’intérêt ?"),("projets","Quels projets ou changements envisagez-vous ?")]:
            intro_parts.append((fld,open_response_widget(label,f"profile_{fld}",value=profile.get(fld,""),height=90,dependency_scope="profile")))
        goal_label="Qu’aimeriez-vous mieux comprendre ou vérifier grâce à cette recherche de valeurs ?"
        goal=open_response_widget(goal_label,"profile_objectif",value=profile.get("objectif_demarche",""),height=110,dependency_scope="profile")
        intro="\n\n".join(v.strip() for _,v in intro_parts if v.strip())
        st.caption("Il ne s’agit pas d’un formulaire administratif. Quelques éléments sincères suffisent.")
        if st.button("Poursuivre",type="primary",disabled=not intro.strip()):
            new_profile={"prenom_usage":preferred.strip(),"presentation_libre":intro.strip(),"objectif_demarche":goal.strip(),"date":now_iso(),**{k:v.strip() for k,v in intro_parts}}
            old_profile=st.session_state.get("beneficiary_profile",{})
            meaningful_old={k:v for k,v in old_profile.items() if k not in ("prenom_usage","date")}
            meaningful_new={k:v for k,v in new_profile.items() if k not in ("prenom_usage","date")}
            if meaningful_old and meaningful_old!=meaningful_new: invalidate_dependencies("profile",reason="questionnaire bénéficiaire modifié")
            st.session_state.beneficiary_profile=new_profile
            st.session_state.profile_complete=True
            business_trace("presentation_beneficiaire")
            st.session_state.page="Presentation assistant"; st.rerun()

    elif page=="Presentation assistant":
        st.title("Comment je vais vous accompagner")
        text=("Je suis l’assistant Clarté360 dédié à la recherche de vos valeurs. Je complète le travail réalisé avec votre accompagnateur, sans le remplacer. "
              "Je vais alterner les sujets pour mieux comprendre ce qui vous pousse régulièrement à agir ou à réagir. Je pourrai proposer des hypothèses, mais je peux me tromper et vous seul pourrez valider une valeur. "
              "Une valeur solide se retrouve généralement dans plusieurs situations ou domaines de vie. L’objectif indicatif est souvent d’en identifier environ 8 à 12, mais ce n’est jamais un quota : votre liste peut être plus courte ou plus longue.")
        st.markdown(f'<div class="clarte-box">{text}</div>',unsafe_allow_html=True)
        speak_button(text,"assistant_intro")
        info_voice="À chaque question ouverte, vous pourrez répondre librement au clavier ou à la voix, et alterner à tout moment. Pour une réponse orale, vous comparerez la transcription initiale et une proposition Clarté360 rédigée en français écrit. La version choisie doit être validée avant d’être enregistrée."
        speak_button(info_voice,"listen_voice_info")
        st.info(info_voice)
        if st.button("J’ai compris, continuer",type="primary"):
            st.session_state.assistant_presented=True; st.session_state.interaction_preferences={"mode":"clavier_et_voix_permanents"}; business_trace("presentation_assistant"); st.session_state.page="Valeurs interseances"; st.rerun()

    elif page=="Valeurs interseances":
        st.title("Valeurs découvertes depuis votre dernière séance")
        answer=st.radio("Depuis votre dernière séance, avez-vous découvert une ou plusieurs valeurs personnelles ?",["Choisissez une réponse","Non","Oui"],key="inter_yes")
        if answer=="Non":
            if st.button("Continuer",type="primary"):
                target=st.session_state.get("return_after_personal_values")
                st.session_state.page=target or "Decision exploration"
                st.session_state.return_after_personal_values=""
                business_trace("aucune_valeur_interseance"); st.rerun()
        elif answer=="Oui":
            existing_inter=st.session_state.get("inter_session_values",[])
            count=int(st.number_input("Combien ?",1,10,max(1,len(existing_inter)),key="inter_count"))
            records=[]
            sources=["Observation personnelle ou cahier","Émotion ou réaction forte","Événement vécu","Échange avec un proche","Autre"]
            for i in range(count):
                st.markdown(f"### Valeur repérée n°{i+1}")
                previous=existing_inter[i] if i < len(existing_inter) else {}
                name=open_response_widget("Nom proposé",f"inter_name_{i}",value=previous.get("nom",""),height=70,allow_reformulation=False,dependency_scope="personal_values")
                source=st.selectbox("Comment l’avez-vous découverte ?",sources,key=f"inter_source_{i}")
                meaning=open_response_widget("Que signifie ce mot pour vous ?",f"inter_meaning_{i}",value=previous.get("definition",""),height=100,dependency_scope="personal_values",value_name=name.strip())
                situations=open_response_widget("Dans quelles situations l’avez-vous reconnue ?",f"inter_situations_{i}",value=" ; ".join(previous.get("situations",[]) or []),height=100,dependency_scope="personal_values",value_name=name.strip())
                reactions=open_response_widget("Que ressentez-vous lorsqu’elle est respectée ou bafouée ?",f"inter_reactions_{i}",value=" ; ".join(previous.get("emotions",[]) or []),height=100,dependency_scope="personal_values",value_name=name.strip())
                certainty=st.slider("À quel point êtes-vous certain qu’il s’agit d’une valeur importante pour vous ?",0,100,50,key=f"inter_cert_{i}")
                if name.strip() and meaning.strip() and situations.strip(): records.append({"nom":name.strip(),"source":source,"definition":meaning.strip(),"situations":[situations.strip()],"emotions":[reactions.strip()] if reactions.strip() else [],"certitude":certainty})
            direct=st.radio("Que souhaitez-vous faire de ces valeurs découvertes par vous-même ?",["Les valider maintenant","Les conserver en attente afin d’y revenir plus tard"],key="direct_validation_choice")
            if st.button("Enregistrer ces valeurs et continuer",type="primary",disabled=len(records)!=count):
                old_records=st.session_state.get("inter_session_values",[])
                if old_records and old_records!=records: invalidate_dependencies("personal_values",reason="valeurs découvertes personnellement modifiées")
                old_names={r.get("nom") for r in old_records}; new_names={r.get("nom") for r in records}
                for removed in old_names-new_names:
                    st.session_state.validation.pop(removed,None); st.session_state.personal_defs.pop(removed,None); st.session_state.value_records.pop(removed,None); st.session_state.hypothesis_status.pop(removed,None)
                st.session_state.inter_session_values=records
                for r in records:
                    st.session_state.personal_defs[r["nom"]]=r["definition"]
                    if direct.startswith("Les valider"):
                        register_value_record(r["nom"],"decouverte_personnelle","en_cours_analyse",r["definition"],r["situations"],r["emotions"],r["certitude"])
                        st.session_state.hypothesis_status[r["nom"]]="en_cours_analyse"
                    else:
                        register_value_record(r["nom"],"decouverte_personnelle","a_confirmer",r["definition"],r["situations"],r["emotions"],r["certitude"])
                        st.session_state.hypothesis_status[r["nom"]]="a_confirmer"
                synchronize_value_state(); business_trace("valeurs_interseances",str(len(records)))
                if direct.startswith("Les valider"):
                    names=[r["nom"] for r in records]
                    st.session_state.candidate_names=names
                    st.session_state.hypothesis_queue=names
                    st.session_state.hypothesis_index=0
                    st.session_state.validation_index=0; st.session_state.validation_stage={n:0 for n in names}; st.session_state.page="Validation"
                else:
                    target=st.session_state.get("return_after_personal_values")
                    st.session_state.page=target or "Decision exploration"
                    st.session_state.return_after_personal_values=""
                st.rerun()

    elif page=="Decision exploration":
        st.title("Souhaitez-vous rechercher d’autres valeurs ?")
        decision=st.radio("Souhaitez-vous que je vous aide à rechercher d’autres valeurs ?",["Choisissez une réponse","Oui","Non, je préfère contrôler ce que j’ai déjà"],key="decision_explore")
        if decision.startswith("Oui") and st.button("Ouvrir l’exploration",type="primary"):
            st.session_state.exploration_wanted=True
            st.session_state.current_question=choose_wide_question()
            st.session_state.page="Exploration IA"; business_trace("exploration_acceptee"); st.rerun()
        if decision.startswith("Non") and st.button("Contrôler la complétude",type="primary"):
            st.session_state.exploration_wanted=False; st.session_state.page="Controle completude"; business_trace("exploration_refusee"); st.rerun()

    elif page=="Exploration IA":
        st.title("Recherche guidée des autres valeurs"); value_reminder()
        if st.session_state.get("pipeline_status")=="queued":
            process_pending_exploration_submission()
        elif st.session_state.get("pipeline_status")=="running":
            st.warning("L’analyse précédente a été interrompue. Toutes vos réponses sont conservées. Vous pouvez relancer simplement l’analyse.")
            if st.button("Relancer cette analyse une seule fois",type="primary"):
                st.session_state.pipeline_status="queued"
                st.rerun()
            return
        st.caption("Une seule question à la fois. Vous pouvez écrire ou enregistrer votre réponse. L'IA travaille uniquement sur vos mots et ne décide jamais à votre place.")
        if st.session_state.get("reasoning_evolution"):
            evo=st.session_state.reasoning_evolution[-1]
            st.info(f"Première hypothèse : {evo.get('premiere_hypothese','')}  →  Hypothèse révisée : {evo.get('hypothese_revisee','')}\n\n{evo.get('explication','')}")
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
        explanation="Une seule question à la fois. Vous pouvez écrire ou enregistrer votre réponse. Pour une réponse orale, l’application affiche la transcription brute et une proposition Clarté360 rédigée en français écrit naturel, fluide et fidèle. Vous choisissez ensuite la version officielle."
        speak_button(explanation,"listen_exploration_instructions")
        st.caption(explanation)
        import hashlib
        question_key=hashlib.sha256(str(st.session_state.current_question).encode("utf-8")).hexdigest()[:12]
        answer_key=f"exploration_{len(st.session_state.get('conversation',[]))}_{question_key}"
        answer=open_response_widget(st.session_state.current_question,answer_key,height=150,allow_reformulation=True,dependency_scope="")
        processing=st.session_state.get("pipeline_status") in ("queued","running")
        if st.button("Envoyer ma réponse validée et afficher la question suivante",type="primary",disabled=(not answer.strip()) or processing):
            queue_exploration_submission(answer.strip())
            st.rerun()
        if st.session_state.get("conversation"):
            with st.expander("Modifier une réponse précédente et recalculer la suite",expanded=False):
                options=list(range(len(st.session_state.conversation)))
                selected_turn=st.selectbox("Réponse à modifier",options,format_func=lambda i:f"Question {i+1} — {st.session_state.conversation[i].get('question','')[:70]}",key="edit_turn_select")
                old_turn=st.session_state.conversation[selected_turn]
                revised=open_response_widget(old_turn.get("question",""),f"revise_turn_{selected_turn}",value=old_turn.get("answer",""),height=140,allow_reformulation=True,dependency_scope="")
                if st.button("Enregistrer cette modification et recalculer toutes les étapes dépendantes",type="primary",disabled=not revised.strip(),key="recalc_turn"):
                    revise_exploration_turn(selected_turn,revised)
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
        st.title("Examiner une hypothèse à la fois"); value_reminder()
        hyp_intro="Nous examinons une seule hypothèse jusqu’à sa validation ou son abandon. Les autres restent en attente et seront proposées ensuite."
        speak_button(hyp_intro,"listen_hyp_intro")
        st.markdown(f'<div class="clarte-box">{hyp_intro}</div>',unsafe_allow_html=True)
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
            st.session_state.personal_defs[name]=open_response_widget("Que signifie précisément ce mot pour vous ? Vous pouvez accepter, compléter ou remplacer la définition.",f"one_def_{name}",value=proposed,height=120,dependency_scope="value_definition",value_name=name)
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
        st.title("Questionnaire spécifique HEC"); value_reminder()
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
                    register_value_record(name,(st.session_state.value_records.get(name,{}) or {}).get("source","application"),"validee",st.session_state.personal_defs.get(name) or value_info(name).get("definition",""),certainty=100)
                    if name in st.session_state.custom_values and not st.session_state.custom_values[name].get("notified"):
                        notify_new_value(name,st.session_state.personal_defs.get(name) or value_info(name).get("definition",""))
                        st.session_state.custom_values[name]["notified"]=True
                if answer=="Oui": st.session_state.validation_stage[name]=stage+1
                else:
                    st.session_state.validation_stage[name]=3; current["fondamentale"]=False
                    st.session_state.hypothesis_status[name]="a_revoir"
                    register_value_record(name,(st.session_state.value_records.get(name,{}) or {}).get("source","application"),"a_revoir",st.session_state.personal_defs.get(name,""),certainty=40)
                synchronize_value_state()
                mark_data_change("validation_valeur",["controle_completude","rapport_final"])
                st.rerun()
        else:
            if current.get("fondamentale"): st.success("Cette valeur a franchi successivement les trois niveaux et est validée comme fondamentale.")
            else: st.info("Cette hypothèse n'est pas validée comme valeur fondamentale à ce stade. Elle pourra être reprise avec l'accompagnateur.")
            st.session_state.comments[name]=open_response_widget("Commentaire facultatif",f"comment_{name}",value=st.session_state.comments.get(name,""),height=90,dependency_scope="validation",value_name=name)
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
                    target=st.session_state.get("return_after_personal_values")
                    if target:
                        st.session_state.page=target
                        st.session_state.return_after_personal_values=""
                    else:
                        st.session_state.page="Controle completude"
                st.rerun()

    elif page=="Controle completude":
        st.title("Contrôle de complétude")
        vals=validated_names()
        explored=list(st.session_state.get("domains_explored",{}).keys())
        missing=[d for d in EXPLORATION_DOMAINS if d not in explored]
        close_values=[]
        for i,a in enumerate(vals):
            for b in vals[i+1:]:
                if SequenceMatcher(None,normalize(a),normalize(b)).ratio()>.72: close_values.append((a,b))
        completion_summary=(f"Vous avez actuellement {len(vals)} valeur(s) fondamentale(s) validée(s). "
                            + ("Certains domaines restent peu explorés : "+", ".join(missing)+". " if missing else "Les principaux domaines ont été explorés. ")
                            + ("Certaines valeurs paraissent proches et méritent d’être différenciées : "+" ; ".join(f"{a} et {b}" for a,b in close_values)+"." if close_values else ""))
        speak_button(completion_summary,"listen_completion_summary")
        st.markdown(f"**Valeurs actuellement validées : {len(vals)}**")
        if len(vals)<8: st.info("Votre liste contient moins de 8 valeurs. Ce n’est pas un problème : 8 à 12 est un repère indicatif, jamais un quota.")
        if missing: st.warning("Domaines encore peu ou pas explorés : "+", ".join(missing))
        else: st.success("Les principaux domaines d’exploration ont été abordés.")
        if close_values: st.warning("Certaines valeurs semblent proches et méritent peut-être d’être différenciées : "+" ; ".join(f"{a} / {b}" for a,b in close_values))
        represented=st.radio("Cette liste représente-t-elle suffisamment ce qui vous pousse à agir, choisir, accepter, refuser, vous engager, vous protéger ou réagir ?",["Choisissez","Oui","Partiellement","Non"],key="complete_rep")
        blind=open_response_widget("Y a-t-il un angle, une situation ou une valeur que vous souhaiteriez encore explorer ?","complete_blind",height=100,dependency_scope="validation")
        if st.button("Enregistrer ce contrôle",type="primary",disabled=represented=="Choisissez"):
            st.session_state.completion_check={"nombre_valeurs":len(vals),"domaines_explores":explored,"domaines_non_explores":missing,"valeurs_proches":close_values,"representation":represented,"angles_a_reprendre":blind.strip(),"date":now_iso(),"revision_donnees":st.session_state.get("data_revision",0)}
            st.session_state.stale_sections=[]; st.session_state.last_consistent_revision=st.session_state.get("data_revision",0)
            st.session_state.page="Resultats"; business_trace("controle_completude",represented); st.rerun()
        if st.button("Reprendre l’exploration"):
            st.session_state.current_question=choose_wide_question(); st.session_state.page="Exploration IA"; st.rerun()

    elif page=="Resultats":
        st.title("État actuel de ma recherche"); value_reminder()
        if st.session_state.get("stale_sections"):
            st.warning("Certaines informations ont été modifiées depuis le dernier contrôle. Reprenez le contrôle de complétude avant une clôture définitive.")
        validated=validated_names(); st.metric("Nombre de valeurs fondamentales validées",len(validated))
        for idx,name in enumerate(validated,1):
            info=value_info(name); source=(st.session_state.value_records.get(name,{}) or {}).get("source") or ("Séance avec l'accompagnateur" if name in st.session_state.existing_values else "Exploration avec l'application")
            st.markdown(f"### {idx}. {name}"); st.caption(f"{info.get('famille','')} - Origine : {source}"); st.write(st.session_state.personal_defs.get(name) or info.get("definition",""))
        result_info="Cette page n’est pas une fin imposée. Vous pouvez rechercher une autre valeur, revoir une hypothèse ou terminer volontairement votre exercice inter-séance."
        speak_button(result_info,"listen_result_info")
        st.markdown(f'<div class="clarte-box">{result_info}</div>',unsafe_allow_html=True)
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
        st.subheader("Sortie du parcours")
        exit_choice=st.radio("Souhaitez-vous quitter temporairement ou clôturer définitivement ?",["Sortie temporaire : conserver un JSON de reprise","Fermeture définitive : figer les résultats"],key="exit_choice")
        if exit_choice.startswith("Sortie temporaire"):
            st.download_button("Télécharger mon JSON de reprise",payload_bytes(False),file_name=make_filename("RVC360_reprise","json"),mime="application/json",use_container_width=True,on_click=lambda:record_save_event("sortie_temporaire"))
        elif st.button("Préparer la clôture définitive",type="primary",use_container_width=True):
            ok,issues=closure_consistency_audit()
            if ok: st.session_state.page="Cloture definitive"; st.rerun()
            else:
                st.error("La clôture est bloquée tant que les incohérences suivantes ne sont pas corrigées :")
                for issue in issues: st.write("• "+issue)
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
    init_state()
    if not st.session_state.get("access_authorized") and not st.session_state.get("test_started") and st.session_state.get("welcome_choice")!="import":
        access_gate_screen(); return
    sidebar_progress(); install_beforeunload_warning()
    if st.session_state.get("show_contact_page"): contact_page(); return
    if st.session_state.get("show_rgpd_page"): rgpd_page(); return
    if st.session_state.get("session_expired"): expired_screen(); return
    if st.session_state.get("test_started"):
        if st.session_state.get("exit_json_ready"): exit_prepared_screen(); return
        timeout_watchdog(); check_session_limit(); render_business_v218(); return
    choice=st.session_state.get("welcome_choice")
    if choice=="import": import_json_screen()
    elif choice=="new": identification_screen()
    else: welcome_screen()

if __name__=="__main__": main()
