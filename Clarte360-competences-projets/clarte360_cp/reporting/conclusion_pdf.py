from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer
from clarte360_cp.reporting.conclusion_content import (
    action_plan_sections, results_sections, synthesis_sections,
)

TEAL = colors.HexColor("#087E80")
DARK = colors.HexColor("#243A3A")
MUTED = colors.HexColor("#5C7070")


def _p(value, style):
    text = escape(str(value or "")).replace("\n", "<br/>")
    return Paragraph(text or "—", style)


def _footer(canvas, doc):
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(colors.HexColor("#DDE7E7")); canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 8); canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Clarté360 · Bilan de compétences · Document de travail confidentiel")
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def render_conclusion_pdf(title: str, sections: list[tuple[str, str]], *, version: str | int) -> bytes:
    """Generate a readable PDF from an already finalized/published C&P artifact."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=19 * mm, leftMargin=19 * mm,
        topMargin=18 * mm, bottomMargin=21 * mm, title=str(title)[:160], author="Clarté360")
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("CPTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22,
            leading=27, textColor=DARK, alignment=TA_CENTER, spaceAfter=7 * mm),
        "eyebrow": ParagraphStyle("CPEyebrow", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9,
            leading=13, textColor=TEAL, alignment=TA_CENTER, spaceAfter=3 * mm),
        "heading": ParagraphStyle("CPHeading", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12,
            leading=16, textColor=TEAL, spaceBefore=5 * mm, spaceAfter=2 * mm, keepWithNext=True),
        "body": ParagraphStyle("CPBody", parent=base["BodyText"], fontName="Helvetica", fontSize=10,
            leading=15, textColor=DARK, spaceAfter=2 * mm, wordWrap="CJK"),
        "meta": ParagraphStyle("CPMeta", parent=base["Normal"], fontName="Helvetica", fontSize=9,
            leading=12, textColor=MUTED, alignment=TA_CENTER),
    }
    story = [
        _p("CLARTÉ360 · COMPÉTENCES & PROJETS", styles["eyebrow"]),
        _p(title, styles["title"]),
        _p(f"Version {version} · Préparé le {datetime.now(timezone.utc).date().isoformat()}", styles["meta"]),
        Spacer(1, 4 * mm), HRFlowable(width="100%", thickness=1, color=TEAL),
        Spacer(1, 3 * mm),
    ]
    for heading, content in sections:
        story.append(KeepTogether([_p(heading, styles["heading"]), _p(content, styles["body"])]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def render_action_plan_pdf(plan: dict) -> bytes:
    return render_conclusion_pdf("Plan d’action convenu", action_plan_sections(plan), version=plan.get("version_no") or 1)


def render_results_pdf(record: dict) -> bytes:
    return render_conclusion_pdf("Résultats détaillés du bilan", results_sections(record), version=record.get("version") or 1)


def render_synthesis_pdf(record: dict) -> bytes:
    return render_conclusion_pdf("Synthèse finale du bilan", synthesis_sections(record), version=record.get("version") or 1)
