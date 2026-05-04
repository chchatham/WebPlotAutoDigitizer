"""Synthetic scatterplot generator with known ground-truth data.

Generates PNG images + companion JSON files for evaluation.
Parameterized over: point count, marker shape, marker size, opacity,
axis range, grid lines, and background color.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FIXED_DPI = 150
FIXED_FIGSIZE = (8, 6)

MarkerShape = Literal["o", "s", "^", "x", "D"]
MarkerSizeName = Literal["small", "medium", "large"]

MARKER_SIZES: dict[MarkerSizeName, int] = {"small": 20, "medium": 40, "large": 80}


@dataclass
class PlotConfig:
    n_points: int = 20
    marker: MarkerShape = "o"
    marker_size: MarkerSizeName = "medium"
    opacity: float = 1.0
    x_range: tuple[float, float] = (0.0, 10.0)
    y_range: tuple[float, float] = (0.0, 10.0)
    grid: bool = False
    bg_color: str = "white"
    seed: int | None = None
    label: str = ""


@dataclass
class PlotOutput:
    image_path: Path
    json_path: Path
    config: PlotConfig
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)


def generate_plot(config: PlotConfig, output_dir: Path) -> PlotOutput:
    rng = np.random.default_rng(config.seed)

    x = rng.uniform(config.x_range[0], config.x_range[1], config.n_points)
    y = rng.uniform(config.y_range[0], config.y_range[1], config.n_points)

    fig, ax = plt.subplots(figsize=FIXED_FIGSIZE, dpi=FIXED_DPI)
    fig.set_facecolor(config.bg_color)
    ax.set_facecolor(config.bg_color)

    ax.scatter(
        x, y,
        marker=config.marker,
        s=MARKER_SIZES[config.marker_size],
        alpha=config.opacity,
        color="black",
        zorder=5,
    )

    ax.set_xlim(config.x_range)
    ax.set_ylim(config.y_range)
    ax.grid(config.grid)

    label = config.label or f"n{config.n_points}_{config.marker}_{config.marker_size}"
    image_path = output_dir / f"{label}.png"
    json_path = output_dir / f"{label}.json"

    fig.savefig(image_path, dpi=FIXED_DPI, facecolor=fig.get_facecolor())
    plt.close(fig)

    ground_truth = {
        "x": x.tolist(),
        "y": y.tolist(),
        "x_range": list(config.x_range),
        "y_range": list(config.y_range),
        "params": {
            "n_points": config.n_points,
            "marker": config.marker,
            "marker_size": MARKER_SIZES[config.marker_size],
            "opacity": config.opacity,
            "grid": config.grid,
            "bg_color": config.bg_color,
            "dpi": FIXED_DPI,
            "figsize": list(FIXED_FIGSIZE),
        },
    }
    json_path.write_text(json.dumps(ground_truth, indent=2))

    return PlotOutput(
        image_path=image_path,
        json_path=json_path,
        config=config,
        x=x.tolist(),
        y=y.tolist(),
    )


BASELINE_CONFIGS: list[PlotConfig] = [
    # Vary point count
    PlotConfig(n_points=5, marker="o", marker_size="medium", seed=1, label="01_sparse_circle"),
    PlotConfig(n_points=20, marker="o", marker_size="medium", seed=2, label="02_medium_circle"),
    PlotConfig(n_points=50, marker="o", marker_size="medium", seed=3, label="03_dense_circle"),
    PlotConfig(n_points=200, marker="o", marker_size="medium", seed=4, label="04_very_dense_circle"),
    # Vary marker shape
    PlotConfig(n_points=20, marker="s", marker_size="medium", seed=5, label="05_square"),
    PlotConfig(n_points=20, marker="^", marker_size="medium", seed=6, label="06_triangle"),
    PlotConfig(n_points=20, marker="x", marker_size="medium", seed=7, label="07_x_marker"),
    PlotConfig(n_points=20, marker="D", marker_size="medium", seed=8, label="08_diamond"),
    # Vary marker size
    PlotConfig(n_points=20, marker="o", marker_size="small", seed=9, label="09_small_circle"),
    PlotConfig(n_points=20, marker="o", marker_size="large", seed=10, label="10_large_circle"),
    # Vary opacity
    PlotConfig(n_points=20, marker="o", marker_size="medium", opacity=0.7, seed=11, label="11_opacity_70"),
    PlotConfig(n_points=20, marker="o", marker_size="medium", opacity=0.4, seed=12, label="12_opacity_40"),
    # Axis ranges: floats, negative
    PlotConfig(n_points=20, x_range=(-5.0, 5.0), y_range=(-5.0, 5.0), seed=13, label="13_negative_axes"),
    PlotConfig(n_points=20, x_range=(0.0, 1.0), y_range=(0.0, 1.0), seed=14, label="14_unit_range"),
    PlotConfig(n_points=20, x_range=(0.0, 100.0), y_range=(0.0, 100.0), seed=15, label="15_large_range"),
    # Grid lines
    PlotConfig(n_points=20, grid=True, seed=16, label="16_with_grid"),
    PlotConfig(n_points=50, grid=True, seed=17, label="17_dense_with_grid"),
    # Background color
    PlotConfig(n_points=20, bg_color="lightgray", seed=18, label="18_gray_bg"),
    PlotConfig(n_points=20, bg_color="lightgray", grid=True, seed=19, label="19_gray_bg_grid"),
    # Combined challenge
    PlotConfig(n_points=50, marker="^", marker_size="small", opacity=0.7, grid=True, bg_color="lightgray", seed=20, label="20_challenge"),
    # --- Extended suite (21-55) for Phase 6 hardening ---
    # Overlapping/close points
    PlotConfig(n_points=100, x_range=(4.0, 6.0), y_range=(4.0, 6.0), marker="o", marker_size="small", seed=21, label="21_clustered"),
    PlotConfig(n_points=30, x_range=(0.0, 2.0), y_range=(0.0, 2.0), marker="o", marker_size="large", seed=22, label="22_overlap_large"),
    # Points near axis lines
    PlotConfig(n_points=20, x_range=(0.0, 10.0), y_range=(0.0, 10.0), seed=23, label="23_near_axes"),
    # Grid + various markers
    PlotConfig(n_points=20, marker="s", grid=True, seed=24, label="24_square_grid"),
    PlotConfig(n_points=20, marker="D", grid=True, seed=25, label="25_diamond_grid"),
    PlotConfig(n_points=20, marker="x", grid=True, seed=26, label="26_x_grid"),
    PlotConfig(n_points=20, marker="^", grid=True, seed=27, label="27_triangle_grid"),
    # Gray bg + various markers
    PlotConfig(n_points=20, marker="s", bg_color="lightgray", seed=28, label="28_square_gray"),
    PlotConfig(n_points=20, marker="D", bg_color="lightgray", seed=29, label="29_diamond_gray"),
    PlotConfig(n_points=20, marker="^", bg_color="lightgray", seed=30, label="30_triangle_gray"),
    # Very small markers
    PlotConfig(n_points=30, marker="o", marker_size="small", seed=31, label="31_tiny_circles"),
    PlotConfig(n_points=30, marker="s", marker_size="small", seed=32, label="32_tiny_squares"),
    PlotConfig(n_points=30, marker="^", marker_size="small", seed=33, label="33_tiny_triangles"),
    # Low opacity variants
    PlotConfig(n_points=20, marker="s", opacity=0.4, seed=34, label="34_faint_squares"),
    PlotConfig(n_points=20, marker="D", opacity=0.4, seed=35, label="35_faint_diamonds"),
    PlotConfig(n_points=20, marker="^", opacity=0.7, seed=36, label="36_semi_triangles"),
    # Large point counts
    PlotConfig(n_points=100, marker="o", marker_size="small", seed=37, label="37_100_circles"),
    PlotConfig(n_points=100, marker="s", marker_size="small", seed=38, label="38_100_squares"),
    # Various axis ranges
    PlotConfig(n_points=20, x_range=(-100.0, 100.0), y_range=(-100.0, 100.0), seed=39, label="39_wide_range"),
    PlotConfig(n_points=20, x_range=(0.001, 0.01), y_range=(0.001, 0.01), seed=40, label="40_tiny_range"),
    PlotConfig(n_points=20, x_range=(1000.0, 2000.0), y_range=(1000.0, 2000.0), seed=41, label="41_offset_range"),
    # Asymmetric ranges
    PlotConfig(n_points=20, x_range=(0.0, 100.0), y_range=(0.0, 1.0), seed=42, label="42_asymmetric"),
    PlotConfig(n_points=20, x_range=(-1.0, 1.0), y_range=(0.0, 1000.0), seed=43, label="43_asymmetric_neg"),
    # Dense with all feature combinations
    PlotConfig(n_points=50, marker="o", marker_size="small", opacity=0.7, grid=True, seed=44, label="44_dense_faint_grid"),
    PlotConfig(n_points=50, marker="s", marker_size="small", opacity=0.7, bg_color="lightgray", seed=45, label="45_dense_faint_gray"),
    # Edge cases: very few points
    PlotConfig(n_points=1, marker="o", marker_size="large", seed=46, label="46_single_point"),
    PlotConfig(n_points=2, marker="o", marker_size="large", seed=47, label="47_two_points"),
    PlotConfig(n_points=3, marker="o", marker_size="large", seed=48, label="48_three_points"),
    # Maximum density
    PlotConfig(n_points=200, marker="o", marker_size="small", grid=True, seed=49, label="49_max_density_grid"),
    PlotConfig(n_points=200, marker="o", marker_size="small", bg_color="lightgray", grid=True, seed=50, label="50_max_challenge"),
    # Additional marker+size combos
    PlotConfig(n_points=20, marker="^", marker_size="large", seed=51, label="51_large_triangle"),
    PlotConfig(n_points=20, marker="x", marker_size="large", seed=52, label="52_large_x"),
    PlotConfig(n_points=20, marker="D", marker_size="large", seed=53, label="53_large_diamond"),
    PlotConfig(n_points=20, marker="s", marker_size="large", seed=54, label="54_large_square"),
    PlotConfig(n_points=20, marker="o", marker_size="medium", opacity=0.4, grid=True, bg_color="lightgray", seed=55, label="55_everything"),
]


def generate_baseline_suite(output_dir: Path) -> list[PlotOutput]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return [generate_plot(cfg, output_dir) for cfg in BASELINE_CONFIGS]


if __name__ == "__main__":
    out = Path(__file__).parent / "fixtures"
    results = generate_baseline_suite(out)
    print(f"Generated {len(results)} plots in {out}")
    for r in results:
        print(f"  {r.image_path.name}: {r.config.n_points} points")
