from __future__ import annotations

import numpy as np

from tests.eval_digitizer import score_predictions


def test_perfect_match():
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    result = score_predictions(x, y, x, y, (0, 10), (0, 10))

    assert result.matched_pct == 100.0
    assert result.false_positives == 0
    assert result.false_negatives == 0
    assert result.mean_error_x == 0.0
    assert result.mean_error_y == 0.0


def test_within_tolerance():
    truth_x = np.array([5.0])
    truth_y = np.array([5.0])
    pred_x = np.array([5.05])
    pred_y = np.array([5.05])
    result = score_predictions(pred_x, pred_y, truth_x, truth_y, (0, 10), (0, 10), tolerance_pct=1.0)

    assert result.matched_pct == 100.0
    assert result.false_negatives == 0


def test_outside_tolerance():
    truth_x = np.array([5.0])
    truth_y = np.array([5.0])
    pred_x = np.array([6.5])
    pred_y = np.array([6.5])
    result = score_predictions(pred_x, pred_y, truth_x, truth_y, (0, 10), (0, 10), tolerance_pct=1.0)

    assert result.matched_pct == 0.0
    assert result.false_negatives == 1
    assert result.false_positives == 1


def test_false_positives():
    truth_x = np.array([1.0])
    truth_y = np.array([1.0])
    pred_x = np.array([1.0, 8.0, 9.0])
    pred_y = np.array([1.0, 8.0, 9.0])
    result = score_predictions(pred_x, pred_y, truth_x, truth_y, (0, 10), (0, 10))

    assert result.matched_pct == 100.0
    assert result.false_positives == 2
    assert result.n_predicted == 3


def test_empty_predictions():
    truth_x = np.array([1.0, 2.0])
    truth_y = np.array([3.0, 4.0])
    result = score_predictions(np.array([]), np.array([]), truth_x, truth_y, (0, 10), (0, 10))

    assert result.matched_pct == 0.0
    assert result.false_negatives == 2
    assert result.n_predicted == 0


def test_empty_ground_truth():
    pred_x = np.array([1.0, 2.0])
    pred_y = np.array([3.0, 4.0])
    result = score_predictions(pred_x, pred_y, np.array([]), np.array([]), (0, 10), (0, 10))

    assert result.matched_pct == 0.0
    assert result.false_positives == 2
    assert result.n_ground_truth == 0


def test_tolerance_scales_with_range():
    truth_x = np.array([50.0])
    truth_y = np.array([50.0])
    pred_x = np.array([50.5])
    pred_y = np.array([50.5])
    result = score_predictions(pred_x, pred_y, truth_x, truth_y, (0, 100), (0, 100), tolerance_pct=1.0)

    assert result.matched_pct == 100.0
