from __future__ import annotations

import io
import json

import numpy as np
from PIL import Image

from tests.generate_plots import PlotConfig, generate_plot
from tests.eval_digitizer import score_predictions


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_png(client):
    img = Image.new("RGB", (200, 150), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)

    resp = client.post("/api/upload", files={"file": ("test.png", buf, "image/png")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["width"] == 200
    assert data["height"] == 150
    assert len(data["image_id"]) == 12
    assert data["filename"] == "test.png"


def test_upload_rejects_large_dimension(client):
    img = Image.new("RGB", (5000, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)

    resp = client.post("/api/upload", files={"file": ("big.png", buf, "image/png")})
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


def test_upload_rejects_bad_extension(client):
    buf = io.BytesIO(b"not an image")
    resp = client.post("/api/upload", files={"file": ("test.bmp", buf, "image/bmp")})
    assert resp.status_code == 400
    assert "unsupported" in resp.json()["detail"].lower()


def test_digitize_with_detection_bounds(client):
    img = Image.new("RGB", (400, 300), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)

    upload_resp = client.post("/api/upload", files={"file": ("test.png", buf, "image/png")})
    assert upload_resp.status_code == 200
    image_id = upload_resp.json()["image_id"]

    resp = client.post("/api/digitize", json={
        "image_id": image_id,
        "calibration": {
            "x_pixel_range": [50, 350],
            "y_pixel_range": [250, 50],
            "x_data_range": [0, 10],
            "y_data_range": [0, 10],
        },
        "detection_bounds": {
            "x_min": 20,
            "x_max": 380,
            "y_min": 20,
            "y_max": 280,
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "points" in data
    assert "method" in data


def test_digitize_without_detection_bounds(client):
    img = Image.new("RGB", (400, 300), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)

    upload_resp = client.post("/api/upload", files={"file": ("test.png", buf, "image/png")})
    assert upload_resp.status_code == 200
    image_id = upload_resp.json()["image_id"]

    resp = client.post("/api/digitize", json={
        "image_id": image_id,
        "calibration": {
            "x_pixel_range": [50, 350],
            "y_pixel_range": [250, 50],
            "x_data_range": [0, 10],
            "y_data_range": [0, 10],
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "points" in data


def test_digitize_missing_image_returns_404(client):
    """When the image ID doesn't exist, return 404 with a JSON error message."""
    resp = client.post("/api/digitize", json={
        "image_id": "nonexistent_id",
        "calibration": {
            "x_pixel_range": [50, 350],
            "y_pixel_range": [250, 50],
            "x_data_range": [0, 10],
            "y_data_range": [0, 10],
        },
    })
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_digitize_degenerate_calibration_returns_400(client):
    """When pixel ranges have zero width, return 400 instead of crashing."""
    img = Image.new("RGB", (400, 300), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)

    upload_resp = client.post("/api/upload", files={"file": ("test.png", buf, "image/png")})
    image_id = upload_resp.json()["image_id"]

    resp = client.post("/api/digitize", json={
        "image_id": image_id,
        "calibration": {
            "x_pixel_range": [200, 200],
            "y_pixel_range": [150, 150],
            "x_data_range": [0, 10],
            "y_data_range": [0, 10],
        },
    })
    assert resp.status_code == 400
    assert "zero-width" in resp.json()["detail"].lower()


def test_digitize_response_has_no_nan_or_null(client):
    """All numeric fields in the digitize response must be finite numbers, never NaN/null."""
    import cv2
    img_arr = np.ones((400, 600, 3), dtype=np.uint8) * 255
    for x, y in [(150, 200), (300, 100), (450, 300)]:
        cv2.circle(img_arr, (x, y), 8, (0, 0, 0), -1)

    pil_img = Image.fromarray(img_arr)
    buf = io.BytesIO()
    pil_img.save(buf, "PNG")
    buf.seek(0)

    upload_resp = client.post("/api/upload", files={"file": ("test.png", buf, "image/png")})
    image_id = upload_resp.json()["image_id"]

    resp = client.post("/api/digitize", json={
        "image_id": image_id,
        "calibration": {
            "x_pixel_range": [50, 550],
            "y_pixel_range": [350, 50],
            "x_data_range": [0, 10],
            "y_data_range": [0, 10],
        },
        "detection_bounds": {
            "x_min": 30,
            "x_max": 570,
            "y_min": 30,
            "y_max": 370,
        },
        "expected_point_count": 3,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["points"], list)
    assert isinstance(data["elapsed_ms"], (int, float))
    assert np.isfinite(data["elapsed_ms"])

    for i, pt in enumerate(data["points"]):
        for field in ["x_data", "y_data", "x_pixel", "y_pixel", "confidence"]:
            val = pt[field]
            assert val is not None, f"point[{i}].{field} is None"
            assert np.isfinite(val), f"point[{i}].{field} = {val} (not finite)"


def test_digitize_y_coordinate_accuracy(client, tmp_path):
    """End-to-end test: upload synthetic plot, digitize via API, verify returned
    data coordinates (what the CSV would contain) match ground truth."""
    cfg = PlotConfig(n_points=15, marker="o", marker_size="large", seed=42, label="api_y_acc")
    out = generate_plot(cfg, tmp_path)

    gt = json.loads(out.json_path.read_text())
    pil_img = Image.open(out.image_path).convert("RGB")
    w, h = pil_img.size

    buf = io.BytesIO()
    pil_img.save(buf, "PNG")
    buf.seek(0)

    upload_resp = client.post("/api/upload", files={"file": ("plot.png", buf, "image/png")})
    assert upload_resp.status_code == 200
    image_id = upload_resp.json()["image_id"]

    x_min_px = w * 0.125
    x_max_px = w * 0.9
    y_min_px = h * 0.88
    y_max_px = h * 0.11

    resp = client.post("/api/digitize", json={
        "image_id": image_id,
        "calibration": {
            "x_pixel_range": [x_min_px, x_max_px],
            "y_pixel_range": [y_min_px, y_max_px],
            "x_data_range": list(gt["x_range"]),
            "y_data_range": list(gt["y_range"]),
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["points"]) > 0

    pred_x = np.array([p["x_data"] for p in data["points"]])
    pred_y = np.array([p["y_data"] for p in data["points"]])

    score = score_predictions(
        pred_x, pred_y,
        np.array(gt["x"]), np.array(gt["y"]),
        tuple(gt["x_range"]), tuple(gt["y_range"]),
        tolerance_pct=2.0,
    )
    assert score.matched_pct >= 50.0, f"Only matched {score.matched_pct}% (need >=50%)"
    assert score.mean_error_y < 1.0, f"Y mean error {score.mean_error_y} too high (scalar offset?)"
