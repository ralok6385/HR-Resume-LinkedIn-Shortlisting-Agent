"""
PDF Report Generator — Creates shortlist reports using ReportLab.

Generates:
- PDF (ReportLab) — professional formatted report
- HTML (Jinja2) — rich interactive report
- JSON (spec-compliant) — machine-readable API output
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR, TEMPLATES_DIR

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates shortlist reports in PDF, HTML, and JSON formats."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ------------------------------------------------------------------ #
    # PDF — ReportLab
    # ------------------------------------------------------------------ #
    def generate_pdf(self, ranked, job_requirements, stats) -> Path:
        """Generate a professional PDF report using ReportLab."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                HRFlowable, KeepTogether
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        except ImportError:
            logger.error("ReportLab not installed. Run: pip install reportlab")
            raise

        output_path = self.output_dir / f"shortlist_report_{self.timestamp}.pdf"
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )

        styles = getSampleStyleSheet()
        # Custom styles
        title_style = ParagraphStyle("Title", parent=styles["Title"],
            fontSize=22, textColor=colors.HexColor("#1e293b"), spaceAfter=6)
        subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"],
            fontSize=11, textColor=colors.HexColor("#64748b"), spaceAfter=16)
        h2_style = ParagraphStyle("H2", parent=styles["Heading2"],
            fontSize=14, textColor=colors.HexColor("#1e40af"), spaceBefore=16, spaceAfter=8)
        h3_style = ParagraphStyle("H3", parent=styles["Heading3"],
            fontSize=11, textColor=colors.HexColor("#374151"), spaceBefore=10, spaceAfter=4)
        body_style = ParagraphStyle("Body", parent=styles["Normal"],
            fontSize=9, textColor=colors.HexColor("#374151"), leading=14)
        small_style = ParagraphStyle("Small", parent=styles["Normal"],
            fontSize=8, textColor=colors.HexColor("#6b7280"), leading=12)
        center_style = ParagraphStyle("Center", parent=styles["Normal"],
            alignment=TA_CENTER, fontSize=9)

        story = []

        # ── Cover ────────────────────────────────────────────────────────
        story.append(Spacer(1, 1*cm))
        jd_title = getattr(job_requirements, "title", "Position") if job_requirements else "Position"
        story.append(Paragraph("HR Candidate Shortlist Report", title_style))
        story.append(Paragraph(f"Role: {jd_title}", subtitle_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#3b82f6")))
        story.append(Spacer(1, 0.5*cm))

        # ── Summary Stats ────────────────────────────────────────────────
        story.append(Paragraph("Executive Summary", h2_style))
        summary_data = [
            ["Metric", "Value"],
            ["Total Candidates Evaluated", str(stats.get("total_candidates", len(ranked)))],
            ["Average Score", f"{stats.get('average_score', 0):.1f} / 10"],
            ["Recommended to Hire", str(stats.get("strong_hire_count", 0) + stats.get("hire_count", 0))],
            ["Maybe (Further Review)", str(stats.get("maybe_count", 0))],
            ["Not Recommended", str(stats.get("no_hire_count", 0))],
        ]
        summary_table = Table(summary_data, colWidths=[9*cm, 6*cm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#f8fafc"), colors.white]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0,0), (-1,-1), 8),
            ("ALIGN", (1,0), (1,-1), "CENTER"),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.5*cm))

        # ── Ranked Table ─────────────────────────────────────────────────
        story.append(Paragraph("Ranked Shortlist", h2_style))
        table_data = [["#", "Candidate", "Skills\n(30%)", "Exp\n(25%)", "Edu\n(15%)", "Portfolio\n(20%)", "Comm\n(10%)", "Total", "Rec"]]
        rec_colors = {
            "Strong Hire": colors.HexColor("#16a34a"),
            "Hire": colors.HexColor("#0284c7"),
            "Maybe": colors.HexColor("#d97706"),
            "No Hire": colors.HexColor("#dc2626"),
        }
        for rc in ranked:
            s = rc.score
            dims = {d.dimension: d.score for d in s.dimension_scores}
            table_data.append([
                str(rc.rank),
                s.candidate_name[:22],
                str(dims.get("Skills Match", "-")),
                str(dims.get("Experience Relevance", "-")),
                str(dims.get("Education & Certifications", "-")),
                str(dims.get("Project / Portfolio", "-")),
                str(dims.get("Communication Quality", "-")),
                f"{s.total_weighted_score:.1f}",
                s.recommendation,
            ])

        ranked_table = Table(table_data, colWidths=[0.8*cm,4.5*cm,1.5*cm,1.5*cm,1.5*cm,1.8*cm,1.5*cm,1.5*cm,2*cm])
        ranked_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#f8fafc"), colors.white]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0,0), (-1,-1), 6),
            ("ALIGN", (2,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(ranked_table)
        story.append(Spacer(1, 0.5*cm))

        # ── Per-Candidate Detail ──────────────────────────────────────────
        story.append(Paragraph("Candidate Scoring Details", h2_style))
        for rc in ranked:
            s = rc.score
            rec = s.recommendation
            rec_color = rec_colors.get(rec, colors.HexColor("#374151"))

            candidate_block = []
            candidate_block.append(Paragraph(
                f"#{rc.rank} — {s.candidate_name}  |  Total: {s.total_weighted_score:.1f}/10  |  {rec}",
                h3_style
            ))
            if s.overall_summary:
                candidate_block.append(Paragraph(f"<i>{s.overall_summary}</i>", small_style))
            candidate_block.append(Spacer(1, 0.2*cm))

            dim_data = [["Dimension", "Weight", "Score", "Justification"]]
            for d in s.dimension_scores:
                dim_data.append([
                    d.dimension, f"{int(d.weight*100)}%", f"{d.score:.1f}/10",
                    Paragraph(d.justification[:100], small_style)
                ])
            dim_table = Table(dim_data, colWidths=[3.5*cm, 1.5*cm, 1.8*cm, 9.5*cm])
            dim_table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 8),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#f1f5f9"), colors.white]),
                ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ("PADDING", (0,0), (-1,-1), 5),
                ("ALIGN", (1,0), (2,-1), "CENTER"),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ]))
            candidate_block.append(dim_table)

            # Override log
            if s.is_overridden:
                candidate_block.append(Spacer(1, 0.15*cm))
                candidate_block.append(Paragraph(
                    f"⚠ HR Override: {s.override_recommendation} — Reason: {s.override_reason}",
                    ParagraphStyle("Override", parent=small_style, textColor=colors.HexColor("#b45309"))
                ))

            candidate_block.append(Spacer(1, 0.4*cm))
            story.append(KeepTogether(candidate_block))

        # ── Footer ────────────────────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            "Generated by HR Resume Shortlisting AI Agent | All scores are AI-assisted and subject to HR review.",
            center_style
        ))

        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")
        return output_path

    # ------------------------------------------------------------------ #
    # HTML — Jinja2
    # ------------------------------------------------------------------ #
    def generate_html(self, ranked, job_requirements, stats) -> Path:
        """Generate rich HTML report using Jinja2 template."""
        output_path = self.output_dir / f"shortlist_report_{self.timestamp}.html"
        template_path = TEMPLATES_DIR / "shortlist.html"

        context = {
            "title": f"Shortlist Report — {getattr(job_requirements, 'title', 'Position')}",
            "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "job_requirements": job_requirements,
            "ranked": ranked,
            "stats": stats,
        }

        if template_path.exists():
            try:
                from jinja2 import Environment, FileSystemLoader
                env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
                template = env.get_template("shortlist.html")
                html_content = template.render(**context)
            except Exception as e:
                logger.warning(f"Jinja2 template failed: {e}. Using built-in template.")
                html_content = self._render_html_builtin(context)
        else:
            html_content = self._render_html_builtin(context)

        output_path.write_text(html_content, encoding="utf-8")
        logger.info(f"HTML report generated: {output_path}")
        return output_path

    def _render_html_builtin(self, ctx) -> str:
        """Built-in HTML template — no Jinja2 dependency."""
        ranked = ctx["ranked"]
        stats = ctx["stats"]
        jd = ctx["job_requirements"]

        def rec_color(rec):
            return {"Strong Hire": "#16a34a", "Hire": "#0284c7", "Maybe": "#d97706", "No Hire": "#dc2626"}.get(rec, "#6b7280")

        rows = ""
        for rc in ranked:
            s = rc.score
            dims = {d.dimension: d for d in s.dimension_scores}
            override_html = ""
            if s.is_overridden:
                override_html = f'<div class="override-badge">⚠ HR Override: {s.override_recommendation} — {s.override_reason}</div>'

            dim_rows = ""
            for d in s.dimension_scores:
                bar_pct = int(d.score * 10)
                bar_color = "#16a34a" if d.score >= 7 else "#d97706" if d.score >= 4.5 else "#dc2626"
                dim_rows += f"""
                <tr>
                  <td>{d.dimension}</td>
                  <td>{int(d.weight*100)}%</td>
                  <td>
                    <div class="score-bar-wrap">
                      <div class="score-bar" style="width:{bar_pct}%;background:{bar_color}"></div>
                    </div>
                    {d.score:.1f}/10
                  </td>
                  <td>{d.justification}</td>
                </tr>"""

            rows += f"""
            <div class="candidate-card">
              <div class="candidate-header">
                <span class="rank">#{rc.rank}</span>
                <span class="cand-name">{s.candidate_name}</span>
                <span class="total-score">{s.total_weighted_score:.1f}/10</span>
                <span class="rec-badge" style="background:{rec_color(s.recommendation)}20;color:{rec_color(s.recommendation)}">{s.recommendation}</span>
              </div>
              {f'<p class="summary">{s.overall_summary}</p>' if s.overall_summary else ''}
              <table class="dim-table">
                <thead><tr><th>Dimension</th><th>Weight</th><th>Score</th><th>Justification</th></tr></thead>
                <tbody>{dim_rows}</tbody>
              </table>
              {override_html}
            </div>"""

        jd_title = getattr(jd, "title", "Position") if jd else "Position"
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{ctx['title']}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Inter',sans-serif;background:#0f172a;color:#e2e8f0;padding:2rem}}
  .container{{max-width:1100px;margin:0 auto}}
  h1{{font-size:2rem;font-weight:800;background:linear-gradient(135deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
  .meta{{color:#94a3b8;font-size:.85rem;margin:.5rem 0 2rem}}
  .stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-bottom:2rem}}
  .stat-card{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.25rem;text-align:center}}
  .stat-val{{font-size:1.8rem;font-weight:800;color:#3b82f6}}
  .stat-lbl{{font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-top:.25rem}}
  .candidate-card{{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:1.5rem;margin-bottom:1.25rem}}
  .candidate-header{{display:flex;align-items:center;gap:1rem;margin-bottom:1rem;flex-wrap:wrap}}
  .rank{{font-size:1.1rem;font-weight:800;color:#3b82f6;min-width:2.5rem}}
  .cand-name{{font-size:1.2rem;font-weight:700;flex:1}}
  .total-score{{font-size:1rem;font-weight:700;color:#e2e8f0}}
  .rec-badge{{padding:.25rem .75rem;border-radius:20px;font-size:.8rem;font-weight:700}}
  .summary{{color:#94a3b8;font-size:.875rem;margin-bottom:1rem;font-style:italic}}
  .dim-table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  .dim-table th{{background:#0f172a;color:#94a3b8;text-align:left;padding:.6rem .75rem;font-weight:600;text-transform:uppercase;font-size:.7rem;letter-spacing:.05em}}
  .dim-table td{{padding:.55rem .75rem;border-bottom:1px solid #1e293b;vertical-align:middle}}
  .score-bar-wrap{{background:#0f172a;border-radius:4px;height:6px;width:80px;display:inline-block;vertical-align:middle;margin-right:.5rem}}
  .score-bar{{height:6px;border-radius:4px}}
  .override-badge{{background:#fef3c7;color:#92400e;border-radius:8px;padding:.5rem 1rem;margin-top:.75rem;font-size:.8rem;font-weight:600}}
  footer{{text-align:center;color:#475569;font-size:.75rem;margin-top:3rem;padding-top:1rem;border-top:1px solid #1e293b}}
</style>
</head>
<body>
<div class="container">
  <h1>📋 HR Candidate Shortlist Report</h1>
  <p class="meta">Role: {jd_title} &nbsp;|&nbsp; Generated: {ctx['generated_at']}</p>

  <div class="stats-grid">
    <div class="stat-card"><div class="stat-val">{stats.get('total_candidates',len(ranked))}</div><div class="stat-lbl">Total Evaluated</div></div>
    <div class="stat-card"><div class="stat-val">{stats.get('average_score',0):.1f}</div><div class="stat-lbl">Avg Score</div></div>
    <div class="stat-card"><div class="stat-val" style="color:#16a34a">{stats.get('strong_hire_count',0)+stats.get('hire_count',0)}</div><div class="stat-lbl">Recommended</div></div>
    <div class="stat-card"><div class="stat-val" style="color:#d97706">{stats.get('maybe_count',0)}</div><div class="stat-lbl">Maybe</div></div>
    <div class="stat-card"><div class="stat-val" style="color:#dc2626">{stats.get('no_hire_count',0)}</div><div class="stat-lbl">Not Recommended</div></div>
  </div>

  <h2 style="font-size:1.25rem;font-weight:700;margin-bottom:1rem;color:#94a3b8">RANKED SHORTLIST</h2>
  {rows}

  <footer>Generated by HR Resume Shortlisting AI Agent &nbsp;|&nbsp; All scores are AI-assisted and subject to HR review.</footer>
</div>
</body>
</html>"""

    # ------------------------------------------------------------------ #
    # JSON
    # ------------------------------------------------------------------ #
    def generate_json(self, ranked, job_requirements, stats, agent=None) -> Path:
        """Generate spec-compliant JSON report."""
        output_path = self.output_dir / f"shortlist_report_{self.timestamp}.json"

        if agent and hasattr(agent, "to_output_json"):
            candidates_output = agent.to_output_json()
        else:
            candidates_output = []
            for rc in ranked:
                s = rc.score
                dim_map = {d.dimension: d for d in s.dimension_scores}
                def get_dim(name):
                    d = dim_map.get(name)
                    return {"score": d.score, "justification": d.justification} if d else {"score": 0, "justification": "N/A"}
                candidates_output.append({
                    "candidate_name": s.candidate_name,
                    "rank": rc.rank,
                    "scores": {
                        "skills_match": get_dim("Skills Match"),
                        "experience_relevance": get_dim("Experience Relevance"),
                        "education_certs": get_dim("Education & Certifications"),
                        "project_portfolio": get_dim("Project / Portfolio"),
                        "communication_quality": get_dim("Communication Quality"),
                    },
                    "weighted_total": round(s.total_weighted_score * 10, 1),
                    "recommendation": s.recommendation.lower().replace(" ", "-"),
                    "override_log": [{"reason": s.override_reason, "new_recommendation": s.override_recommendation}] if s.is_overridden else [],
                })

        report = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "job_title": getattr(job_requirements, "title", "Unknown") if job_requirements else "Unknown",
                "total_candidates": len(ranked),
                "scoring_rubric": {
                    "skills_match": {"weight": 0.30},
                    "experience_relevance": {"weight": 0.25},
                    "education_certs": {"weight": 0.15},
                    "project_portfolio": {"weight": 0.20},
                    "communication_quality": {"weight": 0.10},
                },
            },
            "summary": stats,
            "candidates": candidates_output,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON report generated: {output_path}")
        return output_path
