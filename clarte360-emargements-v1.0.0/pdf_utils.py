from __future__ import annotations
import io, os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER,TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from branding import BRAND, LEGAL_LINE_1, LEGAL_LINE_2, LOGO_PATH
from services import slot_duration_hours, actual_hours_for_participant
from db import q, one

TZ=ZoneInfo('Europe/Paris')

def _local(iso):
    d=datetime.fromisoformat(iso)
    if d.tzinfo is None: d=d.replace(tzinfo=ZoneInfo('UTC'))
    return d.astimezone(TZ)

TEAL=colors.HexColor(BRAND); LIGHT=colors.HexColor('#F1F8F8'); GREY=colors.HexColor('#6B7280')

def _styles():
    ss=getSampleStyleSheet();
    ss.add(ParagraphStyle(name='C360Title',parent=ss['Title'],textColor=TEAL,fontSize=18,leading=21,spaceAfter=8))
    ss.add(ParagraphStyle(name='C360H2',parent=ss['Heading2'],textColor=TEAL,fontSize=12,leading=14,spaceBefore=8,spaceAfter=6))
    ss.add(ParagraphStyle(name='C360Small',parent=ss['BodyText'],fontSize=7.5,leading=9,textColor=GREY))
    ss.add(ParagraphStyle(name='C360Body',parent=ss['BodyText'],fontSize=9.5,leading=12))
    return ss

def _footer(canvas,doc):
    canvas.saveState();canvas.setFont('Helvetica',6.5);canvas.setFillColor(GREY)
    page_w=canvas._pagesize[0]
    canvas.drawCentredString(page_w/2,12*mm,LEGAL_LINE_1)
    canvas.drawCentredString(page_w/2,8.5*mm,LEGAL_LINE_2)
    canvas.restoreState()

def _header(story,action,ss):
    if LOGO_PATH.exists(): story.append(Image(str(LOGO_PATH),width=18*mm,height=18*mm))
    story.append(Paragraph('CLARTÉ360 — ÉMARGEMENTS',ss['C360Title']))
    story.append(Paragraph(f"<b>{action['action_no']} — {action['title']}</b>",ss['C360Body']))
    if action.get('subtitle'): story.append(Paragraph(action['subtitle'],ss['C360Body']))
    meta=[]
    if action.get('client_name'): meta.append(f"Client : {action['client_name']}")
    if action.get('trainer_name'): meta.append(f"Intervenant : {action['trainer_name']}")
    if action.get('location'): meta.append(f"Lieu : {action['location']}")
    if meta: story.append(Paragraph(' — '.join(meta),ss['C360Small']))
    story.append(Spacer(1,5*mm))

def _sig_image(path,w=24*mm,h=9*mm):
    try:
        if path and Path(path).exists(): return Image(path,width=w,height=h)
    except: pass
    return ''

def collective_pdf(engine,aid):
    action=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':aid}); parts=q(engine,'SELECT * FROM participants WHERE action_id=:a AND active=1 ORDER BY last_name,first_name',{'a':aid}); slots=q(engine,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':aid})
    sigs=q(engine,'SELECT * FROM signatures WHERE slot_id IN (SELECT id FROM slots WHERE action_id=:a)',{'a':aid}); sm={(x['participant_id'],x['slot_id']):x for x in sigs}
    buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=10*mm,rightMargin=10*mm,topMargin=10*mm,bottomMargin=18*mm)
    ss=_styles(); story=[]; _header(story,action,ss)
    dates=[]
    for s in slots:
        if s['slot_date'] not in dates: dates.append(s['slot_date'])
    for di,d in enumerate(dates):
        ds=[s for s in slots if s['slot_date']==d]
        story.append(Paragraph(f"Feuille d'émargement — {datetime.fromisoformat(d).strftime('%d/%m/%Y')}",ss['C360H2']))
        header=['Participant']+[f"{s['start_time']}–{s['end_time']}" for s in ds]
        data=[header]
        for p in parts:
            row=[Paragraph(f"<b>{p['last_name']} {p['first_name']}</b><br/><font size=7>{p.get('company_name') or ''}</font>",ss['C360Body'])]
            for s in ds:
                x=sm.get((p['id'],s['id']))
                if x:
                    t=_local(x['signed_at']).strftime('%H:%M'); late='<br/><b>Signature a posteriori</b>' if x.get('is_late') else ''
                    row.append([_sig_image(x['signature_path']),Paragraph(f"Signé {t}{late}",ss['C360Small'])])
                else: row.append(Paragraph('Non signé',ss['C360Small']))
            data.append(row)
        widths=[65*mm]+[(landscape(A4)[0]-20*mm-65*mm)/max(1,len(ds))]*len(ds)
        tbl=Table(data,colWidths=widths,repeatRows=1)
        tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),TEAL),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#B8CCCC')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story.append(tbl);story.append(Spacer(1,4*mm))
        if di<len(dates)-1: story.append(PageBreak())
    doc.build(story,onFirstPage=_footer,onLaterPages=_footer); return buf.getvalue()

def individual_pdf(engine,pid):
    p=one(engine,'SELECT * FROM participants WHERE id=:p',{'p':pid}); action=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':p['action_id']});slots=q(engine,'SELECT * FROM slots WHERE action_id=:a ORDER BY slot_date,start_time',{'a':p['action_id']}); sigs=q(engine,'SELECT * FROM signatures WHERE participant_id=:p',{'p':pid});sm={x['slot_id']:x for x in sigs}
    buf=io.BytesIO();doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=16*mm,rightMargin=16*mm,topMargin=12*mm,bottomMargin=20*mm);ss=_styles();story=[];_header(story,action,ss)
    story.append(Paragraph(f"Feuille individuelle — <b>{p['last_name']} {p['first_name']}</b>",ss['C360H2']))
    data=[['Date','Créneau','Durée','Signature']]
    for s in slots:
        x=sm.get(s['id']); att=one(engine,'SELECT * FROM attendance_status WHERE participant_id=:p AND slot_id=:s',{'p':pid,'s':s['id']})
        if x:
            mode='Signature manuscrite' if x.get('signature_method')=='MANUSCRITE' else 'Nom et prénom + certification'
            sig=[_sig_image(x['signature_path'],28*mm,10*mm),Paragraph(_local(x['signed_at']).strftime('Signé le %d/%m/%Y à %H:%M') + (' — <b>A POSTERIORI</b>' if x.get('is_late') else '') + f'<br/>{mode}',ss['C360Small'])]
        elif att and att['status']=='ABSENT': sig=Paragraph('<b>ABSENT</b>'+(f"<br/>{att.get('reason') or ''}"),ss['C360Small'])
        elif att and att['status']=='NON_CONCERNE': sig=Paragraph('Non concerné',ss['C360Small'])
        else: sig=Paragraph('Non signé',ss['C360Small'])
        data.append([datetime.fromisoformat(s['slot_date']).strftime('%d/%m/%Y'),f"{s['start_time']}–{s['end_time']}",f"{slot_duration_hours(s):g} h",sig])
        cs=one(engine,'SELECT * FROM trainer_countersignatures WHERE slot_id=:s',{'s':s['id']})
        if cs: data.append(['','','',Paragraph(f"Contresigné par {cs['trainer_name']} le {_local(cs['signed_at']).strftime('%d/%m/%Y à %H:%M')}",ss['C360Small'])])
    tbl=Table(data,colWidths=[28*mm,34*mm,20*mm,90*mm],repeatRows=1);tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),TEAL),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#B8CCCC')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT])]))
    story.append(tbl);doc.build(story,onFirstPage=_footer,onLaterPages=_footer);return buf.getvalue()

def certificate_pdf(engine,pid):
    p=one(engine,'SELECT * FROM participants WHERE id=:p',{'p':pid});a=one(engine,'SELECT * FROM actions WHERE id=:a',{'a':p['action_id']})
    hours=actual_hours_for_participant(engine,pid)
    slots=q(engine,"""SELECT s.* FROM slots s JOIN signatures x ON x.slot_id=s.id WHERE x.participant_id=:p AND x.status='VALIDE' ORDER BY s.slot_date,s.start_time""",{'p':pid})
    dates=sorted({x['slot_date'] for x in slots})
    buf=io.BytesIO();doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=22*mm,rightMargin=22*mm,topMargin=18*mm,bottomMargin=22*mm);ss=_styles();story=[];_header(story,a,ss)
    story.append(Spacer(1,8*mm));story.append(Paragraph('CERTIFICAT DE RÉALISATION',ss['C360Title']));story.append(Spacer(1,6*mm))
    story.append(Paragraph(f"Je soussigné(e), représentant de Clarté360, certifie que <b>{p['first_name']} {p['last_name']}</b> a réalisé l'action <b>{a['title']}</b> (n° {p.get('individual_action_no') or a['action_no']}).",ss['C360Body']));story.append(Spacer(1,5*mm))
    nature=(a.get('nature') or '').upper(); formation='☒' if 'FORMATION' in nature or 'ACTION' in nature else '☐'; bilan='☒' if 'BILAN' in nature else '☐'
    story.append(Paragraph(f"Nature de l'action : {formation} Action de formation &nbsp;&nbsp;&nbsp; {bilan} Bilan de compétences",ss['C360Body']))
    if p.get('company_name'): story.append(Paragraph(f"Entreprise : {p['company_name']}",ss['C360Body']))
    if dates: story.append(Paragraph(f"Dates effectivement réalisées : du {datetime.fromisoformat(dates[0]).strftime('%d/%m/%Y')} au {datetime.fromisoformat(dates[-1]).strftime('%d/%m/%Y')}",ss['C360Body']))
    story.append(Paragraph(f"Durée effectivement justifiée : <b>{hours:g} heure(s)</b>",ss['C360Body']))
    story.append(Spacer(1,8*mm));story.append(Paragraph("Les heures indiquées ci-dessus correspondent aux créneaux disposant d'une preuve d'émargement enregistrée. Les absences non réalisées ne sont pas comptabilisées.",ss['C360Small']))
    story.append(Spacer(1,12*mm));story.append(Paragraph(f"Fait le {datetime.now(TZ).strftime('%d/%m/%Y')} — Document généré à partir du registre d'émargement électronique Clarté360.",ss['C360Small']))
    doc.build(story,onFirstPage=_footer,onLaterPages=_footer);return buf.getvalue()
