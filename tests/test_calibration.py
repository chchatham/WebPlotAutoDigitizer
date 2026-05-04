from __future__ import annotations

from backend.models import AxisCalibration


def test_pixel_to_data_basic():
    cal = AxisCalibration(
        x_pixel_range=(100.0, 700.0),
        y_pixel_range=(500.0, 50.0),
        x_data_range=(0.0, 10.0),
        y_data_range=(0.0, 10.0),
    )

    x, y = cal.pixel_to_data(100.0, 500.0)
    assert abs(x - 0.0) < 0.001
    assert abs(y - 0.0) < 0.001

    x, y = cal.pixel_to_data(700.0, 50.0)
    assert abs(x - 10.0) < 0.001
    assert abs(y - 10.0) < 0.001

    x, y = cal.pixel_to_data(400.0, 275.0)
    assert abs(x - 5.0) < 0.001
    assert abs(y - 5.0) < 0.001


def test_data_to_pixel_roundtrip():
    cal = AxisCalibration(
        x_pixel_range=(80.0, 720.0),
        y_pixel_range=(520.0, 40.0),
        x_data_range=(-5.0, 5.0),
        y_data_range=(-5.0, 5.0),
    )

    for dx, dy in [(0.0, 0.0), (-5.0, -5.0), (5.0, 5.0), (2.5, -2.5)]:
        px, py = cal.data_to_pixel(dx, dy)
        rx, ry = cal.pixel_to_data(px, py)
        assert abs(rx - dx) < 0.001
        assert abs(ry - dy) < 0.001


def test_negative_ranges():
    cal = AxisCalibration(
        x_pixel_range=(50.0, 750.0),
        y_pixel_range=(550.0, 50.0),
        x_data_range=(-10.0, 10.0),
        y_data_range=(-100.0, 100.0),
    )

    x, y = cal.pixel_to_data(400.0, 300.0)
    assert abs(x - 0.0) < 0.01
    assert abs(y - 0.0) < 0.1
