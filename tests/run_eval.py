"""Run the eval harness against all baseline plots for a given digitizer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from backend.digitizers.blob_detector import BlobDetector
from backend.digitizers.template_matcher import TemplateMatcher
from backend.digitizers.hybrid import HybridDigitizer
from backend.models import AxisCalibration
from tests.eval_digitizer import score_predictions
from tests.generate_plots import generate_baseline_suite


DETECTORS = {
    "blob": BlobDetector,
    "template": TemplateMatcher,
    "hybrid": HybridDigitizer,
}


def make_calibration(gt: dict, image: np.ndarray) -> AxisCalibration:
    h, w = image.shape[:2]
    return AxisCalibration(
        x_pixel_range=(w * 0.125, w * 0.9),
        y_pixel_range=(h * 0.88, h * 0.11),
        x_data_range=tuple(gt["x_range"]),
        y_data_range=tuple(gt["y_range"]),
    )


def run_eval(method_name: str):
    fixtures_dir = Path(__file__).parent / "fixtures"
    if not any(fixtures_dir.glob("*.png")):
        print("Generating baseline plots...")
        generate_baseline_suite(fixtures_dir)

    detector_cls = DETECTORS.get(method_name)
    if not detector_cls:
        print(f"Unknown method: {method_name}. Available: {list(DETECTORS.keys())}")
        return

    detector = detector_cls()
    print(f"\n=== Evaluating: {method_name} ({detector.__class__.__name__}) ===\n")

    json_files = sorted(fixtures_dir.glob("*.json"))
    results = []

    for jf in json_files:
        gt = json.loads(jf.read_text())
        img_path = jf.with_suffix(".png")
        img = np.array(Image.open(img_path).convert("RGB"))
        cal = make_calibration(gt, img)

        det = detector.digitize(img, cal)

        pred_x = np.array([p.x_data for p in det.points])
        pred_y = np.array([p.y_data for p in det.points])

        score = score_predictions(
            pred_x, pred_y,
            np.array(gt["x"]), np.array(gt["y"]),
            tuple(gt["x_range"]), tuple(gt["y_range"]),
            tolerance_pct=1.0,
        )

        label = jf.stem
        results.append((label, score, det))

        status = "OK" if score.matched_pct >= 80 else "WARN" if score.matched_pct >= 50 else "FAIL"
        print(f"[{status}] {label}: {score.matched_pct:.1f}% matched, "
              f"err_x={score.mean_error_x:.3f} err_y={score.mean_error_y:.3f}, "
              f"FP={score.false_positives} FN={score.false_negatives} "
              f"({score.n_predicted} pred / {score.n_ground_truth} truth) "
              f"[{det.elapsed_ms:.1f}ms]")

    matched_rates = [r[1].matched_pct for r in results]
    print(f"\n--- Summary ---")
    print(f"Mean detection rate: {np.mean(matched_rates):.1f}%")
    print(f"Median detection rate: {np.median(matched_rates):.1f}%")
    print(f"Min detection rate: {np.min(matched_rates):.1f}%")
    print(f"Plots ≥80%: {sum(1 for m in matched_rates if m >= 80)}/{len(matched_rates)}")
    print(f"Plots ≥50%: {sum(1 for m in matched_rates if m >= 50)}/{len(matched_rates)}")


def main():
    methods = sys.argv[1:] if len(sys.argv) > 1 else list(DETECTORS.keys())
    for method in methods:
        run_eval(method)


if __name__ == "__main__":
    main()
