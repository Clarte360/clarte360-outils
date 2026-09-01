from __future__ import annotations
import io
import pandas as pd

NULLS = {"", "0", "0.0", "nan", "NaT", "None"}
def clean(v):
    if pd.isna(v): return None
    if hasattr(v, "to_pydatetime"): v=v.to_pydatetime()
    if hasattr(v, "isoformat"): return v.isoformat()[:10] if "date" in type(v).__name__.lower() or hasattr(v,"year") else str(v)
    s=str(v).strip()
    return None if s in NULLS else s

def read_clarte360_xlsm(file_bytes: bytes, action_no: str):
    bio=io.BytesIO(file_bytes)
    conv=pd.read_excel(bio,sheet_name="CONV ADM",engine="openpyxl")
    bio.seek(0)
    stag=pd.read_excel(bio,sheet_name="STAGIAIRE",engine="openpyxl")
    action_no=action_no.strip().upper()
    c=conv[conv["NO_CLAR"].astype(str).str.upper()==action_no]
    s=stag[stag["NO_CLAR"].astype(str).str.upper()==action_no]
    row = c.iloc[0] if not c.empty else (s.iloc[0] if not s.empty else None)
    if row is None: return None, []
    data={
      "action_no": action_no,
      "title": clean(row.get("INTITULE_FORMA")) or "Action sans intitulé",
      "subtitle": clean(row.get("INTITULE_FORMA_COMPL")),
      "planned_hours": float(row.get("DUREE_HEURES_STAGIAIRE") or 0),
      "client_name": clean(row.get("NOM_ENT")),
      "trainer_name": clean(row.get("Nom_et_Prenom_du_formateur")),
      "location": clean(row.get("Nom_site")) or clean(row.get("Adresse_du_site")),
      "source": "GESTION OF CLARTE360",
      "date_start": clean(row.get("Date_debut_action")),
      "date_end": clean(row.get("Date_de_fin_d_action")),
      "default_start": clean(row.get("Horaire_du_site_debut")),
      "default_end": clean(row.get("Horaire_du_site_fin")),
    }
    participants=[]
    source_df=s if not s.empty else c
    seen=set()
    for _,r in source_df.iterrows():
        last=clean(r.get("NOM_STAGIAIRE")); first=clean(r.get("PRENOM_STAGIAIRE"))
        if not last or not first: continue
        key=(last.upper(),first.upper(),clean(r.get("DATE_NAISSANCE")))
        if key in seen: continue
        seen.add(key)
        participants.append({
          "last_name": last,
          "birth_name": clean(r.get("NOM_NAISSANCE")) or clean(r.get("NOM_DE_NAISSANCE")),
          "first_name": first,
          "birth_date": clean(r.get("DATE_NAISSANCE")),
          "email": clean(r.get("EMAIL")),
          "employee_id": clean(r.get("MATRICULE_entreprise")),
          "company_name": clean(r.get("NOM_ENT")),
          "phone": clean(r.get("No_de_telephone")),
          "individual_action_no": action_no,
        })
    return data, participants
