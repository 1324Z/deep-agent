"""Report generation utilities for downloadable workflow outputs."""

from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parent
REPORTS_DIR = ROOT_DIR / "reports"
PDF_FONT_NAME = "STSong-Light"
REPORT_BASE_URL = os.getenv("REPORT_BASE_URL", "http://127.0.0.1:2024")


def _ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _summary_text(summary_output: str) -> str:
    return _to_text(summary_output).strip() or "N/A"

def _summary_html(content: str) -> str:
    return (
        "<section class=\"report-section\">"
        "<h2>Summary</h2>"
        f"<pre>{html.escape(content)}</pre>"
        "</section>"
    )


def build_report_html(
    user_query: str,
    market_output,
    product_output,
    dev_output,
    summary_output: str,
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    display_title = user_query[:45] + "..." if len(user_query) > 45 else user_query
    summary_text = _summary_text(summary_output)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(display_title)} - Deep Agent Report</title>
  <style>
    :root {{
      --bg: #ffffff;
      --card: #f9fafb;
      --ink: #111827;
      --muted: #6b7280;
      --line: #e5e7eb;
      --accent: #2563eb;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.6;
    }}
    .page {{
      max-width: 800px;
      margin: 60px auto;
      padding: 0 24px;
    }}
    .hero {{
      border-bottom: 2px solid var(--accent);
      padding-bottom: 32px;
      margin-bottom: 40px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 32px;
      font-weight: 800;
      color: var(--ink);
      letter-spacing: -0.025em;
    }}
    .meta {{
      color: var(--muted);
      font-size: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .report-content {{
      background: var(--card);
      border-radius: 16px;
      padding: 32px;
      border: 1px solid var(--line);
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: inherit;
      font-size: 16px;
      line-height: 1.8;
      color: #374151;
    }}
    .footer {{
      margin-top: 60px;
      padding-top: 20px;
      border-top: 1px solid var(--line);
      text-align: center;
      color: var(--muted);
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <h1>{html.escape(display_title)}</h1>
      <div class="meta">
        <span>Deep Agent · 智能报告</span>
        <span>生成于 {html.escape(generated_at)}</span>
      </div>
    </header>
    <section class="report-content">
      <pre>{html.escape(summary_text)}</pre>
    </section>
    <footer class="footer">
      本报告由 Deep Agent 多智能体系统自动生成 • 仅供参考
    </footer>
  </main>
</body>
</html>
"""


def _ensure_pdf_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    if PDF_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(PDF_FONT_NAME))
    return PDF_FONT_NAME


def _paragraph_html(text: str) -> str:
    escaped = html.escape(text)
    return escaped.replace("\n", "<br/>")


def build_report_pdf(
    output_path: Path,
    user_query: str,
    market_output,
    product_output,
    dev_output,
    summary_output: str,
) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    font_name = _ensure_pdf_font()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    display_title = user_query[:40] + "..." if len(user_query) > 40 else user_query
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=24,
        leading=32,
        alignment=0, # Left align
        textColor=HexColor("#111827"),
        spaceAfter=14,
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        textColor=HexColor("#6b7280"),
        alignment=0, # Left align
        spaceAfter=24,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=12,
        leading=20,
        textColor=HexColor("#374151"),
        wordWrap="CJK",
        borderColor=HexColor("#e5e7eb"),
        borderWidth=0.5,
        borderPadding=12,
        backColor=HexColor("#f9fafb"),
        spaceAfter=12,
    )
    footer_style = ParagraphStyle(
        "ReportFooter",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=12,
        textColor=HexColor("#9ca3af"),
        alignment=TA_CENTER,
        spaceBefore=30,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=display_title,
    )

    story = [
        Paragraph(html.escape(display_title), title_style),
        Paragraph(f"Deep Agent · 生成于 {html.escape(generated_at)}", meta_style),
        Spacer(1, 4),
        Paragraph(_paragraph_html(_summary_text(summary_output)), body_style),
        Spacer(1, 10),
        Paragraph("本报告由 Deep Agent 多智能体系统自动生成 • 仅供参考", footer_style)
    ]

    doc.build(story)


def create_report_files(
    user_query: str,
    market_output,
    product_output,
    dev_output,
    summary_output: str,
) -> dict[str, str]:
    reports_dir = _ensure_reports_dir()
    report_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]

    html_filename = f"{report_id}.html"
    pdf_filename = f"{report_id}.pdf"

    html_path = reports_dir / html_filename
    pdf_path = reports_dir / pdf_filename

    html_content = build_report_html(
        user_query=user_query,
        market_output=market_output,
        product_output=product_output,
        dev_output=dev_output,
        summary_output=summary_output,
    )

    html_path.write_text(html_content, encoding="utf-8")
    pdf_error = ""
    try:
        build_report_pdf(
            output_path=pdf_path,
            user_query=user_query,
            market_output=market_output,
            product_output=product_output,
            dev_output=dev_output,
            summary_output=summary_output,
        )
    except Exception as exc:
        pdf_error = str(exc)

    base = REPORT_BASE_URL.rstrip("/")
    return {
        "report_id": report_id,
        "html_filename": html_filename,
        "pdf_filename": pdf_filename if pdf_path.exists() else "",
        "preview_url": f"{base}/reports/{html_filename}",
        "download_url": f"{base}/reports/download/{html_filename}",
        "pdf_url": f"{base}/reports/download/{pdf_filename}" if pdf_path.exists() else "",
        "html_path": str(html_path),
        "pdf_path": str(pdf_path) if pdf_path.exists() else "",
        "pdf_error": pdf_error,
    }
