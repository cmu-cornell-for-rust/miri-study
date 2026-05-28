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

INPUT_CSV  = sys.argv[1] if len(sys.argv) > 1 else "inputs/results6.csv"
OUTPUT_PNG = sys.argv[2] if len(sys.argv) > 2 else "outputs/runtimes6.png"
CUTOFF = 500

# -------------------------------------------------------------------
# 1. Load data
# -------------------------------------------------------------------
data = defaultdict(lambda: defaultdict(list))
build_order = []
builds_seen = set()

with open(INPUT_CSV, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        build = row["build"]
        if build not in builds_seen:
            builds_seen.add(build)
            build_order.append(build)
        data[row["crate"]][row["build"]].append(
            (row["status"], float(row["elapsed_seconds"]))
        )

# Derive build labels from the CSV in observed order
build_labels = list(build_order)
if not build_labels:
    print("No builds found in CSV.")
    sys.exit(1)

# Choose the reference/base build: prefer 'base' if present, otherwise fallback to first observed build
base_label = "base" if "base" in build_labels else build_labels[0]

# -------------------------------------------------------------------
# 2. Keep only crates that succeeded in every run for all three builds
# -------------------------------------------------------------------
eligible = {}
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
crates_sorted = sorted(eligible, key=lambda c: np.mean(trimmed[c][base_label]))

low_crates  = [c for c in crates_sorted if np.mean(trimmed[c][base_label]) <  CUTOFF]
high_crates = [c for c in crates_sorted if np.mean(trimmed[c][base_label]) >= CUTOFF]

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
# Dynamic labels and colors based on observed builds
palette = plt.get_cmap('tab10').colors
if len(build_labels) > len(palette):
    palette = plt.get_cmap('tab20').colors
colors = {build: palette[(i + (1 if i >= 3 else 0)) % len(palette)] for i, build in enumerate(build_labels)}
labels = {build: build.replace('_', ' ').title() for build in build_labels}

# Bar width per-build within a group (group occupies ~80% of tick)
group_width = 0.8
bar_width = group_width / max(1, len(build_labels))


def summarize(values):
    arr = np.asarray(values, dtype=float)
    return {
        "count": int(arr.size),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def print_runtime_stats(group_crates, group_label):
    print(f"\n── {group_label} runtime stats ──")
    if len(group_crates) == 0:
        print("None")
        return

    for build in build_labels:
        crate_means = [float(np.mean(trimmed[c][build])) for c in group_crates]
        stats = summarize(crate_means)
        print(
            f"  {labels[build]:<5}: "
            f"mean={stats['mean']:.3f}s, median={stats['median']:.3f}s, "
            f"std={stats['std']:.3f}s, min={stats['min']:.3f}s, max={stats['max']:.3f}s"
        )

def print_paired_stats(group_crates, group_label):
    print(f"\n── {group_label} paired comparisons ──")
    if len(group_crates) == 0:
        print("None")
        return
    # Compare each other build against the base/reference build
    other_builds = [b for b in build_labels if b != base_label]
    for build in other_builds:
        pretty_name = labels[build]
        base_means = np.array([float(np.mean(trimmed[c][base_label])) for c in group_crates])
        other_means = np.array([float(np.mean(trimmed[c][build])) for c in group_crates])
        delta = base_means - other_means
        pct = np.where(base_means != 0, delta / base_means * 100.0, 0.0)
        speedups = np.where(other_means != 0, base_means / other_means, np.nan)
        wins = int(np.sum(delta > 0))
        stats = summarize(delta)
        pct_stats = summarize(pct)
        speedup_stats = summarize(speedups[~np.isnan(speedups)])
        print(
            f"  {labels[base_label]} vs {pretty_name}: "
            f"delta mean={stats['mean']:.3f}s, median={stats['median']:.3f}s, "
            f"std={stats['std']:.3f}s; "
            f"pct mean={pct_stats['mean']:.2f}%, median={pct_stats['median']:.2f}%; "
            f"speedup mean={speedup_stats['mean']:.3f}x; "
            f"base faster on {wins}/{len(group_crates)} crates"
        )


def print_speedup_stats(group_crates, group_label):
    speedup_sets = {
        labels[build]: {c: np.mean(trimmed[c][base_label]) / np.mean(trimmed[c][build]) for c in group_crates}
        for build in build_labels if build != base_label
    }
    print(f"\n── {group_label} ──")
    if len(group_crates) == 0:
        print("None")
        return
    for lbl, speedups in speedup_sets.items():
        avg = float(np.mean(list(speedups.values())))
        best_crate, best_val = max(speedups.items(), key=lambda kv: kv[1])
        print(f"  Average speedup (base/{lbl}): {avg:.3f}x ({(avg-1)*100:.1f}%)")
        print(f"  Max     speedup (base/{lbl}): {best_val:.3f}x ({(best_val-1)*100:.1f}%) on {best_crate}")


def make_plot(group_crates, title, out_path):
    if len(group_crates) == 0:
        return

    n = len(group_crates)
    x = np.arange(n)

    fig, ax = plt.subplots(figsize=(max(10, n * 1.1), 6))

    n_builds = len(build_labels)
    offsets = [ (i - (n_builds - 1) / 2.0) * bar_width for i in range(n_builds) ]

    for i, build in enumerate(build_labels):
        offset = offsets[i]
        means = [np.mean(trimmed[c][build]) for c in group_crates]
        ax.bar(x + offset, means, bar_width,
               label=labels[build], color=colors[build], alpha=0.85, zorder=2)

    ax.set_xticks(x)
    ax.set_xticklabels(group_crates, rotation=40, ha="right", fontsize=10)
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
print_runtime_stats(low_crates,  f"Low overhead  (<{CUTOFF}s)")
print_paired_stats(low_crates,   f"Low overhead  (<{CUTOFF}s)")
print_speedup_stats(low_crates,  f"Low overhead  (<{CUTOFF}s)")

print_runtime_stats(high_crates, f"High overhead (≥{CUTOFF}s)")
print_paired_stats(high_crates,   f"High overhead (≥{CUTOFF}s)")
print_speedup_stats(high_crates, f"High overhead (≥{CUTOFF}s)")

make_plot(
    low_crates,
    f"End-to-End Runtime: Base Miri vs Lazy Allocator",
    out_low,
)
make_plot(
    high_crates,
    f"End-to-End Runtime: Base Miri vs Lazy Allocator",
    out_high,
)