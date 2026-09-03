from __future__ import annotations
import io
import pandas as pd

NULLS={"","0","0.0","nan","NaT","None"}
def clean(v):
    if pd.isna(v): return None
    if hasattr(v,'to_pydatetime'): v=v.to_pydatetime()
    if hasattr(v,'isoformat'): return v.isoformat()[:10] if hasattr(v,'year') else str(v)
    s=str(v).strip(); return None if s in NULLS else s

def _read(file_bytes,key,action_no,mode='INTRA',source='GESTION'):
    bio=io.BytesIO(file_bytes); conv=pd.read_excel(bio,sheet_name='CONV ADM',engine='openpyxl'); bio.seek(0); stag=pd.read_excel(bio,sheet_name='STAGIAIRE',engine='openpyxl')
    action_no=action_no.strip().upper(); c=conv[conv[key].astype(str).str.strip().str.upper()==action_no]; s=stag[stag[key].astype(str).str.strip().str.upper()==action_no]
    if c.empty and s.empty:return None,[]
    # Règle métier : INDIVIDUEL/INTER = CONV ADM fait foi ; INTRA = STAGIAIRE fait foi. Repli uniquement si la source attendue est absente.
    mode=(mode or 'INTRA').upper(); master=c if mode in ('INDIVIDUEL','INTER') else s
    if master.empty: master=s if not s.empty else c
    row=master.iloc[0]
    data={'action_no':action_no,'title':clean(row.get('INTITULE_FORMA')) or 'Action sans intitulé','subtitle':clean(row.get('INTITULE_FORMA_COMPL')),
      'planned_hours':float(row.get('DUREE_HEURES_STAGIAIRE') or 0),'client_name':clean(row.get('NOM_ENT')),'trainer_name':clean(row.get('Nom_et_Prenom_du_formateur')) or clean(row.get('Nom_et_Prenom_du_formateur_PSIP_ATTTESTATION')),
      'location':clean(row.get('Nom_site')) or clean(row.get('Adresse_du_site')),'source':source,'date_start':clean(row.get('Date_debut_action')),'date_end':clean(row.get('Date_de_fin_d_action')),
      'default_start':clean(row.get('Horaire_du_site_debut')),'default_end':clean(row.get('Horaire_du_site_fin')),'mode':mode,'source_sheet':'CONV ADM' if master is c else 'STAGIAIRE'}
    # Participants : INTRA depuis STAGIAIRE ; INDIVIDUEL/INTER depuis CONV ADM, conformément au mapping validé. Repli contrôlé si noms absents.
    pdf=c if mode in ('INDIVIDUEL','INTER') else s
    def rows_from(df):
      out=[];seen=set()
      for _,r in df.iterrows():
        last=clean(r.get('NOM_STAGIAIRE'));first=clean(r.get('PRENOM_STAGIAIRE'))
        if not last or not first:continue
        k=(last.upper(),first.upper(),clean(r.get('DATE_NAISSANCE')))
        if k in seen:continue
        seen.add(k);out.append({'last_name':last,'birth_name':clean(r.get('NOM_NAISSANCE')) or clean(r.get('NOM_DE_NAISSANCE')),'first_name':first,'birth_date':clean(r.get('DATE_NAISSANCE')),
          'email':clean(r.get('EMAIL')),'employee_id':clean(r.get('MATRICULE_entreprise')),'company_name':clean(r.get('NOM_ENT')),'phone':clean(r.get('No_de_telephone')) or clean(r.get('TELEPHONE')),'individual_action_no':action_no})
      return out
    participants=rows_from(pdf)
    if not participants and pdf is not s: participants=rows_from(s)
    return data,participants

def read_clarte360_xlsm(file_bytes,action_no,mode='INTRA'): return _read(file_bytes,'NO_CLAR',action_no,mode,'GESTION OF CLARTE360')
def read_adca_xlsm(file_bytes,action_no,mode='INTRA'): return _read(file_bytes,'NO_ADCA',action_no,mode,'GESTION OF ADCA')

def list_action_numbers(file_bytes,source='CLARTE360'):
    key='NO_ADCA' if source.upper()=='ADCA' else 'NO_CLAR'; bio=io.BytesIO(file_bytes); conv=pd.read_excel(bio,sheet_name='CONV ADM',usecols=[key],engine='openpyxl')
    return sorted({str(x).strip().upper() for x in conv[key].dropna() if str(x).strip()})
