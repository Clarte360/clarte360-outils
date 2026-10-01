from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

TEAL=colors.HexColor('#008080'); LIGHT=colors.HexColor('#EAF7F7'); DARK=colors.HexColor('#223333'); GREY=colors.HexColor('#6B7777')
DOMAIN_ORDER=('N','E','O','A','C')

def _esc(s:Any)->str:
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def _bar(value:float,width=230,height=8):
    value=max(0,min(100,float(value)))
    d=[]
    from reportlab.graphics.shapes import Drawing, Rect, Line
    dr=Drawing(width,height+10)
    dr.add(Rect(0,5,width,height,fillColor=colors.HexColor('#E6ECEC'),strokeColor=None))
    dr.add(Rect(0,5,width*value/100,height,fillColor=TEAL,strokeColor=None))
    dr.add(Line(width*.5,3,width*.5,height+7,strokeColor=colors.HexColor('#AABBBB'),strokeWidth=.5))
    return dr

def _five_branch_canvas(c:canvas.Canvas,x:float,y:float,w:float,h:float,domains:list[dict]):
    import math
    cx=x+w/2; cy=y+h/2; radius=min(w,h)*.34
    c.setFillColor(colors.HexColor('#F4FAFA')); c.setStrokeColor(colors.HexColor('#AACFCF')); c.circle(cx,cy,35,fill=1,stroke=1)
    c.setFillColor(DARK); c.setFont('Helvetica-Bold',9); c.drawCentredString(cx,cy+3,'Mon profil'); c.setFont('Helvetica',7); c.drawCentredString(cx,cy-8,'5 dimensions')
    pos=[90,18,-54,-126,162]
    for dom,ang in zip(domains,pos):
        a=math.radians(ang); nx=cx+radius*math.cos(a); ny=cy+radius*math.sin(a)
        c.setStrokeColor(colors.HexColor('#A8CDCD')); c.line(cx,cy,nx,ny)
        c.setFillColor(LIGHT); c.setStrokeColor(TEAL); c.circle(nx,ny,28,fill=1,stroke=1)
        c.setFillColor(DARK); c.setFont('Helvetica-Bold',7)
        label=dom['display_fr']
        words=label.split(); lines=[]; cur=''
        for word in words:
            if len(cur)+len(word)+1>18: lines.append(cur); cur=word
            else: cur=(cur+' '+word).strip()
        if cur: lines.append(cur)
        yy=ny+6 if len(lines)>1 else ny+1
        for line in lines[:3]: c.drawCentredString(nx,yy,line); yy-=8
        c.setFont('Helvetica',6.5); c.drawCentredString(nx,ny-18,f"{dom['index_0_100']:.0f}/100")

def generate_report(path:Path, *, interpretation:dict[str,Any], feedback:dict[str,Any], app_version:str, reference_version:str, interpretation_version:str)->str:
    path.parent.mkdir(parents=True,exist_ok=True)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleC',parent=styles['Title'],fontName='Helvetica-Bold',fontSize=24,leading=28,textColor=TEAL,alignment=TA_CENTER,spaceAfter=8))
    styles.add(ParagraphStyle(name='H1C',parent=styles['Heading1'],fontName='Helvetica-Bold',fontSize=15,leading=18,textColor=TEAL,spaceBefore=10,spaceAfter=7))
    styles.add(ParagraphStyle(name='H2C',parent=styles['Heading2'],fontName='Helvetica-Bold',fontSize=11.5,leading=14,textColor=DARK,spaceBefore=7,spaceAfter=4))
    styles.add(ParagraphStyle(name='BodyC',parent=styles['BodyText'],fontName='Helvetica',fontSize=9.5,leading=13,textColor=DARK,spaceAfter=5))
    styles.add(ParagraphStyle(name='SmallC',parent=styles['BodyText'],fontName='Helvetica',fontSize=7.7,leading=10,textColor=GREY,spaceAfter=4))
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=1.55*cm,leftMargin=1.55*cm,topMargin=1.5*cm,bottomMargin=1.5*cm,title='Clarté360 — Profil de fonctionnement professionnel')
    story=[]
    story += [Spacer(1,1.1*cm),Paragraph('Clarté360',styles['TitleC']),Paragraph('Profil de fonctionnement professionnel',ParagraphStyle(name='Sub',parent=styles['BodyC'],fontSize=16,leading=20,alignment=TA_CENTER,textColor=DARK)),Spacer(1,.35*cm),Paragraph('Basé sur l’IPIP-NEO-120 et le modèle des cinq grands facteurs de personnalité (Big Five)',ParagraphStyle(name='Sub2',parent=styles['SmallC'],fontSize=9.5,leading=13,alignment=TA_CENTER)),Spacer(1,.7*cm)]
    notice=Table([[Paragraph('<b>À retenir</b><br/>Les résultats constituent un support d’exploration, de réflexion et de dialogue. Ils ne constituent ni une évaluation clinique, ni un diagnostic psychologique ou psychiatrique.',styles['BodyC'])]],colWidths=[17.2*cm])
    notice.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),.6,TEAL),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)])); story += [notice,Spacer(1,.5*cm)]
    story += [Paragraph('Comment lire ce profil ?',styles['H1C']),Paragraph('Les cinq dimensions et leurs trente facettes décrivent des tendances continues. Un score plus élevé ou plus faible n’est pas en soi meilleur. L’intérêt du profil est d’identifier des nuances, des contrastes et des questions à mettre en perspective avec votre expérience professionnelle.',styles['BodyC']),Paragraph(interpretation['non_normative_notice'],styles['SmallC']),PageBreak()]
    story += [Paragraph('Vue d’ensemble — les 5 dimensions',styles['H1C'])]
    # Placeholder table; branch graphic is painted through onFirstPage of a separate mini canvas is cumbersome in Platypus; use a compact table + bars.
    data=[[Paragraph('<b>Dimension</b>',styles['BodyC']),Paragraph('<b>Repère</b>',styles['BodyC']),Paragraph('<b>Lecture</b>',styles['BodyC'])]]
    for d in interpretation['domains']:
        data.append([Paragraph(_esc(d['display_fr']),styles['BodyC']),_bar(d['index_0_100'],180,7),Paragraph(_esc(d['tendency_label']),styles['BodyC'])])
    t=Table(data,colWidths=[5.5*cm,6.5*cm,4.5*cm],repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('TEXTCOLOR',(0,0),(-1,0),TEAL),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#DDEAEA')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)])); story += [t,Spacer(1,.3*cm)]
    for d in interpretation['domains']:
        story += [KeepTogether([Paragraph(_esc(d['display_fr']),styles['H2C']),Paragraph(_esc(d['plain_definition']),styles['BodyC']),Paragraph(f"<b>Repère descriptif :</b> {d['index_0_100']:.0f}/100 — {_esc(d['tendency_label'])}",styles['BodyC'])])]
    story += [PageBreak(),Paragraph('Lecture détaillée — les 30 facettes',styles['H1C'])]
    for dom in DOMAIN_ORDER:
        dmeta=next(x for x in interpretation['domains'] if x['code']==dom)
        story += [Paragraph(_esc(dmeta['display_fr']),styles['H2C'])]
        rows=[[Paragraph('<b>Facette</b>',styles['SmallC']),Paragraph('<b>Repère</b>',styles['SmallC']),Paragraph('<b>Lecture</b>',styles['SmallC'])]]
        for f in [x for x in interpretation['facets'] if x['domain']==dom]:
            rows.append([Paragraph(_esc(f['display_fr']),styles['SmallC']),_bar(f['index_0_100'],135,5),Paragraph(_esc(f['tendency_text']),styles['SmallC'])])
        tt=Table(rows,colWidths=[5.1*cm,5.4*cm,6.0*cm],repeatRows=1)
        tt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('GRID',(0,0),(-1,-1),.2,colors.HexColor('#E2EEEE')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)])); story += [tt,Spacer(1,.25*cm)]
        for f in [x for x in interpretation['facets'] if x['domain']==dom]:
            story += [KeepTogether([Paragraph(f"{_esc(f['display_fr'])} <font color='#6B7777'>({_esc(f['scientific_term'])})</font>",styles['H2C']),Paragraph(_esc(f['plain_definition']),styles['BodyC']),Paragraph(f"<b>Votre tendance :</b> {_esc(f['tendency_text'])}",styles['BodyC']),Paragraph(f"<b>Question à explorer :</b> {_esc(f['debrief_question'])}",styles['BodyC'])])]
        story += [PageBreak()]
    story += [Paragraph('Votre ressenti sur les résultats',styles['H1C']),Paragraph('Votre ressenti ne modifie pas les scores. Il permet de nuancer, confirmer ou questionner ce que vous avez lu afin de préparer le dialogue avec votre accompagnateur.',styles['BodyC'])]
    labels={'global':'Le profil présenté vous ressemble','dominants':'Les dimensions/facettes saillantes vous correspondent','nuances':'Le rapport rend compte des nuances de votre fonctionnement','useful':'Les résultats vous aident à mieux comprendre votre fonctionnement professionnel'}
    fbrows=[]
    for k,l in labels.items(): fbrows.append([Paragraph(_esc(l),styles['BodyC']),Paragraph(str(feedback[k])+'/5',styles['BodyC'])])
    fb=Table(fbrows,colWidths=[13.5*cm,2.5*cm]); fb.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.25,colors.HexColor('#DDEAEA')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)])); story += [fb,Spacer(1,.25*cm)]
    if feedback.get('over'): story += [Paragraph('<b>Élément perçu comme plus marqué :</b> '+_esc(feedback['over']),styles['BodyC'])]
    if feedback.get('under'): story += [Paragraph('<b>Élément perçu comme moins marqué :</b> '+_esc(feedback['under']),styles['BodyC'])]
    story += [Paragraph('<b>Souhaite approfondir avec son accompagnateur :</b> '+('Oui' if feedback['dialogue']=='oui' else 'Non'),styles['BodyC'])]
    if feedback.get('free'): story += [Paragraph('<b>À retenir, nuancer ou approfondir :</b><br/>'+_esc(feedback['free']).replace('\n','<br/>'),styles['BodyC'])]
    story += [Spacer(1,.3*cm),Paragraph('Méthode, droits et limites',styles['H1C']),Paragraph('Instrument de base : Johnson IPIP-NEO-120, issu de l’International Personality Item Pool (IPIP), domaine public. Adaptation française Clarté360 réalisée avec l’assistance de ChatGPT (OpenAI), GPT-5.6 Sol, septembre 2026. La facette O6 « Ouverture aux conventions » utilise une adaptation Clarté360 non politique documentée.',styles['BodyC']),Paragraph(f"Version application : {_esc(app_version)} — Référentiel questionnaire : {_esc(reference_version)} — Référentiel d’interprétation : {_esc(interpretation_version)}",styles['SmallC'])]
    def footer(c,doc):
        c.saveState(); c.setStrokeColor(colors.HexColor('#DCE9E9')); c.line(1.5*cm,1.1*cm,A4[0]-1.5*cm,1.1*cm); c.setFont('Helvetica',7); c.setFillColor(GREY); c.drawString(1.5*cm,.75*cm,'Clarté360 — Profil de fonctionnement professionnel'); c.drawRightString(A4[0]-1.5*cm,.75*cm,f'Page {doc.page}'); c.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return hashlib.sha256(path.read_bytes()).hexdigest()
