"""Tests for clumped/overlapping point detection.

Includes both seeded (deterministic) and randomized (different each run) tests
to stress-test the digitizer's ability to separate adjacent markers.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from backend.digitizers.blob_detector import BlobDetector
from backend.digitizers.hybrid import HybridDigitizer
from backend.models import AxisCalibration
from tests.eval_digitizer import score_predictions
from tests.generate_plots import (
    PlotConfig, ClumpSpec, generate_plot,
    CLUMP_CONFIGS, RANDOM_CLUMP_CONFIGS,
)


def _make_calibration_from_gt(gt: dict, image: np.ndarray) -> AxisCalibration:
    h, w = image.shape[:2]
    return AxisCalibration(
        x_pixel_range=(w * 0.125, w * 0.9),
        y_pixel_range=(h * 0.88, h * 0.11),
        x_data_range=tuple(gt["x_range"]),
        y_data_range=tuple(gt["y_range"]),
    )


def _run_detection_test(
    tmp_path: Path,
    cfg: PlotConfig,
    clump: ClumpSpec,
    min_pct: float = 40.0,
    tolerance: float = 3.0,
) -> float:
    out = generate_plot(cfg, tmp_path, clump=clump)
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
        tolerance_pct=tolerance,
    )
    assert score.matched_pct >= min_pct, (
        f"Clump test '{cfg.label}': only {score.matched_pct}% matched "
        f"(need {min_pct}%), {score.false_negatives} missed, {score.false_positives} FP"
    )
    return score.matched_pct


class TestSeededClumps:
    def test_clump_circles(self, tmp_path: Path):
        cfg, clump = CLUMP_CONFIGS[0]
        _run_detection_test(tmp_path, cfg, clump, min_pct=40.0)

    def test_clump_small_markers(self, tmp_path: Path):
        cfg, clump = CLUMP_CONFIGS[1]
        _run_detection_test(tmp_path, cfg, clump, min_pct=30.0)

    def test_clump_tight_large(self, tmp_path: Path):
        cfg, clump = CLUMP_CONFIGS[2]
        _run_detection_test(tmp_path, cfg, clump, min_pct=25.0)

    def test_clump_squares(self, tmp_path: Path):
        cfg, clump = CLUMP_CONFIGS[3]
        _run_detection_test(tmp_path, cfg, clump, min_pct=30.0)

    def test_clump_grid(self, tmp_path: Path):
        cfg, clump = CLUMP_CONFIGS[4]
        _run_detection_test(tmp_path, cfg, clump, min_pct=25.0)


class TestBlobSplitting:
    def test_blob_splits_merged_circles(self, tmp_path: Path):
        cfg = PlotConfig(n_points=12, marker="o", marker_size="large", seed=70, label="blob_split")
        clump = ClumpSpec(n_clumps=3, points_per_clump=4, clump_radius_pct=0.8)
        out = generate_plot(cfg, tmp_path, clump=clump)

        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        blob = BlobDetector()
        result = blob.digitize(img, cal)

        assert len(result.points) >= 3, (
            f"Blob should detect at least 3 blobs from 3 clumps, got {len(result.points)}"
        )


class TestRandomizedClumps:
    """Randomized each run — exercises the detector on fresh data every time."""

    def test_random_clump_detection(self, tmp_path: Path):
        results = []
        for cfg, clump in RANDOM_CLUMP_CONFIGS:
            out = generate_plot(cfg, tmp_path, clump=clump)
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
                tolerance_pct=3.0,
            )
            results.append(score.matched_pct)

        avg = sum(results) / len(results)
        assert avg >= 25.0, (
            f"Average detection on random clumps: {avg:.1f}% (need 25%+). "
            f"Individual: {[f'{r:.0f}%' for r in results]}"
        )

    def test_random_scatter_baseline(self, tmp_path: Path):
        from tests.generate_plots import RANDOM_SCATTER_CONFIGS
        results = []
        for cfg in RANDOM_SCATTER_CONFIGS:
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
            results.append(score.matched_pct)

        avg = sum(results) / len(results)
        assert avg >= 50.0, (
            f"Average detection on random scatter: {avg:.1f}% (need 50%+). "
            f"Individual: {[f'{r:.0f}%' for r in results]}"
        )
