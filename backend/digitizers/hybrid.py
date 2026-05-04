"""Method C: Hybrid digitizer combining blob detection and template matching.

Strategy based on Method A/B failure analysis:
- Method A (blob): fast, high accuracy on circles/squares/diamonds, fails on triangles
- Method B (template): handles all shapes, catches adversarial cases, but slower and more FPs

Approach:
1. Always run blob detection (fast, ~1ms)
2. Run template matching on a quick subset to validate
3. Compare agreement between methods — if they largely agree, use blob (more precise)
4. If they disagree significantly, prefer template (handles non-circular markers)
"""
from __future__ import annotations

import time

import numpy as np

from backend.digitizers import BaseDigitizer
from backend.digitizers.blob_detector import BlobDetector
from backend.digitizers.template_matcher import TemplateMatcher
from backend.models import AxisCalibration, DetectedPoint, DetectionResult


class HybridDigitizer(BaseDigitizer):
    def __init__(self):
        self.blob = BlobDetector()
        self.template = TemplateMatcher()

    def digitize(self, image: np.ndarray, calibration: AxisCalibration) -> DetectionResult:
        t0 = time.perf_counter()

        blob_result = self.blob.digitize(image, calibration)
        template_result = self.template.digitize(image, calibration)

        blob_pts = blob_result.points
        tmpl_pts = template_result.points

        if not blob_pts and not tmpl_pts:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return DetectionResult(points=[], method="hybrid-empty", elapsed_ms=elapsed_ms)

        if not blob_pts:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return DetectionResult(points=tmpl_pts, method="hybrid-template", elapsed_ms=elapsed_ms)

        if not tmpl_pts:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return DetectionResult(points=blob_pts, method="hybrid-blob", elapsed_ms=elapsed_ms)

        blob_avg_conf = float(np.mean([p.confidence for p in blob_pts]))
        tmpl_avg_conf = float(np.mean([p.confidence for p in tmpl_pts]))

        agreement = _compute_agreement(blob_pts, tmpl_pts, calibration)

        if agreement >= 0.5:
            # Methods agree on locations — prefer whichever has higher confidence
            if blob_avg_conf >= tmpl_avg_conf:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                return DetectionResult(points=blob_pts, method="hybrid-blob", elapsed_ms=elapsed_ms)
            else:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                return DetectionResult(points=tmpl_pts, method="hybrid-template", elapsed_ms=elapsed_ms)

        # Methods disagree — prefer template (handles non-standard markers better)
        if tmpl_avg_conf >= blob_avg_conf * 0.8:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return DetectionResult(points=tmpl_pts, method="hybrid-template", elapsed_ms=elapsed_ms)

        merged = _merge_points(blob_pts, tmpl_pts, calibration)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return DetectionResult(points=merged, method="hybrid-merged", elapsed_ms=elapsed_ms)


def _compute_agreement(
    pts_a: list[DetectedPoint],
    pts_b: list[DetectedPoint],
    calibration: AxisCalibration,
) -> float:
    """Fraction of points in A that have a nearby match in B."""
    if not pts_a or not pts_b:
        return 0.0

    x_span = calibration.x_data_range[1] - calibration.x_data_range[0]
    y_span = calibration.y_data_range[1] - calibration.y_data_range[0]
    tol_x = x_span * 0.02
    tol_y = y_span * 0.02

    matches = 0
    for pa in pts_a:
        for pb in pts_b:
            if abs(pa.x_data - pb.x_data) < tol_x and abs(pa.y_data - pb.y_data) < tol_y:
                matches += 1
                break

    return matches / len(pts_a)


def _merge_points(
    primary: list[DetectedPoint],
    secondary: list[DetectedPoint],
    calibration: AxisCalibration,
) -> list[DetectedPoint]:
    x_span = calibration.x_data_range[1] - calibration.x_data_range[0]
    y_span = calibration.y_data_range[1] - calibration.y_data_range[0]
    merge_tol_x = x_span * 0.015
    merge_tol_y = y_span * 0.015

    merged = list(primary)

    for sp in secondary:
        is_dup = False
        for mp in merged:
            if abs(sp.x_data - mp.x_data) < merge_tol_x and abs(sp.y_data - mp.y_data) < merge_tol_y:
                is_dup = True
                break
        if not is_dup:
            merged.append(sp)

    return merged
