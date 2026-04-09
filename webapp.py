"""Custom HTTP routes for report preview, download, and homepage."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from reporting import REPORTS_DIR


app = FastAPI(title="Liuliumei Report Routes")


def _list_reports() -> list[Path]:
    if not REPORTS_DIR.exists():
        return []
    return sorted(
        (path for path in REPORTS_DIR.iterdir() if path.is_file()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def _resolve_report_path(filename: str) -> Path:
    path = (REPORTS_DIR / filename).resolve()
    reports_root = REPORTS_DIR.resolve()
    if reports_root not in path.parents and path != reports_root:
        raise HTTPException(status_code=400, detail="Invalid report path")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return path


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    report_items = []
    for path in _list_reports():
        suffix = path.suffix.lower()
        if suffix not in {".html", ".pdf", ".md"}:
            continue
        label = "HTML" if suffix == ".html" else "PDF" if suffix == ".pdf" else "MD"
        action = "预览" if suffix in {".html", ".pdf"} else "下载"
        href = f"/reports/{path.name}" if suffix in {".html", ".pdf"} else f"/reports/download/{path.name}"
        report_items.append(
            f"""
            <li class="report-item">
              <div>
                <div class="report-name">{path.name}</div>
                <div class="report-meta">{label}</div>
              </div>
              <a class="report-link" href="{href}" target="_blank" rel="noreferrer">{action}</a>
            </li>
            """
        )

    reports_html = "\n".join(report_items) if report_items else "<p class='empty'>当前还没有生成报告。</p>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>六溜梅工作流首页</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --card: rgba(255, 252, 247, 0.92);
      --text: #1f2937;
      --muted: #6b7280;
      --line: #e5d7c5;
      --accent: #9a3412;
      --accent-soft: #fff1e8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(255, 240, 220, 0.9), transparent 28%),
        radial-gradient(circle at right, rgba(251, 207, 232, 0.32), transparent 22%),
        linear-gradient(180deg, #f8f3ec 0%, var(--bg) 100%);
      min-height: 100vh;
    }}
    .page {{
      max-width: 980px;
      margin: 0 auto;
      padding: 40px 20px 56px;
    }}
    .hero, .panel {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: 0 18px 45px rgba(105, 64, 30, 0.08);
    }}
    .hero {{
      padding: 30px;
      margin-bottom: 20px;
    }}
    .eyebrow {{
      display: inline-block;
      padding: 6px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }}
    h1 {{
      margin: 16px 0 10px;
      font-size: clamp(30px, 5vw, 48px);
      line-height: 1.05;
    }}
    .lead {{
      margin: 0;
      max-width: 720px;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.7;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 22px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 18px;
      border-radius: 14px;
      text-decoration: none;
      font-weight: 600;
      border: 1px solid var(--line);
      color: var(--text);
      background: #fff;
    }}
    .button.primary {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}
    .panel {{
      padding: 24px;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 22px;
    }}
    .tips {{
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.7;
    }}
    .report-list {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 12px;
    }}
    .report-item {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 16px 18px;
      border-radius: 18px;
      border: 1px solid #eadfce;
      background: #fffdfa;
    }}
    .report-name {{
      font-weight: 600;
      word-break: break-all;
    }}
    .report-meta {{
      margin-top: 6px;
      font-size: 13px;
      color: var(--muted);
    }}
    .report-link {{
      white-space: nowrap;
      text-decoration: none;
      color: var(--accent);
      font-weight: 700;
    }}
    .empty {{
      margin: 0;
      color: var(--muted);
    }}
    @media (max-width: 640px) {{
      .report-item {{
        align-items: flex-start;
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <span class="eyebrow">LIULIUMEI WORKFLOW</span>
      <h1>六溜梅产品讨论系统</h1>
      <p class="lead">这里是本地 Web 首页。你可以从这里查看历史报告、进入接口文档，或者继续通过 LangGraph Studio 调试完整工作流。</p>
      <div class="actions">
        <a class="button primary" href="/docs" target="_blank" rel="noreferrer">打开 API 文档</a>
      </div>
    </section>
    <section class="panel">
      <h2>报告列表</h2>
      <p class="tips">下面列出了 reports 目录下可直接访问的报告文件。HTML 和 PDF 支持在线查看，Markdown 文件提供下载。</p>
      <ul class="report-list">
        {reports_html}
      </ul>
    </section>
  </main>
</body>
</html>
"""


@app.get("/reports/{filename}")
def preview_report(filename: str):
    path = _resolve_report_path(filename)
    suffix = path.suffix.lower()
    if suffix == ".html":
        media_type = "text/html"
    elif suffix == ".pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@app.get("/reports/download/{filename}")
def download_report(filename: str):
    path = _resolve_report_path(filename)
    suffix = path.suffix.lower()
    if suffix == ".html":
        media_type = "text/html"
    elif suffix == ".pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)
