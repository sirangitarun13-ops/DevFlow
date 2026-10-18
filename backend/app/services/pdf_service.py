"""ReportLab renderer for deterministic DevFlow report data."""

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _safe(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value).replace("_", " ")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.HexColor("#17213d"), alignment=TA_LEFT, spaceAfter=4))
    styles.add(ParagraphStyle(name="ReportSubtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#59647f"), spaceAfter=12))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor("#27345c"), spaceBefore=14, spaceAfter=7))
    styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#2f3850")))
    styles.add(ParagraphStyle(name="Header", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white, alignment=TA_LEFT))
    return styles


def _paragraph(value: Any, styles, style: str = "BodySmall") -> Paragraph:
    return Paragraph(_safe(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), styles[style])


def _table(rows: list[list[Any]], styles, widths: list[float] | None = None) -> Table:
    wrapped = [[_paragraph(cell, styles, "Header" if index == 0 else "BodySmall") for cell in row] for index, row in enumerate(rows)]
    table = Table(wrapped, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#354375")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8deed")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fb")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _metric_table(metrics: dict[str, Any], styles) -> Table:
    rows = [[_paragraph(label, styles, "Header") for label in metrics.keys()], [_paragraph(value, styles) for value in metrics.values()]]
    table = Table(rows, colWidths=[175 * mm / max(len(metrics), 1)] * len(metrics), hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#354375")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eef1ff")), ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd3ef")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd3ef")), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _section(title: str, styles) -> list[Any]:
    return [Paragraph(title, styles["Section"]), HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd3ef"), spaceAfter=7)]


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#68738e"))
    canvas.drawString(18 * mm, 12 * mm, "DevFlow - Project Report")
    canvas.drawRightString(192 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def render_report(report: dict[str, Any]) -> bytes:
    """Render a report data dictionary into a printable PDF byte string."""
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=17 * mm, bottomMargin=20 * mm, title=report["title"], author="DevFlow")
    story: list[Any] = [Paragraph("DEVFLOW", styles["ReportTitle"]), Paragraph(report["title"], styles["Section"]), Paragraph(f"{report['project']['name']} | Generated {report['generated_at']}", styles["ReportSubtitle"])]
    story.extend(_section("Project overview", styles))
    story.append(_metric_table({"Status": report["project"]["status"], "Progress": f"{report['project'].get('progress_percent', 0)}%", "Start": report["project"].get("start_date"), "End": report["project"].get("end_date")}, styles))
    if report["project"].get("description"):
        story.extend([Spacer(1, 5), _paragraph(report["project"]["description"], styles)])

    if report["type"] in {"project-summary", "sdlc-status"}:
        for title, key in (("Requirements", "requirements"), ("Milestones", "milestones"), ("Sprints", "sprints"), ("Tasks", "tasks"), ("Bugs", "bugs"), ("Test cases", "test_cases"), ("Change requests", "change_requests")):
            metric = report["analytics"].get(key, {})
            rows = [["Metric", "Value"]] + [["Total", metric.get("total", 0)]]
            if metric.get("by_status"):
                rows.extend([[f"Status: {status}", count] for status, count in sorted(metric["by_status"].items())])
            if key == "bugs" and report["analytics"].get("bugs_by_severity"):
                rows.extend([[f"Severity: {severity}", count] for severity, count in sorted(report["analytics"]["bugs_by_severity"].items())])
            story.append(KeepTogether(_section(title, styles) + [_table(rows, styles, [125 * mm, 50 * mm])]))
        story.extend(_section("RCIA summary", styles))
        impact = report["analytics"]["impact_analysis"]
        story.append(_metric_table({"Analyses": impact["total_analyses"], "Impacted artifacts": impact["impacted_artifacts"], "Direct": impact["by_category"].get("direct", 0), "Indirect": impact["by_category"].get("indirect", 0)}, styles))

    if report["type"] == "change-impact":
        story.extend(_section("Requirement and change request", styles))
        requirement = report["requirement"]
        change = report["change_request"]
        story.append(_table([["Field", "Value"], ["Requirement", f"{requirement['requirement_key']} - {requirement['title']}"], ["Priority", requirement["priority"]], ["Status", requirement["status"]], ["Change summary", change["change_summary"]], ["Change status", change["status"]], ["Description", change.get("proposed_description") or "No proposed description recorded."]], styles, [45 * mm, 130 * mm]))
        story.extend(_section("Impact analysis", styles))
        if not report.get("analysis"):
            story.append(_paragraph("No impact analysis has been generated for this change request.", styles))
        else:
            analysis = report["analysis"]
            story.append(_paragraph(f"Status: {analysis['status']} | Started: {analysis['started_at']} | {analysis.get('summary') or ''}", styles))
            impacts = report.get("results", [])
            if impacts:
                story.extend([Spacer(1, 7), _table([["Category", "Artifact", "Path / explanation"]] + [[item["impact_category"], f"{item['artifact_type']} {item['artifact_id']}", f"{item['path']} | {item['explanation']}"] for item in impacts], styles, [28 * mm, 42 * mm, 105 * mm])])
            else:
                story.extend([Spacer(1, 7), _paragraph("The analysis completed without identifying impacted artifacts.", styles)])

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
