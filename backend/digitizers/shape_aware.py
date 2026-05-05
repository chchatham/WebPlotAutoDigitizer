"""Method D: Shape-aware clump decomposition.

Uses singleton marker analysis to build a marker profile, then decomposes
clumps by fitting estimated marker shapes into silhouettes.
"""
from __future__ import annotations

import time

import cv2
import numpy as np
from scipy import ndimage
from scipy.spatial import KDTree

from backend.digitizers import BaseDigitizer
from backend.models import (
    AxisCalibration, DetectedPoint, DetectionBounds, DetectionResult, MarkerProfile,
)


def _extract_roi(
    gray: np.ndarray,
    calibration: AxisCalibration,
    detection_bounds: DetectionBounds | None,
) -> tuple[np.ndarray, int, int]:
    """Extract the region of interest and return (roi, x_offset, y_offset)."""
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
    return roi, x_min_px, y_min_px


def _threshold_roi(roi: np.ndarray) -> np.ndarray:
    """Threshold the ROI to isolate marker pixels."""
    bg_val = np.median(roi)
    if bg_val > 128:
        _, thresh = cv2.threshold(roi, bg_val - 60, 255, cv2.THRESH_BINARY_INV)
    else:
        _, thresh = cv2.threshold(roi, bg_val + 60, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
    return thresh


def _compute_fill_ratio(thresh: np.ndarray, contour: np.ndarray) -> float:
    """Compute ratio of foreground pixels inside the contour's convex hull."""
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    if hull_area < 1:
        return 1.0

    mask = np.zeros(thresh.shape[:2], dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    fg_inside = np.sum((mask > 0) & (thresh > 0))
    return float(fg_inside) / hull_area


def estimate_marker_profile(
    gray: np.ndarray,
    calibration: AxisCalibration,
    detection_bounds: DetectionBounds | None = None,
) -> MarkerProfile | None:
    """Estimate marker shape/size from isolated singletons in the image.

    Returns None if fewer than 3 singletons are found (insufficient data).
    """
    roi, x_off, y_off = _extract_roi(gray, calibration, detection_bounds)
    thresh = _threshold_roi(roi)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    roi_h, roi_w = roi.shape
    min_area = max(4, (roi_h * roi_w) * 0.00005)
    max_area = (roi_h * roi_w) * 0.02

    # First pass: collect all valid contour areas to compute median
    valid_areas = []
    for c in contours:
        a = cv2.contourArea(c)
        if min_area <= a <= max_area:
            valid_areas.append(a)

    if len(valid_areas) < 3:
        return None

    median_area = float(np.median(valid_areas))
    merge_threshold = median_area * 1.8

    # Second pass: identify singletons (area within [0.4x, 1.8x] median)
    singleton_data: list[dict] = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < median_area * 0.4 or area > merge_threshold:
            continue

        perimeter = cv2.arcLength(c, True)
        if perimeter < 1:
            continue
        circularity = (4 * np.pi * area) / (perimeter * perimeter)

        # Check isolation: no other contour centroid within 3x radius
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cx = M["m10"] / M["m00"]
        cy = M["m01"] / M["m00"]
        radius = np.sqrt(area / np.pi)

        fill_ratio = _compute_fill_ratio(thresh, c)

        singleton_data.append({
            "area": area,
            "radius": radius,
            "circularity": circularity,
            "fill_ratio": fill_ratio,
            "cx": cx,
            "cy": cy,
            "contour": c,
        })

    if len(singleton_data) < 3:
        return None

    # Filter for isolation: remove contours that have a neighbor within 2.5x radius
    centers = np.array([[s["cx"], s["cy"]] for s in singleton_data])
    radii = np.array([s["radius"] for s in singleton_data])
    median_radius = float(np.median(radii))

    isolated = []
    if len(centers) >= 2:
        tree = KDTree(centers)
        for i, s in enumerate(singleton_data):
            neighbors = tree.query_ball_point(centers[i], r=median_radius * 2.5)
            # Exclude self
            if len(neighbors) <= 1:
                isolated.append(s)
    else:
        isolated = list(singleton_data)

    if len(isolated) < 3:
        # Fall back to using all singletons sorted by circularity (top 50%)
        singleton_data.sort(key=lambda s: s["circularity"], reverse=True)
        isolated = singleton_data[: max(3, len(singleton_data) // 2)]

    if len(isolated) < 3:
        return None

    # Compute profile from isolated singletons
    areas = np.array([s["area"] for s in isolated])
    radii_arr = np.array([s["radius"] for s in isolated])
    circularities = np.array([s["circularity"] for s in isolated])
    fill_ratios = np.array([s["fill_ratio"] for s in isolated])

    # Use median to be robust to outliers
    mean_radius = float(np.median(radii_arr))
    std_radius = float(np.std(radii_arr))
    mean_area = float(np.median(areas))
    median_circularity = float(np.median(circularities))
    median_fill_ratio = float(np.median(fill_ratios))

    is_hollow = median_fill_ratio < 0.7

    # Estimate edge width for hollow markers
    edge_width = 0.0
    if is_hollow:
        # Edge width ≈ radius - inner_radius
        # inner_radius ≈ radius * sqrt(1 - fill_ratio)
        # Simplified: edge_width ≈ radius * (1 - sqrt(1 - fill_ratio))
        edge_width = mean_radius * (1 - np.sqrt(max(0, 1 - median_fill_ratio)))

    return MarkerProfile(
        mean_radius_px=mean_radius,
        std_radius_px=std_radius,
        mean_area_px=mean_area,
        is_hollow=is_hollow,
        edge_width_px=edge_width,
        circularity=median_circularity,
        fill_ratio=median_fill_ratio,
        n_singletons=len(isolated),
    )


def _local_maxima_nms(
    dist: np.ndarray,
    min_distance: float,
    min_val: float = 1.0,
) -> list[tuple[int, int, float]]:
    """Find local maxima in distance transform with non-maximum suppression."""
    kernel_size = max(3, int(min_distance))
    if kernel_size % 2 == 0:
        kernel_size += 1
    dilated = cv2.dilate(dist, np.ones((kernel_size, kernel_size)))
    local_max = (dist == dilated) & (dist >= min_val)

    ys, xs = np.where(local_max)
    if len(xs) == 0:
        return []

    vals = dist[ys, xs]
    order = np.argsort(-vals)
    xs, ys, vals = xs[order], ys[order], vals[order]

    kept: list[tuple[int, int, float]] = []
    suppressed = np.zeros(len(xs), dtype=bool)

    for i in range(len(xs)):
        if suppressed[i]:
            continue
        kept.append((int(xs[i]), int(ys[i]), float(vals[i])))
        dists_sq = (xs[i+1:].astype(float) - xs[i])**2 + (ys[i+1:].astype(float) - ys[i])**2
        suppressed[i+1:] |= dists_sq < (min_distance * 0.5)**2

    return kept


def _ellipse_based_placement(
    contour: np.ndarray,
    profile: MarkerProfile,
    estimated_n: int,
    x_offset: int,
    y_offset: int,
) -> list[tuple[float, float, float]]:
    """Place N points along the major axis of a contour's fitted ellipse.

    For two overlapping circles, the merged shape is elongated along the
    axis connecting their centers. Fitting an ellipse and distributing
    points along its major axis recovers the original centers.
    """
    if len(contour) < 5:
        return []

    try:
        (ecx, ecy), (minor, major), angle = cv2.fitEllipse(contour)
    except cv2.error:
        return []

    angle_rad = np.deg2rad(angle)
    dx = np.cos(angle_rad)
    dy = np.sin(angle_rad)

    r = profile.mean_radius_px
    if estimated_n == 2:
        half_len = major / 2.0 - r * 0.95
        half_len = max(half_len, r * 0.15)
        return [
            (ecx - dx * half_len + x_offset, ecy - dy * half_len + y_offset, 0.80),
            (ecx + dx * half_len + x_offset, ecy + dy * half_len + y_offset, 0.80),
        ]

    total_span = major - 2.0 * r * 0.95
    spacing = total_span / (estimated_n - 1) if estimated_n > 1 else 0
    centroids = []
    for i in range(estimated_n):
        t = -total_span / 2.0 + i * spacing
        cx = ecx + dx * t + x_offset
        cy = ecy + dy * t + y_offset
        centroids.append((cx, cy, 0.70))
    return centroids


def _refine_centroids_via_dist(
    centroids: list[tuple[float, float, float]],
    dist: np.ndarray,
    x0: int,
    y0: int,
    x_offset: int,
    y_offset: int,
    radius: float,
) -> list[tuple[float, float, float]]:
    """Refine centroid positions by finding the local distance-transform maximum
    near each initial placement. Uses mutual exclusion: after placing a point,
    suppress the DT around it so the next point can't collapse to the same peak.
    """
    search_r = max(5, int(radius * 1.2))
    exclude_r = max(3, int(radius * 0.5))
    work_dist = dist.copy().astype(np.float64)
    refined = []

    for cx, cy, conf in centroids:
        local_x = int(cx - x_offset - x0)
        local_y = int(cy - y_offset - y0)

        ly0 = max(0, local_y - search_r)
        ly1 = min(work_dist.shape[0], local_y + search_r + 1)
        lx0 = max(0, local_x - search_r)
        lx1 = min(work_dist.shape[1], local_x + search_r + 1)

        patch = work_dist[ly0:ly1, lx0:lx1]
        if patch.size == 0 or patch.max() < 0.5:
            refined.append((cx, cy, conf))
            continue

        best_y, best_x = np.unravel_index(patch.argmax(), patch.shape)
        abs_x = best_x + lx0
        abs_y = best_y + ly0
        new_x = float(abs_x) + x0 + x_offset
        new_y = float(abs_y) + y0 + y_offset
        refined.append((new_x, new_y, conf))

        # Suppress DT around this point so next point finds a different peak
        ey0 = max(0, abs_y - exclude_r)
        ey1 = min(work_dist.shape[0], abs_y + exclude_r + 1)
        ex0 = max(0, abs_x - exclude_r)
        ex1 = min(work_dist.shape[1], abs_x + exclude_r + 1)
        work_dist[ey0:ey1, ex0:ex1] = 0

    return refined


def _erosion_split(
    mask: np.ndarray,
    profile: MarkerProfile,
    estimated_n: int,
    x0: int,
    y0: int,
    x_offset: int,
    y_offset: int,
) -> list[tuple[float, float, float]]:
    """Split a clump by progressively eroding until it separates into components."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    best_centroids: list[tuple[float, float, float]] = []
    max_iters = max(2, int(profile.mean_radius_px * 0.7))

    eroded = mask.copy()
    for _ in range(max_iters):
        eroded = cv2.erode(eroded, kernel)
        if cv2.countNonZero(eroded) < 4:
            break

        contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) >= estimated_n:
            centroids = []
            for c in contours:
                M = cv2.moments(c)
                if M["m00"] == 0:
                    continue
                cx = M["m10"] / M["m00"] + x0 + x_offset
                cy = M["m01"] / M["m00"] + y0 + y_offset
                centroids.append((cx, cy, 0.78))
            if len(centroids) >= estimated_n:
                best_centroids = centroids[:estimated_n]
                break

    return best_centroids


def decompose_filled_clump(
    thresh: np.ndarray,
    contour: np.ndarray,
    profile: MarkerProfile,
    x_offset: int,
    y_offset: int,
    expected_n: int | None = None,
) -> list[tuple[float, float, float]]:
    """Decompose a merged filled-marker clump into individual point centers.

    Uses multiple strategies: ellipse-based placement, distance transform
    with NMS, label-based decomposition, and skeleton spacing.
    All results are refined using the distance transform for sub-pixel accuracy.
    Returns list of (px_x, px_y, confidence).
    """
    x, y, w, h = cv2.boundingRect(contour)
    pad = 3
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(thresh.shape[1], x + w + pad)
    y1 = min(thresh.shape[0], y + h + pad)

    mask = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
    shifted = contour.copy()
    shifted[:, :, 0] -= x0
    shifted[:, :, 1] -= y0
    cv2.drawContours(mask, [shifted], -1, 255, -1)

    clump_area = cv2.contourArea(contour)
    estimated_n = max(2, round(clump_area / profile.mean_area_px))

    if expected_n is not None:
        estimated_n = round(estimated_n * 0.7 + expected_n * 0.3)
        estimated_n = max(2, estimated_n)

    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)

    # Strategy 0a: Erosion split — most accurate for touching/overlapping circles
    erosion_centroids = _erosion_split(
        mask, profile, estimated_n, x0, y0, x_offset, y_offset,
    )

    # Strategy 0b: Ellipse-based placement with DT refinement
    ellipse_centroids = _ellipse_based_placement(
        contour, profile, estimated_n, x_offset, y_offset,
    )
    if ellipse_centroids:
        ellipse_centroids = _refine_centroids_via_dist(
            ellipse_centroids, dist, x0, y0, x_offset, y_offset,
            profile.mean_radius_px,
        )

    # Strategy 1: Local maxima with NMS at reduced spacing
    min_sep = profile.mean_radius_px * 0.6
    best_centroids: list[tuple[float, float, float]] = []
    best_diff = float("inf")

    for min_val_frac in [0.2, 0.15, 0.3, 0.1, 0.4, 0.5]:
        min_val = dist.max() * min_val_frac
        peaks = _local_maxima_nms(dist, min_sep, min_val)
        if len(peaks) < 2:
            continue

        centroids = []
        for lx, ly, dval in peaks:
            cx = float(lx) + x0 + x_offset
            cy = float(ly) + y0 + y_offset
            conf = min(0.85, 0.4 + 0.4 * (dval / (profile.mean_radius_px + 1e-6)))
            centroids.append((cx, cy, conf))

        diff = abs(len(centroids) - estimated_n)
        if diff < best_diff:
            best_diff = diff
            best_centroids = centroids

        if len(centroids) == estimated_n:
            break

    # Pick best among erosion, ellipse, and NMS results
    # Erosion is preferred when it finds the right count (most accurate centroids)
    if erosion_centroids and len(erosion_centroids) == estimated_n:
        best_centroids = erosion_centroids
        best_diff = 0
    elif ellipse_centroids:
        ellipse_diff = abs(len(ellipse_centroids) - estimated_n)
        if not best_centroids or ellipse_diff < best_diff:
            best_centroids = ellipse_centroids
            best_diff = ellipse_diff

    # Strategy 2: Label-based approach with lower thresholds
    if len(best_centroids) < estimated_n:
        for threshold_frac in [0.25, 0.2, 0.15, 0.1]:
            thresh_val = dist.max() * threshold_frac
            if thresh_val < 0.5:
                continue
            _, peaks_img = cv2.threshold(dist, thresh_val, 255, 0)
            peaks_img = peaks_img.astype(np.uint8)

            labels_arr, n_labels = ndimage.label(peaks_img)
            if n_labels <= len(best_centroids):
                continue

            centroids = []
            for i in range(1, n_labels + 1):
                ys, xs = np.where(labels_arr == i)
                if len(xs) == 0:
                    continue
                cx = float(np.mean(xs)) + x0 + x_offset
                cy = float(np.mean(ys)) + y0 + y_offset
                local_cx, local_cy = int(np.mean(xs)), int(np.mean(ys))
                dval = dist[local_cy, local_cx] if 0 <= local_cy < dist.shape[0] and 0 <= local_cx < dist.shape[1] else 0
                conf = min(0.75, 0.3 + 0.3 * (dval / (profile.mean_radius_px + 1e-6)))
                centroids.append((cx, cy, conf))

            if len(centroids) > len(best_centroids):
                diff = abs(len(centroids) - estimated_n)
                if diff < best_diff:
                    best_diff = diff
                    best_centroids = centroids

            if len(centroids) >= estimated_n:
                break

    # Strategy 3: Skeleton-based center spacing for larger clumps
    if len(best_centroids) < estimated_n and estimated_n >= 3:
        skeleton = cv2.ximgproc.thinning(mask) if hasattr(cv2, 'ximgproc') else None
        if skeleton is None:
            eroded = mask.copy()
            for _ in range(max(1, int(profile.mean_radius_px * 0.5))):
                eroded = cv2.erode(eroded, np.ones((3, 3), np.uint8))
                if cv2.countNonZero(eroded) < 2:
                    break
            skeleton = eroded

        skel_ys, skel_xs = np.where(skeleton > 0)
        if len(skel_xs) >= estimated_n:
            indices = np.linspace(0, len(skel_xs) - 1, estimated_n, dtype=int)
            centroids = []
            for idx in indices:
                cx = float(skel_xs[idx]) + x0 + x_offset
                cy = float(skel_ys[idx]) + y0 + y_offset
                centroids.append((cx, cy, 0.5))
            if len(centroids) > len(best_centroids):
                best_centroids = centroids

    if not best_centroids:
        M = cv2.moments(contour)
        if M["m00"] > 0:
            cx = M["m10"] / M["m00"] + x_offset
            cy = M["m01"] / M["m00"] + y_offset
            best_centroids = [(cx, cy, 0.3)]

    return best_centroids


def decompose_hollow_clump(
    gray_roi: np.ndarray,
    thresh: np.ndarray,
    contour: np.ndarray,
    profile: MarkerProfile,
    x_offset: int,
    y_offset: int,
    expected_n: int | None = None,
) -> list[tuple[float, float, float]]:
    """Decompose overlapping hollow/unfilled circles using Hough circle detection.

    Tries multiple Hough parameter combinations for robustness.
    Falls back to ellipse-based then filled decomposition if Hough finds too few.
    """
    x, y, w, h = cv2.boundingRect(contour)
    pad = int(profile.mean_radius_px * 2.0)
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(gray_roi.shape[1], x + w + pad)
    y1 = min(gray_roi.shape[0], y + h + pad)

    sub_roi = gray_roi[y0:y1, x0:x1]
    if sub_roi.size == 0:
        return decompose_filled_clump(thresh, contour, profile, x_offset, y_offset, expected_n)

    clump_area = cv2.contourArea(contour)
    estimated_n = max(2, round(clump_area / profile.mean_area_px))

    r = profile.mean_radius_px
    r_tol = max(4, int(r * 0.35))
    min_r = max(3, int(r - r_tol))
    max_r = int(r + r_tol)

    best_circles: list[tuple[float, float, float]] = []

    hough_configs = [
        (1.2, int(r * 1.0), 50, 20),
        (1.2, int(r * 1.0), 80, 25),
        (1.0, int(r * 0.8), 50, 15),
        (1.5, int(r * 1.2), 60, 20),
        (1.2, int(r * 0.8), 40, 12),
    ]

    for dp, min_dist, p1, p2 in hough_configs:
        min_dist = max(min_dist, int(r * 0.6))
        blur_k = max(3, int(r * 0.4) | 1)
        blurred = cv2.GaussianBlur(sub_roi, (blur_k, blur_k), 0.8)

        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT,
            dp=dp, minDist=min_dist,
            param1=p1, param2=p2,
            minRadius=min_r, maxRadius=max_r,
        )

        if circles is not None and len(circles[0]) >= 2:
            centroids = []
            for circle in circles[0]:
                cx = float(circle[0]) + x0 + x_offset
                cy = float(circle[1]) + y0 + y_offset
                cr = float(circle[2])
                r_diff = abs(cr - r) / (r + 1e-6)
                conf = min(0.9, 0.6 + 0.3 * max(0, 1 - r_diff))
                centroids.append((cx, cy, conf))

            if len(centroids) > len(best_circles):
                best_circles = centroids

            if len(best_circles) >= estimated_n:
                break

    if len(best_circles) >= max(2, int(estimated_n * 0.6)):
        return best_circles

    # Fallback to ellipse-based placement then filled decomposition
    return decompose_filled_clump(thresh, contour, profile, x_offset, y_offset, expected_n)


class ShapeAwareDetector(BaseDigitizer):
    """Method D: Shape-aware clump decomposition.

    Uses singleton marker analysis to build a marker profile, then
    decomposes clumps by fitting estimated marker shapes into silhouettes.
    """

    def digitize(
        self,
        image: np.ndarray,
        calibration: AxisCalibration,
        detection_bounds: DetectionBounds | None = None,
        expected_point_count: int | None = None,
    ) -> DetectionResult:
        t0 = time.perf_counter()

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        profile = estimate_marker_profile(gray, calibration, detection_bounds)

        if profile is None:
            # Not enough singletons — fall back to basic blob detection
            from backend.digitizers.blob_detector import BlobDetector
            result = BlobDetector().digitize(image, calibration, detection_bounds)
            result.method = "shape-aware-fallback"
            result.elapsed_ms = (time.perf_counter() - t0) * 1000
            return result

        roi, x_off, y_off = _extract_roi(gray, calibration, detection_bounds)
        thresh = _threshold_roi(roi)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        roi_h, roi_w = roi.shape
        min_area = max(4, (roi_h * roi_w) * 0.00005)

        # Use a lower merge threshold when user provides expected count
        if expected_point_count is not None:
            merge_threshold = profile.mean_area_px * 1.15
        else:
            merge_threshold = profile.mean_area_px * 1.3

        points: list[DetectedPoint] = []
        singletons_found = 0

        # Separate contours into singletons and clumps
        singleton_contours = []
        clump_contours = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area:
                continue
            if area > merge_threshold:
                clump_contours.append(c)
            elif area > profile.mean_area_px * 1.0:
                # Check elongation: 2 merged circles form an elongated shape
                x_bb, y_bb, w_bb, h_bb = cv2.boundingRect(c)
                aspect = max(w_bb, h_bb) / (min(w_bb, h_bb) + 1e-6)
                if aspect > 1.3:
                    clump_contours.append(c)
                else:
                    singleton_contours.append(c)
            else:
                singleton_contours.append(c)

        # Process singletons normally
        for c in singleton_contours:
            M = cv2.moments(c)
            if M["m00"] == 0:
                continue
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
            px_x = cx + x_off
            px_y = cy + y_off
            data_x, data_y = calibration.pixel_to_data(px_x, px_y)

            area = cv2.contourArea(c)
            perimeter = cv2.arcLength(c, True)
            circularity = (4 * np.pi * area) / (perimeter * perimeter + 1e-6)
            confidence = min(1.0, circularity * 0.8 + 0.2)

            points.append(DetectedPoint(
                x_data=data_x, y_data=data_y,
                x_pixel=px_x, y_pixel=px_y,
                confidence=confidence,
            ))
            singletons_found += 1

        # Compute per-clump expected point count if user provided total
        remaining_expected = None
        if expected_point_count is not None:
            remaining_expected = max(0, expected_point_count - singletons_found)

        # Process clumps with shape-aware decomposition
        for c in clump_contours:
            clump_area = cv2.contourArea(c)
            this_clump_expected = None

            if remaining_expected is not None and len(clump_contours) > 0:
                # Distribute remaining expected points proportionally by area
                total_clump_area = sum(cv2.contourArea(cc) for cc in clump_contours)
                if total_clump_area > 0:
                    proportion = clump_area / total_clump_area
                    this_clump_expected = max(2, round(remaining_expected * proportion))

            if profile.is_hollow:
                centroids = decompose_hollow_clump(
                    roi, thresh, c, profile, x_off, y_off, this_clump_expected
                )
            else:
                centroids = decompose_filled_clump(
                    thresh, c, profile, x_off, y_off, this_clump_expected
                )

            for px_x, px_y, conf in centroids:
                data_x, data_y = calibration.pixel_to_data(px_x, px_y)
                points.append(DetectedPoint(
                    x_data=data_x, y_data=data_y,
                    x_pixel=px_x, y_pixel=px_y,
                    confidence=conf,
                ))

        # Post-processing: if expected_point_count provided, apply soft constraint
        if expected_point_count is not None and len(points) != expected_point_count:
            points = _apply_count_constraint(points, expected_point_count)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return DetectionResult(points=points, method="shape-aware", elapsed_ms=elapsed_ms)


def _apply_count_constraint(
    points: list[DetectedPoint],
    expected: int,
) -> list[DetectedPoint]:
    """Soft adjustment: if we have too many points, remove lowest confidence.
    If too few, keep all (can't invent new ones without more analysis).
    """
    if len(points) <= expected:
        return points

    # Too many: remove lowest confidence points (soft — only trim up to 30% excess)
    excess = len(points) - expected
    max_trim = int(len(points) * 0.3)
    n_trim = min(excess, max_trim)

    if n_trim <= 0:
        return points

    sorted_pts = sorted(points, key=lambda p: p.confidence, reverse=True)
    return sorted_pts[:len(points) - n_trim]
