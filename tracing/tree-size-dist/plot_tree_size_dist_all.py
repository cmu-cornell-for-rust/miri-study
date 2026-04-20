#!/usr/bin/env python3

import csv
import glob
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from typing import List, Tuple


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "traces"))
INPUT_GLOB = os.path.join(SCRIPT_DIR, "outputs", "output_tree_size_dist_*.csv")


def load_distribution(csv_path: str) -> List[Tuple[int, int]]:
    rows: List[Tuple[int, int]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tree_size = int(row["tree_size"])
            count = int(row["count"])
            rows.append((tree_size, count))
    rows.sort(key=lambda x: x[0])
    return rows


def output_png_path(csv_path: str) -> str:
    base = os.path.basename(csv_path)
    stem, _ = os.path.splitext(base)
    return os.path.join(TRACE_ROOT, f"{stem}.png")


def title_from_csv(csv_path: str) -> str:
    base = os.path.basename(csv_path)
    stem, _ = os.path.splitext(base)
    prefix = "output_tree_size_dist_"
    crate = stem[len(prefix):] if stem.startswith(prefix) else stem
    return f"Tree-size distribution: {crate}"


def main() -> None:

    csv_paths = sorted(glob.glob(INPUT_GLOB))
    if not csv_paths:
        print(f"No files matched: {INPUT_GLOB}", file=sys.stderr)
        sys.exit(2)

    for csv_path in csv_paths:
        dist = load_distribution(csv_path)
        if not dist:
            print(f"[skip] no rows: {csv_path}")
            continue

        tree_sizes = [tree_size for tree_size, _ in dist]
        y = [count for _, count in dist]
        positions = list(range(len(dist)))

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(positions, y, width=0.9, color="#1f77b4")
        ax.set_xlabel("Tree size (nodes)")
        ax.set_ylabel("Number of trees")
        ax.set_title(title_from_csv(csv_path))

        if len(tree_sizes) <= 30:
            tick_positions = positions
        else:
            step = max(1, len(tree_sizes) // 15)
            tick_positions = positions[::step]

        tick_labels = [str(tree_sizes[idx]) for idx in tick_positions]
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=45, ha="right")

        ax.grid(axis="y", linestyle="--", alpha=0.35)
        fig.tight_layout()

        png_path = output_png_path(csv_path)
        fig.savefig(png_path, dpi=150)
        plt.close(fig)

        total_trees = sum(count for _, count in dist)
        print(f"Wrote plot: {png_path} (points={len(dist)} total_trees={total_trees})")


if __name__ == "__main__":
    main()