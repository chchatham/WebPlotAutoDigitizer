# Phase 14 Spec — Shape-Aware Clump Decomposition

## Motivation

The current watershed-based clump splitting (`_split_merged_contour` in `blob_detector.py`) uses distance-transform peaks to split merged blobs. This works when clumps are loosely touching but fails when:
- Points significantly overlap (2+ markers sharing >30% area)
- Marker size is large relative to point spacing
- Unfilled circles overlap (the algorithm doesn't exploit the ring structure)
- The user knows the total point count but the algorithm doesn't

The fundamental weakness: the current approach treats clumps as amorphous blobs and guesses how many peaks to split them into using local geometry alone. It never learns the actual marker shape/size from the image.

## Core Idea: Shape Estimation from Singletons

**Phase 14 introduces a "marker profile" step that runs before clump decomposition:**

1. **Identify singletons** — Find isolated, high-confidence blobs that clearly represent single data points (not touching anything, circular/well-formed, area within the normal distribution)
2. **Estimate marker profile** — From these singletons, compute: mean radius, area, eccentricity, fill type (solid vs hollow), edge width (for unfilled markers), dominant color
3. **Use marker profile to decompose clumps** — Given a clump silhouette + the known marker shape, fit N copies of the estimated marker into the clump. This is essentially a packing/coverage problem.
4. **Optional user constraint** — If the user provides the total expected point count, use it to constrain decomposition (e.g., if 50 points expected and 42 singletons found, the remaining clumps must contain ~8 points total)

## Algorithm Detail

### Step 1: Marker Profile Estimation

```python
@dataclass
class MarkerProfile:
    mean_radius_px: float        # mean radius of singleton markers
    std_radius_px: float         # variability in radius
    mean_area_px: float          # mean contour area
    is_hollow: bool              # True for unfilled circles/markers
    edge_width_px: float         # stroke width for hollow markers (0 for filled)
    circularity: float           # 4*pi*area / perimeter^2 (1.0 = perfect circle)
    color_bgr: tuple[int,int,int]  # dominant marker color
    fill_ratio: float            # ratio of foreground pixels inside convex hull (low = hollow)
```

**Hollow detection:** For each singleton contour, compute the fill ratio = (foreground pixels inside contour) / (contour area from `cv2.contourArea`). A solid circle has fill_ratio ≈ 1.0. An unfilled circle has fill_ratio ≈ 0.3–0.5 (only the ring is filled). Threshold at ~0.7 to classify.

**Profile computation:** Use the median of measurements from the top 50% highest-confidence singletons (by circularity). Outliers (area > 2x median or < 0.5x median) are excluded.

### Step 2: Clump Decomposition (Filled Markers)

For filled markers overlapping into a clump:

1. Compute the clump silhouette area
2. Estimate N = round(clump_area / marker_profile.mean_area) as the expected point count
3. If user provides `expected_total_points`, adjust N using the deficit: `N = max(N, deficit)` where deficit = expected_total - singletons_found - already_decomposed
4. Use iterative erosion + distance transform:
   - Erode by `marker_profile.mean_radius * 0.5`
   - Find connected components in the eroded image → initial centers
   - If fewer centers than N, reduce erosion threshold and retry
   - If more centers than N (and user constraint is present), merge the closest pairs
5. Refine centers via local peak-finding in the distance transform
6. Assign each center the estimated marker radius as its confidence weight

### Step 3: Clump Decomposition (Hollow/Unfilled Markers)

For unfilled circles, the ring structure provides additional constraints:

1. Apply Hough circle detection within the clump bounding box, using the known radius from marker profile: `cv2.HoughCircles(... minRadius=r-2, maxRadius=r+2)`
2. Each detected circle = one data point
3. For overlapping rings that Hough misses: look for arc segments. Two overlapping unfilled circles create 4 arc segments — detect them via contour curvature analysis and fit circles
4. Fallback to the filled-marker algorithm (Step 2) if Hough finds too few circles

### Step 4: User Point Count Constraint

**New API parameter:** `expected_point_count: int | None`

When provided:
- After all singletons and clump decompositions are computed, compare total detected vs expected
- If detected < expected: lower confidence thresholds and re-examine rejected small blobs, or split remaining clumps more aggressively
- If detected > expected: raise confidence threshold, merge very close detections
- The constraint is soft — it guides but doesn't force exact agreement (the user might be wrong)

Weight: `constraint_pressure = 0.3` — only shifts thresholds by 30% toward the target

## New Digitizer: `ShapeAwareDetector`

```python
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
        ...
```

This extends `BaseDigitizer` with an optional `expected_point_count` parameter. The base interface is NOT changed — the new parameter has a default of None, maintaining backward compatibility.

## Updated HybridDigitizer

The `HybridDigitizer` gains a new routing path:

1. Run blob detection (fast baseline, as before)
2. **NEW:** If blob detection finds clumps (contours > 1.8x median area), AND more than 20% of detected area is in clumps → run ShapeAwareDetector on the full image
3. Compare ShapeAwareDetector results against blob results using the same agreement logic
4. If user provides `expected_point_count`, pass it through to ShapeAwareDetector

This means ShapeAwareDetector only activates when there are actual clumps to decompose — it doesn't slow down the common case of well-separated points.

## Test Framework Expansion

### New Plot Generator Parameters

```python
@dataclass
class OverlapConfig:
    """Controls deliberate point overlap for testing clump decomposition."""
    overlap_fraction: float = 0.3  # fraction of marker diameter that overlaps (0=touching, 1=concentric)
    n_overlap_pairs: int = 5       # number of overlapping pairs
    n_isolated: int = 10           # number of non-overlapping singletons (for profile estimation)

@dataclass  
class PlotConfig:
    # ... existing fields ...
    fill_style: Literal["filled", "unfilled"] = "filled"  # NEW
    edge_width: float = 1.5                                # NEW: for unfilled markers
    marker_color: str = "black"                            # NEW: support colored markers
    overlap: OverlapConfig | None = None                   # NEW
```

### New Test Cases (Phase 14 suite)

The test suite adds ~30 new cases specifically targeting overlap scenarios:

**Category A: Filled circle overlaps (varying degree)**
- 2 points overlapping 20%, 30%, 50%, 70% of diameter
- 3 points in a tight triangle (pairwise overlap 30%)
- 5 points in a linear chain (each overlaps neighbor by 40%)
- 10 points in a cluster with random 20-50% overlaps

**Category B: Unfilled circle overlaps**
- Same geometry as Category A but with unfilled circles (edge_width=1.5)
- Unfilled circles where rings overlap but centers are clearly distinct
- Unfilled circles where rings overlap and create confusing intersections

**Category C: Various backgrounds**
- White, light gray (#e0e0e0), dark gray (#404040), ggplot-style (#ebebeb)
- With and without grid lines
- Point color: black, blue, red (to test color-based isolation)

**Category D: Various point sizes**
- Small (20), medium (40), large (80), extra-large (120)
- Mixed sizes within one plot (if applicable — tests that the profile picks the mode)

**Category E: Mixed isolated + clumped**
- 50 points: 40 isolated, 10 in 2 clumps of 5
- 100 points: 70 isolated, 30 in 6 clumps of 5
- With user point count hint vs without

**Category F: Point count constraint tests**
- Plot with known N points, provide correct N → compare accuracy with/without hint
- Plot with known N points, provide wrong N (N+5, N-5) → verify graceful degradation

### Eval Harness Update

`eval_digitizer.py` gains a new metric:

```python
@dataclass
class EvalResult:
    # ... existing fields ...
    clump_recall: float      # % of ground-truth clumped points that were detected
    singleton_recall: float  # % of isolated points detected (should stay high)
    clump_precision: float   # % of points detected in clump regions that are true positives
```

The harness determines which ground-truth points are "clumped" by checking pairwise distances < 2x marker radius.

## API Changes

### `/api/digitize` request body update

```json
{
  "image_id": "abc123",
  "calibration": { ... },
  "detection_bounds": { ... },
  "expected_point_count": 50  // NEW — optional
}
```

### Frontend: Point Count Input

A new optional numeric input on the **AxisCalibration screen** (alongside the axis range inputs):

- Label: "Expected number of points (optional)"
- Placeholder: "Leave blank for auto-detect"
- Type: number, min=1, max=1000
- Position: below the bounding box controls, before the "Digitize" button
- Passed through to `/api/digitize` as `expected_point_count`

This is a lightweight addition — one `<input>` field and one extra key in the request body.

## File Changes Summary

| File | Change |
|------|--------|
| `backend/digitizers/shape_aware.py` | **NEW** — ShapeAwareDetector implementation |
| `backend/digitizers/__init__.py` | Export ShapeAwareDetector |
| `backend/digitizers/hybrid.py` | Route to ShapeAwareDetector when clumps detected |
| `backend/models.py` | Add `MarkerProfile` dataclass |
| `backend/main.py` | Parse `expected_point_count` from request, pass to digitizer |
| `frontend/src/api.ts` | Add `expected_point_count` to digitize request |
| `frontend/src/components/AxisCalibration.tsx` | Add point count input field |
| `tests/generate_plots.py` | Add `OverlapConfig`, `fill_style`, new test configs |
| `tests/eval_digitizer.py` | Add `clump_recall`, `singleton_recall`, `clump_precision` |
| `tests/test_shape_aware.py` | **NEW** — Unit tests for ShapeAwareDetector |
| `tests/test_clump_decomposition.py` | **NEW** — Integration tests for overlap scenarios |

## Non-Changes

- `AxisCalibration` dataclass: unchanged
- `BaseDigitizer` interface: unchanged (new param is optional with default None)
- `BlobDetector`, `TemplateMatcher`: unchanged (still used by hybrid as first pass)
- Existing 48 tests: must all still pass (no regressions)
- Docker/deployment config: unchanged

## Implementation Order

1. **Test framework first** (as always per guardrails):
   - Expand `generate_plots.py` with `OverlapConfig`, `fill_style`, new configs
   - Generate overlap test suite
   - Update `eval_digitizer.py` with clump-specific metrics
   - Write test stubs in `test_shape_aware.py`

2. **MarkerProfile estimation** — the foundation everything depends on

3. **Filled-marker clump decomposition** — the most common case

4. **Hollow-marker decomposition** — leverages Hough circles

5. **Point count constraint** — API + frontend + algorithm integration

6. **HybridDigitizer routing update** — tie it all together

7. **Eval and compare** — run full suite, compare Phase 14 vs Phase 13 detection rates on clumped plots

## Success Criteria

- Clump recall ≥ 75% on filled circle overlaps with ≤50% overlap fraction
- Clump recall ≥ 85% on unfilled circle overlaps
- Singleton recall unchanged (≥ 95% — no regression)
- With correct point count hint: clump recall improves by ≥10 percentage points
- All existing 48 tests still pass
- `/api/digitize` < 10s even with shape-aware decomposition active

---

## Phase 14h — Threshold Tuning for 2-Point Clumps (post-user-testing)

### Problem

User tested with a ~100-point plot (red filled circles on white background). System detected 93/100 points. A visible 2-3 point clump forming an elongated "peanut" shape was not decomposed. Root cause analysis identified three overly conservative thresholds:

1. **Hybrid routing threshold (`_has_significant_clumps`) = 20%**: With 100 mostly-separated points and ~3-4 small clumps, total clump area ≈ 2-3% of total — far below 20%. ShapeAwareDetector is never invoked.

2. **Merge/clump classification threshold = 1.8x median area**: A 2-point overlap with ~30% area overlap produces a merged contour of only ~1.4-1.5x single marker area. These are classified as singletons and emitted as a single centroid, losing 1 point.

3. **Blob detector distance transform peak threshold = 0.4**: Too high to separate gentle 2-point overlaps where the distance transform has a plateau rather than distinct peaks.

### Fix: Three-Pronged Threshold Reduction

**A. Lower hybrid routing threshold: 20% → 5%**

With `expected_point_count` provided, use 0% (always route to shape-aware). Without hint, use 5% instead of 20%. Rationale: if there are ANY merged contours, it's worth running shape-aware since the overhead is only ~1-2ms.

**B. Lower merge classification threshold: 1.8x → 1.3x**

Change in both `shape_aware.py` and `blob_detector.py`. A 2-point overlap at ~20% produces ~1.3x area; at ~30% produces ~1.5x. The old 1.8x only catches overlaps ≥ 40-50%.

Additionally, add an **elongation criterion**: classify a contour as a clump if its bounding box aspect ratio > 1.5 AND area > median * 1.0. An elongated blob is almost certainly 2+ merged markers even if the area is only slightly above median.

**C. Lower blob detector split threshold: 0.4 → 0.25**

Lower the distance-transform peak threshold in `_split_merged_contour` to detect peaks in gentler overlaps. Also lower `n_labels <= 1` early-exit to try harder.

### New Test Cases

Add to `OVERLAP_CONFIGS`:
- **Dense-with-sparse-clumps**: 100 points, ~90 isolated + 5 pairs (0.3 overlap) — mimics the user's actual scenario
- **Red markers**: `marker_color="red"` versions of existing configs
- **2-point-only overlaps**: configs where ALL overlapping groups are exactly 2 points (no triples)
- **Small overlap fractions**: 15-20% overlap (currently just barely merge contours)

### Stronger `expected_point_count` Constraint

When `expected_point_count` is provided and `detected < expected`:
- Always invoke ShapeAwareDetector (bypass the 5% routing check)
- Lower the merge threshold further to 1.15x (any contour noticeably larger than a singleton)
- After initial detection, scan for contours between 1.15x and 1.3x median area that have elongation > 1.3; try to split each one via distance transform

### File Changes

| File | Change |
|------|--------|
| `backend/digitizers/hybrid.py` | Lower routing threshold; bypass when hint provided |
| `backend/digitizers/shape_aware.py` | Lower merge threshold; add elongation criterion; strengthen hint |
| `backend/digitizers/blob_detector.py` | Lower split threshold from 0.4 to 0.25, merge threshold from 1.8x to 1.3x |
| `tests/generate_plots.py` | Add dense-with-sparse-clumps configs, red markers, 2-point-only configs |
| `tests/test_clump_decomposition.py` | Add tests for 2-point clump detection, dense plots with hint |
