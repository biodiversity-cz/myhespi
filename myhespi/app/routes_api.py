import shutil
from pathlib import Path

from flask import Blueprint, current_app, request, send_file
from werkzeug.utils import secure_filename

from .auth import api_error, require_api_token
from .services.hespi_runner import (
    ProcessingDependencyError,
    ProcessingRuntimeError,
    ProcessingTimeoutError,
    process_image,
)
from .services.storage import get_job_dir, load_result, new_job_id, safe_job_file, save_result

api_bp = Blueprint("api", __name__)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/tiff", "image/jp2", "image/jpeg2000"}


@api_bp.get("/openapi.yaml")
def openapi_spec():
    spec_path = Path(__file__).resolve().parents[1] / "openapi.yaml"
    return send_file(spec_path, mimetype="application/yaml")


@api_bp.get("/health")
@require_api_token
def health():
    return {"status": "ok"}, 200


@api_bp.post("/jobs")
@require_api_token
def create_job():
    image = request.files.get("image")
    if image is None:
        return api_error(400, "missing_image", "Missing required form field 'image'.")
    if image.mimetype not in ALLOWED_MIME_TYPES:
        return api_error(415, "unsupported_media_type", "Supported file types: JPEG, PNG, TIFF, JP2.")

    job_id = new_job_id()
    job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    input_name = secure_filename(image.filename or "input.jpg") or "input.jpg"
    input_path = job_dir / input_name
    image.save(input_path)

    try:
        payload = process_image(
            settings=current_app.config["MYHESPI_SETTINGS"],
            input_image=input_path,
            job_dir=job_dir,
            job_id=job_id,
        )
        save_result(job_dir, payload)
        return payload, 200
    except ProcessingTimeoutError:
        shutil.rmtree(job_dir, ignore_errors=True)
        return api_error(504, "processing_timeout", "HESPI processing exceeded timeout limit.")
    except ProcessingDependencyError as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        return api_error(
            500,
            "missing_runtime_dependency",
            "Required HESPI runtime dependency is missing.",
            details={
                "module": exc.module_name,
                "hint": "Install full runtime dependencies using: pip install -r myhespi/requirements-hespi.txt",
            },
        )
    except ProcessingRuntimeError as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        return api_error(
            500,
            "processing_runtime_error",
            "HESPI processing failed at runtime.",
            details={"reason": str(exc)},
        )
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        return api_error(500, "processing_failed", "Unexpected internal error during processing.")


@api_bp.get("/jobs/<job_id>")
@require_api_token
def get_job(job_id: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        payload = load_result(job_dir)
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
    return send_file(csv_path, mimetype="text/csv", as_attachment=True, download_name="dwc.csv")


@api_bp.get("/jobs/<job_id>/export/dwca.zip")
@require_api_token
def export_dwca_zip(job_id: str):
    return api_error(404, "export_not_found", "DwCA ZIP export is not implemented in v1.")


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

    return send_file(Path(file_path))
