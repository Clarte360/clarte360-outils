import json, math, re
from datetime import date

class ValidationError(ValueError): pass
MAX_JSON_BYTES=2*1024*1024
MAX_TEXT=4000
MAX_SHORT=160
EMAIL_RE=re.compile(r'^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$')
ID_RE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$')

def clean_text(value, field='Texte', max_len=MAX_TEXT, required=False):
    s=str(value or '').strip()
    if required and not s: raise ValidationError(f'{field} est obligatoire.')
    if len(s)>max_len: raise ValidationError(f'{field} est trop long ({max_len} caractères maximum).')
    if any(ord(c)<32 and c not in '\n\t' for c in s): raise ValidationError(f'{field} contient des caractères non autorisés.')
    return s

def name(value, field='Nom', required=True):
    s=clean_text(value,field,100,required)
    if s and (any(ch.isdigit() for ch in s) or not all(ch.isalpha() or ch in " '-’" for ch in s)):
        raise ValidationError(f'{field} contient des caractères non autorisés.')
    return s

def email(value, required=True):
    s=clean_text(value,'Adresse e-mail',254,required).lower()
    if s and ('\r' in s or '\n' in s or not EMAIL_RE.fullmatch(s)): raise ValidationError("Adresse e-mail invalide.")
    return s

def phone(value, required=False):
    s=clean_text(value,'Téléphone',40,required)
    if not s: return ''
    if not re.fullmatch(r'\+?[0-9 ().-]+',s): raise ValidationError('Téléphone invalide.')
    digits=re.sub(r'\D','',s)
    if not 7<=len(digits)<=15: raise ValidationError('Téléphone invalide.')
    return s

def safe_id(value, field='Identifiant', required=True):
    s=clean_text(value,field,160,required)
    if s and (not ID_RE.fullmatch(s) or '..' in s): raise ValidationError(f'{field} invalide.')
    return s

def score(value, field='Cote'):
    if isinstance(value,bool): raise ValidationError(f'{field} invalide.')
    try: f=float(value)
    except Exception: raise ValidationError(f'{field} invalide.')
    if not math.isfinite(f) or f<0 or f>10 or int(f)!=f: raise ValidationError(f'{field} doit être un entier entre 0 et 10.')
    return int(f)

def validate_state(data):
    if not isinstance(data,dict): raise ValidationError('Le JSON doit contenir un objet.')
    if len(data)>80: raise ValidationError('Structure JSON incohérente.')
    b=data.get('beneficiaire',{})
    if not isinstance(b,dict): raise ValidationError('Bénéficiaire invalide.')
    if b.get('prenom'): name(b['prenom'],'Prénom')
    if b.get('nom'): name(b['nom'],'Nom')
    if b.get('email'): email(b['email'])
    if b.get('consultant'): clean_text(b['consultant'],'Consultant',100)
    vals=data.get('valeurs',[])
    if not isinstance(vals,list) or len(vals)>30: raise ValidationError('La liste des valeurs est invalide (30 maximum).')
    for i,v in enumerate(vals):
        if not isinstance(v,dict): raise ValidationError(f'Valeur {i+1} invalide.')
        clean_text(v.get('nom',''),f'Nom valeur {i+1}',120)
        clean_text(v.get('definition',''),f'Définition valeur {i+1}',1200)
        ds=v.get('domaines',[])
        if not isinstance(ds,list) or len(ds)>10: raise ValidationError(f'Points d’appui valeur {i+1} invalides.')
        for d in ds:
            if not isinstance(d,dict): raise ValidationError('Point d’appui invalide.')
            clean_text(d.get('periode',''),'Date/période',160)
            clean_text(d.get('exemple',''),'Exemple',2000)
            score(d.get('cote',0))
    ve=data.get('valeurs_energies',{})
    if ve and not isinstance(ve,dict): raise ValidationError('Valeurs énergies invalides.')
    if isinstance(ve,dict):
        sel=ve.get('selected',[])
        if not isinstance(sel,list) or len(sel)>3: raise ValidationError('Trois valeurs énergie maximum.')
        for x in sel:
            if not isinstance(x,int) or x<0 or x>=len(vals): raise ValidationError('Sélection de valeur énergie invalide.')
        entries=ve.get('entries',{})
        if not isinstance(entries,dict): raise ValidationError('Données valeurs énergies invalides.')
        for e in entries.values():
            if not isinstance(e,dict): raise ValidationError('Donnée valeur énergie invalide.')
            score(e.get('score_revise',0),'Cotation revisitée')
            clean_text(e.get('commentaire',''),'Commentaire énergie',2000)
            for key in ('actions','maintien'):
                arr=e.get(key,[])
                if not isinstance(arr,list) or len(arr)>5: raise ValidationError('Liste actions/points d’appui invalide.')
                for t in arr: clean_text(t,'Action/point d’appui',500)
    return data

def decode_json_bytes(raw):
    if not isinstance(raw,(bytes,bytearray)): raise ValidationError('Fichier JSON invalide.')
    if len(raw)>MAX_JSON_BYTES: raise ValidationError('Fichier JSON trop volumineux (2 Mo maximum).')
    try: data=json.loads(bytes(raw).decode('utf-8'))
    except (UnicodeDecodeError,json.JSONDecodeError): raise ValidationError('Le fichier doit être un JSON UTF-8 valide.')
    return validate_state(data)
