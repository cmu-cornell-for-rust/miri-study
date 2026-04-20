#!/usr/bin/env python3

import csv
import sys
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from pathlib import Path

INPUT_CSV  = sys.argv[1] if len(sys.argv) > 1 else "inputs/results.csv"
OUTPUT_PNG = sys.argv[2] if len(sys.argv) > 2 else "outputs/lazy_alloc/runtimes.png"
CUTOFF = 60

# -------------------------------------------------------------------
# 1. Load data
# -------------------------------------------------------------------
data = defaultdict(lambda: defaultdict(list))

with open(INPUT_CSV, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        data[row["crate"]][row["build"]].append(
            (row["status"], int(row["elapsed_seconds"]))
        )

# -------------------------------------------------------------------
# 2. Keep only crates that succeeded in every run for all three builds
# -------------------------------------------------------------------
eligible = {}
build_labels = ["base", "lazy", "lazy2"]
for crate, builds in data.items():
    if any(build not in builds for build in build_labels):
        continue
    build_times = {}
    all_success = True
    for build in build_labels:
        times = [t for s, t in builds[build] if s == "success"]
        total  = len(builds[build])
        if len(times) != total or total == 0:
            all_success = False
            break
        build_times[build] = times
    if all_success:
        eligible[crate] = build_times

if not eligible:
    print("No crates passed the all-successful filter.")
    sys.exit(1)

print(f"Eligible crates ({len(eligible)}): {sorted(eligible)}")


def remove_furthest_from_mean(values):
    """Return values with the single furthest-from-mean point removed."""
    if len(values) <= 1:
        return list(values)
    mean = float(np.mean(values))
    idx  = max(range(len(values)), key=lambda i: abs(values[i] - mean))
    return [v for i, v in enumerate(values) if i != idx]


trimmed = {
    crate: {
        build: remove_furthest_from_mean(times)
        for build, times in builds.items()
    }
    for crate, builds in eligible.items()
}

# -------------------------------------------------------------------
# 3. Sort by base average then split into low / high overhead groups
# -------------------------------------------------------------------
crates_sorted = sorted(eligible, key=lambda c: np.mean(trimmed[c]["base"]))

low_crates  = [c for c in crates_sorted if np.mean(trimmed[c]["base"]) <  CUTOFF]
high_crates = [c for c in crates_sorted if np.mean(trimmed[c]["base"]) >= CUTOFF]

print(f"Low-overhead  crates (<{CUTOFF}s base avg)  ({len(low_crates)}):  {low_crates}")
print(f"High-overhead crates (≥{CUTOFF}s base avg) ({len(high_crates)}): {high_crates}")

# -------------------------------------------------------------------
# 4. Derive output filenames from the provided output path
# -------------------------------------------------------------------
stem   = Path(OUTPUT_PNG).stem
suffix = Path(OUTPUT_PNG).suffix or ".png"
parent = Path(OUTPUT_PNG).parent

out_low  = parent / f"{stem}_low{suffix}"
out_high = parent / f"{stem}_high{suffix}"

# -------------------------------------------------------------------
# 5. Shared plot helper
# -------------------------------------------------------------------
colors = {"base": "#4C72B0", "lazy": "#DD8452", "lazy2": "#55A868"}
labels = {"base": "Base",    "lazy": "Lazy v1", "lazy2": "Lazy v2"}
width  = 0.28


def print_speedup_stats(group_crates, group_label):
    speedup_sets = {
        "lazy v1": {c: np.mean(trimmed[c]["base"]) / np.mean(trimmed[c]["lazy"])  for c in group_crates},
        "lazy v2": {c: np.mean(trimmed[c]["base"]) / np.mean(trimmed[c]["lazy2"]) for c in group_crates},
    }
    print(f"\n── {group_label} ──")
    for lbl, speedups in speedup_sets.items():
        avg = float(np.mean(list(speedups.values())))
        best_crate, best_val = max(speedups.items(), key=lambda kv: kv[1])
        print(f"  Average speedup (base/{lbl}): {avg:.3f}x ({(avg-1)*100:.1f}%)")
        print(f"  Max     speedup (base/{lbl}): {best_val:.3f}x ({(best_val-1)*100:.1f}%) on {best_crate}")


def make_plot(group_crates, title, out_path):

    n = len(group_crates)
    x = np.arange(n)

    fig, ax = plt.subplots(figsize=(max(10, n * 1.1), 6))

    for build, offset in [("base", -width), ("lazy", 0.0), ("lazy2", width)]:
        means = [np.mean(trimmed[c][build]) for c in group_crates]
        ax.bar(x + offset, means, width,
               label=labels[build], color=colors[build], alpha=0.85, zorder=2)

        for j, crate in enumerate(group_crates):
            pts = trimmed[crate][build]
            ax.scatter(
                np.full(len(pts), x[j] + offset),
                pts,
                color="white",
                edgecolors=colors[build],
                linewidths=1.2,
                s=40,
                zorder=4,
                clip_on=False,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(group_crates, rotation=40, ha="right", fontsize=9)
    ax.set_ylabel("Time (s)", fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.legend(fontsize=10)
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(axis="y", which="major", linestyle="--", alpha=0.4, zorder=0)
    ax.grid(axis="y", which="minor", linestyle=":",  alpha=0.2, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved → {out_path}")


# -------------------------------------------------------------------
# 6. Emit both plots
# -------------------------------------------------------------------
print_speedup_stats(low_crates,  f"Low overhead  (<{CUTOFF}s)")
print_speedup_stats(high_crates, f"High overhead (≥{CUTOFF}s)")

make_plot(
    low_crates,
    f"End-to-End Runtime: Base Miri vs Lazy Allocator  [low overhead, base avg < {CUTOFF}s]",
    out_low,
)
make_plot(
    high_crates,
    f"End-to-End Runtime: Base Miri vs Lazy Allocator  [high overhead, base avg ≥ {CUTOFF}s]",
    out_high,
)