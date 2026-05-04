# WebPlotAutoDigitizer — Task Anchor

## Success Criteria
All checkboxes checked. All tests pass. App deployable to a hosted service.

## Environment
- Language: Python 3.11+ (backend), TypeScript/React (frontend)
- Backend framework: FastAPI
- Image processing: OpenCV, scikit-image, numpy
- Frontend: React + Canvas API
- Testing: pytest (backend), generated synthetic plots via matplotlib
- Deployment target: Docker container (Railway / Fly.io / Render compatible)

---

## Phase 0 — Project Scaffolding
- [x] Initialize FastAPI backend with health endpoint
- [x] Initialize React frontend with file upload component
- [x] Create Dockerfile and docker-compose.yml for local dev
- [x] Set up pytest with a single passing smoke test
- [x] Wire frontend → backend image upload round-trip (upload returns echo metadata)

## Phase 1 — Synthetic Test Harness
> Build the test infrastructure FIRST. Every digitization method will be evaluated against these.
- [x] Write `tests/generate_plots.py` — generates synthetic scatterplots via matplotlib with known ground-truth data
- [x] Generator supports parameterized: point count (5, 20, 50, 200), marker shape (circle, square, triangle, x, diamond), marker size (small/med/large), opacity (1.0, 0.7, 0.4), axis range (integers, floats, negative), grid lines (on/off), background color (white, light gray)
- [x] Generator saves each plot as PNG + companion JSON `{x: [...], y: [...], x_range: [min,max], y_range: [min,max], params: {...}}`
- [x] Write `tests/eval_digitizer.py` — scoring harness that takes predicted points + ground truth and reports: matched %, mean positional error, max error, false positives, false negatives
- [x] Scoring uses nearest-neighbor matching with configurable tolerance (default: 1% of axis range)
- [x] Create baseline test suite: 20 generated plots spanning the parameter space
- [x] All test generation and evaluation passes as pytest fixtures

## Phase 2 — Axis Detection & Calibration
- [x] Implement axis line detection (find the two primary axis lines in image)
- [x] Implement tick mark detection along each axis
- [x] Implement OCR or template-based reading of axis labels/numbers
- [x] Build calibration model: pixel coordinates ↔ data coordinates mapping given fiducial points
- [x] Expose `/api/detect-axes` endpoint: image in → detected axes + suggested fiducial points out
- [x] Frontend: display uploaded image with overlay of detected axes, allow user to confirm/adjust fiducials and enter min/max values
- [x] Calibration unit tests: synthetic plots with known axis ranges → detected range within 2% error
- [x] Store calibration as a typed dataclass: `AxisCalibration(x_pixel_range, y_pixel_range, x_data_range, y_data_range)`

## Phase 3 — Point Digitization (Method A: Color/Blob Detection)
> First attempt. May or may not be the final method.
- [x] Implement blob detection approach (e.g., SimpleBlobDetector or contour-based)
- [x] Apply calibration to convert detected blob centers from pixel → data coordinates
- [x] Expose `/api/digitize` endpoint: image + calibration → list of (x, y) data points
- [x] Run eval harness against baseline test suite, record results in `.ralph/progress.md`
- [x] Document failure modes (which plot types break this method) in `progress.md`

## Phase 4 — Point Digitization (Method B: Template Matching)
> Second technique. Compare against Method A.
- [x] Implement template matching approach (cross-correlation with marker templates)
- [x] Support multiple marker templates (circle, square, triangle, etc.)
- [x] Run eval harness, record results alongside Method A scores
- [x] Compare: which method wins on which plot categories?
- [x] Document findings in `progress.md`

## Phase 5 — Point Digitization (Method C: ML/Heuristic Hybrid)
> Third technique, informed by what broke in A and B. May be skipped if A or B is sufficient.
- [x] Design approach based on failure analysis of Methods A and B
- [x] Implement method C
- [x] Run eval harness, compare all three methods
- [x] Select best method (or ensemble) as the production digitizer
- [x] Document method selection rationale as a guardrail decision

## Phase 6 — Method Selection & Hardening
- [x] Finalize the production digitizer (single method or ensemble router)
- [x] Add confidence scores per detected point
- [x] Handle edge cases: overlapping points, points on grid lines, points on axis lines, legend markers (false positives)
- [x] Expand test suite to 50+ plots including adversarial cases
- [x] All tests pass with ≥90% point detection rate and ≤2% positional error on non-adversarial plots

## Phase 7 — Full Web UI
- [x] Upload flow: drag-and-drop or file picker for plot image
- [x] Axis calibration screen: image with overlaid detected axes, draggable fiducial handles, numeric range inputs
- [x] Digitization results screen: image with overlaid detected points, data table below
- [x] "Copy CSV" button — copies comma-delimited `x,y` rows to clipboard
- [x] "Download CSV" button
- [x] Error/loading states for all async operations
- [x] Responsive layout (usable on tablet)

## Phase 8 — Deployment & Polish
- [x] Dockerfile builds and runs cleanly
- [x] `docker-compose up` starts full stack locally
- [x] Add a landing page explaining the tool
- [x] README with deployment instructions for Railway/Fly.io/Render
- [x] Final end-to-end test: upload a real-world scatterplot screenshot, digitize, verify output makes sense

---

## Phase 9 — GitHub & Cloud Deployment
- [x] Initialize git repo, create `.gitignore`
- [x] Create GitHub repo (https://github.com/chchatham/WebPlotAutoDigitizer)
- [x] Push all code to GitHub
- [x] Install Railway CLI, authenticate
- [x] Create Railway project, deploy via `railway up`
- [x] Fix Dockerfile for Debian Trixie (`libgl1` replaces `libgl1-mesa-glx`)
- [x] Fix Railway PORT env var (shell form CMD)
- [x] Fix frontend API base URL for production (empty string = same-origin)
- [x] Generate public Railway domain
- [x] Fix canvas rendering (image ref → state)
- [x] Fix CORS origins (allow all) and remove `crossOrigin="anonymous"`
- [x] Health check passes on live URL
- [ ] User confirms calibration screen works end-to-end in production
- [x] Write project report (`report.html`)

## Phase 10 — Refinements (User-Requested)
- [x] About page: serve report.html as an About tab accessible from anywhere in the app
- [x] Translucent overlay: detected points drawn with low opacity so original markers show through
- [x] Independent axis handles: X-axis (blue) and Y-axis (green) each have their own line with 2 handles, no shared corner
- [x] Fix points-outside-handles: digitizers expand ROI by 10% padding so edge points are found
- [x] Clump test cases: 5 seeded clump configs + 4 randomized-per-run clump/scatter tests + watershed blob splitting
- [x] All 43 tests pass
- [x] Deploy revised version to Railway for user testing

## Phase 11 — Axis Constraints, Zoom Panel, Detection Bounding Box
- [x] Spec written (.ralph/spec_phase11.md)
- [x] Constrained axis handles: X handles move horizontally only, Y handles move vertically only
- [x] Axis line dragging: drag X-axis line up/down, Y-axis line left/right to reposition
- [x] High-res zoom panel: 8x magnified view of active handle with crosshairs
- [x] Detection bounding box: orange draggable rectangle defining point search area
- [x] Backend: DetectionBounds dataclass, passed through API → digitizers
- [x] All digitizers (blob, template, hybrid) accept optional detection_bounds for ROI
- [x] API accepts detection_bounds in /api/digitize request
- [x] 4 new tests (2 blob detector bounds tests + 2 API tests), all 47 tests pass
- [x] Frontend builds cleanly
- [x] Deploy to Railway
- [x] Phase 11b fixes: Back button label (transparent→light gray bg), 15% bounding box padding, wider About page
- [x] Phase 11c fixes: Background-color-based plot bbox detection for ggplot-style plots, robust button styling
- [x] Deploy 11c to Railway
- [x] Fix TS6133 build error (unused `getHandlePixelPos`), redeploy successfully (deployment 947e28f9)
- [ ] User confirms all changes work in production

## Phase 12 — User-Requested Refinements (2026-05-04)
- [x] Bounding box: clamp corners to visible image bounds (init + drag)
- [x] X-axis handles: dragging vertically translates both handles together (updates xAxisY)
- [x] Y-axis handles: dragging horizontally translates both handles together (updates yAxisX)
- [x] About page: remove fixed-width constraints — content fills available viewport width
- [x] Frontend builds cleanly, all 47 tests pass
- [x] Deploy Phase 12 to Railway (deployment d183b59a, SUCCESS)

## Phase 13 — Y-Coordinate Fix, Calibration Persistence, Layout (2026-05-04)
- [x] Fix Y-coordinate scalar offset: `y_pixel_range` was using `Math.max(yBottomY, xAxisY)` instead of `yBottomY`
- [x] Calibration persistence: "Adjust calibration" now restores prior handle positions, data ranges, and bounding box
- [x] About page fluid layout: separate render path with 100vw container, borderless full-width iframe
- [x] Stripped Vite scaffold CSS from `#root` (text-align:center, flex column, margin:0 auto)
- [x] New test: `test_digitize_y_coordinate_accuracy` — end-to-end API test verifying data coordinate accuracy including Y
- [x] All 48 tests pass, frontend builds cleanly
- [x] Deploy Phase 13 to Railway (final: deployment 27a52dea, SUCCESS)
- [ ] User confirms all changes

## Phase 14 — Shape-Aware Clump Decomposition (2026-05-04)
> Improve detection of overlapping/clumped points by estimating marker shape from singletons, then fitting markers into clump silhouettes. Add optional user point-count constraint.

### 14a — Test Framework Expansion
- [x] Add `OverlapConfig` dataclass to `generate_plots.py` (controls overlap fraction, pair count, isolated count)
- [x] Add `fill_style` ("filled"/"unfilled") and `edge_width` params to `PlotConfig`
- [x] Add `marker_color` param to `PlotConfig` (support non-black markers)
- [x] Generate overlap test suite: ~30 new cases (filled overlaps, unfilled overlaps, various backgrounds, various sizes, mixed isolated+clumped, point-count-hint tests)
- [x] Update `eval_digitizer.py` with `clump_recall`, `singleton_recall`, `clump_precision` metrics
- [x] New test file `tests/test_shape_aware.py` with test stubs
- [x] New test file `tests/test_clump_decomposition.py` with integration test stubs
- [x] All existing 48 tests still pass after framework changes (63 pass total, 14 skipped stubs)

### 14b — Marker Profile Estimation
- [x] Add `MarkerProfile` dataclass to `backend/models.py`
- [x] Implement `estimate_marker_profile()` function: analyze singletons → compute mean radius, area, hollow/filled, edge width, circularity, fill ratio
- [x] Hollow detection: fill_ratio threshold at ~0.7 to classify filled vs unfilled
- [x] Unit tests for profile estimation on synthetic singletons (4 tests pass)

### 14c — Filled-Marker Clump Decomposition
- [x] Implement `decompose_filled_clump()`: iterative erosion + distance transform, guided by marker profile
- [x] Point count estimation: `N = round(clump_area / profile.mean_area)`
- [x] Center refinement via local peak-finding in distance transform
- [x] Integration tests: filled circle overlaps at 20%, 30%, 50% overlap fractions — measure clump recall
- [ ] Clump recall ≥ 75% on filled overlaps with ≤50% overlap (currently ~40%+, needs tuning)

### 14d — Hollow-Marker Clump Decomposition
- [x] Implement `decompose_hollow_clump()`: Hough circle detection with known radius ± tolerance
- [x] Fallback to filled-marker algorithm when Hough finds too few
- [x] Integration tests: unfilled circle overlaps — measure clump recall
- [ ] Clump recall ≥ 85% on unfilled circle overlaps (currently ~30%+, needs tuning)

### 14e — User Point Count Constraint
- [x] Add `expected_point_count: int | None` to `/api/digitize` request parsing
- [x] Pass through to digitizers (optional param, default None)
- [x] Implement constraint pressure logic: soft adjustment of thresholds toward target count
- [x] Frontend: add "Expected number of points" input on AxisCalibration screen
- [x] Update `frontend/src/api.ts` to include `expected_point_count` in request
- [x] Tests: point count hint effect test passes (correct hint produces valid results, no crash)

### 14f — ShapeAwareDetector & Hybrid Routing
- [x] Create `backend/digitizers/shape_aware.py` implementing `ShapeAwareDetector`
- [x] Integrate profile estimation → clump decomposition pipeline
- [x] Update `HybridDigitizer` to route to ShapeAwareDetector when clumps detected
- [x] Routing condition: >20% of detected area is in clumps (contours > 1.8x median)
- [x] Full eval comparison: ShapeAwareDetector vs Phase 13 HybridDigitizer on overlap test suite (documented in progress.md)
- [x] All existing tests still pass (78 pass, no regression)
- [x] `/api/digitize` < 10s with shape-aware decomposition active

### 14g — Deployment
- [x] Frontend builds cleanly
- [x] Deploy to Railway (deployment 8abf8b28, SUCCESS)
- [ ] User confirms improved clump detection in production

## Current Focus
Phase 14 — Shape-aware clump decomposition. Start with 14a (test framework expansion).
