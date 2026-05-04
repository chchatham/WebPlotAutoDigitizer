"""Detect axis lines, ticks, and labels from a plot image.

Strategy for synthetic matplotlib plots:
1. Find axis lines using edge detection + Hough lines
2. Identify the plot bounding box (the region enclosed by axes)
3. Use OCR (pytesseract) or regex-based text detection for axis labels
4. Return an AxisCalibration with pixel ranges and suggested data ranges
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

from backend.models import AxisCalibration


@dataclass
class AxisDetectionResult:
    calibration: AxisCalibration
    confidence: float


def _find_plot_bbox_hough(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Find plot bbox using Hough line detection (works for plots with axis border lines)."""
    edges = cv2.Canny(gray, 50, 150)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
    if lines is None:
        return None

    h_lines = []
    v_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if angle < 5 or angle > 175:
            h_lines.append((x1, y1, x2, y2, length))
        elif 85 < angle < 95:
            v_lines.append((x1, y1, x2, y2, length))

    h, w = gray.shape

    if not h_lines or not v_lines:
        return None

    h_lines.sort(key=lambda l: l[4], reverse=True)
    v_lines.sort(key=lambda l: l[4], reverse=True)

    bottom_line = max(h_lines[:5], key=lambda l: (l[1] + l[3]) / 2)
    top_line = min(h_lines[:5], key=lambda l: (l[1] + l[3]) / 2)
    left_line = min(v_lines[:5], key=lambda l: (l[0] + l[2]) / 2)
    right_line = max(v_lines[:5], key=lambda l: (l[0] + l[2]) / 2)

    x_min = int((left_line[0] + left_line[2]) / 2)
    x_max = int((right_line[0] + right_line[2]) / 2)
    y_min = int((top_line[1] + top_line[3]) / 2)
    y_max = int((bottom_line[1] + bottom_line[3]) / 2)

    x_min = max(0, x_min)
    y_min = max(0, y_min)
    x_max = min(w - 1, x_max)
    y_max = min(h - 1, y_max)

    if x_max - x_min < w * 0.2 or y_max - y_min < h * 0.2:
        return None

    return (x_min, y_min, x_max, y_max)


def _find_plot_bbox_background(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Find plot bbox by detecting the colored/gray background rectangle.

    Many plot styles (ggplot2, seaborn, etc.) render the plot area with a
    distinct background color (typically light gray ~230-245). This method
    finds that rectangle, which is more reliable than Hough lines for plots
    that use grid lines instead of border lines.
    """
    h, w = gray.shape

    white_thresh = 250
    near_white = gray >= white_thresh
    not_white = gray < white_thresh
    dark = gray < 200

    bg_mask = (~near_white & ~dark).astype(np.uint8) * 255

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    bg_mask = cv2.morphologyEx(bg_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    bg_mask = cv2.morphologyEx(bg_mask, cv2.MORPH_OPEN, kernel, iterations=2)

    contours, _ = cv2.findContours(bg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    min_area = h * w * 0.1
    candidates = []
    for c in contours:
        area = cv2.contourArea(c)
        if area >= min_area:
            x, y, cw, ch = cv2.boundingRect(c)
            candidates.append((x, y, x + cw, y + ch, area))

    if not candidates:
        return None

    best = max(candidates, key=lambda c: c[4])
    x_min, y_min, x_max, y_max = best[0], best[1], best[2], best[3]

    x_min = max(0, x_min)
    y_min = max(0, y_min)
    x_max = min(w - 1, x_max)
    y_max = min(h - 1, y_max)

    if x_max - x_min < w * 0.2 or y_max - y_min < h * 0.2:
        return None

    return (x_min, y_min, x_max, y_max)


def _find_plot_bbox(gray: np.ndarray) -> tuple[int, int, int, int]:
    """Find the plot area bounding box (x_min, y_min, x_max, y_max in pixels).

    Uses two strategies and picks the larger result:
    1. Background color detection (for ggplot/seaborn with gray plot areas)
    2. Hough line detection (for matplotlib with axis border lines)
    """
    h, w = gray.shape
    fallback = (int(w * 0.1), int(h * 0.1), int(w * 0.9), int(h * 0.9))

    bg_bbox = _find_plot_bbox_background(gray)
    hough_bbox = _find_plot_bbox_hough(gray)

    if bg_bbox and hough_bbox:
        bg_area = (bg_bbox[2] - bg_bbox[0]) * (bg_bbox[3] - bg_bbox[1])
        hough_area = (hough_bbox[2] - hough_bbox[0]) * (hough_bbox[3] - hough_bbox[1])
        return bg_bbox if bg_area >= hough_area else hough_bbox

    return bg_bbox or hough_bbox or fallback


def _extract_axis_numbers(gray: np.ndarray, bbox: tuple[int, int, int, int]) -> tuple[
    tuple[float, float] | None, tuple[float, float] | None
]:
    """Try to read axis tick labels using pytesseract OCR.

    Returns (x_data_range, y_data_range) or None for each if OCR fails.
    """
    try:
        import pytesseract
    except ImportError:
        return None, None

    h, w = gray.shape
    x_min, y_min, x_max, y_max = bbox

    # X-axis labels: region below the plot bottom
    x_label_region = gray[min(y_max + 2, h - 1):min(y_max + 50, h), max(x_min - 20, 0):min(x_max + 20, w)]
    # Y-axis labels: region to the left of the plot
    y_label_region = gray[max(y_min - 20, 0):min(y_max + 20, h), max(0, x_min - 80):max(x_min - 2, 1)]

    x_range = _parse_numbers_from_region(x_label_region)
    y_range = _parse_numbers_from_region(y_label_region)

    return x_range, y_range


def _parse_numbers_from_region(region: np.ndarray) -> tuple[float, float] | None:
    """OCR a small image region and extract numeric values."""
    if region.size == 0:
        return None

    try:
        import pytesseract
        text = pytesseract.image_to_string(region, config="--psm 6")
    except Exception:
        return None

    numbers = re.findall(r"-?\d+\.?\d*", text)
    if len(numbers) < 2:
        return None

    vals = sorted(float(n) for n in numbers)
    return (vals[0], vals[-1])


def detect_axes(image: np.ndarray) -> AxisDetectionResult:
    """Detect axes in a plot image and return calibration with confidence.

    Args:
        image: RGB numpy array of the plot image.

    Returns:
        AxisDetectionResult with calibration and confidence score.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    bbox = _find_plot_bbox(gray)
    x_min_px, y_min_px, x_max_px, y_max_px = bbox

    x_data_range, y_data_range = _extract_axis_numbers(gray, bbox)

    confidence = 0.5
    if x_data_range is not None and y_data_range is not None:
        confidence = 0.8

    if x_data_range is None:
        x_data_range = (0.0, 10.0)
        confidence = min(confidence, 0.3)
    if y_data_range is None:
        y_data_range = (0.0, 10.0)
        confidence = min(confidence, 0.3)

    # y_pixel_range: top of plot (y_min_px) maps to max data value,
    # bottom (y_max_px) maps to min data value (y increases downward in pixels)
    calibration = AxisCalibration(
        x_pixel_range=(float(x_min_px), float(x_max_px)),
        y_pixel_range=(float(y_max_px), float(y_min_px)),
        x_data_range=x_data_range,
        y_data_range=y_data_range,
    )

    return AxisDetectionResult(calibration=calibration, confidence=confidence)
