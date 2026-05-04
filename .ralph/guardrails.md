# WebPlotAutoDigitizer — Guardrails

Append-only. Each sign is a constraint learned from experience or defined upfront.
Format: 🚧 SIGN: description

---

## Architecture Guardrails

🚧 SIGN: The synthetic test harness (Phase 1) must be complete and passing BEFORE any digitization method is implemented. Never skip ahead to digitization without the eval framework.

🚧 SIGN: The `AxisCalibration` dataclass is the contract between axis detection and point digitization. Both sides consume it. If you change its shape, update all consumers.

🚧 SIGN: Every digitization method must be evaluated through the SAME `tests/eval_digitizer.py` harness with the SAME baseline test suite. No ad-hoc "it looks right" testing.

🚧 SIGN: Do not delete or modify a digitization method's code when moving on to the next method. Keep all methods importable so they can be compared side-by-side at selection time.

🚧 SIGN: The frontend fiducial adjustment screen is critical for real-world accuracy. Auto-detected axes are a starting suggestion — user confirmation is the source of truth for calibration.

## Image Processing Guardrails

🚧 SIGN: Always convert uploaded images to RGB before processing. RGBA, grayscale, and CMYK inputs must be normalized.

🚧 SIGN: Do not assume white background. Many scatterplots have light gray or colored backgrounds, or grid lines that can confuse blob detection.

🚧 SIGN: Legend markers are a known source of false positives. Any digitization method must account for legend regions (typically upper-right, upper-left, or outside the plot area).

🚧 SIGN: Points sitting on axis lines or grid lines will have different color profiles than points on plain background. Test for this explicitly.

🚧 SIGN: Overlapping or very close points are an expected hard case. Track detection rate separately for dense vs sparse plots.

## Testing Guardrails

🚧 SIGN: Synthetic plot generation must use matplotlib's `savefig` with a fixed DPI (150) and fixed figure size (8x6 inches) to ensure consistency. Random DPI will break pixel-level tests.

🚧 SIGN: Ground truth JSON must store data coordinates, NOT pixel coordinates. The eval harness converts predicted pixel coords → data coords using the known calibration before comparing.

🚧 SIGN: The scoring tolerance (default 1% of axis range) is per-axis. A point at (10.1, 20.0) vs ground truth (10.0, 20.0) on a 0–100 x-axis is within tolerance (0.1 < 1.0).

🚧 SIGN: When eval reports "false positives," manually inspect a sample before assuming the digitizer is wrong — the ground truth generator itself could have edge-case bugs.

## Deployment Guardrails

🚧 SIGN: The Docker image must work without GPU. All image processing must use CPU-only libraries. Do not introduce torch/tensorflow unless there's no alternative and the image stays under 2GB.

🚧 SIGN: Uploaded images must be validated: max 10MB, must be PNG/JPG/WEBP, dimensions ≤ 4000x4000. Reject early with clear error messages.

🚧 SIGN: The `/api/digitize` endpoint must return results in under 10 seconds for a typical plot. If a method is slower, it needs optimization or it's not viable for production.

## Process Guardrails

🚧 SIGN: When a digitization method fails on a category of plots, log the failure mode clearly in `progress.md` under the method comparison table. This drives the design of the next method.

🚧 SIGN: Do not pick the "best" method until at least 2 methods have been fully evaluated. The comparison table in `progress.md` must be filled in.

🚧 SIGN: If a test fails twice for the same root cause, add a guardrail sign here before fixing it. The fix addresses the symptom; the sign prevents recurrence.

## Method Selection Guardrails (added Phase 5)

🚧 SIGN: The HybridDigitizer is the production method. It was selected based on eval results across 55 plots: 91.9% mean detection, 95% median. Do not swap to a single method without re-running the full eval harness comparison.

🚧 SIGN: The hybrid's agreement-based selection (blob vs template) uses confidence comparison, NOT a fixed threshold. When both methods find points at similar locations, the one with higher average confidence wins. This is critical for triangle markers where blob finds wrong centroids with lower confidence.

🚧 SIGN: Template matching is slow on grid plots (~4 seconds). If performance becomes an issue, optimize template matching before removing it — the hybrid only falls back to template when blob's confidence is low.

## Deployment Guardrails (added Phase 9 — Railway deployment)

🚧 SIGN: Debian Trixie (used by `python:3.11-slim`) removed `libgl1-mesa-glx`. Use `libgl1` instead. If upgrading the Python base image, check that OpenGL/OpenCV system deps still exist under the same package names.

🚧 SIGN: Railway assigns a dynamic PORT via environment variable. The Dockerfile CMD must use shell form (`CMD uvicorn ... --port ${PORT:-8000}`) not exec form (`CMD ["uvicorn", ...]`) so the variable expands at runtime.

🚧 SIGN: Frontend `VITE_API_URL` must default to `""` (empty string), NOT `http://localhost:8000`. In production the frontend and backend are served from the same origin, so relative paths work. Hardcoding localhost breaks production.

🚧 SIGN: Never use `crossOrigin="anonymous"` on `new Image()` when loading same-origin images. It forces a CORS preflight and if the server doesn't return `Access-Control-Allow-Origin`, the image load fails silently (triggers `onerror` not `onload`). Only use crossOrigin when actually loading cross-origin resources.

🚧 SIGN: CORS `allow_origins` must include the production domain, not just localhost. Using `["*"]` is acceptable when the frontend is same-origin and there are no cookie-based auth concerns. If credentials are added later, switch to an explicit origin list.

🚧 SIGN: In React canvas components, store loaded images in `useState`, NOT `useRef`. A ref update doesn't trigger re-renders, so the draw effect won't fire when the image loads asynchronously. State ensures the effect dependency array picks up the change.

🚧 SIGN: Railway `/tmp` is ephemeral — uploaded images are lost on redeploy or container restart. This is fine for the current stateless design but would need a persistent volume or object storage (S3/R2) if image persistence is required.

## UI & Detection Guardrails (added Phase 10)

🚧 SIGN: X-axis and Y-axis handles must be independent — each axis has its own line with 2 handles. Never share a corner point between axes. X handles are blue (#2563eb), Y handles are green (#16a34a).

🚧 SIGN: Detected point overlay must be translucent (max opacity ~0.5) so original plot markers are visible underneath. Users need to see which points were missed.

🚧 SIGN: Digitizer ROI must extend 10% beyond the calibration pixel range on each side. Points at or near axis boundaries are common in real plots and must not be clipped.

🚧 SIGN: The blob detector uses distance-transform watershed to split merged contours that are >1.8x the median single-blob area. This handles clumped/overlapping markers. Do not remove this without verifying clump test cases still pass.

🚧 SIGN: Some test cases use `seed=None` (randomized each run). These are intentional — they exercise the detector on fresh data. Do not add seeds to stabilize them; the assertion thresholds are set conservatively to allow variance.
