from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from backend.models import AxisCalibration, DetectionResult


class BaseDigitizer(ABC):
    @abstractmethod
    def digitize(self, image: np.ndarray, calibration: AxisCalibration) -> DetectionResult:
        ...
