from __future__ import annotations

import math
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.axis_detection import detect_axes
from backend.digitizers.hybrid import HybridDigitizer
from backend.image_utils import save_upload, load_image, UPLOAD_DIR, ImageValidationError
from backend.models import AxisCalibration, DetectionBounds, UploadResponse, HealthResponse

app = FastAPI(title="WebPlotAutoDigitizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@app.post("/api/upload", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    data = await file.read()
    try:
        image_id, width, height = save_upload(data, file.filename or "upload.png")
    except ImageValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return UploadResponse(
        image_id=image_id,
        width=width,
        height=height,
        filename=file.filename or "upload.png",
    )


@app.get("/api/image/{image_id}")
async def get_image(image_id: str):
    path = UPLOAD_DIR / f"{image_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")


class DetectAxesRequest(BaseModel):
    image_id: str


class DetectAxesResponse(BaseModel):
    axes: dict
    confidence: float


@app.post("/api/detect-axes", response_model=DetectAxesResponse)
async def detect_axes_endpoint(request: DetectAxesRequest):
    try:
        image = load_image(request.image_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")

    result = detect_axes(image)
    cal = result.calibration

    return DetectAxesResponse(
        axes={
            "x_pixel_range": list(cal.x_pixel_range),
            "y_pixel_range": list(cal.y_pixel_range),
            "x_data_range": list(cal.x_data_range),
            "y_data_range": list(cal.y_data_range),
        },
        confidence=result.confidence,
    )


class DigitizeRequest(BaseModel):
    image_id: str
    calibration: dict
    detection_bounds: dict | None = None
    expected_point_count: int | None = None


@app.post("/api/digitize")
async def digitize_endpoint(request: DigitizeRequest):
    try:
        image = load_image(request.image_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")

    cal_data = request.calibration
    x_px = tuple(cal_data["x_pixel_range"])
    y_px = tuple(cal_data["y_pixel_range"])

    if abs(x_px[1] - x_px[0]) < 1e-6 or abs(y_px[1] - y_px[0]) < 1e-6:
        raise HTTPException(
            status_code=400,
            detail="Invalid calibration: pixel ranges must not be zero-width",
        )

    cal = AxisCalibration(
        x_pixel_range=x_px,
        y_pixel_range=y_px,
        x_data_range=tuple(cal_data["x_data_range"]),
        y_data_range=tuple(cal_data["y_data_range"]),
    )

    bounds = None
    if request.detection_bounds:
        bounds = DetectionBounds(
            x_min_px=request.detection_bounds["x_min"],
            x_max_px=request.detection_bounds["x_max"],
            y_min_px=request.detection_bounds["y_min"],
            y_max_px=request.detection_bounds["y_max"],
        )

    try:
        digitizer = HybridDigitizer()
        result = digitizer.digitize(image, cal, bounds, request.expected_point_count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Digitization error: {str(e)}")

    def sanitize(v: float) -> float:
        v = float(v)
        if math.isnan(v) or math.isinf(v):
            return 0.0
        return v

    return {
        "points": [
            {
                "x_data": sanitize(p.x_data),
                "y_data": sanitize(p.y_data),
                "x_pixel": sanitize(p.x_pixel),
                "y_pixel": sanitize(p.y_pixel),
                "confidence": sanitize(p.confidence),
            }
            for p in result.points
        ],
        "method": result.method,
        "elapsed_ms": sanitize(result.elapsed_ms),
    }


if STATIC_DIR.exists():
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file_path = STATIC_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
