"""Method B: Template matching point detection.

Uses normalized cross-correlation with a library of marker templates.
Generates templates at multiple scales and picks peaks in the correlation map.
"""
from __future__ import annotations

import time

import cv2
import numpy as np

from backend.digitizers import BaseDigitizer
from backend.models import AxisCalibration, DetectedPoint, DetectionResult


def _make_circle_template(size: int) -> np.ndarray:
    tmpl = np.ones((size, size), dtype=np.uint8) * 255
    cv2.circle(tmpl, (size // 2, size // 2), size // 2 - 1, 0, -1)
    return tmpl


def _make_square_template(size: int) -> np.ndarray:
    tmpl = np.ones((size, size), dtype=np.uint8) * 255
    m = max(1, size // 8)
    tmpl[m:size - m, m:size - m] = 0
    return tmpl


def _make_triangle_template(size: int) -> np.ndarray:
    tmpl = np.ones((size, size), dtype=np.uint8) * 255
    pts = np.array([[size // 2, 1], [1, size - 2], [size - 2, size - 2]])
    cv2.fillPoly(tmpl, [pts], 0)
    return tmpl


def _make_x_template(size: int) -> np.ndarray:
    tmpl = np.ones((size, size), dtype=np.uint8) * 255
    t = max(1, size // 6)
    cv2.line(tmpl, (1, 1), (size - 2, size - 2), 0, t)
    cv2.line(tmpl, (size - 2, 1), (1, size - 2), 0, t)
    return tmpl


def _make_diamond_template(size: int) -> np.ndarray:
    tmpl = np.ones((size, size), dtype=np.uint8) * 255
    c = size // 2
    pts = np.array([[c, 1], [size - 2, c], [c, size - 2], [1, c]])
    cv2.fillPoly(tmpl, [pts], 0)
    return tmpl


TEMPLATE_MAKERS = {
    "circle": _make_circle_template,
    "square": _make_square_template,
    "triangle": _make_triangle_template,
    "x": _make_x_template,
    "diamond": _make_diamond_template,
}


class TemplateMatcher(BaseDigitizer):
    def __init__(self, template_sizes: list[int] | None = None):
        self.template_sizes = template_sizes or [7, 11, 15, 21]

    def digitize(self, image: np.ndarray, calibration: AxisCalibration) -> DetectionResult:
        t0 = time.perf_counter()

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        x_min_px = int(min(calibration.x_pixel_range))
        x_max_px = int(max(calibration.x_pixel_range))
        y_min_px = int(min(calibration.y_pixel_range))
        y_max_px = int(max(calibration.y_pixel_range))

        x_pad = int((x_max_px - x_min_px) * 0.10)
        y_pad = int((y_max_px - y_min_px) * 0.10)
        x_min_px = max(0, x_min_px - x_pad)
        x_max_px = min(gray.shape[1] - 1, x_max_px + x_pad)
        y_min_px = max(0, y_min_px - y_pad)
        y_max_px = min(gray.shape[0] - 1, y_max_px + y_pad)

        roi = gray[y_min_px:y_max_px, x_min_px:x_max_px]
        roi_h, roi_w = roi.shape

        bg_val = np.median(roi)
        if bg_val > 128:
            roi_inv = 255 - roi
        else:
            roi_inv = roi.copy()

        best_peaks: list[tuple[float, float, float]] = []
        best_score = -1.0

        for name, maker in TEMPLATE_MAKERS.items():
            for size in self.template_sizes:
                if size >= min(roi_h, roi_w):
                    continue

                tmpl = maker(size)
                if bg_val > 128:
                    tmpl = 255 - tmpl

                result = cv2.matchTemplate(roi_inv, tmpl, cv2.TM_CCOEFF_NORMED)

                threshold = 0.4
                locs = np.where(result >= threshold)
                if len(locs[0]) == 0:
                    continue

                peaks = []
                for py, px in zip(locs[0], locs[1]):
                    score = result[py, px]
                    cx = px + size / 2
                    cy = py + size / 2
                    peaks.append((cx, cy, float(score)))

                peaks = _non_max_suppression(peaks, min_dist=size * 0.6)

                avg_score = np.mean([p[2] for p in peaks]) if peaks else 0.0
                if avg_score > best_score and len(peaks) >= 3:
                    best_score = avg_score
                    best_peaks = peaks

        points = []
        for cx, cy, score in best_peaks:
            px_x = cx + x_min_px
            px_y = cy + y_min_px
            data_x, data_y = calibration.pixel_to_data(px_x, px_y)
            points.append(DetectedPoint(
                x_data=data_x,
                y_data=data_y,
                x_pixel=px_x,
                y_pixel=px_y,
                confidence=min(1.0, score),
            ))

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return DetectionResult(
            points=points,
            method="template",
            elapsed_ms=elapsed_ms,
        )


def _non_max_suppression(
    peaks: list[tuple[float, float, float]], min_dist: float
) -> list[tuple[float, float, float]]:
    if not peaks:
        return []

    peaks_sorted = sorted(peaks, key=lambda p: p[2], reverse=True)
    kept = []

    for cx, cy, score in peaks_sorted:
        too_close = False
        for kx, ky, _ in kept:
            if (cx - kx) ** 2 + (cy - ky) ** 2 < min_dist ** 2:
                too_close = True
                break
        if not too_close:
            kept.append((cx, cy, score))

    return kept
