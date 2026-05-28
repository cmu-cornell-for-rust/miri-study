#!/usr/bin/env python3
import csv
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

INPUT_FILE   = "inputs/output.csv"
SPLIT_FILE   = "inputs/output_split.csv"
OUTPUT_NORM  = "outputs/event_durations_normalized.png"
OUTPUT_RAW   = "outputs/event_durations_raw.png"

SPLIT_EVENTS = ["alloc", "reborrow", "read", "write", "visits", "pruned"]
EVENT_LABELS = ["alloc", "reborrow", "read", "write", "visits", "GC", "pruned"]
COLORS       = ["#534AB7", "#1D9E75", "#D85A30", "#D4537E", "#378ADD", "#BA7517", "#639922"]
RED_COLOR    = "#E24B4A"
NONRED_COLOR = "#DED222"

def strip(s):
    try:
        return float(str(s).replace(",", ""))
    except (ValueError, AttributeError):
        return 0.0

def find_col(row, col):
    if col in row:
        return strip(row[col])
    for k in row:
        if k.rstrip(")],. ") == col.rstrip(")],. "):
            return strip(row[k])
    return 0.0

def load_main(path):
    with open(path, newline="") as f:
        return [r for r in csv.DictReader(f) if strip(r.get("trees", "0")) > 0]

def load_split(path):
    with open(path, newline="") as f:
        return {r["crate"]: r for r in csv.DictReader(f)}

def normalize_proportions(rows, cols):
    """Per-crate proportions averaged — each crate weighted equally."""
    prop_accum  = [0.0] * len(cols)
    total_accum = 0.0
    n = 0
    for row in rows:
        vals  = [find_col(row, c) for c in cols]
        total = sum(vals)
        if total == 0:
            continue
        for i, v in enumerate(vals):
            prop_accum[i] += v / total
        total_accum += total
        n += 1
    if n == 0:
        return [0.0] * len(cols), 0.0
    return [p / n for p in prop_accum], total_accum / n

def raw_proportions(rows, cols):
    """Sum all values across crates, then compute proportions from the grand total."""
    totals      = [0.0] * len(cols)
    grand_total = 0.0
    n = 0
    for row in rows:
        vals = [find_col(row, c) for c in cols]
        for i, v in enumerate(vals):
            totals[i] += v
        grand_total += sum(vals)
        n += 1
    avg_total = grand_total / n if n else 0.0
    if grand_total == 0:
        return [0.0] * len(cols), 0.0
    return [t / grand_total for t in totals], avg_total

main_rows  = load_main(INPUT_FILE)
split_dict = load_split(SPLIT_FILE)
split_rows = [split_dict[r["crate"]] for r in main_rows if r["crate"] in split_dict]

red_nonred_cols = ["red events (ns)", "nonred events (ns)"]
red_cols        = [f"red {e} total (ns)"    for e in SPLIT_EVENTS]
nr_cols         = [f"nonred {e} total (ns)" for e in SPLIT_EVENTS]

# normalized
rn_props_n,  rn_avg_n  = normalize_proportions(main_rows,  red_nonred_cols)
red_props_n,  red_avg_n  = normalize_proportions(split_rows, red_cols)
nr_props_n,   nr_avg_n   = normalize_proportions(split_rows, nr_cols)

# raw
rn_props_r,  rn_avg_r  = raw_proportions(main_rows,  red_nonred_cols)
red_props_r,  red_avg_r  = raw_proportions(split_rows, red_cols)
nr_props_r,   nr_avg_r   = raw_proportions(split_rows, nr_cols)

def fmt_duration(ns):
    ms = ns / 1_000_000
    if ms >= 1000:
        return f"avg total: {ms/1000:.2f} s"
    return f"avg total: {ms:.1f} ms"

def draw_pie(ax, labels, props, colors, title, avg_total_ns):
    pairs = [(l, p, c) for l, p, c in zip(labels, props, colors) if p > 0]
    if not pairs:
        ax.text(0.5, 0.5, "no data", ha="center", va="center")
        ax.axis("off")
        return
    ls, ps, cs = zip(*pairs)
    ax.pie(ps, colors=cs, startangle=90,
           wedgeprops=dict(linewidth=0.5, edgecolor="white"))
    legend_labels = [f"{l}  {p*100:.2f}%" for l, p in zip(ls, ps)]
    patches = [mpatches.Patch(color=c, label=lbl) for c, lbl in zip(cs, legend_labels)]
    ax.legend(handles=patches, loc="lower center",
              bbox_to_anchor=(0.5, -0.22),
              fontsize=12, frameon=False, ncol=2)
    ax.set_title(f"{title}\n{fmt_duration(avg_total_ns)}", fontsize=14,
                 fontweight="normal", pad=10)

def save_figure(props_rn, avg_rn, props_red, avg_red, props_nr, avg_nr, path, subtitle):
    fig, axes = plt.subplots(1, 3, figsize=(17, 6))
    fig.patch.set_facecolor("white")
    draw_pie(axes[0], ["red trees", "non-red trees"], props_rn,
             [RED_COLOR, NONRED_COLOR], "time in red vs non-red trees", avg_rn)
    draw_pie(axes[1], SPLIT_EVENTS, props_red,
             [COLORS[i] for i in range(len(SPLIT_EVENTS))], "red trees", avg_red)
    draw_pie(axes[2], SPLIT_EVENTS, props_nr,
             [COLORS[i] for i in range(len(SPLIT_EVENTS))], "non-red trees", avg_nr)
    fig.suptitle(f"Average event duration breakdown across crates ({subtitle})",
                 fontsize=16, fontweight="normal", y=1.02)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved {path}")

save_figure(rn_props_n, rn_avg_n, red_props_n, red_avg_n, nr_props_n, nr_avg_n,
            OUTPUT_NORM, "normalized per-crate")
save_figure(rn_props_r, rn_avg_r, red_props_r, red_avg_r, nr_props_r, nr_avg_r,
            OUTPUT_RAW,  "raw totals")