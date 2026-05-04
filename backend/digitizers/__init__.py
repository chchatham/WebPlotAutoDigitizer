from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from backend.models import AxisCalibration, DetectionBounds, DetectionResult


class BaseDigitizer(ABC):
    @abstractmethod
    def digitize(
        self,
        image: np.ndarray,
        calibration: AxisCalibration,
        detection_bounds: DetectionBounds | None = None,
    ) -> DetectionResult:
        ...
