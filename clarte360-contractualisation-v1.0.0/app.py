from __future__ import annotations

import io, json, uuid, zipfile
from datetime import date, datetime, time
from pathlib import Path

import streamlit as st

from xlsm_safe import inspect_workbook, first_available_conv_row, patch_conv_adm, replace_financements_for_action, force_recalc_on_open, action_row, workbook_values, ensure_financements_schema, assert_xlsm_integrity
from contracts import build_bc_particulier_pdf, MODEL_VERSION

APP_VERSION='1.1.1-VPS-BASE-LOCALE'
APP_NAME='Clarté360 – Contractualisation'
BASE=Path(__file__).resolve().parent
LOGO=BASE/'assets'/'site_icon.png'
TEAL='#008080'; LIGHT='#E6F4F4'; DARK='#243A3A'

st.set_page_config(page_title=APP_NAME,page_icon='📄',layout='wide')
st.markdown(f"""<style>
.stApp {{color:{DARK};}} .clarte-box{{background:{LIGHT};border-left:6px solid {TEAL};padding:16px 18px;border-radius:10px;margin:8px 0 16px 0;}}
.clarte-warning{{background:#fff7d6;border-left:6px solid #d6a600;padding:14px 16px;border-radius:10px;}}
.small{{font-size:.85rem;color:#667777}}
</style>""",unsafe_allow_html=True)


def get_secret(section,key,default=''):
    try: return st.secrets.get(section,{}).get(key,default)
    except Exception: return default


def gate():
    expected=str(get_secret('security','admin_password','')).strip()
    if st.session_state.get('auth'): return
    if LOGO.exists(): st.image(str(LOGO),width=90)
    st.title(APP_NAME)
    st.markdown('<div class="clarte-box"><b>Application administrative Clarté360.</b><br>Le programme fonctionne sur le VPS, mais votre base Excel reste sur votre ordinateur. Vous chargez ponctuellement le fichier .xlsm, l’application travaille uniquement sur sa copie en mémoire, puis vous récupérez la base mise à jour. Aucune base Excel Clarté360 n’est conservée sur le VPS.</div>',unsafe_allow_html=True)
    if not expected:
        st.error("Le mot de passe administrateur n'est pas configuré. Ajoutez [security].admin_password dans les Secrets Streamlit Cloud.")
        st.stop()
    pwd=st.text_input('Mot de passe administrateur',type='password')
    if st.button('Ouvrir l’application',type='primary'):
        if pwd==expected:
            st.session_state.auth=True; st.rerun()
        else: st.error('Mot de passe incorrect.')
    st.stop()

def parse_aps(file):
    d=json.load(file)
    if d.get('meta',{}).get('document_type')!='APS': raise ValueError('Le JSON fourni ne semble pas être une APS Clarté360.')
    return d

def calc_finance_rows(no_clar, rows):
    out=[]
    for i,r in enumerate(rows, start=1):
        amt=float(r.get('MONTANT_TTC') or 0)
        rate=float(r.get('TAUX_TVA') or 20)
        ht=amt/(1+rate/100) if rate!=-100 else amt
        out.append({
            'ID_FINANCEMENT':f'FIN-{no_clar}-{i:02d}','NO_CLAR':no_clar,'ORDRE':i,'ORDRE_FINANCEMENT':i,
            'TYPE_FINANCEUR':r.get('TYPE_FINANCEUR',''),'NOM_FINANCEUR':r.get('NOM_FINANCEUR',''),
            'SIRET_FINANCEUR':r.get('SIRET_FINANCEUR',''),'ADRESSE_FINANCEUR':r.get('ADRESSE_FINANCEUR',''),
            'CODE_POST_FINANCEUR':r.get('CODE_POST_FINANCEUR') or r.get('CP_FINANCEUR',''),'CP_FINANCEUR':r.get('CP_FINANCEUR') or r.get('CODE_POST_FINANCEUR',''),'VILLE_FINANCEUR':r.get('VILLE_FINANCEUR',''),
            'CONTACT_FINANCEUR':r.get('CONTACT_FINANCEUR',''),'EMAIL_FACTURATION':r.get('EMAIL_FACTURATION') or r.get('EMAIL_FINANCEUR',''),'EMAIL_FINANCEUR':r.get('EMAIL_FINANCEUR') or r.get('EMAIL_FACTURATION',''),'MONTANT_HT':round(ht,2),'TAUX_TVA':rate,
            'MONTANT_TVA':round(amt-ht,2),'MONTANT_TTC':round(amt,2),'FACTURE_A_ETABLIR_A':r.get('FACTURE_A_ETABLIR_A',''),
            'REFERENCE_PRISE_EN_CHARGE':r.get('REFERENCE_PRISE_EN_CHARGE',''),'STATUT_FINANCEMENT':r.get('STATUT_FINANCEMENT','Prévu'),
            'DATE_ACCORD':r.get('DATE_ACCORD',''),'OBSERVATIONS':r.get('OBSERVATIONS','')})
    return out

def to_date(s, fallback=None):
    if isinstance(s,(date,datetime)): return s.date() if isinstance(s,datetime) else s
    try: return datetime.fromisoformat(str(s)[:10]).date()
    except Exception: return fallback


def page_header():
    c1,c2=st.columns([1,8])
    with c1:
        if LOGO.exists(): st.image(str(LOGO),width=78)
    with c2:
        st.title(APP_NAME)
        st.caption(f'Version {APP_VERSION} – application VPS / base Excel locale – moteur PDF sans Word')


gate(); page_header()

st.markdown("""<div class="clarte-box"><b>Base de données :</b> la base maître reste sur votre ordinateur. Le VPS n'en conserve aucune copie permanente. Chargez la base Clarté360 à traiter ; elle reste en mémoire pendant la session et la version mise à jour vous est proposée au téléchargement après validation.</div>""",unsafe_allow_html=True)

uploaded_db=st.file_uploader('Base Clarté360 locale (.xlsm)',type=['xlsm'],key='db_local')
if uploaded_db is None:
    st.info('Chargez votre base Excel Clarté360 pour commencer. Aucune base n’est stockée sur le VPS.')
    st.stop()

db_filename=uploaded_db.name or 'GESTION_OF_CLARTE360.xlsm'
db_bytes=uploaded_db.getvalue()
info=inspect_workbook(db_bytes)
if not info['has_vba']:
    st.error('Le classeur chargé ne contient pas le projet VBA attendu. Aucune écriture n’est autorisée.')
    st.stop()
try:
    db_bytes,_=ensure_financements_schema(db_bytes)
except Exception as e:
    st.error(f'Base non compatible : {e}')
    st.stop()
st.success(f"Base locale chargée – {db_filename} – macros VBA détectées – {info['zip_entries']} composants internes.")

mode=st.radio('1. Source du dossier',['Créer / compléter depuis une APS JSON','Reprendre une action déjà présente dans la base'],horizontal=True)
aps=None; rownum=None; no_clar=''
if mode.startswith('Créer'):
    aps_file=st.file_uploader('Charger l’APS JSON du bénéficiaire',type=['json'])
    if not aps_file: st.stop()
    try: aps=parse_aps(aps_file)
    except Exception as e: st.error(str(e)); st.stop()
    rownum,no_clar=first_available_conv_row(db_bytes)
    st.info(f'Première action libre détectée : **{no_clar}** (ligne {rownum} de CONV ADM).')
else:
    no_clar=st.text_input('N° action Clarté360 (ex. CLA0002)').strip().upper()
    if not no_clar: st.stop()
    found=action_row(db_bytes,no_clar)
    if not found: st.error('Action introuvable.'); st.stop()
    rownum,existing=found
    st.success(f'Action {no_clar} trouvée.')

# Build defaults
b=(aps or {}).get('beneficiaire',{})
dem=(aps or {}).get('demande_besoin',{})
obj=(aps or {}).get('objectifs',{})
mod=(aps or {}).get('modalites',{})
if mode.startswith('Reprendre'):
    b={'prenom':existing.get('PRENOM_STAGIAIRE',''),'nom':existing.get('NOM_STAGIAIRE',''),'date_naissance':existing.get('DATE_NAISSANCE',''),'adresse':existing.get('ADRESSE',''),'code_postal':existing.get('CODE_POST',''),'ville':existing.get('VILLE',''),'email':existing.get('EMAIL',''),'telephone':''}
    dem={}; obj={}; mod={'format_souhaite':existing.get('Adresse_du_site','')}

existing_action = existing if mode.startswith('Reprendre') else {}

st.subheader('2. Données de l’action et du bénéficiaire')
c1,c2,c3=st.columns(3)
with c1:
    prestation=st.selectbox('Type de prestation',['Bilan de compétences','Coaching professionnel','Formation professionnelle','Autre prestation'],index=0)
    contract_type=st.selectbox('Type de contractualisation',['Particulier – bipartite','Entreprise – bipartite','Tripartite'],index=0)
    contract_date=st.date_input('Date du contrat',value=date.today())
with c2:
    prenom=st.text_input('Prénom bénéficiaire',value=str(b.get('prenom','')).title())
    nom=st.text_input('Nom bénéficiaire',value=str(b.get('nom','')).upper())
    email=st.text_input('E-mail',value=str(b.get('email','')))
with c3:
    birth=st.date_input('Date de naissance',value=to_date(b.get('date_naissance'),None))
    telephone=st.text_input('Téléphone',value=str(b.get('telephone','')))
    adresse=st.text_input('Adresse',value=str(b.get('adresse','')))
cp=st.text_input('Code postal',value=str(b.get('code_postal',''))); ville=st.text_input('Ville',value=str(b.get('ville','')).upper())
intitule_compl=st.text_input('Intitulé complémentaire',value=str(existing_action.get('INTITULE_FORMA_COMPL') or '') if mode.startswith('Reprendre') else '')

if prestation!='Bilan de compétences':
    st.warning('La V1.0 génère juridiquement le contrat **Bilan de compétences – particulier bipartite**. Les moteurs Coaching / Formation / Tripartite sont préparés dans l’architecture mais seront activés après validation de leurs clauses. Vous pouvez néanmoins préparer la base.')

st.subheader('3. Organisation du bilan')
st.caption('Important : l’APS ne contient ni le calendrier contractuel, ni la durée définitive, ni le prix. L’application ne les invente pas : ces éléments doivent être saisis ici ou provenir d’une action déjà renseignée dans CONV ADM.')
c1,c2,c3=st.columns(3)
with c1:
    duree=st.number_input('Durée d’accompagnement (heures)',min_value=0.5,value=float(existing_action.get('DUREE_HEURES_STAGIAIRE')) if existing_action.get('DUREE_HEURES_STAGIAIRE') else None,step=0.5,placeholder='À renseigner')
    nb_temps=st.number_input('Nombre de temps / séances',min_value=1,value=int(existing_action.get('REPARTITION_NB_DE_JOURS')) if existing_action.get('REPARTITION_NB_DE_JOURS') else None,step=1,placeholder='À renseigner')
with c2:
    date_debut=st.date_input('Début de l’action',value=to_date(existing_action.get('Date_debut_action'),None))
    date_fin=st.date_input('Fin de l’action',value=to_date(existing_action.get('Date_de_fin_d_action'),None))
with c3:
    modalite_default = str(existing_action.get('Adresse_du_site') or existing_action.get('Nom_site') or mod.get('format_souhaite') or '')
    modalite=st.text_input('Lieu / modalité',value=modalite_default)
    consultant=st.text_input('Accompagnateur',value=str(existing_action.get('Nom_et_Prenom_du_formateur') or get_secret('contractualisation','consultant_name','BRIET Dominique')))
    consultant_email=st.text_input('E-mail accompagnateur',value=str(existing_action.get('email_du_formateur') or get_secret('contractualisation','consultant_email','dbriet@clarte360.com')))
consultant_tel=st.text_input('Téléphone accompagnateur',value=str(existing_action.get('telephone_du_formateur') or get_secret('contractualisation','consultant_phone','')))
ct1,ct2=st.columns(2)
with ct1:
    horaire_debut=st.time_input('Horaire habituel de début',value=existing_action.get('Horaire_du_site_debut') if isinstance(existing_action.get('Horaire_du_site_debut'),time) else time(10,0))
with ct2:
    horaire_fin=st.time_input('Horaire habituel de fin',value=existing_action.get('Horaire_du_site_fin') if isinstance(existing_action.get('Horaire_du_site_fin'),time) else time(11,30))

calendrier=st.text_area('Planning prévisionnel',value=str(existing_action.get('CALENDRIER') or ''),height=220,placeholder='Ex. 19/09/2026 - Séance 1 - 1 h 30')

demande=st.text_area('Demande / besoin',value=str(dem.get('revalidation_entretien') or dem.get('origine_demande') or ''),height=90)
objectifs=st.text_area('Objectifs individualisés',value=str(obj.get('objectifs_personnels','')),height=90)
criteres=st.text_area('Critères de réussite',value=str(obj.get('criteres_reussite','')),height=70)
financeur_aps = str((aps or {}).get('convention_future',{}).get('financeur_envisage',''))

if aps:
    with st.expander('Voir la table de correspondance APS JSON → CONV ADM', expanded=False):
        mapping_rows=[
            {'Source APS':'beneficiaire.prenom','Rubrique CONV ADM':'PRENOM_STAGIAIRE','Valeur':prenom},
            {'Source APS':'beneficiaire.nom','Rubrique CONV ADM':'NOM_STAGIAIRE','Valeur':nom},
            {'Source APS':'beneficiaire.nom_naissance','Rubrique CONV ADM':'NOM_DE_NAISSANCE','Valeur':str(b.get('nom_naissance',''))},
            {'Source APS':'beneficiaire.date_naissance','Rubrique CONV ADM':'DATE_NAISSANCE','Valeur':str(birth)},
            {'Source APS':'beneficiaire.email','Rubrique CONV ADM':'EMAIL','Valeur':email},
            {'Source APS':'beneficiaire.adresse','Rubrique CONV ADM':'ADRESSE','Valeur':adresse},
            {'Source APS':'beneficiaire.code_postal','Rubrique CONV ADM':'CODE_POST','Valeur':cp},
            {'Source APS':'beneficiaire.ville','Rubrique CONV ADM':'VILLE','Valeur':ville},
            {'Source APS':'beneficiaire.telephone','Rubrique CONV ADM':'Pas de champ téléphone bénéficiaire dédié - non injecté en contact pour un particulier bipartite','Valeur':telephone},
            {'Source APS':'modalites.format_souhaite','Rubrique CONV ADM':'Nom_site / Adresse_du_site (à valider)','Valeur':str(mod.get('format_souhaite',''))},
            {'Source APS':'convention_future.financeur_envisage','Rubrique CONV ADM':'Pas injecté directement - utilisé pour préparer FINANCEMENTS','Valeur':financeur_aps},
        ]
        st.dataframe(mapping_rows,use_container_width=True,hide_index=True)
        st.caption('Les dates, la durée, le planning et le prix ne figurent pas dans l’APS : ils ne sont donc jamais déduits du JSON.')

st.subheader('4. Prix et financements')
c1,c2,c3=st.columns(3)
existing_ht = existing_action.get('INTRA_HT') if existing_action else None
with c1: total_ht=st.number_input('Montant total HT de l’action (INTRA_HT)',min_value=0.0,value=float(existing_ht) if isinstance(existing_ht,(int,float)) else None,step=10.0,placeholder='À renseigner')
with c2: taux_tva=st.number_input('TVA (%)',min_value=0.0,value=20.0,step=1.0)
total_ttc=(float(total_ht)*(1+taux_tva/100)) if total_ht is not None else None
with c3:
    if total_ttc is not None: st.metric('Prix total TTC',f"{total_ttc:,.2f} €".replace(',', ' ').replace('.', ','))
    else: st.metric('Prix total TTC','-')

seed=[]
if aps and 'personnel' in financeur_aps.lower():
    seed=[{'TYPE_FINANCEUR':'BENEFICIAIRE','NOM_FINANCEUR':f'{prenom} {nom}'.strip(),'MONTANT_TTC':None,'TAUX_TVA':taux_tva,'FACTURE_A_ETABLIR_A':f'{prenom} {nom} {adresse} {cp} {ville}'.strip(),'STATUT_FINANCEMENT':'Prévu','OBSERVATIONS':'Financement personnel déclaré dans l’APS'}]
fin_key=f"fin_editor::{no_clar}::{email}"
if st.session_state.get('fin_editor_key') != fin_key:
    st.session_state.fin_editor=seed
    st.session_state.fin_editor_key=fin_key
fin=st.data_editor(st.session_state.fin_editor,num_rows='dynamic',use_container_width=True,column_config={
    'TYPE_FINANCEUR':st.column_config.SelectboxColumn('Type financeur',options=['BENEFICIAIRE','ENTREPRISE','CPF','OPCO','FRANCE TRAVAIL','AUTRE FINANCEUR']),
    'MONTANT_TTC':st.column_config.NumberColumn('Montant TTC',min_value=0.0,step=10.0,format='%.2f €'),
    'TAUX_TVA':st.column_config.NumberColumn('TVA %',min_value=0.0,step=1.0,format='%.1f'),
},key='finance_editor')
fin_rows=fin.to_dict('records') if hasattr(fin,'to_dict') else list(fin)
sum_fin=sum(float(r.get('MONTANT_TTC') or 0) for r in fin_rows)
diff=round((float(total_ttc) if total_ttc is not None else 0.0)-sum_fin,2)
if total_ttc is not None and abs(diff)<0.01: st.success(f'Financement équilibré : {sum_fin:,.2f} € TTC'.replace(',', ' ').replace('.', ','))
elif total_ttc is not None: st.error(f'Écart de financement : {diff:,.2f} €'.replace(',', ' ').replace('.', ','))

modalites_paiement=st.text_area('Modalités de paiement / précisions',value='Le reste à charge du bénéficiaire est soumis aux règles de paiement applicables au contrat individuel de bilan de compétences. Les autres prises en charge sont facturées selon les accords conclus avec les financeurs concernés.',height=80)

st.subheader('5. Contrôles avant enregistrement')
if prestation=='Bilan de compétences' and contract_type=='Particulier – bipartite' and date_debut and date_debut < contract_date:
    st.markdown('<div class="clarte-warning"><b>Attention conformité :</b> la date de début de l’action est antérieure à la date du contrat. Pour un contrat conclu avec une personne physique finançant tout ou partie de la prestation à titre individuel, le contrat doit être conclu avant l’inscription définitive et tout règlement. Vérifiez la chronologie du dossier avant signature ; l’application ne rétrodate jamais un contrat.</div>',unsafe_allow_html=True)

can_generate=bool(total_ttc and total_ttc>0 and duree and nb_temps and date_debut and date_fin and calendrier.strip() and prenom and nom and email and abs(diff)<0.01)
if not can_generate: st.info('Complétez les champs obligatoires et équilibrez les financements pour générer.')

if can_generate:
    if st.button('6. Injecter dans la base chargée et générer le contrat PDF',type='primary',use_container_width=True):
        ht=round(float(total_ht),2)
        frows=calc_finance_rows(no_clar,fin_rows)
        facture='\n'.join(dict.fromkeys([str(x.get('FACTURE_A_ETABLIR_A') or x.get('NOM_FINANCEUR') or '').strip() for x in frows if float(x.get('MONTANT_TTC') or 0)>0 and str(x.get('FACTURE_A_ETABLIR_A') or x.get('NOM_FINANCEUR') or '').strip()]))
        obs=' | '.join(f"{x.get('NOM_FINANCEUR')}: {x.get('MONTANT_TTC')} € TTC" for x in frows if float(x.get('MONTANT_TTC') or 0)>0)
        values={
            'DATE_CONV':contract_date,'NOM_ENT':f'{prenom} {nom}'.strip(),'ADRESSE':adresse,'CODE_POST':cp,'VILLE':ville,
            'SPEC_BPF':'Autres','INTITULE_FORMA':'Bilan de compétences' if prestation=='Bilan de compétences' else prestation,
            'INTITULE_FORMA_COMPL':intitule_compl,'DUREE_HEURES_STAGIAIRE':duree,'REPARTITION_NB_DE_JOURS':nb_temps,
            'INTRA_HT':ht,'FACTURE_A_ETABLIR_A':facture,'OBSERVATIONS':obs,'NOM_STAGIAIRE':nom,'NOM_DE_NAISSANCE':str(b.get('nom_naissance','')),
            'PRENOM_STAGIAIRE':prenom,'SEXE_1_Homme_2_Femme':2 if str(b.get('civilite','')).lower().startswith('madame') else 1,
            'DATE_NAISSANCE':birth,'EMAIL':email,'Date_debut_action':date_debut,'Date_de_fin_d_action':date_fin,'CALENDRIER':calendrier,
            'Contact_mise_en_place_de_la_formation_Nom_et_ou_Prenom':'','Email_du_contact_de_la_formation':'',
            'No_de_telephone_du_contact_de_la_formation':'','Nom_site':modalite,'Adresse_du_site':modalite,'Horaire_du_site_debut':horaire_debut,'Horaire_du_site_fin':horaire_fin,'Nombre_de_stagiaires':1,
            'Nom_et_Prenom_du_formateur':consultant,'email_du_formateur':consultant_email,'telephone_du_formateur':consultant_tel,'NOM_STRUCTURE':'Clarté360'}
        updated=patch_conv_adm(db_bytes,rownum,values)
        updated=replace_financements_for_action(updated,no_clar,frows)
        updated=force_recalc_on_open(updated)
        assert_xlsm_integrity(db_bytes, updated)
        # Vérification supplémentaire : le classeur patché doit rester lisible avant toute écriture serveur.
        check_wb=workbook_values(updated,data_only=False); check_wb.close()
        st.session_state.updated_xlsm=updated
        st.session_state.updated_xlsm_name=db_filename
        contract_data={'beneficiaire':{'civilite':b.get('civilite',''),'prenom':prenom,'nom':nom,'date_naissance':birth,'adresse':adresse,'code_postal':cp,'ville':ville,'email':email,'telephone':telephone},
                       'action':{'no_clar':no_clar,'date_contrat':contract_date,'duree_heures':duree,'date_debut':date_debut,'date_fin':date_fin,'modalite':modalite,'calendrier':calendrier,'demande':demande,'objectifs':objectifs,'criteres_reussite':criteres,'suivi_6_mois':f'Un entretien de suivi est proposé environ six mois après la conclusion du bilan. Il est distinct des {duree:g} heures d’accompagnement contractualisées.'},
                       'prix':{'ttc':total_ttc,'ht':ht,'tva':total_ttc-ht,'modalites_paiement':modalites_paiement},'financements':frows,
                       'consultant':{'nom':consultant,'email':consultant_email,'telephone':consultant_tel}}
        if prestation=='Bilan de compétences' and contract_type=='Particulier – bipartite':
            st.session_state.pdf=build_bc_particulier_pdf(contract_data,LOGO)
            st.session_state.pdfname=f'{no_clar}_CONTRAT_BILAN_COMPETENCES_{nom}_{prenom}.pdf'.replace(' ','_')
        else:
            st.session_state.pdf=None
        st.session_state.contract_json=json.dumps(contract_data,ensure_ascii=False,default=str,indent=2).encode('utf-8')
        st.success(f'Action {no_clar} injectée dans la copie de votre base. Téléchargez la base mise à jour ci-dessous pour remplacer votre fichier local.')

if st.session_state.get('contract_json'):
    st.subheader('7. Fichiers prêts')
    st.warning('Important : le programme est sur le VPS, mais la base maître reste sur votre ordinateur. Le navigateur ne peut pas écraser automatiquement votre fichier local : téléchargez cette version mise à jour puis remplacez votre base locale après contrôle.')
    if st.session_state.get('updated_xlsm'):
        st.download_button('⬇️ Base Clarté360 mise à jour (.xlsm)',data=st.session_state.updated_xlsm,file_name=st.session_state.get('updated_xlsm_name') or 'GESTION_OF_CLARTE360.xlsm',mime='application/vnd.ms-excel.sheet.macroEnabled.12',use_container_width=True)
    st.download_button('⬇️ Dossier contractuel JSON',data=st.session_state.contract_json,file_name=f'{no_clar}_dossier_contractuel.json',mime='application/json',use_container_width=True)
    if st.session_state.get('pdf'):
        st.download_button('⬇️ Contrat PDF',data=st.session_state.pdf,file_name=st.session_state.pdfname,mime='application/pdf',use_container_width=True)
    else:
        st.warning('PDF non généré pour ce type de document dans cette version. Les données et la base mise à jour sont néanmoins prêtes.')

    if st.button('Purger les données de cette session',use_container_width=True):
        for key in ['updated_xlsm','updated_xlsm_name','contract_json','pdf','pdfname','fin_editor','fin_editor_key']:
            st.session_state.pop(key,None)
        st.success('Données de travail supprimées de la session.')
        st.rerun()

st.markdown('---')
st.caption(f"Clarté360 – Application administrative de contractualisation – V{APP_VERSION}. Les clauses juridiques sont versionnées et déterministes ; aucune IA n’est utilisée pour générer le texte juridique. Modèle BC actif : {MODEL_VERSION}.")
