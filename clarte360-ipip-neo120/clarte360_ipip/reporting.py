from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image

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

def _safe_identity(beneficiary_identity:dict[str,Any]|None)->str:
    if not beneficiary_identity:
        return ''
    first=str(beneficiary_identity.get('first_name') or '').strip()
    last=str(beneficiary_identity.get('last_name') or '').strip()
    return ' '.join(x for x in (first,last) if x)

def _footer_factory(*,app_version:str,reference_version:str):
    def footer(c,doc):
        c.saveState()
        c.setStrokeColor(colors.HexColor('#DCE9E9'))
        c.line(1.5*cm,1.1*cm,A4[0]-1.5*cm,1.1*cm)
        c.setFont('Helvetica',7); c.setFillColor(GREY)
        c.drawString(1.5*cm,.75*cm,'Clarté360 - Profil de fonctionnement professionnel')
        c.drawCentredString(A4[0]/2,.75*cm,f'Application {app_version} | Référentiel {reference_version}')
        c.drawRightString(A4[0]-1.5*cm,.75*cm,f'Page {doc.page}')
        c.restoreState()
    return footer

def generate_report(path:Path, *, interpretation:dict[str,Any], feedback:dict[str,Any], app_version:str, reference_version:str, interpretation_version:str, beneficiary_identity:dict[str,Any]|None=None, report_date:str|None=None, logo_path:Path|None=None)->str:
    """Generate the final Clarté360 beneficiary report.

    Identity is optional and must only be supplied by the authorised ACCOMPAGNEMENT
    context. No identity is inferred from questionnaire answers or persisted results.
    """
    from datetime import datetime, timezone
    path.parent.mkdir(parents=True,exist_ok=True)
    report_date=report_date or datetime.now(timezone.utc).date().isoformat()
    identity=_safe_identity(beneficiary_identity)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleC',parent=styles['Title'],fontName='Helvetica-Bold',fontSize=23,leading=27,textColor=TEAL,alignment=TA_CENTER,spaceAfter=8))
    styles.add(ParagraphStyle(name='H1C',parent=styles['Heading1'],fontName='Helvetica-Bold',fontSize=15,leading=18,textColor=TEAL,spaceBefore=10,spaceAfter=7))
    styles.add(ParagraphStyle(name='H2C',parent=styles['Heading2'],fontName='Helvetica-Bold',fontSize=11.5,leading=14,textColor=DARK,spaceBefore=7,spaceAfter=4))
    styles.add(ParagraphStyle(name='BodyC',parent=styles['BodyText'],fontName='Helvetica',fontSize=9.4,leading=13,textColor=DARK,spaceAfter=5))
    styles.add(ParagraphStyle(name='SmallC',parent=styles['BodyText'],fontName='Helvetica',fontSize=7.7,leading=10,textColor=GREY,spaceAfter=4))
    styles.add(ParagraphStyle(name='CoverMeta',parent=styles['BodyC'],fontSize=9.3,leading=13,alignment=TA_CENTER,textColor=DARK))
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=1.55*cm,leftMargin=1.55*cm,topMargin=1.5*cm,bottomMargin=1.55*cm,title='Clarté360 - Profil de fonctionnement professionnel')
    story=[]
    if logo_path and Path(logo_path).exists():
        story += [Spacer(1,.35*cm),Image(str(logo_path),width=2.35*cm,height=2.35*cm),Spacer(1,.18*cm)]
        story[-2].hAlign='CENTER'
    else:
        story += [Spacer(1,.9*cm)]
    story += [Paragraph('Clarté360',styles['TitleC']),Paragraph('Profil de fonctionnement professionnel',ParagraphStyle(name='Sub',parent=styles['BodyC'],fontSize=16,leading=20,alignment=TA_CENTER,textColor=DARK)),Spacer(1,.18*cm),Paragraph('Explorer mes tendances de fonctionnement',ParagraphStyle(name='Tag',parent=styles['SmallC'],fontSize=10,leading=13,alignment=TA_CENTER,textColor=TEAL)),Spacer(1,.38*cm)]
    meta=[]
    if identity: meta.append(f'<b>Bénéficiaire :</b> {_esc(identity)}')
    meta += [f'<b>Date du rapport :</b> {_esc(report_date)}',f'<b>Version application :</b> {_esc(app_version)}',f'<b>Référentiel :</b> {_esc(reference_version)}']
    story += [Paragraph('<br/>'.join(meta),styles['CoverMeta']),Spacer(1,.45*cm)]
    notice=Table([[Paragraph('<b>Finalité et limites</b><br/>Cet outil explore des tendances de fonctionnement. Les résultats ne définissent pas la personne et ne constituent ni une évaluation clinique, ni un diagnostic psychologique ou psychiatrique. Ils doivent être mis en perspective avec l’expérience, les valeurs, les préférences, les motivations et le projet professionnel.',styles['BodyC'])]],colWidths=[17.2*cm])
    notice.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),.7,TEAL),('LEFTPADDING',(0,0),(-1,-1),11),('RIGHTPADDING',(0,0),(-1,-1),11),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)])); story += [notice,Spacer(1,.35*cm)]
    story += [Paragraph('Comment lire ce rapport ?',styles['H1C']),Paragraph('Les cinq dimensions et leurs trente facettes décrivent des tendances continues. Un repère plus élevé ou plus faible n’est pas en soi meilleur. L’intérêt du profil est d’identifier des nuances, des contrastes et des questions à mettre en perspective avec des situations réellement vécues.',styles['BodyC']),Paragraph(_esc(interpretation['non_normative_notice']),styles['SmallC']),PageBreak()]

    story += [Paragraph('Vue d’ensemble - les 5 dimensions',styles['H1C']),Paragraph('Le repère 0-100 facilite uniquement la lecture visuelle. Il ne s’agit ni d’un percentile, ni d’une norme française, ni d’un classement.',styles['SmallC'])]
    data=[[Paragraph('<b>Dimension</b>',styles['BodyC']),Paragraph('<b>Repère descriptif</b>',styles['BodyC']),Paragraph('<b>Lecture</b>',styles['BodyC'])]]
    for d in interpretation['domains']:
        data.append([Paragraph(_esc(d['display_fr']),styles['BodyC']),_bar(d['index_0_100'],180,7),Paragraph(_esc(d['tendency_label']),styles['BodyC'])])
    t=Table(data,colWidths=[5.5*cm,6.5*cm,4.5*cm],repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('TEXTCOLOR',(0,0),(-1,0),TEAL),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#DDEAEA')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)])); story += [t,Spacer(1,.35*cm)]
    for d in interpretation['domains']:
        story += [KeepTogether([Paragraph(_esc(d['display_fr']),styles['H2C']),Paragraph(_esc(d['plain_definition']),styles['BodyC']),Paragraph(f"<b>Repère descriptif :</b> {d['index_0_100']:.0f}/100 - {_esc(d['tendency_label'])}",styles['BodyC'])])]

    story += [PageBreak(),Paragraph('Lecture détaillée - les 30 facettes',styles['H1C'])]
    for di,dom in enumerate(DOMAIN_ORDER):
        dmeta=next(x for x in interpretation['domains'] if x['code']==dom)
        story += [Paragraph(_esc(dmeta['display_fr']),styles['H2C'])]
        rows=[[Paragraph('<b>Facette</b>',styles['SmallC']),Paragraph('<b>Repère</b>',styles['SmallC']),Paragraph('<b>Lecture</b>',styles['SmallC'])]]
        facets=[x for x in interpretation['facets'] if x['domain']==dom]
        for f in facets:
            rows.append([Paragraph(_esc(f['display_fr']),styles['SmallC']),_bar(f['index_0_100'],135,5),Paragraph(_esc(f['tendency_text']),styles['SmallC'])])
        tt=Table(rows,colWidths=[5.1*cm,5.4*cm,6.0*cm],repeatRows=1)
        tt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('GRID',(0,0),(-1,-1),.2,colors.HexColor('#E2EEEE')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])); story += [tt,Spacer(1,.25*cm)]
        for f in facets:
            story += [KeepTogether([Paragraph(f"{_esc(f['display_fr'])} <font color='#6B7777'>({_esc(f['scientific_term'])})</font>",styles['H2C']),Paragraph(_esc(f['plain_definition']),styles['BodyC']),Paragraph(f"<b>Votre tendance :</b> {_esc(f['tendency_text'])}",styles['BodyC']),Paragraph(f"<b>Question à explorer :</b> {_esc(f['debrief_question'])}",styles['BodyC'])])]
        if di < len(DOMAIN_ORDER)-1: story += [PageBreak()]

    story += [PageBreak(),Paragraph('Points d’appui et points de vigilance',styles['H1C']),Paragraph('Un même trait peut jouer différemment selon la situation. Ces pistes servent à préparer le dialogue et ne transforment pas un score en qualité ou en défaut.',styles['BodyC'])]
    pv=Table([[Paragraph('<b>Points d’appui possibles</b><br/>- Dans quelles situations cette tendance vous aide-t-elle à agir efficacement ?<br/>- Que facilite-t-elle dans vos relations, vos décisions ou votre organisation ?<br/>- Qu’aimeriez-vous continuer à mobiliser ?',styles['BodyC']),Paragraph('<b>Points de vigilance possibles</b><br/>- Dans quels contextes cette même tendance devient-elle moins adaptée ?<br/>- Que se passe-t-il lorsqu’elle est trop ou pas assez mobilisée ?<br/>- Quel ajustement pourrait vous donner davantage de choix ?',styles['BodyC'])]],colWidths=[8.25*cm,8.25*cm])
    pv.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F7FBFB')),('BOX',(0,0),(-1,-1),.4,colors.HexColor('#DDEAEA')),('INNERGRID',(0,0),(-1,-1),.3,colors.HexColor('#DDEAEA')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)])); story += [pv,Spacer(1,.3*cm)]
    story += [Paragraph('Exemples professionnels non prescriptifs',styles['H1C']),Paragraph('Ces exemples servent uniquement à faire émerger des situations à discuter. Ils ne constituent ni une recommandation de métier ni une conclusion sur votre aptitude.',styles['SmallC'])]
    context_map={'N':'dans les périodes de pression, d’incertitude ou de charge émotionnelle','E':'dans les interactions, prises de parole, coopérations et temps de travail plus solitaire','O':'face à la nouveauté, aux idées, à l’apprentissage et aux changements de méthode','A':'dans la coopération, les désaccords, la relation de service et la négociation','C':'dans la planification, le suivi, les délais, l’autonomie et l’adaptation aux imprévus'}
    for d in interpretation['domains']: story += [Paragraph(f"<b>{_esc(d['display_fr'])}</b> : observez comment cette tendance se manifeste {_esc(context_map.get(d['code'],'dans vos situations professionnelles'))}.",styles['BodyC'])]
    story += [Paragraph('Questions de réflexion',styles['H1C'])]
    for dom in DOMAIN_ORDER:
        facets=[x for x in interpretation['facets'] if x['domain']==dom]
        if facets: story += [Paragraph('• '+_esc(facets[0]['debrief_question']),styles['BodyC'])]
    story += [Paragraph('À mettre en perspective avec mon parcours',styles['H1C']),Paragraph('Ces résultats gagnent à être croisés avec vos expériences, vos valeurs, vos moteurs, vos préférences, votre RIASEC, vos compétences et votre projet. Recherchez ce qui vous ressemble, ce qui vous surprend, ce que vous souhaitez nuancer et les situations concrètes qui confirment ou contredisent ces repères.',styles['BodyC'])]

    story += [PageBreak(),Paragraph('Mon ressenti sur les résultats',styles['H1C']),Paragraph('Ce ressenti est distinct du scoring et ne modifie jamais les scores psychométriques. Il sert à nuancer, confirmer ou questionner la restitution avant le débrief.',styles['BodyC'])]
    labels={'global':'Le profil présenté vous ressemble','dominants':'Les dimensions/facettes saillantes vous correspondent','nuances':'Le rapport rend compte des nuances de votre fonctionnement','useful':'Les résultats vous aident à mieux comprendre votre fonctionnement professionnel'}
    fbrows=[]
    for k,l in labels.items(): fbrows.append([Paragraph(_esc(l),styles['BodyC']),Paragraph(str(feedback[k])+'/5',styles['BodyC'])])
    fb=Table(fbrows,colWidths=[13.5*cm,2.5*cm]); fb.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.25,colors.HexColor('#DDEAEA')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)])); story += [fb,Spacer(1,.25*cm)]
    if feedback.get('over'): story += [Paragraph('<b>Élément perçu comme plus marqué :</b> '+_esc(feedback['over']),styles['BodyC'])]
    if feedback.get('under'): story += [Paragraph('<b>Élément perçu comme moins marqué :</b> '+_esc(feedback['under']),styles['BodyC'])]
    story += [Paragraph('<b>Souhaite approfondir avec son accompagnateur :</b> '+('Oui' if feedback['dialogue']=='oui' else 'Non'),styles['BodyC'])]
    if feedback.get('free'): story += [Paragraph('<b>À retenir, nuancer ou approfondir :</b><br/>'+_esc(feedback['free']).replace('\n','<br/>'),styles['BodyC'])]

    story += [Spacer(1,.25*cm),Paragraph('Méthode, droits et références',styles['H1C']),Paragraph('Référence scientifique : Johnson, J. A. (2014), Measuring thirty facets of the Five Factor Model with a 120-item public domain inventory: Development of the IPIP-NEO-120, Journal of Research in Personality, 51, 78-89, DOI 10.1016/j.jrp.2014.05.003.',styles['BodyC']),Paragraph('Instrument de base : Johnson IPIP-NEO-120, issu de l’International Personality Item Pool (IPIP), domaine public. Adaptation française Clarté360 réalisée avec l’assistance de ChatGPT (OpenAI), GPT-5.6 Sol, septembre 2026. Cette adaptation linguistique ne constitue pas une validation psychométrique française indépendante.',styles['BodyC']),Paragraph('Avertissement O6 : la facette « Ouverture aux conventions » utilise l’adaptation Clarté360 non politique fondée sur les items IPIP D73, H690, D99 et D88. Elle ne doit pas être présentée comme strictement équivalente à la facette O6 Johnson originale.',styles['BodyC']),Paragraph(f"Version application : {_esc(app_version)} | Référentiel questionnaire : {_esc(reference_version)} | Référentiel d’interprétation : {_esc(interpretation_version)}",styles['SmallC'])]
    footer=_footer_factory(app_version=app_version,reference_version=reference_version)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return hashlib.sha256(path.read_bytes()).hexdigest()
