"""Tests for Method B: Template Matching digitizer."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from backend.digitizers.template_matcher import TemplateMatcher
from backend.models import AxisCalibration
from tests.eval_digitizer import score_predictions
from tests.generate_plots import PlotConfig, generate_plot


def _make_calibration_from_gt(gt: dict, image: np.ndarray) -> AxisCalibration:
    h, w = image.shape[:2]
    return AxisCalibration(
        x_pixel_range=(w * 0.125, w * 0.9),
        y_pixel_range=(h * 0.88, h * 0.11),
        x_data_range=tuple(gt["x_range"]),
        y_data_range=tuple(gt["y_range"]),
    )


def test_template_matcher_basic(tmp_path: Path):
    cfg = PlotConfig(n_points=10, marker="o", marker_size="large", seed=42, label="tmpl_basic")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = TemplateMatcher()
    result = detector.digitize(img, cal)

    assert result.method == "template"
    assert result.elapsed_ms > 0
    assert len(result.points) > 0


def test_template_matcher_circles(tmp_path: Path):
    cfg = PlotConfig(n_points=20, marker="o", marker_size="medium", seed=2, label="tmpl_circle")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = TemplateMatcher()
    result = detector.digitize(img, cal)

    pred_x = np.array([p.x_data for p in result.points])
    pred_y = np.array([p.y_data for p in result.points])

    score = score_predictions(
        pred_x, pred_y,
        np.array(gt["x"]), np.array(gt["y"]),
        tuple(gt["x_range"]), tuple(gt["y_range"]),
        tolerance_pct=2.0,
    )

    assert score.matched_pct >= 40.0, f"Only matched {score.matched_pct}%"


def test_template_matcher_triangles(tmp_path: Path):
    """Method B should handle triangles better than Method A."""
    cfg = PlotConfig(n_points=20, marker="^", marker_size="medium", seed=6, label="tmpl_triangle")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = TemplateMatcher()
    result = detector.digitize(img, cal)

    assert len(result.points) > 0


def test_template_matcher_returns_detection_result(tmp_path: Path):
    cfg = PlotConfig(n_points=15, seed=7, label="tmpl_result")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = TemplateMatcher()
    result = detector.digitize(img, cal)

    for p in result.points:
        assert 0.0 <= p.confidence <= 1.0
