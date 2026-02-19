import shutil

from flask import Blueprint, current_app, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from .services.hespi_runner import (
    ProcessingDependencyError,
    ProcessingRuntimeError,
    ProcessingTimeoutError,
    process_image,
)
from .services.storage import get_job_dir, load_result, new_job_id, safe_job_file, save_result

web_bp = Blueprint("web", __name__)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/tiff", "image/jp2", "image/jpeg2000"}


@web_bp.get("/")
def index():
    return render_template(
        "index.html",
        max_upload_mb=current_app.config["MYHESPI_MAX_UPLOAD_MB"],
    )


@web_bp.post("/process")
def process_upload():
    image = request.files.get("image")
    if image is None:
        return render_template("error.html", message="Chybi vstupni obrazek."), 400
    if image.mimetype not in ALLOWED_MIME_TYPES:
        return render_template("error.html", message="Povolene jsou pouze JPEG, PNG, TIFF a JP2."), 415

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
        return redirect(url_for("web.result_page", job_id=job_id))
    except ProcessingTimeoutError:
        shutil.rmtree(job_dir, ignore_errors=True)
        return render_template("error.html", message="Zpracovani presahlo timeout 60 sekund."), 504
    except ProcessingDependencyError as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        return render_template(
            "error.html",
            message=(
                f"Chybi runtime zavislost pro HESPI: {exc.module_name}. "
                "Doinstaluj plny runtime: pip install -r myhespi/requirements-hespi.txt"
            ),
        ), 500
    except ProcessingRuntimeError as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        return render_template(
            "error.html",
            message=f"Chyba behem behu HESPI: {exc}",
        ), 500
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        return render_template("error.html", message="Pri zpracovani doslo k neocekavane chybe."), 500


@web_bp.get("/jobs/<job_id>")
def result_page(job_id: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        payload = load_result(job_dir)
    except (ValueError, FileNotFoundError):
        return render_template("error.html", message="Vysledek nebyl nalezen."), 404

    # Web UI uses a non-authenticated file endpoint for rendering images.
    for segment in payload.get("segments", []):
        image_path = segment.get("image_path")
        if image_path:
            segment["image_url"] = url_for("web.get_job_file", job_id=job_id, filename=image_path)

    return render_template("result.html", payload=payload)


@web_bp.get("/jobs/<job_id>/export/dwc.csv")
def web_export_dwc_csv(job_id: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        csv_path = safe_job_file(job_dir, "dwc.csv")
    except ValueError:
        return render_template("error.html", message="Export nebyl nalezen."), 404

    if not csv_path.exists():
        return render_template("error.html", message="Export nebyl nalezen."), 404
    return send_file(csv_path, mimetype="text/csv", as_attachment=True, download_name="dwc.csv")


@web_bp.get("/jobs/<job_id>/files/<path:filename>")
def get_job_file(job_id: str, filename: str):
    try:
        job_dir = get_job_dir(current_app.config["MYHESPI_TEMP_ROOT"], job_id)
        file_path = safe_job_file(job_dir, filename)
    except ValueError:
        return render_template("error.html", message="Soubor nebyl nalezen."), 404

    if not file_path.exists() or not file_path.is_file():
        return render_template("error.html", message="Soubor nebyl nalezen."), 404
    return send_file(file_path)
