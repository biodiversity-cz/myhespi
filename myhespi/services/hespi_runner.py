from __future__ import annotations

import math
import shutil
import uuid as _uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path

from werkzeug.utils import secure_filename

from ..config import Settings
from ..dwc import map_hespi_row_to_dwc, write_dwc_csv
from ..services.storage import get_job_dir, save_result


class ProcessingTimeoutError(RuntimeError):
    pass


class ProcessingDependencyError(RuntimeError):
    def __init__(self, module_name: str):
        super().__init__(f"Missing runtime dependency: {module_name}")
        self.module_name = module_name


class ProcessingRuntimeError(RuntimeError):
    pass


def run_processing(settings: Settings, image_file, job_id: str) -> dict:
    """Create job directory, save uploaded file, run HESPI and persist the result.

    On any processing error the job directory is removed before re-raising.
    Returns the raw payload (without URL fields – callers add those).
    """
    job_dir = get_job_dir(settings.temp_root, job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    input_name = secure_filename(image_file.filename or "input.jpg") or "input.jpg"
    input_path = job_dir / input_name
    image_file.save(input_path)

    preview_path = _ensure_web_preview(input_path)

    try:
        payload = process_image(settings, input_path, job_dir, job_id)
        if preview_path != input_path:
            payload["preview_image"] = preview_path.name
        save_result(job_dir, payload)
        return payload
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise


def process_image(settings: Settings, input_image: Path, job_dir: Path, job_id: str) -> dict:
    """Run HESPI detection and build structured payload (no URLs)."""

    def _run_hespi():
        try:
            from hespi.hespi import Hespi
        except ModuleNotFoundError as exc:
            raise ProcessingDependencyError(exc.name or "unknown") from exc

        detector = Hespi(
            gpu=settings.hespi_use_gpu,
            llm_model=settings.hespi_llm_model,
            llm_api_key=settings.openai_api_key,
        )
        return detector.detect([input_image], output_dir=job_dir, report=False)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_hespi)
        try:
            df = future.result(timeout=settings.process_timeout_seconds)
        except FutureTimeoutError as exc:
            raise ProcessingTimeoutError(
                "Zpracování HESPI překročilo časový limit."
            ) from exc
        except ProcessingDependencyError:
            raise
        except Exception as exc:
            raise ProcessingRuntimeError(
                str(exc) or exc.__class__.__name__
            ) from exc

    all_rows: list[dict] = []
    if len(df.index) > 0:
        all_rows = [_sanitize_row(row.to_dict()) for _, row in df.iterrows()]

    dwc_records: list[dict] = []
    for row in all_rows:
        occ_id = f"urn:uuid:{_uuid.uuid4()}"
        dwc_records.append(map_hespi_row_to_dwc(row, occ_id).to_dict())

    primary_idx = 0
    primary_dwc = dwc_records[primary_idx] if dwc_records else {}

    if primary_dwc:
        write_dwc_csv(
            job_dir / "dwc.csv",
            map_hespi_row_to_dwc(
                all_rows[primary_idx], primary_dwc["occurrenceID"]
            ),
        )

    primary_row = all_rows[primary_idx] if all_rows else {}
    text_segments = _row_segments(primary_row)
    image_segments = _collect_segments(job_dir)
    segments = _merge_segments(text_segments, image_segments)

    return {
        "job_id": job_id,
        "status": "completed",
        "input_image": input_image.name,
        "primary_row_index": primary_idx,
        "all_rows": all_rows,
        "dwc_per_row": dwc_records,
        "dwc": primary_dwc,
        "segments": segments,
    }


_WEB_SAFE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _ensure_web_preview(input_path: Path) -> Path:
    """If the input image is not displayable in a browser (e.g. JP2, TIFF),
    convert it to JPEG.  Returns the path to the preview file (may be the
    original if no conversion was needed)."""
    if input_path.suffix.lower() in _WEB_SAFE_SUFFIXES:
        return input_path
    try:
        from PIL import Image

        preview_path = input_path.with_suffix(".preview.jpg")
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img.save(preview_path, "JPEG", quality=85)
        return preview_path
    except Exception:
        return input_path


def _sanitize_value(value):
    """Convert a single value to a JSON-safe type."""
    if value is None:
        return ""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    return value


def _sanitize_row(row: dict) -> dict:
    """Replace NaN, Path and other non-JSON-serializable values."""
    return {key: _sanitize_value(value) for key, value in row.items()}


def _collect_segments(job_dir: Path) -> list[dict]:
    segments: list[dict] = []
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    for image_path in sorted(job_dir.rglob("*")):
        if not image_path.is_file():
            continue
        if image_path.suffix.lower() not in allowed_suffixes:
            continue
        if image_path.name.lower().startswith("input"):
            continue
        if ".preview." in image_path.name.lower():
            continue
        relative = image_path.relative_to(job_dir).as_posix()
        label = image_path.stem.split(".")[-1].replace("_", " ").replace("-", " ")
        segments.append({"label": label, "text": "", "image_path": relative})
        if len(segments) >= 50:
            break
    return segments


def _row_segments(row: dict) -> list[dict]:
    ignored = {"id", "predictions", "label_classification"}
    segments: list[dict] = []
    for key, value in row.items():
        if key in ignored or key.endswith("_match_score"):
            continue
        text = "" if value is None else str(value).strip()
        if not text:
            continue
        segments.append({"label": key, "text": text})
    return segments


def _merge_segments(
    text_segments: list[dict], image_segments: list[dict]
) -> list[dict]:
    by_label: dict[str, dict] = {seg["label"]: dict(seg) for seg in text_segments}

    for img_seg in image_segments:
        label = img_seg["label"]
        if label in by_label:
            by_label[label]["image_path"] = img_seg["image_path"]
        else:
            by_label[label] = {
                "label": label,
                "text": "",
                "image_path": img_seg["image_path"],
            }

    return list(by_label.values())
