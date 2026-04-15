"""Downscale uploaded raster images before HESPI processing."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def resize_upload_if_needed(path: Path, max_long_side: int) -> None:
    """Downscale image so max(width, height) <= max_long_side; overwrites path.

    On Pillow errors, multi-page image, or max_long_side <= 0, leaves file unchanged.
    """
    if max_long_side <= 0:
        return
    try:
        from PIL import Image, ImageOps
    except ImportError:
        log.warning("Pillow není k dispozici, resize se přeskočí.")
        return

    try:
        with Image.open(path) as im:
            im.load()
            if getattr(im, "n_frames", 1) > 1:
                log.warning(
                    "Vícestránkový obrázek (%s), resize se přeskočí.", path.name
                )
                return
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            if max(w, h) <= max_long_side:
                return
            scale = max_long_side / float(max(w, h))
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:  # Pillow < 9.1
                resample = Image.LANCZOS
            out = im.resize((new_w, new_h), resample)

        tmp = path.with_name(f"{path.stem}.resizing{path.suffix}")
        ext = path.suffix.lower()
        try:
            if ext in {".jpg", ".jpeg"}:
                out.convert("RGB").save(tmp, "JPEG", quality=92, optimize=True)
            elif ext == ".png":
                out.save(tmp, "PNG", optimize=True)
            elif ext in {".tif", ".tiff"}:
                out.save(tmp, "TIFF")
            elif ext in {".jp2", ".j2k"}:
                out.save(tmp, "JPEG2000", quality_mode="lossy")
            else:
                out.convert("RGB").save(tmp, "JPEG", quality=92, optimize=True)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
        tmp.replace(path)
    except Exception as exc:
        log.warning(
            "Resize obrázku se nepovedl (%s), pokračuji s původním souborem: %s",
            path.name,
            exc,
        )
