# WebPlotAutoDigitizer

## Session Recovery (READ THIS FIRST)
If you're starting a new session, recovering from compaction, or running in a Ralph loop:
1. Read `.ralph/ralph_task.md` — the anchor. Has all checkboxes. Defines "done."
2. Read `.ralph/progress.md` — what exists, what's broken, what to do next.
3. Read `.ralph/guardrails.md` — learned constraints. Follow every sign.
4. Do NOT re-read the full codebase unless progress.md says something is broken. Trust the files.
5. Pick up the "Current Focus" from progress.md and work on it.
6. Before exiting or if context feels heavy: update progress.md with what you did and what's next.

## Compaction Instructions
When compacting this conversation, preserve:
- Current task and its completion state
- Any new guardrails discovered this session
- Any new known issues
- The exact next step to take
- Current state of the method comparison table
Do NOT preserve: file contents already read, full API/command outputs, failed approaches
(log failures to .ralph/errors.log instead).

## Project Purpose
A web application that digitizes scatterplot images into structured data. Users upload a plot image, confirm axis calibration via interactive fiducials, and receive the plotted points as a downloadable/copyable CSV. Designed for researchers who need to extract data from published figures.

## Architecture
```
webplotautodigitizer/
├── backend/
│   ├── main.py                    — FastAPI app entry point, CORS, routes
│   ├── models.py                  — Pydantic models & dataclasses (AxisCalibration, DetectionResult, etc.)
│   ├── axis_detection.py          — Detect axis lines, ticks, labels from plot image
│   ├── calibration.py             — Pixel ↔ data coordinate transform using fiducial points
│   ├── digitizers/
│   │   ├── __init__.py            — Digitizer interface (ABC)
│   │   ├── blob_detector.py       — Method A: OpenCV blob/contour detection
│   │   ├── template_matcher.py    — Method B: Template matching with marker library
│   │   └── hybrid.py              — Method C: Designed after analyzing A & B failures
│   ├── digitizer_router.py        — Selects best digitizer or ensembles them
│   └── image_utils.py             — Normalization, validation, preprocessing
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                — Main app shell, routing between steps
│   │   ├── components/
│   │   │   ├── ImageUpload.tsx    — Drag-and-drop / file picker
│   │   │   ├── AxisCalibration.tsx — Canvas overlay with draggable fiducials
│   │   │   ├── ResultsView.tsx    — Detected points overlay + data table
│   │   │   └── CsvExport.tsx      — Copy/download CSV controls
│   │   └── api.ts                 — Fetch wrappers for backend endpoints
│   └── public/
│
├── tests/
│   ├── generate_plots.py          — Synthetic scatterplot generator (matplotlib)
│   ├── eval_digitizer.py          — Scoring harness (nearest-neighbor matching)
│   ├── fixtures/                  — Generated PNGs + ground-truth JSONs
│   ├── test_axis_detection.py
│   ├── test_calibration.py
│   ├── test_blob_detector.py
│   ├── test_template_matcher.py
│   ├── test_hybrid.py
│   ├── test_api.py
│   └── conftest.py                — Shared fixtures, test plot generation
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── package.json                   — (frontend)
├── CLAUDE.md
└── .ralph/
```

## Key Schemas / Interfaces

### AxisCalibration (the contract between axis detection and digitization)
```python
@dataclass
class AxisCalibration:
    # Pixel coordinates of the axis endpoints
    x_pixel_range: tuple[float, float]  # (x_min_px, x_max_px)
    y_pixel_range: tuple[float, float]  # (y_min_px, y_max_px) — NOTE: y increases downward in pixels
    # Data coordinates (what the axis labels say)
    x_data_range: tuple[float, float]   # (x_min_val, x_max_val)
    y_data_range: tuple[float, float]   # (y_min_val, y_max_val)

    def pixel_to_data(self, px_x: float, px_y: float) -> tuple[float, float]: ...
    def data_to_pixel(self, data_x: float, data_y: float) -> tuple[float, float]: ...
```

### DetectionResult
```python
@dataclass
class DetectedPoint:
    x_data: float
    y_data: float
    x_pixel: float
    y_pixel: float
    confidence: float  # 0.0–1.0

@dataclass
class DetectionResult:
    points: list[DetectedPoint]
    method: str  # "blob", "template", "hybrid"
    elapsed_ms: float
```

### API Endpoints
```
POST /api/upload          — image file → { image_id, width, height }
POST /api/detect-axes     — { image_id } → { axes: AxisCalibration, confidence }
POST /api/digitize        — { image_id, calibration: AxisCalibration } → DetectionResult
GET  /health              — { status: "ok" }
```

### Frontend → Backend Payload (calibration confirmation)
```json
{
  "image_id": "abc123",
  "calibration": {
    "x_pixel_range": [80, 720],
    "y_pixel_range": [520, 40],
    "x_data_range": [0, 100],
    "y_data_range": [0, 50]
  }
}
```

### Ground Truth (test harness)
```json
{
  "x": [1.2, 3.4, 5.6],
  "y": [7.8, 9.0, 2.1],
  "x_range": [0, 10],
  "y_range": [0, 10],
  "params": {
    "n_points": 3,
    "marker": "o",
    "marker_size": 6,
    "opacity": 1.0,
    "grid": false,
    "bg_color": "white",
    "dpi": 150,
    "figsize": [8, 6]
  }
}
```

### Eval Harness Output
```json
{
  "matched_pct": 95.0,
  "mean_error_x": 0.3,
  "mean_error_y": 0.5,
  "max_error": 1.2,
  "false_positives": 1,
  "false_negatives": 2,
  "tolerance_pct": 1.0,
  "n_ground_truth": 50,
  "n_predicted": 49
}
```

## Digitizer Interface (ABC)
```python
from abc import ABC, abstractmethod

class BaseDigitizer(ABC):
    @abstractmethod
    def digitize(self, image: np.ndarray, calibration: AxisCalibration) -> DetectionResult:
        """Detect scatter points in the plot region and return data coordinates."""
        ...
```
All digitizer methods must implement this interface so they can be swapped into the eval harness and the API interchangeably.

## Environment
- Python 3.11+
- FastAPI, uvicorn
- OpenCV (opencv-python-headless), scikit-image, numpy, scipy
- matplotlib (test-only, for synthetic plot generation)
- pytesseract or easyocr (for axis label reading — evaluate both)
- React 18+, TypeScript
- Docker (CPU only — no GPU)
- Test: `cd backend && pytest -v`
- Run: `docker-compose up`

## Design Principles
1. **Test harness first** — No digitization code is written until the eval framework can score any method against ground truth. This is non-negotiable.
2. **Methods are disposable, the interface is not** — All digitizers implement `BaseDigitizer`. If a method fails, we throw it away and try another. The API and frontend never know which method is running.
3. **User calibration is ground truth** — Auto-detected axes are suggestions. The user's fiducial adjustments override everything. The system must work even if auto-detection is completely wrong, as long as the user corrects the fiducials.
4. **Empirical method selection** — The best digitization method is chosen by eval harness scores, not by intuition. The comparison table in `progress.md` drives the decision.
5. **CPU only, <10s response** — Must deploy on cheap hosting without GPU. If a method is too slow, it's not viable.
6. **No magic image sizes** — The system must handle plots of varying pixel dimensions. All coordinate math goes through `AxisCalibration`, never hardcoded offsets.
