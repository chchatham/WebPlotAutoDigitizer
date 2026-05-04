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

## Current Focus
Complete. All phases done.
