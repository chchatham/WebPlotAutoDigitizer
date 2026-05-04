"""Method C: Hybrid digitizer combining blob detection, template matching,
and shape-aware clump decomposition.

Strategy based on Method A/B failure analysis:
- Method A (blob): fast, high accuracy on circles/squares/diamonds, fails on triangles
- Method B (template): handles all shapes, catches adversarial cases, but slower and more FPs
- Method D (shape-aware): activated when clumps detected, uses marker profile for decomposition

Approach:
1. Always run blob detection (fast, ~1ms)
2. Check if significant clumping is present (>20% area in merged contours)
3. If clumps detected: run ShapeAwareDetector and compare results
4. Otherwise: compare blob vs template as before
"""
from __future__ import annotations

import time

import cv2
import numpy as np

from backend.digitizers import BaseDigitizer
from backend.digitizers.blob_detector import BlobDetector
from backend.digitizers.template_matcher import TemplateMatcher
from backend.models import AxisCalibration, DetectedPoint, DetectionBounds, DetectionResult


def _has_significant_clumps(image: np.ndarray, calibration: AxisCalibration, detection_bounds: DetectionBounds | None) -> bool:
    """Check if >20% of detected contour area is in merged/clumped blobs."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    if detection_bounds:
        x_min = int(detection_bounds.x_min_px)
        x_max = int(detection_bounds.x_max_px)
        y_min = int(detection_bounds.y_min_px)
        y_max = int(detection_bounds.y_max_px)
    else:
        x_min = int(min(calibration.x_pixel_range))
        x_max = int(max(calibration.x_pixel_range))
        y_min = int(min(calibration.y_pixel_range))
        y_max = int(max(calibration.y_pixel_range))
        x_pad = int((x_max - x_min) * 0.10)
        y_pad = int((y_max - y_min) * 0.10)
        x_min = max(0, x_min - x_pad)
        x_max = min(gray.shape[1] - 1, x_max + x_pad)
        y_min = max(0, y_min - y_pad)
        y_max = min(gray.shape[0] - 1, y_max + y_pad)

    roi = gray[max(0, y_min):min(gray.shape[0], y_max), max(0, x_min):min(gray.shape[1], x_max)]
    if roi.size == 0:
        return False

    bg_val = np.median(roi)
    if bg_val > 128:
        _, thresh = cv2.threshold(roi, bg_val - 60, 255, cv2.THRESH_BINARY_INV)
    else:
        _, thresh = cv2.threshold(roi, bg_val + 60, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    roi_h, roi_w = roi.shape
    min_area = max(4, (roi_h * roi_w) * 0.00005)
    max_area = (roi_h * roi_w) * 0.02

    normal_areas = []
    for c in contours:
        a = cv2.contourArea(c)
        if min_area <= a <= max_area * 0.3:
            normal_areas.append(a)

    if not normal_areas:
        return False

    median_area = float(np.median(normal_areas))
    merge_threshold = median_area * 1.8

    total_area = 0.0
    clump_area = 0.0
    for c in contours:
        a = cv2.contourArea(c)
        if a < min_area:
            continue
        total_area += a
        if a > merge_threshold:
            clump_area += a

    if total_area == 0:
        return False

    return (clump_area / total_area) > 0.20


class HybridDigitizer(BaseDigitizer):
    def __init__(self):
        self.blob = BlobDetector()
        self.template = TemplateMatcher()

    def digitize(
        self,
        image: np.ndarray,
        calibration: AxisCalibration,
        detection_bounds: DetectionBounds | None = None,
        expected_point_count: int | None = None,
    ) -> DetectionResult:
        t0 = time.perf_counter()

        blob_result = self.blob.digitize(image, calibration, detection_bounds)

        # Check if shape-aware decomposition should be used
        if _has_significant_clumps(image, calibration, detection_bounds):
            from backend.digitizers.shape_aware import ShapeAwareDetector
            shape_result = ShapeAwareDetector().digitize(
                image, calibration, detection_bounds, expected_point_count
            )
            # Compare: if shape-aware found more points with reasonable confidence, prefer it
            if (len(shape_result.points) > len(blob_result.points) and
                    shape_result.method != "shape-aware-fallback"):
                shape_avg_conf = float(np.mean([p.confidence for p in shape_result.points])) if shape_result.points else 0
                blob_avg_conf = float(np.mean([p.confidence for p in blob_result.points])) if blob_result.points else 0
                if shape_avg_conf >= blob_avg_conf * 0.6:
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    return DetectionResult(
                        points=shape_result.points,
                        method="hybrid-shape-aware",
                        elapsed_ms=elapsed_ms,
                    )

        template_result = self.template.digitize(image, calibration, detection_bounds)

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
            if blob_avg_conf >= tmpl_avg_conf:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                return DetectionResult(points=blob_pts, method="hybrid-blob", elapsed_ms=elapsed_ms)
            else:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                return DetectionResult(points=tmpl_pts, method="hybrid-template", elapsed_ms=elapsed_ms)

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
