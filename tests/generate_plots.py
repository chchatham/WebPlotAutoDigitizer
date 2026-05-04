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
MarkerSizeName = Literal["small", "medium", "large", "xlarge"]
FillStyle = Literal["filled", "unfilled"]

MARKER_SIZES: dict[MarkerSizeName, int] = {"small": 20, "medium": 40, "large": 80, "xlarge": 120}


@dataclass
class OverlapConfig:
    """Controls deliberate point overlap for testing clump decomposition."""
    overlap_fraction: float = 0.3
    n_overlap_pairs: int = 5
    n_overlap_triples: int = 0
    n_isolated: int = 10


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
    fill_style: FillStyle = "filled"
    edge_width: float = 1.5
    marker_color: str = "black"
    overlap: OverlapConfig | None = None


@dataclass
class PlotOutput:
    image_path: Path
    json_path: Path
    config: PlotConfig
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)


@dataclass
class ClumpSpec:
    n_clumps: int = 3
    points_per_clump: int = 5
    clump_radius_pct: float = 2.0  # % of axis range


def _generate_clumped_points(
    config: PlotConfig, clump: ClumpSpec, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    x_span = config.x_range[1] - config.x_range[0]
    y_span = config.y_range[1] - config.y_range[0]
    radius_x = x_span * clump.clump_radius_pct / 100.0
    radius_y = y_span * clump.clump_radius_pct / 100.0

    margin = 0.1
    cx = rng.uniform(
        config.x_range[0] + x_span * margin,
        config.x_range[1] - x_span * margin,
        clump.n_clumps,
    )
    cy = rng.uniform(
        config.y_range[0] + y_span * margin,
        config.y_range[1] - y_span * margin,
        clump.n_clumps,
    )

    all_x, all_y = [], []
    for i in range(clump.n_clumps):
        px = rng.normal(cx[i], radius_x, clump.points_per_clump)
        py = rng.normal(cy[i], radius_y, clump.points_per_clump)
        px = np.clip(px, config.x_range[0], config.x_range[1])
        py = np.clip(py, config.y_range[0], config.y_range[1])
        all_x.append(px)
        all_y.append(py)

    return np.concatenate(all_x), np.concatenate(all_y)


def _generate_overlap_points(
    config: PlotConfig, overlap: OverlapConfig, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Generate points with deliberate overlaps at a specified fraction of marker diameter."""
    x_span = config.x_range[1] - config.x_range[0]
    y_span = config.y_range[1] - config.y_range[0]

    marker_size_pts = MARKER_SIZES[config.marker_size]
    # Approximate marker diameter in data units (based on figure geometry)
    # matplotlib marker size is in points^2, so diameter ~ 2*sqrt(size/pi) points
    # At 150 DPI, 8in wide figure, axis fills ~80% → pixels_per_data_unit ≈ (8*150*0.8) / x_span
    pixels_per_data_x = (FIXED_FIGSIZE[0] * FIXED_DPI * 0.8) / x_span
    pixels_per_data_y = (FIXED_FIGSIZE[1] * FIXED_DPI * 0.8) / y_span
    marker_diameter_pts = 2 * np.sqrt(marker_size_pts / np.pi)
    # Convert from points to data units (72 points per inch)
    marker_diam_data_x = marker_diameter_pts * (FIXED_DPI / 72.0) / pixels_per_data_x
    marker_diam_data_y = marker_diameter_pts * (FIXED_DPI / 72.0) / pixels_per_data_y

    overlap_dist_x = marker_diam_data_x * (1 - overlap.overlap_fraction)
    overlap_dist_y = marker_diam_data_y * (1 - overlap.overlap_fraction)

    all_x, all_y = [], []

    # Generate isolated singletons
    margin_x = x_span * 0.1
    margin_y = y_span * 0.1
    for _ in range(overlap.n_isolated):
        all_x.append(rng.uniform(config.x_range[0] + margin_x, config.x_range[1] - margin_x))
        all_y.append(rng.uniform(config.y_range[0] + margin_y, config.y_range[1] - margin_y))

    # Generate overlapping pairs
    for _ in range(overlap.n_overlap_pairs):
        cx = rng.uniform(config.x_range[0] + margin_x * 2, config.x_range[1] - margin_x * 2)
        cy = rng.uniform(config.y_range[0] + margin_y * 2, config.y_range[1] - margin_y * 2)
        angle = rng.uniform(0, 2 * np.pi)
        all_x.append(cx - overlap_dist_x * 0.5 * np.cos(angle))
        all_y.append(cy - overlap_dist_y * 0.5 * np.sin(angle))
        all_x.append(cx + overlap_dist_x * 0.5 * np.cos(angle))
        all_y.append(cy + overlap_dist_y * 0.5 * np.sin(angle))

    # Generate overlapping triples (tight triangle arrangement)
    for _ in range(overlap.n_overlap_triples):
        cx = rng.uniform(config.x_range[0] + margin_x * 2, config.x_range[1] - margin_x * 2)
        cy = rng.uniform(config.y_range[0] + margin_y * 2, config.y_range[1] - margin_y * 2)
        for k in range(3):
            angle = k * (2 * np.pi / 3) + rng.uniform(0, np.pi / 6)
            all_x.append(cx + overlap_dist_x * 0.6 * np.cos(angle))
            all_y.append(cy + overlap_dist_y * 0.6 * np.sin(angle))

    x = np.clip(np.array(all_x), config.x_range[0], config.x_range[1])
    y = np.clip(np.array(all_y), config.y_range[0], config.y_range[1])
    return x, y


def generate_plot(config: PlotConfig, output_dir: Path, clump: ClumpSpec | None = None) -> PlotOutput:
    rng = np.random.default_rng(config.seed)

    if config.overlap is not None:
        x, y = _generate_overlap_points(config, config.overlap, rng)
    elif clump is not None:
        x, y = _generate_clumped_points(config, clump, rng)
    else:
        x = rng.uniform(config.x_range[0], config.x_range[1], config.n_points)
        y = rng.uniform(config.y_range[0], config.y_range[1], config.n_points)

    fig, ax = plt.subplots(figsize=FIXED_FIGSIZE, dpi=FIXED_DPI)
    fig.set_facecolor(config.bg_color)
    ax.set_facecolor(config.bg_color)

    scatter_kwargs: dict = {
        "marker": config.marker,
        "s": MARKER_SIZES[config.marker_size],
        "alpha": config.opacity,
        "zorder": 5,
    }

    if config.fill_style == "unfilled":
        scatter_kwargs["facecolors"] = "none"
        scatter_kwargs["edgecolors"] = config.marker_color
        scatter_kwargs["linewidths"] = config.edge_width
    else:
        scatter_kwargs["color"] = config.marker_color

    ax.scatter(x, y, **scatter_kwargs)

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
            "n_points": len(x),
            "marker": config.marker,
            "marker_size": MARKER_SIZES[config.marker_size],
            "opacity": config.opacity,
            "grid": config.grid,
            "bg_color": config.bg_color,
            "dpi": FIXED_DPI,
            "figsize": list(FIXED_FIGSIZE),
            "fill_style": config.fill_style,
            "edge_width": config.edge_width,
            "marker_color": config.marker_color,
            "has_overlaps": config.overlap is not None,
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

CLUMP_CONFIGS: list[tuple[PlotConfig, ClumpSpec]] = [
    # Tight clumps of circles
    (PlotConfig(n_points=15, marker="o", marker_size="medium", seed=60, label="56_clump_circles"),
     ClumpSpec(n_clumps=3, points_per_clump=5, clump_radius_pct=1.5)),
    # Dense clumps with small markers
    (PlotConfig(n_points=25, marker="o", marker_size="small", seed=61, label="57_clump_small"),
     ClumpSpec(n_clumps=5, points_per_clump=5, clump_radius_pct=1.0)),
    # Very tight clumps (sub-marker-size spacing)
    (PlotConfig(n_points=12, marker="o", marker_size="large", seed=62, label="58_clump_tight"),
     ClumpSpec(n_clumps=3, points_per_clump=4, clump_radius_pct=0.5)),
    # Clumps with squares
    (PlotConfig(n_points=15, marker="s", marker_size="medium", seed=63, label="59_clump_squares"),
     ClumpSpec(n_clumps=3, points_per_clump=5, clump_radius_pct=1.5)),
    # Clumps on gray bg with grid
    (PlotConfig(n_points=20, marker="o", marker_size="medium", bg_color="lightgray", grid=True, seed=64, label="60_clump_grid"),
     ClumpSpec(n_clumps=4, points_per_clump=5, clump_radius_pct=2.0)),
]

RANDOM_CLUMP_CONFIGS: list[tuple[PlotConfig, ClumpSpec]] = [
    # No seed — randomized each run
    (PlotConfig(n_points=15, marker="o", marker_size="medium", seed=None, label="rand_clump_circle"),
     ClumpSpec(n_clumps=3, points_per_clump=5, clump_radius_pct=1.5)),
    (PlotConfig(n_points=20, marker="o", marker_size="small", seed=None, label="rand_clump_small"),
     ClumpSpec(n_clumps=4, points_per_clump=5, clump_radius_pct=1.0)),
    (PlotConfig(n_points=20, marker="s", marker_size="medium", seed=None, label="rand_clump_squares"),
     ClumpSpec(n_clumps=4, points_per_clump=5, clump_radius_pct=1.5)),
    (PlotConfig(n_points=30, marker="o", marker_size="medium", seed=None, label="rand_scatter_medium"),
     ClumpSpec(n_clumps=6, points_per_clump=5, clump_radius_pct=2.0)),
]

RANDOM_SCATTER_CONFIGS: list[PlotConfig] = [
    PlotConfig(n_points=20, marker="o", marker_size="medium", seed=None, label="rand_20_circle"),
    PlotConfig(n_points=30, marker="o", marker_size="small", seed=None, label="rand_30_small"),
    PlotConfig(n_points=15, marker="s", marker_size="medium", seed=None, label="rand_15_square"),
    PlotConfig(n_points=20, marker="D", marker_size="medium", seed=None, label="rand_20_diamond"),
]

# --- Phase 14: Overlap test suite ---

OVERLAP_CONFIGS: list[PlotConfig] = [
    # Category A: Filled circle overlaps (varying degree)
    PlotConfig(
        marker="o", marker_size="medium", seed=100, label="ovl_01_filled_20pct",
        overlap=OverlapConfig(overlap_fraction=0.2, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", seed=101, label="ovl_02_filled_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", seed=102, label="ovl_03_filled_50pct",
        overlap=OverlapConfig(overlap_fraction=0.5, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", seed=103, label="ovl_04_filled_70pct",
        overlap=OverlapConfig(overlap_fraction=0.7, n_overlap_pairs=3, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", seed=104, label="ovl_05_filled_triple_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=2, n_overlap_triples=3, n_isolated=8),
    ),
    PlotConfig(
        marker="o", marker_size="large", seed=105, label="ovl_06_filled_large_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="small", seed=106, label="ovl_07_filled_small_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=8, n_isolated=15),
    ),
    # Linear chain (5 points, each overlaps neighbor by 40%)
    PlotConfig(
        marker="o", marker_size="medium", seed=107, label="ovl_08_filled_chain",
        overlap=OverlapConfig(overlap_fraction=0.4, n_overlap_pairs=0, n_overlap_triples=0, n_isolated=5),
        # Note: chain generated via clump with tight radius; overlap here for metadata
    ),
    # Dense cluster (10 points with 20-50% overlaps)
    PlotConfig(
        marker="o", marker_size="medium", seed=108, label="ovl_09_filled_dense_cluster",
        overlap=OverlapConfig(overlap_fraction=0.35, n_overlap_pairs=3, n_overlap_triples=3, n_isolated=5),
    ),

    # Category B: Unfilled circle overlaps
    PlotConfig(
        marker="o", marker_size="medium", fill_style="unfilled", edge_width=1.5, seed=110,
        label="ovl_10_hollow_20pct",
        overlap=OverlapConfig(overlap_fraction=0.2, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", fill_style="unfilled", edge_width=1.5, seed=111,
        label="ovl_11_hollow_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", fill_style="unfilled", edge_width=1.5, seed=112,
        label="ovl_12_hollow_50pct",
        overlap=OverlapConfig(overlap_fraction=0.5, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="large", fill_style="unfilled", edge_width=2.0, seed=113,
        label="ovl_13_hollow_large_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", fill_style="unfilled", edge_width=1.5, seed=114,
        label="ovl_14_hollow_triple_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=2, n_overlap_triples=3, n_isolated=8),
    ),
    PlotConfig(
        marker="o", marker_size="xlarge", fill_style="unfilled", edge_width=2.5, seed=115,
        label="ovl_15_hollow_xlarge_20pct",
        overlap=OverlapConfig(overlap_fraction=0.2, n_overlap_pairs=4, n_isolated=8),
    ),

    # Category C: Various backgrounds
    PlotConfig(
        marker="o", marker_size="medium", bg_color="lightgray", seed=120,
        label="ovl_16_gray_bg_filled_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", bg_color="#e0e0e0", seed=121,
        label="ovl_17_medgray_bg_filled_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", bg_color="#ebebeb", grid=True, seed=122,
        label="ovl_18_ggplot_bg_grid_filled_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", marker_color="blue", seed=123,
        label="ovl_19_blue_markers_filled_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", marker_color="red", bg_color="lightgray", seed=124,
        label="ovl_20_red_markers_gray_bg",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", fill_style="unfilled", edge_width=1.5,
        bg_color="#ebebeb", grid=True, seed=125, label="ovl_21_hollow_ggplot_grid",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),

    # Category D: Various point sizes
    PlotConfig(
        marker="o", marker_size="small", seed=130, label="ovl_22_small_filled_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=8, n_isolated=15),
    ),
    PlotConfig(
        marker="o", marker_size="xlarge", seed=131, label="ovl_23_xlarge_filled_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=4, n_isolated=8),
    ),
    PlotConfig(
        marker="o", marker_size="xlarge", seed=132, label="ovl_24_xlarge_filled_50pct",
        overlap=OverlapConfig(overlap_fraction=0.5, n_overlap_pairs=4, n_isolated=8),
    ),

    # Category E: Mixed isolated + clumped (higher ratio of clumped)
    PlotConfig(
        marker="o", marker_size="medium", seed=140, label="ovl_25_mixed_40iso_10clump",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=40),
    ),
    PlotConfig(
        marker="o", marker_size="medium", seed=141, label="ovl_26_mixed_many_clumps",
        overlap=OverlapConfig(overlap_fraction=0.35, n_overlap_pairs=8, n_overlap_triples=4, n_isolated=20),
    ),
    PlotConfig(
        marker="o", marker_size="large", seed=142, label="ovl_27_mixed_large_heavy_overlap",
        overlap=OverlapConfig(overlap_fraction=0.5, n_overlap_pairs=6, n_overlap_triples=2, n_isolated=15),
    ),

    # Category F: Point count constraint tests (same plots, tested with/without hint)
    PlotConfig(
        marker="o", marker_size="medium", seed=150, label="ovl_28_hint_test_20pts",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=10),
    ),
    PlotConfig(
        marker="o", marker_size="medium", seed=151, label="ovl_29_hint_test_30pts",
        overlap=OverlapConfig(overlap_fraction=0.4, n_overlap_pairs=5, n_overlap_triples=2, n_isolated=14),
    ),
    PlotConfig(
        marker="o", marker_size="large", seed=152, label="ovl_30_hint_test_heavy",
        overlap=OverlapConfig(overlap_fraction=0.5, n_overlap_pairs=6, n_overlap_triples=3, n_isolated=10),
    ),

    # Category G: Dense plots with sparse 2-point clumps (user's real-world scenario)
    PlotConfig(
        marker="o", marker_size="medium", marker_color="red", seed=160,
        label="ovl_31_dense_red_100pts",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=90),
    ),
    PlotConfig(
        marker="o", marker_size="medium", marker_color="red", seed=161,
        label="ovl_32_dense_red_50pts",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=40),
    ),
    PlotConfig(
        marker="o", marker_size="medium", seed=162, label="ovl_33_dense_black_100pts",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=90),
    ),
    PlotConfig(
        marker="o", marker_size="medium", marker_color="red", seed=163,
        label="ovl_34_dense_red_20pct_overlap",
        overlap=OverlapConfig(overlap_fraction=0.2, n_overlap_pairs=5, n_isolated=90),
    ),
    PlotConfig(
        marker="o", marker_size="medium", marker_color="blue", seed=164,
        label="ovl_35_dense_blue_30pct",
        overlap=OverlapConfig(overlap_fraction=0.3, n_overlap_pairs=5, n_isolated=90),
    ),
    # 2-point-only overlaps at small fractions (15-20%)
    PlotConfig(
        marker="o", marker_size="medium", seed=165, label="ovl_36_pairs_only_15pct",
        overlap=OverlapConfig(overlap_fraction=0.15, n_overlap_pairs=8, n_isolated=20),
    ),
    PlotConfig(
        marker="o", marker_size="large", seed=166, label="ovl_37_pairs_only_large_25pct",
        overlap=OverlapConfig(overlap_fraction=0.25, n_overlap_pairs=6, n_isolated=15),
    ),
    # Large marker with few subtle overlaps
    PlotConfig(
        marker="o", marker_size="large", marker_color="red", seed=167,
        label="ovl_38_large_red_subtle",
        overlap=OverlapConfig(overlap_fraction=0.25, n_overlap_pairs=4, n_isolated=30),
    ),
]


def generate_baseline_suite(output_dir: Path) -> list[PlotOutput]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [generate_plot(cfg, output_dir) for cfg in BASELINE_CONFIGS]
    for cfg, clump in CLUMP_CONFIGS:
        results.append(generate_plot(cfg, output_dir, clump=clump))
    return results


def generate_overlap_suite(output_dir: Path) -> list[PlotOutput]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return [generate_plot(cfg, output_dir) for cfg in OVERLAP_CONFIGS]


def generate_randomized_suite(output_dir: Path) -> list[PlotOutput]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for cfg in RANDOM_SCATTER_CONFIGS:
        results.append(generate_plot(cfg, output_dir))
    for cfg, clump in RANDOM_CLUMP_CONFIGS:
        results.append(generate_plot(cfg, output_dir, clump=clump))
    return results


if __name__ == "__main__":
    out = Path(__file__).parent / "fixtures"
    results = generate_baseline_suite(out)
    print(f"Generated {len(results)} baseline plots in {out}")

    ovl_out = Path(__file__).parent / "fixtures_overlap"
    ovl_results = generate_overlap_suite(ovl_out)
    print(f"Generated {len(ovl_results)} overlap plots in {ovl_out}")

    rand_out = Path(__file__).parent / "fixtures_random"
    rand_results = generate_randomized_suite(rand_out)
    print(f"Generated {len(rand_results)} randomized plots in {rand_out}")

    for r in results + ovl_results + rand_results:
        print(f"  {r.image_path.name}: {len(r.x)} points")
