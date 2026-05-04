# WebPlotAutoDigitizer — Progress

## Last Updated
Iteration 3 — All phases complete. 2026-05-04.

## Current Focus
Done. All 8 phases complete. All checkboxes checked. 35 tests pass.

## What Exists
- **Backend** (5 endpoints): `/health`, `/api/upload`, `/api/image/{id}`, `/api/detect-axes`, `/api/digitize`
- **Axis detection**: Hough line bbox detection, optional OCR, AxisCalibration dataclass
- **3 Digitizers**: BlobDetector (A), TemplateMatcher (B), HybridDigitizer (C — production)
- **Test harness**: 55 baseline plots, eval scorer, 35 passing pytest tests
- **Frontend**: 3-step wizard (Upload → AxisCalibration → ResultsView + CsvExport), responsive CSS
- **Docker**: Multi-stage Dockerfile, docker-compose.yml, .dockerignore
- **Static serving**: Backend serves frontend build from `/static` in production
- **README**: With deployment instructions for Railway/Fly.io/Render

## What's Broken
Nothing.

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

## Known Issues
- Triangle + grid combo: 0% detection (both methods confused by grid intersections)
- X markers: 60-75% detection (thin cross shapes hard for both methods)
- Docker untested locally (Docker not installed on dev machine)
