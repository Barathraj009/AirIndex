from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_permission
from app.services.index_engine import IndexConfig, compute_index
from app.services.reports import export_index, export_index_pdf, export_index_excel
from app.api.query_helpers import load_observations_df
from app.models.reference import Route
from app.models.auth import User

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/export")
def export_report(current_user: User = Depends(require_permission("view_reports")), formats: str = "pdf,excel", db: Session = Depends(get_db)):
    """Compute the latest index and export to PDF and/or Excel.

    Query params:
        formats: comma-separated list, e.g. 'pdf' or 'pdf,excel'

    Returns a zip file containing the requested formats, or the single
    format if only one is requested.
    """
    fmt_list = [f.strip().lower() for f in formats.split(",") if f.strip()]
    if not fmt_list:
        fmt_list = ["pdf", "excel"]

    df = load_observations_df(db)
    if df.empty:
        raise HTTPException(status_code=404, detail="No observation data found.")

    route_weights = {r.route_key: r.weight for r in db.query(Route).filter(Route.active == True).all()}
    config = IndexConfig(base_period="2026-01", route_weights=route_weights)
    period = sorted(df["travel_date"].str[:7].unique())[-1]
    result = compute_index(df, config, as_of_period=period)

    if len(fmt_list) == 1:
        fmt = fmt_list[0]
        if fmt == "pdf":
            pdf_bytes = export_index_pdf(result, config_base_period="2026-01")
            return StreamingResponse(
                iter([pdf_bytes]),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=airindex_{period}.pdf"},
            )
        elif fmt == "excel":
            xl_bytes = export_index_excel(result)
            return StreamingResponse(
                iter([xl_bytes]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=airindex_{period}.xlsx"},
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown format: {fmt}")
    else:
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if "pdf" in fmt_list:
                zf.writestr("airindex_report.pdf", export_index_pdf(result, config_base_period="2026-01"))
            if "excel" in fmt_list:
                zf.writestr("airindex_report.xlsx", export_index_excel(result))
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=airindex_{period}_reports.zip"},
        )