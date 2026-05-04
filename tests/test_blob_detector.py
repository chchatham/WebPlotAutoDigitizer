"""Tests for Method A: Blob Detection digitizer.

Runs against the baseline test suite and records results.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from backend.digitizers.blob_detector import BlobDetector
from backend.models import AxisCalibration, DetectionBounds
from tests.eval_digitizer import score_predictions
from tests.generate_plots import PlotConfig, generate_plot, FIXED_DPI, FIXED_FIGSIZE


def _make_calibration_from_gt(gt: dict, image: np.ndarray) -> AxisCalibration:
    """Build a 'perfect' calibration from ground truth for testing the digitizer alone.

    Uses matplotlib's default margins to estimate pixel ranges.
    """
    h, w = image.shape[:2]
    # matplotlib default: ~12.5% left margin, ~5% right, ~10% top, ~12% bottom (approx)
    x_min_px = w * 0.125
    x_max_px = w * 0.9
    y_min_px = h * 0.88  # bottom of plot (higher pixel y)
    y_max_px = h * 0.11  # top of plot (lower pixel y)

    return AxisCalibration(
        x_pixel_range=(x_min_px, x_max_px),
        y_pixel_range=(y_min_px, y_max_px),
        x_data_range=tuple(gt["x_range"]),
        y_data_range=tuple(gt["y_range"]),
    )


def test_blob_detector_basic(tmp_path: Path):
    cfg = PlotConfig(n_points=10, marker="o", marker_size="large", seed=42, label="blob_basic")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = BlobDetector()
    result = detector.digitize(img, cal)

    assert result.method == "blob"
    assert result.elapsed_ms > 0
    assert len(result.points) > 0


def test_blob_detector_circle_medium(tmp_path: Path):
    cfg = PlotConfig(n_points=20, marker="o", marker_size="medium", seed=2, label="blob_circle")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = BlobDetector()
    result = detector.digitize(img, cal)

    pred_x = np.array([p.x_data for p in result.points])
    pred_y = np.array([p.y_data for p in result.points])

    score = score_predictions(
        pred_x, pred_y,
        np.array(gt["x"]), np.array(gt["y"]),
        tuple(gt["x_range"]), tuple(gt["y_range"]),
        tolerance_pct=2.0,
    )

    assert score.matched_pct >= 50.0, f"Only matched {score.matched_pct}% of points"


def test_blob_detector_sparse(tmp_path: Path):
    cfg = PlotConfig(n_points=5, marker="o", marker_size="large", seed=1, label="blob_sparse")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = BlobDetector()
    result = detector.digitize(img, cal)

    pred_x = np.array([p.x_data for p in result.points])
    pred_y = np.array([p.y_data for p in result.points])

    score = score_predictions(
        pred_x, pred_y,
        np.array(gt["x"]), np.array(gt["y"]),
        tuple(gt["x_range"]), tuple(gt["y_range"]),
        tolerance_pct=3.0,
    )

    assert score.matched_pct >= 40.0, f"Only matched {score.matched_pct}% of sparse points"


def test_blob_detector_returns_detection_result(tmp_path: Path):
    cfg = PlotConfig(n_points=15, seed=7, label="blob_result")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    detector = BlobDetector()
    result = detector.digitize(img, cal)

    for p in result.points:
        assert hasattr(p, "x_data")
        assert hasattr(p, "y_data")
        assert hasattr(p, "x_pixel")
        assert hasattr(p, "y_pixel")
        assert 0.0 <= p.confidence <= 1.0


def test_blob_detector_with_detection_bounds(tmp_path: Path):
    cfg = PlotConfig(n_points=20, marker="o", marker_size="large", seed=42, label="blob_bounds")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    h, w = img.shape[:2]
    bounds = DetectionBounds(
        x_min_px=w * 0.05,
        x_max_px=w * 0.95,
        y_min_px=h * 0.05,
        y_max_px=h * 0.95,
    )

    detector = BlobDetector()
    result_with_bounds = detector.digitize(img, cal, bounds)
    result_without = detector.digitize(img, cal)

    assert len(result_with_bounds.points) >= len(result_without.points)


def test_blob_detector_narrow_bounds_restricts(tmp_path: Path):
    cfg = PlotConfig(n_points=20, marker="o", marker_size="large", seed=42, label="blob_narrow")
    out = generate_plot(cfg, tmp_path)

    img = np.array(Image.open(out.image_path).convert("RGB"))
    gt = json.loads(out.json_path.read_text())
    cal = _make_calibration_from_gt(gt, img)

    h, w = img.shape[:2]
    narrow = DetectionBounds(
        x_min_px=w * 0.4,
        x_max_px=w * 0.6,
        y_min_px=h * 0.4,
        y_max_px=h * 0.6,
    )

    detector = BlobDetector()
    result_narrow = detector.digitize(img, cal, narrow)
    result_full = detector.digitize(img, cal)

    assert len(result_narrow.points) <= len(result_full.points)
