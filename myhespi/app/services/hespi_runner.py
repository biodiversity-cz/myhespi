from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path

from ..config import Settings
from ..dwc import map_hespi_row_to_dwc, write_dwc_csv


class ProcessingTimeoutError(RuntimeError):
    pass


class ProcessingDependencyError(RuntimeError):
    def __init__(self, module_name: str):
        super().__init__(f"Missing runtime dependency: {module_name}")
        self.module_name = module_name


class ProcessingRuntimeError(RuntimeError):
    pass


def process_image(settings: Settings, input_image: Path, job_dir: Path, job_id: str) -> dict:
    job_dir.mkdir(parents=True, exist_ok=True)

    def _run_hespi():
        # Lazy import keeps test collection lightweight when full HESPI
        # runtime dependencies are not installed.
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
            raise ProcessingTimeoutError("HESPI processing exceeded timeout.") from exc
        except ProcessingDependencyError:
            raise
        except Exception as exc:
            raise ProcessingRuntimeError(str(exc) or exc.__class__.__name__) from exc

    first_row = {}
    if len(df.index) > 0:
        first_row = df.iloc[0].to_dict()

    dwc_record = map_hespi_row_to_dwc(first_row)
    dwc_csv_path = job_dir / "dwc.csv"
    write_dwc_csv(dwc_csv_path, dwc_record)

    text_segments = _row_segments(first_row)
    image_segments = _collect_segments(job_dir)
    segments = _merge_segments(text_segments, image_segments, job_id)
    payload = {
        "job_id": job_id,
        "status": "completed",
        "input_image_url": f"/api/v1/jobs/{job_id}/files/{input_image.name}",
        "segments": segments,
        "dwc": dwc_record.to_dict(),
        "exports": {
            "dwc_csv_url": f"/api/v1/jobs/{job_id}/export/dwc.csv",
            "dwca_zip_url": None,
        },
    }
    return payload


def _collect_segments(job_dir: Path) -> list[dict]:
    segments = []
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    for image_path in sorted(job_dir.rglob("*")):
        if not image_path.is_file():
            continue
        if image_path.suffix.lower() not in allowed_suffixes:
            continue
        if image_path.name.lower().startswith("input"):
            continue
        relative = image_path.relative_to(job_dir).as_posix()
        label = image_path.stem.split(".")[-1].replace("_", " ").replace("-", " ")
        segments.append(
            {
                "label": label,
                "text": "",
                "image_path": relative,
            }
        )
        if len(segments) >= 50:
            break
    return segments


def _row_segments(row: dict) -> list[dict]:
    ignored = {"id", "predictions", "label_classification"}
    segments = []
    for key, value in row.items():
        if key in ignored or key.endswith("_match_score"):
            continue
        text = "" if value is None else str(value).strip()
        if not text:
            continue
        segments.append({"label": key, "text": text, "image_url": None})
    return segments


def _merge_segments(text_segments: list[dict], image_segments: list[dict], job_id: str) -> list[dict]:
    by_label = {segment["label"]: dict(segment) for segment in text_segments}

    for image_segment in image_segments:
        label = image_segment["label"]
        image_path = image_segment["image_path"]
        image_url = f"/api/v1/jobs/{job_id}/files/{image_path}"
        if label in by_label:
            by_label[label]["image_url"] = image_url
            by_label[label]["image_path"] = image_path
        else:
            by_label[label] = {"label": label, "text": "", "image_url": image_url, "image_path": image_path}

    return list(by_label.values())
