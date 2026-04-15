"""Tests for post-upload image resize."""

import importlib.util
from pathlib import Path

from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]
_ir_spec = importlib.util.spec_from_file_location(
    "myhespi.image_resize",
    _ROOT / "myhespi" / "image_resize.py",
)
assert _ir_spec and _ir_spec.loader
_image_resize = importlib.util.module_from_spec(_ir_spec)
_ir_spec.loader.exec_module(_image_resize)
resize_upload_if_needed = _image_resize.resize_upload_if_needed


def test_resize_scales_down_longer_side(tmp_path):
    path = tmp_path / "big.jpg"
    Image.new("RGB", (3200, 800), color="white").save(path, "JPEG")

    resize_upload_if_needed(path, 2560)

    with Image.open(path) as im:
        w, h = im.size
    assert max(w, h) == 2560
    assert min(w, h) == 640


def test_resize_skips_when_already_small(tmp_path):
    path = tmp_path / "small.jpg"
    Image.new("RGB", (800, 600), color="white").save(path, "JPEG")

    resize_upload_if_needed(path, 2560)

    with Image.open(path) as im:
        assert im.size == (800, 600)


def test_resize_noop_when_max_zero(tmp_path):
    path = tmp_path / "big.jpg"
    Image.new("RGB", (4000, 4000), color="white").save(path, "JPEG")

    resize_upload_if_needed(path, 0)

    with Image.open(path) as im:
        assert im.size == (4000, 4000)
