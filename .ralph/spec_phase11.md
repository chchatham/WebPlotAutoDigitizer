# Phase 11 Spec — Axis Constraints, Zoom Panel, Bounding Box Detection

## Changes Required

### 1. Constrained Axis Handles (single degree of freedom)

**Problem:** X-axis handles currently move freely in both X and Y. Y-axis handles also move in both dimensions. This allows the user to create non-horizontal X-axes and non-vertical Y-axes, which is wrong — real scatterplot axes are perfectly horizontal and vertical.

**Solution:**
- X-axis handles (`xLeft`, `xRight`): constrain to horizontal movement only. Both share a single Y coordinate (the Y pixel position of the X-axis). The user drags left/right to set where the X-axis starts and ends.
- Y-axis handles (`yBottom`, `yTop`): constrain to vertical movement only. Both share a single X coordinate (the X pixel position of the Y-axis). The user drags up/down to set where the Y-axis starts and ends.
- Additionally, allow the user to drag the **axis line itself** to reposition the shared coordinate (e.g., drag the X-axis line up/down to change its Y position, drag the Y-axis line left/right to change its X position).

**Implementation (AxisCalibration.tsx):**
- Replace 4x `{x, y}` handle state with: `xAxisY` (number), `xLeftX` (number), `xRightX` (number), `yAxisX` (number), `yBottomY` (number), `yTopY` (number).
- On drag of `xLeft`: only update `xLeftX` from mouse X.
- On drag of `xRight`: only update `xRightX` from mouse X.
- On drag of `yBottom`: only update `yBottomY` from mouse Y.
- On drag of `yTop`: only update `yTopY` from mouse Y.
- Draw X-axis as horizontal line at y=`xAxisY`, from x=`xLeftX` to x=`xRightX`.
- Draw Y-axis as vertical line at x=`yAxisX`, from y=`yBottomY` to y=`yTopY`.
- Calibration payload: `x_pixel_range = [xLeftX, xRightX]`, `y_pixel_range = [yBottomY, yTopY]`.

### 2. High-Resolution Zoom Panel

**Problem:** Placing axis handles at the exact pixel requires sub-pixel precision, but the canvas is scaled down (often 760px wide for a 1200px+ image). The user can't see exactly where the handle sits relative to the axis line.

**Solution:** Add a zoom inset panel that shows a magnified view around the currently-dragged (or last-dragged) handle.

**Implementation (AxisCalibration.tsx):**
- Add a secondary canvas (or div with a canvas) positioned to the right of or below the main canvas.
- Size: ~200x200px.
- When a handle is being dragged (or was last touched), crop a small region around the handle's pixel position from the **original-resolution** image and render it at high magnification (e.g., 8x zoom → 25x25 pixel source region → 200x200 display).
- Draw crosshairs at the handle's exact position within the zoom panel.
- Label the zoom panel with the handle name ("X min", "Y max", etc.).
- When no handle is active, show a "Drag a handle to zoom" placeholder.

### 3. Bounding Box for Detection Area

**Problem:** Points within the plot area but outside the axis handle positions are missed by the digitizer. The current 10% ROI padding helps but doesn't fully solve this — users need explicit control over the detection region.

**Solution:** Add a user-drawn bounding box that defines the detection area. Points are detected within this box, but calibration still uses the axis handles for coordinate mapping.

**Implementation:**

**Frontend (AxisCalibration.tsx):**
- Add 4 draggable corner handles (orange/amber) for the bounding box, initialized to contain the axis area with some padding.
- Draw a dashed orange rectangle connecting the 4 corners.
- The bounding box is always axis-aligned (rectangular).
- The user can drag any corner to resize.
- The bounding box defines where to look for points. The axis handles define how to convert found pixel coordinates to data coordinates.
- Instructions text updated: "Orange box = detection area. Blue/Green = axis calibration."

**API (api.ts, main.py):**
- Add `detection_bounds` to the `Calibration` interface: `{ x_min: number, x_max: number, y_min: number, y_max: number }` in pixel coordinates.
- Pass `detection_bounds` alongside `calibration` in the `/api/digitize` request.
- If `detection_bounds` is absent, fall back to the current behavior (axis range + 10% padding).

**Backend (models.py, blob_detector.py, template_matcher.py):**
- Add optional `detection_bounds` parameter to `BaseDigitizer.digitize()` (or pass it as a separate field alongside `AxisCalibration`).
- When `detection_bounds` is provided, use it directly as the ROI instead of computing from calibration + padding.
- `AxisCalibration` still used purely for coordinate mapping (pixel_to_data), NOT for ROI clipping.

**Backend model addition:**
```python
@dataclass
class DetectionBounds:
    x_min_px: float
    x_max_px: float
    y_min_px: float
    y_max_px: float
```

### File Changes Summary

| File | Change |
|------|--------|
| `frontend/src/components/AxisCalibration.tsx` | Rewrite: constrained handles, zoom panel, bounding box |
| `frontend/src/api.ts` | Add `detection_bounds` to `Calibration` and `digitize()` |
| `backend/main.py` | Parse `detection_bounds` from request, pass to digitizer |
| `backend/models.py` | Add `DetectionBounds` dataclass |
| `backend/digitizers/__init__.py` | Update `BaseDigitizer.digitize()` signature with optional bounds |
| `backend/digitizers/blob_detector.py` | Use `detection_bounds` for ROI when provided |
| `backend/digitizers/template_matcher.py` | Use `detection_bounds` for ROI when provided |
| `backend/digitizers/hybrid.py` | Pass `detection_bounds` through to sub-digitizers |
| `tests/test_calibration.py` | Add test for detection_bounds passthrough |
| `tests/test_blob_detector.py` | Add test with explicit bounds wider than axis range |
| `tests/test_api.py` | Add test for /api/digitize with detection_bounds |

### Non-Changes
- `AxisCalibration` dataclass and `pixel_to_data`/`data_to_pixel` methods: **unchanged**. The calibration math is not affected — it maps between axis pixel positions and data values. The bounding box is purely about WHERE to search, not how to map coordinates.
- Test harness (`eval_digitizer.py`, `generate_plots.py`): unchanged. Eval still passes calibration to digitizers; tests that don't use detection_bounds get the existing 10% padding fallback.

---

## Phase 11b Spec — Post-User-Testing Fixes

### 4. Back Button Label Fix

**Problem:** The "Back" button on the calibration screen has transparent background + border-only styling, making it appear as an empty unlabeled box in some contexts. The text "Back" is there but it inherits white from the global `button` style's color override.

**Solution:** Add explicit `color` to the back button so the label is visible. The button takes the user back to upload, so "Back" is the correct label.

**Implementation (AxisCalibration.tsx):**
- Add `color: "#475569"` to the Back button's inline style.

### 5. Points Below Y-min / Outside Axis Range

**Problem:** Points that lie below the Y-axis minimum or left of the X-axis minimum are missed because:
1. The detection bounding box may not extend far enough past the axis handles.
2. Even when detected, the coordinate mapping via `pixel_to_data()` already extrapolates linearly — so points outside the axis range DO get correct coordinates. The only issue is they need to be inside the detection box.

**Solution:** The bounding box already solves this conceptually — the user just needs to extend it to cover the full plot area. But the current 5% default padding is too small. Fix:
- Increase default bounding box padding from 5% to 15% of axis span.
- Add instructional text clarifying that the bounding box should cover ALL points, even those beyond the axis labels.
- The `pixel_to_data()` math already extrapolates linearly outside the axis range — no backend changes needed.

### 6. About Page Narrow Column

**Problem:** The About page renders `report.html` inside an iframe. The iframe is inside a container with `maxWidth: 800px` (App.tsx line 34). The report itself has `max-width: 900px` on its `.container` class. The double nesting makes the text column unnecessarily narrow, especially on wide screens.

**Solution:**
- Remove the `maxWidth: 800` constraint on the outer container when the About page is active, or increase it significantly.
- Widen the report.html `.container` from `max-width: 900px` to `max-width: 1200px`.
- The hero section's subtitle max-width (`600px`) should increase to `800px`.

**Implementation:**
- App.tsx: When `page === "about"`, use a wider container (maxWidth: 1200 or no max).
- report.html: Change `.container` max-width from 900px to 1200px. Change `.hero p` max-width from 600px to 800px.
- Copy updated report.html to `frontend/public/about.html`.
