# WebPlotAutoDigitizer — Progress

## Last Updated
Iteration 5 — Phase 10 refinements. 2026-05-04.

## Current Focus
Phase 10 complete. Deploying to Railway for user testing.

## What Exists
- **Backend** (5 endpoints): `/health`, `/api/upload`, `/api/image/{id}`, `/api/detect-axes`, `/api/digitize`
- **Axis detection**: Hough line bbox detection, optional OCR, AxisCalibration dataclass
- **3 Digitizers**: BlobDetector (A, with watershed splitting), TemplateMatcher (B), HybridDigitizer (C — production)
- **Test harness**: 60 baseline plots + 8 randomized-per-run tests, eval scorer, 43 passing pytest tests
- **Frontend**: 3-step wizard (Upload → AxisCalibration → ResultsView + CsvExport), About page, responsive CSS
- **Docker**: Multi-stage Dockerfile, docker-compose.yml, .dockerignore
- **Static serving**: Backend serves frontend build from `/static` in production
- **README**: With deployment instructions for Railway/Fly.io/Render
- **GitHub repo**: https://github.com/chchatham/WebPlotAutoDigitizer
- **Live deployment**: https://webplotautodigitizer-production.up.railway.app
- **Railway project**: https://railway.com/project/37e40b77-e1e3-4521-8b6c-2fb6a59bc2c7
- **Project report**: `report.html` — also served as About page at `/about.html`

## What Changed (Phase 10)
1. **About page** — `report.html` copied to `frontend/public/about.html`, persistent nav bar with Digitizer/About tabs, About renders in iframe
2. **Translucent overlay** — Detected point fill opacity reduced from max 1.0 to max 0.225, stroke max 0.65. Radius increased to 6px for hollow-ring appearance. Original markers visible underneath.
3. **Independent axis handles** — X-axis (blue) and Y-axis (green) each have 2 draggable handles with their own line. Handles labeled "X min", "X max", "Y min", "Y max". No shared corner. Calibration computed from handle positions.
4. **Points outside handles** — Both blob_detector.py and template_matcher.py now expand ROI by 10% of axis span on each side. Points near/beyond axis endpoints are detected.
5. **Clump tests + blob splitting** — 5 seeded clump configs (56-60) with ClumpSpec dataclass. 4 randomized clump tests + 4 randomized scatter tests. BlobDetector now uses distance-transform watershed to split merged contours into sub-blobs.

## What's Broken
- Nothing currently broken. All 43 tests pass.

## Production Bugs Fixed (this session)
(None — Phase 10 was feature additions, not bug fixes)

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

## Known Issues
- Triangle + grid combo: 0% detection (both methods confused by grid intersections)
- X markers: 60-75% detection (thin cross shapes hard for both methods)
- Clumps with very tight spacing (<0.5% of axis range): watershed splitting finds fewer sub-blobs than actual points
- `/tmp` uploads are ephemeral — lost on container restart (acceptable for now)
