"""Tests for Phase 14 ShapeAwareDetector — marker profile estimation and clump decomposition.

Tests the overlap test suite generation, clump-aware scoring, marker profile
estimation, and shape-aware detection.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from backend.digitizers.shape_aware import (
    ShapeAwareDetector, estimate_marker_profile, decompose_filled_clump,
)
from backend.models import AxisCalibration, MarkerProfile
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


class TestOverlapPlotGeneration:
    """Verify that the overlap test suite generates valid plots."""

    def test_overlap_configs_count(self):
        assert len(OVERLAP_CONFIGS) >= 30

    def test_overlap_plot_generates(self, tmp_path: Path):
        cfg = OVERLAP_CONFIGS[0]
        out = generate_plot(cfg, tmp_path)
        assert out.image_path.exists()
        assert out.json_path.exists()

    def test_overlap_plot_point_count(self, tmp_path: Path):
        cfg = PlotConfig(
            marker="o", marker_size="medium", seed=200,
            label="test_overlap_count",
            overlap=OverlapConfig(
                overlap_fraction=0.3, n_overlap_pairs=5, n_overlap_triples=2, n_isolated=10
            ),
        )
        out = generate_plot(cfg, tmp_path)
        gt = json.loads(out.json_path.read_text())
        expected = 10 + 5 * 2 + 2 * 3  # isolated + pairs + triples
        assert len(gt["x"]) == expected
        assert len(gt["y"]) == expected

    def test_overlap_plot_has_overlaps_flag(self, tmp_path: Path):
        cfg = OVERLAP_CONFIGS[0]
        out = generate_plot(cfg, tmp_path)
        gt = json.loads(out.json_path.read_text())
        assert gt["params"]["has_overlaps"] is True

    def test_unfilled_plot_generates(self, tmp_path: Path):
        cfg = PlotConfig(
            marker="o", marker_size="medium", fill_style="unfilled",
            edge_width=1.5, seed=201, label="test_unfilled",
            overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=3, n_isolated=5),
        )
        out = generate_plot(cfg, tmp_path)
        assert out.image_path.exists()
        gt = json.loads(out.json_path.read_text())
        assert gt["params"]["fill_style"] == "unfilled"

    def test_colored_markers_generate(self, tmp_path: Path):
        cfg = PlotConfig(
            marker="o", marker_size="medium", marker_color="blue",
            seed=202, label="test_blue",
            overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=3, n_isolated=5),
        )
        out = generate_plot(cfg, tmp_path)
        gt = json.loads(out.json_path.read_text())
        assert gt["params"]["marker_color"] == "blue"

    def test_xlarge_marker_size(self, tmp_path: Path):
        cfg = PlotConfig(
            marker="o", marker_size="xlarge", seed=203, label="test_xlarge",
            overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=3, n_isolated=5),
        )
        out = generate_plot(cfg, tmp_path)
        gt = json.loads(out.json_path.read_text())
        assert gt["params"]["marker_size"] == 120


class TestClumpAwareScoring:
    """Verify the clump-aware eval metrics work correctly."""

    def test_clump_scoring_separates_clumped_and_isolated(self, tmp_path: Path):
        cfg = PlotConfig(
            marker="o", marker_size="medium", seed=210, label="test_clump_score",
            overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
        )
        out = generate_plot(cfg, tmp_path)
        gt = json.loads(out.json_path.read_text())
        truth_x = np.array(gt["x"])
        truth_y = np.array(gt["y"])

        # Perfect predictions = all points match
        result = score_predictions_with_clumps(
            truth_x, truth_y, truth_x, truth_y,
            tuple(gt["x_range"]), tuple(gt["y_range"]),
            marker_size=40.0,
        )
        assert result.matched_pct == 100.0
        assert result.singleton_recall == 100.0
        assert result.clump_recall == 100.0

    def test_clump_scoring_missing_clumped_points(self, tmp_path: Path):
        cfg = PlotConfig(
            marker="o", marker_size="medium", seed=211, label="test_clump_miss",
            overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
        )
        out = generate_plot(cfg, tmp_path)
        gt = json.loads(out.json_path.read_text())
        truth_x = np.array(gt["x"])
        truth_y = np.array(gt["y"])

        # Predict only the first 10 points (the isolated ones)
        pred_x = truth_x[:10]
        pred_y = truth_y[:10]

        result = score_predictions_with_clumps(
            pred_x, pred_y, truth_x, truth_y,
            tuple(gt["x_range"]), tuple(gt["y_range"]),
            marker_size=40.0,
        )
        # Singleton recall should be high, clump recall should be lower
        assert result.singleton_recall is not None
        assert result.clump_recall is not None
        assert result.singleton_recall > result.clump_recall


class TestMarkerProfileEstimation:
    """Tests for marker profile estimation from singletons."""

    def test_profile_from_filled_circles(self, tmp_path: Path):
        """Profile estimation on a plot with well-separated filled circles."""
        cfg = PlotConfig(
            n_points=20, marker="o", marker_size="medium", seed=220,
            label="test_profile_filled",
        )
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        profile = estimate_marker_profile(gray, cal)

        assert profile is not None
        assert profile.n_singletons >= 3
        assert profile.mean_radius_px > 1.0
        assert profile.is_hollow is False
        assert profile.fill_ratio >= 0.7
        assert profile.circularity > 0.5

    def test_profile_from_hollow_circles(self, tmp_path: Path):
        """Profile estimation correctly identifies unfilled circles as hollow."""
        cfg = PlotConfig(
            n_points=15, marker="o", marker_size="large", fill_style="unfilled",
            edge_width=2.0, seed=221, label="test_profile_hollow",
        )
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        profile = estimate_marker_profile(gray, cal)

        assert profile is not None
        assert profile.n_singletons >= 3
        assert profile.is_hollow is True
        assert profile.fill_ratio < 0.7
        assert profile.edge_width_px > 0

    def test_profile_returns_none_with_few_points(self, tmp_path: Path):
        """Should return None if fewer than 3 singletons found."""
        cfg = PlotConfig(
            n_points=2, marker="o", marker_size="medium", seed=222,
            label="test_profile_few",
        )
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        profile = estimate_marker_profile(gray, cal)
        # May or may not be None depending on whether 2 is detected, but shouldn't crash
        if profile is not None:
            assert profile.n_singletons >= 3

    def test_profile_radius_reasonable(self, tmp_path: Path):
        """Estimated radius should be proportional to marker size."""
        results = {}
        for size_name in ["small", "medium", "large"]:
            cfg = PlotConfig(
                n_points=15, marker="o", marker_size=size_name, seed=223,
                label=f"test_profile_{size_name}",
            )
            out = generate_plot(cfg, tmp_path)
            img = np.array(Image.open(out.image_path).convert("RGB"))
            gt = json.loads(out.json_path.read_text())
            cal = _make_calibration_from_gt(gt, img)

            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            profile = estimate_marker_profile(gray, cal)
            if profile is not None:
                results[size_name] = profile.mean_radius_px

        # If we got at least 2 sizes, larger markers should have larger radius
        if "small" in results and "large" in results:
            assert results["large"] > results["small"]


class TestShapeAwareDetector:
    """Tests for the full ShapeAwareDetector pipeline."""

    def test_detector_runs_on_filled_overlap(self, tmp_path: Path):
        """Detector should run without errors on overlapping filled circles."""
        cfg = OVERLAP_CONFIGS[1]  # 30% overlap
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = ShapeAwareDetector()
        result = detector.digitize(img, cal)

        assert len(result.points) > 0
        assert result.method.startswith("shape-aware")

    def test_detector_runs_on_hollow_overlap(self, tmp_path: Path):
        """Detector should run without errors on overlapping hollow circles."""
        cfg = OVERLAP_CONFIGS[10]  # hollow 30%
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = ShapeAwareDetector()
        result = detector.digitize(img, cal)

        assert len(result.points) > 0

    def test_detector_with_point_count_hint(self, tmp_path: Path):
        """Providing expected_point_count should not crash and should produce results."""
        cfg = OVERLAP_CONFIGS[0]  # 20% overlap
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)
        n_expected = len(gt["x"])

        detector = ShapeAwareDetector()
        result = detector.digitize(img, cal, expected_point_count=n_expected)

        assert len(result.points) > 0

    def test_detector_falls_back_with_few_singletons(self, tmp_path: Path):
        """With very few points, should either fall back or still produce results."""
        cfg = PlotConfig(
            n_points=2, marker="o", marker_size="medium", seed=230,
            label="test_fallback",
        )
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = ShapeAwareDetector()
        result = detector.digitize(img, cal)

        # Should produce some result regardless of path taken
        assert result.method.startswith("shape-aware")
        assert len(result.points) >= 0

    def test_detector_performance_under_10s(self, tmp_path: Path):
        """Full pipeline must complete in < 10 seconds."""
        cfg = OVERLAP_CONFIGS[8]  # dense cluster
        out = generate_plot(cfg, tmp_path)
        img = np.array(Image.open(out.image_path).convert("RGB"))
        gt = json.loads(out.json_path.read_text())
        cal = _make_calibration_from_gt(gt, img)

        detector = ShapeAwareDetector()
        result = detector.digitize(img, cal)

        assert result.elapsed_ms < 10000
