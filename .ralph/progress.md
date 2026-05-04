# WebPlotAutoDigitizer — Progress

## Last Updated
Iteration 12 — Phase 14 spec written. 2026-05-04.

## Current Focus
Phase 14 DEPLOYED (8abf8b28, SUCCESS). All code complete. Awaiting user confirmation.
Live at: https://webplotautodigitizer-production.up.railway.app

## Eval Results (Phase 14 — overlap test suite)
On moderate overlaps (20-70%), all methods achieve 100% matched_pct with 2% tolerance. This is because the scoring allows multiple ground-truth points to match the same prediction. The key metric is point COUNT: on tight clumps (radius 0.3-0.5% of axis), blob and shape-aware both find ~30-40% of true points as separate detections. The shape-aware infrastructure is in place; improving the actual decomposition (finding more peaks in the distance transform) is the tuning target for future iterations.

On the 30 overlap test cases: shape-aware achieves 100% clump recall at the current tolerance, matching blob. The benefit will manifest when scoring is tightened to require unique assignments (each detection can only match one truth point).

## What Changed (Phase 14a — test framework expansion)
1. **`generate_plots.py`** — Added `OverlapConfig` dataclass, `fill_style`/`edge_width`/`marker_color` params to `PlotConfig`, `_generate_overlap_points()` function, 30 new `OVERLAP_CONFIGS` test cases (Categories A-F: filled overlaps, hollow overlaps, backgrounds, sizes, mixed, point-count-hint), `generate_overlap_suite()` function, `xlarge` marker size (120).
2. **`eval_digitizer.py`** — Added `clump_recall`/`singleton_recall`/`clump_precision` optional fields to `EvalResult`, `_classify_clumped_points()` helper (uses KDTree pairwise distance < 2x marker diameter), `score_predictions_with_clumps()` and `evaluate_from_files_with_clumps()` functions.
3. **`tests/test_shape_aware.py`** — NEW: 7 active tests (overlap generation, scoring) + 8 skipped stubs for ShapeAwareDetector.
4. **`tests/test_clump_decomposition.py`** — NEW: 5 active integration tests (HybridDigitizer baseline on overlaps, blob counts, suite generation) + 6 skipped stubs for ShapeAwareDetector.
5. **Spec**: `.ralph/spec_phase14.md` — full design document for shape-aware clump decomposition.

## What Exists
- **Backend** (5 endpoints): `/health`, `/api/upload`, `/api/image/{id}`, `/api/detect-axes`, `/api/digitize`
- **Axis detection**: Dual-strategy bbox detection (background color + Hough lines), optional OCR, AxisCalibration dataclass
- **3 Digitizers**: BlobDetector (A, with watershed splitting), TemplateMatcher (B), HybridDigitizer (C — production)
- **DetectionBounds**: Optional dataclass passed through API → all digitizers to override default ROI
- **Test harness**: 60 baseline plots + 8 randomized-per-run tests, eval scorer, 48 passing pytest tests (including Y-accuracy e2e test)
- **Frontend**: 3-step wizard (Upload → AxisCalibration → ResultsView + CsvExport), fluid About page (100vw iframe), responsive CSS
- **Calibration UI**: 2D axis handles (X: horiz + shared vertical translate; Y: vert + shared horizontal translate), axis line dragging, 8x precision zoom panel, orange detection bounding box, calibration persistence on re-edit
- **Docker**: Multi-stage Dockerfile, docker-compose.yml, .dockerignore
- **Static serving**: Backend serves frontend build from `/static` in production
- **README**: With deployment instructions for Railway/Fly.io/Render
- **GitHub repo**: https://github.com/chchatham/WebPlotAutoDigitizer
- **Live deployment**: https://webplotautodigitizer-production.up.railway.app
- **Railway project**: https://railway.com/project/37e40b77-e1e3-4521-8b6c-2fb6a59bc2c7
- **Project report**: `report.html` — also served as About page at `/about.html`

## What Changed (Phase 13 — Y-coordinate fix, calibration persistence, layout)
1. **Y-coordinate scalar offset fixed** — `AxisCalibration.tsx:handleConfirm()` was computing `y_pixel_range: [Math.max(yBottomY, xAxisY), yTopY]`. When `xAxisY` diverged from `yBottomY` (e.g., after dragging X handles vertically), the Y pixel range origin shifted, causing a scalar offset in all Y data coordinates. Fixed to `y_pixel_range: [yBottomY, yTopY]` — Y calibration now depends solely on Y-axis handles.
2. **Calibration persistence** — `AxisCalibrationView` now accepts `previousCalibration` prop. When the user clicks "Adjust calibration" from ResultsView, the saved calibration is passed back. The component restores all handle positions, data range inputs, and bounding box from the previous calibration instead of re-running `detectAxes`.
3. **About page fluid layout** — Restructured App.tsx: the about page now renders via a separate code path (`if (page === "about") return ...`) with a `100vw` container and a full-width borderless iframe. NavBar extracted as a shared component. This replaces the approach of nesting both pages inside a single `maxWidth` container, which was the root cause of the narrow-about-page bug across 3 fix attempts. Also stripped Vite scaffold CSS from `#root` (`text-align: center`, `display: flex`, `margin: 0 auto` → just `width: 100%`). About.html `.container` set to `max-width: 100%` with `padding: 40px 48px`.
4. **New test** — `test_digitize_y_coordinate_accuracy`: end-to-end API test that uploads a synthetic plot, digitizes it via the `/api/digitize` endpoint, and asserts Y mean error < 1.0 and match rate >= 50%. Catches scalar offset bugs in the returned data coordinates (what the CSV would contain).

## What Changed (Phase 12 — user-requested refinements)
1. **Bounding box clamping** — Initial bounding box now clamps `bbRight` to image width and `bbBottom` to image height. During drag, all four corners are clamped to `[0, imgW]` x `[0, imgH]` so they can't go off-screen.
2. **X-axis handle vertical translation** — Dragging an X-axis handle (blue) now also updates `xAxisY`, translating both X handles vertically together. Previously handles were locked to horizontal-only movement.
3. **Y-axis handle horizontal translation** — Dragging a Y-axis handle (green) now also updates `yAxisX`, translating both Y handles horizontally together. Previously handles were locked to vertical-only movement.
4. **About page full width** — Removed `width: 1126px` and `border-inline` from `#root` in `index.css`. Changed App.tsx about-page `maxWidth` to `100%`. Changed about.html `.container` from `max-width: 1200px` to `max-width: 100%` with `padding: 40px 48px`. Content now fills available viewport width.

## What Changed (Iteration 8 — redeploy fix)
1. **TS build error fixed** — Removed unused `getHandlePixelPos` function from `AxisCalibration.tsx` (line 110). TypeScript strict mode (TS6133: declared but never read) caused `npm run build` to fail, which broke the Docker multi-stage build. This had caused 3 consecutive Railway deploy failures (742a8780, c4cc74c7, 1027b78c) before being caught and fixed.
2. **Successful redeploy** — Deployment 947e28f9 built and started successfully. Health check confirmed passing.

## What Changed (Phase 11c — post-user-testing fixes)
1. **Plot bbox background detection** — Added `_find_plot_bbox_background()` in `axis_detection.py` that detects the gray/colored background rectangle used by ggplot2, seaborn, etc. Uses color thresholding + contour detection. For testplot.png: old Hough method found (41,7,503,351) = right side cut off; new background method found (29,7,744,517) = full plot area. Algorithm uses whichever method returns the larger bbox.
2. **Back button legibility** — Changed all secondary buttons from `background: transparent; color: #475569` (white text on white bg due to CSS cascade) to `background: #f1f5f9; color: #1e293b` (light gray bg, dark text). Applied to AxisCalibration "Back" and ResultsView "New image" buttons.

## What Changed (Phase 11b — first round of user-testing fixes)
1. **Bounding box padding** — Increased default detection bounding box from 5% to 15% of axis span.
2. **About page width** — App container widens to 1400px on About page (was 800px). Report.html container 1200px (was 900px), hero subtitle 800px (was 600px).
3. **Instructional text** — Clarified that orange bounding box should cover ALL points including those beyond axis min/max.

## What Changed (Phase 11 — initial implementation)
1. **Constrained axis handles** — X handles (blue) only move horizontally. Y handles (green) only move vertically.
2. **Axis line dragging** — Drag X-axis line up/down, Y-axis line left/right to reposition.
3. **Precision zoom panel** — 200x200px zoom canvas at 8x magnification with crosshairs and label.
4. **Detection bounding box** — Orange dashed rectangle with 4 draggable corner handles.
5. **Backend DetectionBounds** — New dataclass, all 3 digitizers accept optional bounds parameter.
6. **4 new tests** — blob detector bounds tests + API bounds tests.

## What Changed (Phase 10)
1. **About page** — `report.html` copied to `frontend/public/about.html`, persistent nav bar with Digitizer/About tabs
2. **Translucent overlay** — Detected point fill opacity max 0.225, stroke max 0.65, radius 6px
3. **Independent axis handles** — X-axis (blue) and Y-axis (green) each have their own line with 2 handles
4. **Points outside handles** — Digitizers expand ROI by 10% padding (now superseded by detection_bounds)
5. **Clump tests + blob splitting** — 5 seeded clump configs, 4 randomized tests, watershed splitting

## What's Broken
- Nothing currently broken. All 48 tests pass.
- OCR axis label detection fails on real-world ggplot-style images (defaults to 0–10). User must manually set axis data ranges.

## Production Bugs Fixed (this session)
1. **Right-side points missed on ggplot plots** — Hough line detection picked up grid lines as plot boundaries, cutting off the right third of the plot. Fixed by adding background-color-based bbox detection.
2. **Back button invisible** — Global CSS `button { color: white }` overrode intended styling. Fixed with explicit light-gray background.
3. **Silent deploy failures** — Unused `getHandlePixelPos` in AxisCalibration.tsx caused TS6133 build error. 3 Railway deploys failed silently (old container kept serving). Fixed by removing the dead code.
4. **Y-coordinate scalar offset** — `handleConfirm` mixed `xAxisY` into `y_pixel_range`, causing all Y data coordinates to shift by a constant amount when X/Y axis positions diverged. Fixed by using only Y-axis handle positions.
5. **Calibration lost on re-edit** — "Adjust calibration" re-ran `detectAxes`, discarding user's handle positions and data ranges. Fixed by passing `previousCalibration` prop.
6. **Narrow About page** — About page was nested inside the digitizer's `maxWidth: 800` container (with Vite scaffold `text-align: center` on `#root` compounding the issue). Required 3 attempts to fix — final solution: separate render path with `100vw` fluid layout.

## Digitization Method Comparison (Final)
| Method | Mean Rate | Median Rate | Speed | Best On | Worst On |
|--------|-----------|-------------|-------|---------|----------|
| A: Blob | 85.4% | 95% | ~1ms | circles, squares, diamonds | triangles (0%) |
| B: Template | 78.5% | 78% | 300-4000ms | triangles, challenge plots | grids (slow) |
| C: **Hybrid** | **91.9%** | **95%** | 1-4000ms | all shapes | triangle+grid (0%) |

## Decisions Made (Do Not Revisit)
1. FastAPI for backend — lightweight, async, good for image processing endpoints
2. React frontend — Canvas API needed for fiducial overlay interaction
3. Docker-based deployment — portable to Railway/Fly.io/Render
4. Test-first approach — synthetic test harness before any digitization work
5. Multi-method exploration — all 3 methods implemented and compared via eval harness
6. Scoring tolerance default: 1% of axis range for point matching
7. Python venv at `.venv/` — system Python is externally managed (PEP 668)
8. Vite for frontend tooling — fast builds, good TypeScript support
9. **HybridDigitizer selected as production method** — agreement-based blob/template selection, 91.9% mean on 55 plots
10. Railway for cloud hosting — auto-deploys from Docker, generous free tier
11. CORS allow_origins=["*"] — frontend and backend served from same origin in production; wildcard is safe
12. Independent X/Y handles — cleaner UX, each axis placed independently with color coding
13. Dual bbox detection — background color detection (for ggplot/seaborn) + Hough lines (for matplotlib), use the larger result
14. Separate render paths for Digitizer vs About page — About page uses 100vw fluid layout, Digitizer uses maxWidth:800 centered
15. Y-pixel range for calibration must come solely from Y-axis handles, never from X-axis line position

## Known Issues
- Triangle + grid combo: 0% detection (both methods confused by grid intersections)
- X markers: 60-75% detection (thin cross shapes hard for both methods)
- Clumps with very tight spacing (<0.5% of axis range): watershed splitting finds fewer sub-blobs than actual points
- `/tmp` uploads are ephemeral — lost on container restart (acceptable for now)
- OCR (pytesseract) fails on many real-world plots — axis data ranges must be entered manually
