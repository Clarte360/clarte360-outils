# -*- coding: utf-8 -*-
"""
Clarté360 – Analyse des compétences transférables et faisabilité du projet professionnel V1.1
Analyse des compétences transférables et aide à la décision projet professionnel.

Sources locales attendues dans /data :
- RefRomeXml.zip
- rome_riasec_clarte360.xlsx
- site_icon.png (optionnel)
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import random
import re
import smtplib
import string
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

APP_VERSION = "1.2.0"
APP_NAME = "Clarté360 – Analyse des compétences transférables et faisabilité du projet professionnel"
DATA_DIR = Path(__file__).parent / "data"
ROME_ZIP = DATA_DIR / "RefRomeXml.zip"
RIASEC_XLSX = DATA_DIR / "rome_riasec_clarte360.xlsx"
ICON = DATA_DIR / "site_icon.png"

CLARTE_TEAL = "#008B86"
CLARTE_TEAL_DARK = "#006C68"
CLARTE_YELLOW = "#FFE478"
CLARTE_DARK = "#2B2D3A"
CLARTE_BG = "#F7FAFA"
CLARTE_RED = "#FF4B4B"

STATUS_OPTIONS = ["Non renseigné", "Acquis", "En cours d'acquisition", "Non acquis", "Non applicable"]
STATUS_SCORE = {
    "Acquis": 1.0,
    "En cours d'acquisition": 0.5,
    "Non acquis": 0.0,
    "Non applicable": None,
    "Non renseigné": None,
}

# -----------------------------
# Utilitaires
# -----------------------------

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean_text(text: Optional[str]) -> str:
    """Corrige les espaces et les mojibakes les plus fréquents du XML ROME."""
    if text is None:
        return ""
    t = str(text).strip()
    if not t:
        return ""
    # Certaines données ROME apparaissent en mojibake après parsing selon l'environnement.
    if any(x in t for x in ["Ã", "Â", "Å", "Ž", "š", "œ"]):
        for enc in ("latin1", "cp1252"):
            try:
                candidate = t.encode(enc, errors="ignore").decode("utf-8", errors="ignore")
                if candidate and candidate.count("�") <= t.count("�") and candidate.count("Ã") < t.count("Ã"):
                    t = candidate
                    break
            except Exception:
                pass
    t = t.replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t)
    return t


def safe_key(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def normalize(s: str) -> str:
    s = clean_text(s).lower()
    repl = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
    return re.sub(r"[^a-z0-9]+", " ", s.translate(repl)).strip()


def code_matches(a: str, b: str) -> bool:
    return normalize(a).replace(" ", "") == normalize(b).replace(" ", "")


def make_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def init_state() -> None:
    defaults = {
        "authorized": False,
        "access_code": "",
        "generated_code": "",
        "beneficiaire": {},
        "shortlist": [],
        "analyses": {},
        "constraints": {},
        "cross_data": {},
        "decision": {},
        "sessions": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "last_activity": time.time(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def touch() -> None:
    st.session_state.updated_at = now_iso()
    st.session_state.last_activity = time.time()


# -----------------------------
# SMTP optionnel
# -----------------------------

def get_secret(name: str, default: str = "") -> str:
    """Compatibilité ancienne et nouvelle configuration Secrets.
    Priorité à la section [email] utilisée par les autres apps Clarté360.
    Fallback sur les clés plates SMTP_* si une ancienne configuration existe.
    """
    try:
        if "email" in st.secrets:
            e = st.secrets.get("email", {})
            mapping = {
                "SMTP_HOST": "smtp_server",
                "SMTP_PORT": "smtp_port",
                "SMTP_USER": "smtp_user",
                "SMTP_PASSWORD": "smtp_password",
                "SMTP_FROM": "from_email",
                "ADMIN_EMAIL": "to_email",
            }
            key = mapping.get(name, name)
            if key in e and e.get(key):
                return str(e.get(key))
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def smtp_configured() -> bool:
    return bool(get_secret("SMTP_HOST") and get_secret("SMTP_USER") and get_secret("SMTP_PASSWORD") and get_secret("SMTP_FROM"))


def send_mail(to_email: str, subject: str, body: str, attachments: Optional[List[Tuple[str, bytes, str]]] = None) -> Tuple[bool, str]:
    """Envoie un email avec la même logique que les apps Préférences/Moteurs.
    Secrets attendus :
    [email]
    smtp_server, smtp_port, smtp_user, smtp_password, from_email, to_email
    """
    if not smtp_configured():
        return False, "SMTP non configuré dans les Secrets Streamlit."
    try:
        host = get_secret("SMTP_HOST")
        port = int(get_secret("SMTP_PORT", "465"))
        user = get_secret("SMTP_USER")
        pwd = get_secret("SMTP_PASSWORD")
        sender = get_secret("SMTP_FROM", user)
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        for filename, payload, mime in attachments or []:
            maintype, subtype = mime.split("/", 1) if "/" in mime else ("application", "octet-stream")
            msg.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=25) as server:
                server.login(user, pwd)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=25) as server:
                server.starttls()
                server.login(user, pwd)
                server.send_message(msg)
        return True, "Email envoyé."
    except Exception as e:
        return False, f"Erreur email : {e}"

# -----------------------------
# Chargement ROME
# -----------------------------

@dataclass
class RomeItem:
    code_rome: str
    intitule: str
    definition: str
    acces_metier: str
    appellations: List[str]
    competences: List[Dict[str, str]]
    contextes: List[Dict[str, str]]
    secteurs: List[str]
    riasec: str = ""


def elem_text(elem: Optional[ET.Element], path: str = "") -> str:
    if elem is None:
        return ""
    target = elem.find(path) if path else elem
    return clean_text(target.text if target is not None else "")


def extract_items(parent: ET.Element, section: str, item_type: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    sec = parent.find(section)
    if sec is None:
        return out
    # Savoir-faire et savoir-être : enjeux/enjeu/items/item
    for enjeu in sec.findall(".//enjeu"):
        group = elem_text(enjeu, "libelle")
        for item in enjeu.findall(".//item"):
            lib = elem_text(item, "libelle")
            if lib:
                out.append({
                    "type": item_type,
                    "groupe": group,
                    "libelle": lib,
                    "code_ogr": elem_text(item, "code_ogr"),
                    "coeur_metier": elem_text(item, "coeur_metier") or "Secondaire",
                })
    # Savoirs : categories/categorie/items/item
    for cat in sec.findall(".//categorie"):
        group = elem_text(cat, "libelle")
        for item in cat.findall(".//item"):
            lib = elem_text(item, "libelle")
            if lib:
                out.append({
                    "type": item_type,
                    "groupe": group,
                    "libelle": lib,
                    "code_ogr": elem_text(item, "code_ogr"),
                    "coeur_metier": elem_text(item, "coeur_metier") or "Secondaire",
                })
    return out


@st.cache_data(show_spinner="Chargement du référentiel ROME...")
def load_riasec_table() -> Dict[str, str]:
    if not RIASEC_XLSX.exists():
        return {}
    df = pd.read_excel(RIASEC_XLSX, sheet_name="ROME_RIASEC")
    cols = {c.lower(): c for c in df.columns}
    code_col = cols.get("code rome") or df.columns[0]
    riasec_col = cols.get("riasec normalise") or cols.get("riasec fiche") or df.columns[2]
    return {clean_text(r[code_col]).upper(): clean_text(r[riasec_col]).upper() for _, r in df.iterrows() if clean_text(r[code_col])}


@st.cache_data(show_spinner="Lecture de RefRomeXml.zip...")
def load_rome() -> Dict[str, Dict[str, Any]]:
    if not ROME_ZIP.exists():
        st.error("Fichier data/RefRomeXml.zip absent.")
        return {}
    riasec_map = load_riasec_table()
    with zipfile.ZipFile(ROME_ZIP) as z:
        fname = [n for n in z.namelist() if "fiche_emploi_metier" in n][0]
        raw = z.read(fname)
    root = ET.fromstring(raw)
    data: Dict[str, Dict[str, Any]] = {}
    for fiche in root.findall("fiche_metier"):
        code = elem_text(fiche, "rome/code_rome").upper()
        if not code:
            continue
        appellations = []
        for a in fiche.findall(".//appellations/appellation"):
            lib = elem_text(a, "libelle")
            if lib:
                appellations.append(lib)
        comp_parent = fiche.find("competences")
        competences: List[Dict[str, str]] = []
        if comp_parent is not None:
            competences.extend(extract_items(comp_parent, "savoir_faire", "Savoir-faire"))
            competences.extend(extract_items(comp_parent, "savoir_etre_professionnel", "Savoir-être professionnel"))
            competences.extend(extract_items(comp_parent, "savoirs", "Savoir"))
        contextes = []
        for tc in fiche.findall(".//contextes_travail/type_contexte"):
            group = elem_text(tc, "libelle")
            for item in tc.findall(".//item"):
                lib = elem_text(item, "libelle")
                if lib:
                    contextes.append({"groupe": group, "libelle": lib, "code_ogr": elem_text(item, "code_ogr")})
        secteurs = []
        for s in fiche.findall(".//secteurs_activite/secteur_activite"):
            lib = elem_text(s, "libelle")
            if lib:
                secteurs.append(lib)
        data[code] = {
            "code_rome": code,
            "intitule": elem_text(fiche, "rome/intitule"),
            "definition": elem_text(fiche, "definition"),
            "acces_metier": elem_text(fiche, "acces_metier"),
            "appellations": appellations,
            "competences": competences,
            "contextes": contextes,
            "secteurs": sorted(list(dict.fromkeys(secteurs))),
            "riasec": riasec_map.get(code, ""),
            "search": normalize(" ".join([code, elem_text(fiche, "rome/intitule")] + appellations)),
        }
    return data


def search_rome(query: str, rome: Dict[str, Dict[str, Any]], limit: int = 30) -> List[Dict[str, Any]]:
    q = normalize(query)
    if not q:
        return []
    tokens = q.split()
    res = []
    for item in rome.values():
        score = 0
        if item["code_rome"].lower().startswith(q.lower()):
            score += 100
        title_norm = normalize(item["intitule"])
        if q in title_norm:
            score += 80
        if q in item["search"]:
            score += 40
        score += sum(8 for t in tokens if t in item["search"])
        if score:
            res.append((score, item))
    res.sort(key=lambda x: (-x[0], x[1]["code_rome"]))
    return [r[1] for r in res[:limit]]


# -----------------------------
# Export / import JSON et PDF
# -----------------------------

def export_state() -> Dict[str, Any]:
    return {
        "app": "Clarté360 Outil 5",
        "version": APP_VERSION,
        "exported_at": now_iso(),
        "created_at": st.session_state.created_at,
        "updated_at": st.session_state.updated_at,
        "beneficiaire": st.session_state.beneficiaire,
        "shortlist": st.session_state.shortlist,
        "analyses": st.session_state.analyses,
        "constraints": st.session_state.constraints,
        "cross_data": st.session_state.cross_data,
        "decision": st.session_state.decision,
        "sessions": st.session_state.sessions,
    }


def import_state(payload: Dict[str, Any]) -> None:
    for k in ["beneficiaire", "shortlist", "analyses", "constraints", "cross_data", "decision", "sessions", "created_at", "updated_at"]:
        if k in payload:
            st.session_state[k] = payload[k]
    st.session_state.authorized = True
    touch()


def make_json_download() -> bytes:
    return json.dumps(export_state(), ensure_ascii=False, indent=2).encode("utf-8")


def score_for_job(code: str) -> Dict[str, Any]:
    analyses = st.session_state.analyses.get(code, {})
    comp = analyses.get("competences", {})
    vals = []
    for v in comp.values():
        sc = STATUS_SCORE.get(v.get("statut"))
        if sc is not None:
            vals.append(sc)
    competence_score = round(sum(vals) / len(vals) * 100, 1) if vals else 0
    constraints = st.session_state.constraints.get(code, {})
    criteria = {
        "Compétences": competence_score,
        "Valeurs": float(constraints.get("valeurs", 50)),
        "Préférences": float(constraints.get("preferences", 50)),
        "Moteurs professionnels": float(constraints.get("moteurs", constraints.get("moteurs", 50))),
        "RIASEC": float(constraints.get("riasec", 50)),
        "Contraintes": float(constraints.get("contraintes", 50)),
        "Mobilité": float(constraints.get("mobilite", 50)),
        "Formation": float(constraints.get("formation", 50)),
        "Marché": float(constraints.get("marche", 50)),
    }
    weights = {
        "Compétences": 25,
        "Valeurs": 10,
        "Préférences": 10,
        "Moteurs professionnels": 15,
        "RIASEC": 5,
        "Contraintes": 10,
        "Mobilité": 5,
        "Formation": 10,
        "Marché": 10,
    }
    total = sum(criteria[k] * weights[k] for k in criteria) / sum(weights.values())
    return {"score": round(total, 1), "criteria": criteria, "weights": weights}



def comp_key(code: str, c: Dict[str, str]) -> str:
    return safe_key(code, c.get("code_ogr", ""), c.get("type", ""), c.get("libelle", ""))


def all_competence_rows(code: str, rome: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    item = rome.get(code, {})
    comp_data = st.session_state.analyses.setdefault(code, {}).setdefault("competences", {})
    rows = []
    for c in item.get("competences", []):
        k = comp_key(code, c)
        current = comp_data.setdefault(k, {
            "statut": "Non renseigné", "preuve": "", "plan": "", "commentaire": "",
            "libelle": c.get("libelle", ""), "type": c.get("type", ""),
            "groupe": c.get("groupe", ""), "coeur_metier": c.get("coeur_metier", ""),
            "code_ogr": c.get("code_ogr", "")
        })
        rows.append({"key": k, **c, **current})
    return rows


def competence_stats(code: str, rome: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    rows = all_competence_rows(code, rome)
    total = len(rows)
    counts = {"Acquis": 0, "En cours d'acquisition": 0, "Non acquis": 0, "Non applicable": 0, "Non renseigné": 0}
    by_family: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        statut = r.get("statut", "Non renseigné") or "Non renseigné"
        if statut not in counts:
            counts[statut] = 0
        counts[statut] += 1
        fam = r.get("type", "Autre") or "Autre"
        fam_row = by_family.setdefault(fam, {"Famille": fam, "Total": 0, "A": 0, "ECA": 0, "NA": 0, "NR": 0, "% acquis": 0.0})
        fam_row["Total"] += 1
        if statut == "Acquis": fam_row["A"] += 1
        elif statut == "En cours d'acquisition": fam_row["ECA"] += 1
        elif statut == "Non acquis": fam_row["NA"] += 1
        elif statut != "Non applicable": fam_row["NR"] += 1
    for fam_row in by_family.values():
        fam_row["% acquis"] = round(fam_row["A"] / fam_row["Total"] * 100, 1) if fam_row["Total"] else 0
    return {"total": total, "counts": counts, "families": list(by_family.values()), "rows": rows}


def status_short(statut: str) -> str:
    return {
        "Acquis": "🟢 A",
        "En cours d'acquisition": "🟠 ECA",
        "Non acquis": "🔴 NA",
        "Non applicable": "⚪ N.A.",
        "Non renseigné": "⚫ NR",
    }.get(statut or "Non renseigné", "⚫ NR")


def pct_label(n: int, total: int) -> str:
    return f"{n} / {total} ({round(n/total*100,1) if total else 0} %)"


def appreciation(score: float) -> str:
    if score >= 80: return "Très élevée"
    if score >= 65: return "Élevée"
    if score >= 50: return "À approfondir"
    if score >= 35: return "Fragile"
    return "Très fragile"


def parse_clarte_json(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extrait les éléments utiles depuis les JSON Clarté360 existants.
    Les apps Préférences et Moteurs stockent déjà les scores sous la clé scores.
    """
    out = {"raw": payload, "scores": [], "top": [], "low": [], "summary": ""}
    scores = payload.get("scores") or payload.get("resultats") or []
    if isinstance(scores, dict):
        scores = list(scores.values())
    clean_scores = []
    for r in scores if isinstance(scores, list) else []:
        if not isinstance(r, dict):
            continue
        label = r.get("Dimension") or r.get("Moteur") or r.get("Valeur") or r.get("Libellé") or r.get("libelle") or r.get("Code") or "Élément"
        pct = r.get("Pourcentage") if "Pourcentage" in r else r.get("score") if "score" in r else r.get("Score")
        try:
            pct = float(str(pct).replace("%", "").replace(",", "."))
        except Exception:
            pct = None
        clean_scores.append({"Libellé": clean_text(label), "Pourcentage": pct, "Lecture": clean_text(r.get("Lecture", ""))})
    clean_scores = [r for r in clean_scores if r["Pourcentage"] is not None]
    clean_scores.sort(key=lambda x: x["Pourcentage"], reverse=True)
    out["scores"] = clean_scores
    out["top"] = clean_scores[:3]
    out["low"] = sorted(clean_scores, key=lambda x: x["Pourcentage"])[:3]
    if clean_scores:
        out["summary"] = "Principaux résultats : " + ", ".join(f"{r['Libellé']} ({r['Pourcentage']:.0f} %)" for r in clean_scores[:3])
    return out


def render_import_analysis(label: str, key: str, cross: Dict[str, Any]) -> None:
    block = cross.get(key, {}) if isinstance(cross.get(key), dict) else {}
    parsed = block.get("parsed") or {}
    notes = block.get("notes", "")
    if parsed.get("scores"):
        df = pd.DataFrame(parsed["scores"])
        st.dataframe(df, hide_index=True, use_container_width=True)
        chart_df = df.set_index("Libellé")[["Pourcentage"]]
        st.bar_chart(chart_df, height=220)
        st.caption("Ces données seront reprises dans la synthèse et croisées avec les métiers retenus. Le radar détaillé sera reconstruit dans l'interface Consultant à partir du JSON complet.")
    elif notes:
        st.info("Aucun score structuré détecté automatiquement dans ce JSON ; la note de synthèse sera conservée.")
    else:
        st.caption("Aucun élément importé pour le moment.")


def riasec_match(user_code: str, job_code: str) -> Tuple[int, str]:
    user = clean_text(user_code).upper().replace(" ", "")
    job = clean_text(job_code).upper().replace(" ", "")
    if not user or not job:
        return 50, "Non déterminé"
    score = 0
    if len(user) >= 1 and user[0] in job[:1]: score += 60
    if len(user) >= 2 and user[1] in job[:2]: score += 30
    if len(user) >= 3 and user[2] in job[:3]: score += 10
    return min(score, 100), "Très cohérent" if score >= 80 else "Cohérent" if score >= 50 else "À explorer"


def plan_action_from_competences(code: str, rome: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for i, r in enumerate(all_competence_rows(code, rome), start=1):
        statut = r.get("statut")
        action = clean_text(r.get("plan", ""))
        if statut in ("En cours d'acquisition", "Non acquis") and action:
            rows.append({
                "ID": f"PA-{i:03d}",
                "Ind": "",
                "Origine": f"ROME {code} – {r.get('type','')} – {r.get('libelle','')} – {status_short(statut)}",
                "Famille": r.get("type", ""),
                "Compétence concernée": r.get("libelle", ""),
                "Statut origine": statut,
                "Action à réaliser": action,
                "Moyens externes / internes": "",
                "Objectif visé par cette action": f"Acquérir ou renforcer : {r.get('libelle','')}",
                "Date de réalisation": "",
                "Indicateur de réussite": "",
                "Commentaires": "",
            })
    return rows


def regroup_plan_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    result = []
    for r in rows:
        ind = clean_text(str(r.get("Ind", "")))
        if not ind:
            result.append(r)
            continue
        if ind not in grouped:
            grouped[ind] = dict(r)
            result.append(grouped[ind])
        else:
            base = grouped[ind]
            for col in ["Origine", "Famille", "Compétence concernée", "Action à réaliser", "Moyens externes / internes", "Objectif visé par cette action", "Indicateur de réussite", "Commentaires"]:
                a = clean_text(str(base.get(col, "")))
                b = clean_text(str(r.get(col, "")))
                if b and b not in a:
                    base[col] = (a + "\n" + b).strip() if a else b
            if not clean_text(str(base.get("Date de réalisation", ""))) and clean_text(str(r.get("Date de réalisation", ""))):
                base["Date de réalisation"] = r.get("Date de réalisation", "")
    return result

def validate_job_analysis(code: str, rome: Dict[str, Dict[str, Any]]) -> List[str]:
    """Retourne les points à compléter pour rendre l'analyse exploitable."""
    warnings: List[str] = []
    comp_data = st.session_state.analyses.get(code, {}).get("competences", {})
    if not comp_data:
        warnings.append("Aucune compétence ROME n'a encore été analysée.")
        return warnings
    for key, row in comp_data.items():
        statut = row.get("statut", "Non renseigné")
        lib = row.get("libelle", key)
        preuve = clean_text(row.get("preuve", ""))
        plan = clean_text(row.get("plan", ""))
        if statut in ("Acquis", "En cours d'acquisition") and len(preuve) < 10:
            warnings.append(f"Preuve à compléter pour : {lib}")
        if statut in ("En cours d'acquisition", "Non acquis") and len(plan) < 10:
            warnings.append(f"Plan d'acquisition à compléter pour : {lib}")
        if statut == "Non renseigné":
            warnings.append(f"Statut non renseigné pour : {lib}")
    return warnings[:30]


def global_validation(rome: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    missing: List[str] = []
    if not st.session_state.beneficiaire.get("nom") or not st.session_state.beneficiaire.get("prenom"):
        missing.append("Identité bénéficiaire incomplète.")
    if not st.session_state.shortlist:
        missing.append("Aucun métier sélectionné.")
    for code in st.session_state.shortlist:
        for w in validate_job_analysis(code, rome):
            missing.append(f"{code} – {w}")
    if not st.session_state.decision.get("choix_final"):
        missing.append("Projet final non sélectionné.")
    if not st.session_state.decision.get("validation_beneficiaire"):
        missing.append("Confirmation du libre choix par le bénéficiaire non cochée.")
    return {"ok": len(missing) == 0, "missing": missing}


def pdf_report(rome: Dict[str, Dict[str, Any]]) -> bytes:
    if not REPORTLAB_OK:
        return b""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.4*cm, leftMargin=1.4*cm, topMargin=1.4*cm, bottomMargin=1.4*cm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ClarteTitle", parent=styles["Title"], textColor=colors.HexColor(CLARTE_TEAL_DARK), fontSize=18, leading=22))
    styles.add(ParagraphStyle(name="ClarteH", parent=styles["Heading2"], textColor=colors.HexColor(CLARTE_TEAL), fontSize=13))
    normal = styles["BodyText"]
    story = []
    b = st.session_state.beneficiaire
    story.append(Paragraph("Clarté360 – Analyse des compétences transférables et faisabilité du projet professionnel", styles["ClarteTitle"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"Bénéficiaire : <b>{b.get('prenom','')} {b.get('nom','')}</b>", normal))
    story.append(Paragraph(f"Email : {b.get('email','')}", normal))
    story.append(Paragraph(f"Export : {now_iso()}", normal))
    if st.session_state.sessions:
        story.append(Paragraph("Connexions : " + "; ".join([f"{x.get('event','')} {x.get('at','')}" for x in st.session_state.sessions]), normal))
    story.append(Spacer(1, 0.4*cm))

    # Données importées
    story.append(Paragraph("Données Clarté360 importées", styles["ClarteH"]))
    for label, key in [("Valeurs", "valeurs"), ("Préférences professionnelles", "preferences"), ("Moteurs professionnels", "moteurs")]:
        block = st.session_state.cross_data.get(key, {}) if isinstance(st.session_state.cross_data.get(key), dict) else {}
        parsed = block.get("parsed", {})
        note = block.get("notes", "")
        summary = parsed.get("summary") or note or "Non renseigné"
        story.append(Paragraph(f"<b>{label}</b> : {clean_text(summary)}", normal))
    rblock = st.session_state.cross_data.get("riasec", {}) if isinstance(st.session_state.cross_data.get("riasec"), dict) else {}
    story.append(Paragraph(f"<b>RIASEC Diagoriente</b> : {rblock.get('profil','Non renseigné')}", normal))
    story.append(Spacer(1, 0.4*cm))

    for code in st.session_state.shortlist:
        item = rome.get(code, {})
        story.append(Paragraph(f"{code} – {item.get('intitule','')}", styles["ClarteH"]))
        story.append(Paragraph(f"RIASEC métier : {item.get('riasec','Non renseigné')}", normal))
        if item.get("definition"):
            story.append(Paragraph(clean_text(item.get("definition", "")), normal))
        sc = score_for_job(code)
        story.append(Paragraph(f"Compatibilité globale : <b>{appreciation(sc['score'])}</b>", normal))
        stats = competence_stats(code, rome)
        total = stats["total"]
        counts = stats["counts"]
        story.append(Paragraph(f"Total compétences ROME : <b>{total}</b> – Acquises : {pct_label(counts.get('Acquis',0), total)} – ECA : {pct_label(counts.get('En cours d\'acquisition',0), total)} – NA : {pct_label(counts.get('Non acquis',0), total)}", normal))
        if stats["families"]:
            rows = [["Famille", "Total", "A", "ECA", "NA", "% acquis"]]
            for r in stats["families"]:
                rows.append([r["Famille"], r["Total"], r["A"], r["ECA"], r["NA"], r["% acquis"]])
            table = Table(rows, colWidths=[5.2*cm, 2*cm, 1.5*cm, 1.5*cm, 1.5*cm, 2*cm])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor(CLARTE_TEAL)),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ]))
            story.append(table)
        with_calc = [["Critère", "Score", "Pondération"]] + [[k, str(sc["criteria"][k]), str(sc["weights"][k])] for k in sc["criteria"]]
        table = Table(with_calc, colWidths=[6.5*cm, 3*cm, 3*cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor(CLARTE_TEAL)),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ]))
        story.append(Spacer(1, 0.2*cm))
        story.append(table)
        story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Décision finale", styles["ClarteH"]))
    choice = st.session_state.decision.get("choix_final", "Non renseigné")
    story.append(Paragraph(f"Projet retenu : <b>{choice}</b>", normal))
    story.append(Paragraph(st.session_state.decision.get("justification", ""), normal))
    story.append(Paragraph("Plan d'action", styles["ClarteH"]))
    plan_rows = st.session_state.decision.get("plan_action_rows", [])
    if plan_rows:
        rows = [["Origine", "Action", "Moyens", "Objectif", "Date", "Indicateur"]]
        for r in plan_rows[:60]:
            rows.append([clean_text(str(r.get("Origine", "")))[:90], clean_text(str(r.get("Action à réaliser", "")))[:90], clean_text(str(r.get("Moyens externes / internes", "")))[:70], clean_text(str(r.get("Objectif visé par cette action", "")))[:80], clean_text(str(r.get("Date de réalisation", ""))), clean_text(str(r.get("Indicateur de réussite", "")))[:70]])
        table = Table(rows, colWidths=[3.2*cm, 3.4*cm, 2.8*cm, 3.2*cm, 2*cm, 3*cm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor(CLARTE_TEAL)),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("Plan d'action non généré.", normal))
    doc.build(story)
    return buf.getvalue()


# -----------------------------
# UI
# -----------------------------

def inject_css() -> None:
    st.markdown(f"""
    <style>
    .stApp {{ background: {CLARTE_BG}; }}
    h1, h2, h3 {{ color: {CLARTE_DARK}; }}
    .clarte-title {{ color: {CLARTE_TEAL} !important; margin-bottom:0.2rem; }}
    .clarte-subtitle {{ color:#6B7280; font-size:1.05rem; margin-top:0.2rem; }}
    .clarte-card {{
        background:#FFFFFF; border:1px solid #D7ECEA; border-radius:18px; padding:22px;
        box-shadow:0 4px 14px rgba(0,0,0,0.04); margin-bottom:16px;
    }}
    .metric-card {{background:#fff; border-left:6px solid {CLARTE_TEAL}; border-radius:12px; padding:14px;}}
    .small-muted {{ color:#7B7F88; font-size:0.92rem; }}
    div.stButton > button:first-child {{ background:{CLARTE_TEAL}; color:white; border-radius:10px; border:0; }}
    div.stDownloadButton > button:first-child {{ border-radius:10px; }}
    </style>
    """, unsafe_allow_html=True)


def header() -> None:
    cols = st.columns([1, 7])
    with cols[0]:
        if ICON.exists():
            st.image(str(ICON), width=105)
    with cols[1]:
        st.markdown('<h1 class="clarte-title">Clarté360 - Analyse des compétences transférables et faisabilité du projet professionnel</h1>', unsafe_allow_html=True)
        st.markdown("<div class='clarte-subtitle'>Version 1.2 - outil propriétaire d’exploration des compétences, de la faisabilité et du plan d’action</div>", unsafe_allow_html=True)


def objectif_outil_card() -> None:
    st.markdown("""
    <div class='clarte-card'>
        <h3 style='margin-top:0;'>Objectif de l'outil</h3>
        <p>
        Cet outil permet d'analyser l'adéquation entre un ou plusieurs projets professionnels et les compétences attendues dans le référentiel ROME.
        Il aide à repérer les compétences déjà acquises, celles en cours d'acquisition et celles qui restent à développer.
        </p>
        <p>
        L'objectif n'est pas de décider automatiquement à la place du bénéficiaire, mais de construire une lecture structurée : compétences transférables,
        cohérence avec les valeurs, préférences professionnelles, moteurs professionnels, RIASEC, contraintes, mobilité et faisabilité du projet.
        </p>
        <p>
        Le résultat sert de support d'échange avec le consultant Clarté360 et alimente le choix final ainsi que le plan d'action du bilan de compétences.
        </p>
    </div>
    """, unsafe_allow_html=True)


def access_screen() -> None:
    header()
    objectif_outil_card()
    st.markdown("<div class='clarte-card'>", unsafe_allow_html=True)
    st.subheader("Accès bénéficiaire")
    st.write("Cet outil n'est pas un test psychométrique. Il sert de support d'analyse et d'échange avec le consultant Clarté360.")
    c1, c2 = st.columns(2)
    with c1:
        prenom = st.text_input("Prénom *")
        nom = st.text_input("Nom *")
    with c2:
        email = st.text_input("Adresse email *")
        consultant = st.text_input("Consultant", value="Clarté360")
    consent = st.checkbox("Je comprends que mes réponses seront utilisées uniquement dans le cadre de mon bilan de compétences.")
    if st.button("Recevoir / générer mon code d'accès"):
        if not (prenom and nom and email and consent):
            st.error("Merci de compléter les champs obligatoires et de confirmer le consentement.")
        else:
            code = make_code()
            st.session_state.generated_code = code
            st.session_state.beneficiaire = {"prenom": prenom, "nom": nom, "email": email, "consultant": consultant}
            msg = f"Bonjour {prenom},\n\nVotre code d'accès Clarté360 est : {code}\n\nCe code vous permet d'ouvrir votre session et de sauvegarder votre travail."
            ok, info = send_mail(email, "Votre code d'accès Clarté360", msg)
            admin_email = get_secret("ADMIN_EMAIL", "contact@clarte360.com")
            send_mail(admin_email, "Connexion Clarté360 – Compétences projets", f"Code généré pour {prenom} {nom} - {email} - {now_iso()}")
            if ok:
                st.success("Code envoyé par email.")
            else:
                st.warning(info)
                st.info(f"Mode test : code généré = {code}")
    code_in = st.text_input("Saisir le code d'accès", type="password")
    if st.button("Entrer dans l'outil"):
        if code_in and (code_in == st.session_state.generated_code or code_in == get_secret("MASTER_CODE", "CLARTE360")):
            st.session_state.authorized = True
            st.session_state.sessions.append({"event": "start", "at": now_iso(), "code": code_in[:2] + "****"})
            touch()
            st.rerun()
        else:
            st.error("Code incorrect.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Reprendre à partir d'une sauvegarde JSON")
    upl = st.file_uploader("Importer une sauvegarde Outil 5 (.json)", type=["json"])
    if upl:
        try:
            payload = json.loads(upl.read().decode("utf-8"))
            import_state(payload)
            st.success("Sauvegarde importée.")
            st.rerun()
        except Exception as e:
            st.error(f"Import impossible : {e}")


def sidebar_exports(rome: Dict[str, Dict[str, Any]]) -> None:
    st.sidebar.markdown("### Sauvegarde")
    val = global_validation(rome)
    if val["ok"]:
        st.sidebar.success("Dossier complet")
    else:
        st.sidebar.warning(f"{len(val['missing'])} point(s) à compléter")
    st.sidebar.download_button("Télécharger JSON intermédiaire", data=make_json_download(), file_name="clarte360_outil5_sauvegarde.json", mime="application/json")
    if REPORTLAB_OK:
        st.sidebar.download_button("Télécharger rapport PDF", data=pdf_report(rome), file_name="clarte360_outil5_rapport.pdf", mime="application/pdf")
    st.sidebar.caption(f"Version {APP_VERSION} — dernière activité : {st.session_state.updated_at}")


def tab_identite() -> None:
    st.subheader("1. Bénéficiaire et contexte")
    b = st.session_state.beneficiaire.copy()
    c1, c2 = st.columns(2)
    with c1:
        b["prenom"] = st.text_input("Prénom", value=b.get("prenom", ""))
        b["nom"] = st.text_input("Nom", value=b.get("nom", ""))
        b["email"] = st.text_input("Email", value=b.get("email", ""))
    with c2:
        b["situation"] = st.selectbox("Situation actuelle", ["", "Salarié", "Demandeur d'emploi", "Indépendant", "Agent public", "Autre"], index=0 if not b.get("situation") else ["", "Salarié", "Demandeur d'emploi", "Indépendant", "Agent public", "Autre"].index(b.get("situation")))
        b["financeur"] = st.selectbox("Financement", ["", "CPF", "Employeur", "Personnel", "France Travail", "Autre"], index=0 if not b.get("financeur") else ["", "CPF", "Employeur", "Personnel", "France Travail", "Autre"].index(b.get("financeur")))
        b["consultant"] = st.text_input("Consultant", value=b.get("consultant", ""))
    b["demande_initiale"] = st.text_area("Demande initiale / attente principale", value=b.get("demande_initiale", ""), height=110)
    b["objectif_bilan"] = st.text_area("Objectif du bilan et objectif de l'outil 5", value=b.get("objectif_bilan", ""), height=110)
    st.session_state.beneficiaire = b
    touch()


def tab_imports() -> None:
    st.subheader("2. Données des autres outils Clarté360")
    st.info("Les imports ne sont pas passifs : les JSON importés sont lus, résumés, puis utilisés pour éclairer l'adéquation aux métiers retenus. Les JSON complets restent conservés pour la future interface Clarté360 Consultant.")
    cross = st.session_state.cross_data.copy()
    tool_defs = [
        ("Roue des valeurs", "valeurs", "Importer le JSON de la roue des valeurs si disponible."),
        ("Préférences professionnelles", "preferences", "Importer le JSON de l'outil Préférences professionnelles."),
        ("Moteurs professionnels", "moteurs", "Importer le JSON de l'outil Moteurs professionnels."),
    ]
    for label, key, help_text in tool_defs:
        st.markdown(f"#### {label}")
        upl = st.file_uploader(help_text, type=["json"], key=f"upl_{key}")
        block = cross.get(key, {}) if isinstance(cross.get(key), dict) else {}
        if upl:
            try:
                raw = json.loads(upl.read().decode("utf-8"))
                block["json"] = raw
                block["parsed"] = parse_clarte_json(raw)
                st.success("JSON importé et analysé.")
            except Exception as e:
                st.error(f"Lecture impossible : {e}")
        notes = st.text_area(f"Synthèse / éléments utiles – {label}", value=block.get("notes", ""), key=f"notes_{key}", height=90)
        block["notes"] = notes
        cross[key] = block
        render_import_analysis(label, key, cross)

    st.markdown("#### RIASEC Diagoriente")
    st.caption("Le RIASEC provient de Diagoriente : il n'y a pas de JSON à importer. Saisir simplement le profil dominant utilisé pendant l'entretien.")
    rblock = cross.get("riasec", {}) if isinstance(cross.get("riasec"), dict) else {}
    cols = st.columns(3)
    with cols[0]: rblock["r1"] = st.selectbox("1er code RIASEC", [""] + list("RIASEC"), index=([""] + list("RIASEC")).index(rblock.get("r1", "")) if rblock.get("r1", "") in [""] + list("RIASEC") else 0)
    with cols[1]: rblock["r2"] = st.selectbox("2e code RIASEC", [""] + list("RIASEC"), index=([""] + list("RIASEC")).index(rblock.get("r2", "")) if rblock.get("r2", "") in [""] + list("RIASEC") else 0)
    with cols[2]: rblock["r3"] = st.selectbox("3e code optionnel", [""] + list("RIASEC"), index=([""] + list("RIASEC")).index(rblock.get("r3", "")) if rblock.get("r3", "") in [""] + list("RIASEC") else 0)
    rblock["profil"] = "".join([rblock.get("r1", ""), rblock.get("r2", ""), rblock.get("r3", "")])
    rblock["notes"] = st.text_area("Note d'interprétation RIASEC", value=rblock.get("notes", ""), height=80)
    cross["riasec"] = rblock
    st.session_state.cross_data = cross
    touch()

def tab_metiers(rome: Dict[str, Dict[str, Any]]) -> None:
    st.subheader("3. Recherche et shortlist métiers ROME")
    st.info("Sélectionnez de 1 à 3 métiers maximum. Le ROME XML fournit les compétences ; la table Clarté360 complète le RIASEC.")
    query = st.text_input("Recherche libre : intitulé, appellation, code ROME", placeholder="ex. responsable qualité, formateur, K2101...")
    results = search_rome(query, rome) if query else []
    for item in results[:15]:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{item['code_rome']} – {item['intitule']}**  ")
            st.caption(f"RIASEC : {item.get('riasec') or 'n.c.'} | {', '.join(item.get('secteurs', [])[:2])}")
        with c2:
            if st.button("Ajouter", key=f"add_{item['code_rome']}"):
                if item["code_rome"] not in st.session_state.shortlist and len(st.session_state.shortlist) < 3:
                    st.session_state.shortlist.append(item["code_rome"])
                    touch()
                    st.rerun()
                elif len(st.session_state.shortlist) >= 3:
                    st.error("Maximum 3 métiers.")
    st.markdown("### Shortlist")
    if not st.session_state.shortlist:
        st.warning("Aucun métier sélectionné.")
    for code in list(st.session_state.shortlist):
        item = rome.get(code, {})
        with st.expander(f"{code} – {item.get('intitule','')}", expanded=True):
            st.write(item.get("definition", ""))
            st.caption(f"Accès métier : {item.get('acces_metier', '')}")
            st.caption(f"RIASEC : {item.get('riasec','n.c.')} | Secteurs : {', '.join(item.get('secteurs', []))}")
            if st.button("Retirer", key=f"remove_{code}"):
                st.session_state.shortlist.remove(code)
                touch()
                st.rerun()


def tab_competences(rome: Dict[str, Dict[str, Any]]) -> None:
    st.subheader("4. Analyse Acquis / ECA / NA")
    if not st.session_state.shortlist:
        st.warning("Sélectionnez d'abord un métier dans la shortlist.")
        return
    code = st.selectbox("Métier à analyser", st.session_state.shortlist, format_func=lambda c: f"{c} – {rome[c]['intitule']}")
    item = rome[code]
    dec = st.session_state.decision
    plan_exists = bool(dec.get("plan_action_generated")) and dec.get("choix_final") == code
    if plan_exists:
        st.warning("Le plan d'action a déjà été généré à partir de cette étude des compétences. L'étude est figée pour éviter de rendre le plan incohérent.")
        allow_edit = st.checkbox("Je comprends le risque et je souhaite modifier quand même l'étude des compétences", value=False)
    else:
        allow_edit = True
    st.markdown(f"### {code} – {item['intitule']}")
    st.caption("Pour Acquis ou En cours d'acquisition : preuve obligatoire. Pour ECA ou Non acquis : action d'acquisition à renseigner pour alimenter le plan d'action.")

    stats = competence_stats(code, rome)
    total = stats["total"]
    counts = stats["counts"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total compétences ROME", total)
    c2.metric("Acquises", pct_label(counts.get("Acquis",0), total))
    c3.metric("En cours", pct_label(counts.get("En cours d'acquisition",0), total))
    c4.metric("Non acquises", pct_label(counts.get("Non acquis",0), total))
    if stats["families"]:
        with st.expander("Synthèse par famille de compétences", expanded=True):
            st.dataframe(pd.DataFrame(stats["families"]), hide_index=True, use_container_width=True)

    filt = st.multiselect("Types à afficher", ["Savoir-faire", "Savoir-être professionnel", "Savoir"], default=["Savoir-faire", "Savoir-être professionnel", "Savoir"])
    core_only = st.checkbox("Afficher uniquement les éléments principaux", value=False)
    comp_data = st.session_state.analyses.setdefault(code, {}).setdefault("competences", {})
    comps = [c for c in item["competences"] if c["type"] in filt]
    if core_only:
        comps = [c for c in comps if c.get("coeur_metier") == "Principale"]
    st.write(f"{len(comps)} éléments affichés sur {total} compétences ROME au total.")
    for c in comps:
        k = comp_key(code, c)
        current = comp_data.setdefault(k, {"statut": "Non renseigné", "preuve": "", "plan": "", "commentaire": "", "libelle": c["libelle"], "type": c["type"], "groupe": c.get("groupe",""), "coeur_metier": c.get("coeur_metier",""), "code_ogr": c.get("code_ogr", "")})
        label = f"{status_short(current.get('statut','Non renseigné'))} | {c['type']} | {c.get('groupe','')} | {c['libelle']}"
        with st.expander(label, expanded=False):
            current["statut"] = st.selectbox("Statut", STATUS_OPTIONS, index=STATUS_OPTIONS.index(current.get("statut", "Non renseigné")), key=f"statut_{k}", disabled=not allow_edit)
            current["preuve"] = st.text_area("Preuve / justification : Quand ? Où ? Comment ?", value=current.get("preuve", ""), key=f"preuve_{k}", height=80, disabled=not allow_edit)
            current["plan"] = st.text_area("Action à réaliser / Comment acquérir ou renforcer ?", value=current.get("plan", ""), key=f"plan_{k}", height=80, disabled=not allow_edit)
            current["commentaire"] = st.text_area("Commentaire consultant", value=current.get("commentaire", ""), key=f"comment_{k}", height=70, disabled=not allow_edit)
    touch()

def tab_contextes(rome: Dict[str, Dict[str, Any]]) -> None:
    st.subheader("5. Contextes ROME, contraintes et faisabilité")
    if not st.session_state.shortlist:
        st.warning("Sélectionnez d'abord un métier.")
        return
    st.info("Les contextes ROME décrivent les conditions d'exercice habituellement rencontrées dans le métier : environnement de travail, public, horaires, déplacements, type d'employeur, statut, contraintes. Ils ne sont pas des obligations, mais aident à vérifier la compatibilité concrète du projet.")
    cross = st.session_state.cross_data
    user_riasec = (cross.get("riasec", {}) if isinstance(cross.get("riasec"), dict) else {}).get("profil", "")
    for code in st.session_state.shortlist:
        item = rome[code]
        with st.expander(f"{code} – {item['intitule']}", expanded=True):
            st.markdown("**Contextes ROME**")
            if item.get("contextes"):
                ctx_df = pd.DataFrame(item.get("contextes", []))[["groupe", "libelle"]].drop_duplicates()
                st.dataframe(ctx_df, hide_index=True, use_container_width=True, height=220)
            else:
                st.caption("Aucun contexte ROME détecté pour cette fiche.")
            cdata = st.session_state.constraints.setdefault(code, {})
            job_riasec = item.get("riasec", "")
            if user_riasec and job_riasec:
                rscore, rlabel = riasec_match(user_riasec, job_riasec)
                cdata.setdefault("riasec", rscore)
                st.caption(f"RIASEC Diagoriente : {user_riasec} | RIASEC métier : {job_riasec} | Lecture : {rlabel}")
            st.markdown("**Cotation d'exploration**")
            st.caption("Cette cotation est une aide à la réflexion. Elle ne décide jamais à votre place : elle sert à préparer l'échange avec le consultant et à rendre le calcul final compréhensible.")
            fields = [
                ("valeurs", "Compatibilité valeurs", "Le métier permet-il de vivre les valeurs importantes pour le bénéficiaire ?"),
                ("preferences", "Compatibilité préférences", "Les conditions de travail correspondent-elles aux préférences professionnelles ?"),
                ("moteurs", "Compatibilité moteurs professionnels", "Le métier nourrit-il les principaux moteurs professionnels ?"),
                ("riasec", "Cohérence RIASEC", "Le profil RIASEC Diagoriente est-il proche du profil RIASEC du métier ?"),
                ("contraintes", "Contraintes personnelles", "Les contraintes personnelles sont-elles compatibles avec ce projet ?"),
                ("mobilite", "Mobilité", "La mobilité nécessaire est-elle possible et acceptée ?"),
                ("formation", "Formation accessible", "Les formations ou prérequis nécessaires sont-ils accessibles ?"),
                ("marche", "Marché / débouchés", "Le projet semble-t-il réaliste au regard des débouchés identifiés ?"),
                ("adhesion", "Adhésion bénéficiaire", "Le bénéficiaire exprime-t-il une envie réelle de poursuivre cette piste ?"),
            ]
            cols = st.columns(3)
            for i, (key, label, help_text) in enumerate(fields):
                with cols[i % 3]:
                    st.caption(help_text)
                    cdata[key] = st.slider(label, 0, 100, int(cdata.get(key, 50)), key=f"slider_{code}_{key}")
            cdata["freins"] = st.text_area("Freins / obstacles repérés", value=cdata.get("freins", ""), key=f"freins_{code}")
            cdata["leviers"] = st.text_area("Leviers / ressources", value=cdata.get("leviers", ""), key=f"leviers_{code}")
            cdata["actions"] = st.text_area("Actions à mener pour valider la faisabilité", value=cdata.get("actions", ""), key=f"actions_{code}")
    touch()

def tab_synthese(rome: Dict[str, Dict[str, Any]]) -> None:
    st.subheader("6. Synthèse comparée et aide à la décision")
    if not st.session_state.shortlist:
        st.warning("Aucun métier à comparer.")
        return
    st.info("La synthèse compare les projets, mais ne décide pas à la place du bénéficiaire. L'appréciation Clarté360 est un support d'analyse multicritères.")
    rows = []
    for code in st.session_state.shortlist:
        item = rome[code]
        sc = score_for_job(code)
        stats = competence_stats(code, rome)
        total = stats["total"]
        counts = stats["counts"]
        rows.append({
            "Code": code,
            "Métier": item["intitule"],
            "RIASEC": item.get("riasec",""),
            "Total compétences ROME": total,
            "Acquis": f"{counts.get('Acquis',0)} ({round(counts.get('Acquis',0)/total*100,1) if total else 0} %)",
            "ECA": f"{counts.get('En cours d\'acquisition',0)} ({round(counts.get('En cours d\'acquisition',0)/total*100,1) if total else 0} %)",
            "NA": f"{counts.get('Non acquis',0)} ({round(counts.get('Non acquis',0)/total*100,1) if total else 0} %)",
            "Compatibilité globale": appreciation(sc["score"]),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.warning("L'appréciation globale n'est pas une note scolaire. Elle agrège plusieurs dimensions et reste subordonnée au choix libre du bénéficiaire et à l'analyse du consultant.")

    for code in st.session_state.shortlist:
        item = rome[code]
        sc = score_for_job(code)
        stats = competence_stats(code, rome)
        total = stats["total"]
        counts = stats["counts"]
        st.markdown(f"### {code} – {item['intitule']}")
        st.markdown(f"**Compatibilité globale : {appreciation(sc['score'])}**")
        st.progress(int(sc["score"]))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total compétences ROME", total)
        c2.metric("A", pct_label(counts.get("Acquis",0), total))
        c3.metric("ECA", pct_label(counts.get("En cours d'acquisition",0), total))
        c4.metric("NA", pct_label(counts.get("Non acquis",0), total))
        if stats["families"]:
            st.dataframe(pd.DataFrame(stats["families"]), hide_index=True, use_container_width=True)
        with st.expander("Comment est calculée cette appréciation ?", expanded=False):
            st.write("L'appréciation Clarté360 est calculée à partir d'une pondération indicative. Elle sert uniquement de support d'analyse.")
            wdf = pd.DataFrame([{"Critère": k, "Score": sc["criteria"][k], "Pondération": sc["weights"][k]} for k in sc["criteria"]])
            st.dataframe(wdf, hide_index=True, use_container_width=True)
            st.caption("Pondération actuelle : compétences transférables, valeurs, préférences, moteurs professionnels, RIASEC, contraintes, mobilité, formation et marché. Cette logique pourra être ajustée dans l'interface Consultant.")

def tab_decision(rome: Dict[str, Dict[str, Any]]) -> None:
    st.subheader("7. Décision finale et plan d'action")
    dec = st.session_state.decision.copy()
    options = [""] + st.session_state.shortlist
    previous_choice = dec.get("choix_final", "")
    dec["choix_final"] = st.selectbox("Projet retenu par le bénéficiaire", options, index=options.index(dec.get("choix_final", "")) if dec.get("choix_final", "") in options else 0, format_func=lambda c: "Aucun" if c == "" else f"{c} – {rome[c]['intitule']}")
    if previous_choice and previous_choice != dec["choix_final"] and dec.get("plan_action_generated"):
        st.warning("Le projet retenu a changé alors qu'un plan d'action existe déjà. Le plan existant reste conservé mais devra être régénéré volontairement si nécessaire.")
    dec["choix_mode"] = st.radio("Mode de choix", ["Choix manuel du bénéficiaire", "Choix accompagné consultant", "Choix avec aide automatisée optionnelle"], index=["Choix manuel du bénéficiaire", "Choix accompagné consultant", "Choix avec aide automatisée optionnelle"].index(dec.get("choix_mode", "Choix manuel du bénéficiaire")))
    dec["justification"] = st.text_area("Justification du choix", value=dec.get("justification", ""), height=120)
    dec["points_vigilance"] = st.text_area("Points de vigilance", value=dec.get("points_vigilance", ""), height=100)
    dec["validation_beneficiaire"] = st.checkbox("Le bénéficiaire confirme que le choix final lui appartient", value=dec.get("validation_beneficiaire", False))

    st.markdown("### Plan d'action")
    st.caption("Le plan d'action ne concerne qu'un seul métier : le projet professionnel retenu. Il est généré depuis les compétences ECA / NA du métier choisi, puis devient indépendant.")
    chosen = dec.get("choix_final", "")
    if not chosen:
        st.warning("Sélectionnez d'abord le projet final pour générer le plan d'action.")
    else:
        if not dec.get("plan_action_generated"):
            if st.button("Générer le plan d'action à partir de l'étude des compétences"):
                dec["plan_action_rows"] = plan_action_from_competences(chosen, rome)
                dec["plan_action_generated"] = True
                dec["plan_action_source_code"] = chosen
                dec["plan_action_generated_at"] = now_iso()
                st.success("Plan d'action généré. Il devient maintenant indépendant de l'étude des compétences.")
                st.session_state.decision = dec
                st.rerun()
        else:
            st.success(f"Plan d'action généré le {dec.get('plan_action_generated_at','')} à partir du métier {dec.get('plan_action_source_code','')}. Il n'est plus remis à zéro automatiquement.")
            if dec.get("plan_action_source_code") != chosen:
                st.error("Le plan d'action existant ne correspond pas au métier actuellement retenu. Utilisez une régénération volontaire uniquement si vous souhaitez repartir de zéro.")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("MAJ regroupement par Ind"):
                    dec["plan_action_rows"] = regroup_plan_rows(dec.get("plan_action_rows", []))
                    st.session_state.decision = dec
                    st.rerun()
            with col_b:
                with st.expander("Régénération exceptionnelle", expanded=False):
                    st.warning("Cette action remplace le plan d'action actuel par une nouvelle extraction depuis l'étude des compétences. À utiliser uniquement volontairement.")
                    if st.button("Écraser et régénérer le plan d'action"):
                        dec["plan_action_rows"] = plan_action_from_competences(chosen, rome)
                        dec["plan_action_generated"] = True
                        dec["plan_action_source_code"] = chosen
                        dec["plan_action_generated_at"] = now_iso()
                        st.session_state.decision = dec
                        st.rerun()

        rows = dec.get("plan_action_rows", [])
        if dec.get("plan_action_generated"):
            if not rows:
                st.info("Aucune action issue des compétences ECA / NA n'a été trouvée. Vous pouvez ajouter des lignes manuellement.")
            df = pd.DataFrame(rows)
            base_cols = ["Ind", "Origine", "Action à réaliser", "Moyens externes / internes", "Objectif visé par cette action", "Date de réalisation", "Indicateur de réussite", "Commentaires", "ID", "Famille", "Compétence concernée", "Statut origine"]
            for col in base_cols:
                if col not in df.columns:
                    df[col] = ""
            edited = st.data_editor(df[base_cols], use_container_width=True, num_rows="dynamic", hide_index=True, key="plan_action_editor")
            dec["plan_action_rows"] = edited.to_dict(orient="records")
            with st.expander("Comprendre l'origine des actions", expanded=False):
                st.write("La colonne Origine explique pourquoi une action apparaît dans le plan : elle reprend le code ROME, la famille de compétence, la compétence concernée et le statut ECA / NA au moment de la génération.")
                st.write("Les colonnes techniques ID, Famille, Compétence concernée et Statut origine seront utiles pour la traçabilité et la future interface Clarté360 Consultant.")

    st.session_state.decision = dec
    val = global_validation(rome)
    if val["ok"]:
        st.success("Dossier prêt : le JSON final et le rapport PDF peuvent être transmis.")
    else:
        with st.expander(f"Points à compléter avant clôture ({len(val['missing'])})", expanded=False):
            for m in val["missing"][:80]:
                st.write("- " + m)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("Télécharger JSON final", data=make_json_download(), file_name="clarte360_outil5_final.json", mime="application/json")
    with c2:
        if REPORTLAB_OK:
            st.download_button("Télécharger PDF final", data=pdf_report(rome), file_name="clarte360_outil5_rapport_final.pdf", mime="application/pdf")
    with c3:
        if st.button("Clôturer et envoyer à Clarté360"):
            st.session_state.sessions.append({"event": "end", "at": now_iso()})
            admin_email = get_secret("ADMIN_EMAIL", "contact@clarte360.com")
            b = st.session_state.beneficiaire
            attachments = [("clarte360_outil5_final.json", make_json_download(), "application/json")]
            if REPORTLAB_OK:
                attachments.append(("clarte360_outil5_rapport_final.pdf", pdf_report(rome), "application/pdf"))
            ok, info = send_mail(admin_email, f"Clarté360 Compétences projets final – {b.get('prenom','')} {b.get('nom','')}", "Dossier Outil 5 clôturé en pièce jointe.", attachments=attachments)
            if ok:
                st.success("Dossier envoyé à Clarté360.")
            else:
                st.warning(info)
                st.info("SMTP absent : télécharge le JSON/PDF final et transmets-les manuellement.")
    touch()

def main_app() -> None:
    rome = load_rome()
    header()
    st.success(f"Référentiel chargé : {len(rome)} fiches ROME. Table RIASEC : {len(load_riasec_table())} correspondances.")
    sidebar_exports(rome)
    tabs = st.tabs(["1 Identité", "2 Imports", "3 Métiers", "4 Compétences", "5 Faisabilité", "6 Synthèse", "7 Décision"])
    with tabs[0]: tab_identite()
    with tabs[1]: tab_imports()
    with tabs[2]: tab_metiers(rome)
    with tabs[3]: tab_competences(rome)
    with tabs[4]: tab_contextes(rome)
    with tabs[5]: tab_synthese(rome)
    with tabs[6]: tab_decision(rome)


def main() -> None:
    st.set_page_config(page_title="Clarté360 – Compétences & projets", page_icon=str(ICON) if ICON.exists() else "🧭", layout="wide")
    inject_css()
    init_state()
    # Auto-sauvegarde conceptuelle : en Streamlit Cloud, le vrai téléchargement automatique navigateur est bloqué.
    # On conserve l'état en session et on fournit toujours le bouton JSON.
    if not st.session_state.authorized:
        access_screen()
    else:
        main_app()


if __name__ == "__main__":
    main()
