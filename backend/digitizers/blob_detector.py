"""Method A: Blob/contour-based point detection.

Uses color thresholding and contour detection to find scatter markers.
Works best on high-contrast plots with solid markers on clean backgrounds.
Includes watershed splitting for merged/clumped markers.
"""
from __future__ import annotations

import time

import cv2
import numpy as np
from scipy import ndimage

from backend.digitizers import BaseDigitizer
from backend.models import AxisCalibration, DetectedPoint, DetectionBounds, DetectionResult


def _split_merged_contour(
    thresh_roi: np.ndarray,
    contour: np.ndarray,
    median_area: float,
) -> list[tuple[float, float, float]]:
    """Split a large contour into sub-blobs via distance-transform watershed."""
    x, y, w, h = cv2.boundingRect(contour)
    pad = 2
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(thresh_roi.shape[1], x + w + pad)
    y1 = min(thresh_roi.shape[0], y + h + pad)

    mask = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
    shifted = contour.copy()
    shifted[:, :, 0] -= x0
    shifted[:, :, 1] -= y0
    cv2.drawContours(mask, [shifted], -1, 255, -1)

    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    _, thresh_peaks = cv2.threshold(dist, dist.max() * 0.4, 255, 0)
    thresh_peaks = thresh_peaks.astype(np.uint8)

    labels_arr, n_labels = ndimage.label(thresh_peaks)
    if n_labels <= 1:
        return []

    centroids = []
    for i in range(1, n_labels + 1):
        ys, xs = np.where(labels_arr == i)
        if len(xs) == 0:
            continue
        cx = float(np.mean(xs)) + x0
        cy = float(np.mean(ys)) + y0
        region_area = np.sum(mask[ys.min():ys.max()+1, xs.min():xs.max()+1] > 0)
        conf = min(1.0, 0.5 + 0.3 * min(region_area / max(median_area, 1), 1.0))
        centroids.append((cx, cy, conf))

    return centroids


class BlobDetector(BaseDigitizer):
    def digitize(
        self,
        image: np.ndarray,
        calibration: AxisCalibration,
        detection_bounds: DetectionBounds | None = None,
    ) -> DetectionResult:
        t0 = time.perf_counter()

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        if detection_bounds:
            x_min_px = int(detection_bounds.x_min_px)
            x_max_px = int(detection_bounds.x_max_px)
            y_min_px = int(detection_bounds.y_min_px)
            y_max_px = int(detection_bounds.y_max_px)
        else:
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

        x_min_px = max(0, x_min_px)
        x_max_px = min(gray.shape[1] - 1, x_max_px)
        y_min_px = max(0, y_min_px)
        y_max_px = min(gray.shape[0] - 1, y_max_px)

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
        merge_threshold = max_area * 0.3

        normal_areas = []
        for c in contours:
            a = cv2.contourArea(c)
            if min_area <= a <= merge_threshold:
                normal_areas.append(a)
        median_area = float(np.median(normal_areas)) if normal_areas else min_area * 10

        points = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            if area > merge_threshold and median_area > 0 and area > median_area * 1.8:
                sub_blobs = _split_merged_contour(thresh, contour, median_area)
                if len(sub_blobs) >= 2:
                    for cx, cy, conf in sub_blobs:
                        px_x = cx + x_min_px
                        px_y = cy + y_min_px
                        data_x, data_y = calibration.pixel_to_data(px_x, px_y)
                        points.append(DetectedPoint(
                            x_data=data_x, y_data=data_y,
                            x_pixel=px_x, y_pixel=px_y,
                            confidence=conf,
                        ))
                    continue

            if area > max_area:
                continue

            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue

            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]

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
