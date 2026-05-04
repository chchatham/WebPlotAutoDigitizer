from __future__ import annotations

from dataclasses import dataclass
from pydantic import BaseModel


@dataclass
class AxisCalibration:
    x_pixel_range: tuple[float, float]
    y_pixel_range: tuple[float, float]
    x_data_range: tuple[float, float]
    y_data_range: tuple[float, float]

    def pixel_to_data(self, px_x: float, px_y: float) -> tuple[float, float]:
        x_frac = (px_x - self.x_pixel_range[0]) / (self.x_pixel_range[1] - self.x_pixel_range[0])
        y_frac = (px_y - self.y_pixel_range[0]) / (self.y_pixel_range[1] - self.y_pixel_range[0])
        data_x = self.x_data_range[0] + x_frac * (self.x_data_range[1] - self.x_data_range[0])
        data_y = self.y_data_range[0] + y_frac * (self.y_data_range[1] - self.y_data_range[0])
        return data_x, data_y

    def data_to_pixel(self, data_x: float, data_y: float) -> tuple[float, float]:
        x_frac = (data_x - self.x_data_range[0]) / (self.x_data_range[1] - self.x_data_range[0])
        y_frac = (data_y - self.y_data_range[0]) / (self.y_data_range[1] - self.y_data_range[0])
        px_x = self.x_pixel_range[0] + x_frac * (self.x_pixel_range[1] - self.x_pixel_range[0])
        px_y = self.y_pixel_range[0] + y_frac * (self.y_pixel_range[1] - self.y_pixel_range[0])
        return px_x, px_y


@dataclass
class DetectedPoint:
    x_data: float
    y_data: float
    x_pixel: float
    y_pixel: float
    confidence: float


@dataclass
class DetectionResult:
    points: list[DetectedPoint]
    method: str
    elapsed_ms: float


class UploadResponse(BaseModel):
    image_id: str
    width: int
    height: int
    filename: str


class CalibrationRequest(BaseModel):
    image_id: str
    calibration: dict


@dataclass
class DetectionBounds:
    x_min_px: float
    x_max_px: float
    y_min_px: float
    y_max_px: float


@dataclass
class MarkerProfile:
    mean_radius_px: float
    std_radius_px: float
    mean_area_px: float
    is_hollow: bool
    edge_width_px: float
    circularity: float
    fill_ratio: float
    n_singletons: int


class HealthResponse(BaseModel):
    status: str
