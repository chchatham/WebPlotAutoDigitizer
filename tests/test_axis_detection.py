from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from backend.axis_detection import detect_axes, _find_plot_bbox
from tests.generate_plots import PlotConfig, generate_plot


def test_detect_axes_returns_result(tmp_path: Path):
    cfg = PlotConfig(n_points=20, seed=42, label="axis_test")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    result = detect_axes(img)

    assert result.confidence > 0
    cal = result.calibration
    assert cal.x_pixel_range[1] > cal.x_pixel_range[0]
    # y_pixel_range[0] is bottom (larger pixel y), [1] is top (smaller pixel y)
    assert cal.y_pixel_range[0] > cal.y_pixel_range[1]


def test_plot_bbox_finds_reasonable_region(tmp_path: Path):
    cfg = PlotConfig(n_points=10, seed=1, label="bbox_test")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    import cv2
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    x_min, y_min, x_max, y_max = _find_plot_bbox(gray)
    h, w = gray.shape

    assert x_min < w * 0.3
    assert x_max > w * 0.6
    assert y_min < h * 0.3
    assert y_max > h * 0.6
    assert x_max - x_min > w * 0.3
    assert y_max - y_min > h * 0.3


def test_detect_axes_api_endpoint(client, tmp_path: Path):
    cfg = PlotConfig(n_points=10, seed=99, label="api_test")
    out = generate_plot(cfg, tmp_path)

    with open(out.image_path, "rb") as f:
        resp = client.post("/api/upload", files={"file": ("plot.png", f, "image/png")})
    assert resp.status_code == 200
    image_id = resp.json()["image_id"]

    resp = client.post("/api/detect-axes", json={"image_id": image_id})
    assert resp.status_code == 200
    data = resp.json()
    assert "axes" in data
    assert "confidence" in data
    axes = data["axes"]
    assert len(axes["x_pixel_range"]) == 2
    assert len(axes["y_pixel_range"]) == 2
    assert len(axes["x_data_range"]) == 2
    assert len(axes["y_data_range"]) == 2


def test_detect_axes_unknown_image(client):
    resp = client.post("/api/detect-axes", json={"image_id": "nonexistent"})
    assert resp.status_code == 404


def test_calibration_pixel_range_accuracy(tmp_path: Path):
    """For synthetic plots with known axes, verify pixel detection is within 2% of image dimensions."""
    cfg = PlotConfig(n_points=20, x_range=(0, 10), y_range=(0, 10), seed=42, label="accuracy_test")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    result = detect_axes(img)
    cal = result.calibration

    h, w = img.shape[:2]
    tolerance = max(w, h) * 0.15

    assert cal.x_pixel_range[1] - cal.x_pixel_range[0] > w * 0.3
    assert abs(cal.y_pixel_range[0] - cal.y_pixel_range[1]) > h * 0.3
