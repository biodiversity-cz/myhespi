from __future__ import annotations

import math
import shutil
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path

from werkzeug.utils import secure_filename

from ..config import Settings
from ..dwc import map_hespi_row_to_dwc, write_dwc_csv
from ..services.storage import get_job_dir, save_result


_LABEL_FIELDS = (
    "family", "genus", "species", "infrasp_taxon", "authority",
    "collector_number", "collector", "locality", "geolocation",
    "year", "month", "day",
)

_LABEL_FIELDS_SET = frozenset(_LABEL_FIELDS)


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
        dwc_records.append(map_hespi_row_to_dwc(row).to_dict())

    primary_idx = 0
    primary_dwc = dwc_records[primary_idx] if dwc_records else {}

    if primary_dwc:
        write_dwc_csv(job_dir / "dwc.csv", map_hespi_row_to_dwc(all_rows[primary_idx]))

    primary_row = all_rows[primary_idx] if all_rows else {}
    text_segments = _row_segments(primary_row)
    image_segments = _collect_segments(job_dir)
    segments = _merge_segments(text_segments, image_segments)

    structured = _collect_structured_images(job_dir)

    intermediates_per_row = [_extract_intermediates(row) for row in all_rows]

    return {
        "job_id": job_id,
        "status": "completed",
        "input_image": input_image.name,
        "primary_row_index": primary_idx,
        "all_rows": all_rows,
        "dwc_per_row": dwc_records,
        "dwc": primary_dwc,
        "segments": segments,
        "structured_images": structured,
        "intermediates": intermediates_per_row[primary_idx] if intermediates_per_row else {},
        "intermediates_per_row": intermediates_per_row,
    }


# ── Web preview ──────────────────────────────────────────────────

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


# ── Sanitization ─────────────────────────────────────────────────

def _sanitize_value(value):
    """Convert a single value to a JSON-safe type."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return ""
        return value
    # numpy scalar types from pandas row.to_dict() are not JSON-serializable
    if (getattr(type(value), "__module__", "") or "").startswith("numpy") and hasattr(value, "item"):
        try:
            v = value.item()
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return ""
            return v
        except (ValueError, AttributeError):
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


# ── HESPI intermediates extraction ───────────────────────────────

def _flat_text(value) -> str:
    """Collapse a value (possibly a list) into a single string."""
    if isinstance(value, list):
        return " | ".join(str(v) for v in value if v)
    if not value:
        return ""
    return str(value).strip()


def _extract_intermediates(row: dict) -> dict:
    """Build a namespaced dict of HESPI intermediates for CSV export.

    Keys use the convention: hespi:{field}, hespiTrOCR:{field}, hespiTesseract:{field}.
    """
    result: dict[str, str] = {
        "hespi:labelClassification": _flat_text(row.get("label_classification")),
    }

    for field in _LABEL_FIELDS:
        result[f"hespi:{field}"] = _flat_text(row.get(field))
        result[f"hespiTrOCR:{field}"] = (
            _flat_text(row.get(f"{field}_TrOCR_adjusted"))
            or _flat_text(row.get(f"{field}_TrOCR_original"))
        )
        result[f"hespiTesseract:{field}"] = (
            _flat_text(row.get(f"{field}_Tesseract_adjusted"))
            or _flat_text(row.get(f"{field}_Tesseract_original"))
        )

    return result


# ── Structured image collection ───────────────────────────────────

def _collect_structured_images(job_dir: Path) -> dict:
    """Walk the HESPI output tree and return images grouped by role.

    Returns dict with keys:
      sheet_segmentation  – path to {stub}.all.jpg (bbox-annotated sheet)
      sheet_components    – list of {label, image_path} for cropped sheet parts
                            (excluding primary specimen labels)
      labels              – list of dicts per primary specimen label:
                            {image_path, segmentation_path, field_segments}
                            where field_segments is [{label, image_path}, ...]
    """
    result: dict = {
        "sheet_segmentation": "",
        "sheet_components": [],
        "labels": [],
    }

    allowed = {".jpg", ".jpeg", ".png"}

    for stub_dir in sorted(job_dir.iterdir()):
        if not stub_dir.is_dir():
            continue

        stub = stub_dir.name
        sheet_seg = stub_dir / f"{stub}.all.jpg"
        if sheet_seg.exists():
            result["sheet_segmentation"] = sheet_seg.relative_to(job_dir).as_posix()

        for img in sorted(stub_dir.iterdir()):
            if not img.is_file() or img.suffix.lower() not in allowed:
                continue
            if img.name.endswith((".all.jpg", ".thumbnail.jpg", ".medium.jpg")):
                continue

            rel = img.relative_to(job_dir).as_posix()
            label = img.stem.split(".")[-1].replace("_", " ").replace("-", " ")

            if "primary specimen label" in label.lower():
                label_stub_dir = stub_dir / _stem_no_ext(img)
                label_entry = {
                    "label": label,
                    "image_path": rel,
                    "segmentation_path": "",
                    "field_segments": [],
                }

                if label_stub_dir.is_dir():
                    label_stub = label_stub_dir.name
                    seg_img = label_stub_dir / f"{label_stub}.all.jpg"
                    if seg_img.exists():
                        label_entry["segmentation_path"] = seg_img.relative_to(job_dir).as_posix()

                    for field_img in sorted(label_stub_dir.iterdir()):
                        if not field_img.is_file() or field_img.suffix.lower() not in allowed:
                            continue
                        if field_img.name.endswith((".all.jpg", ".thumbnail.jpg", ".medium.jpg")):
                            continue
                        field_label = field_img.stem.split(".")[-1].replace("_", " ").replace("-", " ")
                        label_entry["field_segments"].append({
                            "label": field_label,
                            "image_path": field_img.relative_to(job_dir).as_posix(),
                        })

                result["labels"].append(label_entry)
            else:
                result["sheet_components"].append({
                    "label": label,
                    "image_path": rel,
                })

    return result


def _stem_no_ext(path: Path) -> str:
    """Return filename without the last extension: 'a.b.jpg' -> 'a.b'."""
    name = path.name
    dot = name.rfind(".")
    return name[:dot] if dot > 0 else name


# ── Segments ─────────────────────────────────────────────────────

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
    """Extract only main label field values as text segments (no intermediates)."""
    segments: list[dict] = []
    for field in _LABEL_FIELDS:
        value = row.get(field)
        text = "" if value is None else str(value).strip()
        if not text:
            continue
        label = field.replace("_", " ")
        segments.append({"label": label, "text": text})
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
