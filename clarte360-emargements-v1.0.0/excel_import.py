from __future__ import annotations
import io, json, re
from datetime import date, datetime, timedelta
import pandas as pd

NULLS={"","0","0.0","nan","NaT","None"}

DEFAULT_MAPPING = {
    'title':['INTITULE_FORMA'],
    'subtitle':['INTITULE_FORMA_COMPL'],
    'planned_hours':['DUREE_HEURES_STAGIAIRE'],
    'client_name':['NOM_ENT'],
    'trainer_name':['Nom_et_Prenom_du_formateur','Nom_et_Prenom_du_formateur_PSIP_ATTTESTATION'],
    'location':['Nom_site','Adresse_du_site'],
    'date_start':['Date_debut_action'],
    'date_end':['Date_de_fin_d_action'],
    'default_start':['Horaire_du_site_debut'],
    'default_end':['Horaire_du_site_fin'],
    'quality_contact_name':['Responsable_d_agence_Qualite_Nom_et_ou_Prenom'],
    'client_quality_email':['Email_du_Responsable_Agence_Qualite'],
    'training_contact_name':['Contact_mise_en_place_de_la_formation_Nom_et_ou_Prenom'],
    'client_training_email':['Email_du_contact_de_la_formation'],
    'training_contact_phone':['No_de_telephone_du_contact_de_la_formation'],
    'participant_last_name':['NOM_STAGIAIRE'],
    'participant_birth_name':['NOM_NAISSANCE','NOM_DE_NAISSANCE'],
    'participant_first_name':['PRENOM_STAGIAIRE'],
    'participant_birth_date':['DATE_NAISSANCE'],
    'participant_email':['EMAIL'],
    'participant_employee_id':['MATRICULE_entreprise'],
    'participant_company':['NOM_ENT'],
    'participant_phone':['No_de_telephone','TELEPHONE'],
}

def clean(v):
    if pd.isna(v): return None
    if hasattr(v,'to_pydatetime'): v=v.to_pydatetime()
    if hasattr(v,'isoformat'): return v.isoformat()[:10] if hasattr(v,'year') else str(v)
    s=str(v).strip(); return None if s in NULLS else s


def normalize_date_value(v, *, field_name='date'):
    """Normalize unambiguous Excel/Python/text dates to ISO. Returns (iso, source_repr, converted)."""
    if v is None or (isinstance(v,float) and pd.isna(v)):
        return None,None,False
    original=v
    if isinstance(v,pd.Timestamp): v=v.to_pydatetime()
    if isinstance(v,datetime): return v.date().isoformat(),str(original),False
    if isinstance(v,date): return v.isoformat(),str(original),False
    if isinstance(v,(int,float)) and not isinstance(v,bool):
        n=float(v)
        if n.is_integer() and 1 <= n <= 80000:
            d=(datetime(1899,12,30)+timedelta(days=int(n))).date()
            return d.isoformat(),str(original),True
        raise ValueError(f"{field_name} numérique impossible : {original}")
    raw=str(v).strip()
    if not raw or raw in NULLS:return None,raw,False
    if re.fullmatch(r'\d+(?:\.0+)?',raw):
        return normalize_date_value(float(raw),field_name=field_name)
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y'):
        try:return datetime.strptime(raw,fmt).date().isoformat(),raw,(fmt!='%Y-%m-%d')
        except ValueError:pass
    raise ValueError(f"{field_name} ambiguë ou invalide : {raw}")

def _raw_value(row,mapping,key):
    for col in mapping.get(key,[]):
        if col in row.index:
            val=row.get(col)
            if val is not None and not (isinstance(val,float) and pd.isna(val)):
                return val
    return None

def _mapping(profile):
    raw=(profile or {}).get('mapping_json')
    if isinstance(raw,str) and raw.strip():
        try: raw=json.loads(raw)
        except Exception: raw={}
    if not isinstance(raw,dict): raw={}
    out={k:list(v) for k,v in DEFAULT_MAPPING.items()}
    for k,v in raw.items():
        if v is None: continue
        out[k]=v if isinstance(v,list) else [v]
    return out

def _value(row, mapping, key):
    for col in mapping.get(key,[]):
        if col in row.index:
            val=clean(row.get(col))
            if val is not None: return val
    return None

def _hours(v):
    try: return float(v or 0)
    except Exception: return 0.0

def read_action_xlsm(file_bytes, action_no, profile, mode='INTRA'):
    """Generic workbook reader driven by an organization import profile."""
    profile=profile or {}
    action_key=(profile.get('action_key') or '').strip()
    if not action_key: raise ValueError("Le profil d'import ne définit pas de colonne clé d'action.")
    action_sheet=profile.get('action_sheet') or 'CONV ADM'
    participant_sheet=profile.get('participant_sheet') or 'STAGIAIRE'
    mapping=_mapping(profile)
    bio=io.BytesIO(file_bytes)
    conv=pd.read_excel(bio,sheet_name=action_sheet,engine='openpyxl')
    bio.seek(0)
    stag=pd.read_excel(bio,sheet_name=participant_sheet,engine='openpyxl')
    for sheet_name,df in ((action_sheet,conv),(participant_sheet,stag)):
        if action_key not in df.columns:
            raise ValueError(f"Colonne clé '{action_key}' absente de l'onglet {sheet_name}.")
    action_no=(action_no or '').strip().upper()
    c=conv[conv[action_key].astype(str).str.strip().str.upper()==action_no]
    s=stag[stag[action_key].astype(str).str.strip().str.upper()==action_no]
    if c.empty and s.empty:return None,[]
    mode=(mode or 'INTRA').upper()
    master=c if mode in ('INDIVIDUEL','INTER') else s
    if master.empty: master=s if not s.empty else c
    row=master.iloc[0]
    data={
      'action_no':action_no,
      'title':_value(row,mapping,'title') or 'Action sans intitulé',
      'subtitle':_value(row,mapping,'subtitle'),
      'planned_hours':_hours(_value(row,mapping,'planned_hours')),
      'client_name':_value(row,mapping,'client_name'),
      'trainer_name':_value(row,mapping,'trainer_name'),
      'location':_value(row,mapping,'location'),
      'source':profile.get('name') or profile.get('code') or 'BASE DE GESTION',
      'import_profile_id':profile.get('id'),
      'organization_id':profile.get('organization_id'),
      'date_start':normalize_date_value(_raw_value(row,mapping,'date_start'),field_name='Date de début')[0] if _raw_value(row,mapping,'date_start') is not None else None,
      'date_end':normalize_date_value(_raw_value(row,mapping,'date_end'),field_name='Date de fin')[0] if _raw_value(row,mapping,'date_end') is not None else None,
      'default_start':_value(row,mapping,'default_start'),
      'default_end':_value(row,mapping,'default_end'),
      'mode':mode,
      'source_sheet':action_sheet if master is c else participant_sheet,
      'quality_contact_name':_value(row,mapping,'quality_contact_name'),
      'client_quality_email':_value(row,mapping,'client_quality_email'),
      'training_contact_name':_value(row,mapping,'training_contact_name'),
      'client_training_email':_value(row,mapping,'client_training_email'),
      'training_contact_phone':_value(row,mapping,'training_contact_phone'),
    }
    pdf=c if mode in ('INDIVIDUEL','INTER') else s
    def rows_from(df):
      out=[];seen=set()
      for _,r in df.iterrows():
        last=_value(r,mapping,'participant_last_name');first=_value(r,mapping,'participant_first_name')
        if not last or not first:continue
        raw_birth=_raw_value(r,mapping,'participant_birth_date')
        birth,birth_source,birth_converted=normalize_date_value(raw_birth,field_name='Date de naissance') if raw_birth is not None else (None,None,False)
        k=(last.upper(),first.upper(),birth)
        if k in seen:continue
        seen.add(k);out.append({
          'last_name':last,'birth_name':_value(r,mapping,'participant_birth_name'),'first_name':first,'birth_date':birth,
          '_birth_date_source':birth_source if birth_converted else None,
          'email':_value(r,mapping,'participant_email'),'employee_id':_value(r,mapping,'participant_employee_id'),
          'company_name':_value(r,mapping,'participant_company'),'phone':_value(r,mapping,'participant_phone'),'individual_action_no':action_no})
      return out
    participants=rows_from(pdf)
    if not participants and pdf is not s: participants=rows_from(s)
    return data,participants

def list_action_numbers_for_profile(file_bytes, profile):
    key=(profile or {}).get('action_key')
    sheet=(profile or {}).get('action_sheet') or 'CONV ADM'
    if not key: return []
    bio=io.BytesIO(file_bytes); df=pd.read_excel(bio,sheet_name=sheet,usecols=[key],engine='openpyxl')
    return sorted({str(x).strip().upper() for x in df[key].dropna() if str(x).strip()})

# Backward-compatible wrappers retained for existing tests and historical imports.
def read_clarte360_xlsm(file_bytes,action_no,mode='INTRA'):
    return read_action_xlsm(file_bytes,action_no,{'action_key':'NO_CLAR','action_sheet':'CONV ADM','participant_sheet':'STAGIAIRE','name':'GESTION OF CLARTE360'},mode)
def read_adca_xlsm(file_bytes,action_no,mode='INTRA'):
    return read_action_xlsm(file_bytes,action_no,{'action_key':'NO_ADCA','action_sheet':'CONV ADM','participant_sheet':'STAGIAIRE','name':'GESTION OF ADCA'},mode)
def list_action_numbers(file_bytes,source='CLARTE360'):
    key='NO_ADCA' if str(source).upper()=='ADCA' else 'NO_CLAR'
    return list_action_numbers_for_profile(file_bytes,{'action_key':key,'action_sheet':'CONV ADM'})
