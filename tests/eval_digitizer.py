"""Scoring harness for digitizer evaluation.

Compares predicted points against ground truth using nearest-neighbor matching.
Tolerance is per-axis, defaulting to 1% of axis range.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.spatial import KDTree

from backend.models import AxisCalibration, DetectionResult


@dataclass
class EvalResult:
    matched_pct: float
    mean_error_x: float
    mean_error_y: float
    max_error: float
    false_positives: int
    false_negatives: int
    tolerance_pct: float
    n_ground_truth: int
    n_predicted: int
    clump_recall: float | None = None
    singleton_recall: float | None = None
    clump_precision: float | None = None

    def to_dict(self) -> dict:
        d = {
            "matched_pct": round(self.matched_pct, 2),
            "mean_error_x": round(self.mean_error_x, 4),
            "mean_error_y": round(self.mean_error_y, 4),
            "max_error": round(self.max_error, 4),
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "tolerance_pct": self.tolerance_pct,
            "n_ground_truth": self.n_ground_truth,
            "n_predicted": self.n_predicted,
        }
        if self.clump_recall is not None:
            d["clump_recall"] = round(self.clump_recall, 2)
        if self.singleton_recall is not None:
            d["singleton_recall"] = round(self.singleton_recall, 2)
        if self.clump_precision is not None:
            d["clump_precision"] = round(self.clump_precision, 2)
        return d


def score_predictions(
    predicted_x: np.ndarray,
    predicted_y: np.ndarray,
    truth_x: np.ndarray,
    truth_y: np.ndarray,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    tolerance_pct: float = 1.0,
) -> EvalResult:
    x_span = x_range[1] - x_range[0]
    y_span = y_range[1] - y_range[0]
    tol_x = x_span * tolerance_pct / 100.0
    tol_y = y_span * tolerance_pct / 100.0

    n_truth = len(truth_x)
    n_pred = len(predicted_x)

    if n_pred == 0:
        return EvalResult(
            matched_pct=0.0,
            mean_error_x=0.0,
            mean_error_y=0.0,
            max_error=0.0,
            false_positives=0,
            false_negatives=n_truth,
            tolerance_pct=tolerance_pct,
            n_ground_truth=n_truth,
            n_predicted=0,
        )

    if n_truth == 0:
        return EvalResult(
            matched_pct=0.0,
            mean_error_x=0.0,
            mean_error_y=0.0,
            max_error=0.0,
            false_positives=n_pred,
            false_negatives=0,
            tolerance_pct=tolerance_pct,
            n_ground_truth=0,
            n_predicted=n_pred,
        )

    # Normalize to make tolerance isotropic for KDTree
    pred_norm = np.column_stack([predicted_x / tol_x, predicted_y / tol_y])
    truth_norm = np.column_stack([truth_x / tol_x, truth_y / tol_y])

    tree = KDTree(pred_norm)
    distances, indices = tree.query(truth_norm)

    # A match requires distance <= 1.0 in normalized space (within tolerance on both axes)
    matched_mask = distances <= np.sqrt(2.0)  # max L2 when both axes at tolerance

    matched_truth_indices = np.where(matched_mask)[0]
    matched_pred_indices = set(indices[matched_mask])

    n_matched = len(matched_truth_indices)
    matched_pct = (n_matched / n_truth) * 100.0

    errors_x = []
    errors_y = []
    for ti in matched_truth_indices:
        pi = indices[ti]
        errors_x.append(abs(predicted_x[pi] - truth_x[ti]))
        errors_y.append(abs(predicted_y[pi] - truth_y[ti]))

    if errors_x:
        mean_err_x = float(np.mean(errors_x))
        mean_err_y = float(np.mean(errors_y))
        max_err = float(max(max(errors_x), max(errors_y)))
    else:
        mean_err_x = mean_err_y = max_err = 0.0

    false_positives = n_pred - len(matched_pred_indices)
    false_negatives = n_truth - n_matched

    return EvalResult(
        matched_pct=matched_pct,
        mean_error_x=mean_err_x,
        mean_error_y=mean_err_y,
        max_error=max_err,
        false_positives=false_positives,
        false_negatives=false_negatives,
        tolerance_pct=tolerance_pct,
        n_ground_truth=n_truth,
        n_predicted=n_pred,
    )


def _classify_clumped_points(
    truth_x: np.ndarray,
    truth_y: np.ndarray,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    marker_size: float,
) -> np.ndarray:
    """Classify each ground-truth point as clumped (True) or singleton (False).

    A point is 'clumped' if it has at least one neighbor within 2x marker diameter
    in normalized data space.
    """
    x_span = x_range[1] - x_range[0]
    y_span = y_range[1] - y_range[0]

    # Approximate marker diameter as fraction of axis range
    # marker_size is in points^2; diameter ~ 2*sqrt(size/pi) points
    # Normalize relative to plot area (assume 8x6 figure at 150 DPI)
    marker_diam_pts = 2 * np.sqrt(marker_size / np.pi)
    pixels_per_point = 150.0 / 72.0  # DPI / points_per_inch
    marker_diam_px = marker_diam_pts * pixels_per_point
    plot_width_px = 8 * 150 * 0.8  # approximate plot area width
    plot_height_px = 6 * 150 * 0.8
    threshold_x = (marker_diam_px * 2.0 / plot_width_px) * x_span
    threshold_y = (marker_diam_px * 2.0 / plot_height_px) * y_span

    n = len(truth_x)
    is_clumped = np.zeros(n, dtype=bool)

    if n < 2:
        return is_clumped

    points_norm = np.column_stack([truth_x / threshold_x, truth_y / threshold_y])
    tree = KDTree(points_norm)
    pairs = tree.query_pairs(r=1.0)
    for i, j in pairs:
        is_clumped[i] = True
        is_clumped[j] = True

    return is_clumped


def score_predictions_with_clumps(
    predicted_x: np.ndarray,
    predicted_y: np.ndarray,
    truth_x: np.ndarray,
    truth_y: np.ndarray,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    marker_size: float = 40.0,
    tolerance_pct: float = 1.0,
) -> EvalResult:
    """Extended scoring that separately tracks clumped vs singleton recall."""
    base_result = score_predictions(
        predicted_x, predicted_y, truth_x, truth_y, x_range, y_range, tolerance_pct
    )

    if len(truth_x) == 0:
        return base_result

    is_clumped = _classify_clumped_points(truth_x, truth_y, x_range, y_range, marker_size)
    clump_indices = np.where(is_clumped)[0]
    singleton_indices = np.where(~is_clumped)[0]

    x_span = x_range[1] - x_range[0]
    y_span = y_range[1] - y_range[0]
    tol_x = x_span * tolerance_pct / 100.0
    tol_y = y_span * tolerance_pct / 100.0

    def _recall_for_subset(indices: np.ndarray) -> float | None:
        if len(indices) == 0:
            return None
        if len(predicted_x) == 0:
            return 0.0
        subset_x = truth_x[indices]
        subset_y = truth_y[indices]
        pred_norm = np.column_stack([predicted_x / tol_x, predicted_y / tol_y])
        truth_norm = np.column_stack([subset_x / tol_x, subset_y / tol_y])
        tree = KDTree(pred_norm)
        distances, _ = tree.query(truth_norm)
        matched = np.sum(distances <= np.sqrt(2.0))
        return float(matched) / len(indices) * 100.0

    clump_recall = _recall_for_subset(clump_indices)
    singleton_recall = _recall_for_subset(singleton_indices)

    # Clump precision: of predictions near clump regions, how many are true positives?
    clump_precision = None
    if len(clump_indices) > 0 and len(predicted_x) > 0:
        clump_truth_norm = np.column_stack([
            truth_x[clump_indices] / tol_x, truth_y[clump_indices] / tol_y
        ])
        pred_norm = np.column_stack([predicted_x / tol_x, predicted_y / tol_y])
        # Find predictions that are near any clumped truth point (within 3x tolerance)
        clump_tree = KDTree(clump_truth_norm)
        dists, _ = clump_tree.query(pred_norm)
        preds_in_clump_region = np.sum(dists <= 3.0 * np.sqrt(2.0))
        # Of those, how many actually match a truth point?
        truth_tree = KDTree(clump_truth_norm)
        dists2, _ = truth_tree.query(pred_norm)
        true_pos_in_clump = np.sum(dists2 <= np.sqrt(2.0))
        if preds_in_clump_region > 0:
            clump_precision = float(true_pos_in_clump) / float(preds_in_clump_region) * 100.0

    base_result.clump_recall = clump_recall
    base_result.singleton_recall = singleton_recall
    base_result.clump_precision = clump_precision
    return base_result


def evaluate_from_files(
    prediction_result: DetectionResult,
    ground_truth_path: Path,
    tolerance_pct: float = 1.0,
) -> EvalResult:
    gt = json.loads(ground_truth_path.read_text())
    truth_x = np.array(gt["x"])
    truth_y = np.array(gt["y"])
    x_range = tuple(gt["x_range"])
    y_range = tuple(gt["y_range"])

    pred_x = np.array([p.x_data for p in prediction_result.points])
    pred_y = np.array([p.y_data for p in prediction_result.points])

    return score_predictions(pred_x, pred_y, truth_x, truth_y, x_range, y_range, tolerance_pct)


def evaluate_from_files_with_clumps(
    prediction_result: DetectionResult,
    ground_truth_path: Path,
    tolerance_pct: float = 1.0,
) -> EvalResult:
    """Like evaluate_from_files but includes clump/singleton recall breakdown."""
    gt = json.loads(ground_truth_path.read_text())
    truth_x = np.array(gt["x"])
    truth_y = np.array(gt["y"])
    x_range = tuple(gt["x_range"])
    y_range = tuple(gt["y_range"])
    marker_size = gt.get("params", {}).get("marker_size", 40.0)

    pred_x = np.array([p.x_data for p in prediction_result.points])
    pred_y = np.array([p.y_data for p in prediction_result.points])

    return score_predictions_with_clumps(
        pred_x, pred_y, truth_x, truth_y, x_range, y_range, marker_size, tolerance_pct
    )
