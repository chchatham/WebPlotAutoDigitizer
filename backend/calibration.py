"""Calibration utilities for pixel <-> data coordinate transforms.

The AxisCalibration dataclass handles the core transform. This module provides
helpers for building calibrations from user-supplied fiducial points.
"""
from __future__ import annotations

from backend.models import AxisCalibration


def calibration_from_fiducials(
    x_pixel_range: tuple[float, float],
    y_pixel_range: tuple[float, float],
    x_data_range: tuple[float, float],
    y_data_range: tuple[float, float],
) -> AxisCalibration:
    return AxisCalibration(
        x_pixel_range=x_pixel_range,
        y_pixel_range=y_pixel_range,
        x_data_range=x_data_range,
        y_data_range=y_data_range,
    )
