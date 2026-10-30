"""GO22 RC3B - passation lisible, dynamique et sourcée, sans IA bénéficiaire.

Pas de st.form sur les questions conditionnelles : les champs apparaissent dès
que la personne clique, sans devoir sauvegarder/revenir en arrière.
"""
from __future__ import annotations

import copy
import html

from clarte360_cp.domain.preparation import (
    CAV1_MEANINGS, CAV1_STATUSES, CAV1_ATTRACTIONS, CAV1_ACCESS,
)
from clarte360_cp.domain.preparation_v2 import (
    INTEREST_CHOICES, DEFAULT_CONTEXT_CHOICES, CHOICE_POLE,
    CHOICE_IMPORTANCE, SITUATION_CHOICES,
)

_STATUS = {
    "EXPLORER":"Oui, je souhaite explorer cette piste",
    "ACTIVITES_LIEES":"Je souhaite surtout explorer certaines activités associées",
    "NON_ACTUELLEMENT":"Cette piste ne m'intéresse plus pour le moment",
    "INDECISE":"Je ne sais pas encore",
}
_INTERESTS = tuple(_STATUS)
_IMPORTANCE = {
    "INDISPENSABLE":"Indispensable pour moi",
    "IMPORTANT_ADAPTABLE":"Important, mais adaptable",
}
_SITUATIONS = {"OUI":"Oui, une situation précise", "NON":"Non", "PAS_IDENTIFIEE":"Je n'en ai pas identifié"}
CAV1_MORE_INFORMATION_LABEL = "Autres informations sur cette piste ou son contexte"
CAV1_MEANING_INSTRUCTION = (
    "Plusieurs réponses possibles. Si vous choisissez Je souhaite préciser, "
    "utilisez la zone Autres informations sur cette piste ou son contexte, "
    "située en bas de cette fiche."
)
_RIASEC_DESC = {
    "R":"Réaliste — activités concrètes, techniques et pratiques",
    "I":"Investigateur — observer, analyser et comprendre",
    "A":"Artistique — imaginer, concevoir et créer",
    "S":"Social — accompagner, transmettre et conseiller",
    "E":"Entreprenant — initier, convaincre et développer",
    "C":"Conventionnel — structurer, organiser et fiabiliser",
}


def apply_ui_style():
    import streamlit as st
    st.markdown("""<style>
        [data-testid='stVerticalBlockBorderWrapper'] { border-radius:16px; }
        [data-testid='stWidgetLabel'] p { font-weight:600; color:#173f44; font-size:1.02rem; }
        [data-testid='stTextArea'] textarea, [data-testid='stTextInput'] input {
            background:#fff; border:1.5px solid #7eaaa9; border-radius:10px; min-height:43px;
        }
        div[data-baseweb='radio'] label { padding:.25rem .2rem; }
        div[data-testid='stCheckbox'] label {padding-top:.22rem;padding-bottom:.22rem;}
        .cl360-mini { background:#e9f5f4; border-left:4px solid #008b8a;
             padding:14px 18px; border-radius:10px; margin:9px 0 18px; line-height:1.55; }
        .cl360-num { color:#067b7a; font-weight:700; font-size:.78rem; letter-spacing:.05em; }
        .cl360-badge {display:inline-block;padding:.20rem .65rem;background:#fff1d6;color:#815014;
             font-size:.82rem;font-weight:700;border-radius:999px;margin-left:.3rem;}
        .cl360-evidence {background:#f2f8f7;border-radius:12px;padding:1rem 1.2rem;}
        </style>""",unsafe_allow_html=True)


def hint(title,text):
    import streamlit as st
    with st.popover("ⓘ "+title):
        st.write(text)


def _lines(text):
    return list(dict.fromkeys(v.strip() for v in text.splitlines() if v.strip()))


def _multi(label,options,original,key,description="Vous pouvez sélectionner plusieurs réponses.",*,disabled=False):
    import streamlit as st
    st.markdown("**"+label+"**")
    st.caption(description)
    if hasattr(st,"pills"):
        result=st.pills("Choix possibles",list(options),selection_mode="multi",
            default=list(original),key=key,label_visibility="collapsed",disabled=disabled)
        return list(result or [])
    return [opt for idx,opt in enumerate(options)
            if st.checkbox(opt,value=opt in original,key=f"{key}_{idx}",disabled=disabled)]


def _none_or_options(options,old,prefix,code,*,limit=3):
    """Cases plafonnées : aucune action selection globale et zéro présélection par score."""
    import streamlit as st
    reason=old.get("none_reason","")
    reason_key=f"{prefix}_{code}_no_priority_reason"
    reason_options=("CHOISIR","AUCUN_CRITERE_IDENTIFIE","A_AFFINER")
    reason_choice=st.radio(
        "Si vous ne retenez aucun choix, quelle réponse vous correspond ?",
        reason_options,
        index=reason_options.index(reason) if reason in reason_options else 0,
        format_func=lambda value: {
            "CHOISIR":"Je souhaite retenir une ou plusieurs réponses",
            "AUCUN_CRITERE_IDENTIFIE":"Je n'ai identifié aucune priorité à retenir pour le moment",
            "A_AFFINER":"J'ai réfléchi, mais je ne peux pas encore hiérarchiser",
        }[value],
        key=reason_key,
    )
    none_checked=reason_choice!="CHOISIR"
    selected_keys=[f"{prefix}_{code}_pick_{i}" for i in range(len(options))]
    if none_checked:
        for key in selected_keys:
            st.session_state[key]=False
        before=[]
    else:
        before=[v for i,v in enumerate(options) if st.session_state.get(selected_keys[i],v in old.get("choices",[]))]
    if len(before)>limit:
        # Défense contre un état de widgets ancien/importé incohérent.
        for i,v in enumerate(options):
            if v in before[limit:]:st.session_state[selected_keys[i]]=False
        before=before[:limit]
        st.warning("Le maximum est de trois priorités : les choix excédentaires ont été retirés.")
    picked=[]
    st.caption(f"Au maximum {limit} choix • actuellement {len(before)}/{limit}. Aucune réponse n'est précochée à partir du rapport.")
    cols=st.columns(2)
    for i,choice in enumerate(options):
        with cols[i%2]:
            active=choice in before
            checked=st.checkbox(choice,value=choice in old.get("choices",[]),key=selected_keys[i],
               disabled=(none_checked or (len(before)>=limit and not active)))
            if checked and not none_checked:
                picked.append(choice)
    if len(picked)>=limit:
        st.caption(f"{limit} priorités sont sélectionnées. Vous pouvez en retirer une pour en choisir une autre.")
    if picked:
        reason_choice="CHOISIR"
    return picked,reason_choice if reason_choice!="CHOISIR" and not picked else ""


def _no_priority_reason(old_reason,prefix,key_suffix,*,label):
    """Expose both valid non-priority states without implying that they are identical."""
    import streamlit as st
    options=("CHOISIR","AUCUN_CRITERE_IDENTIFIE","A_AFFINER")
    key=f"{prefix}_{key_suffix}"
    chosen=st.radio(
        label,
        options,
        index=options.index(old_reason) if old_reason in options else 0,
        format_func=lambda value: {
            "CHOISIR":"Je souhaite formuler ou sélectionner une préférence",
            "AUCUN_CRITERE_IDENTIFIE":"Je n'ai identifié aucune priorité à retenir pour le moment",
            "A_AFFINER":"J'ai réfléchi, mais je ne peux pas encore hiérarchiser",
        }[value],
        key=key,
    )
    return chosen


def _evidence_box(q,code,*,title,expected_choices=None):
    import streamlit as st
    evidence=q.get("evidence",{}).get(code)
    name={"valeurs":"BOUSSOLE_VALEURS","moteurs":"MOTEURS_PRO", "preferences":"PREFERENCES_PRO",
          "ipip":"IPIP_REPORT","pip":"PIP_REPORT"}[code]
    refs={x["code"]:x for x in q.get("source_refs",[])}
    docs={x["code"]:x for x in q.get("report_refs",[])}
    src=refs.get(name,docs.get(name))
    if not evidence or not evidence.get("rows"):
        with st.expander(title,expanded=False):
            if src:
                st.info("Le rapport est référencé, mais ses résultats détaillés ne sont pas encore raccordés à ce questionnaire. Aucun chiffre n'est inventé.")
            else:
                st.caption("Aucun résultat transmis pour cet outil dans ce dossier : vous pouvez poursuivre sans le test.")
        return
    is_fake=evidence.get("status")=="FICTIF"
    with st.expander(title+(" · DONNÉES FICTIVES" if is_fake else ""),expanded=True):
        st.caption(evidence["scale"])
        if evidence["note"]: st.caption(evidence["note"])
        data=[]
        for row in evidence["rows"]:
            record={"Repère du rapport":row["label"],"Signification":row["explanation"],"Résultat source":row["score_display"] or "Non fourni"}
            if expected_choices and row["key"] not in expected_choices and row["label"] not in expected_choices:
                continue
            data.append(record)
        if data: st.dataframe(data,use_container_width=True,hide_index=True)
        if is_fake:st.caption("Résultats inventés pour cette recette technique. Ils ne concernent aucune personne réelle.")


def _choice_pole(choice,dim):
    return {
        "POLE_1":"Je souhaite plutôt : "+dim["pole_1"],
        "EQUILIBRE":"Je souhaite un équilibre entre ces deux modes",
        "POLE_2":"Je souhaite plutôt : "+dim["pole_2"],
        "AUTRE":"Ma préférence est différente : je vais préciser",
    }[choice]


def render_av1(q,a,prefix):
    """Construit le brouillon visible, sans attendre un submit pour les champs liés."""
    import streamlit as st
    data=copy.deepcopy(a);cav=data["cav1"]
    st.markdown("### Étape 1/2 — Mes idées et pistes professionnelles")
    st.markdown('<div class="cl360-mini">Pour chaque idée, indiquez ce qui vous intéresse aujourd’hui. '
        'Vous pouvez garder, nuancer ou écarter une piste, puis en ajouter d’autres. '
        '<strong>Plusieurs réponses sont possibles</strong> dans les questions qui le précisent.</div>',unsafe_allow_html=True)
    old_answers={x["id"]:x for x in cav["ideas"]}
    current=[]
    total=len(q["ideas_active"])
    if total==0:st.info("Aucune piste n'a encore été proposée. Vous pouvez ajouter une idée, un secteur, une activité ou simplement indiquer que vous n'avez pas encore de piste.")
    for ix,idea in enumerate(q["ideas_active"],1):
        old=old_answers.get(idea["id"],{})
        with st.container(border=True):
            st.markdown(f'<div class="cl360-num">PISTE {ix} SUR {total} · À EXAMINER</div>',unsafe_allow_html=True)
            st.markdown("#### "+idea["wording"])
            st.caption("Vous êtes libre de ne plus retenir cette idée, même si elle a été évoquée auparavant.")
            prev=old.get("interest")
            interest=st.radio("1. Souhaitez-vous encore explorer cette piste ?",list(_INTERESTS),
                index=list(_INTERESTS).index(prev) if prev in _INTERESTS else None,
                format_func=lambda x:_STATUS[x],key=f"{prefix}_interest_{idea['id']}")
            if interest is None:
                st.caption("Choisissez d'abord votre réponse à la question 1 pour pouvoir préciser cette piste. Vous pouvez déjà lire toutes les questions ci-dessous.")
            if interest=="NON_ACTUELLEMENT":
                st.caption("Cette piste ne sera pas retenue pour votre exploration actuelle ; elle restera simplement dans l'historique de votre parcours.")
            else:
                st.divider()
                selections={}
                entries=(
                    ("meaning","2. Que représente cette idée pour vous ?",CAV1_MEANINGS),
                    ("status","3. Dans quel cadre pourriez-vous envisager cette activité ?",CAV1_STATUSES),
                    ("attraction","4. Qu'est-ce qui vous attire dans cette piste ?",CAV1_ATTRACTIONS),
                    ("access","5. Qu'avez-vous déjà vérifié à son sujet ?",CAV1_ACCESS),
                )
                for key,label,opts in entries:
                    description=(CAV1_MEANING_INSTRUCTION if key=="meaning"
                                 else "Vous pouvez sélectionner plusieurs réponses.")
                    selections[key]=_multi(label,opts,old.get(key,[]),f"{prefix}_{key}_{idea['id']}",
                                           description=description,disabled=interest is None)
                st.markdown("**6. Y a-t-il un contexte particulier d'exercice ?**")
                st.write(idea["context_prompt"])
                choices=_multi("Cadre ou contexte envisagé",idea["context_choices"],old.get("context",{}).get("choices",[]),f"{prefix}_context_{idea['id']}",disabled=interest is None)
                other=st.text_area(CAV1_MORE_INFORMATION_LABEL+" (facultatif)",
                    value=old.get("context",{}).get("other",""),key=f"{prefix}_other_{idea['id']}",height=90,disabled=interest is None)
                note=st.text_area("Une autre précision à apporter ? (facultatif)",
                    value=old.get("note",""),key=f"{prefix}_note_{idea['id']}",height=80,disabled=interest is None)
            if interest:
                current.append({"id":idea["id"],"interest":interest,
                    "meaning":selections["meaning"] if interest!="NON_ACTUELLEMENT" else [],
                    "status":selections["status"] if interest!="NON_ACTUELLEMENT" else [],
                    "attraction":selections["attraction"] if interest!="NON_ACTUELLEMENT" else [],
                    "access":selections["access"] if interest!="NON_ACTUELLEMENT" else [],
                    "context":{"choices":choices if interest!="NON_ACTUELLEMENT" else [],
                               "other":other if interest!="NON_ACTUELLEMENT" else ""},
                    "note":note if interest!="NON_ACTUELLEMENT" else ""})
    cav["ideas"]=current
    st.markdown("### Ajouter une autre idée")
    st.caption("Un métier, une activité, un secteur ou une envie, même encore imprécise, peuvent être ajoutés. Une idée par ligne.")
    prev_news={x["wording"].casefold():x for x in cav["new_ideas"]}
    raw=st.text_area("Mes autres idées (facultatif)",value="\n".join(x["wording"] for x in cav["new_ideas"]),
                     key=f"{prefix}_new",height=90)
    new_items=[]
    for i,wording in enumerate(_lines(raw)):
        old=prev_news.get(wording.casefold(),{"context":{"choices":[],"other":""}})
        with st.container(border=True):
            st.markdown("**Nouvelle piste : "+wording+"**")
            st.caption("Vous pouvez préciser maintenant son contexte. Aucune sauvegarde intermédiaire n'est nécessaire.")
            ctx_sel=_multi("Dans quel contexte envisageriez-vous cette idée ?",DEFAULT_CONTEXT_CHOICES,
                old.get("context",{}).get("choices",[]),f"{prefix}_newcontext_{i}")
            ctx_other=st.text_area("Autres informations sur ce contexte (facultatif)",value=old.get("context",{}).get("other",""),
                key=f"{prefix}_newcontext_note_{i}",height=80)
            new_items.append({"wording":wording,"context":{"choices":ctx_sel,"other":ctx_other}})
    cav["new_ideas"]=new_items
    none_offered=(total==0 or bool(current) and len(current)==total and all(x["interest"]=="NON_ACTUELLEMENT" for x in current))
    if none_offered and not new_items:
        st.markdown("### Et si aucune idée ne vous correspond aujourd'hui ?")
        st.caption("Vous pouvez confirmer qu'aucune piste n'est retenue actuellement. Vous pourrez continuer C-AV2 et explorer votre parcours ensuite.")
        cav["no_idea"]=st.checkbox("Je confirme ne pas avoir de piste professionnelle à explorer aujourd'hui",
            value=cav["no_idea"],key=f"{prefix}_no_idea")
    else:
        cav["no_idea"]=False
    if q["enterprise_wording"]:
        from clarte360_cp.domain.preparation import ENTERPRISE_RESPONSES
        st.markdown("### Perspective évoquée par mon entreprise — distincte de mes idées")
        st.info("Cette piste est une proposition du contexte d'accompagnement ; elle ne m'engage pas.")
        st.write(q["enterprise_wording"])
        labels={"NE_SOUHAITE_PAS":"Je ne souhaite pas l'explorer","SOUHAITE_EXPLORER":"Je souhaite l'explorer",
                "SOUHAITE_CLARIFIER":"Je souhaite en clarifier le sens", "NE_SAIS_PAS":"Je ne sais pas encore"}
        cav["enterprise_position"]=st.radio("Ma position personnelle",list(ENTERPRISE_RESPONSES),
            index=list(ENTERPRISE_RESPONSES).index(cav["enterprise_position"]),format_func=lambda x:labels[x],
            key=f"{prefix}_enterprise")
        cav["enterprise_note"]=st.text_area("Ma remarque (facultatif)",value=cav["enterprise_note"],key=f"{prefix}_enterprise_note")
    st.caption(f"Pistes examinées : {len(current)}/{total}. Les réponses peuvent être modifiées jusqu'à la transmission finale.")
    data["cav1"]=cav
    return data


def _priorities(q, data, code, prefix):
    import streamlit as st
    config=q["cav2"][code]; x=data[code]
    title="1. Mes valeurs essentielles" if code=="valeurs" else "2. Mes moteurs essentiels"
    desc=("Ce qui compte profondément pour moi. La cotation Boussole exprime l'incarnation d'une valeur, pas sa priorité future."
        if code=="valeurs" else "Ce qui me donne envie de m'investir. Un pourcentage ne détermine pas ce que je dois choisir aujourd'hui.")
    with st.container(border=True):
        st.markdown("#### "+title)
        st.caption(desc)
        _evidence_box(q,code,title="Lire mes résultats précédents et leur signification")
        st.markdown("**À moi de choisir pour mon avenir**")
        st.write(config["question"])
        if config["mode"]=="CHOIX":
            x["choices"],x["none_reason"]=_none_or_options(config["choices"],x,prefix,code)
            x["free"]=[]
        else:
            x["free"]=_lines(st.text_area("Je formule jusqu'à trois réponses, une par ligne",
                  value="\n".join(x["free"]),key=f"{prefix}_free_{code}",height=110,
                  disabled=st.session_state.get(f"{prefix}_{code}_free_reason",x["none_reason"]) in ("AUCUN_CRITERE_IDENTIFIE","A_AFFINER")))
            if x["free"]:
                x["none_reason"]=""
                st.session_state[f"{prefix}_{code}_free_reason"]="CHOISIR"
            else:
                chosen=_no_priority_reason(x["none_reason"],prefix,f"{code}_free_reason",
                    label="Si vous n'écrivez aucune priorité, quelle réponse vous correspond ?")
                x["none_reason"]=chosen if chosen!="CHOISIR" else ""
            x["choices"]=[]
        x["note"]=st.text_area(config["note_prompt"]+" (facultatif)",value=x["note"],key=f"{prefix}_note_{code}",height=90)
    data[code]=x


def render_av2(q,a,prefix):
    import streamlit as st
    data=copy.deepcopy(a);cav=data["cav2"]
    st.markdown("### Étape 2/2 — Mes repères professionnels")
    st.markdown('<div class="cl360-mini"><strong>Vos résultats précédents vous éclairent, mais ne décident pas à votre place.</strong> '
        'Prenez connaissance des explications et retenez ce qui importe pour votre avenir. '
        'Aucune IA n’analyse vos réponses pendant ce questionnaire.</div>',unsafe_allow_html=True)
    if q.get("evidence") and any(e.get("status")=="FICTIF" for e in q["evidence"].values()):
        st.warning("RECETTE : les chiffres et profils ci-dessous sont entièrement fictifs. Ils ne correspondent à aucun bénéficiaire.")
    for code in ("valeurs","moteurs"):
        _priorities(q,cav,code,prefix)
    pc=q["cav2"]["preferences"]
    pref=cav["preferences"]
    with st.container(border=True):
        st.markdown("#### 3. Mes préférences de fonctionnement")
        st.caption("Un résultat de Préférences indique une position sur un continuum, pas une aptitude ni une obligation pour le futur.")
        _evidence_box(q,"preferences",title="Lire les dix dimensions, leurs pôles et mes résultats précédents")
        st.write(pc["question"])
        if pc["mode"]=="DIMENSIONS":
            old_p={z["code"]:z for z in pref["priorities"]}
            labels=[(d["code"],d["label"]) for d in pc["dimensions"]]
            current=[k for k,v in labels if st.session_state.get(f"{prefix}_pref_pick_{k}",k in old_p)]
            if len(current)>3:
                for code in current[3:]:st.session_state[f"{prefix}_pref_pick_{code}"]=False
                current=current[:3]
                st.warning("Trois préférences prioritaires maximum : les choix excédentaires ont été retirés.")
            st.caption(f"Sélectionnez jusqu'à 3 dimensions importantes pour votre avenir : {len(current)}/3")
            no_key=f"{prefix}_pref_no_priority_reason"
            reason_options=("CHOISIR","AUCUN_CRITERE_IDENTIFIE","A_AFFINER")
            reason=st.radio("Si vous ne retenez aucune dimension, quelle réponse vous correspond ?",
                reason_options,index=reason_options.index(pref["none_reason"]) if pref["none_reason"] in reason_options else 0,
                format_func=lambda value:{"CHOISIR":"Je souhaite sélectionner une ou plusieurs dimensions",
                    "AUCUN_CRITERE_IDENTIFIE":"Je n'ai identifié aucune priorité à retenir pour le moment",
                    "A_AFFINER":"J'ai réfléchi, mais je ne peux pas encore hiérarchiser"}[value],key=no_key)
            disabled_all=reason!="CHOISIR"
            if disabled_all:
                for code,_label in labels:st.session_state[f"{prefix}_pref_pick_{code}"]=False
                current=[]
            sel=[]
            cols=st.columns(2)
            for i,(code,label) in enumerate(labels):
                with cols[i%2]:
                    flag=st.checkbox(label,value=code in old_p,key=f"{prefix}_pref_pick_{code}",
                        disabled=(disabled_all or (len(current)>=3 and code not in current)))
                    if flag and not disabled_all:sel.append(code)
            if sel:
                pref["none_reason"]=""
                st.markdown("**Précisez ce que vous souhaitez réellement pour chaque dimension retenue :**")
            priorities=[]
            for code in sel:
                dim=next(d for d in pc["dimensions"] if d["code"]==code)
                old=old_p.get(code,{})
                with st.container(border=True):
                    st.markdown("**"+dim["label"]+"**")
                    st.caption("Deux façons possibles : "+dim["pole_1"]+" ↔ "+dim["pole_2"])
                    pole=st.radio("Mon fonctionnement souhaité",list(CHOICE_POLE),
                        index=list(CHOICE_POLE).index(old["pole"]) if old.get("pole") in CHOICE_POLE else None,
                        format_func=lambda v,_d=dim:_choice_pole(v,_d),key=f"{prefix}_pole_{code}") or ""
                    imp=st.radio("L'importance pour mon avenir",list(CHOICE_IMPORTANCE),
                        index=list(CHOICE_IMPORTANCE).index(old["importance"]) if old.get("importance") in CHOICE_IMPORTANCE else None,
                        format_func=lambda v:_IMPORTANCE[v],key=f"{prefix}_imp_{code}") or ""
                    other=st.text_input("La façon de travailler que je souhaite (précisez)",value=old.get("other",""),
                        key=f"{prefix}_pother_{code}") if pole=="AUTRE" else ""
                    note=st.text_area("Un exemple ou une nuance (facultatif)",value=old.get("note",""),
                        key=f"{prefix}_pnote_{code}",height=80)
                    priorities.append({"code":code,"pole":pole,"importance":imp,"other":other,"note":note})
            pref["priorities"]=priorities
            pref["free"]=""
            pref["none_reason"]="" if priorities else (reason if reason!="CHOISIR" else "")
        else:
            pref["free"]=st.text_area("Les conditions de travail qui me conviennent (réponse libre)",
                value=pref["free"],key=f"{prefix}_pref_free",height=100,
                disabled=st.session_state.get(f"{prefix}_pref_free_reason",pref["none_reason"]) in ("AUCUN_CRITERE_IDENTIFIE","A_AFFINER"))
            if pref["free"]:
                pref["none_reason"]=""
                st.session_state[f"{prefix}_pref_free_reason"]="CHOISIR"
            else:
                chosen=_no_priority_reason(pref["none_reason"],prefix,"pref_free_reason",
                    label="Si vous n'écrivez aucune préférence, quelle réponse vous correspond ?")
                pref["none_reason"]=chosen if chosen!="CHOISIR" else ""
            pref["priorities"]=[]
        st.divider()
        st.markdown("**Une condition que je souhaite vraiment éviter**")
        st.write(pc["situation_question"])
        cur=pref["situation"]
        situation=st.radio("Ma réponse",list(SITUATION_CHOICES),
              index=list(SITUATION_CHOICES).index(cur) if cur in SITUATION_CHOICES else None,
              format_func=lambda x:_SITUATIONS[x],key=f"{prefix}_situation") or ""
        pref["situation"]=situation
        if situation=="OUI":
            pref["situation_note"]=st.text_area("Décrivez la situation à éviter (obligatoire si vous répondez Oui)",
                value=pref["situation_note"],key=f"{prefix}_situation_note",height=100,
                placeholder="Par exemple, des déplacements fréquents non compatibles avec mes contraintes.")
        else:
            pref["situation_note"]=""
    cav["preferences"]=pref
    st.markdown("### Mes deux autres rapports : pour comprendre, sans refaire les tests")
    st.caption("Ces éclairages compléteront l'analyse croisée préparée par votre accompagnateur. Ils ne déterminent jamais à eux seuls votre métier.")
    with st.container(border=True):
        st.markdown("#### 4. Mon fonctionnement professionnel — IPIP-NEO-120")
        st.caption("Cinq dimensions décrivent des tendances de fonctionnement. Aucune n'est une qualité ou un défaut en soi.")
        _evidence_box(q,"ipip",title="Voir les cinq dimensions, leurs significations et mes résultats")
        hint("À quoi sert ce résultat ?","Il aide à formuler des hypothèses sur des façons de travailler et des contextes possibles, à confronter à votre expérience. Ni diagnostic, ni preuve d'aptitude.")
    with st.container(border=True):
        st.markdown("#### 5. Mes centres d'intérêt — PIP RIASEC")
        st.caption("Le modèle RIASEC décrit six familles d'activités susceptibles de vous intéresser. Il ne mesure pas votre capacité à les exercer.")
        ev=q.get("evidence",{}).get("pip",{})
        if ev.get("profile_code"):
            code=ev["profile_code"]
            st.markdown("**Code d'intérêts indiqué dans le rapport : `"+html.escape(code)+"`**")
            st.caption("Il comporte "+str(len(code))+" lettres dans ce rapport ; nous n'ajoutons jamais de lettres qui n'y figurent pas.")
            if len(code)>=2:
                st.markdown("**Mes deux premières familles d'intérêt, expliquées :**")
                st.write("**1. "+code[0]+" :** "+_RIASEC_DESC[code[0]])
                st.write("**2. "+code[1]+" :** "+_RIASEC_DESC[code[1]])
        _evidence_box(q,"pip",title="Voir toutes les familles RIASEC et les indices du rapport")
        st.markdown("**Qu'est-ce que le ROME ?**")
        st.write("Le Répertoire opérationnel des métiers et des emplois, utilisé par France Travail, décrit des métiers, leurs activités et leurs compétences. Nous pourrons y rechercher ensemble des pistes plus tard, en nous appuyant sur vos intérêts **et** sur votre expérience, sans calcul automatique de métier idéal.")
        hint("Lire RIASEC avec prudence","Ces indices sont des intérêts déclarés. Ils ne prouvent ni compétence, ni qualification, ni possibilité réglementaire d'accès à un métier.")
    st.caption("Les rapports d'origine restent dans l'espace documentaire du parcours, lorsqu'ils y ont été publiés. Le lien direct au document Hub n'est pas encore raccordé dans cette candidate de recette.")
    data["cav2"]=cav
    return data
