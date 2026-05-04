"""Tests for Method C: Hybrid digitizer."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from backend.digitizers.hybrid import HybridDigitizer
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


def test_hybrid_circles(tmp_path: Path):
    """Should use blob path (fast) for circles."""
    cfg = PlotConfig(n_points=20, marker="o", marker_size="medium", seed=2, label="hybrid_circle")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = HybridDigitizer()
    result = detector.digitize(img, cal)

    assert "hybrid" in result.method
    assert len(result.points) > 0

    pred_x = np.array([p.x_data for p in result.points])
    pred_y = np.array([p.y_data for p in result.points])

    score = score_predictions(
        pred_x, pred_y,
        np.array(gt["x"]), np.array(gt["y"]),
        tuple(gt["x_range"]), tuple(gt["y_range"]),
        tolerance_pct=2.0,
    )
    assert score.matched_pct >= 80.0


def test_hybrid_triangles(tmp_path: Path):
    """Should fall back to template for triangles where blob fails."""
    cfg = PlotConfig(n_points=20, marker="^", marker_size="medium", seed=6, label="hybrid_triangle")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = HybridDigitizer()
    result = detector.digitize(img, cal)

    pred_x = np.array([p.x_data for p in result.points])
    pred_y = np.array([p.y_data for p in result.points])

    score = score_predictions(
        pred_x, pred_y,
        np.array(gt["x"]), np.array(gt["y"]),
        tuple(gt["x_range"]), tuple(gt["y_range"]),
        tolerance_pct=2.0,
    )
    assert score.matched_pct >= 50.0, f"Hybrid on triangles only {score.matched_pct}%"


def test_hybrid_challenge(tmp_path: Path):
    """Should handle the adversarial challenge plot."""
    cfg = PlotConfig(
        n_points=50, marker="^", marker_size="small", opacity=0.7,
        grid=True, bg_color="lightgray", seed=20, label="hybrid_challenge"
    )
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = HybridDigitizer()
    result = detector.digitize(img, cal)

    assert len(result.points) > 0
