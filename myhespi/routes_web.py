from __future__ import annotations

import logging
import traceback

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from .config import ALLOWED_MIME_TYPES
from .errors import handle_errors
from .services.hespi_runner import (
    ProcessingDependencyError,
    ProcessingRuntimeError,
    ProcessingTimeoutError,
    run_processing,
)
from .services.storage import get_job_dir, load_result, new_job_id, safe_job_file

log = logging.getLogger(__name__)

web_bp = Blueprint("web", __name__)


def _web_error(status: int, message: str):
    return render_template("error.html", message=message), status


def _handle_processing_error(exc: Exception):
    if isinstance(exc, ProcessingTimeoutError):
        return _web_error(504, "Zpracování překročilo časový limit.")
    if isinstance(exc, ProcessingDependencyError):
        return _web_error(
            500,
            f"Chybí runtime závislost pro HESPI: {exc.module_name}. "
            "Doinstalujte plný HESPI runtime: pip install -r requirements-hespi.txt",
        )
    if isinstance(exc, ProcessingRuntimeError):
        return _web_error(500, f"Chyba při zpracování HESPI: {exc}")

    log.exception("Neočekávaná chyba při zpracování")
    detail = traceback.format_exception_only(type(exc), exc)[-1].strip()
    if current_app.debug:
        return _web_error(500, f"Neočekávaná chyba: {detail}")
    return _web_error(500, "Při zpracování došlo k neočekávané chybě.")


@web_bp.get("/")
def index():
    return render_template(
        "index.html",
        max_upload_mb=current_app.config["MYHESPI_MAX_UPLOAD_MB"],
    )


@web_bp.post("/process")
@handle_errors(_handle_processing_error)
def process_upload():
    image = request.files.get("image")
    if image is None:
        return _web_error(400, "Chybí vstupní obrázek.")
    if image.mimetype not in ALLOWED_MIME_TYPES:
        return _web_error(415, "Povolené formáty: JPEG, PNG, TIFF a JP2.")

    job_id = new_job_id()
    run_processing(
        settings=current_app.config["MYHESPI_SETTINGS"],
        image_file=image,
        job_id=job_id,
    )
    return redirect(url_for("web.result_page", job_id=job_id))


@web_bp.get("/jobs/<job_id>")
def result_page(job_id: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        payload = load_result(job_dir)
    except (ValueError, FileNotFoundError):
        return _web_error(404, "Výsledek nebyl nalezen.")

    _enrich_web_urls(payload, job_id)
    return render_template("result.html", payload=payload)


@web_bp.get("/jobs/<job_id>/export/dwc.csv")
def web_export_dwc_csv(job_id: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        csv_path = safe_job_file(job_dir, "dwc.csv")
    except ValueError:
        return _web_error(404, "Export nebyl nalezen.")

    if not csv_path.exists():
        return _web_error(404, "Export nebyl nalezen.")
    return send_file(
        csv_path, mimetype="text/csv", as_attachment=True, download_name="dwc.csv"
    )


@web_bp.get("/jobs/<job_id>/files/<path:filename>")
def get_job_file(job_id: str, filename: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        file_path = safe_job_file(job_dir, filename)
    except ValueError:
        return _web_error(404, "Soubor nebyl nalezen.")

    if not file_path.exists() or not file_path.is_file():
        return _web_error(404, "Soubor nebyl nalezen.")
    return send_file(file_path)


def _enrich_web_urls(payload: dict, job_id: str) -> None:
    """Add flask url_for-based URLs to segments and input image."""
    preview_name = payload.get("preview_image") or payload.get("input_image", "")
    if preview_name:
        payload["input_image_url"] = url_for(
            "web.get_job_file", job_id=job_id, filename=preview_name
        )

    for segment in payload.get("segments", []):
        image_path = segment.get("image_path")
        if image_path:
            segment["image_url"] = url_for(
                "web.get_job_file", job_id=job_id, filename=image_path
            )

    si = payload.get("structured_images", {})
    if si.get("sheet_segmentation"):
        si["sheet_segmentation_url"] = url_for(
            "web.get_job_file", job_id=job_id, filename=si["sheet_segmentation"]
        )
    for comp in si.get("sheet_components", []):
        if comp.get("image_path"):
            comp["image_url"] = url_for(
                "web.get_job_file", job_id=job_id, filename=comp["image_path"]
            )
    for lbl in si.get("labels", []):
        if lbl.get("image_path"):
            lbl["image_url"] = url_for(
                "web.get_job_file", job_id=job_id, filename=lbl["image_path"]
            )
        if lbl.get("segmentation_path"):
            lbl["segmentation_url"] = url_for(
                "web.get_job_file", job_id=job_id, filename=lbl["segmentation_path"]
            )
        for fs in lbl.get("field_segments", []):
            if fs.get("image_path"):
                fs["image_url"] = url_for(
                    "web.get_job_file", job_id=job_id, filename=fs["image_path"]
                )
