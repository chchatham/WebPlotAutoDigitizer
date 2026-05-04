from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tests.generate_plots import PlotConfig, generate_plot, generate_baseline_suite


def test_generate_single_plot(tmp_path: Path):
    cfg = PlotConfig(n_points=10, marker="o", seed=42, label="test_single")
    out = generate_plot(cfg, tmp_path)

    assert out.image_path.exists()
    assert out.json_path.exists()
    assert len(out.x) == 10
    assert len(out.y) == 10

    gt = json.loads(out.json_path.read_text())
    assert len(gt["x"]) == 10
    assert gt["x_range"] == [0.0, 10.0]
    assert gt["params"]["dpi"] == 150
    assert gt["params"]["figsize"] == [8, 6]


def test_generate_deterministic(tmp_path: Path):
    cfg = PlotConfig(n_points=15, seed=99, label="det_a")
    a = generate_plot(cfg, tmp_path)

    cfg2 = PlotConfig(n_points=15, seed=99, label="det_b")
    b = generate_plot(cfg2, tmp_path)

    assert a.x == b.x
    assert a.y == b.y


def test_generate_respects_axis_range(tmp_path: Path):
    cfg = PlotConfig(n_points=50, x_range=(-3.0, 3.0), y_range=(10.0, 20.0), seed=7, label="range_test")
    out = generate_plot(cfg, tmp_path)

    assert all(-3.0 <= v <= 3.0 for v in out.x)
    assert all(10.0 <= v <= 20.0 for v in out.y)


def test_baseline_suite_generates_20_plots(tmp_path: Path):
    results = generate_baseline_suite(tmp_path)
    assert len(results) == 55
    for r in results:
        assert r.image_path.exists()
        assert r.json_path.exists()


def test_ground_truth_json_schema(tmp_path: Path):
    cfg = PlotConfig(n_points=5, seed=1, label="schema_check")
    out = generate_plot(cfg, tmp_path)
    gt = json.loads(out.json_path.read_text())

    required_keys = {"x", "y", "x_range", "y_range", "params"}
    assert required_keys <= set(gt.keys())

    param_keys = {"n_points", "marker", "marker_size", "opacity", "grid", "bg_color", "dpi", "figsize"}
    assert param_keys <= set(gt["params"].keys())
