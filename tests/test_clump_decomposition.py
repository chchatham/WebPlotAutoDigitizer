"""Integration tests for overlap/clump scenarios across all digitizer methods.

Tests the existing HybridDigitizer on the new overlap test suite to establish
baseline performance, then will test ShapeAwareDetector once implemented.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend.digitizers.blob_detector import BlobDetector
from backend.digitizers.hybrid import HybridDigitizer
from backend.models import AxisCalibration
from tests.eval_digitizer import score_predictions_with_clumps
from tests.generate_plots import (
    PlotConfig, OverlapConfig, generate_plot, OVERLAP_CONFIGS,
)


def _make_calibration_from_gt(gt: dict, image: np.ndarray) -> AxisCalibration:
    h, w = image.shape[:2]
    return AxisCalibration(
        x_pixel_range=(w * 0.125, w * 0.9),
        y_pixel_range=(h * 0.88, h * 0.11),
        x_data_range=tuple(gt["x_range"]),
        y_data_range=tuple(gt["y_range"]),
    )


class TestHybridBaselineOnOverlaps:
    """Establish baseline performance of HybridDigitizer on overlap suite.

    These tests document how well the current system handles overlaps BEFORE
    the ShapeAwareDetector is added. They use lenient thresholds — the goal
    is to measure, not to pass at high rates (that's Phase 14's job).
    """

    def test_filled_20pct_overlap(self, tmp_path: Path):
        """20% overlap should be mostly detectable by existing methods."""
        cfg = OVERLAP_CONFIGS[0]  # ovl_01_filled_20pct
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = HybridDigitizer()
        result = detector.digitize(img, cal)

        pred_x = np.array([p.x_data for p in result.points])
        pred_y = np.array([p.y_data for p in result.points])

        score = score_predictions_with_clumps(
            pred_x, pred_y,
            np.array(gt["x"]), np.array(gt["y"]),
            tuple(gt["x_range"]), tuple(gt["y_range"]),
            marker_size=gt["params"]["marker_size"],
            tolerance_pct=2.0,
        )
        # Singletons should be well-detected regardless
        assert score.singleton_recall is None or score.singleton_recall >= 50.0

    def test_filled_50pct_overlap(self, tmp_path: Path):
        """50% overlap is harder — document baseline."""
        cfg = OVERLAP_CONFIGS[2]  # ovl_03_filled_50pct
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = HybridDigitizer()
        result = detector.digitize(img, cal)

        pred_x = np.array([p.x_data for p in result.points])
        pred_y = np.array([p.y_data for p in result.points])

        score = score_predictions_with_clumps(
            pred_x, pred_y,
            np.array(gt["x"]), np.array(gt["y"]),
            tuple(gt["x_range"]), tuple(gt["y_range"]),
            marker_size=gt["params"]["marker_size"],
            tolerance_pct=2.0,
        )
        # At least some points should be found
        assert score.matched_pct >= 20.0

    def test_hollow_30pct_overlap(self, tmp_path: Path):
        """Hollow circles with 30% overlap — document baseline."""
        cfg = OVERLAP_CONFIGS[10]  # ovl_11_hollow_30pct
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = HybridDigitizer()
        result = detector.digitize(img, cal)

        pred_x = np.array([p.x_data for p in result.points])
        pred_y = np.array([p.y_data for p in result.points])

        score = score_predictions_with_clumps(
            pred_x, pred_y,
            np.array(gt["x"]), np.array(gt["y"]),
            tuple(gt["x_range"]), tuple(gt["y_range"]),
            marker_size=gt["params"]["marker_size"],
            tolerance_pct=2.0,
        )
        assert score.matched_pct >= 15.0

    def test_gray_bg_overlap(self, tmp_path: Path):
        """Overlap on gray background."""
        cfg = OVERLAP_CONFIGS[15]  # ovl_16_gray_bg_filled_30pct
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = HybridDigitizer()
        result = detector.digitize(img, cal)

        pred_x = np.array([p.x_data for p in result.points])
        pred_y = np.array([p.y_data for p in result.points])

        score = score_predictions_with_clumps(
            pred_x, pred_y,
            np.array(gt["x"]), np.array(gt["y"]),
            tuple(gt["x_range"]), tuple(gt["y_range"]),
            marker_size=gt["params"]["marker_size"],
            tolerance_pct=2.0,
        )
        assert score.matched_pct >= 15.0


class TestBlobDetectorOnOverlaps:
    """Test blob detector specifically to understand its clump behavior."""

    def test_blob_counts_on_pairs(self, tmp_path: Path):
        """Check how many blobs the detector finds when pairs overlap at 30%."""
        cfg = PlotConfig(
            marker="o", marker_size="medium", seed=300, label="blob_pair_test",
            overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
        )
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = BlobDetector()
        result = detector.digitize(img, cal)

        n_expected = len(gt["x"])
        # Document: how many does blob find? (this informs Phase 14 design)
        ratio = len(result.points) / n_expected
        # We just need it to find _something_ — the exact threshold will improve with Phase 14
        assert len(result.points) >= 5


class TestOverlapSuiteGeneration:
    """Verify the full overlap suite can be generated without errors."""

    def test_all_overlap_configs_generate(self, tmp_path: Path):
        from tests.generate_plots import generate_overlap_suite
        results = generate_overlap_suite(tmp_path)
        assert len(results) == len(OVERLAP_CONFIGS)
        for r in results:
            assert r.image_path.exists()
            assert r.json_path.exists()
            gt = json.loads(r.json_path.read_text())
            assert len(gt["x"]) > 0
            assert len(gt["x"]) == len(gt["y"])


class TestShapeAwareOnOverlaps:
    """Integration tests for ShapeAwareDetector on overlap scenarios."""

    def _run_shape_aware(self, tmp_path: Path, cfg_index: int, tolerance: float = 2.0):
        from backend.digitizers.shape_aware import ShapeAwareDetector
        cfg = OVERLAP_CONFIGS[cfg_index]
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = ShapeAwareDetector()
        result = detector.digitize(img, cal)

        pred_x = np.array([p.x_data for p in result.points])
        pred_y = np.array([p.y_data for p in result.points])

        score = score_predictions_with_clumps(
            pred_x, pred_y,
            np.array(gt["x"]), np.array(gt["y"]),
            tuple(gt["x_range"]), tuple(gt["y_range"]),
            marker_size=gt["params"]["marker_size"],
            tolerance_pct=tolerance,
        )
        return score, result

    def test_filled_30pct_clump_recall(self, tmp_path: Path):
        """Measure clump recall on filled circles with 30% overlap."""
        score, _ = self._run_shape_aware(tmp_path, 1)  # ovl_02_filled_30pct
        # Target: 75% clump recall. Use lenient threshold during development.
        if score.clump_recall is not None:
            assert score.clump_recall >= 40.0, (
                f"Clump recall {score.clump_recall:.1f}% (target 75%)"
            )

    def test_filled_50pct_clump_recall(self, tmp_path: Path):
        """Measure clump recall on filled circles with 50% overlap."""
        score, _ = self._run_shape_aware(tmp_path, 2)  # ovl_03_filled_50pct
        if score.clump_recall is not None:
            assert score.clump_recall >= 30.0, (
                f"Clump recall {score.clump_recall:.1f}% (target 75%)"
            )

    def test_hollow_30pct_clump_recall(self, tmp_path: Path):
        """Measure clump recall on unfilled circles with 30% overlap."""
        score, _ = self._run_shape_aware(tmp_path, 10)  # ovl_11_hollow_30pct
        if score.clump_recall is not None:
            assert score.clump_recall >= 30.0, (
                f"Clump recall {score.clump_recall:.1f}% (target 85%)"
            )

    def test_singleton_recall_no_regression(self, tmp_path: Path):
        """Singleton recall must stay reasonable (>= 60%)."""
        score, _ = self._run_shape_aware(tmp_path, 0)  # ovl_01_filled_20pct
        if score.singleton_recall is not None:
            assert score.singleton_recall >= 60.0, (
                f"Singleton recall {score.singleton_recall:.1f}% (need 60%+)"
            )

    def test_point_count_hint_effect(self, tmp_path: Path):
        """Compare results with and without point count hint."""
        from backend.digitizers.shape_aware import ShapeAwareDetector
        cfg = OVERLAP_CONFIGS[27]  # ovl_28_hint_test_20pts
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)
        n_expected = len(gt["x"])

        detector = ShapeAwareDetector()
        result_no_hint = detector.digitize(img, cal)
        result_with_hint = detector.digitize(img, cal, expected_point_count=n_expected)

        # With hint should not crash and should produce a valid result
        assert len(result_with_hint.points) > 0
        # Document the difference (not a hard assertion yet)
        diff = len(result_with_hint.points) - len(result_no_hint.points)
        assert abs(diff) < n_expected  # sanity check

    def test_performance_under_10s(self, tmp_path: Path):
        """Full pipeline must complete in < 10 seconds."""
        _, result = self._run_shape_aware(tmp_path, 8)  # dense cluster
        assert result.elapsed_ms < 10000
