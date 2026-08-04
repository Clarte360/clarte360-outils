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
from reportlab.platypus import CondPageBreak, PageBreak, Paragraph, SimpleDocTemplate, Spacer

try:
    from openai import OpenAI
except Exception:
    OpenAI = None
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

APP_VERSION = "2.1.9C-preproduction"
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

def load_referentiel() -> list[dict[str, str]]:
    if not REFERENTIEL_PATH.exists(): return []
    xls = pd.ExcelFile(REFERENTIEL_PATH)
    candidates = [name for name in xls.sheet_names if normalize(name).startswith("referentiel")]
    sheet = candidates[0] if candidates else xls.sheet_names[0]
    df = pd.read_excel(REFERENTIEL_PATH, sheet_name=sheet)
    df = df.rename(columns={
        "Code":"code", "Valeur":"nom", "Famille":"famille",
        "Définition Clarté360 - base de travail":"definition",
        "Définition Clarté360":"definition",
    })
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
        "json_schema_version":"2.1.3.9D",
        "active_module":"accueil_modules","pending_module_entry":"",
        "module_states":{
            "module_1":{"status":"non_commence","step":"intro"},
            "module_2":{"status":"indisponible","step":"questionnaire"},
            "module_3":{"status":"indisponible","step":"accueil"},
            "module_4":{"status":"indisponible","step":"complement_connaissance"},
            "module_5":{"status":"indisponible","step":"accueil"},
        },
        "central_validated_values":[], "values_to_examine":[], "session_review_items":[],
        "clarification_tracks":[], "hypothesis_basket":[], "module4_exploration_history":[],
        "current_value_work":{}, "module1_count":0, "module1_index":0,
        "module2_question_index":0, "module2_answers":{},
        "module3_declared_count":0, "module3_index":0, "module3_queue":[],
        "followup_panel_open":True, "report_history":[], "answer_history":{},
        "module4_knowledge_completed":False, "module4_knowledge_started_at":"",
        "module4_knowledge_completed_at":"", "module4_knowledge_index":0,
        "module4_knowledge_answers":{}, "module4_knowledge_version":"M4-CC-1.0",
        "module4_route":"", "module4_intro_acknowledged":False,
        "module4_current_cycle":{}, "module4_question_memory":[], "module4_candidate_options":[],
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


def _clean_value_label_input(text: str) -> str:
    """Nettoie un nom de valeur dicté sans lui substituer arbitrairement un autre concept.

    Les articles, répétitions orales et expressions comme « je répète » sont retirés.
    Un rapprochement vers le référentiel n'est proposé que lorsqu'un seul candidat est
    nettement dominant. Le bénéficiaire conserve toujours la validation finale.
    """
    raw=str(text or "").strip()
    if not raw:
        return ""
    cleaned=re.sub(r"(?i)\b(?:je\s+répète|je\s+redis|encore\s+une\s+fois)\b", " ", raw)
    cleaned=re.sub(r"[,:;.!?]+", " ", cleaned)
    cleaned=re.sub(r"\s+", " ", cleaned).strip()
    normalized_cleaned=" "+normalize(cleaned)+" "
    mentioned=[]
    for name in VALUE_NAMES:
        n=normalize(name)
        if n and (f" {n} " in normalized_cleaned or normalized_cleaned.strip()==n):
            mentioned.append(name)
    mentioned=list(dict.fromkeys(mentioned))
    if len(mentioned)==1:
        return mentioned[0]
    chunks=[]
    for part in re.split(r"\s+(?:et|ou)\s+", cleaned):
        candidate=_normalise_value_name(part)
        if candidate:
            chunks.append(candidate)
    # Une répétition du même terme doit devenir un seul nom de valeur.
    unique=[]
    for item in chunks:
        if normalize(item) not in {normalize(x) for x in unique}:
            unique.append(item)
    if len(unique)==1:
        candidate=unique[0]
    else:
        words=re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+", cleaned)
        candidate=_normalise_value_name(" ".join(words))
    exact=_referential_value_info(candidate)
    if exact:
        return exact.get("nom", candidate)
    matches=local_value_matches(candidate, limit=3)
    if matches:
        best=matches[0]
        score=SequenceMatcher(None,normalize(candidate),normalize(best)).ratio()
        second=SequenceMatcher(None,normalize(candidate),normalize(matches[1])).ratio() if len(matches)>1 else 0.0
        # Correction prudente des erreurs de transcription évidentes, ex. Loopisme -> Optimisme.
        if score>=0.68 and score-second>=0.08:
            return best
    return candidate


def clean_spoken_text(text: str, *, expected_value_label: bool=False, question_kind: str="open") -> str:
    """Corrige systématiquement la langue, puis reformule seulement si cela aide.

    La correction orthographique, grammaticale et typographique est obligatoire.
    Une proposition peut donc être très proche de l'original lorsqu'elle corrige une
    faute réelle. La fonction retourne une chaîne vide uniquement lorsque le texte est
    déjà correct et qu'aucune amélioration fidèle n'est nécessaire.
    """
    original=str(text or "").strip()
    if expected_value_label:
        candidate=_clean_value_label_input(original)
        return candidate if normalize(candidate)!=normalize(_normalise_value_name(original)) or candidate.strip()!=original.strip() else ""
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
    """Qualifie un terme sans lancer d'exploration verticale dans le Module 3.

    Règle 9F :
    - le nom de la valeur est prioritaire ;
    - un terme reconnu au référentiel reste une valeur reconnue ;
    - sa définition peut produire une alerte non bloquante, jamais un rejet automatique ;
    - pour un terme absent, le nom et la définition sont comparés pour décider entre
      valeur personnelle plausible et formulation non-valeur ;
    - aucune question de clarification n'est produite ici : l'exploration appartient au Module 4.
    """
    term=str(term or "").strip(); definition=str(definition or "").strip()
    canonical=_normalise_value_name(term)
    present=bool(_referential_value_info(canonical))
    if not _looks_like_value_label(term):
        return {"decision":"formulation_non_valeur","explication":"Cette proposition ressemble davantage à une phrase, un constat, un ressenti, une aspiration ou un concept qu'au nom d'une valeur.","question":"","alerte_definition":""}
    if present:
        warning=""
        low=normalize(definition)
        indicators=["peur", "manque", "besoin", "detresse", "angoiss", "stress", "objectif", "resultat", "obtenir"]
        if definition and any(marker in low for marker in indicators):
            warning="Votre définition personnelle évoque aussi un besoin, une peur, un état ou un résultat. Cela n'annule pas la valeur reconnue ; vous pouvez conserver votre formulation, la modifier ou choisir de l'explorer dans le Module 4."
        return {"decision":"valeur_reconnue","explication":"Le terme figure dans le référentiel Clarté360 et peut poursuivre son examen.","question":"","alerte_definition":warning}
    fallback={"decision":"valeur_absente_possible","explication":"Le terme ne figure pas dans le référentiel Clarté360, mais il peut néanmoins constituer une valeur personnelle selon le sens que vous lui donnez.","question":"","alerte_definition":"","definition_proposee":""}
    if not term or not definition or not ai_ready():
        return fallback
    instructions="""Analysez un NOUVEAU terme absent du référentiel Clarté360 en comparant son nom et sa définition personnelle.
Le Module 3 ne doit poser aucune question exploratoire. Concluez obligatoirement par UNE décision :
1. valeur_absente_possible : le terme peut constituer une valeur personnelle, c'est-à-dire un principe durable orientant les choix et les comportements ;
2. formulation_non_valeur : le terme désigne principalement un besoin, une peur, une émotion, un état recherché, un objectif, une croyance, une limite, une qualité, une compétence ou un comportement.
N'utilisez jamais un mot isolé de la définition comme preuve suffisante. Analysez le sens global du nom et de la définition. Ne diagnostiquez pas et n'ajoutez aucune question.
Proposez aussi une définition courte, neutre et fidèle au sens exprimé, formulée comme un principe durable, sans imposer cette formulation au bénéficiaire.
Retournez un JSON strict avec decision, explication et definition_proposee."""
    schema={"type":"object","properties":{"decision":{"type":"string","enum":["valeur_absente_possible","formulation_non_valeur"]},"explication":{"type":"string"},"definition_proposee":{"type":"string"}},"required":["decision","explication","definition_proposee"],"additionalProperties":False}
    try:
        out=response_json(instructions,{"terme":term,"definition_personnelle":definition,"present_referentiel":False},"analyse_nature_concept",schema,max_tokens=450)
        decision=str(out.get("decision") or fallback["decision"])
        explanation=str(out.get("explication") or fallback["explication"]).strip()
        if decision=="valeur_absente_possible":
            explanation=("Le terme ne figure pas dans le référentiel Clarté360, mais il peut néanmoins constituer une valeur personnelle selon le sens que vous lui donnez. "+explanation).strip()
        return {"decision":decision,"explication":explanation,"question":"","alerte_definition":"","definition_proposee":str(out.get("definition_proposee") or "").strip()}
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


def _ctrl_enter_marker(widget_key: str, button_label: str) -> None:
    """Place un repère DOM unique avant la zone de réponse concernée."""
    safe_key=html.escape(str(widget_key), quote=True)
    safe_label=html.escape(str(button_label), quote=True)
    st.markdown(
        f'<span data-clarte360-response-key="{safe_key}" '
        f'data-clarte360-target-label="{safe_label}" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def _install_ctrl_enter_bridge() -> None:
    """Installe un gestionnaire Ctrl+Entrée ciblé sur le champ actif.

    Le bouton est recherché uniquement dans la tranche DOM comprise entre le
    repère unique du champ actif et le repère du champ suivant. Deux champs
    portant le même libellé ne peuvent donc plus déclencher la mauvaise action.
    """
    components.html("""
    <script>
    (() => {
      const doc = window.parent.document;
      const handlerKey = '__clarte360_ctrl_enter_scoped_v1';
      if (doc[handlerKey]) return;
      doc[handlerKey] = true;

      const follows = (node, reference) =>
        !!(reference.compareDocumentPosition(node) & window.parent.Node.DOCUMENT_POSITION_FOLLOWING);

      doc.addEventListener('keydown', (event) => {
        if (!(event.ctrlKey && event.key === 'Enter')) return;
        const active = doc.activeElement;
        if (!active || !['TEXTAREA','INPUT'].includes(active.tagName)) return;

        const markers = Array.from(doc.querySelectorAll('[data-clarte360-response-key]'));
        const currentIndex = markers.reduce((found, marker, index) =>
          follows(active, marker) ? index : found, -1);
        if (currentIndex < 0) return;

        const current = markers[currentIndex];
        const next = markers[currentIndex + 1] || null;
        const wanted = (current.dataset.clarte360TargetLabel || '').trim();
        if (!wanted) return;

        const buttons = Array.from(doc.querySelectorAll('button'));
        const target = buttons.find((button) => {
          if (button.disabled || button.offsetParent === null) return false;
          if (button.innerText.trim() !== wanted) return false;
          if (!follows(button, active)) return false;
          if (next && follows(button, next)) return false;
          return true;
        });
        if (!target) return;

        event.preventDefault();
        event.stopPropagation();
        target.click();
      }, true);
    })();
    </script>
    """, height=0, width=0)


def open_response_widget(label: str, key: str, *, value: str="", height: int=110,
                         allow_reformulation: bool=True, help_text: str="",
                         listen: bool=True, dependency_scope: str="", value_name: str="",
                         expected_value_label: bool=False, question_kind: str="open") -> str:
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
    if help_text:
        st.caption(help_text)
    elif question_kind == "word":
        st.caption("Nous recherchons un mot ou une courte expression. Si rien ne vous vient, vous pouvez répondre « Je ne sais pas » ou « Je ne vois pas » ; Clarté360 pourra ensuite vous proposer quelques hypothèses.")
    else:
        st.caption("Prenez votre temps et cherchez une réponse personnelle. N'hésitez pas à répondre à l'oral, même si vous hésitez ou vous reprenez : votre explication nous aide à comprendre ce qui est important pour vous.")

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
                st.session_state[proposal_key]=reliable_clean_spoken_text(official, expected_value_label=expected_value_label)
        proposal=str(st.session_state.get(proposal_key) or "").strip()
        if not proposal:
            st.success("Votre réponse est déjà suffisamment claire. Aucune reformulation supplémentaire n’est nécessaire.")
            if st.button("Conserver ma réponse actuelle",key=f"{base}_keep_clear",type="primary",use_container_width=True): st.session_state[editing_key]=False; st.session_state[mode_key]=""; st.rerun()
        else:
            difference_kind=_text_difference_kind(official,proposal)
            if difference_kind=="identique":
                st.success("Votre réponse est déjà claire et correctement formulée. Aucune modification n’est nécessaire.")
                choice=st.radio("Validation",["Choisissez une option","Conserver ma réponse actuelle"],key=f"{base}_direct_choice")
            elif difference_kind=="correction_legere":
                st.info("Clarté360 propose une légère correction de forme, sans modifier le sens. Comparez les deux versions avant de choisir.")
                st.markdown(f'<div class="transcript-card"><b>Formulation initiale</b><br><br>{html.escape(official)}</div>',unsafe_allow_html=True)
                st.markdown(f'<div class="transcript-card corrected"><b>Correction de forme proposée</b><br><br>{html.escape(proposal)}</div>',unsafe_allow_html=True)
                choice=st.radio("Quelle version souhaitez-vous conserver ?",["Choisissez une option","Conserver ma formulation","Utiliser la correction de forme"],key=f"{base}_direct_choice")
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
    # Le repère unique est rendu immédiatement avant la zone de texte. Le
    # gestionnaire navigateur limite ensuite sa recherche au segment DOM de ce
    # champ, jusqu'au repère du champ suivant.
    ctrl_enter_button_label = "✓ Valider ma réponse écrite" if (not allow_reformulation and not expected_value_label) else "Préparer et comparer"
    _ctrl_enter_marker(f"{base}_typed_{edit_mode}", ctrl_enter_button_label)
    typed=st.text_area("Votre réponse écrite",value=initial_text,height=height,key=f"{base}_typed_{edit_mode}",label_visibility="collapsed",placeholder="Écrivez ou collez votre réponse ici…",on_change=mark_user_activity,args=(f"saisie_{base}",))
    st.caption("Ctrl + Entrée : valider immédiatement" if ctrl_enter_button_label.startswith("✓") else "Ctrl + Entrée : préparer et comparer immédiatement")
    _install_ctrl_enter_bridge()
    proposal_key=f"{base}_typed_proposal_{edit_mode}"; source_key=f"{base}_typed_source_{edit_mode}"
    if typed.strip():
        if not allow_reformulation and not expected_value_label:
            if st.button("✓ Valider ma réponse écrite",key=f"{base}_validate_typed_{edit_mode}",type="primary",use_container_width=True):
                new_value=typed.strip(); meta.setdefault("historique_versions",[])
                if official: meta["historique_versions"].append({"version":official,"remplacee_le":now_iso(),"motif":"modification bénéficiaire"})
                meta.update({"mode_saisie":"clavier","texte_brut":new_value,"reformulation_proposee":"","reformulation_retenue":"original","transcription":"","transcription_corrigee":"","version_officielle":new_value,"validee_le":now_iso()})
                st.session_state[f"{base}_official"]=new_value; st.session_state[editing_key]=False; st.session_state[mode_key]=""; st.rerun()
        else:
            if st.session_state.get(source_key)!=typed.strip(): st.session_state.pop(proposal_key,None)
            if st.button("Préparer et comparer",key=f"{base}_prepare_typed_{edit_mode}",type="primary",use_container_width=True):
                st.session_state[source_key]=typed.strip(); st.session_state[proposal_key]=reliable_clean_spoken_text(typed.strip(), expected_value_label=expected_value_label); st.rerun()
            if source_key in st.session_state:
                proposal=str(st.session_state.get(proposal_key) or "").strip()
                difference_kind=_text_difference_kind(typed.strip(),proposal)
                options=["Choisissez une option"]
                if difference_kind=="identique":
                    st.markdown(f'<div class="transcript-card"><b>Votre réponse</b><br><br>{html.escape(typed.strip())}</div>',unsafe_allow_html=True)
                    st.success("Votre réponse est déjà claire et correctement formulée. Aucune modification n’est nécessaire.")
                    options.append("Conserver ma réponse initiale")
                elif difference_kind=="correction_legere":
                    st.info("Clarté360 propose une légère correction de forme, sans modifier le sens. Comparez les deux versions avant de choisir.")
                    st.markdown(f'<div class="transcript-card"><b>Réponse initiale</b><br><br>{html.escape(typed.strip())}</div>',unsafe_allow_html=True)
                    st.markdown(f'<div class="transcript-card corrected"><b>Version légèrement corrigée</b><br><br>{html.escape(proposal)}</div>',unsafe_allow_html=True)
                    options.extend(["Conserver ma réponse initiale","Utiliser la correction de forme"])
                else:
                    st.markdown(f'<div class="transcript-card"><b>Réponse initiale</b><br><br>{html.escape(typed.strip())}</div>',unsafe_allow_html=True)
                    st.markdown(f'<div class="transcript-card corrected"><b>Proposition Clarté360</b><br><br>{html.escape(proposal)}</div>',unsafe_allow_html=True)
                    options.append("Conserver ma réponse initiale")
                    if proposal: options.append("Utiliser la proposition Clarté360")
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
                raw=""; last_error=None
                for attempt in range(2):
                    try:
                        raw=transcribe_audio(audio)
                        if raw.strip(): break
                    except Exception as exc:
                        last_error=exc
                    if attempt==0:
                        st.caption("Nouvelle tentative automatique de transcription…")
                if not raw.strip():
                    raise RuntimeError(str(last_error or "Aucune transcription n’a été retournée."))
                # Mémoriser immédiatement la transcription : même si la correction IA
                # tarde ou échoue, le premier clic affiche toujours la version originale.
                st.session_state[f"{base}_transcript_raw"]=raw
                st.session_state[f"{base}_transcript_clean"]=raw
                proposal=reliable_clean_spoken_text(raw, expected_value_label=expected_value_label)
                st.session_state[f"{base}_transcript_clean"]=proposal or raw
            # Un seul clic doit suffire : on force immédiatement le rerun qui affiche
            # la transcription déjà mémorisée, sans relancer ni la transcription ni l'IA.
            st.rerun()
        except Exception as exc: st.session_state[f"{base}_transcription_error"]=str(exc)
    err=str(st.session_state.pop(f"{base}_transcription_error","") or "")
    if err: st.error(f"La transcription n’a pas pu être réalisée : {err}")
    raw=str(st.session_state.get(f"{base}_transcript_raw","") or ""); proposal=str(st.session_state.get(f"{base}_transcript_clean","") or "")
    if raw:
        difference_kind=_text_difference_kind(raw,proposal)
        options=["Choisissez une option"]
        if difference_kind=="identique":
            st.markdown(f'<div class="transcript-card"><b>Votre transcription</b><br><br>{html.escape(raw)}</div>',unsafe_allow_html=True)
            st.success("Votre transcription est déjà claire et correctement formulée. Aucune modification n’est nécessaire.")
            options.append("Conserver la transcription initiale")
        elif difference_kind=="correction_legere":
            st.info("Clarté360 propose une légère correction de forme, sans modifier le sens. Comparez les deux versions avant de choisir.")
            st.markdown(f'<div class="transcript-card"><b>Transcription initiale</b><br><br>{html.escape(raw)}</div>',unsafe_allow_html=True)
            st.markdown(f'<div class="transcript-card corrected"><b>Version légèrement corrigée</b><br><br>{html.escape(proposal)}</div>',unsafe_allow_html=True)
            options.append("Conserver la transcription initiale")
            options.append("Utiliser la correction de forme")
        else:
            st.markdown(f'<div class="transcript-card"><b>Transcription initiale</b><br><br>{html.escape(raw)}</div>',unsafe_allow_html=True)
            options.append("Conserver la transcription initiale")
            if proposal:
                st.markdown(f'<div class="transcript-card corrected"><b>Proposition Clarté360</b><br><br>{html.escape(proposal)}</div>',unsafe_allow_html=True)
                options.append("Utiliser la proposition Clarté360")
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
        return [str(v.get("nom_final") or v.get("nom") or "").strip() for v in central if v.get("statut") == "validee" and str(v.get("nom_final") or v.get("nom") or "").strip()]
    names=list(dict.fromkeys(st.session_state.existing_values+st.session_state.get("validated_app_values",[])))
    return [n for n in names if st.session_state.validation.get(n,{}).get("fondamentale")]


MODULE_LABELS = {
    "module_1":"MODULE 1\nPrérequis", "module_2":"MODULE 2\nFaisons connaissance",
    "module_3":"MODULE 3\nValider ou revoir une valeur", "module_4":"MODULE 4\nRechercher une nouvelle valeur",
    "module_5":"MODULE 5\nMes rapports",
}
MODULE4_KNOWLEDGE_VERSION = "M4-CC-1.0"

# Complément de connaissance du module 4.
# Ces micro-exercices ne produisent ni score, ni profil, ni valeur supposée.
# Ils sont réalisés une seule fois et servent seulement à personnaliser les futures questions.
MODULE4_KNOWLEDGE_EXERCISES = [
    {
        "id":"M4-CC-001", "version":"1.0", "type":"choix_binaire",
        "title":"Quand une journée se libère au dernier moment",
        "prompt":"Quelle réaction vous ressemble le plus spontanément ?",
        "options":[
            "Je profite de l'occasion pour faire quelque chose que je n'avais pas prévu.",
            "Je préfère utiliser ce temps pour avancer sur quelque chose déjà important pour moi.",
        ],
        "intention":"Repérer le type de situations concrètes qui pourront être proposées ensuite, sans conclure sur une valeur.",
    },
    {
        "id":"M4-CC-002", "version":"1.0", "type":"choix_binaire",
        "title":"Dans un projet collectif",
        "prompt":"Quelle contribution vous attire le plus naturellement ?",
        "options":[
            "Faire émerger une idée nouvelle et donner l'impulsion de départ.",
            "Faire en sorte que chacun sache clairement comment avancer.",
        ],
        "intention":"Adapter les futurs exemples de questionnement à des situations de lancement ou de structuration.",
    },
    {
        "id":"M4-CC-003", "version":"1.0", "type":"micro_situation",
        "title":"Une personne vous demande de l'aide",
        "prompt":"Quelle première réaction vous vient le plus facilement ?",
        "options":[
            "L'écouter d'abord pour comprendre précisément ce qu'elle traverse.",
            "Chercher rapidement avec elle une manière concrète d'avancer.",
            "L'aider à identifier les personnes ou ressources qui pourraient aussi intervenir.",
        ],
        "intention":"Choisir ultérieurement des relances centrées sur l'écoute, l'action ou la mobilisation de ressources, sans attribuer de trait.",
    },
    {
        "id":"M4-CC-004", "version":"1.0", "type":"choix_binaire",
        "title":"Vous découvrez une nouvelle activité",
        "prompt":"Qu'est-ce qui vous donne le plus envie de continuer ?",
        "options":[
            "Comprendre progressivement comment tout fonctionne.",
            "Pouvoir rapidement essayer, ajuster et voir un résultat concret.",
        ],
        "intention":"Adapter le rythme et la forme des futures questions à des situations d'apprentissage ou d'expérimentation.",
    },
    {
        "id":"M4-CC-005", "version":"1.0", "type":"choix_binaire",
        "title":"Deux options sont possibles",
        "prompt":"Quand les deux solutions se valent, qu'est-ce qui vous aide le plus à décider ?",
        "options":[
            "Pouvoir comparer calmement les conséquences de chaque option.",
            "Sentir qu'une option correspond davantage à ce que je veux vivre maintenant.",
        ],
        "intention":"Choisir des formulations de relance plus factuelles ou plus expérientielles, sans conclure sur le fonctionnement de la personne.",
    },
    {
        "id":"M4-CC-006", "version":"1.0", "type":"micro_situation",
        "title":"Un moment dont vous êtes satisfait",
        "prompt":"Lequel de ces moments vous semblerait le plus agréable ?",
        "options":[
            "Avoir mené quelque chose jusqu'au bout malgré les difficultés.",
            "Avoir partagé un moment simple mais vraiment réussi avec d'autres personnes.",
            "Avoir découvert une possibilité à laquelle je n'avais pas pensé.",
        ],
        "intention":"Diversifier les futurs points de départ entre accomplissement, expérience partagée et découverte.",
    },
    {
        "id":"M4-CC-007", "version":"1.0", "type":"choix_binaire",
        "title":"Quelqu'un n'est pas d'accord avec vous",
        "prompt":"Quelle suite vous paraît la plus utile ?",
        "options":[
            "Prendre le temps de comprendre ce qui explique son point de vue.",
            "Revenir aux faits et chercher une solution acceptable pour avancer.",
        ],
        "intention":"Préparer des questions futures portant sur le sens de la relation ou sur les critères concrets de décision.",
    },
    {
        "id":"M4-CC-008", "version":"1.0", "type":"classement_court",
        "title":"Dans une période agréable",
        "prompt":"Classez ces trois situations de celle qui vous attire le plus à celle qui vous attire le moins.",
        "options":[
            "Pouvoir consacrer du temps à un projet personnel.",
            "Vivre davantage de moments de qualité avec des personnes importantes.",
            "Découvrir de nouveaux lieux, idées ou façons de faire.",
        ],
        "intention":"Sélectionner de futurs domaines d'exploration sans transformer le classement en résultat ou en profil.",
    },
]

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
    _finalise_pending_history(work,"validee",canonical)
    st.session_state.personal_defs[canonical]=definition_personnelle.strip()
    st.session_state.validation[canonical]={"importante":True,"tres_importante":True,"fondamentale":True,"origine_validation":source}
    if source=="accompagnateur" and canonical not in st.session_state.existing_values: st.session_state.existing_values.append(canonical)
    if source!="accompagnateur" and canonical not in st.session_state.validated_app_values: st.session_state.validated_app_values.append(canonical)
    register_value_record(canonical,source,"validee",definition_personnelle,certainty=100)
    _set_module_status("module_5","disponible","accueil")

def _finalise_pending_history(work: dict[str,Any], final_status: str, final_name: str="") -> None:
    """Clôture les anciens marqueurs d'une valeur reprise afin qu'elle ne soit pas remigrée."""
    original=str(work.get("original_name") or work.get("nom_initial") or "").strip()
    canonical=_normalise_value_name(final_name or work.get("nom_final") or original)
    for key in {original, canonical}:
        if not key:
            continue
        rec=st.session_state.get("value_records",{}).get(key)
        if isinstance(rec,dict):
            rec["statut"]=final_status
            rec["validation_finale"]=final_status=="validee"
            rec["nom_final"]=canonical
            rec["date_mise_a_jour"]=now_iso()
    # Les anciens tableaux techniques ne doivent plus forcer un statut abandonné/rejeté
    # lorsque la valeur est remise en traitement ou vient d'être décidée.
    for list_key in ("discarded","abandoned_hypotheses"):
        values=list(st.session_state.get(list_key,[]) or [])
        st.session_state[list_key]=[v for v in values if normalize(_normalise_value_name(v)) not in {normalize(_normalise_value_name(original)),normalize(canonical)}]
    rejected=st.session_state.get("rejected_values",[])
    if isinstance(rejected,list):
        st.session_state.rejected_values=[x for x in rejected if normalize(_normalise_value_name(x.get("nom") if isinstance(x,dict) else x)) not in {normalize(_normalise_value_name(original)),normalize(canonical)}]
    if original and original in st.session_state.get("hypothesis_status",{}):
        st.session_state.hypothesis_status[original]=final_status
    if canonical:
        st.session_state.hypothesis_status[canonical]=final_status

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
    _finalise_pending_history(work,"a_revoir_en_seance",item["terme"])
    return True

def _send_work_to_explore(work: dict[str,Any], reason: str="Exploration verticale demandée par le bénéficiaire") -> bool:
    terme=_normalise_value_name(work.get("nom_final") or work.get("nom_initial") or work.get("nom") or "")
    if not terme:
        return False
    item={"id":str(uuid.uuid4()),"terme_initial":terme,"definition_personnelle":work.get("definition_personnelle","") or work.get("definition", ""),"classification_provisoire":work.get("nature_decision") or "formulation_ambigue","nature_provisoire":work.get("nature_decision") or "formulation ambiguë","origine":"module_3","elements_source":deepcopy(work),"motif":reason,"statut":"piste_a_clarifier","created_at":now_iso()}
    _remove_value_from_active_lists(terme,keep="a_explorer")
    st.session_state.clarification_tracks.append(item)
    _finalise_pending_history(work,"piste_a_clarifier",terme)
    business_trace("piste_a_clarifier_module4",terme)
    return True

def _save_work_for_later(work: dict[str,Any]) -> bool:
    terme=_normalise_value_name(work.get("nom_final") or work.get("nom_initial") or work.get("nom") or "")
    if not terme:
        return False
    item=deepcopy(work)
    item.update({"nom_initial":work.get("nom_initial") or terme,"nom_normalise":terme,"nom_final":terme,"stage":"nom","statut":"a_examiner","created_at":work.get("created_at") or now_iso()})
    _remove_value_from_active_lists(terme,keep="a_examiner")
    st.session_state.values_to_examine.append(item)
    _finalise_pending_history(work,"a_examiner",terme)
    business_trace("valeur_conservee_a_examiner",terme)
    return True

def _finish_module3_orientation() -> None:
    st.session_state.module3_queue=[]
    st.session_state.current_value_work={}
    st.session_state.module3_index=0
    _set_module_status("module_3","disponible","accueil")

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
    for item in st.session_state.get("clarification_tracks",[]):
        if normalize(_normalise_value_name(item.get("terme_initial") or item.get("terme") or ""))==n and item.get("statut")=="piste_a_clarifier":
            return "a_explorer",item
    for item in st.session_state.get("session_review_items",[]):
        if normalize(_normalise_value_name(item.get("terme") or ""))==n and item.get("statut")=="a_revoir_en_seance":
            return "a_revoir",item
    return "",None

def _remove_value_from_active_lists(name: str, *, keep: str="validee") -> None:
    """Garantit : une valeur = un état actuel = une seule liste active."""
    n=normalize(_normalise_value_name(name))
    if keep!="a_examiner":
        st.session_state.values_to_examine=[x for x in st.session_state.get("values_to_examine",[]) if normalize(_normalise_value_name(x.get("nom_final") or x.get("nom_initial") or x.get("nom") or ""))!=n]
    if keep!="a_explorer":
        st.session_state.clarification_tracks=[x for x in st.session_state.get("clarification_tracks",[]) if normalize(_normalise_value_name(x.get("terme_initial") or x.get("terme") or ""))!=n]
    if keep!="a_revoir":
        st.session_state.session_review_items=[x for x in st.session_state.get("session_review_items",[]) if normalize(_normalise_value_name(x.get("terme") or ""))!=n]
    if keep!="validee":
        st.session_state.central_validated_values=[x for x in st.session_state.get("central_validated_values",[]) if normalize(_normalise_value_name(x.get("nom_final") or x.get("nom") or ""))!=n]
    # Nettoyage des états de reprise actifs : ils ne doivent jamais recréer un ancien panier.
    reprise=st.session_state.get("resume_state",{})
    if isinstance(reprise,dict):
        for key in ("values_to_examine","inter_session_pending","pistes_a_clarifier","a_revoir_en_seance"):
            values=reprise.get(key)
            if isinstance(values,list):
                reprise[key]=[x for x in values if normalize(_normalise_value_name((x.get("nom_final") or x.get("nom_initial") or x.get("nom") or x.get("terme_initial") or x.get("terme") or "") if isinstance(x,dict) else x))!=n]

def _value_alias_norms(*names: str) -> set[str]:
    aliases=set()
    for name in names:
        raw=str(name or "").strip()
        if not raw:
            continue
        aliases.add(normalize(raw))
        aliases.add(normalize(_normalise_value_name(raw)))
    return {x for x in aliases if x}

def _purge_value_everywhere(*names: str) -> None:
    """Supprime définitivement une valeur et toutes ses données métier liées.

    Aucun contenu métier, questionnaire, réponse, historique ou état de reprise
    rattaché à cette valeur ne doit rester dans le JSON de travail.
    """
    aliases=_value_alias_norms(*names)
    if not aliases:
        return
    def match(value: Any) -> bool:
        if value is None:
            return False
        return normalize(_normalise_value_name(str(value))) in aliases or normalize(str(value)) in aliases
    def item_name(item: Any) -> str:
        if isinstance(item,dict):
            for key in ("nom_final","nom_normalise","nom_initial","nom_propose","nom","terme","valeur"):
                if item.get(key):
                    return str(item.get(key))
            return ""
        return str(item or "")

    for key in ("central_validated_values","values_to_examine","session_review_items","inter_session_values","inter_session_pending"):
        st.session_state[key]=[x for x in list(st.session_state.get(key,[]) or []) if not match(item_name(x))]
    for key in ("existing_values","validated_app_values","candidate_names","hypothesis_queue","completed_hypotheses","abandoned_hypotheses","discarded"):
        st.session_state[key]=[x for x in list(st.session_state.get(key,[]) or []) if not match(x)]
    rejected=[]
    for x in list(st.session_state.get("rejected_values",[]) or []):
        if not match(item_name(x)):
            rejected.append(x)
    st.session_state.rejected_values=rejected

    for key in ("validation","personal_defs","comments","value_records","hypothesis_status","hypothesis_decisions","candidate_reasons","candidate_evidence"):
        data=dict(st.session_state.get(key,{}) or {})
        st.session_state[key]={k:v for k,v in data.items() if not match(k) and not match(item_name(v) if isinstance(v,dict) else "")}

    # Historique et traces métier : suppression de toute entrée citant explicitement la valeur.
    for key in ("trace","historique","dependency_events","evenements_dependances","reasoning_evolution","hypothesis_history","analysis_history"):
        cleaned=[]
        for event in list(st.session_state.get(key,[]) or []):
            blob=" ".join(str(v) for v in event.values()) if isinstance(event,dict) else str(event)
            if any(a and a in normalize(blob) for a in aliases):
                continue
            cleaned.append(event)
        st.session_state[key]=cleaned

    # Réponses structurées / métadonnées de réponses liées à la valeur.
    metadata=dict(st.session_state.get("answer_metadata",{}) or {})
    to_remove=[]
    for key,meta in metadata.items():
        blob=key+" "+(" ".join(str(v) for v in meta.values()) if isinstance(meta,dict) else str(meta))
        if any(a and a in normalize(blob) for a in aliases):
            to_remove.append(key)
    for key in to_remove:
        metadata.pop(key,None)
        for state_key in list(st.session_state.keys()):
            if str(state_key).startswith(key):
                st.session_state.pop(state_key,None)
    st.session_state.answer_metadata=metadata

    st.session_state.module3_queue=[x for x in list(st.session_state.get("module3_queue",[]) or []) if not match(item_name(x))]
    current=st.session_state.get("current_value_work",{}) or {}
    if match(item_name(current)) or match(current.get("original_name","")):
        st.session_state.current_value_work={}
        st.session_state.module3_index=0
    st.session_state.data_revision=int(st.session_state.get("data_revision",0))+1
    st.session_state.completion_check={}
    st.session_state.exploration_complete=False

def _restore_current_module3_origin(work: dict[str,Any]) -> None:
    """Restaure sans modification une valeur temporairement sortie de son panier."""
    source=work.get("source")
    if source=="examen_attente":
        restored=deepcopy(work.get("origin_snapshot") or work)
        restored["source"]=work.get("source_initiale") or restored.get("source") or "migration_v2137"
        restored.pop("origin_snapshot",None)
        if not any(normalize(_normalise_value_name(x.get("nom_final") or x.get("nom_initial") or x.get("nom") or ""))==normalize(_normalise_value_name(restored.get("nom_final") or restored.get("nom_initial") or restored.get("nom") or "")) for x in st.session_state.get("values_to_examine",[])):
            st.session_state.values_to_examine.append(restored)
    elif source=="examen_seance":
        restored=deepcopy(work.get("origin_snapshot") or work)
        restored["statut"]="a_revoir_en_seance"
        restored["terme"]=restored.get("terme") or restored.get("nom_final") or restored.get("nom_initial")
        restored.pop("origin_snapshot",None)
        if not any(normalize(_normalise_value_name(x.get("terme") or ""))==normalize(_normalise_value_name(restored.get("terme") or "")) for x in st.session_state.get("session_review_items",[])):
            st.session_state.session_review_items.append(restored)
    elif source=="examen_hypothese":
        restored=deepcopy(work.get("origin_snapshot") or {})
        if restored and not any(normalize(x.get("nom") or "")==normalize(restored.get("nom") or "") for x in st.session_state.get("hypothesis_basket",[])):
            st.session_state.hypothesis_basket.append(restored)
    elif source=="reexamen":
        original=_find_central_value(work.get("original_name") or work.get("nom_initial") or work.get("nom_final") or "")
        if original:
            original["en_reexamen"]=False

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
    # Une valeur déjà ouverte dans le module 3 ne doit jamais être recréée par la migration
    # à chaque rerun Streamlit. Sinon elle réapparaît dans « À examiner » et se bloque
    # elle-même comme doublon pendant son propre réexamen.
    active_work_names=set()
    for x in list(st.session_state.get("module3_queue",[]) or [])+[st.session_state.get("current_value_work",{}) or {}]:
        for v in (x.get("original_name"),x.get("nom_final"),x.get("nom_normalise"),x.get("nom_initial"),x.get("nom")):
            if v:
                active_work_names.add(normalize(_normalise_value_name(v)))
    validated_norm={normalize(x.get("nom_final") or x.get("nom") or "") for x in st.session_state.get("central_validated_values",[])}
    for name,record in (st.session_state.get("value_records",{}) or {}).items():
        status=str(record.get("statut", "")).lower()
        if status not in {"en_cours_analyse","a_confirmer","a_examiner","terme_a_confirmer","questionnaire_a_realiser"}:
            continue
        candidate_variants={normalize(name), normalize(record.get("nom_propose") or name), normalize(_normalise_value_name(record.get("nom_propose") or name))}
        if candidate_variants & validated_norm or candidate_variants & pending_names or candidate_variants & active_work_names:
            continue
        info=_referential_value_info(name)
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

def _module_has_temporary_work(module_id: str) -> bool:
    if module_id == "module_3":
        work = st.session_state.get("current_value_work") or {}
        return bool(work and not work.get("completed") and work.get("stage") not in {"", "termine"})
    if module_id == "module_4":
        cycle = st.session_state.get("module4_current_cycle") or {}
        return bool(cycle and cycle.get("stage") not in {"", "termine"})
    return False

def _abandon_module_temporary_work(module_id: str) -> None:
    if module_id == "module_3":
        st.session_state.current_value_work = {}
        st.session_state.module3_queue = []
        st.session_state.module3_index = 0
    elif module_id == "module_4":
        cycle = st.session_state.get("module4_current_cycle") or {}
        cycle_id = str(cycle.get("id") or "")
        if cycle_id:
            st.session_state.module4_exploration_history = [x for x in st.session_state.get("module4_exploration_history", []) if str(x.get("cycle_id") or "") != cycle_id]
            st.session_state.module4_question_memory = [x for x in st.session_state.get("module4_question_memory", []) if str(x.get("cycle_id") or "") != cycle_id]
            prefix = f"m4_cycle_{cycle_id}_"
            for store_name in ("answer_metadata",):
                store = st.session_state.get(store_name, {})
                for key in list(store.keys()):
                    if str(key).startswith(prefix):
                        store.pop(key, None)
        st.session_state.module4_current_cycle = {}
        st.session_state.module4_candidate_options = []
        st.session_state.module4_route = ""
        st.session_state.pipeline_status = "idle"
        st.session_state.pipeline_error = ""
        st.session_state.pending_pipeline_answer = ""
        st.session_state.pending_analysis_card = {}
        st.session_state.pending_submission = {}
    _set_module_status(module_id, "disponible", "accueil" if module_id != "module_4" else "choix_voie")

def _request_module_entry(module_id: str) -> None:
    current = st.session_state.get("active_module", "")
    if module_id != current and _module_has_temporary_work(module_id):
        st.session_state.pending_module_entry = module_id
    else:
        st.session_state.active_module = module_id

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
                _request_module_entry(mid); st.session_state.page="Modules"; st.rerun()
        st.markdown("<div style='text-align:center;color:#6B7D7D;font-size:.78rem;margin-top:.5rem'>✅ Terminé &nbsp;·&nbsp; ▶ En cours &nbsp;·&nbsp; ○ Disponible</div>",unsafe_allow_html=True)

def render_followup_panel() -> None:
    vals=validated_names(); pending=st.session_state.get("values_to_examine",[]); review=st.session_state.get("session_review_items",[]); hypotheses=st.session_state.get("hypothesis_basket",[]); tracks=st.session_state.get("clarification_tracks",[])
    opened=st.toggle(f"Afficher le suivi de mes valeurs ({len(vals)})",value=bool(st.session_state.get("followup_panel_open",True)),key="followup_panel_toggle")
    st.session_state.followup_panel_open=bool(opened)
    if not opened:
        st.caption(f"Mes valeurs ({len(vals)}) ▶")
        return
    with st.container(border=True):
        st.markdown("**✅ Valeurs validées**")
        st.write(", ".join(vals) if vals else "Aucune pour le moment.")
        st.markdown("**💡 Panier Hypothèses**")
        st.write(", ".join(str(x.get("nom") or x.get("nom_final") or "") for x in hypotheses) if hypotheses else "Aucune hypothèse conservée.")
        c_title,c_info=st.columns([8,1])
        with c_title:
            st.markdown("**🧭 À explorer — Module 4**")
        with c_info:
            with st.popover("ⓘ", help="Comprendre l’exploration du Module 4"):
                st.write("Le Module 4 approfondit un terme grâce à un questionnement guidé et vertical. Utilisez-le lorsque le mot ou sa signification restent flous, ou pour rechercher la valeur éventuellement cachée derrière un besoin, une peur, une émotion, une situation ou un objectif. Le Module 3 sert uniquement à identifier et valider une valeur déjà formulée.")
        if tracks:
            for track in tracks:
                nature=track.get("nature_provisoire") or track.get("nature") or "formulation ambiguë"
                st.write(f"{track.get('terme_initial') or track.get('terme') or 'Piste'} — Piste à clarifier ({nature})")
        else: st.write("Aucune piste à clarifier.")
        st.markdown("**🔎 Valeurs à examiner**")
        st.write(", ".join(str(x.get("nom_final") or x.get("nom") or x.get("nom_initial") or "") for x in pending) if pending else "Aucune.")
        st.markdown("**📋 À revoir en séance**")
        st.write(", ".join(str(x.get("terme") or "") for x in review) if review else "Aucun sujet.")

def _value_definition_choices(work: dict[str,Any], prefix: str, allow_ai_rewrite: bool=True) -> tuple[str,str,bool]:
    personal=str(work.get("definition_personnelle","") or "").strip()
    official=str(work.get("definition_clarte360","") or "").strip()
    st.markdown("**Votre définition personnelle**")
    st.info(personal or "Non renseignée")
    if official:
        st.markdown("**Définition Clarté360**")
        st.info(official)
    options=["Conserver ma définition personnelle"]
    if official:
        options += ["Adopter la définition Clarté360", "Créer une formulation combinée"]
    options += ["Modifier manuellement ma définition"]
    choice=st.radio("Comment souhaitez-vous traiter votre définition ?",options,key=f"{prefix}_def_choice")
    final_def=personal
    if choice=="Adopter la définition Clarté360":
        final_def=official
    elif choice=="Créer une formulation combinée":
        seed=personal if normalize(personal)==normalize(official) else (personal + (" — " + official if official else ""))
        final_def=st.text_area("Votre formulation combinée",value=seed,key=f"{prefix}_combined",height=110)
    elif choice=="Modifier manuellement ma définition":
        final_def=st.text_area("Votre définition modifiée",value=personal,key=f"{prefix}_manual",height=110)
    signature=normalize(choice+" | "+final_def)
    confirmed_key=f"{prefix}_definition_confirmed"; signature_key=f"{prefix}_definition_signature"
    if st.session_state.get(signature_key)!=signature:
        st.session_state[confirmed_key]=False; st.session_state[signature_key]=signature
    if st.button("Valider la définition retenue",type="primary",disabled=not bool(final_def.strip()),key=f"{prefix}_confirm_definition",use_container_width=True):
        st.session_state[confirmed_key]=True; st.session_state[signature_key]=signature; st.rerun()
    confirmed=bool(st.session_state.get(confirmed_key,False) and st.session_state.get(signature_key)==signature)
    return choice,final_def,confirmed

def render_modules_home() -> None:
    if not st.session_state.get("prerequisite_confirmed"):
        st.session_state.active_module="module_1"
        render_module_1()
        return
    st.title("Mon parcours de recherche de valeurs")
    labels={"module_1":("MODULE 1","Prérequis"),"module_2":("MODULE 2","Faisons connaissance"),"module_3":("MODULE 3","Valider ou revoir une valeur"),"module_4":("MODULE 4","Rechercher une nouvelle valeur"),"module_5":("MODULE 5","Mes rapports")}
    st.markdown("""<style>
    .cl360-module-card{min-height:126px;padding:18px 22px;border:1px solid #d9e2ec;border-radius:14px;background:#fff;display:flex;flex-direction:column;justify-content:center;margin-bottom:8px}
    .cl360-module-number{font-size:.78rem;font-weight:800;letter-spacing:.12em;color:#556575;margin-bottom:7px}
    .cl360-module-title{font-size:1.18rem;font-weight:750;line-height:1.25;color:#14213d;margin-bottom:8px}
    .cl360-module-status{font-size:.86rem;color:#5f6b78}
    </style>""",unsafe_allow_html=True)
    for mid in MODULE_LABELS:
        state=_module_state(mid); status=state.get("status","non_commence")
        status_label={"termine":"✓ Terminé","en_cours":"● En cours","disponible":"Disponible","indisponible":"Indisponible","non_commence":"Non commencé"}.get(status,status)
        number,title=labels[mid]
        with st.container(border=False):
            c1,c2=st.columns([4,1],vertical_alignment="center")
            with c1:
                st.markdown(f'<div class="cl360-module-card"><div class="cl360-module-number">{number}</div><div class="cl360-module-title">{html.escape(title)}</div><div class="cl360-module-status">{status_label}</div></div>',unsafe_allow_html=True)
            with c2:
                if st.button("Ouvrir",key=f"home_open_{mid}",use_container_width=True,disabled=status=="indisponible"):
                    st.session_state.active_module=mid; st.session_state.page="Modules"; st.rerun()

def render_module_1() -> None:
    st.title("Prérequis — valeurs déjà validées avec l’accompagnateur")
    state=_module_state("module_1")
    if state.get("status")=="termine":
        st.success("Ce prérequis est clôturé.")
        for item in [x for x in st.session_state.central_validated_values if x.get("source")=="accompagnateur"]:
            with st.container(border=True):
                st.markdown(f"### {item.get('nom_final','')}")
                st.markdown("**Définition retenue**"); st.write(item.get("definition_personnelle") or "Non renseignée")
        if st.button("← Retour à l’accueil du parcours",use_container_width=True,key="m1_back_home"):
            st.session_state.active_module="accueil_modules"; st.rerun()
        return
    _set_module_status("module_1","en_cours",state.get("step","intro"))
    if not st.session_state.get("module1_count"):
        st.warning("Ce prérequis est obligatoire pour accéder à l’application.")
        answer=st.radio("Avez-vous déjà identifié et validé au moins une valeur avec votre accompagnateur ?",["Choisissez une réponse","Oui","Non"],key="m1_gate_yesno")
        if answer=="Non":
            st.error("Le parcours ne peut pas commencer. Reprenez d’abord cette étape avec votre accompagnateur.")
            return
        if answer!="Oui": return
        count=int(st.number_input("Combien de valeurs avez-vous déjà identifiées et validées avec votre accompagnateur ?",min_value=1,max_value=15,value=1))
        if st.button("Commencer le prérequis",type="primary",use_container_width=True):
            st.session_state.module1_count=count; st.session_state.module1_index=0; st.session_state.current_value_work=_new_value_work("accompagnateur"); st.rerun()
        return
    idx=int(st.session_state.module1_index); total=int(st.session_state.module1_count)
    labels=["Première","Deuxième","Troisième","Quatrième","Cinquième","Sixième","Septième","Huitième","Neuvième","Dixième"]
    label=labels[idx] if idx < len(labels) else f"Valeur {idx+1}"
    st.markdown(f"## {label} valeur validée en séance — {idx+1} sur {total}")
    st.progress(min(1.0,(idx+1)/max(1,total)))
    work=st.session_state.current_value_work or _new_value_work("accompagnateur")
    name=open_response_widget("Quelle valeur avez-vous identifiée et validée avec votre accompagnateur ?",f"m1_name_{idx}",value=work.get("nom_initial",""),height=70,allow_reformulation=False,expected_value_label=True,question_kind="word")
    if not name: return
    work["nom_initial"]=name; work["nom_normalise"]=_normalise_value_name(name); work["nom_final"]=work["nom_normalise"]
    definition=open_response_widget("Que signifie précisément cette valeur pour vous ?",f"m1_def_{idx}",value=work.get("definition_personnelle",""),height=110,dependency_scope="prerequisites",value_name=name)
    if not definition: return
    work["definition_personnelle"]=definition
    info=_referential_value_info(work["nom_final"]); work["present_referentiel"]=bool(info); work["definition_clarte360"]=info.get("definition","")
    choice,final_def,definition_confirmed=_value_definition_choices(work,f"m1_{idx}",allow_ai_rewrite=False)
    if not definition_confirmed: return
    st.markdown("### Questionnaire spécifique HEC")
    value_label=work.get("nom_final") or work.get("nom_normalise") or work.get("nom_initial") or "cette valeur"
    important=st.radio(f'Pour vous, la valeur « {value_label} » est-elle importante ?', ["Choisissez","Oui","Non"],key=f"m1_q1_{idx}")
    very=st.radio(f'Pour vous, la valeur « {value_label} » est-elle très importante ?', ["Choisissez","Oui","Non"],key=f"m1_q2_{idx}") if important=="Oui" else "Non"
    fundamental=st.radio(f'Pour vous, la valeur « {value_label} » est-elle fondamentale ?', ["Choisissez","Oui","Non"],key=f"m1_q3_{idx}") if very=="Oui" else "Non"
    complete=not (important=="Choisissez" or (important=="Oui" and very=="Choisissez") or (very=="Oui" and fundamental=="Choisissez"))
    if st.button("Valider cette valeur et poursuivre",type="primary",disabled=not complete,key=f"m1_save_{idx}",use_container_width=True):
        q={"importante":important=="Oui","tres_importante":very=="Oui","fondamentale":fundamental=="Oui"}
        _upsert_central_value(work["nom_final"],final_def,"accompagnateur",definition_clarte360=work.get("definition_clarte360",""),questionnaire=q,protected=True,work=work)
        st.session_state.module1_index=idx+1; st.session_state.current_value_work=_new_value_work("accompagnateur")
        if idx+1>=total:
            st.session_state.prerequisite_confirmed=True
            _set_module_status("module_1","termine","termine")
            _set_module_status("module_2","disponible","questionnaire")
            _set_module_status("module_3","disponible","accueil")
            _set_module_status("module_4","disponible","complement_connaissance")
            st.session_state.active_module="accueil_modules"
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
    st.caption("Une question à la fois. L’IA intervient uniquement pour corriger ou reformuler votre réponse, jamais pour vous analyser.")
    _hydrate_module2_answers()
    state=_module_state("module_2")
    answers=st.session_state.module2_answers
    completed=state.get("status")=="termine"
    if not completed:
        _set_module_status("module_2","en_cours","questionnaire")
    idx=int(st.session_state.get("module2_question_index",0))
    idx=max(0,min(idx,len(MODULE2_QUESTIONS)))
    if completed:
        idx=len(MODULE2_QUESTIONS)

    # Les questions déjà traitées utilisent exactement le même composant que le Module 3 :
    # grande question, réponse enregistrée et modification permanente (nouvelle saisie,
    # correction manuelle ou reformulation Clarté360).
    for q in MODULE2_QUESTIONS[:idx]:
        qid=q["id"]
        value=str(answers.get(qid,"") or "").strip()
        if not value:
            continue
        retained=open_response_widget(
            q["text"], f"m2_{qid}", value=value, height=110,
            dependency_scope="profile", allow_reformulation=True,
        )
        if retained and retained!=value:
            answers[qid]=retained
            st.session_state.beneficiary_profile={
                "questions":deepcopy(answers),
                "presentation_libre":"\n\n".join(v for v in answers.values() if v),
                "date":now_iso(),
            }
            business_trace("module2_reponse_modifiee",qid)

    if completed:
        st.success("Vos réponses sont enregistrées. Vous pouvez modifier chacune d’elles à tout moment, manuellement ou avec une reformulation Clarté360.")
        if st.button("← Retour à l’accueil du parcours",use_container_width=True,key="m2_back_home"):
            st.session_state.active_module="accueil_modules"; st.session_state.page="Modules"; st.rerun()
        return

    q=MODULE2_QUESTIONS[idx]
    st.progress(idx/len(MODULE2_QUESTIONS))
    st.caption(f"Question {idx+1} sur {len(MODULE2_QUESTIONS)} — {q['rubrique']}")
    val=open_response_widget(
        q["text"], f"m2_{q['id']}", value=answers.get(q["id"],""), height=110,
        dependency_scope="profile", allow_reformulation=True,
        help_text="Prenez votre temps. Vous pouvez répondre à l’écrit ou à l’oral, même si vous cherchez vos mots ou vous reprenez. L’objectif est simplement de mieux comprendre votre situation et votre parcours.",
    )
    if val:
        answers[q["id"]]=val
        c1,c2=st.columns(2)
        with c1:
            if st.button("← Retour au parcours",use_container_width=True,key=f"m2_back_{idx}"):
                st.session_state.active_module="accueil_modules"; st.rerun()
        with c2:
            if st.button("Continuer",type="primary",key=f"m2_next_{idx}",use_container_width=True):
                st.session_state.module2_question_index=idx+1
                st.session_state.beneficiary_profile={
                    "questions":deepcopy(answers),
                    "presentation_libre":"\n\n".join(v for v in answers.values() if v),
                    "date":now_iso(),
                }
                if idx+1>=len(MODULE2_QUESTIONS):
                    _set_module_status("module_2","termine","consultation")
                    st.session_state.profile_complete=True
                    st.session_state.active_module="accueil_modules"
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
    """Quitte la valeur courante sans la modifier et la remet dans son panier d'origine."""
    work=st.session_state.get("current_value_work",{}) or {}
    _restore_current_module3_origin(work)
    business_trace("abandon_valeur_courante",work.get("nom_final") or work.get("nom_initial") or work.get("terme") or "")
    _advance_module3()

def _stop_module3_series() -> None:
    """Arrête les valeurs restantes sans supprimer celles déjà complètement validées, et restaure la valeur courante dans son état d'origine."""
    work=st.session_state.get("current_value_work",{}) or {}
    _restore_current_module3_origin(work)
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
        review=st.session_state.get("session_review_items",[])
        hypotheses=st.session_state.get("hypothesis_basket",[])
        options=["Saisir une nouvelle valeur"]+(["Examiner une hypothèse conservée"] if hypotheses else [])+(["Examiner une valeur en attente"] if pending else [])+(["Reprendre un sujet à revoir en séance"] if review else [])+(["Réexaminer une valeur déjà validée dans Clarté360"] if any(v.get('source')!='accompagnateur' for v in st.session_state.central_validated_values) else [])
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
        elif mode=="Examiner une hypothèse conservée":
            selected=st.selectbox("Hypothèse conservée",range(len(hypotheses)),format_func=lambda i:hypotheses[i].get("nom") or "Hypothèse",key="m3_hypothesis_select")
            chosen=hypotheses[selected]
            with st.container(border=True):
                st.markdown(f"### {chosen.get('nom','')}")
                st.write(chosen.get("definition_clarte360","") or "Définition non disponible.")
                context=chosen.get("question_reponses",[]) or []
                if context:
                    st.caption("Contexte utile enregistré dans le Module 4")
                    for exchange in context[-3:]:
                        st.write(f"**Clarté360 :** {exchange.get('question','')}")
                        st.write(f"**Vous :** {exchange.get('reponse_validee','')}")
            decision=st.radio("Que souhaitez-vous faire ?",["Choisissez une décision","Commencer l’examen de cette hypothèse","La conserver pour plus tard","La supprimer définitivement"],key=f"m3_hypothesis_decision_{chosen.get('id','')}")
            if st.button("Valider cette décision",type="primary",use_container_width=True,disabled=decision=="Choisissez une décision",key="m3_hypothesis_validate"):
                if decision=="La conserver pour plus tard":
                    business_trace("hypothese_conservee_plus_tard",chosen.get("nom","")); st.success("L’hypothèse reste dans le Panier Hypothèses."); st.rerun()
                elif decision=="La supprimer définitivement":
                    st.session_state.hypothesis_basket=[x for i,x in enumerate(hypotheses) if i!=selected]
                    st.session_state.setdefault("hypothesis_history",[]).append({"date":now_iso(),"nom":chosen.get("nom",""),"statut":"supprimee_definitivement","source":"module_4"})
                    business_trace("hypothese_supprimee",chosen.get("nom","")); st.rerun()
                else:
                    work=_new_value_work("hypothese_module4")
                    work.update({"nom_initial":chosen.get("nom",""),"nom_normalise":_normalise_value_name(chosen.get("nom","")),"nom_final":_normalise_value_name(chosen.get("nom","")),"definition_clarte360":chosen.get("definition_clarte360",""),"source":"examen_hypothese","origin_snapshot":deepcopy(chosen),"original_name":chosen.get("nom",""),"stage":"definition","contexte_module4":deepcopy(chosen.get("question_reponses",[]))})
                    st.session_state.hypothesis_basket=[x for i,x in enumerate(hypotheses) if i!=selected]
                    st.session_state.module3_queue=[work]; st.session_state.module3_index=0; st.session_state.current_value_work=work
                    business_trace("hypothese_ouverte_module3",chosen.get("nom","")); st.rerun()
        elif mode=="Examiner une valeur en attente":
            selected=st.selectbox("Valeur à examiner",range(len(pending)),format_func=lambda i:pending[i].get("nom_final") or pending[i].get("nom_initial") or "Valeur")
            chosen=pending[selected]
            _pending_value_summary(chosen)
            c1,c2,c3=st.columns(3)
            with c1:
                if st.button("← Retour sans modifier",use_container_width=True,key="m3_pending_back"):
                    st.session_state.active_module="accueil_modules"; st.rerun()
            with c2:
                if st.button("🗑️ Supprimer définitivement",use_container_width=True,key="m3_pending_delete"):
                    st.session_state["m3_confirm_delete_pending"]=True; st.rerun()
            with c3:
                if st.button("Poursuivre l’examen de cette valeur",type="primary",use_container_width=True,key="m3_pending_open"):
                    work=deepcopy(chosen)
                    work["origin_snapshot"]=deepcopy(chosen)
                    work["source_initiale"]=work.get("source","")
                    work["source"]="examen_attente"
                    work["original_name"]=work.get("nom_final") or work.get("nom_normalise") or work.get("nom_initial") or work.get("nom") or ""
                    work["pending_origin_id"]=work.get("id","")
                    work["stage"]="nom"
                    st.session_state.values_to_examine=[x for i,x in enumerate(pending) if i!=selected]
                    st.session_state.module3_queue=[work]; st.session_state.module3_index=0; st.session_state.current_value_work=work; st.rerun()
            if st.session_state.get("m3_confirm_delete_pending"):
                st.error("Cette suppression effacera définitivement cette valeur et toutes les informations qui lui sont associées. Cette action est irréversible.")
                d1,d2=st.columns(2)
                with d1:
                    if st.button("Annuler la suppression",use_container_width=True,key="m3_cancel_delete_pending"):
                        st.session_state.pop("m3_confirm_delete_pending",None); st.rerun()
                with d2:
                    if st.button("Confirmer la suppression définitive",type="primary",use_container_width=True,key="m3_do_delete_pending"):
                        _purge_value_everywhere(chosen.get("nom_final") or chosen.get("nom_initial") or chosen.get("nom") or ""); st.session_state.pop("m3_confirm_delete_pending",None); st.rerun()
        elif mode=="Reprendre un sujet à revoir en séance":
            selected=st.selectbox("Sujet à reprendre en séance",range(len(review)),format_func=lambda i:review[i].get("terme") or "Sujet")
            chosen=review[selected]
            _pending_value_summary(chosen)
            c1,c2,c3=st.columns(3)
            with c1:
                if st.button("← Retour sans modifier",use_container_width=True,key="m3_review_back"):
                    st.session_state.active_module="accueil_modules"; st.rerun()
            with c2:
                if st.button("🗑️ Supprimer définitivement",use_container_width=True,key="m3_review_delete"):
                    st.session_state["m3_confirm_delete_review"]=True; st.rerun()
            with c3:
                if st.button("Reprendre l’étude en séance",type="primary",use_container_width=True,key="m3_review_open"):
                    work=_new_value_work("examen_seance")
                    work.update({"original_name":chosen.get("terme", ""),"nom_initial":chosen.get("terme", ""),"nom_final":chosen.get("terme", ""),"definition_personnelle":chosen.get("definition", ""),"analyse":chosen.get("analyse", ""),"clarifications":deepcopy(chosen.get("clarifications",[])),"origin_snapshot":deepcopy(chosen),"pending_origin_id":chosen.get("id","")})
                    st.session_state.session_review_items=[x for i,x in enumerate(review) if i!=selected]
                    st.session_state.module3_queue=[work]; st.session_state.module3_index=0; st.session_state.current_value_work=work; st.rerun()
            if st.session_state.get("m3_confirm_delete_review"):
                st.error("Cette suppression effacera définitivement ce sujet et toutes les informations qui lui sont associées. Cette action est irréversible.")
                d1,d2=st.columns(2)
                with d1:
                    if st.button("Annuler la suppression",use_container_width=True,key="m3_cancel_delete_review"):
                        st.session_state.pop("m3_confirm_delete_review",None); st.rerun()
                with d2:
                    if st.button("Confirmer la suppression définitive",type="primary",use_container_width=True,key="m3_do_delete_review"):
                        _purge_value_everywhere(chosen.get("terme", "")); st.session_state.pop("m3_confirm_delete_review",None); st.rerun()
        else:
            candidates=[v for v in st.session_state.central_validated_values if v.get("source")!="accompagnateur"]
            selected=st.selectbox("Valeur à réexaminer",range(len(candidates)),format_func=lambda i:candidates[i]["nom_final"])
            original=candidates[selected]
            with st.container(border=True):
                st.markdown(f"### {original.get('nom_final','')}")
                st.write(f"**Définition personnelle actuelle :** {original.get('definition_personnelle') or 'Non renseignée'}")
                if original.get("definition_clarte360"): st.write(f"**Définition Clarté360 :** {original.get('definition_clarte360')}")
            st.warning("Réexaminer cette valeur signifie reprendre sa définition et répondre de nouveau au questionnaire spécifique, même si vous ne changez rien. Vous pourrez annuler à tout moment avant la décision finale : la valeur restera alors inchangée.")
            c1,c2,c3=st.columns(3)
            with c1:
                if st.button("← Annuler",use_container_width=True,key="m3_reex_back"):
                    st.session_state.active_module="accueil_modules"; st.rerun()
            with c2:
                if st.button("🗑️ Supprimer définitivement",use_container_width=True,key="m3_reex_delete"):
                    st.session_state["m3_confirm_delete_validated"]=True; st.rerun()
            with c3:
                if st.button("Commencer le réexamen",type="primary",use_container_width=True,key="m3_reex_start"):
                    w=_new_value_work("reexamen"); w.update({"original_name":original["nom_final"],"nom_initial":original["nom_final"],"nom_final":original["nom_final"],"mode_decouverte":original.get("mode_decouverte") or "Par introspection","definition_personnelle":original.get("definition_personnelle",""),"definition_clarte360":original.get("definition_clarte360",""),"origin_snapshot":deepcopy(original)})
                    st.session_state.module3_queue=[w]; st.session_state.module3_index=0; st.session_state.current_value_work=w; st.rerun()
            if st.session_state.get("m3_confirm_delete_validated"):
                st.error("Cette suppression effacera définitivement cette valeur validée et toutes les informations qui lui sont associées. Cette action est irréversible.")
                d1,d2=st.columns(2)
                with d1:
                    if st.button("Annuler la suppression",use_container_width=True,key="m3_cancel_delete_validated"):
                        st.session_state.pop("m3_confirm_delete_validated",None); st.rerun()
                with d2:
                    if st.button("Confirmer la suppression définitive",type="primary",use_container_width=True,key="m3_do_delete_validated"):
                        _purge_value_everywhere(original.get("nom_final", "")); st.session_state.pop("m3_confirm_delete_validated",None); st.rerun()
        return
    idx=int(st.session_state.module3_index); total=len(st.session_state.module3_queue); work=_module3_current_work()
    st.markdown(f"<div style='background:#EAF7F6;border:2px solid #0E7774;border-radius:12px;padding:.75rem 1rem;text-align:center;margin-bottom:1rem'><strong style='font-size:1.45rem;color:#0E7774'>Valeur {idx+1} / {total}</strong></div>",unsafe_allow_html=True)
    # Sorties permanentes : aucun écran du module 3 ne peut être une impasse.
    nav1,nav2,nav3=st.columns(3)
    with nav1:
        if st.button("← Retour au choix des valeurs",use_container_width=True,key=f"m3_exit_{work['id']}"):
            _restore_current_module3_origin(work); st.session_state.module3_queue=[]; st.session_state.current_value_work={}; st.session_state.module3_index=0; _set_module_status("module_3","disponible","accueil"); st.rerun()
    with nav2:
        if st.button("Abandonner ce réexamen",use_container_width=True,key=f"m3_cancel_work_{work['id']}"):
            _abandon_current_module3_value(); st.rerun()
    with nav3:
        if st.button("🗑️ Supprimer définitivement",use_container_width=True,key=f"m3_delete_work_{work['id']}"):
            st.session_state[f"m3_confirm_delete_work_{work['id']}"]=True; st.rerun()
    if st.session_state.get(f"m3_confirm_delete_work_{work['id']}"):
        st.error("Cette suppression effacera définitivement cette valeur et toutes les informations qui lui sont associées. Cette action est irréversible.")
        d1,d2=st.columns(2)
        with d1:
            if st.button("Annuler",use_container_width=True,key=f"m3_cancel_delete_work_{work['id']}"):
                st.session_state.pop(f"m3_confirm_delete_work_{work['id']}",None); st.rerun()
        with d2:
            if st.button("Confirmer la suppression définitive",type="primary",use_container_width=True,key=f"m3_confirm_delete_work_btn_{work['id']}"):
                _purge_value_everywhere(work.get("original_name",""),work.get("nom_final",""),work.get("nom_initial",""),work.get("terme","")); st.session_state.pop(f"m3_confirm_delete_work_{work['id']}",None); st.session_state.module3_queue=[]; st.session_state.current_value_work={}; st.session_state.module3_index=0; _set_module_status("module_3","disponible","accueil"); st.rerun()
    if work.get("source") in {"migration_v2137","module_4","recherche_guidee","examen_attente","examen_seance"}: _pending_value_summary(work)
    name=open_response_widget("Quelle valeur avez-vous identifiée ?",f"m3_name_{work['id']}",value=work.get("nom_initial",work.get("nom_final","")),height=70,allow_reformulation=False,expected_value_label=True, question_kind="word")
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
    own_pending=work.get("source")=="examen_attente" and normalize(canonical)==normalize(_normalise_value_name(work.get("original_name","")))
    own_review=work.get("source")=="examen_seance" and normalize(canonical)==normalize(_normalise_value_name(work.get("original_name","")))
    # Compatibilité : ancien contrôle = not (own_reexam or own_pending) ; ajout du cas séance.
    if location and not (own_reexam or own_pending or own_review):
        labels={"validee":"vos valeurs validées","a_examiner":"vos valeurs à examiner","a_explorer":"vos pistes À explorer — Module 4","a_revoir":"votre liste À revoir en séance"}
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
    # Une valeur reconnue au référentiel poursuit toujours son examen.
    # Sa définition personnelle ne peut jamais bloquer le questionnaire spécifique.
    if info:
        nature={
            "decision":"valeur_reconnue",
            "explication":"Cette valeur figure dans le référentiel Clarté360. Vous pouvez conserver votre définition personnelle, la modifier ou demander une reformulation avant de poursuivre.",
            "question":"",
            "alerte_definition":"",
            "definition_proposee":"",
        }
        st.session_state[analysis_key]=nature
        st.session_state[analysis_sig_key]=analysis_signature
    else:
        if st.session_state.get(analysis_sig_key)!=analysis_signature:
            st.session_state[analysis_key]=analyse_concept_nature(canonical,definition,current_clarification)
            st.session_state[analysis_sig_key]=analysis_signature
        nature=st.session_state[analysis_key]
    decision=nature.get("decision","")
    work["analyse"]=nature.get("explication","")
    work["nature_decision"]=decision
    if not info and nature.get("definition_proposee"):
        work["definition_clarte360"]=str(nature.get("definition_proposee") or "").strip()
        st.markdown("**Définition proposée par Clarté360**")
        st.info(work["definition_clarte360"])
    if decision=="formulation_non_valeur":
        st.warning(nature.get("explication") or "Votre définition semble actuellement mettre davantage l’accent sur un besoin, un état recherché ou un résultat.")
        st.info("Cette observation est uniquement une invitation à préciser votre formulation. Elle ne bloque jamais votre parcours : vous pouvez conserver votre définition, la modifier ou poursuivre directement vers le questionnaire spécifique.")
    elif decision=="valeur_absente_possible":
        st.info((nature.get("explication") or "Cette valeur ne figure pas dans le référentiel Clarté360, mais elle peut constituer une valeur personnelle.")+" Vous pouvez poursuivre son examen ; son absence du catalogue n'est pas une erreur.")
    elif decision=="valeur_reconnue":
        st.success(nature.get("explication") or "Le nom correspond à une valeur reconnue et peut poursuivre son examen.")

    # En réexamen, le panier et la valeur sont déjà choisis : aucune nouvelle orientation
    # n'est imposée. On passe directement au choix de définition puis au questionnaire.
    direct_to_questionnaire = work.get("source")=="reexamen"
    if not direct_to_questionnaire:
        st.markdown("### Choisissez la suite la plus utile")
        st.caption("Chaque choix correspond à un parcours différent. Votre terme ne sera placé que dans un seul panier actif.")
        conceptual=st.radio(
            "Comment souhaitez-vous poursuivre ?",
            [
                "Poursuivre l’examen maintenant dans le Module 3",
                "Conserver dans Valeurs à examiner",
                "Envoyer vers À explorer — Module 4",
                "Placer dans À revoir en séance",
            ],
            key=f"m3_concept_{work['id']}",on_change=mark_user_activity,args=("choix_orientation_valeur",)
        )
        explanations={
            "Poursuivre l’examen maintenant dans le Module 3":"Vous continuez immédiatement la définition et le questionnaire spécifique du Module 3.",
            "Conserver dans Valeurs à examiner":"Vous reprendrez plus tard ce même examen, seul, dans le Module 3.",
            "Envoyer vers À explorer — Module 4":"Le Module 4 reprendra ce terme avec un questionnement vertical pour comprendre ce qu'il recouvre réellement.",
            "Placer dans À revoir en séance":"Vous préférez en discuter avec votre accompagnateur, qui pourra ensuite le remettre dans le parcours le plus adapté.",
        }
        st.info(explanations[conceptual])
        if conceptual=="Conserver dans Valeurs à examiner":
            if st.button("Confirmer : conserver pour plus tard",type="primary",use_container_width=True,key=f"m3_pending_{work['id']}"):
                _save_work_for_later(work); _finish_module3_orientation(); st.rerun()
            return
        if conceptual=="Envoyer vers À explorer — Module 4":
            if st.button("Confirmer : explorer dans le Module 4",type="primary",use_container_width=True,key=f"m3_explore_{work['id']}"):
                _send_work_to_explore(work); _finish_module3_orientation(); st.rerun()
            return
        if conceptual=="Placer dans À revoir en séance":
            if st.button("Confirmer : revoir avec mon accompagnateur",type="primary",use_container_width=True,key=f"m3_review_{work['id']}"):
                _add_review_item(work,"Décision du bénéficiaire : en discuter avec l’accompagnateur avant de poursuivre"); business_trace("valeur_a_revoir_en_seance",canonical); _finish_module3_orientation(); st.rerun()
            return
    choice,final_def,definition_confirmed=_value_definition_choices(work,f"m3_{work['id']}")
    work["definition_finale"]=final_def
    if not definition_confirmed:
        return
    st.markdown("### Questionnaire spécifique HEC")
    value_label=canonical or work.get("nom_final") or work.get("nom_normalise") or work.get("nom_initial") or "cette valeur"
    important=st.radio(f'Pour vous, la valeur « {value_label} » est-elle importante ?', ["Choisissez","Oui","Non"],key=f"m3_q1_{work['id']}",on_change=mark_user_activity,args=("questionnaire_valeur_q1",))
    very=st.radio(f'Pour vous, la valeur « {value_label} » est-elle très importante ?', ["Choisissez","Oui","Non"],key=f"m3_q2_{work['id']}",on_change=mark_user_activity,args=("questionnaire_valeur_q2",)) if important=="Oui" else "Non"
    fundamental=st.radio(f'Pour vous, la valeur « {value_label} » est-elle fondamentale ?', ["Choisissez","Oui","Non"],key=f"m3_q3_{work['id']}",on_change=mark_user_activity,args=("questionnaire_valeur_q3",)) if very=="Oui" else "Non"
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
                _finalise_pending_history(work,"non_retenue",canonical)
            _advance_module3(); st.rerun()

def _advance_module3() -> None:
    idx=int(st.session_state.module3_index)+1
    st.session_state.module3_index=idx
    if idx<len(st.session_state.module3_queue): st.session_state.current_value_work=st.session_state.module3_queue[idx]
    else:
        st.session_state.module3_queue=[]; st.session_state.current_value_work={}; _set_module_status("module_3","termine","accueil")

def _module4_knowledge_answer(exercise: dict[str,Any]) -> dict[str,Any]:
    return deepcopy(st.session_state.get("module4_knowledge_answers",{}).get(exercise["id"],{}))

def _module4_save_knowledge_answer(exercise: dict[str,Any], answer: Any, status: str="termine") -> None:
    answers=deepcopy(st.session_state.get("module4_knowledge_answers",{}))
    previous=answers.get(exercise["id"],{})
    answers[exercise["id"]]={
        "id":exercise["id"], "version":exercise["version"], "type":exercise["type"],
        "titre":exercise["title"], "question":exercise["prompt"],
        "propositions":deepcopy(exercise["options"]), "reponse":deepcopy(answer),
        "statut":status, "date_heure":now_iso(), "modifiee":bool(previous),
    }
    st.session_state.module4_knowledge_answers=answers
    st.session_state.data_revision=int(st.session_state.get("data_revision",0))+1
    business_trace("module4_complement_reponse",f"{exercise['id']}:{status}")

def _module4_complete_knowledge() -> None:
    st.session_state.module4_knowledge_completed=True
    st.session_state.module4_knowledge_completed_at=now_iso()
    st.session_state.module4_knowledge_index=len(MODULE4_KNOWLEDGE_EXERCISES)
    _set_module_status("module_4","en_cours","choix_voie")
    business_trace("module4_complement_termine",MODULE4_KNOWLEDGE_VERSION)

def _module4_validated_value_labels() -> list[str]:
    """Liste dédupliquée des valeurs déjà validées, sans interprétation."""
    names=[]
    for item in st.session_state.get("central_validated_values",[]) or []:
        name=str(item.get("nom_final","") or "").strip()
        if name and normalize(name) not in {normalize(x) for x in names}: names.append(name)
    if not names:
        for name in validated_names():
            if name and normalize(name) not in {normalize(x) for x in names}: names.append(name)
    return names


def _module4_intro_text() -> str:
    values=_module4_validated_value_labels()
    values_text=", ".join(values) if values else "certaines valeurs déjà identifiées"
    return (
        f"Vous avez déjà identifié et validé plusieurs valeurs importantes pour vous, notamment : {values_text}. "
        "Dans cette nouvelle étape, nous allons vous aider à explorer d’autres pistes possibles. "
        "À partir de ce que vous racontez, de ce que vous ressentez et de ce que vous avez déjà partagé, "
        "Clarté360 pourra vous proposer une ou plusieurs hypothèses de valeurs. "
        "Ces propositions ne sont jamais des conclusions. Nous ne pouvons pas savoir à votre place si une valeur vous correspond réellement. "
        "Vous restez libre d’accepter une hypothèse, de la conserver pour plus tard ou de la refuser. "
        "Une hypothèse acceptée sera enregistrée uniquement dans votre panier Hypothèses. "
        "Elle ne deviendra pas automatiquement une valeur. Plus tard, depuis le module 3, vous pourrez décider de l’examiner et, seulement si elle vous correspond réellement, de la valider."
    )


def _module4_render_choice() -> None:
    st.title("Rechercher une nouvelle valeur avec Clarté360")
    st.success("Le complément de connaissance a déjà été réalisé. Il ne sera pas rejoué automatiquement.")
    intro=_module4_intro_text()
    st.markdown("### Avant de commencer")
    st.info(intro)
    speak_button(intro,"m4_intro_hypotheses")
    st.caption("Il est tout à fait possible qu’aucune nouvelle valeur n’émerge. Ce n’est ni un échec ni une obligation d’en trouver une.")
    st.markdown("### Comment souhaitez-vous poursuivre ?")
    c1,c2=st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("#### 1. Partir d’une situation que j’ai observée")
            txt="Racontez une situation récente ou marquante qui vous a fait agir, réagir, vous réjouir, vous déranger ou vous toucher. Nous chercherons ensuite, avec prudence, si elle fait apparaître une autre piste que vos valeurs déjà validées."
            st.write(txt); speak_button(txt,"m4_choice_way1")
            if st.button("Choisir cette voie",type="primary",use_container_width=True,key="m4_choose_way1"):
                st.session_state.module4_route="situation"; _set_module_status("module_4","en_cours","voie_1_situation"); business_trace("module4_voie_choisie","situation"); st.rerun()
    with c2:
        with st.container(border=True):
            st.markdown("#### 2. Aidez-moi à trouver une piste")
            txt="Clarté360 utilisera ce que vous avez déjà partagé, le complément de connaissance, vos valeurs validées et les pistes déjà explorées pour vous proposer quelques questions personnalisées, sans établir de profil et sans vous attribuer de valeur."
            st.write(txt); speak_button(txt,"m4_choice_way2")
            if st.button("Choisir cette voie",type="primary",use_container_width=True,key="m4_choose_way2"):
                st.session_state.module4_route="questions_personnalisees"; _set_module_status("module_4","en_cours","voie_2_preparation"); business_trace("module4_voie_choisie","questions_personnalisees"); st.rerun()
    tracks=st.session_state.get("clarification_tracks",[])
    if tracks:
        st.markdown("### Reprendre une piste mise en attente")
        with st.container(border=True):
            st.markdown("#### 3. Explorer une piste à clarifier")
            st.write("Reprenez une formulation qui n’a pas pu être examinée comme valeur dans le Module 3. Clarté360 utilisera les éléments déjà saisis et le même moteur de questionnement vertical que dans les deux autres voies.")
            if st.button("Choisir cette voie",type="primary",use_container_width=True,key="m4_choose_way3"):
                st.session_state.module4_route="piste_clarifier"; st.session_state.module4_current_cycle={}; _set_module_status("module_4","en_cours","voie_3_piste_clarifier"); business_trace("module4_voie_choisie","piste_clarifier"); st.rerun()

    with st.expander("Consulter mes réponses au complément de connaissance",expanded=False):
        answers=st.session_state.get("module4_knowledge_answers",{})
        for exercise in MODULE4_KNOWLEDGE_EXERCISES:
            item=answers.get(exercise["id"],{})
            with st.container(border=True):
                st.markdown(f"**{exercise['title']}**")
                response=item.get("reponse")
                if isinstance(response,list):
                    for i,value in enumerate(response,1): st.write(f"{i}. {value}")
                else: st.write(response or "Non répondu")
                st.caption("Cette réponse n’est ni un score, ni un profil, ni une valeur attribuée.")
    if st.button("← Retour à l’accueil du parcours",use_container_width=True,key="m4_choice_back_home"):
        st.session_state.active_module="accueil_modules"; st.rerun()


def _module4_all_known_names() -> set[str]:
    names={normalize(x) for x in _module4_validated_value_labels()}
    for item in st.session_state.get("values_to_examine",[]): names.add(normalize(item.get("nom_final") or item.get("nom_normalise") or item.get("nom_initial") or ""))
    for item in st.session_state.get("session_review_items",[]): names.add(normalize(item.get("nom") or item.get("nom_final") or ""))
    for item in st.session_state.get("hypothesis_basket",[]): names.add(normalize(item.get("nom") or ""))
    for item in st.session_state.get("rejected_values",[]): names.add(normalize(item.get("nom") or ""))
    return {x for x in names if x}


def _module4_context_payload() -> dict[str,Any]:
    return {
        "module2":deepcopy(st.session_state.get("module2_answers") or st.session_state.get("beneficiary_profile",{}).get("questions",{})),
        "complement_connaissance":deepcopy(st.session_state.get("module4_knowledge_answers",{})),
        "valeurs_validees":_module4_validated_value_labels(),
        "valeurs_a_examiner":[x.get("nom_final") or x.get("nom_normalise") or x.get("nom_initial") for x in st.session_state.get("values_to_examine",[])],
        "a_revoir_en_seance":[x.get("nom") or x.get("nom_final") for x in st.session_state.get("session_review_items",[])],
        "panier_hypotheses":[x.get("nom") for x in st.session_state.get("hypothesis_basket",[])],
        "hypotheses_refusees":[x.get("nom") for x in st.session_state.get("rejected_values",[])],
        "memoire_questions_reponses":deepcopy(st.session_state.get("module4_question_memory",[])),
    }



MODULE4_WORD_QUESTION = "Si vous deviez mettre un mot sur ce qui était le plus important pour vous dans cette situation, lequel serait-il ?"
MODULE4_MAX_VERTICAL_QUESTIONS = 5


def _module4_question_signature(text: str) -> str:
    """Signature déterministe pour bloquer les questions identiques ou quasi identiques."""
    words=[w for w in normalize(text).split() if w not in {"le","la","les","un","une","des","de","du","dans","cette","vous","votre","vos","qui","que","quoi"}]
    return " ".join(words)


def _module4_question_already_asked(cycle: dict[str,Any], question: str) -> bool:
    """Bloque une répétition dans le cycle courant et dans la mémoire du module 4."""
    signature=_module4_question_signature(question)
    if not signature:
        return False
    previous=[_module4_question_signature(x.get("question", "")) for x in cycle.get("exchanges", [])]
    previous += [_module4_question_signature(x.get("question", "")) for x in st.session_state.get("module4_question_memory", [])]
    current_question=_module4_question_signature(cycle.get("question", ""))
    if current_question:
        previous.append(current_question)
    if signature in previous:
        return True
    current=set(signature.split())
    for old in previous:
        old_words=set(old.split())
        if current and old_words and len(current & old_words) / max(1, len(current | old_words)) >= .72:
            return True
    return False


def _module4_distinct_followup(cycle: dict[str,Any]) -> str:
    """Retourne une relance réellement différente lorsque l'IA répète une question."""
    candidates=[
        "Qu'est-ce qui vous a le plus marqué dans cette situation, au-delà du résultat obtenu ?",
        "Qu'auriez-vous voulu rendre possible pour les personnes concernées ?",
        "Qu'est-ce qui aurait été difficilement acceptable pour vous dans la situation inverse ?",
        "Dans votre manière d'agir, qu'est-ce qui comptait le plus pour vous personnellement ?",
        "Retrouvez-vous cette même importance dans d'autres situations de votre vie ? Donnez un exemple concret.",
    ]
    for candidate in candidates:
        if not _module4_question_already_asked(cycle,candidate):
            return candidate
    return MODULE4_WORD_QUESTION


def _module4_no_word_answer(answer: str) -> bool:
    low=normalize(answer)
    exact={"je ne sais pas","aucune idee","rien ne me vient","je ne trouve pas","je n en sais rien","aucun mot"}
    return low in exact or any(x in low for x in ("pas d idee","aucune idee","ne me vient","ne trouve pas de mot"))


def _module4_vertical_count(cycle: dict[str,Any]) -> int:
    return sum(1 for x in cycle.get("exchanges", []) if x.get("role") in {"initial","relance_verticale"})


def _module4_render_exchange_thread(cycle: dict[str,Any]) -> None:
    exchanges=cycle.get("exchanges", [])
    if not exchanges:
        return
    with st.expander("Voir mes questions et réponses validées", expanded=True):
        for exchange in exchanges:
            with st.chat_message("assistant", avatar=str(CHATBOT_PATH) if CHATBOT_PATH.exists() else None):
                st.markdown("**Clarté360**")
                st.write(exchange.get("question", ""))
            with st.chat_message("user"):
                st.markdown("**Vous**")
                st.write(exchange.get("reponse_validee", ""))


def _module4_resolve_source_track(cycle: dict[str,Any], outcome: str, new_hypothesis: str="") -> None:
    """Mutation atomique des paniers lors de la résolution d'une piste à clarifier."""
    source=cycle.get("source_track") or {}
    track_id=cycle.get("track_id") or source.get("id")
    old_name=source.get("terme_initial") or source.get("nom_initial") or ""
    source_work=source.get("elements_source") if isinstance(source.get("elements_source"),dict) else {}
    source_id=source_work.get("pending_origin_id") or source_work.get("id") or source.get("source_value_id")
    aliases=_value_alias_norms(old_name,source_work.get("original_name"),source_work.get("nom_initial"),source_work.get("nom_normalise"),source_work.get("nom_final"))
    if track_id:
        st.session_state.clarification_tracks=[x for x in st.session_state.get("clarification_tracks", []) if x.get("id") != track_id]
    if old_name or source_id:
        st.session_state.values_to_examine=[x for x in st.session_state.get("values_to_examine", []) if not ((source_id and x.get("id")==source_id) or normalize(_normalise_value_name(x.get("nom_final") or x.get("nom_initial") or x.get("nom") or "")) in aliases)]
        # Nettoyer aussi les anciennes listes de reprise qui pourraient ressusciter la piste.
        reprise=st.session_state.get("resume_state",{})
        if isinstance(reprise,dict):
            for key in ("values_to_examine","inter_session_pending"):
                vals=reprise.get(key)
                if isinstance(vals,list):
                    reprise[key]=[x for x in vals if not ((source_id and isinstance(x,dict) and x.get("id")==source_id) or normalize(_normalise_value_name((x.get("nom_final") or x.get("nom_initial") or x.get("nom") or "") if isinstance(x,dict) else x)) in aliases)]
    history=st.session_state.setdefault("clarification_history", [])
    history.append({"date_heure":now_iso(),"track":deepcopy(source),"issue":outcome,"nouvelle_hypothese":new_hypothesis})
    business_trace("module4_piste_resolue",f"{old_name}:{outcome}:{new_hypothesis}")


def reliable_clean_spoken_text(text: str, *, expected_value_label: bool=False, question_kind: str="open") -> str:
    """Exécute la correction en un seul clic, avec une seconde tentative interne si l'API ne renvoie rien."""
    last = ""
    for _ in range(2):
        try:
            last = str(clean_spoken_text(text, expected_value_label=expected_value_label, question_kind=question_kind) or "").strip()
            if last:
                return last
        except Exception:
            continue
    return str(text or "").strip()

def _text_difference_kind(original: str, proposal: str) -> str:
    """Classe la différence afin d'éviter deux blocs artificiellement identiques."""
    import difflib
    a=" ".join(str(original or "").split())
    b=" ".join(str(proposal or "").split())
    if not b or a == b:
        return "identique"
    strip_punct=lambda t: re.sub(r"[^a-z0-9à-ÿ]+"," ",normalize(t)).strip()
    if strip_punct(a) == strip_punct(b):
        return "correction_legere"
    ratio=difflib.SequenceMatcher(None,strip_punct(a),strip_punct(b)).ratio()
    return "correction_legere" if ratio >= .88 else "reformulation_reelle"

def _module4_new_cycle(voie:str) -> None:
    st.session_state.module4_current_cycle={
        "id":str(uuid.uuid4()), "voie":voie, "stage":"initial", "started_at":now_iso(),
        "question":"", "exchanges":[], "candidate_options":[], "result":"", "candidate_rounds":0, "reorientation_count":0,
        "word_question_asked":False, "word_no_answer":False, "axis_closed":False, "hypothesis_checkpoint_shown":False,
    }
    st.session_state.module4_candidate_options=[]
    business_trace("module4_cycle_demarre",voie)


def _module4_record_exchange(cycle:dict[str,Any], question:str, answer:str, role:str="exploration") -> None:
    meta=deepcopy(st.session_state.get("answer_metadata",{}).get(f"m4_cycle_{cycle['id']}_{len(cycle.get('exchanges',[]))}",{}))
    item={"cycle_id":cycle["id"],"voie":cycle["voie"],"question":question,"reponse_validee":answer,"role":role,"date_heure":now_iso(),"metadata":meta}
    cycle.setdefault("exchanges",[]).append(item)
    st.session_state.module4_question_memory.append(deepcopy(item))
    st.session_state.module4_exploration_history.append(deepcopy(item))
    business_trace("module4_question_reponse",f"{cycle['voie']}:{role}")



def _module4_generate_way1_question() -> str:
    questions=[
        "Racontez une situation récente qui vous a particulièrement satisfait ou contrarié. Que s’est-il passé concrètement ?",
        "Pensez à une décision récente que vous avez prise sans hésiter. Qu’est-ce qui a compté le plus pour vous ?",
        "Racontez un moment récent où vous avez admiré ou désapprouvé la manière d’agir de quelqu’un. Qu’est-ce qui vous a marqué ?",
        "Pensez à une situation où vous avez accepté un effort ou un compromis. Pour préserver quoi l’avez-vous fait ?",
        "Racontez un moment où vous vous êtes senti vraiment à votre place. Qu’est-ce qui rendait ce moment important ?",
    ]
    used={_module4_question_signature(x.get("question","")) for x in st.session_state.get("module4_question_memory",[])}
    for question in questions:
        if _module4_question_signature(question) not in used:
            return question
    return "Racontez une autre situation, différente de celles déjà explorées, qui vous a fait réagir fortement. Que s’est-il passé ?"

def _module4_generate_way2_question() -> str:
    fallback="Pensez à un moment récent où vous vous êtes senti particulièrement satisfait, contrarié ou touché. Qu’est-ce qui s’est passé concrètement ?"
    if not ai_ready(): return fallback
    instructions="""Vous êtes le moteur de questionnement du module 4 Clarté360. Produisez UNE question ouverte, courte et concrète, destinée à aider le bénéficiaire à faire émerger une nouvelle piste de valeur.
Respectez impérativement : aucune conclusion psychologique, aucun profil, aucune valeur attribuée, aucun conseil. Tenez compte des questions-réponses déjà enregistrées dans les deux voies, des valeurs validées et des pistes déjà connues afin d’éviter les répétitions. Ne citez pas directement le nom d’une valeur attendue. La question doit rechercher un fait, une réaction, une admiration, une gêne, une satisfaction ou un choix concret. Retournez seulement la question."""
    schema={"type":"object","properties":{"question":{"type":"string"}},"required":["question"],"additionalProperties":False}
    try:
        return str(response_json(instructions,_module4_context_payload(),"module4_question_personnalisee",schema,max_tokens=220).get("question") or fallback).strip()
    except Exception:
        return fallback


def _module4_analyse_progress(cycle:dict[str,Any]) -> dict[str,Any]:
    exchanges=cycle.get("exchanges",[])
    vertical_count=sum(1 for x in exchanges if x.get("role")=="relance_verticale")
    last_answer=normalize(exchanges[-1].get("reponse_validee","") if exchanges else "")
    stop_markers=("deja repondu","déjà répondu","je ne sais plus","tourne en rond","rien d autre","rien d'autre","arreter","arrêter")
    if any(marker in last_answer for marker in stop_markers):
        return {"action":"proposer_hypotheses","question":"","raison":"Le bénéficiaire indique que l’axe est suffisamment exploré.","idee_principale":""}
    if len(exchanges)>=3:
        return {"action":"proposer_hypotheses","question":"","raison":"Point d’étape après trois échanges utiles.","idee_principale":""}
    fallback_action="demander_mot" if vertical_count>=3 or _module4_vertical_count(cycle)>=MODULE4_MAX_VERTICAL_QUESTIONS else "relance_verticale"
    fallback={"action":fallback_action,"question":("Si vous deviez mettre un mot sur ce qui était le plus important pour vous dans cette situation, lequel serait-il ?" if fallback_action=="demander_mot" else "Qu’est-ce qui était réellement important pour vous dans cette situation ?"),"raison":"","idee_principale":""}
    if not ai_ready(): return fallback
    instructions="""Analysez la progression d’un questionnement vertical Clarté360, sans attribuer de valeur et sans établir de profil.
Décidez d’une seule action :
- relance_verticale : tant qu'il manque une étape utile entre le fait raconté, ce qui a été attendu ou refusé, ce qui comptait réellement et le principe durable sous-jacent ;
- demander_mot : uniquement lorsque les réponses permettent déjà de comprendre clairement ce qui était important, au-delà de la seule émotion ou du seul besoin ;
- proposer_hypotheses : dès que trois échanges utiles ont eu lieu, qu’une ou plusieurs pistes deviennent plausibles, ou que le bénéficiaire indique avoir déjà répondu ;
- aucune_piste : uniquement si aucune matière exploitable n’existe réellement.

Ne demandez jamais un mot immédiatement après le seul récit initial. Posez normalement entre trois et cinq relances utiles, sans dépasser cinq. Chaque nouvelle question doit s'appuyer sur la dernière réponse et apporter un angle réellement nouveau. Ne répétez jamais une question presque identique.
La recherche du mot doit viser ce qui était important, pas seulement le ressenti. Formulation recommandée : « Si vous deviez mettre un mot sur ce qui était le plus important pour vous dans cette situation, lequel serait-il ? »
Une idée explorée ne pourra produire qu’une seule hypothèse retenue."""
    schema={"type":"object","properties":{"action":{"type":"string","enum":["relance_verticale","demander_mot","proposer_hypotheses","aucune_piste"]},"question":{"type":"string"},"raison":{"type":"string"},"idee_principale":{"type":"string"}},"required":["action","question","raison","idee_principale"],"additionalProperties":False}
    payload={"voie":cycle.get("voie"),"echanges":exchanges,"valeurs_deja_connues":list(_module4_all_known_names())}
    try:
        out=response_json(instructions,payload,"module4_progression_verticale",schema,max_tokens=420)
        if len(exchanges)<=1 and out.get("action")=="demander_mot":
            out["action"]="relance_verticale"; out["question"]="Qu’est-ce qui vous a le plus touché ou dérangé dans cette situation, précisément ?"
        if vertical_count<2 and out.get("action")=="demander_mot":
            out["action"]="relance_verticale"; out["question"]="Qu’auriez-vous voulu voir respecté, compris ou préservé dans cette situation ?"
        if _module4_vertical_count(cycle)>=MODULE4_MAX_VERTICAL_QUESTIONS and out.get("action")=="relance_verticale":
            out["action"]="demander_mot"; out["question"]=MODULE4_WORD_QUESTION
        if out.get("action")=="relance_verticale" and _module4_question_already_asked(cycle,out.get("question","")):
            replacement=_module4_distinct_followup(cycle)
            if replacement==MODULE4_WORD_QUESTION:
                out["action"]="demander_mot"
            out["question"]=replacement
        return out
    except Exception:
        if fallback.get("action")=="relance_verticale" and _module4_question_already_asked(cycle,fallback.get("question","")):
            fallback["question"]=_module4_distinct_followup(cycle)
            if fallback["question"]==MODULE4_WORD_QUESTION:
                fallback["action"]="demander_mot"
        return fallback

def _module4_word_candidates(cycle:dict[str,Any], word:str) -> list[dict[str,str]]:
    texts=[word]+[x.get("reponse_validee","") for x in cycle.get("exchanges",[])]
    pool=lexical_prefilter(texts,limit=24)
    known=_module4_all_known_names()
    pool=[x for x in pool if normalize(x.get("nom","")) not in known]
    exact=_referential_value_info(_normalise_value_name(word))
    if exact and normalize(exact.get("nom","")) not in known:
        return [{"nom":exact["nom"],"definition":exact.get("definition","")}]
    if not ai_ready():
        return [{"nom":x["nom"],"definition":x.get("definition","")} for x in pool[:3]]
    instructions="""À partir du mot du bénéficiaire, de sa signification dans le questionnement vertical et d’un sous-ensemble du référentiel Clarté360, proposez zéro à trois mots candidats maximum.
Règles :
- ce sont de simples hypothèses, jamais des conclusions ;
- comparez surtout le sens exprimé, pas seulement la ressemblance lexicale ;
- repartez de la définition HEC d’une valeur : un principe durable susceptible d’orienter les choix et comportements d’un individu ;
- utilisez silencieusement comme garde-fou la possibilité que ce principe puisse se manifester dans plusieurs domaines de vie, sans demander au bénéficiaire de le prouver ;
- ne transformez pas automatiquement un besoin, une émotion, une croyance, une limite, un objectif ou un comportement en valeur ;
- une idée explorée = une seule hypothèse éventuellement retenue ;
- ne proposez que des valeurs présentes dans la liste fournie ;
- si rien n’est suffisamment plausible, retournez une liste vide ;
- relisez toute la situation et le contexte déjà connu : un mot comme « reconnaissance » ne doit pas masquer un autre enjeu distinct déjà exprimé, par exemple le travail, l’engagement, la qualité, la contribution ou la responsabilité ;
- lorsqu’une précédente série de candidats a été refusée, cherchez un axe de sens réellement différent et non de simples synonymes."""
    schema={"type":"object","properties":{"candidats":{"type":"array","maxItems":3,"items":{"type":"object","properties":{"nom":{"type":"string"},"definition":{"type":"string"},"raison":{"type":"string"}},"required":["nom","definition","raison"],"additionalProperties":False}}},"required":["candidats"],"additionalProperties":False}
    payload={"mot_beneficiaire":word,"echanges":cycle.get("exchanges",[]),"candidats_referentiel":pool,"valeurs_deja_connues":list(known),"contexte_beneficiaire":_module4_context_payload(),"candidats_deja_refuses":cycle.get("candidate_round_history",[])}
    try:
        out=response_json(instructions,payload,"module4_hypotheses_candidates",schema,max_tokens=650)
        valid=[]
        allowed={normalize(x["nom"]):x for x in pool}
        for c in out.get("candidats",[]):
            src=allowed.get(normalize(c.get("nom","")))
            if src: valid.append({"nom":src["nom"],"definition":src.get("definition","") or c.get("definition","")})
        return valid[:3]
    except Exception:
        return [{"nom":x["nom"],"definition":x.get("definition","")} for x in pool[:3]]


def _module4_generate_reorientation_question(cycle:dict[str,Any]) -> str:
    fallback="Dans cette même situation, vous avez aussi évoqué votre investissement ou votre travail. Qu’est-ce qui était important pour vous dans cet aspect précis ?"
    if not ai_ready(): return fallback
    instructions="""Vous poursuivez avec modestie un questionnement vertical Clarté360 après le refus de plusieurs mots candidats.
Le refus d’une hypothèse ne signifie pas que la situation est épuisée. Relisez tous les couples questions-réponses et repérez UN aspect significatif encore peu exploré.
Posez UNE question ouverte, courte, ancrée dans les mots du bénéficiaire, afin d’approfondir cet autre aspect.
Ne proposez aucun mot de valeur dans la question. Ne répétez pas l’axe déjà refusé et ne cherchez pas un simple synonyme.
Vous pouvez notamment revenir sur un élément concret passé au second plan : travail, investissement, effort, qualité, utilité, responsabilité, relation, choix ou autre élément réellement présent dans le récit.
Aucune analyse psychologique, aucune conclusion et aucun conseil. Retournez seulement la question."""
    schema={"type":"object","properties":{"question":{"type":"string"}},"required":["question"],"additionalProperties":False}
    payload={"echanges":cycle.get("exchanges",[]),"candidats_deja_refuses":cycle.get("candidate_round_history",[]),"contexte_beneficiaire":_module4_context_payload()}
    try:
        return str(response_json(instructions,payload,"module4_reorientation_apres_refus",schema,max_tokens=260).get("question") or fallback).strip()
    except Exception:
        return fallback


def _module4_add_hypothesis(cycle:dict[str,Any], candidate:dict[str,str]) -> None:
    item={"id":str(uuid.uuid4()),"nom":candidate["nom"],"definition_clarte360":candidate.get("definition",""),"source":"module_4","voie":cycle.get("voie"),"cycle_id":cycle.get("id"),"statut":"hypothese","created_at":now_iso(),"question_reponses":deepcopy(cycle.get("exchanges",[])),"contexte_initial":deepcopy(cycle.get("source_track") or {})}
    existing={normalize(x.get("nom") or "") for x in st.session_state.get("hypothesis_basket",[])}
    if normalize(candidate["nom"]) not in existing:
        st.session_state.hypothesis_basket.append(item)
    if cycle.get("voie")=="piste_clarifier":
        _module4_resolve_source_track(cycle,"hypothese_retenue",candidate["nom"])
    cycle["result"]="hypothese_retenue"; cycle["selected_hypothesis"]=candidate["nom"]; cycle["stage"]="termine"
    business_trace("module4_hypothese_panier",candidate["nom"])


def _module4_threshold_invitation() -> None:
    validated=len(_module4_validated_value_labels()); hypotheses=len(st.session_state.get("hypothesis_basket",[]))
    if hypotheses>=3 and validated+hypotheses>=8:
        st.info(f"Vous avez maintenant {validated} valeur(s) validée(s) et {hypotheses} hypothèse(s), soit {validated+hypotheses} éléments au total. Il peut être utile d’examiner vos hypothèses dans le module 3. Vous restez libre de continuer votre recherche.")
        if st.button("Examiner mes hypothèses dans le module 3",use_container_width=True,key="m4_go_module3_threshold"):
            st.session_state.active_module="module_3"; st.session_state.module4_route=""; st.rerun()


def _module4_candidates_from_dialogue(cycle: dict[str,Any]) -> list[dict[str,str]]:
    """Fait émerger des hypothèses depuis tout le dialogue, sans exiger un mot préalable."""
    joined=" ".join(x.get("reponse_validee","") for x in cycle.get("exchanges",[]))
    return _module4_word_candidates(cycle, joined)

def _module4_module2_completed() -> bool:
    return _module_state("module_2").get("status")=="termine"

def _module4_render_cycle(voie:str) -> None:
    cycle=st.session_state.get("module4_current_cycle") or {}
    if not cycle or cycle.get("voie")!=voie or cycle.get("stage")=="termine":
        if cycle.get("stage")=="termine":
            if cycle.get("result")=="hypothese_retenue": st.success(f"L’hypothèse **{cycle.get('selected_hypothesis','')}** a été ajoutée uniquement au panier Hypothèses.")
            else: st.info("Ce cycle est terminé sans hypothèse retenue. Cela est parfaitement normal.")
            _module4_threshold_invitation()
            c1,c2=st.columns(2)
            with c1:
                if st.button("Rechercher une autre valeur",type="primary",use_container_width=True,key=f"m4_restart_{voie}"):
                    _module4_new_cycle(voie); st.rerun()
            with c2:
                if st.button("Retour au choix des voies",use_container_width=True,key=f"m4_back_routes_{voie}"):
                    st.session_state.module4_route=""; st.session_state.module4_current_cycle={}; _set_module_status("module_4","en_cours","choix_voie"); st.rerun()
            return
        _module4_new_cycle(voie); cycle=st.session_state.module4_current_cycle

    if voie=="questions_personnalisees" and not cycle.get("question"):
        cycle["question"]=_module4_generate_way2_question(); cycle["stage"]="question"
    elif voie=="situation" and not cycle.get("question"):
        cycle["question"]=_module4_generate_way1_question(); cycle["stage"]="question"
    elif voie=="piste_clarifier" and not cycle.get("question"):
        cycle["question"]="Derrière cette formulation, qu’est-ce qui est réellement important pour vous ?"; cycle["stage"]="question"

    _module4_render_exchange_thread(cycle)

    if cycle.get("stage") in {"question","mot"}:
        question=cycle.get("question","")
        st.markdown(f"### {question}"); speak_button(question,f"m4_q_{cycle['id']}_{len(cycle.get('exchanges',[]))}")
        widget_key=f"m4_cycle_{cycle['id']}_{len(cycle.get('exchanges',[]))}"
        answer=open_response_widget("Votre réponse",widget_key,height=140,allow_reformulation=True,listen=True,dependency_scope="exploration",question_kind="word" if cycle.get("stage")=="mot" else "open")
        if answer and not cycle.get("pending_answer_processed"):
            role="initial" if not cycle.get("exchanges") else ("recherche_mot" if cycle.get("stage")=="mot" else "relance_verticale")
            _module4_record_exchange(cycle,question,answer,role)
            cycle["pending_answer_processed"]=True
            if role=="recherche_mot":
                cycle["word_question_asked"]=True
                if _module4_no_word_answer(answer):
                    cycle["word_no_answer"]=True
                    cycle["stage"]="proposition_permission"
                else:
                    candidates=_module4_word_candidates(cycle,answer)
                    cycle["candidate_options"]=candidates
                    if candidates: cycle["candidate_rounds"]=int(cycle.get("candidate_rounds",0))+1
                    cycle["stage"]="candidats" if candidates else "proposition_permission"
            else:
                progress=_module4_analyse_progress(cycle)
                if progress.get("action")=="aucune_piste":
                    cycle["candidate_options"]=_module4_candidates_from_dialogue(cycle)
                    cycle["stage"]="checkpoint_hypotheses" if cycle.get("exchanges") else "termine"
                    cycle["result"]="aucune_piste" if not cycle.get("exchanges") else ""
                elif progress.get("action")=="proposer_hypotheses":
                    cycle["candidate_options"]=_module4_candidates_from_dialogue(cycle)
                    cycle["stage"]="checkpoint_hypotheses"
                elif progress.get("action")=="demander_mot":
                    if cycle.get("word_question_asked") and cycle.get("word_no_answer"):
                        cycle["stage"]="proposition_permission"
                    else:
                        cycle["stage"]="mot"; cycle["question"]=MODULE4_WORD_QUESTION; cycle["word_question_asked"]=True
                else:
                    next_question=progress.get("question") or "Qu’est-ce qui était réellement important pour vous dans cette situation ?"
                    if _module4_vertical_count(cycle)>=MODULE4_MAX_VERTICAL_QUESTIONS:
                        cycle["stage"]="mot"; cycle["question"]=MODULE4_WORD_QUESTION; cycle["word_question_asked"]=True
                    elif _module4_question_already_asked(cycle,next_question):
                        cycle["stage"]="mot"; cycle["question"]=MODULE4_WORD_QUESTION; cycle["word_question_asked"]=True
                    else:
                        cycle["stage"]="question"; cycle["question"]=next_question
            st.rerun()
        if cycle.get("pending_answer_processed"):
            cycle.pop("pending_answer_processed",None)

    if cycle.get("stage")=="checkpoint_hypotheses":
        st.info("Faisons un point : ce dialogue peut déjà faire émerger plusieurs pistes. Vous gardez la main sur la suite.")
        options=cycle.get("candidate_options",[])
        if options:
            st.markdown("**Hypothèses repérées par Clarté360**")
            for item in options:
                st.write(f"• **{item.get('nom','')}** — {item.get('definition','')}")
        own=st.text_input("Une autre valeur vous est-elle venue à l’esprit ?",key=f"m4_own_hypothesis_{cycle['id']}",placeholder="Vous pouvez saisir un mot, ou laisser vide.")
        actions=["Choisissez","Examiner une hypothèse","Continuer le questionnement","Arrêter ce dialogue"]
        action=st.radio("Que souhaitez-vous faire maintenant ?",actions,key=f"m4_checkpoint_action_{cycle['id']}")
        if action=="Examiner une hypothèse":
            labels=[x.get("nom","") for x in options]
            if own.strip(): labels.append(_normalise_value_name(own.strip()))
            if not labels:
                st.warning("Aucune hypothèse n’est encore disponible. Vous pouvez saisir votre propre proposition ou poursuivre le dialogue.")
            else:
                selected=st.radio("Quelle hypothèse souhaitez-vous examiner ?",labels,key=f"m4_checkpoint_select_{cycle['id']}")
                if st.button("Conserver cette hypothèse",type="primary",use_container_width=True,key=f"m4_checkpoint_keep_{cycle['id']}"):
                    item=next((x for x in options if x.get("nom")==selected),{"nom":selected,"definition":(_referential_value_info(selected) or {}).get("definition","")})
                    _module4_add_hypothesis(cycle,item); st.rerun()
        elif action=="Continuer le questionnement":
            if st.button("Continuer avec une nouvelle question",type="primary",use_container_width=True,key=f"m4_checkpoint_continue_{cycle['id']}"):
                cycle["question"]=_module4_generate_reorientation_question(cycle); cycle["stage"]="question"; cycle["pending_answer_processed"]=False; st.rerun()
        elif action=="Arrêter ce dialogue":
            if st.button("Arrêter et conserver le travail réalisé",type="primary",use_container_width=True,key=f"m4_checkpoint_stop_{cycle['id']}"):
                cycle["stage"]="termine"; cycle["result"]="dialogue_arrete_sans_hypothese"; st.rerun()

    if cycle.get("stage")=="proposition_permission":
        if cycle.get("word_no_answer"):
            st.info("Aucun mot ne vous vient pour le moment. La même question ne sera pas reposée.")
        else:
            st.warning("Le mot proposé ne correspond pas assez clairement à une valeur du référentiel.")
        if not cycle.get("word_no_answer") and sum(1 for x in cycle.get("exchanges",[]) if x.get("role")=="recherche_mot")<2:
            q="Quel autre mot pourrait mieux résumer ce qui était important pour vous dans cette situation ?"
            if st.button("Approfondir une seconde fois",type="primary",use_container_width=True,key=f"m4_second_word_{cycle['id']}"):
                cycle["question"]=q; cycle["stage"]="mot"; st.rerun()
        consent=st.radio("Souhaitez-vous que Clarté360 vous propose quelques mots comme simples hypothèses ?",["Choisissez","Oui","Non"],key=f"m4_consent_{cycle['id']}")
        if consent=="Oui":
            candidates=_module4_word_candidates(cycle," ".join(x.get("reponse_validee","") for x in cycle.get("exchanges",[]) if x.get("role")=="recherche_mot"))
            cycle["candidate_options"]=candidates
            if candidates: cycle["candidate_rounds"]=int(cycle.get("candidate_rounds",0))+1
            cycle["stage"]="candidats" if candidates else "termine"; cycle["result"]="aucune_piste" if not candidates else ""; st.rerun()
        if consent=="Non": cycle["stage"]="termine"; cycle["result"]="aucune_piste"; st.rerun()

    if cycle.get("stage")=="candidats":
        options=cycle.get("candidate_options",[])
        st.info("Ces mots sont de simples hypothèses. Clarté360 peut se tromper. Une seule hypothèse peut être retenue pour l’idée explorée.")
        for item in options:
            with st.container(border=True):
                st.markdown(f"**{item['nom']}**")
                st.write(item.get("definition","") or "Définition non disponible.")
        labels=[x["nom"] for x in options]+["Aucune ne correspond"]
        selected=st.radio("Laquelle correspond le mieux à ce que vous vouliez exprimer ?",labels,key=f"m4_select_{cycle['id']}")
        if st.button("Confirmer mon choix",type="primary",use_container_width=True,key=f"m4_confirm_{cycle['id']}"):
            if selected=="Aucune ne correspond":
                history=cycle.setdefault("candidate_round_history",[])
                history.append({"date_heure":now_iso(),"candidats":[x.get("nom","") for x in options],"decision":"aucune_ne_correspond"})
                cycle["candidate_options"]=[]
                if int(cycle.get("reorientation_count",0))<2:
                    cycle["stage"]="reorientation_apres_refus"
                else:
                    cycle["stage"]="termine"; cycle["result"]="hypotheses_refusees_apres_approfondissement"
            else: _module4_add_hypothesis(cycle,next(x for x in options if x["nom"]==selected))
            st.rerun()

    if cycle.get("stage")=="reorientation_apres_refus":
        st.info("Aucun de ces mots ne vous correspond. Cela ne signifie pas forcément que la situation est épuisée : un autre aspect de ce que vous avez raconté peut encore être exploré.")
        c1,c2=st.columns(2)
        with c1:
            if st.button("Approfondir un autre aspect de cette situation",type="primary",use_container_width=True,key=f"m4_reorient_{cycle['id']}_{cycle.get('reorientation_count',0)}"):
                cycle["reorientation_count"]=int(cycle.get("reorientation_count",0))+1
                cycle["question"]=_module4_generate_reorientation_question(cycle)
                cycle["stage"]="question"
                cycle["pending_answer_processed"]=False
                st.rerun()
        with c2:
            if st.button("Arrêter cette piste",use_container_width=True,key=f"m4_stop_after_refusal_{cycle['id']}"):
                cycle["stage"]="termine"; cycle["result"]="hypotheses_refusees"; st.rerun()


def _module4_render_way1() -> None:
    st.title("Partir d’une situation observée")
    instruction="Décrivez une situation réelle. Clarté360 vous posera quelques questions verticales, puis cherchera avec vous un mot. Le résultat restera une simple hypothèse et une idée explorée ne pourra produire qu’une seule hypothèse retenue. Si les premiers mots proposés ne correspondent pas, Clarté360 pourra approfondir brièvement un autre aspect de la même situation avant de clore la piste."
    st.info(instruction); speak_button(instruction,"m4_way1_instruction")
    _module4_render_cycle("situation")


def _module4_render_way2() -> None:
    st.title("Aidez-moi à trouver une piste")
    if not _module4_module2_completed():
        st.warning("La voie 2 utilise les réponses du Module 2 pour personnaliser les questions. Terminez d’abord le Module 2, ou choisissez la voie 1.")
        c1,c2=st.columns(2)
        with c1:
            if st.button("Aller au Module 2",type="primary",use_container_width=True,key="m4_way2_go_m2"):
                st.session_state.active_module="module_2"; st.session_state.page="Modules"; st.rerun()
        with c2:
            if st.button("Choisir la voie 1",use_container_width=True,key="m4_way2_go_way1"):
                st.session_state.module4_route="situation"; st.session_state.module4_current_cycle={}; st.rerun()
        return
    instruction="Clarté360 choisira une question à partir de tout ce qui est déjà connu, y compris les couples questions-réponses issus des deux voies. Cette mémoire reste descriptive : elle ne constitue ni un profil ni une conclusion sur vous."
    st.info(instruction); speak_button(instruction,"m4_way2_instruction")
    values=_module4_validated_value_labels()
    if values: st.markdown("**Valeurs déjà validées prises en compte :** "+", ".join(values))
    _module4_render_cycle("questions_personnalisees")

def _module4_render_way3() -> None:
    st.title("Explorer une piste à clarifier")
    tracks=st.session_state.get("clarification_tracks",[])
    if not tracks:
        st.info("Aucune piste à clarifier n’est actuellement enregistrée.")
        if st.button("← Retour au choix des voies",use_container_width=True,key="m4_way3_empty_back"):
            st.session_state.module4_route=""; st.rerun()
        return
    selected=st.selectbox("Piste à reprendre",range(len(tracks)),format_func=lambda i:tracks[i].get("terme_initial") or "Piste",key="m4_way3_track")
    track=tracks[selected]
    with st.container(border=True):
        st.write(f"**Terme initial :** {track.get('terme_initial','')}")
        st.write(f"**Définition personnelle :** {track.get('definition_personnelle','')}")
        if track.get("situation"): st.write(f"**Situation déjà enregistrée :** {track.get('situation')}")
        if track.get("ressenti"): st.write(f"**Réaction ou ressenti déjà enregistré :** {track.get('ressenti')}")
    cycle=st.session_state.get("module4_current_cycle") or {}
    if not cycle or cycle.get("voie")!="piste_clarifier" or cycle.get("track_id")!=track.get("id"):
        _module4_new_cycle("piste_clarifier")
        cycle=st.session_state.module4_current_cycle
        cycle["track_id"]=track.get("id")
        cycle["question"]="Derrière cette formulation, qu’est-ce que vous cherchez surtout à préserver, respecter ou rendre possible dans votre manière de vivre et de décider ?"
        cycle["stage"]="question"
        cycle["source_track"]=deepcopy(track)
    _module4_render_cycle("piste_clarifier")
    cycle=st.session_state.get("module4_current_cycle") or {}
    if cycle.get("stage")=="termine" and cycle.get("result")!="hypothese_retenue" and not cycle.get("track_resolution_recorded"):
        _module4_resolve_source_track(cycle,cycle.get("result") or "aucune_hypothese")
        cycle["track_resolution_recorded"]=True
    if st.button("← Changer de voie",use_container_width=True,key="m4_way3_change"):
        st.session_state.module4_route=""; st.session_state.module4_current_cycle={}; st.rerun()


def render_module_4_placeholder() -> None:
    completed=bool(st.session_state.get("module4_knowledge_completed",False))
    if completed:
        route=str(st.session_state.get("module4_route","") or "")
        if route=="situation": _module4_render_way1(); return
        if route=="questions_personnalisees": _module4_render_way2(); return
        if route=="piste_clarifier": _module4_render_way3(); return
        _module4_render_choice(); return

    st.title("Rechercher une nouvelle valeur avec Clarté360")
    _set_module_status("module_4","en_cours","complement_connaissance")
    if not st.session_state.get("module4_knowledge_started_at"):
        st.markdown("### Quelques questions pour mieux vous connaître")
        intro="Nous avons maintenant une première connaissance de votre parcours. Avant de poursuivre votre recherche de valeurs, nous allons vous proposer quelques questions très simples pour mieux vous connaître encore. Il ne s’agit ni d’un test, ni d’une évaluation. Il n’y a pas de bonne ou de mauvaise réponse. Vos réponses serviront uniquement à personnaliser les prochaines questions."
        st.info(intro); speak_button(intro,"m4_cc_intro_listen")
        warning="Cette étape ne produit aucun score, aucun profil et aucune conclusion. Elle est réalisée une seule fois."
        st.warning(warning); speak_button(warning,"m4_cc_warning_listen")
        c1,c2=st.columns(2)
        with c1:
            if st.button("← Retour au parcours",use_container_width=True,key="m4_cc_intro_back"):
                st.session_state.active_module="accueil_modules"; st.rerun()
        with c2:
            if st.button("Commencer",type="primary",use_container_width=True,key="m4_cc_start"):
                st.session_state.module4_knowledge_started_at=now_iso(); st.session_state.module4_knowledge_index=0; business_trace("module4_complement_demarre",MODULE4_KNOWLEDGE_VERSION); st.rerun()
        return

    idx=min(int(st.session_state.get("module4_knowledge_index",0)),len(MODULE4_KNOWLEDGE_EXERCISES)-1)
    exercise=MODULE4_KNOWLEDGE_EXERCISES[idx]
    st.progress(idx/len(MODULE4_KNOWLEDGE_EXERCISES))
    st.caption(f"Question {idx+1} sur {len(MODULE4_KNOWLEDGE_EXERCISES)} · aucune bonne ou mauvaise réponse")
    with st.container(border=True):
        st.markdown(f"### {exercise['title']}")
        st.write(exercise["prompt"]); speak_button(exercise["prompt"],f"m4_cc_q_{idx}")
        existing=_module4_knowledge_answer(exercise).get("reponse")
        if exercise["type"]=="classement_court":
            st.caption("Attribuez 1 à la situation qui vous attire le plus, puis 2 et 3 sans utiliser deux fois le même rang.")
            ranks=[]; cols=st.columns(3)
            for i,option in enumerate(exercise["options"]):
                default_rank=(existing.index(option)+1) if isinstance(existing,list) and option in existing else i+1
                with cols[i]: st.write(option); ranks.append(int(st.selectbox("Rang",[1,2,3],index=default_rank-1,key=f"m4_rank_{exercise['id']}_{i}")))
            answer=[x for _,x in sorted(zip(ranks,exercise["options"]))] if len(set(ranks))==3 else None
            if answer is None: st.warning("Utilisez une seule fois chacun des rangs 1, 2 et 3.")
        else:
            index=exercise["options"].index(existing) if existing in exercise["options"] else None
            answer=st.radio("Votre choix",exercise["options"],index=index,key=f"m4_choice_{exercise['id']}")
    c1,c2,c3=st.columns([1,1,1])
    with c1:
        if st.button("← Précédent",use_container_width=True,disabled=idx==0,key=f"m4_prev_{idx}"):
            st.session_state.module4_knowledge_index=max(0,idx-1); st.rerun()
    with c2:
        if st.button("Passer cette question",use_container_width=True,key=f"m4_skip_{idx}"):
            _module4_save_knowledge_answer(exercise,None,"ignore")
            if idx+1>=len(MODULE4_KNOWLEDGE_EXERCISES): _module4_complete_knowledge()
            else: st.session_state.module4_knowledge_index=idx+1
            st.rerun()
    with c3:
        if st.button("Valider et continuer" if idx+1<len(MODULE4_KNOWLEDGE_EXERCISES) else "Terminer",type="primary",use_container_width=True,disabled=answer is None,key=f"m4_next_{idx}"):
            _module4_save_knowledge_answer(exercise,answer,"termine")
            if idx+1>=len(MODULE4_KNOWLEDGE_EXERCISES): _module4_complete_knowledge()
            else: st.session_state.module4_knowledge_index=idx+1
            st.rerun()

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
    if not st.session_state.get("prerequisite_confirmed"):
        st.session_state.active_module="module_1"
    if st.session_state.page=="Consultation finale" or st.session_state.get("final_mode"): render_final_consultation(); return
    if st.session_state.page=="Cloture definitive": render_closure_screen(); return
    display_header()
    if st.session_state.page=="Accueil reprise": render_resume_welcome(); return
    render_followup_panel()
    pending_entry=st.session_state.get("pending_module_entry")
    if pending_entry:
        st.title("Travail en cours")
        st.info("Un travail non finalisé existe dans ce module. Souhaitez-vous le reprendre ou l'abandonner ?")
        c1,c2=st.columns(2)
        with c1:
            if st.button("Reprendre exactement où j'en étais",type="primary",use_container_width=True,key="resume_pending_module"):
                st.session_state.active_module=pending_entry; st.session_state.pending_module_entry=""; st.rerun()
        with c2:
            if st.button("Abandonner ce travail et revenir au menu du module",use_container_width=True,key="abandon_pending_module"):
                _abandon_module_temporary_work(pending_entry); st.session_state.active_module=pending_entry; st.session_state.pending_module_entry=""; st.rerun()
        return
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
        "complement_connaissance_module_4":{
            "version":st.session_state.get("module4_knowledge_version",MODULE4_KNOWLEDGE_VERSION),
            "commence_le":st.session_state.get("module4_knowledge_started_at",""),
            "termine":bool(st.session_state.get("module4_knowledge_completed",False)),
            "termine_le":st.session_state.get("module4_knowledge_completed_at",""),
            "reponses":deepcopy(st.session_state.get("module4_knowledge_answers",{})),
            "absence_score_profil_conclusion":True,
        },
        "panier_hypotheses":deepcopy(st.session_state.get("hypothesis_basket",[])),
        "pistes_a_clarifier":deepcopy(st.session_state.get("clarification_tracks",[])),
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

def payload_bytes(completed=False)->bytes:
    with st.spinner("Préparation de votre sauvegarde JSON…"):
        return json.dumps(build_payload(completed),ensure_ascii=False,indent=2).encode("utf-8")
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
    if m.get("pistes_a_clarifier"): st.session_state.clarification_tracks=deepcopy(m.get("pistes_a_clarifier"))
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
    styles.add(ParagraphStyle(name="Teal",parent=styles["Heading1"],textColor=colors.HexColor(OFFICIAL_TEAL),spaceBefore=8,spaceAfter=12,keepWithNext=True))
    styles.add(ParagraphStyle(name="Teal2",parent=styles["Heading2"],textColor=colors.HexColor(OFFICIAL_TEAL),spaceBefore=10,spaceAfter=6,keepWithNext=True))
    styles.add(ParagraphStyle(name="Small",parent=styles["Normal"],fontSize=8,leading=10,textColor=colors.HexColor("#666666")))
    styles.add(ParagraphStyle(name="Cover",parent=styles["Title"],fontSize=24,leading=29,textColor=colors.HexColor(OFFICIAL_TEAL),alignment=1,spaceAfter=18))
    def footer(canvas,doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#D7EAEA")); canvas.line(1.5*cm,1.05*cm,A4[0]-1.5*cm,1.05*cm); canvas.setFont("Helvetica",7.5); canvas.setFillColor(colors.HexColor("#666666")); canvas.drawString(1.5*cm,.65*cm,"Clarté360 - 60 rue François 1er - 75008 Paris - Document confidentiel"); canvas.drawRightString(A4[0]-1.5*cm,.65*cm,f"Page {doc.page}"); canvas.restoreState()
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=1.7*cm,leftMargin=1.7*cm,topMargin=1.5*cm,bottomMargin=1.4*cm,title="Rapport RVC360 - Recherche de mes valeurs")
    b=st.session_state.get("beneficiaire",{}); values=[v for v in st.session_state.get("central_validated_values",[]) if v.get("statut")=="validee"]
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
    sessions=st.session_state.get("session_history",[]) or []
    total_seconds=sum(int(x.get("duree_active_secondes",0) or 0) for x in sessions)
    story += [Paragraph("Temps consacré à l’application",styles["Teal2"]),Paragraph(f"<b>Temps cumulé actif :</b> {html.escape(format_duration(total_seconds))}",styles["Normal"])]
    if sessions:
        session_rows=[["Date","Début","Dernière activité","Durée active","Accès"]]
        for sess in sessions:
            debut=str(sess.get("debut","") or "")
            last=str(sess.get("derniere_activite","") or "")
            session_rows.append([debut[:10],debut[11:16] if len(debut)>=16 else "",last[11:16] if len(last)>=16 else "",format_duration(sess.get("duree_active_secondes",0)),str(sess.get("motif_ouverture","") or "")])
        ts=Table(session_rows,colWidths=[3*cm,2.2*cm,3*cm,3*cm,4.8*cm]); ts.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(LIGHT_TEAL)),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#CFE6E6')),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),8)])); story += [ts,Spacer(1,10)]
    accompagnateur=[v for v in values if v.get("source")=="accompagnateur"]
    application=[v for v in values if v.get("source")!="accompagnateur"]
    for number,title,items in [(3,"Valeurs validées avec l’accompagnateur",accompagnateur),(4,"Valeurs découvertes et validées dans Clarté360",application)]:
        story += [CondPageBreak(3.8*cm),Paragraph(f"{number}. {title}",styles["Teal"])]
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
    story += [CondPageBreak(4.2*cm),Paragraph("5. Liste centrale des valeurs validées",styles["Teal"])]
    if values:
        for i,v in enumerate(values,1): story += [Paragraph(f"{i}. <b>{html.escape(_normalise_value_name(v.get('nom_final') or ''))}</b> - {html.escape(v.get('definition_personnelle') or '')}",styles["Normal"])]
    else: story += [Paragraph("Aucune valeur validée.",styles["Normal"])]
    story += [CondPageBreak(3.2*cm),Paragraph("6. Suite du parcours Clarté360",styles["Teal"]),Paragraph("Cette liste centrale peut servir de base à la Boussole des valeurs professionnelles pour hiérarchiser les valeurs dans le contexte professionnel, ou à la Roue des valeurs pour évaluer leur niveau de satisfaction et leur cohérence dans la vie actuelle.",styles["Normal"]),CondPageBreak(3.0*cm),Paragraph("7. Conclusion",styles["Teal"]),Paragraph("Les valeurs présentées sont uniquement celles actuellement validées. Les valeurs à examiner, non retenues ou à revoir en séance ne sont pas présentées comme des valeurs du bénéficiaire.",styles["Normal"]),Spacer(1,12),Paragraph("Document confidentiel - diffusion réservée au bénéficiaire et, avec son accord, à son accompagnateur.",styles["Small"])]
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
        st.subheader("Code d'accès")
        _ctrl_enter_marker("access_code_input", "Valider le code et commencer")
        code_in=st.text_input("Saisissez le code reçu par e-mail",max_chars=6,key="access_code_input")
        st.caption("Ctrl + Entrée : valider le code et commencer")
        _install_ctrl_enter_bridge()
        c1,c2=st.columns(2)
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
        if st.sidebar.button("💾 Préparer ma sauvegarde JSON",use_container_width=True,key="prepare_sidebar_json"):
            with st.sidebar.spinner("Préparation de votre fichier…"):
                st.session_state.prepared_sidebar_json=payload_bytes(False)
                st.session_state.prepared_sidebar_json_name=make_filename("rvc360_sauvegarde","json")
            record_save_event("sauvegarde_manuelle")
        if st.session_state.get("prepared_sidebar_json"):
            st.sidebar.download_button("Télécharger mon fichier JSON",data=st.session_state.prepared_sidebar_json,file_name=st.session_state.get("prepared_sidebar_json_name") or make_filename("rvc360_sauvegarde","json"),mime="application/json",use_container_width=True)
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
            val=open_response_widget(f"Valeur déjà identifiée n°{i+1}",f"prereq_free_{i}",height=70,allow_reformulation=False,dependency_scope="prerequisites",expected_value_label=True, question_kind="word")
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
                    custom_name=open_response_widget("Nom de votre valeur",f"customname_{i}",value=item['raw'],height=70,allow_reformulation=False,dependency_scope="prerequisites",expected_value_label=True, question_kind="word")
                    custom_def=open_response_widget("Que signifie cette valeur pour vous ?",f"customdef_{i}",height=110,dependency_scope="prerequisites",value_name=custom_name.strip())
                    if custom_name.strip() and custom_def.strip(): confirmed_values.append((custom_name.strip(),custom_def.strip(),True))
            else:
                st.write("Cette formulation n'existe pas telle quelle dans le référentiel. Elle peut néanmoins être retenue pour vous.")
                custom_name=open_response_widget("Nom de votre valeur",f"newname_{i}",value=item['raw'],height=70,allow_reformulation=False,dependency_scope="prerequisites",expected_value_label=True, question_kind="word")
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
                name=open_response_widget("Nom proposé",f"inter_name_{i}",value=previous.get("nom",""),height=70,allow_reformulation=False,dependency_scope="personal_values",expected_value_label=True, question_kind="word")
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
