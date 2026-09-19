from __future__ import annotations
from io import BytesIO
from pathlib import Path
import json, math
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.graphics.shapes import Drawing, Polygon, Line, String, Circle
from clarte360_pip.interpretation import interpret_pip, load_rules, INTERPRETATION_VERSION
from clarte360_pip.connectors.rome import RomePort, two_letter_profile, ROME_REFERENCE_VERSION

PIP_REPORT_VERSION='PIP-RPT-1.6'; ONET_REPORT_VERSION='ONET-RPT-1.1'; REPORT_VERSION=PIP_REPORT_VERSION
RIASEC='RIASEC'; TEAL=colors.HexColor('#008080'); LIGHT=colors.HexColor('#E6F4F4'); DARK=colors.HexColor('#243A3A'); GREY=colors.HexColor('#657575')
_INTERP_RULES=load_rules()
LABELS=dict(_INTERP_RULES['labels'])
DESC=dict(_INTERP_RULES['descriptions'])
ROOT=Path(__file__).resolve().parents[1]

def _fonts():
 reg='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
 try: pdfmetrics.registerFont(TTFont('C360',reg)); pdfmetrics.registerFont(TTFont('C360B',bold)); return 'C360','C360B'
 except Exception: return 'Helvetica','Helvetica-Bold'

def _styles():
 reg,bold=_fonts(); ss=getSampleStyleSheet(); body=ParagraphStyle('b1',parent=ss['BodyText'],fontName=reg,fontSize=9.1,leading=13,textColor=DARK,spaceAfter=6); h1=ParagraphStyle('h11',parent=body,fontName=bold,fontSize=18,leading=22,textColor=TEAL,spaceAfter=8); h2=ParagraphStyle('h21',parent=body,fontName=bold,fontSize=12.5,leading=16,textColor=TEAL,spaceBefore=7,spaceAfter=5); h3=ParagraphStyle('h31',parent=body,fontName=bold,fontSize=10,leading=13,textColor=DARK,spaceBefore=4,spaceAfter=3); small=ParagraphStyle('s1',parent=body,fontSize=7.5,leading=10,textColor=GREY); return reg,bold,body,h1,h2,h3,small

def _footer(c,d,title):
 c.saveState(); c.setStrokeColor(LIGHT); c.line(18*mm,14*mm,192*mm,14*mm); c.setFont('Helvetica',7.2); c.setFillColor(GREY); c.drawString(18*mm,9*mm,title); c.drawRightString(192*mm,9*mm,f'Page {d.page}'); c.restoreState()

def _who(s):
 l=s.get('launch_context'); mode=getattr(getattr(l,'mode',None),'value','')
 if l and 'ACCOMP' in str(mode).upper(): return getattr(l,'beneficiary_display_name','') or ''
 i=s.get('public_identity') or {}; return ' '.join(x for x in [i.get('first_name',''),i.get('last_name','')] if x)

def _start(story,logo,title,subtitle,body,h1):
 p=Path(logo) if logo else None
 if p and p.exists(): story.extend([Image(str(p),22*mm,22*mm),Spacer(1,3*mm)])
 story.extend([Paragraph(title,h1),Paragraph(subtitle,ParagraphStyle('sub'+title[:2],parent=h1,fontSize=14,leading=18,textColor=DARK))])

def _radar(vals,reg,bold,maxv=100):
 w,h=155*mm,108*mm; d=Drawing(w,h); cx,cy=w/2,h/2; r=40*mm; base=[]
 for i,k in enumerate(RIASEC): a=math.radians(90-i*60); base.append((cx+r*math.cos(a),cy+r*math.sin(a)))
 for level in (.25,.5,.75,1):
  q=[]
  for x,y in base:q += [cx+(x-cx)*level,cy+(y-cy)*level]
  d.add(Polygon(q,strokeColor=colors.HexColor('#C9DADA'),fillColor=None,strokeWidth=.6))
 for x,y in base:d.add(Line(cx,cy,x,y,strokeColor=colors.HexColor('#D6E3E3'),strokeWidth=.5))
 q=[]
 for i,k in enumerate(RIASEC):
  a=math.radians(90-i*60); v=max(0,min(maxv,float(vals.get(k,0))))/maxv; x=cx+r*v*math.cos(a); y=cy+r*v*math.sin(a); q += [x,y]; d.add(Circle(x,y,1.2*mm,fillColor=TEAL,strokeColor=TEAL))
 d.add(Polygon(q,strokeColor=TEAL,fillColor=colors.Color(0,.5,.5,alpha=.12),strokeWidth=1.5))
 for i,k in enumerate(RIASEC): a=math.radians(90-i*60); d.add(String(cx+(r+8*mm)*math.cos(a),cy+(r+6*mm)*math.sin(a),f'{k} {float(vals.get(k,0)):.0f}',fontName=bold,fontSize=8,fillColor=DARK,textAnchor='middle'))
 return d

def _table(order,vals,reg,bold,small,suffix=' / 100'):
 rows=[[Paragraph('<b>Rang</b>',small),Paragraph('<b>Dimension</b>',small),Paragraph('<b>Score</b>',small)]]+[[str(i),f'{d} - {LABELS[d]}',f'{float(vals[d]):.0f}{suffix}'] for i,d in enumerate(order,1)]
 t=Table(rows,colWidths=[18*mm,105*mm,40*mm],repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),TEAL),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),bold),('FONTNAME',(0,1),(-1,-1),reg),('FONTSIZE',(0,0),(-1,-1),8.4),('ALIGN',(0,0),(0,-1),'CENTER'),('ALIGN',(-1,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#D7E7E7')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)])); return t
def _facets(session):
 meta=json.loads((ROOT/'resources/runtime/pip_facets_PIP-BANK-0.5.json').read_text(encoding='utf-8'))['facets']; bank=json.loads((ROOT/'resources/runtime/pip_bank_PIP-BANK-0.5.json').read_text(encoding='utf-8')); ans=(session.get('pip_state') or {}).get('answers') or {}; vals={}
 for it in bank['items']:
  v=ans.get(it['item_id']);
  if v in (1,2,3,4,5): vals.setdefault(it['facette'],[]).append(v)
 scores={f:(25*(sum(v)/len(v)-1),len(v)) for f,v in vals.items()}; return meta,scores

def facet_indicators(session):
    _, scores=_facets(session)
    return {k:{'index':v[0],'n':v[1]} for k,v in scores.items()}

def _build_pip_accompaniment_report_pdf(session,logo_path=None):
 sc=dict(session.get('pip_scoring') or {})
 if not sc.get('complete'): raise ValueError('Une passation PIP complète est nécessaire.')
 reg,bold,body,h1,h2,h3,small=_styles(); buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=16*mm,bottomMargin=20*mm,title='Rapport PIP RIASEC Clarté360',author='Clarté360'); story=[]; _start(story,logo_path,'PROFIL D’INTÉRÊTS PROFESSIONNELS','PIP RIASEC Clarté360',body,h1); who=_who(session)
 if who:story.append(Paragraph(f'<b>Bénéficiaire :</b> {who}',body))
 story += [Paragraph("<b>Votre profil RIASEC n'est pas une étiquette.</b> C'est une carte de vos centres d'intérêt professionnels à partir de vos réponses aux activités proposées.",body),Paragraph("Ce rapport explique le modèle, vos résultats, leurs nuances et leurs limites. En accompagnement, il constitue un support de dialogue ; il ne remplace pas l'analyse de vos compétences, valeurs, expériences, contraintes et projets.",body),PageBreak(),Paragraph('1. Comprendre le RIASEC et le PIP Clarté360',h1),Paragraph("Le modèle RIASEC, issu des travaux de John Holland, organise les intérêts professionnels en six grandes familles : Réaliste, Investigateur, Artistique, Social, Entreprenant et Conventionnel. Ces dimensions ne sont pas des cases exclusives : une même personne peut être attirée par plusieurs familles d'activités.",body),Paragraph("<b>Ce que mesure le PIP :</b> votre degré d'attirance déclaré pour des activités professionnelles - autrement dit : « dans mon travail, dans quelle mesure aimerais-je réaliser ce type d'activité ? »",body),Paragraph("<b>Ce qu'il ne mesure pas :</b> vos compétences, votre intelligence, votre niveau scolaire, votre personnalité globale, votre performance future ou votre aptitude à exercer un métier. Un intérêt élevé ne prouve pas une compétence ; un intérêt faible ne prouve pas une incapacité.",body),Paragraph("<b>À quoi sert-il ?</b> À mieux nommer ce qui vous attire, repérer des dominantes et des nuances, alimenter l'exploration professionnelle et préparer des hypothèses à confronter avec votre parcours. Il ne décide pas à votre place et ne recommande pas automatiquement un métier.",body),Paragraph('Les six dimensions',h2)]
 for d in RIASEC: story += [Paragraph(f'{d} - {LABELS[d]}',h3),Paragraph(DESC[d],body)]
 order=list(sc.get('order') or []); indices=sc.get('indices') or {}; story += [PageBreak(),Paragraph('2. Votre profil global',h1),Paragraph("L'hexagone RIASEC place les six dimensions dans l'ordre R-I-A-S-E-C. Le tracé intérieur montre la forme générale de votre profil ; le tableau donne les valeurs exactes.",body),_radar(indices,reg,bold),_table(order,indices,reg,bold,small)]
 code=sc.get('holland_code')
 if code:story += [Paragraph(f'Code de synthèse Holland : {code}',h2),Paragraph('Il résume vos trois dimensions les plus élevées lorsque leur ordre est suffisamment distinct. Il ne constitue ni un diagnostic ni une prescription de métier.',body)]
 else:story += [Paragraph('Code de synthèse Holland',h2),Paragraph("Aucun code à trois lettres n'est forcé lorsque des égalités ou une proximité de scores rendent l'ordre insuffisamment net.",body)]
 interp=interpret_pip(indices,order)
 story += [PageBreak(),Paragraph('3. Interpréter le niveau et le relief de votre profil',h1),Paragraph("Un score PIP doit être lu de deux façons à la fois : <b>son niveau sur l’échelle 0–100</b> et <b>sa position par rapport à vos cinq autres dimensions</b>. Ainsi, une première dimension à 31/100 n’a pas le même sens qu’une première dimension à 93/100. De même, 93/100 suivi de 87/100 décrit deux pôles proches, alors que 93/100 suivi de 52/100 fait apparaître une première dimension beaucoup plus détachée.",body),Paragraph("Les qualificatifs de niveau utilisés ci-dessous sont des <b>repères descriptifs Clarté360</b> directement ancrés dans l’échelle de réponse du PIP ; ce ne sont pas des normes de population, des diagnostics ou des seuils d’aptitude.",body),Paragraph(interp['headline'],h2),Paragraph(interp['summary'],body),Paragraph(f"<b>Relief du profil : {interp['shape']['relief']}.</b> {interp['shape']['relief_text']}",body),Paragraph(interp['shape']['top_text'],body),Paragraph('Lecture détaillée des six dimensions',h2)]
 for n,d in enumerate(order,1):
  band=interp['bands'][d]; relation='parmi vos intérêts les plus présents' if n<=2 else ('dans une zone intermédiaire de votre profil' if n<=4 else 'relativement moins présente dans vos réponses'); story += [Paragraph(f'{n}. {d} - {LABELS[d]} : {float(indices[d]):.0f}/100 — {band["label"]}',h2),Paragraph(DESC[d],body),Paragraph(f"À ce niveau, {band['text']}. Dans votre classement personnel, cette dimension se situe <b>{relation}</b>. Le niveau et le rang décrivent un intérêt déclaré ; ils ne mesurent ni compétence, ni aptitude, ni performance future.",body)]
 meta,fs=_facets(session); story += [PageBreak(),Paragraph('4. Vos 30 facettes Clarté360',h1),Paragraph("Les six dimensions donnent la structure générale du profil. Les facettes proposent une lecture plus fine des formes d'activités qui composent chaque dimension.",body),Paragraph("<b>Précaution :</b> chaque facette repose ici sur 2 ou 3 items. Son indice est un <b>indicateur descriptif</b>, et non une échelle psychométrique autonome. Il sert à préparer le dialogue et à formuler des hypothèses à confronter avec votre expérience.",body)]
 for d in RIASEC:
  ms=[m for m in meta if m['dimension']==d]; rows=[[Paragraph('<b>Facette</b>',small),Paragraph('<b>Ce qu’elle explore</b>',small),Paragraph('<b>Indicateur</b>',small)]]; ranked=[]
  for m in ms:
   x=fs.get(m['facette_id']); ranked.append((x[0],m) if x else (-1,m)); rows.append([Paragraph(f"{m['facette_id']} - {m['facette_nom']}",small),Paragraph(str(m['description_facette']),small),Paragraph('—' if not x else f'{x[0]:.0f}/100<br/>({x[1]} items)',small)])
  t=Table(rows,colWidths=[51*mm,82*mm,30*mm],repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('FONTNAME',(0,0),(-1,0),bold),('FONTNAME',(0,1),(-1,-1),reg),('FONTSIZE',(0,0),(-1,-1),7.3),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(-1,1),(-1,-1),'CENTER'),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#D4E1E1')),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)])); story += [Paragraph(f'{d} - {LABELS[d]} : nuances internes',h2),t]
  rr=sorted([x for x in ranked if x[0]>=0],key=lambda x:-x[0]);
  if rr:story.append(Paragraph(f"Dans cette dimension, l'indicateur le plus élevé concerne <b>{rr[0][1]['facette_nom']}</b> ({rr[0][0]:.0f}/100) et le plus bas <b>{rr[-1][1]['facette_nom']}</b> ({rr[-1][0]:.0f}/100). Cet écart décrit une nuance d'intérêt, pas une compétence ou une incapacité.",small))
 profile2=two_letter_profile(indices,order)
 rome=RomePort()
 story += [PageBreak(),Paragraph('5. Pistes de métiers à explorer',h1),Paragraph("Cette section rapproche votre profil d’intérêts du référentiel ROME/RIASEC Clarté360. Elle ne produit <b>aucune recommandation de métier</b> et ne mesure ni vos compétences, ni vos qualifications, ni vos contraintes, ni les conditions d’accès aux professions. Elle propose seulement quelques fiches ROME à examiner comme supports d’exploration.",body)]
 if profile2:
  matches=rome.matching_profiles(profile2); pistes=rome.explore_equivalent_profiles(profile2,limit=6)
  story += [Paragraph(f'<b>Profil RIASEC à deux lettres utilisé : {profile2}</b>',h2),Paragraph(f"Les deux premières dimensions de votre profil peuvent être ordonnées sans égalité exacte aux positions nécessaires, ce qui permet une recherche exploratoire sur le profil <b>{profile2}</b>. Le référentiel contient {len(matches)} fiches ROME portant exactement ce profil normalisé. Pour garder le rapport lisible, six fiches au maximum sont présentées ci-dessous, en diversifiant autant que possible les grandes familles de codes ROME. Il ne s’agit pas d’un classement de compatibilité.",body)]
  if pistes:
   rows=[[Paragraph('<b>Code ROME</b>',small),Paragraph('<b>Intitulé de la fiche métier</b>',small),Paragraph('<b>Profil</b>',small)]]
   for r in pistes:
    rows.append([Paragraph(str(r['rome_code']),small),Paragraph(str(r['title']).title(),small),Paragraph(str(r['riasec_profile']),small)])
   t=Table(rows,colWidths=[30*mm,110*mm,23*mm],repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),TEAL),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),bold),('FONTNAME',(0,1),(-1,-1),reg),('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(0,-1),'CENTER'),('ALIGN',(-1,0),(-1,-1),'CENTER'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#D7E7E7')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])); story += [t,Paragraph("<b>Comment les utiliser ?</b> Prenez ces métiers comme des points de départ : qu’est-ce qui vous attire ou vous repousse dans leurs activités réelles ? Quelles compétences seraient nécessaires ? Quelles conditions de travail, valeurs, contraintes de vie, qualifications et perspectives d’emploi faut-il vérifier ? D’autres métiers, absents de cette courte liste, peuvent tout autant correspondre à vos intérêts.",body)]
  else:
   story += [Paragraph("Aucune fiche ROME correspondant exactement à ce profil à deux lettres n’a été trouvée dans le référentiel utilisé. Aucune substitution automatique n’est faite.",body)]
 else:
  story += [Paragraph("Votre classement présente une égalité exacte à une position nécessaire pour construire un profil RIASEC stable à deux lettres. Clarté360 ne force donc pas de rapprochement automatique avec des métiers. Cette absence de liste est volontaire : elle évite de transformer une ambiguïté de score en orientation artificielle.",body)]
 story += [Paragraph(f"<b>Référentiel utilisé :</b> {ROME_REFERENCE_VERSION} - données ROME datées {rome.source_date or 'juin 2026'}.",small)]
 feel=session.get('feeling') or {}
 if feel:
  story += [PageBreak(),Paragraph('6. Votre ressenti',h1),Paragraph("Votre ressenti est séparé du calcul : il permet d'identifier ce qui vous ressemble, vous surprend ou mérite d'être approfondi.",body)]; ans=feel.get('answers') or {}; qs=feel.get('questions') or {}
  for k in ('global','dominants','nuances','useful','over','under'):
   if k in ans and k in qs:story += [Paragraph(str(qs[k].get('text','')),small),Paragraph(f'<b>{ans[k]}</b>',body)]
 story += [PageBreak(),Paragraph('7. Utiliser ce rapport dans votre accompagnement',h1),Paragraph("En bilan de compétences, ce profil prend son sens lorsqu'il est confronté à votre histoire professionnelle : activités qui vous donnent de l'énergie, tâches que vous évitez, environnements qui vous mobilisent, expériences satisfaisantes ou insatisfaisantes.",body),Paragraph("Les dimensions, les facettes et les pistes ROME servent à poser des questions : où retrouve-t-on déjà ces intérêts dans votre parcours ? Lesquels sont insuffisamment nourris ? Quelles compétences possédez-vous ou devriez-vous développer ? Quelles valeurs, contraintes de vie, conditions d’accès et réalités du marché faut-il intégrer avant toute hypothèse de projet ?",body),Paragraph("Les métiers présentés dans ce rapport sont des <b>pistes d’exploration</b>. Ils ne deviennent pertinents qu’après confrontation avec vos autres dimensions Clarté360 : valeurs professionnelles, moteurs, préférences, compétences, projets, contraintes et équilibre de vie.",body)]
 mode=str(getattr(getattr(session.get('launch_context'),'mode',None),'value','')).upper()
 if 'ACCOMP' in mode:
  story.append(Paragraph("<b>Ce document constitue une étape de votre processus d’accompagnement Clarté360.</b> Ses résultats sont destinés à être mis en perspective avec les autres éléments travaillés au cours de votre accompagnement. Le profil RIASEC constitue une orientation des intérêts professionnels et ne détermine pas, à lui seul, un choix de métier.",body))
 else:
  story.append(Paragraph("<b>En accès PUBLIC :</b> ce rapport est un support d’exploration. Il ne constitue ni un diagnostic, ni une prescription d’orientation, ni une validation de compétences.",body))
 story.append(Paragraph(f'Version : {PIP_REPORT_VERSION} - Interprétation : {INTERPRETATION_VERSION} - Banque : PIP-BANK-0.5 - Scoring : {sc.get("algorithm_version","")} - ROME : {ROME_REFERENCE_VERSION}',small))
 doc.build(story,onFirstPage=lambda c,d:_footer(c,d,'Clarté360 - Rapport PIP RIASEC'),onLaterPages=lambda c,d:_footer(c,d,'Clarté360 - Rapport PIP RIASEC')); return buf.getvalue()

def _build_pip_public_report_pdf(session,logo_path=None):
 sc=dict(session.get('pip_scoring') or {})
 if not sc.get('complete'): raise ValueError('Une passation PIP complète est nécessaire.')
 reg,bold,body,h1,h2,h3,small=_styles(); buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=16*mm,bottomMargin=20*mm,title='Rapport PIP RIASEC Clarté360 - Public',author='Clarté360'); story=[]
 _start(story,logo_path,'PROFIL D’INTÉRÊTS PROFESSIONNELS','PIP RIASEC Clarté360 - Synthèse personnelle',body,h1); who=_who(session)
 if who: story.append(Paragraph(f'<b>Bénéficiaire :</b> {who}',body))
 story += [Paragraph("<b>Votre profil RIASEC n'est pas une étiquette.</b> Il propose une lecture de vos centres d'intérêt professionnels à partir des activités que vous avez déclaré aimer plus ou moins réaliser.",body),Paragraph("Cette synthèse PUBLIC vous présente l'essentiel : votre profil global, ce qu'il met en évidence et quelques pistes à explorer. Elle ne mesure ni vos compétences ni vos aptitudes et ne prescrit pas un métier.",body),Spacer(1,5*mm),Paragraph("<b>À retenir</b>",h2),Paragraph("Un intérêt professionnel indique ce qui vous attire dans le travail. Il gagne à être confronté à votre expérience, vos compétences, vos valeurs, vos contraintes et vos projets.",body)]
 story += [PageBreak(),Paragraph('1. Comprendre vos résultats',h1),Paragraph("Le modèle RIASEC, issu des travaux de John Holland, regroupe les intérêts professionnels en six familles. Plusieurs dimensions peuvent être présentes simultanément : le profil décrit une combinaison d'attirances, pas une case unique.",body),Paragraph("<b>Le PIP mesure :</b> votre degré d'attirance déclaré pour des activités professionnelles. <b>Il ne mesure pas :</b> vos compétences, votre intelligence, votre personnalité globale, votre performance future ou votre aptitude à exercer un métier.",body)]
 for d in RIASEC: story += [Paragraph(f'{d} - {LABELS[d]}',h3),Paragraph(DESC[d],body)]
 order=list(sc.get('order') or []); indices=sc.get('indices') or {}
 story += [PageBreak(),Paragraph('2. Votre profil global',h1),Paragraph("L'hexagone RIASEC montre la forme générale de votre profil. Le tableau donne les six scores exacts et leur ordre dans vos réponses.",body),_radar(indices,reg,bold),_table(order,indices,reg,bold,small)]
 code=sc.get('holland_code')
 if code: story += [Paragraph(f'Code de synthèse Holland : {code}',h2),Paragraph("Il reprend vos trois dimensions les plus élevées lorsque leur ordre est suffisamment distinct. Il ne constitue ni un diagnostic ni une prescription de métier.",body)]
 else: story += [Paragraph('Code de synthèse Holland',h2),Paragraph("Aucun code à trois lettres n'est forcé lorsque l'ordre des scores est insuffisamment net.",body)]
 interp=interpret_pip(indices,order); meta,fs=_facets(session)
 ranked_facets=[]
 for m in meta:
  x=fs.get(m['facette_id'])
  if x: ranked_facets.append((x[0],m,x[1]))
 # Select the six facets that stand out most from the neutral midpoint 50, while keeping this explicitly descriptive.
 ranked_facets=sorted(ranked_facets,key=lambda z:(-abs(z[0]-50),z[1]['facette_id']))[:6]
 story += [PageBreak(),Paragraph('3. Ce que votre profil met en évidence',h1),Paragraph(interp['headline'],h2),Paragraph(interp['summary'],body),Paragraph(f"<b>Relief du profil : {interp['shape']['relief']}.</b> {interp['shape']['relief_text']}",body),Paragraph(interp['shape']['top_text'],body),Paragraph('Vos dimensions les plus présentes',h2)]
 for n,d in enumerate(order[:3],1):
  band=interp['bands'][d]; story += [Paragraph(f'{n}. {d} - {LABELS[d]} : {float(indices[d]):.0f}/100 - {band["label"]}',h3),Paragraph(DESC[d],body)]
 story += [Paragraph('Quelques facettes qui nuancent votre profil',h2),Paragraph("Les facettes ci-dessous sont celles qui se distinguent le plus dans vos réponses. Chaque facette repose sur 2 ou 3 items : il s'agit d'indicateurs descriptifs, pas d'échelles psychométriques autonomes.",body)]
 rows=[[Paragraph('<b>Facette</b>',small),Paragraph('<b>Indicateur</b>',small)]]
 for score,m,nitems in ranked_facets: rows.append([Paragraph(f"{m['facette_id']} - {m['facette_nom']}",small),Paragraph(f'{score:.0f}/100 ({nitems} items)',small)])
 t=Table(rows,colWidths=[125*mm,38*mm],repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('FONTNAME',(0,0),(-1,0),bold),('FONTNAME',(0,1),(-1,-1),reg),('FONTSIZE',(0,0),(-1,-1),7.5),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(-1,1),(-1,-1),'CENTER'),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#D4E1E1')),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)])); story.append(t)
 profile2=two_letter_profile(indices,order); rome=RomePort()
 story += [PageBreak(),Paragraph('4. Quelques pistes à explorer',h1),Paragraph("Ces pistes rapprochent votre profil d'intérêts du référentiel ROME/RIASEC Clarté360. Elles ne constituent <b>ni des métiers recommandés, ni un classement de compatibilité</b>. Elles servent uniquement de points de départ pour votre exploration.",body)]
 if profile2:
  matches=rome.matching_profiles(profile2); pistes=rome.explore_equivalent_profiles(profile2,limit=4)
  story += [Paragraph(f'Profil RIASEC à deux lettres utilisé : {profile2}',h2),Paragraph(f"Le référentiel contient {len(matches)} fiches ROME portant ce profil. Quatre exemples au maximum sont présentés afin de garder une synthèse courte et diversifiée.",body)]
  if pistes:
   rows=[[Paragraph('<b>Code ROME</b>',small),Paragraph('<b>Intitulé de la fiche métier</b>',small)]]
   for r in pistes: rows.append([Paragraph(str(r['rome_code']),small),Paragraph(str(r['title']).title(),small)])
   t=Table(rows,colWidths=[32*mm,131*mm],repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),TEAL),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),bold),('FONTNAME',(0,1),(-1,-1),reg),('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(0,-1),'CENTER'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#D7E7E7')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])); story += [t]
 else: story += [Paragraph("Votre classement ne permet pas de construire sans ambiguïté un profil stable à deux lettres. Aucune liste de métiers n'est donc forcée.",body)]
 story += [Paragraph('Comment poursuivre ?',h2),Paragraph("Pour chaque piste, demandez-vous : quelles activités m'attirent réellement ? Quelles compétences et qualifications sont nécessaires ? Quelles conditions de travail, valeurs, contraintes de vie et perspectives d'emploi dois-je vérifier ?",body),Paragraph("<b>Cette synthèse est un point de départ.</b> Une analyse plus approfondie peut confronter vos intérêts à votre parcours, vos compétences, vos valeurs, vos moteurs, vos préférences, vos projets et votre équilibre de vie.",body),Paragraph("<b>En accès PUBLIC :</b> ce rapport est un support d’exploration. Il ne constitue ni un diagnostic, ni une prescription d’orientation, ni une validation de compétences.",body),Paragraph(f'<b>Référentiel utilisé :</b> {ROME_REFERENCE_VERSION} - données ROME datées {rome.source_date or "juin 2026"}.',small),Paragraph(f'Version : {PIP_REPORT_VERSION} - Interprétation : {INTERPRETATION_VERSION} - Banque : PIP-BANK-0.5 - Scoring : {sc.get("algorithm_version","")} - ROME : {ROME_REFERENCE_VERSION}',small)]
 doc.build(story,onFirstPage=lambda c,d:_footer(c,d,'Clarté360 - Rapport PIP RIASEC PUBLIC'),onLaterPages=lambda c,d:_footer(c,d,'Clarté360 - Rapport PIP RIASEC PUBLIC')); return buf.getvalue()

def build_pip_report_pdf(session,logo_path=None):
 mode=str(getattr(getattr(session.get('launch_context'),'mode',None),'value','')).upper()
 if 'ACCOMP' in mode:
  return _build_pip_accompaniment_report_pdf(session,logo_path)
 return _build_pip_public_report_pdf(session,logo_path)

def _ocode(r):
 m={'realistic':'R','investigative':'I','artistic':'A','social':'S','enterprising':'E','conventional':'C'}; c=str(r.get('code','')); return m.get(c.lower(),c[:1].upper())

def build_onet_report_pdf(session,logo_path=None):
 onet=session.get('onet_state') or {}
 if not onet.get('completed'):raise ValueError('Une passation O*NET complète est nécessaire.')
 ores=sorted(onet.get('results') or [],key=lambda r:-float(r.get('score',0))); vals={_ocode(r):float(r.get('score',0)) for r in ores}; order=[_ocode(r) for r in ores]; maxv=max([50]+list(vals.values()))
 reg,bold,body,h1,h2,h3,small=_styles(); buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=16*mm,bottomMargin=20*mm,title='Rapport O*NET Interest Profiler',author='Clarté360'); story=[]; _start(story,logo_path,'O*NET® INTEREST PROFILER','Rapport autonome — résultats officiels et lecture Clarté360',body,h1); who=_who(session)
 if who:story.append(Paragraph(f'<b>Bénéficiaire :</b> {who}',body))
 story += [Paragraph("<b>Pourquoi la passation a-t-elle été réalisée en anglais ?</b> Clarté360 utilise les 60 activités de l’O*NET® Interest Profiler dans leur version anglaise fournie par O*NET Web Services. Les questions ne sont ni traduites ni reformulées par Clarté360 afin de conserver l’instrument utilisé dans son format de référence.",body),Paragraph("Le présent rapport est rédigé en français pour faciliter votre lecture. Les <b>scores et données O*NET</b> sont conservés sans modification ; les explications en français sont des <b>commentaires pédagogiques Clarté360</b> clairement distincts de l’instrument officiel.",body),Paragraph("Les scores O*NET restent sur leur échelle propre. Ils ne sont ni convertis en indices PIP, ni fusionnés, ni moyennés avec le PIP Clarté360.",body),PageBreak(),Paragraph('1. Ce que mesure l’O*NET® Interest Profiler',h1),Paragraph("L’O*NET® Interest Profiler explore les intérêts professionnels à travers les six familles RIASEC. Il aide à identifier les types d’activités de travail que vous aimez davantage ou moins. Il ne constitue pas, à lui seul, une mesure de vos compétences, de votre aptitude à exercer un métier ou de votre performance future.",body),Paragraph("Les intitulés français ci-dessous sont fournis par Clarté360 comme aide de lecture. Les catégories officielles restent : Realistic, Investigative, Artistic, Social, Enterprising et Conventional.",body)]
 for d in RIASEC:story += [Paragraph(f'{d} — {LABELS[d]}',h3),Paragraph(DESC[d],body)]
 story += [PageBreak(),Paragraph('2. Vos résultats officiels O*NET',h1),Paragraph("Le graphique et le tableau reprennent les scores retournés par O*NET Web Services. Ils sont présentés sans conversion en score PIP. Le rang indique quelles dimensions obtiennent les scores les plus élevés dans votre propre profil ; il ne doit pas être confondu avec un niveau PIP sur 100.",body),_radar(vals,reg,bold,maxv=maxv),_table(order,vals,reg,bold,small,suffix='')]
 story += [PageBreak(),Paragraph('3. Lecture Clarté360 en français',h1),Paragraph("Cette partie est une aide de lecture rédigée par Clarté360. Elle ne modifie pas les résultats O*NET et ne constitue pas une traduction officielle du matériel O*NET.",body)]
 for n,d in enumerate(order,1):
  title=next((str(r.get('title') or '') for r in ores if _ocode(r)==d),'')
  official=f"{title} ({d})" if title else d
  story += [Paragraph(f'{n}. {official} — score officiel : {vals[d]:.0f}',h2),Paragraph(f'<b>Lecture Clarté360 :</b> {DESC[d]}',body)]
 story += [PageBreak(),Paragraph('4. Comment utiliser ce résultat',h1),Paragraph("L’ordre des six scores permet d’identifier les familles d’activités qui ressortent davantage dans vos réponses. Le rapport ne transforme pas ces scores en catégories françaises de type « faible », « fort » ou « très fort » : nous conservons ici l’échelle et les résultats propres à l’O*NET® Interest Profiler.",body),Paragraph("Si vous avez également réalisé le PIP Clarté360, vous disposez de deux rapports distincts. Les convergences ou différences entre leurs classements peuvent être discutées en accompagnement, sans produire de score composite et sans considérer qu’un outil devrait nécessairement confirmer l’autre.",body),Paragraph("Une divergence peut devenir une question d’exploration : formulation des activités, contexte imaginé, expérience professionnelle, familiarité avec l’anglais ou évolution de vos intérêts. Elle ne signifie pas automatiquement qu’un résultat est erroné.",body),Paragraph("Ce résultat reste un support d’exploration et ne constitue pas une recommandation automatique de métier.",body),PageBreak(),Paragraph('5. Source, droits et méthodologie',h1),Paragraph("Cette application incorpore des informations issues d’O*NET Web Services, service du U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). O*NET® est une marque de USDOL/ETA.",body),Paragraph("Clarté360 utilise l’API O*NET Web Services pour charger les 60 questions en anglais et obtenir les résultats. Les données retournées par le service sont présentées sans altération ; leur format d’affichage peut être adapté sans en changer le sens. Les commentaires pédagogiques en français du présent rapport sont rédigés par Clarté360 et sont identifiés comme tels.",body),Paragraph("Références : O*NET Web Services — https://services.onetcenter.org/ ; O*NET Interest Profiler — https://www.onetcenter.org/IP.html ; conditions de licence des données Web Services — https://services.onetcenter.org/help/license_data",small),Paragraph(f'Version du rapport : {ONET_REPORT_VERSION}',small)]
 doc.build(story,onFirstPage=lambda c,d:_footer(c,d,'Clarté360 - Rapport O*NET® Interest Profiler'),onLaterPages=lambda c,d:_footer(c,d,'Clarté360 - Rapport O*NET® Interest Profiler')); return buf.getvalue()

def build_report_pdf(session,logo_path=None): return build_pip_report_pdf(session,logo_path)
