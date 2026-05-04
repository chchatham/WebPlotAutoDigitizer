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

    def to_dict(self) -> dict:
        return {
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
