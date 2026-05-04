"""Method A: Blob/contour-based point detection.

Uses color thresholding and contour detection to find scatter markers.
Works best on high-contrast plots with solid markers on clean backgrounds.
"""
from __future__ import annotations

import time

import cv2
import numpy as np

from backend.digitizers import BaseDigitizer
from backend.models import AxisCalibration, DetectedPoint, DetectionResult


class BlobDetector(BaseDigitizer):
    def digitize(self, image: np.ndarray, calibration: AxisCalibration) -> DetectionResult:
        t0 = time.perf_counter()

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        x_min_px = int(min(calibration.x_pixel_range))
        x_max_px = int(max(calibration.x_pixel_range))
        y_min_px = int(min(calibration.y_pixel_range))
        y_max_px = int(max(calibration.y_pixel_range))

        # Slight inset to avoid detecting axis lines themselves
        margin = 3
        x_min_px = max(0, x_min_px + margin)
        x_max_px = min(gray.shape[1] - 1, x_max_px - margin)
        y_min_px = max(0, y_min_px + margin)
        y_max_px = min(gray.shape[0] - 1, y_max_px - margin)

        roi = gray[y_min_px:y_max_px, x_min_px:x_max_px]

        bg_val = np.median(roi)

        if bg_val > 128:
            _, thresh = cv2.threshold(roi, bg_val - 60, 255, cv2.THRESH_BINARY_INV)
        else:
            _, thresh = cv2.threshold(roi, bg_val + 60, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        roi_h, roi_w = roi.shape
        min_area = max(4, (roi_h * roi_w) * 0.00005)
        max_area = (roi_h * roi_w) * 0.02

        points = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue

            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]

            # Convert back to full-image pixel coordinates
            px_x = cx + x_min_px
            px_y = cy + y_min_px

            data_x, data_y = calibration.pixel_to_data(px_x, px_y)

            perimeter = cv2.arcLength(contour, True)
            circularity = (4 * np.pi * area) / (perimeter * perimeter + 1e-6)
            confidence = min(1.0, circularity * 0.8 + 0.2)

            points.append(DetectedPoint(
                x_data=data_x,
                y_data=data_y,
                x_pixel=px_x,
                y_pixel=px_y,
                confidence=confidence,
            ))

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return DetectionResult(
            points=points,
            method="blob",
            elapsed_ms=elapsed_ms,
        )
