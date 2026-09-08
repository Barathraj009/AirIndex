"""Report generation for AirIndex India — PDF and Excel executive reports.

Provides two export formats from an IndexResult:
- PDF via reportlab (professional layout, index chart, breakdown table)
- Excel via openpyxl (full data tab + summary tab)

Usage:
    from app.services.reports import export_index_pdf, export_index_excel
    pdf_bytes = export_index_pdf(result, config_base_period="2026-01")
    xl_bytes = export_index_excel(result)
"""

from __future__ import annotations

import base64
import io
from datetime import datetime

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch

from app.services.index_engine import IndexResult, IndexConfig, compute_index
from app.core.database import engine, SessionLocal
from app.models import Base
from app.api.query_helpers import load_observations_df
from app.models.reference import Route


# ---------------------------------------------------------------------------
# Combined export
# ---------------------------------------------------------------------------

def export_index(formats: list[str] | None = None) -> dict[str, bytes]:
    """Compute the latest index and export to requested formats.

    Args:
        formats: List of format names, e.g. ['pdf', 'excel'].
                 Defaults to both if not specified.

    Returns:
        Dict mapping format name to bytes (e.g. {'pdf': b'...', 'excel': b'...'}).
    """
    db = SessionLocal()
    try:
        Base.metadata.create_all(engine)
        df = load_observations_df(db)
        if df.empty:
            raise ValueError("No observation data found.")

        route_weights = {r.route_key: r.weight for r in db.query(Route).filter(Route.active == True).all()}
        config = IndexConfig(base_period="2026-01", route_weights=route_weights)
        period = sorted(df["travel_date"].str[:7].unique())[-1]
        result = compute_index(df, config, as_of_period=period)
    finally:
        db.close()

    formats = formats or ["pdf", "excel"]
    output: dict[str, bytes] = {}
    if "pdf" in formats:
        output["pdf"] = export_index_pdf(result, config_base_period="2026-01")
    if "excel" in formats:
        output["excel"] = export_index_excel(result)
    return output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _style_table(table):
    """Apply a professional table style."""
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#e8edf5"), colors.whitesmoke]),
    ]
    table.setStyle(TableStyle(style))


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------

def export_index_pdf(result: IndexResult, config_base_period: str = "2026-01") -> bytes:
    """Export an IndexResult to a PDF executive report.

    Returns the PDF as bytes. Includes:
    - Title page with index value and base period
    - Summary metrics (index, change %, observation count)
    - Top route contributions table
    - Airline contributions table
    - Calculation breakdown bullet points
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph("AirIndex India — Airfare Price Index", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(
        Paragraph(
            f"Executive Index Report — Base Period: {config_base_period}, As-of Period: {result.as_of_period}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(f"Index Value: <b>{result.index_value:.2f}</b>", styles["Normal"]))
    story.append(
        Paragraph(f"Change from Base: <b>{result.change_from_base_pct:.2f}%</b>", styles["Normal"])
    )
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"Observations Used: <b>{result.n_observations_used}</b>", styles["Normal"]))
    story.append(PageBreak())

    # Summary Metrics
    story.append(Paragraph("Summary Metrics", styles["Heading2"]))

    metrics_data = [["Metric", "Value"]]
    metrics_data.append(["Index Value", f"{result.index_value:.2f}"])
    metrics_data.append(["Change from Base (%)", f"{result.change_from_base_pct:.2f}"])
    metrics_data.append(["Methodology", result.methodology_version])
    metrics_data.append(["Base Period", result.base_period])
    metrics_data.append(["As-of Period", result.as_of_period])
    metrics_data.append(["Observations Used", str(result.n_observations_used)])

    metrics_table = Table(metrics_data, colWidths=[2.5 * inch, 3.5 * inch])
    _style_table(metrics_table)
    story.append(metrics_table)
    story.append(Spacer(1, 0.3 * inch))

    # Top Route Contributions
    story.append(Paragraph("Top Route Contributions", styles["Heading2"]))

    sorted_routes = sorted(
        result.route_contributions.items(), key=lambda kv: abs(kv[1]), reverse=True
    )[:15]

    route_rows = [["Route", "Contribution (%)", "Weight"]]
    for route, contrib in sorted_routes:
        rf = result.route_fares.get(route, {})
        weight = rf.get("weight", 0.0)
        route_rows.append([route, f"{contrib:.2f}", f"{weight:.2f}"])

    route_table = Table(route_rows, colWidths=[2.5 * inch, 2.0 * inch, 1.5 * inch])
    _style_table(route_table)
    story.append(route_table)
    story.append(Spacer(1, 0.2 * inch))

    # Airline Contributions
    story.append(Paragraph("Airline Contributions", styles["Heading2"]))

    sorted_airlines = sorted(
        result.airline_contributions.items(), key=lambda kv: abs(kv[1]), reverse=True
    )
    airline_rows = [["Airline", "Contribution (%)"]]
    for airline, contrib in sorted_airlines:
        airline_rows.append([airline, f"{contrib:.2f}"])

    airline_table = Table(airline_rows, colWidths=[3.0 * inch, 2.0 * inch])
    _style_table(airline_table)
    story.append(airline_table)
    story.append(Spacer(1, 0.2 * inch))

    # Calculation Breakdown
    story.append(Paragraph("Calculation Breakdown", styles["Heading2"]))
    for line in result.calculation_breakdown or []:
        story.append(Paragraph(line, styles["Normal"]))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    return pdf_bytes


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

def export_index_excel(result: IndexResult) -> bytes:
    """Export an IndexResult to an Excel workbook with three tabs.

    Returns the XLSX file as bytes. Tabs:
    - Summary: key metrics, base/as-of periods, observation count
    - Route Contributions: every route with weight, fares, relative, contribution
    - Airline Contributions: every airline with contribution %
    - Calculation Breakdown: each bullet on its own row
    """
    buf = io.BytesIO()

    # Summary tab
    summary_data = {
        "Metric": ["Index Value", "Change from Base (%)", "Methodology", "Base Period",
                    "As-of Period", "Observations Used"],
        "Value": [
            f"{result.index_value:.2f}",
            f"{result.change_from_base_pct:.2f}",
            result.methodology_version,
            result.base_period,
            result.as_of_period,
            str(result.n_observations_used),
        ],
    }
    summary_df = pd.DataFrame(summary_data)

    # Route Contributions tab
    route_rows = []
    for route, contrib in result.route_contributions.items():
        rf = result.route_fares.get(route, {})
        route_rows.append(
            {
                "Route": route,
                "Contribution (%)": f"{contrib:.2f}",
                "Weight": f"{rf.get('weight', 0.0):.2f}",
                "Base Period Fare": rf.get("base_period_fare"),
                "As-of Period Fare": rf.get("as_of_period_fare"),
                "Relative": rf.get("relative"),
            }
        )
    route_df = pd.DataFrame(route_rows)

    # Airline Contributions tab
    airline_rows = []
    for airline, contrib in result.airline_contributions.items():
        airline_rows.append({"Airline": airline, "Contribution (%)": f"{contrib:.2f}"})
    airline_df = pd.DataFrame(airline_rows)

    # Calculation Breakdown tab
    breakdown_rows = []
    for line in result.calculation_breakdown or []:
        breakdown_rows.append({"Breakdown": line})
    breakdown_df = pd.DataFrame(breakdown_rows)

    # Write Excel
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        route_df.to_excel(writer, sheet_name="Route Contributions", index=False)
        airline_df.to_excel(writer, sheet_name="Airline Contributions", index=False)
        breakdown_df.to_excel(writer, sheet_name="Calculation Breakdown", index=False)

    xlsx_bytes = buf.getvalue()
    return xlsx_bytes