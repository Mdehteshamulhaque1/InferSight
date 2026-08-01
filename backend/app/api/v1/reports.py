"""Report export API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession
from app.services import analytics_service, dataset_service, report_service
from app.services.dataset_service import DatasetAccessError, DatasetNotFoundError

router = APIRouter(prefix="/reports", tags=["Reports"])

_MEDIA_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@router.get(
    "/datasets/{dataset_id}.{ext}",
    summary="Export a dataset as CSV, XLSX, or PDF",
    response_class=StreamingResponse,
)
def export_report(
    dataset_id: int,
    ext: str,
    db: DbSession,
    user: CurrentUser,
):
    if ext not in _MEDIA_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported format '{ext}'; use csv, xlsx, or pdf",
        )
    try:
        dataset = dataset_service.get_dataset(db, dataset_id, user)
    except (DatasetNotFoundError, DatasetAccessError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    points = dataset_service.get_points(db, dataset, limit=20000)
    if not points:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="dataset has no metric points to export",
        )
    series = analytics_service.resample(points, dataset.granularity)

    if ext == "csv":
        buffer = report_service.to_csv(dataset, series)
    elif ext == "xlsx":
        buffer = report_service.to_excel(dataset, series)
    else:
        buffer = report_service.to_pdf(dataset, series)

    filename = report_service.filename_for(dataset, ext)
    return StreamingResponse(
        buffer,
        media_type=_MEDIA_TYPES[ext],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
