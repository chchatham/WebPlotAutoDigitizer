from __future__ import annotations

import io

from PIL import Image


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
