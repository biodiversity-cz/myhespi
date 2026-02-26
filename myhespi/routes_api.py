from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, request, send_file

from .auth import api_error, require_api_token
from .config import ALLOWED_MIME_TYPES
from .errors import handle_errors
from .services.hespi_runner import (
    ProcessingDependencyError,
    ProcessingRuntimeError,
    ProcessingTimeoutError,
    run_processing,
)
from .services.storage import get_job_dir, load_result, new_job_id, safe_job_file

api_bp = Blueprint("api", __name__)


def _handle_processing_error(exc: Exception):
    if isinstance(exc, ProcessingTimeoutError):
        return api_error(
            504, "processing_timeout", "HESPI processing exceeded timeout limit."
        )
    if isinstance(exc, ProcessingDependencyError):
        return api_error(
            500,
            "missing_runtime_dependency",
            "Required HESPI runtime dependency is missing.",
            details={"module": exc.module_name},
        )
    if isinstance(exc, ProcessingRuntimeError):
        return api_error(
            500,
            "processing_runtime_error",
            "HESPI processing failed at runtime.",
            details={"reason": str(exc)},
        )
    return api_error(
        500, "processing_failed", "Unexpected internal error during processing."
    )


@api_bp.get("/openapi.yaml")
def openapi_spec():
    spec_path = Path(__file__).resolve().parent / "openapi.yaml"
    return send_file(spec_path, mimetype="application/yaml")


@api_bp.get("/health")
@require_api_token
def health():
    return {"status": "ok"}, 200


@api_bp.post("/jobs")
@require_api_token
@handle_errors(_handle_processing_error)
def create_job():
    image = request.files.get("image")
    if image is None:
        return api_error(400, "missing_image", "Missing required form field 'image'.")
    if image.mimetype not in ALLOWED_MIME_TYPES:
        return api_error(
            415,
            "unsupported_media_type",
            "Supported file types: JPEG, PNG, TIFF, JP2.",
        )

    job_id = new_job_id()
    payload = run_processing(
        settings=current_app.config["MYHESPI_SETTINGS"],
        image_file=image,
        job_id=job_id,
    )
    _enrich_api_urls(payload, job_id)
    return payload, 200


@api_bp.get("/jobs/<job_id>")
@require_api_token
def get_job(job_id: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        payload = load_result(job_dir)
        _enrich_api_urls(payload, job_id)
        return payload, 200
    except (ValueError, FileNotFoundError):
        return api_error(404, "job_not_found", "Requested job was not found.")


@api_bp.get("/jobs/<job_id>/export/dwc.csv")
@require_api_token
def export_dwc_csv(job_id: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        csv_path = safe_job_file(job_dir, "dwc.csv")
    except ValueError:
        return api_error(404, "job_not_found", "Requested job was not found.")

    if not csv_path.exists():
        return api_error(404, "export_not_found", "DwC CSV export is not available.")
    return send_file(
        csv_path, mimetype="text/csv", as_attachment=True, download_name="dwc.csv"
    )


@api_bp.get("/jobs/<job_id>/export/dwca.zip")
@require_api_token
def export_dwca_zip(job_id: str):
    return api_error(
        404, "export_not_found", "DwCA ZIP export is not implemented in v1."
    )


@api_bp.get("/jobs/<job_id>/files/<path:filename>")
@require_api_token
def get_job_file(job_id: str, filename: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        file_path = safe_job_file(job_dir, filename)
    except ValueError:
        return api_error(404, "file_not_found", "Requested file was not found.")

    if not file_path.exists() or not file_path.is_file():
        return api_error(404, "file_not_found", "Requested file was not found.")

    return send_file(file_path)


def _enrich_api_urls(payload: dict, job_id: str) -> None:
    """Add /api/v1/ prefixed URLs to segments and exports."""
    preview_name = payload.get("preview_image") or payload.get("input_image", "")
    if preview_name:
        payload["input_image_url"] = (
            f"/api/v1/jobs/{job_id}/files/{preview_name}"
        )

    payload["exports"] = {
        "dwc_csv_url": f"/api/v1/jobs/{job_id}/export/dwc.csv",
        "dwca_zip_url": None,
    }

    for segment in payload.get("segments", []):
        path = segment.get("image_path")
        if path:
            segment["image_url"] = f"/api/v1/jobs/{job_id}/files/{path}"
