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
