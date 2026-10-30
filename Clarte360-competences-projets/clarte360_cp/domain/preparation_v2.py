"""GO22 RC3 - parcours unique C-AV1 suivi de C-AV2.

Regles metier deterministes. Les donnees du questionnaire proviennent des
sources autorisees et des choix de l'accompagnateur; aucun score n'impose un
choix et aucun appel IA n'est realise pendant la passation beneficiaire.

Le format RC2 est conserve par la couche de compatibilite domain.preparation.
"""
from __future__ import annotations

import copy
import hashlib

SCHEMA_Q_V2 = "GO22_CAV1_CAV2_QUESTIONNAIRE_UNIQUE_V2"
SCHEMA_R_V2 = "GO22_CAV1_CAV2_REPONSES_UNIQUES_V2"
REASON_NONE = ("AUCUN_CRITERE_IDENTIFIE", "A_AFFINER")
CHOICE_POLE = ("POLE_1", "EQUILIBRE", "POLE_2", "AUTRE")
CHOICE_IMPORTANCE = ("INDISPENSABLE", "IMPORTANT_ADAPTABLE")
SITUATION_CHOICES = ("OUI", "NON", "PAS_IDENTIFIEE")
INTEREST_CHOICES = ("EXPLORER", "ACTIVITES_LIEES", "NON_ACTUELLEMENT", "INDECISE")
DEFAULT_CONTEXT_CHOICES = [
    "Dans une organisation existante", "Dans une entreprise familiale",
    "Dans ma propre activité ou entreprise", "Dans un cadre salarié",
    "Dans une autre fonction liée à ce secteur", "Plusieurs contextes possibles",
    "Je ne sais pas encore", "Autre contexte",
]
DEFAULT_CONTEXT_PROMPT = "Envisagez-vous cette piste dans un contexte particulier d'exercice ?"
VAL_QUESTION = "Parmi les valeurs qui ont émergé dans votre Boussole, lesquelles souhaitez-vous absolument préserver dans votre prochain travail ?"
VAL_FREE = "Sans vous appuyer sur un questionnaire précédent, quelles valeurs souhaitez-vous préserver dans votre prochaine activité professionnelle ?"
MOT_QUESTION = "Quels moteurs souhaitez-vous retrouver régulièrement dans votre prochaine activité pour rester engagé(e) et motivé(e) ?"
MOT_FREE = "Quelles activités ou réalisations vous donnent le plus envie de vous investir dans un travail ?"
PREF_QUESTION = "Parmi ces façons de travailler, lesquelles faut-il particulièrement prendre en compte pour votre prochaine situation professionnelle ?"
PREF_FREE = "Quelles conditions concrètes vous permettraient de bien travailler dans votre prochaine situation professionnelle ?"
PREF_SITUATION = "Existe-t-il une condition concrète de travail que vous ne souhaitez absolument plus retrouver ?"
MOTOR_LABELS = ("Accomplir", "Innover", "Contribuer", "Influencer", "Comprendre", "Construire", "Transmettre", "Progresser", "Coopérer", "Être utile")


def require_text(value, name, limit=1200, required=False):
    if not isinstance(value, str):
        raise ValueError(f"{name} : texte requis.")
    value = value.strip()
    if len(value) > limit or (required and not value):
        raise ValueError(f"{name} : longueur ou contenu invalide.")
    return value


def require_list(value, name, maximum=120, width=240):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{name} : liste invalide.")
    result = []
    for v in value:
        v = require_text(v, name, width, required=True)
        if v.casefold() not in {x.casefold() for x in result}:
            result.append(v)
    return result


def _flag(value):
    if not isinstance(value, bool):
        raise ValueError("Confirmation invalide : booléen attendu.")
    return value


def _keys(x, required, label):
    if not isinstance(x, dict) or set(x) != set(required):
        raise ValueError(f"{label} : structure invalide.")


def _choice(v, allowed, name):
    if v not in allowed:
        raise ValueError(f"{name} : option inconnue.")
    return v


def _source_ref(code, item):
    return {"code": code, "source_ref": require_text(item.get("source_ref", ""), "Référence", 240, required=True),
            "label": require_text(item.get("label", code), "Source", 180),
            "date": require_text(item.get("date", ""), "Date", 50),
            "status": _choice(item.get("status", "REEL"), ("REEL", "FICTIF"), "Statut source")}


def new_idea(text, origin="ACCOMPAGNATEUR", *, identifier=None):
    text = require_text(text, "Idée", 300, required=True)
    ident = identifier or "PISTE-" + hashlib.sha256(f"{origin}|{text}".encode()).hexdigest()[:16]
    return {"id": require_text(ident, "Identifiant", 60, required=True), "wording": text,
            "origin": require_text(origin, "Origine", 80, required=True),
            "source_wording": text if origin in ("APS_OBJECTIF", "APS_P1") else "",
            "context_note": "", "context_prompt": DEFAULT_CONTEXT_PROMPT,
            "context_choices": list(DEFAULT_CONTEXT_CHOICES)}


def adapt_context_question(idea, observation):
    """Préparation déterministe : suggestion à valider, pas IA ni propos de la personne.

    La remarque est une hypothèse de l'accompagnateur et la question cherche à
    la confirmer/écarter; la source APS et les autres pistes restent intactes.
    """
    idea = copy.deepcopy(idea)
    observation = require_text(observation, "Observation de l'accompagnateur", 380, required=True)
    idea["context_note"] = observation
    idea["context_prompt"] = (
        "Un contexte possible a été évoqué par votre accompagnateur : « "
        + observation + " ». Cette hypothèse vous correspond-elle, ou envisagez-vous un autre contexte d'exercice ?"
    )
    return idea


def generate_questionnaire_v2(sources, context="AUTRE", intro=""):
    from clarte360_cp.domain.preparation import CONTEXTS, SOURCES, ENTERPRISE_CONTEXTS
    if context not in CONTEXTS or not isinstance(sources, dict) or set(sources) - set(SOURCES):
        raise ValueError("Contexte ou source non reconnu.")
    verified = {k: v for k, v in sources.items() if isinstance(v, dict) and v.get("authorized")}
    refs = [_source_ref(k, v) for k, v in verified.items()]
    ideas = []
    for code in ("APS_OBJECTIF", "APS_P1"):
        for wording in require_list(verified.get(code, {}).get("idea_list", []), "Idées APS", 100, 300):
            if wording.casefold() not in {i["wording"].casefold() for i in ideas}:
                ideas.append(new_idea(wording, code))
    for code in ("APS_OBJECTIF", "APS_P1"):
        for detail in verified.get(code, {}).get("idea_details", []):
            if not isinstance(detail, dict):
                raise ValueError("Détail de piste APS invalide.")
            wording = require_text(detail.get("wording", ""), "Piste APS", 300, True)
            if wording.casefold() in {i["wording"].casefold() for i in ideas}:
                item = next(i for i in ideas if i["wording"].casefold() == wording.casefold())
            else:
                item = new_idea(wording, code)
                ideas.append(item)
            item["source_wording"] = require_text(detail.get("source_quote", ""), "Extrait APS", 300, True)
            item["context_prompt"] = require_text(detail.get("context_prompt", ""), "Question de contexte", 700, True)
            item["context_note"] = require_text(detail.get("context_note", ""), "Observation de l'intervenant", 380)
    employer = verified.get("ENTREPRISE_PERSPECTIVE")
    if employer and context not in ENTERPRISE_CONTEXTS:
        raise ValueError("Perspective employeur non autorisée hors cadre contractuel.")
    val = verified.get("BOUSSOLE_VALEURS", {})
    motors = verified.get("MOTEURS_PRO", {})
    pref = verified.get("PREFERENCES_PRO", {})
    values = require_list(val.get("items", []), "Valeurs", 60)
    motors_list = require_list(motors.get("items", list(MOTOR_LABELS)) if motors else [], "Moteurs", 30)
    dims = pref.get("dimensions", [])
    if not dims and isinstance(pref.get("result_summary"), dict):
        dims = [{"code": row["key"], "label": row["label"], "pole_1": row.get("pole_1", ""),
                 "pole_2": row.get("pole_2", "")}
                for row in pref["result_summary"].get("rows", []) if row.get("pole_1") and row.get("pole_2")]
    if not isinstance(dims, list) or len(dims) > 10:
        raise ValueError("Dix dimensions Préférences maximum.")
    valid_dims = []
    for idx, item in enumerate(dims):
        if not isinstance(item, dict):
            raise ValueError("Dimension Préférences invalide.")
        valid_dims.append({"code": require_text(item.get("code", f"PP{idx+1}"), "Code dimension", 20, True),
                           "label": require_text(item.get("label", ""), "Dimension", 120, True),
                           "pole_1": require_text(item.get("pole_1", ""), "Premier pôle", 260, True),
                           "pole_2": require_text(item.get("pole_2", ""), "Second pôle", 260, True)})
    if len({v["code"] for v in valid_dims}) != len(valid_dims):
        raise ValueError("Dimensions Préférences dupliquées.")
    doc = {
        "schema": SCHEMA_Q_V2, "context": context,
        "intro": require_text(intro, "Introduction", 1400) or (
            "Au cours de votre parcours, certaines envies ou idées ont peut-être émergé. "
            "Ce questionnaire vous invite à préciser librement ce que vous souhaitez explorer. "
            "Vous pourrez modifier vos réponses jusqu'à leur validation définitive."
        ),
        "source_refs": refs,
        "ideas_active": ideas, "ideas_archived": [],
        "enterprise_wording": require_text(employer.get("wording", ""), "Perspective", 800, True) if employer else "",
        "cav2": {
            "valeurs": {"mode": "CHOIX" if values else "LIBRE", "question": VAL_QUESTION if values else VAL_FREE,
                        "choices": values, "max": 3, "note_prompt": "Quel signe concret vous montrerait que ces valeurs sont respectées ?"},
            "moteurs": {"mode": "CHOIX" if motors_list else "LIBRE", "question": MOT_QUESTION if motors_list else MOT_FREE,
                        "choices": motors_list, "max": 3, "note_prompt": "Qu'aimeriez-vous faire concrètement pour retrouver ces moteurs ?"},
            "preferences": {"mode": "DIMENSIONS" if valid_dims else "LIBRE",
                            "question": PREF_QUESTION if valid_dims else PREF_FREE, "dimensions": valid_dims,
                            "max": 3, "situation_question": PREF_SITUATION},
        },
        "report_refs": [{"code": code, "source_ref": verified[code].get("source_ref", ""),
                         "status": verified[code].get("status", "REEL"),
                         "label": "IPIP-NEO-120" if code == "IPIP_REPORT" else "PIP RIASEC"}
                        for code in ("IPIP_REPORT", "PIP_REPORT") if code in verified],
    }
    from clarte360_cp.domain.preparation_evidence import extract_evidence
    for code, source in (("BOUSSOLE_VALEURS", val), ("MOTEURS_PRO", motors)):
        summary = source.get("result_summary") if isinstance(source, dict) else None
        if isinstance(summary, dict):
            source["items"] = [row["label"] for row in summary.get("rows", []) if row.get("label")]
    doc["evidence"] = extract_evidence(verified, refs)
    return valid_questionnaire_v2(doc)


def _check_ideas(items, name):
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError(f"{name} : liste invalide.")
    out = []; ids = set()
    for item in items:
        _keys(item, ("id", "wording", "origin", "source_wording", "context_note", "context_prompt", "context_choices"), "Piste")
        ident = require_text(item["id"], "Identifiant piste", 60, True)
        if ident in ids: raise ValueError("Identifiant de piste dupliqué.")
        ids.add(ident)
        out.append({"id": ident, "wording": require_text(item["wording"], "Piste", 300, True),
                    "origin": require_text(item["origin"], "Origine piste", 80, True),
                    "source_wording": require_text(item["source_wording"], "Libellé source conservé", 300),
                    "context_note": require_text(item["context_note"], "Observation de l'accompagnateur", 380),
                    "context_prompt": require_text(item["context_prompt"], "Question de contexte", 700, True),
                    "context_choices": require_list(item["context_choices"], "Choix de contexte", 20)})
        if not out[-1]["context_choices"]: raise ValueError("La question de contexte doit proposer des réponses.")
        if out[-1]["origin"] in ("APS_OBJECTIF", "APS_P1") and not out[-1]["source_wording"]:
            raise ValueError("Libellé APS d’origine obligatoire et immuable.")
    return out


def valid_questionnaire_v2(q):
    from clarte360_cp.domain.preparation import CONTEXTS, SOURCES, ENTERPRISE_CONTEXTS
    original_keys = {"schema", "context", "intro", "source_refs", "ideas_active", "ideas_archived", "enterprise_wording", "cav2", "report_refs"}
    if set(q) not in (original_keys, original_keys | {"evidence"}):
        raise ValueError("Questionnaire : structure invalide.")
    if q["schema"] != SCHEMA_Q_V2 or q["context"] not in CONTEXTS: raise ValueError("Version ou contexte questionnaire invalide.")
    r = copy.deepcopy(q)
    r["intro"] = require_text(q["intro"], "Introduction", 1400, True)
    r["ideas_active"] = _check_ideas(q["ideas_active"], "Pistes actives")
    r["ideas_archived"] = _check_ideas(q["ideas_archived"], "Pistes exclues")
    if {x["id"] for x in r["ideas_active"]} & {x["id"] for x in r["ideas_archived"]}:
        raise ValueError("Une piste ne peut être active et exclue simultanément.")
    if not isinstance(q["source_refs"], list) or len(q["source_refs"]) > 8: raise ValueError("Liste des sources invalide.")
    seen_refs = set(); refs=[]
    for obj in q["source_refs"]:
        _keys(obj, ("code", "source_ref", "label", "date", "status"), "Source")
        if obj["code"] not in SOURCES or obj["code"] in seen_refs: raise ValueError("Source inconnue ou doublonnée.")
        seen_refs.add(obj["code"])
        refs.append(_source_ref(obj["code"], obj))
    r["source_refs"] = refs
    r["enterprise_wording"] = require_text(q["enterprise_wording"], "Perspective entreprise", 800)
    if r["enterprise_wording"] and q["context"] not in ENTERPRISE_CONTEXTS: raise ValueError("Perspective entreprise non autorisée.")
    _keys(q["cav2"], ("valeurs", "moteurs", "preferences"), "C-AV2")
    for name in ("valeurs", "moteurs"):
        section=q["cav2"][name]
        _keys(section, ("mode", "question", "choices", "max", "note_prompt"), name)
        if section["mode"] not in ("CHOIX", "LIBRE") or type(section["max"]) is not int or section["max"] != 3:
            raise ValueError("Plafond ou mode C-AV2 invalide.")
        choices=require_list(section["choices"], "Options C-AV2", 100)
        if section["mode"] == "CHOIX" and not choices: raise ValueError("Un choix fermé doit contenir des options.")
        if section["mode"] == "LIBRE" and choices: raise ValueError("Questions libres sans choix artificiels.")
        r["cav2"][name] = {**section, "choices": choices,
                           "question": require_text(section["question"], "Question", 650, True),
                           "note_prompt": require_text(section["note_prompt"], "Observation", 400, True)}
    p=q["cav2"]["preferences"]
    _keys(p, ("mode", "question", "dimensions", "max", "situation_question"), "Préférences")
    if p["mode"] not in ("DIMENSIONS", "LIBRE") or type(p["max"]) is not int or p["max"] != 3:
        raise ValueError("Préférences : modalité ou maximum invalide.")
    if not isinstance(p["dimensions"], list) or len(p["dimensions"]) > 10: raise ValueError("Dimensions invalides.")
    valid_dims=[]
    for dim in p["dimensions"]:
        _keys(dim, ("code", "label", "pole_1", "pole_2"), "Dimension")
        valid_dims.append({k: require_text(dim[k], k, 260, True) for k in ("code", "label", "pole_1", "pole_2")})
    if len({v["code"] for v in valid_dims}) != len(valid_dims): raise ValueError("Dimensions dupliquées.")
    if (p["mode"]=="DIMENSIONS") != bool(valid_dims): raise ValueError("Mode Préférences/sources incohérent.")
    r["cav2"]["preferences"] = {**p, "dimensions": valid_dims, "question": require_text(p["question"], "Question", 650, True),
                                   "situation_question": require_text(p["situation_question"], "Situation", 650, True)}
    if not isinstance(q["report_refs"], list) or len(q["report_refs"]) > 2: raise ValueError("Rapports invalides.")
    seen=set(); reports=[]
    for ref in q["report_refs"]:
        _keys(ref, ("code", "source_ref", "status", "label"), "Rapport")
        if ref["code"] not in ("IPIP_REPORT", "PIP_REPORT") or ref["code"] in seen: raise ValueError("Rapport doublonné.")
        seen.add(ref["code"])
        reports.append({"code": ref["code"], "source_ref": require_text(ref["source_ref"], "Référence rapport", 240, True),
                        "status": _choice(ref["status"], ("REEL", "FICTIF"), "Statut rapport"),
                        "label": require_text(ref["label"], "Libellé rapport", 100)})
    r["report_refs"] = reports
    if "evidence" in q:
        from clarte360_cp.domain.preparation_evidence import valid_evidence
        r["evidence"] = valid_evidence(q["evidence"], refs)
    return r


def public_questionnaire_v2(q):
    """Ne donne jamais les pistes écartées ni les identifiants internes des sources."""
    result = copy.deepcopy(valid_questionnaire_v2(q))
    result["ideas_archived"] = []
    result["source_refs"] = []
    result["report_refs"] = [{**r, "source_ref": "REFERENCE_ESPACE_DOCUMENTAIRE"} for r in result["report_refs"]]
    for p in result["ideas_active"]:
        p["context_note"] = ""  # observation interne, jamais déclaration de bénéficiaire
    return result


def empty_answers_v2(q):
    # La projection publique masque les identifiants de sources tout en gardant
    # des repères descriptifs déjà validés avant publication. La génération
    # d'un brouillon ne dépend pas de ces repères.
    cleaned_q = copy.deepcopy(q)
    if not cleaned_q.get("source_refs") and "evidence" in cleaned_q:
        cleaned_q.pop("evidence")
    q=valid_questionnaire_v2(cleaned_q)
    return {"schema": SCHEMA_R_V2, "cav1_done": False, "cav2_done": False,
            "cav1": {"no_idea": False, "ideas": [], "new_ideas": [],
                     "enterprise_position": "NE_SAIS_PAS" if q["enterprise_wording"] else "NON_CONCERNE", "enterprise_note": ""},
            "cav2": {"valeurs": {"choices": [], "free": [], "none_reason": "", "note": ""},
                     "moteurs": {"choices": [], "free": [], "none_reason": "", "note": ""},
                     "preferences": {"priorities": [], "free": "", "none_reason": "", "situation": "", "situation_note": ""}}}


def valid_answers_v2(a,q,final=False):
    from clarte360_cp.domain.preparation import ENTERPRISE_RESPONSES
    q=valid_questionnaire_v2(q)
    _keys(a, ("schema", "cav1_done", "cav2_done", "cav1", "cav2"), "Réponses")
    if a["schema"] != SCHEMA_R_V2: raise ValueError("Format de réponses incompatible.")
    _flag(a["cav1_done"]); _flag(a["cav2_done"])
    if a["cav2_done"] and not a["cav1_done"]: raise ValueError("C-AV1 doit être complété avant C-AV2.")
    _keys(a["cav1"], ("no_idea", "ideas", "new_ideas", "enterprise_position", "enterprise_note"), "C-AV1")
    _flag(a["cav1"]["no_idea"])
    active = {p["id"]:p for p in q["ideas_active"]}
    if not isinstance(a["cav1"]["ideas"], list) or len(a["cav1"]["ideas"])>len(active): raise ValueError("Réponses pistes invalides.")
    seen=set(); idea_list=[]
    for ans in a["cav1"]["ideas"]:
        _keys(ans, ("id", "interest", "meaning", "status", "attraction", "access", "context", "note"), "Réponse piste")
        ident=ans["id"]
        if ident not in active or ident in seen: raise ValueError("Piste exclue, inconnue ou dupliquée.")
        seen.add(ident)
        i={"id":ident, "interest":_choice(ans["interest"], INTEREST_CHOICES, "Intérêt"),
           "note":require_text(ans["note"], "Observation personnelle", 1600)}
        from clarte360_cp.domain.preparation import CAV1_MEANINGS,CAV1_STATUSES,CAV1_ATTRACTIONS,CAV1_ACCESS
        for name, opts in (("meaning", CAV1_MEANINGS), ("status", CAV1_STATUSES), ("attraction", CAV1_ATTRACTIONS), ("access", CAV1_ACCESS)):
            values=require_list(ans[name], name, 20)
            if set(values)-set(opts): raise ValueError("Réponse non prévue dans C-AV1.")
            i[name]=values
        _keys(ans["context"], ("choices", "other"), "Contexte d'exercice")
        choices=require_list(ans["context"]["choices"], "Contexte", 20)
        if set(choices)-set(active[ident]["context_choices"]): raise ValueError("Contexte non proposé par Q.")
        i["context"]={"choices":choices,"other":require_text(ans["context"]["other"], "Autres informations", 1600)}
        idea_list.append(i)
    if a["cav1"]["no_idea"] and (any(x["interest"] != "NON_ACTUELLEMENT" for x in idea_list) or a["cav1"]["new_ideas"]):
        raise ValueError("Aucune idée : les pistes évoquées doivent alors être écartées, sans nouvelle idée ajoutée.")
    if a["cav1_done"] and set(active)-seen:
        raise ValueError("Veuillez traiter chaque piste affichée dans C-AV1.")
    if not isinstance(a["cav1"]["new_ideas"], list) or len(a["cav1"]["new_ideas"]) > 100:
        raise ValueError("Idées nouvelles : liste invalide.")
    new_ideas=[]; used_new=set()
    for raw in a["cav1"]["new_ideas"]:
        _keys(raw, ("wording", "context"), "Idée nouvelle")
        name=require_text(raw["wording"], "Nouvelle idée", 300, True)
        if name.casefold() in used_new:raise ValueError("Idée nouvelle dupliquée.")
        used_new.add(name.casefold())
        _keys(raw["context"], ("choices", "other"), "Contexte idée nouvelle")
        choices=require_list(raw["context"]["choices"], "Contexte d'idée nouvelle", 20)
        if set(choices)-set(DEFAULT_CONTEXT_CHOICES):raise ValueError("Réponse de contexte non prévue.")
        new_ideas.append({"wording":name,"context":{"choices":choices,
                           "other":require_text(raw["context"]["other"], "Autres informations", 1600)}})
    if a["cav1_done"] and not new_ideas and not any(z["interest"] != "NON_ACTUELLEMENT" for z in idea_list) and not a["cav1"]["no_idea"]:
        raise ValueError("Veuillez indiquer une idée ou confirmer qu'aucune n'a émergé.")
    pos=a["cav1"]["enterprise_position"]
    if q["enterprise_wording"]:
        if pos not in ENTERPRISE_RESPONSES: raise ValueError("Position entreprise invalide.")
    elif pos != "NON_CONCERNE": raise ValueError("Bloc entreprise interdit.")
    _keys(a["cav2"], ("valeurs", "moteurs", "preferences"), "C-AV2")
    c2=copy.deepcopy(a["cav2"])
    for name in ("valeurs", "moteurs"):
        x=a["cav2"][name]; cfg=q["cav2"][name]
        _keys(x, ("choices", "free", "none_reason", "note"), name)
        selected=require_list(x["choices"], name, 3)
        free=require_list(x["free"], name, 3, 240)
        if cfg["mode"]=="CHOIX" and (free or set(selected)-set(cfg["choices"])):
            raise ValueError(f"{name} : réponses non proposées par le questionnaire.")
        if cfg["mode"]=="LIBRE" and selected: raise ValueError(f"{name} : sélection non autorisée.")
        if len(selected)+len(free)>3: raise ValueError(f"{name} : 3 choix maximum.")
        reason=x["none_reason"]
        if reason not in ("",*REASON_NONE): raise ValueError(f"{name} : motif inconnu.")
        if reason and (selected or free): raise ValueError(f"{name} : critère choisi et motif aucun incompatibles.")
        if a["cav2_done"] and not reason and not selected and not free:
            raise ValueError(f"{name} : un choix ou un motif explicite est nécessaire.")
        c2[name]={"choices":selected,"free":free,"none_reason":reason,"note":require_text(x["note"], "Observation", 1400)}
    pp=a["cav2"]["preferences"]; pc=q["cav2"]["preferences"]
    _keys(pp, ("priorities", "free", "none_reason", "situation", "situation_note"), "Préférences")
    if not isinstance(pp["priorities"], list) or len(pp["priorities"])>3: raise ValueError("Préférences : maximum trois dimensions.")
    dims={z["code"]:z for z in pc["dimensions"]}; used=set(); priorities=[]
    for raw in pp["priorities"]:
        _keys(raw, ("code", "pole", "other", "importance", "note"), "Priorité")
        code=raw["code"]
        if pc["mode"]!="DIMENSIONS" or code not in dims or code in used: raise ValueError("Dimension inconnue ou dupliquée.")
        used.add(code)
        pole=_choice(raw["pole"], CHOICE_POLE if a["cav2_done"] else ("",*CHOICE_POLE), "Pôle futur")
        other=require_text(raw["other"], "Autre façon de travailler", 500)
        if pole=="AUTRE" and not other and a["cav2_done"]: raise ValueError("Précisez votre modalité de travail souhaitée.")
        priorities.append({"code":code,"pole":pole,"other":other,
                           "importance":_choice(raw["importance"], CHOICE_IMPORTANCE if a["cav2_done"] else ("",*CHOICE_IMPORTANCE), "Importance"),
                           "note":require_text(raw["note"], "Observation", 1000)})
    free=require_text(pp["free"], "Conditions de travail", 1800)
    if pc["mode"]=="DIMENSIONS" and free: raise ValueError("Texte libre réservé à l'absence de continuum.")
    if pc["mode"]=="LIBRE" and priorities: raise ValueError("Pas de dimensions artificielles.")
    reason=pp["none_reason"]
    if reason not in ("",*REASON_NONE) or (reason and (priorities or free)):
        raise ValueError("Motif de non-priorité Préférences invalide.")
    if a["cav2_done"] and not (priorities or free or reason):
        raise ValueError("Préférences : choix ou absence de priorité à confirmer.")
    sit=_choice(pp["situation"], ("",*SITUATION_CHOICES) if not a["cav2_done"] else SITUATION_CHOICES, "Situation difficile à accepter")
    sn=require_text(pp["situation_note"], "Condition concrète à éviter", 1200)
    if sit=="OUI" and not sn and a["cav2_done"]: raise ValueError("Décrivez la situation concrète que vous souhaitez éviter.")
    c2["preferences"]={"priorities":priorities,"free":free,"none_reason":reason,"situation":sit,"situation_note":sn}
    if final and not (a["cav1_done"] and a["cav2_done"]):
        raise ValueError("Complétez C-AV1 puis C-AV2 avant la transmission définitive unique.")
    out=copy.deepcopy(a)
    out["cav1"]["ideas"]=idea_list
    out["cav1"]["new_ideas"]=new_ideas
    out["cav1"]["enterprise_note"]=require_text(a["cav1"]["enterprise_note"], "Note entreprise", 1600)
    out["cav2"]=c2
    return out
