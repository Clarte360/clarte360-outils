from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path

import streamlit as st

from xlsm_safe import inspect_workbook, action_row
from session_export import (
    CLEAR_TOKEN,
    build_import_xlsx,
    build_session_json,
    build_session_zip,
    next_available_action,
    read_financements_for_action,
    workbook_headers,
)
from contracts import build_bc_particulier_pdf, MODEL_VERSION

APP_VERSION = '1.2.0-VPS-IMPORT-MACRO'
APP_NAME = 'Clarté360 – Contractualisation'
BASE = Path(__file__).resolve().parent
LOGO = BASE / 'assets' / 'site_icon.png'
TEAL = '#008080'
LIGHT = '#E6F4F4'
DARK = '#243A3A'

st.set_page_config(page_title=APP_NAME, page_icon='📄', layout='wide')
st.markdown(
    f"""<style>
.stApp {{color:{DARK};}}
.clarte-box{{background:{LIGHT};border-left:6px solid {TEAL};padding:16px 18px;border-radius:10px;margin:8px 0 16px 0;}}
.clarte-warning{{background:#fff7d6;border-left:6px solid #d6a600;padding:14px 16px;border-radius:10px;}}
.small{{font-size:.85rem;color:#667777}}
</style>""",
    unsafe_allow_html=True,
)


def get_secret(section, key, default=''):
    try:
        return st.secrets.get(section, {}).get(key, default)
    except Exception:
        return default


def gate():
    expected = str(get_secret('security', 'admin_password', '')).strip()
    if st.session_state.get('auth'):
        return
    if LOGO.exists():
        st.image(str(LOGO), width=90)
    st.title(APP_NAME)
    st.markdown(
        '<div class="clarte-box"><b>Application administrative Clarté360.</b><br>'
        'La base Excel chargée sert uniquement de référence en lecture : recherche des actions existantes et attribution du prochain NO_CLAR libre. '
        'L’application ne réécrit jamais le fichier .xlsm. Les créations de la session sont exportées dans un fichier d’import destiné à une macro Excel locale.</div>',
        unsafe_allow_html=True,
    )
    if not expected:
        st.error("Le mot de passe administrateur n'est pas configuré dans [security].admin_password.")
        st.stop()
    pwd = st.text_input('Mot de passe administrateur', type='password')
    if st.button('Ouvrir l’application', type='primary'):
        if pwd == expected:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error('Mot de passe incorrect.')
    st.stop()


def parse_aps(file):
    d = json.load(file)
    if d.get('meta', {}).get('document_type') != 'APS':
        raise ValueError('Le JSON fourni ne semble pas être une APS Clarté360.')
    return d


def calc_finance_rows(no_clar, rows):
    out = []
    for i, r in enumerate(rows, start=1):
        amt = float(r.get('MONTANT_TTC') or 0)
        rate = float(r.get('TAUX_TVA') or 20)
        ht = amt / (1 + rate / 100) if rate != -100 else amt
        out.append({
            'ID_FINANCEMENT': f'FIN-{no_clar}-{i:02d}',
            'NO_CLAR': no_clar,
            'ORDRE': i,
            'ORDRE_FINANCEMENT': i,
            'TYPE_FINANCEUR': r.get('TYPE_FINANCEUR', ''),
            'NOM_FINANCEUR': r.get('NOM_FINANCEUR', ''),
            'SIRET_FINANCEUR': r.get('SIRET_FINANCEUR', ''),
            'ADRESSE_FINANCEUR': r.get('ADRESSE_FINANCEUR', ''),
            'CODE_POST_FINANCEUR': r.get('CODE_POST_FINANCEUR') or r.get('CP_FINANCEUR', ''),
            'CP_FINANCEUR': r.get('CP_FINANCEUR') or r.get('CODE_POST_FINANCEUR', ''),
            'VILLE_FINANCEUR': r.get('VILLE_FINANCEUR', ''),
            'CONTACT_FINANCEUR': r.get('CONTACT_FINANCEUR', ''),
            'EMAIL_FACTURATION': r.get('EMAIL_FACTURATION') or r.get('EMAIL_FINANCEUR', ''),
            'EMAIL_FINANCEUR': r.get('EMAIL_FINANCEUR') or r.get('EMAIL_FACTURATION', ''),
            'MONTANT_HT': round(ht, 2),
            'TAUX_TVA': rate,
            'MONTANT_TVA': round(amt - ht, 2),
            'MONTANT_TTC': round(amt, 2),
            'FACTURE_A_ETABLIR_A': r.get('FACTURE_A_ETABLIR_A', ''),
            'REFERENCE_PRISE_EN_CHARGE': r.get('REFERENCE_PRISE_EN_CHARGE', ''),
            'STATUT_FINANCEMENT': r.get('STATUT_FINANCEMENT', 'Prévu'),
            'DATE_ACCORD': r.get('DATE_ACCORD', ''),
            'OBSERVATIONS': r.get('OBSERVATIONS', ''),
        })
    return out


def to_date(s, fallback=None):
    if isinstance(s, (date, datetime)):
        return s.date() if isinstance(s, datetime) else s
    try:
        return datetime.fromisoformat(str(s)[:10]).date()
    except Exception:
        return fallback


def euro(value):
    return f"{float(value):,.2f} €".replace(',', ' ').replace('.', ',')


def page_header():
    c1, c2 = st.columns([1, 8])
    with c1:
        if LOGO.exists():
            st.image(str(LOGO), width=78)
    with c2:
        st.title(APP_NAME)
        st.caption(f'Version {APP_VERSION} – application VPS – base Excel locale en lecture seule – moteur PDF sans Word')


def session_records():
    return st.session_state.setdefault('session_records', [])


def find_session_record(no_clar):
    for rec in reversed(session_records()):
        if rec.get('no_clar', '').upper() == no_clar.upper():
            return rec
    return None


def upsert_session_record(record):
    records = session_records()
    for i, rec in enumerate(records):
        if rec.get('no_clar', '').upper() == record.get('no_clar', '').upper():
            records[i] = record
            return
    records.append(record)


def render_session_exports(db_bytes):
    records = session_records()
    if not records:
        st.info('Aucun contrat n’a été préparé dans cette session.')
        return
    conv_headers = workbook_headers(db_bytes, 'CONV ADM')
    fin_headers = workbook_headers(db_bytes, 'FINANCEMENTS')
    import_xlsx = build_import_xlsx(records, conv_headers, fin_headers)
    session_json = build_session_json(records)
    session_zip = build_session_zip(records, import_xlsx, session_json)

    st.subheader('Fin de session – fichiers à récupérer')
    st.markdown(
        '<div class="clarte-box"><b>La base .xlsm n’a pas été modifiée.</b><br>'
        'Le fichier d’import contient les lignes à injecter dans CONV ADM et FINANCEMENTS. '
        'La macro locale Clarté360 sera chargée d’écrire ces données dans votre vraie base et de laisser Excel recalculer ses formules.</div>',
        unsafe_allow_html=True,
    )
    st.dataframe([
        {
            'NO_CLAR': r['no_clar'],
            'Prestation': r.get('prestation', ''),
            'Contrat': r.get('contract_type', ''),
            'Bénéficiaire': r.get('beneficiaire_label', ''),
            'HT action': r.get('conv_values', {}).get('INTRA_HT', ''),
            'Financeurs': len(r.get('financements') or []),
        }
        for r in records
    ], hide_index=True, use_container_width=True)

    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    st.download_button(
        '⬇️ Fichier d’import Excel – CONV ADM + FINANCEMENTS',
        data=import_xlsx,
        file_name=f'CLARTE360_IMPORT_SESSION_{stamp}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        use_container_width=True,
    )
    st.download_button(
        '⬇️ Sauvegarde JSON complète de la session',
        data=session_json,
        file_name=f'CLARTE360_IMPORT_SESSION_{stamp}.json',
        mime='application/json',
        use_container_width=True,
    )
    st.download_button(
        '⬇️ Dossier complet de la session (ZIP)',
        data=session_zip,
        file_name=f'CLARTE360_CONTRACTUALISATION_SESSION_{stamp}.zip',
        mime='application/zip',
        use_container_width=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button('Reprendre / ajouter un contrat', use_container_width=True):
            st.session_state.session_finished = False
            st.session_state.form_seq = st.session_state.get('form_seq', 0) + 1
            st.rerun()
    with c2:
        if st.button('Purger la session après téléchargement', use_container_width=True):
            for key in ['session_records', 'session_finished', 'await_next', 'last_no_clar']:
                st.session_state.pop(key, None)
            st.session_state.form_seq = st.session_state.get('form_seq', 0) + 1
            st.rerun()


gate()
page_header()

st.markdown(
    '<div class="clarte-box"><b>Règle de fonctionnement :</b> vous chargez votre base Clarté360 pour la lire. '
    'Elle sert à retrouver un NO_CLAR déjà renseigné ou à attribuer le prochain NO_CLAR libre. '
    '<b>Elle n’est jamais modifiée ni proposée au téléchargement.</b></div>',
    unsafe_allow_html=True,
)

uploaded_db = st.file_uploader('Base Clarté360 de référence (.xlsm) – lecture seule', type=['xlsm'], key='db_local')
if uploaded_db is None:
    st.info('Chargez votre base Excel Clarté360 pour commencer.')
    st.stop()

db_filename = uploaded_db.name or 'GESTION_OF_CLARTE360.xlsm'
db_bytes = uploaded_db.getvalue()
info = inspect_workbook(db_bytes)
if not info['has_vba']:
    st.error('Le classeur chargé ne contient pas le projet VBA attendu.')
    st.stop()
st.success(f"Base de référence chargée en lecture seule – {db_filename} – macros VBA détectées – {info['zip_entries']} composants internes.")

if st.session_state.get('session_finished'):
    render_session_exports(db_bytes)
    st.stop()

if st.session_state.get('await_next'):
    rec = find_session_record(st.session_state.get('last_no_clar', ''))
    st.subheader('Contrat ajouté à la session')
    if rec:
        st.success(f"{rec['no_clar']} – {rec.get('beneficiaire_label','')} est prêt. Les données d’import CONV ADM / FINANCEMENTS ont été mémorisées dans la session.")
        if rec.get('contract_json_bytes'):
            st.download_button('⬇️ Dossier contractuel JSON', rec['contract_json_bytes'], file_name=f"{rec['no_clar']}_dossier_contractuel.json", mime='application/json', use_container_width=True)
        if rec.get('pdf_bytes'):
            st.download_button('⬇️ Contrat PDF', rec['pdf_bytes'], file_name=rec.get('pdf_name') or f"{rec['no_clar']}_contrat.pdf", mime='application/pdf', use_container_width=True)
        else:
            st.warning('Le moteur PDF de ce type de contrat n’est pas encore activé.')
    c1, c2 = st.columns(2)
    with c1:
        if st.button('➕ Préparer un autre contrat', type='primary', use_container_width=True):
            st.session_state.await_next = False
            st.session_state.form_seq = st.session_state.get('form_seq', 0) + 1
            st.rerun()
    with c2:
        if st.button('✅ Terminer la session et préparer l’import Excel', use_container_width=True):
            st.session_state.await_next = False
            st.session_state.session_finished = True
            st.rerun()
    st.stop()

form_seq = st.session_state.get('form_seq', 0)
reserved = [r.get('no_clar') for r in session_records()]

mode = st.radio(
    '1. Source du dossier',
    ['Nouveau contrat depuis une APS JSON', 'Contrat à partir d’un NO_CLAR déjà renseigné'],
    horizontal=True,
    key=f'mode_{form_seq}',
)

aps = None
existing = {}
existing_action = {}
source_label = ''
operation = 'CREATION'
rownum = None
no_clar = ''

if mode.startswith('Nouveau'):
    aps_file = st.file_uploader('Charger l’APS JSON du bénéficiaire', type=['json'], key=f'aps_{form_seq}')
    if not aps_file:
        st.stop()
    try:
        aps = parse_aps(aps_file)
    except Exception as e:
        st.error(str(e))
        st.stop()
    try:
        rownum, no_clar = next_available_action(db_bytes, reserved=reserved)
    except Exception as e:
        st.error(str(e))
        st.stop()
    st.info(f'Prochaine action libre : **{no_clar}**. Elle est réservée dans cette session ; la base Excel n’est pas modifiée.')
    source_label = 'APS_JSON'
else:
    no_clar = st.text_input('N° action Clarté360 (ex. CLA0002)', key=f'no_{form_seq}').strip().upper()
    if not no_clar:
        st.stop()
    session_rec = find_session_record(no_clar)
    if session_rec:
        existing_action = dict(session_rec.get('conv_values') or {})
        existing = existing_action
        source_label = 'SESSION'
        operation = 'MISE_A_JOUR'
        st.success(f'Action {no_clar} retrouvée dans la session en cours.')
    else:
        found = action_row(db_bytes, no_clar)
        if not found:
            st.error('Action introuvable dans la base chargée et dans la session.')
            st.stop()
        rownum, existing = found
        existing_action = existing
        source_label = 'BASE_EXCEL'
        operation = 'MISE_A_JOUR'
        st.success(f'Action {no_clar} trouvée dans CONV ADM.')

# Defaults from source
b = (aps or {}).get('beneficiaire', {})
dem = (aps or {}).get('demande_besoin', {})
obj = (aps or {}).get('objectifs', {})
mod = (aps or {}).get('modalites', {})
financeur_aps = str((aps or {}).get('convention_future', {}).get('financeur_envisage', ''))

if mode.startswith('Contrat'):
    session_rec = find_session_record(no_clar)
    if session_rec and session_rec.get('contract_data'):
        cb = session_rec['contract_data'].get('beneficiaire', {})
        b = dict(cb)
        ca = session_rec['contract_data'].get('action', {})
        dem = {'revalidation_entretien': ca.get('demande', '')}
        obj = {'objectifs_personnels': ca.get('objectifs', ''), 'criteres_reussite': ca.get('criteres_reussite', '')}
        mod = {'format_souhaite': ca.get('modalite', '')}
    else:
        b = {
            'prenom': existing.get('PRENOM_STAGIAIRE', ''),
            'nom': existing.get('NOM_STAGIAIRE', ''),
            'nom_naissance': existing.get('NOM_DE_NAISSANCE', ''),
            'date_naissance': existing.get('DATE_NAISSANCE', ''),
            'adresse': existing.get('ADRESSE', ''),
            'code_postal': existing.get('CODE_POST', ''),
            'ville': existing.get('VILLE', ''),
            'email': existing.get('EMAIL', ''),
            'telephone': '',
            'civilite': 'Madame' if existing.get('SEXE_1_Homme_2_Femme') == 2 else 'Monsieur' if existing.get('SEXE_1_Homme_2_Femme') == 1 else '',
        }
        dem = {}
        obj = {}
        mod = {'format_souhaite': existing.get('Adresse_du_site', '')}

st.subheader('2. Client / bénéficiaire')
c1, c2, c3 = st.columns(3)
with c1:
    prenom = st.text_input('Prénom bénéficiaire', value=str(b.get('prenom', '')).title(), key=f'prenom_{form_seq}')
    nom = st.text_input('Nom bénéficiaire', value=str(b.get('nom', '')).upper(), key=f'nom_{form_seq}')
with c2:
    email = st.text_input('E-mail', value=str(b.get('email', '')), key=f'email_{form_seq}')
    telephone = st.text_input('Téléphone', value=str(b.get('telephone', '')), key=f'tel_{form_seq}')
with c3:
    birth = st.date_input('Date de naissance', value=to_date(b.get('date_naissance'), None), key=f'birth_{form_seq}')
    civilite = st.selectbox('Civilité', ['Madame', 'Monsieur', ''], index=['Madame', 'Monsieur', ''].index(str(b.get('civilite', ''))) if str(b.get('civilite', '')) in ['Madame', 'Monsieur', ''] else 2, key=f'civ_{form_seq}')
adresse = st.text_input('Adresse', value=str(b.get('adresse', '')), key=f'adresse_{form_seq}')
c1, c2 = st.columns(2)
with c1:
    cp = st.text_input('Code postal', value=str(b.get('code_postal', '')), key=f'cp_{form_seq}')
with c2:
    ville = st.text_input('Ville', value=str(b.get('ville', '')).upper(), key=f'ville_{form_seq}')

st.subheader('3. Action / contractualisation')
c1, c2, c3 = st.columns(3)
with c1:
    prestation = st.selectbox('Type de prestation', ['Bilan de compétences', 'Coaching professionnel', 'Formation professionnelle', 'Autre prestation'], index=0, key=f'prest_{form_seq}')
with c2:
    contract_type = st.selectbox('Type de contractualisation', ['Particulier – bipartite', 'Entreprise – bipartite', 'Tripartite'], index=0, key=f'ctype_{form_seq}')
with c3:
    contract_date = st.date_input('Date du contrat', value=date.today(), key=f'cdate_{form_seq}')
intitule_compl = st.text_input('Intitulé complémentaire (facultatif)', value=str(existing_action.get('INTITULE_FORMA_COMPL') or ''), key=f'intcomp_{form_seq}')

if prestation != 'Bilan de compétences' or contract_type != 'Particulier – bipartite':
    st.warning('Dans cette version, le PDF juridiquement finalisé est uniquement activé pour **Bilan de compétences – Particulier bipartite**. La structure de session est conçue pour accueillir ensuite tous les autres modèles.')

st.subheader('4. Organisation')
st.caption('L’APS ne contient pas le calendrier contractuel, la durée définitive ni le prix. Ces éléments sont saisis ici ou repris de CONV ADM lorsqu’ils existent.')
c1, c2, c3 = st.columns(3)
with c1:
    duree = st.number_input('Durée d’accompagnement (heures)', min_value=0.5, value=float(existing_action.get('DUREE_HEURES_STAGIAIRE')) if isinstance(existing_action.get('DUREE_HEURES_STAGIAIRE'), (int, float)) else None, step=0.5, placeholder='À renseigner', key=f'duree_{form_seq}')
    nb_temps = st.number_input('Nombre de temps / séances', min_value=1, value=int(existing_action.get('REPARTITION_NB_DE_JOURS')) if isinstance(existing_action.get('REPARTITION_NB_DE_JOURS'), (int, float)) else None, step=1, placeholder='À renseigner', key=f'ntemps_{form_seq}')
with c2:
    date_debut = st.date_input('Début de l’action', value=to_date(existing_action.get('Date_debut_action'), None), key=f'ddeb_{form_seq}')
    date_fin = st.date_input('Fin de l’action', value=to_date(existing_action.get('Date_de_fin_d_action'), None), key=f'dfin_{form_seq}')
with c3:
    modalite_default = str(existing_action.get('Adresse_du_site') or existing_action.get('Nom_site') or mod.get('format_souhaite') or '')
    modalite = st.text_input('Lieu / modalité', value=modalite_default, key=f'modal_{form_seq}')
    consultant = st.text_input('Accompagnateur', value=str(existing_action.get('Nom_et_Prenom_du_formateur') or get_secret('contractualisation', 'consultant_name', 'BRIET Dominique')), key=f'consult_{form_seq}')
    consultant_email = st.text_input('E-mail accompagnateur', value=str(existing_action.get('email_du_formateur') or get_secret('contractualisation', 'consultant_email', 'dbriet@clarte360.com')), key=f'consultmail_{form_seq}')
consultant_tel = st.text_input('Téléphone accompagnateur', value=str(existing_action.get('telephone_du_formateur') or get_secret('contractualisation', 'consultant_phone', '')), key=f'consulttel_{form_seq}')
ct1, ct2 = st.columns(2)
with ct1:
    horaire_debut = st.time_input('Horaire habituel de début', value=existing_action.get('Horaire_du_site_debut') if isinstance(existing_action.get('Horaire_du_site_debut'), time) else time(10, 0), key=f'hdeb_{form_seq}')
with ct2:
    horaire_fin = st.time_input('Horaire habituel de fin', value=existing_action.get('Horaire_du_site_fin') if isinstance(existing_action.get('Horaire_du_site_fin'), time) else time(11, 30), key=f'hfin_{form_seq}')

calendrier = st.text_area('Calendrier / planning prévisionnel – texte repris tel quel dans CONV ADM', value=str(existing_action.get('CALENDRIER') or ''), height=220, key=f'cal_{form_seq}')
demande = st.text_area('Demande / besoin', value=str(dem.get('revalidation_entretien') or dem.get('origine_demande') or ''), height=90, key=f'dem_{form_seq}')
objectifs = st.text_area('Objectifs individualisés', value=str(obj.get('objectifs_personnels', '')), height=90, key=f'obj_{form_seq}')
criteres = st.text_area('Critères de réussite', value=str(obj.get('criteres_reussite', '')), height=70, key=f'crit_{form_seq}')

if aps:
    with st.expander('Voir la correspondance APS JSON → CONV ADM', expanded=False):
        st.dataframe([
            {'Source APS': 'beneficiaire.prenom', 'CONV ADM': 'PRENOM_STAGIAIRE', 'Valeur': prenom},
            {'Source APS': 'beneficiaire.nom', 'CONV ADM': 'NOM_STAGIAIRE', 'Valeur': nom},
            {'Source APS': 'beneficiaire.nom_naissance', 'CONV ADM': 'NOM_DE_NAISSANCE', 'Valeur': str(b.get('nom_naissance', ''))},
            {'Source APS': 'beneficiaire.date_naissance', 'CONV ADM': 'DATE_NAISSANCE', 'Valeur': str(birth)},
            {'Source APS': 'beneficiaire.email', 'CONV ADM': 'EMAIL', 'Valeur': email},
            {'Source APS': 'beneficiaire.adresse', 'CONV ADM': 'ADRESSE + client particulier', 'Valeur': adresse},
            {'Source APS': 'beneficiaire.code_postal', 'CONV ADM': 'CODE_POST', 'Valeur': cp},
            {'Source APS': 'beneficiaire.ville', 'CONV ADM': 'VILLE', 'Valeur': ville},
            {'Source APS': 'modalites.format_souhaite', 'CONV ADM': 'Nom_site / Adresse_du_site à valider', 'Valeur': str(mod.get('format_souhaite', ''))},
            {'Source APS': 'convention_future.financeur_envisage', 'CONV ADM': 'Prépare FINANCEMENTS, jamais un montant', 'Valeur': financeur_aps},
        ], use_container_width=True, hide_index=True)

st.subheader('5. Prix et financements')
c1, c2, c3 = st.columns(3)
existing_ht = existing_action.get('INTRA_HT') if existing_action else None
with c1:
    total_ht = st.number_input('Montant total HT de l’action – sera injecté uniquement dans INTRA_HT', min_value=0.0, value=float(existing_ht) if isinstance(existing_ht, (int, float)) else None, step=10.0, placeholder='À renseigner', key=f'ht_{form_seq}')
with c2:
    taux_tva = st.number_input('TVA (%)', min_value=0.0, value=20.0, step=1.0, key=f'tva_{form_seq}')
total_ttc = (float(total_ht) * (1 + taux_tva / 100)) if total_ht is not None else None
with c3:
    st.metric('Prix total TTC', euro(total_ttc) if total_ttc is not None else '-')

seed = []
session_rec = find_session_record(no_clar)
if session_rec:
    seed = [
        {
            'TYPE_FINANCEUR': r.get('TYPE_FINANCEUR', ''),
            'NOM_FINANCEUR': r.get('NOM_FINANCEUR', ''),
            'MONTANT_TTC': r.get('MONTANT_TTC', None),
            'TAUX_TVA': r.get('TAUX_TVA', taux_tva),
            'FACTURE_A_ETABLIR_A': r.get('FACTURE_A_ETABLIR_A', ''),
            'STATUT_FINANCEMENT': r.get('STATUT_FINANCEMENT', 'Prévu'),
            'OBSERVATIONS': r.get('OBSERVATIONS', ''),
        }
        for r in session_rec.get('financements') or []
    ]
elif mode.startswith('Contrat'):
    existing_fin = read_financements_for_action(db_bytes, no_clar)
    seed = [
        {
            'TYPE_FINANCEUR': r.get('TYPE_FINANCEUR', ''),
            'NOM_FINANCEUR': r.get('NOM_FINANCEUR', ''),
            'MONTANT_TTC': r.get('MONTANT_TTC', None),
            'TAUX_TVA': r.get('TAUX_TVA', taux_tva),
            'FACTURE_A_ETABLIR_A': r.get('FACTURE_A_ETABLIR_A', ''),
            'STATUT_FINANCEMENT': r.get('STATUT_FINANCEMENT', 'Prévu'),
            'OBSERVATIONS': r.get('OBSERVATIONS', ''),
        }
        for r in existing_fin
    ]
elif aps and 'personnel' in financeur_aps.lower():
    seed = [{
        'TYPE_FINANCEUR': 'BENEFICIAIRE',
        'NOM_FINANCEUR': f'{prenom} {nom}'.strip(),
        'MONTANT_TTC': None,
        'TAUX_TVA': taux_tva,
        'FACTURE_A_ETABLIR_A': f'{prenom} {nom} {adresse} {cp} {ville}'.strip(),
        'STATUT_FINANCEMENT': 'Prévu',
        'OBSERVATIONS': 'Financement personnel déclaré dans l’APS',
    }]

fin = st.data_editor(
    seed,
    num_rows='dynamic',
    use_container_width=True,
    column_config={
        'TYPE_FINANCEUR': st.column_config.SelectboxColumn('Type financeur', options=['BENEFICIAIRE', 'ENTREPRISE', 'CPF', 'OPCO', 'FRANCE TRAVAIL', 'AUTRE FINANCEUR']),
        'MONTANT_TTC': st.column_config.NumberColumn('Montant TTC', min_value=0.0, step=10.0, format='%.2f €'),
        'TAUX_TVA': st.column_config.NumberColumn('TVA %', min_value=0.0, step=1.0, format='%.1f'),
    },
    key=f'finance_editor_{form_seq}_{no_clar}',
)
fin_rows = fin.to_dict('records') if hasattr(fin, 'to_dict') else list(fin)
sum_fin = sum(float(r.get('MONTANT_TTC') or 0) for r in fin_rows)
diff = round((float(total_ttc) if total_ttc is not None else 0.0) - sum_fin, 2)
if total_ttc is not None and abs(diff) < 0.01:
    st.success(f'Financement équilibré : {euro(sum_fin)} TTC')
elif total_ttc is not None:
    st.error(f'Écart de financement : {euro(diff)}')

modalites_paiement = st.text_area(
    'Modalités de paiement / précisions',
    value='Le reste à charge du bénéficiaire est soumis aux règles de paiement applicables au contrat individuel de bilan de compétences. Les autres prises en charge sont facturées selon les accords conclus avec les financeurs concernés.',
    height=80,
    key=f'pay_{form_seq}',
)

st.subheader('6. Contrôles et ajout à la session')
if prestation == 'Bilan de compétences' and contract_type == 'Particulier – bipartite' and date_debut and date_debut < contract_date:
    st.markdown('<div class="clarte-warning"><b>Attention conformité :</b> la date de début de l’action est antérieure à la date du contrat. Vérifiez la chronologie du dossier ; l’application ne rétrodate jamais un contrat.</div>', unsafe_allow_html=True)

can_generate = bool(total_ttc and total_ttc > 0 and duree and nb_temps and date_debut and date_fin and calendrier.strip() and prenom and nom and email and abs(diff) < 0.01)
if not can_generate:
    st.info('Complétez les champs obligatoires et équilibrez les financements pour préparer le contrat.')

if can_generate and st.button('Ajouter ce contrat à la session et générer le PDF', type='primary', use_container_width=True, key=f'gen_{form_seq}'):
    ht = round(float(total_ht), 2)
    frows = calc_finance_rows(no_clar, fin_rows)
    facturer_a = ' / '.join(
        f"{str(x.get('NOM_FINANCEUR') or x.get('TYPE_FINANCEUR') or '').strip()} – {euro(x.get('MONTANT_TTC') or 0)} TTC"
        for x in frows
        if float(x.get('MONTANT_TTC') or 0) > 0
    )
    obs = ' | '.join(
        f"{x.get('TYPE_FINANCEUR')}: {x.get('NOM_FINANCEUR')} – {euro(x.get('MONTANT_TTC') or 0)} TTC"
        for x in frows
        if float(x.get('MONTANT_TTC') or 0) > 0
    )

    values = {
        'DATE_CONV': contract_date,
        'NOM_ENT': f'{prenom} {nom}'.strip() if contract_type == 'Particulier – bipartite' else existing_action.get('NOM_ENT', ''),
        'ADRESSE': adresse,
        'CODE_POST': cp,
        'VILLE': ville,
        'SPEC_BPF': 'Autres' if prestation == 'Bilan de compétences' else existing_action.get('SPEC_BPF', ''),
        'INTITULE_FORMA': 'Bilan de compétences' if prestation == 'Bilan de compétences' else prestation,
        'INTITULE_FORMA_COMPL': intitule_compl,
        'DUREE_HEURES_STAGIAIRE': duree,
        'REPARTITION_NB_DE_JOURS': nb_temps,
        'INTRA_HT': ht,
        'FACTURE_A_ETABLIR_A': facturer_a,
        'OBSERVATIONS': obs,
        'NOM_STAGIAIRE': nom,
        'NOM_DE_NAISSANCE': str(b.get('nom_naissance', '')),
        'PRENOM_STAGIAIRE': prenom,
        'SEXE_1_Homme_2_Femme': 2 if civilite == 'Madame' else 1 if civilite == 'Monsieur' else None,
        'DATE_NAISSANCE': birth,
        'EMAIL': email,
        'Date_debut_action': date_debut,
        'Date_de_fin_d_action': date_fin,
        'CALENDRIER': calendrier,
        'Contact_mise_en_place_de_la_formation_Nom_et_ou_Prenom': CLEAR_TOKEN if contract_type == 'Particulier – bipartite' else None,
        'Email_du_contact_de_la_formation': CLEAR_TOKEN if contract_type == 'Particulier – bipartite' else None,
        'No_de_telephone_du_contact_de_la_formation': CLEAR_TOKEN if contract_type == 'Particulier – bipartite' else None,
        'Nom_site': modalite,
        'Adresse_du_site': modalite,
        'Horaire_du_site_debut': horaire_debut,
        'Horaire_du_site_fin': horaire_fin,
        'Nombre_de_stagiaires': 1 if contract_type == 'Particulier – bipartite' else existing_action.get('Nombre_de_stagiaires', None),
        'Nom_et_Prenom_du_formateur': consultant,
        'email_du_formateur': consultant_email,
        'telephone_du_formateur': consultant_tel,
        'NOM_STRUCTURE': 'Clarté360',
    }

    contract_data = {
        'beneficiaire': {
            'civilite': civilite,
            'prenom': prenom,
            'nom': nom,
            'date_naissance': birth,
            'adresse': adresse,
            'code_postal': cp,
            'ville': ville,
            'email': email,
            'telephone': telephone,
        },
        'action': {
            'no_clar': no_clar,
            'date_contrat': contract_date,
            'duree_heures': duree,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'modalite': modalite,
            'calendrier': calendrier,
            'demande': demande,
            'objectifs': objectifs,
            'criteres_reussite': criteres,
            'suivi_6_mois': f'Un entretien de suivi est proposé environ six mois après la conclusion du bilan. Il est distinct des {duree:g} heures d’accompagnement contractualisées.',
        },
        'prix': {
            'ttc': total_ttc,
            'ht': ht,
            'tva': total_ttc - ht,
            'modalites_paiement': modalites_paiement,
        },
        'financements': frows,
        'consultant': {'nom': consultant, 'email': consultant_email, 'telephone': consultant_tel},
    }

    pdf_bytes = None
    pdf_name = None
    if prestation == 'Bilan de compétences' and contract_type == 'Particulier – bipartite':
        pdf_bytes = build_bc_particulier_pdf(contract_data, LOGO)
        pdf_name = f'{no_clar}_CONTRAT_BILAN_COMPETENCES_{nom}_{prenom}.pdf'.replace(' ', '_')
    contract_json_bytes = json.dumps(contract_data, ensure_ascii=False, default=str, indent=2).encode('utf-8')

    rec = {
        'no_clar': no_clar,
        'operation': operation,
        'source': source_label,
        'prestation': prestation,
        'contract_type': contract_type,
        'beneficiaire_label': f'{prenom} {nom}'.strip(),
        'model_version': MODEL_VERSION if pdf_bytes else '',
        'conv_values': values,
        'financements': frows,
        'contract_data': contract_data,
        'pdf_bytes': pdf_bytes,
        'pdf_name': pdf_name,
        'contract_json_bytes': contract_json_bytes,
    }
    upsert_session_record(rec)
    st.session_state.last_no_clar = no_clar
    st.session_state.await_next = True
    st.rerun()

if session_records():
    st.markdown('---')
    st.caption(f"Session en cours : {len(session_records())} action(s) préparée(s) – " + ', '.join(r['no_clar'] for r in session_records()))

st.markdown('---')
st.caption(f"Clarté360 – Application administrative de contractualisation – V{APP_VERSION}. La base Excel chargée est utilisée en lecture seule. Modèle BC actif : {MODEL_VERSION}.")
