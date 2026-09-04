from __future__ import annotations

from io import BytesIO
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether

TEAL = colors.HexColor('#008080')
LIGHT = colors.HexColor('#E6F4F4')
DARK = colors.HexColor('#243A3A')
GREY = colors.HexColor('#667777')
YELLOW = colors.HexColor('#FFF7D6')

LEGAL = {
    'raison_sociale': 'Clarté360 SAS',
    'adresse': '60 rue François 1er – 75008 Paris',
    'telephone': '01 89 48 08 25',
    'email': 'contact@clarte360.com',
    'web': 'www.clarte360.com',
    'rcs': '102349834',
    'siret': '10234983400014',
    'naf': '8559 A',
    'tva': 'FR88102349834',
    'representant': 'Christelle BEN ROMDHANE, Présidente',
}

MODEL_VERSION = 'BC_PARTICULIER_V1.0_2026-09-04'


def money(x):
    try:
        return f"{float(x):,.2f} €".replace(',', ' ').replace('.', ',')
    except Exception:
        return str(x or '')


def frdate(v):
    if not v: return ''
    if isinstance(v, datetime): return v.strftime('%d/%m/%Y')
    if isinstance(v, date): return v.strftime('%d/%m/%Y')
    s=str(v)
    try: return datetime.fromisoformat(s[:10]).strftime('%d/%m/%Y')
    except Exception: return s


def esc(x):
    s='' if x is None else str(x)
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br/>')


def _styles():
    ss=getSampleStyleSheet()
    return {
        'body': ParagraphStyle('Body', parent=ss['BodyText'], fontName='Helvetica', fontSize=9.2, leading=12.5, textColor=DARK, spaceAfter=5),
        'small': ParagraphStyle('Small', parent=ss['BodyText'], fontName='Helvetica', fontSize=7.4, leading=9.2, textColor=GREY),
        'title': ParagraphStyle('Title', parent=ss['Title'], fontName='Helvetica-Bold', fontSize=17, leading=21, alignment=TA_CENTER, textColor=TEAL, spaceAfter=7),
        'subtitle': ParagraphStyle('Subtitle', parent=ss['BodyText'], fontName='Helvetica-Bold', fontSize=10, leading=13, alignment=TA_CENTER, textColor=DARK, spaceAfter=12),
        'h': ParagraphStyle('H', parent=ss['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=TEAL, spaceBefore=7, spaceAfter=5),
        'white': ParagraphStyle('White', parent=ss['BodyText'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.white),
        'sign': ParagraphStyle('Sign', parent=ss['BodyText'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=DARK),
    }


def _footer(canvas, doc):
    canvas.saveState()
    w,h=A4
    canvas.setStrokeColor(colors.HexColor('#B7DADA'))
    canvas.line(1.4*cm, 1.18*cm, w-1.4*cm, 1.18*cm)
    canvas.setFont('Helvetica', 6.4)
    canvas.setFillColor(GREY)
    txt=f"CLARTÉ360 – {LEGAL['adresse']} | {LEGAL['telephone']} | {LEGAL['email']} | {LEGAL['web']}"
    canvas.drawCentredString(w/2, 0.86*cm, txt)
    txt2=f"RCS {LEGAL['rcs']} | SIRET {LEGAL['siret']} | NAF {LEGAL['naf']} | TVA {LEGAL['tva']} | Page {doc.page}"
    canvas.drawCentredString(w/2, 0.58*cm, txt2)
    canvas.restoreState()


def section(story, title, styles):
    t=Table([[Paragraph(esc(title), styles['white'])]], colWidths=[17.6*cm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),TEAL),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story += [Spacer(1,4), t, Spacer(1,5)]


def kv_table(rows, styles, widths=(5.2*cm,12.4*cm)):
    data=[]
    for k,v in rows:
        data.append([Paragraph(f'<b>{esc(k)}</b>', styles['body']), Paragraph(esc(v),styles['body'])])
    t=Table(data,colWidths=list(widths),repeatRows=0)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),LIGHT),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#B7DADA')),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
    ]))
    return t


def financial_table(financing: List[Dict[str,Any]], total_ttc: float, styles):
    rows=[[Paragraph('<b>Financeur / prise en charge</b>',styles['body']),Paragraph('<b>Montant TTC</b>',styles['body'])]]
    for f in financing:
        label=f.get('NOM_FINANCEUR') or f.get('TYPE_FINANCEUR') or 'Financeur'
        if str(f.get('TYPE_FINANCEUR','')).upper() == 'BENEFICIAIRE':
            label='Participation personnelle du bénéficiaire'
        rows.append([Paragraph(esc(label),styles['body']),Paragraph(money(f.get('MONTANT_TTC',0)),styles['body'])])
    rows.append([Paragraph('<b>Prix total du bilan</b>',styles['body']),Paragraph(f'<b>{money(total_ttc)}</b>',styles['body'])])
    t=Table(rows,colWidths=[12.5*cm,5.1*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),LIGHT),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#F2F8F8')),
        ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#B7DADA')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ALIGN',(1,1),(1,-1),'RIGHT'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)
    ]))
    return t


def build_bc_particulier_pdf(d: Dict[str,Any], logo_path: str | Path | None = None) -> bytes:
    """Contrat de bilan de compétences - particulier à ses frais, avec financement tiers possible non signataire.
    Clauses déterministes et versionnées. Aucun texte juridique n'est généré par IA.
    """
    b=d['beneficiaire']; a=d['action']; p=d['prix']; f=d.get('financements',[]); c=d.get('consultant',{})
    styles=_styles(); bio=BytesIO()
    doc=SimpleDocTemplate(bio,pagesize=A4,leftMargin=1.45*cm,rightMargin=1.45*cm,topMargin=1.2*cm,bottomMargin=1.55*cm,title='Contrat de prestation de bilan de compétences')
    story=[]
    if logo_path and Path(logo_path).exists():
        img=Image(str(logo_path),width=2.3*cm,height=2.3*cm); img.hAlign='CENTER'; story += [img,Spacer(1,3)]
    story += [Paragraph('CONTRAT DE PRESTATION DE BILAN DE COMPÉTENCES',styles['title']),
              Paragraph(f"N° ACTION CLARTÉ360 : {esc(a.get('no_clar',''))} — Modèle {MODEL_VERSION}",styles['subtitle'])]

    section(story,'1. Parties au contrat',styles)
    story.append(Paragraph(f"<b>Prestataire :</b> {LEGAL['raison_sociale']}, {LEGAL['adresse']}, SIRET {LEGAL['siret']}, représentée par {LEGAL['representant']}.",styles['body']))
    story.append(Paragraph(f"<b>Bénéficiaire :</b> {esc(b.get('civilite',''))} {esc(b.get('prenom',''))} {esc(b.get('nom',''))}, né(e) le {esc(frdate(b.get('date_naissance')))}, domicilié(e) {esc(b.get('adresse',''))} {esc(b.get('code_postal',''))} {esc(b.get('ville',''))}, e-mail {esc(b.get('email',''))}, téléphone {esc(b.get('telephone',''))}.",styles['body']))
    if c.get('nom'):
        story.append(Paragraph(f"<b>Accompagnateur désigné :</b> {esc(c.get('nom'))} — {esc(c.get('email',''))} — {esc(c.get('telephone',''))}.",styles['body']))

    section(story,'2. Objet et cadre du bilan de compétences',styles)
    story.append(Paragraph("Le présent contrat a pour objet de définir les conditions de réalisation d'un bilan de compétences au sens de l'article L.6313-4 du Code du travail. Il permet au bénéficiaire d'analyser ses compétences professionnelles et personnelles, ses aptitudes et ses motivations afin de définir un projet professionnel et, le cas échéant, un projet de formation.",styles['body']))
    story.append(Paragraph("Le bilan est réalisé avec le consentement du bénéficiaire. Les informations recueillies doivent présenter un lien direct et nécessaire avec l'objet du bilan. Les résultats détaillés et le document de synthèse sont destinés au bénéficiaire et ne peuvent être communiqués à un tiers sans son accord, sous réserve des dispositions légales applicables.",styles['body']))

    section(story,'3. Objectifs individualisés issus de la phase préliminaire',styles)
    story.append(kv_table([
        ('Demande / besoin', a.get('demande','')),
        ('Objectifs à travailler', a.get('objectifs','')),
        ('Critères de réussite', a.get('criteres_reussite','')),
    ],styles))

    section(story,'4. Déroulement et contenu du bilan',styles)
    story.append(Paragraph("Le bilan comprend les trois phases réglementaires : une phase préliminaire destinée à analyser la demande, déterminer le format adapté et définir conjointement les modalités ; une phase d'investigation destinée à construire et vérifier le ou les projets professionnels ; une phase de conclusions, conduite par entretiens personnalisés, permettant l'appropriation des résultats, l'identification des conditions de réussite et la formalisation des principales étapes du projet.",styles['body']))
    story.append(Paragraph("Le programme est individualisé à partir de l'APS et peut mobiliser, selon les besoins, les outils propriétaires Clarté360 relatifs notamment aux valeurs, préférences professionnelles, moteurs, compétences et projets, ainsi que des recherches ou travaux personnels complémentaires. Ces travaux complémentaires ne modifient pas la durée d'accompagnement contractualisée lorsqu'ils ne sont pas comptabilisés dans celle-ci.",styles['body']))

    section(story,'5. Durée, période, modalités et suivi',styles)
    story.append(kv_table([
        ('Durée d’accompagnement contractualisée', f"{a.get('duree_heures','')} heures"),
        ('Période de réalisation', f"du {frdate(a.get('date_debut'))} au {frdate(a.get('date_fin'))}"),
        ('Modalité / lieu', a.get('modalite','')),
        ('Planning prévisionnel', a.get('calendrier','')),
        ('Suivi à six mois', a.get('suivi_6_mois','Un entretien de suivi est proposé environ six mois après la conclusion du bilan. Il est distinct de la durée d’accompagnement contractualisée.')),
    ],styles))
    story.append(Paragraph("Le planning peut être ajusté d'un commun accord sans modifier la finalité du bilan ni la durée globale prévue, sous réserve des disponibilités de l'accompagnateur et de la cohérence du parcours.",styles['body']))

    section(story,'6. Moyens mobilisés et accompagnement',styles)
    story.append(Paragraph("Clarté360 met en œuvre des entretiens individualisés, des supports et outils numériques adaptés, des consignes personnalisées et un accompagnement permettant au bénéficiaire de s'approprier ses résultats. Lorsque des séquences sont réalisées à distance, le bénéficiaire dispose des informations nécessaires à leur accès et à leur réalisation. L'accompagnateur reste responsable de la conduite méthodologique du bilan.",styles['body']))

    section(story,'7. Résultats, synthèse, confidentialité et conservation',styles)
    story.append(Paragraph("À l'issue du bilan, le bénéficiaire reçoit ses résultats détaillés et un document de synthèse. La synthèse ne peut être transmise à une autre personne ou institution qu'avec l'accord du bénéficiaire, hors cas expressément prévus par la loi. Les personnes chargées de réaliser et détenir le bilan sont soumises au secret professionnel dans les conditions légales applicables.",styles['body']))
    story.append(Paragraph("Les documents élaborés pour la réalisation du bilan sont traités conformément aux règles applicables aux bilans de compétences. Les documents pouvant être conservés pour les besoins du suivi le sont uniquement dans les conditions et délais autorisés, avec l'accord requis du bénéficiaire.",styles['body']))

    section(story,'8. Dispositions financières',styles)
    total=float(p.get('ttc') or 0)
    story.append(financial_table(f,total,styles))
    story.append(Spacer(1,5))
    story.append(Paragraph(f"Le prix total de la prestation est fixé à <b>{money(total)}</b>. Les prises en charge mentionnées ci-dessus réduisent, le cas échéant, la part directement acquittée par le bénéficiaire sans modifier la valeur totale de la prestation.",styles['body']))
    benef_amount=sum(float(x.get('MONTANT_TTC') or 0) for x in f if str(x.get('TYPE_FINANCEUR','')).upper()=='BENEFICIAIRE')
    if benef_amount:
        story.append(Paragraph(f"<b>Montant restant à la charge personnelle du bénéficiaire : {money(benef_amount)}.</b>",styles['body']))
    story.append(Paragraph("Conformément aux articles L.6353-5 et L.6353-6 du Code du travail, le bénéficiaire dispose d'un délai de dix jours à compter de la signature du contrat pour se rétracter. Aucune somme ne peut lui être exigée avant l'expiration de ce délai. À l'expiration de ce délai, le premier paiement demandé au bénéficiaire ne peut excéder 30 % du prix convenu restant à sa charge ; le solde est échelonné au fur et à mesure du déroulement de l'action.",styles['body']))
    if p.get('modalites_paiement'):
        story.append(Paragraph(f"<b>Modalités prévues :</b> {esc(p.get('modalites_paiement'))}",styles['body']))

    section(story,'9. Rétractation, interruption et force majeure',styles)
    story.append(Paragraph("Le bénéficiaire peut exercer son droit de rétractation dans le délai légal de dix jours à compter de la signature du présent contrat, par lettre recommandée avec avis de réception. En cas de force majeure dûment reconnue empêchant le bénéficiaire de poursuivre le bilan, le contrat peut être rompu et seules les prestations effectivement dispensées sont rémunérées à due proportion de leur valeur prévue au contrat.",styles['body']))
    story.append(Paragraph("En dehors d'un cas de force majeure, toute interruption est examinée au regard des prestations effectivement réalisées, des engagements des parties et des dispositions contractuelles applicables. Les parties recherchent en priorité une solution permettant un report ou un aménagement compatible avec les objectifs du bilan.",styles['body']))

    section(story,'10. Données personnelles et réclamations',styles)
    story.append(Paragraph("Les données personnelles sont traitées pour la gestion administrative, contractuelle, pédagogique et réglementaire du bilan. Les demandes relatives aux données personnelles peuvent être adressées à contact@clarte360.com. Toute difficulté ou réclamation relative à la prestation peut être adressée à la même adresse afin de rechercher prioritairement une solution amiable.",styles['body']))

    section(story,'11. Droit applicable et acceptation',styles)
    story.append(Paragraph("Le présent contrat est soumis au droit français. En cas de différend, les parties recherchent prioritairement une solution amiable avant de saisir, le cas échéant, les juridictions compétentes ou le dispositif de médiation de la consommation applicable.",styles['body']))
    story.append(Spacer(1,5))
    sign=Table([
        [Paragraph(f"<b>Pour Clarté360</b><br/>{esc(LEGAL['representant'])}<br/><br/><br/>Signature",styles['sign']),
         Paragraph(f"<b>Le / la bénéficiaire</b><br/>{esc(b.get('prenom',''))} {esc(b.get('nom',''))}<br/><br/><br/>Signature précédée de la mention « Lu et approuvé – Bon pour accord »",styles['sign'])]
    ],colWidths=[8.8*cm,8.8*cm],rowHeights=[4.0*cm])
    sign.setStyle(TableStyle([('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#B7DADA')),('INNERGRID',(0,0),(-1,-1),0.5,colors.HexColor('#B7DADA')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8)]))
    story += [Paragraph(f"Fait à Paris, le {frdate(a.get('date_contrat'))}.",styles['body']), sign]

    doc.build(story,onFirstPage=_footer,onLaterPages=_footer)
    return bio.getvalue()
