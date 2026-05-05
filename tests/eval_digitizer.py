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
    unique_matching: bool = False,
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

    pred_norm = np.column_stack([predicted_x / tol_x, predicted_y / tol_y])
    truth_norm = np.column_stack([truth_x / tol_x, truth_y / tol_y])
    max_d = np.sqrt(2.0)

    tree = KDTree(pred_norm)
    distances, indices = tree.query(truth_norm)

    if unique_matching:
        # Greedy unique assignment: each prediction matches at most one truth
        pairs = [(int(ti), int(indices[ti]), float(distances[ti]))
                 for ti in range(n_truth) if distances[ti] <= max_d]
        pairs.sort(key=lambda x: x[2])

        matched_truth_set: set[int] = set()
        matched_pred_set: set[int] = set()
        match_pairs: list[tuple[int, int]] = []

        for ti, pi, d in pairs:
            if ti not in matched_truth_set and pi not in matched_pred_set:
                matched_truth_set.add(ti)
                matched_pred_set.add(pi)
                match_pairs.append((ti, pi))

        n_matched = len(matched_truth_set)
        matched_pct = (n_matched / n_truth) * 100.0

        errors_x = [abs(predicted_x[pi] - truth_x[ti]) for ti, pi in match_pairs]
        errors_y = [abs(predicted_y[pi] - truth_y[ti]) for ti, pi in match_pairs]
        false_positives = n_pred - len(matched_pred_set)
        false_negatives = n_truth - n_matched
    else:
        matched_mask = distances <= max_d
        matched_truth_indices = np.where(matched_mask)[0]
        matched_pred_indices_set = set(indices[matched_mask])

        n_matched = len(matched_truth_indices)
        matched_pct = (n_matched / n_truth) * 100.0

        errors_x = [abs(predicted_x[indices[ti]] - truth_x[ti]) for ti in matched_truth_indices]
        errors_y = [abs(predicted_y[indices[ti]] - truth_y[ti]) for ti in matched_truth_indices]
        false_positives = n_pred - len(matched_pred_indices_set)
        false_negatives = n_truth - n_matched

    if errors_x:
        mean_err_x = float(np.mean(errors_x))
        mean_err_y = float(np.mean(errors_y))
        max_err = float(max(max(errors_x), max(errors_y)))
    else:
        mean_err_x = mean_err_y = max_err = 0.0

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
    unique_matching: bool = False,
) -> EvalResult:
    """Extended scoring that separately tracks clumped vs singleton recall."""
    base_result = score_predictions(
        predicted_x, predicted_y, truth_x, truth_y, x_range, y_range,
        tolerance_pct, unique_matching,
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

    def _recall_for_subset(subset_indices: np.ndarray) -> float | None:
        if len(subset_indices) == 0:
            return None
        if len(predicted_x) == 0:
            return 0.0
        subset_x = truth_x[subset_indices]
        subset_y = truth_y[subset_indices]
        pred_norm = np.column_stack([predicted_x / tol_x, predicted_y / tol_y])
        truth_norm = np.column_stack([subset_x / tol_x, subset_y / tol_y])
        tree = KDTree(pred_norm)
        distances, nn_indices = tree.query(truth_norm)
        max_d = np.sqrt(2.0)

        if unique_matching:
            pairs = [(i, int(nn_indices[i]), float(distances[i]))
                     for i in range(len(subset_indices)) if distances[i] <= max_d]
            pairs.sort(key=lambda x: x[2])
            used_truth: set[int] = set()
            used_pred: set[int] = set()
            for ti, pi, _ in pairs:
                if ti not in used_truth and pi not in used_pred:
                    used_truth.add(ti)
                    used_pred.add(pi)
            matched = len(used_truth)
        else:
            matched = int(np.sum(distances <= max_d))

        return float(matched) / len(subset_indices) * 100.0

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
