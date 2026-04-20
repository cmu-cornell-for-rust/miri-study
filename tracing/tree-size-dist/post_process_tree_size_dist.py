#!/usr/bin/env python3
import csv
import os
import re
from collections import Counter, defaultdict

DEFAULT_CRATES = [
    "getrandom-0.4.0",
    "either-1.11.0",
    "hashbrown-0.16.1",
    "chacha20-0.10.0",
    "foldhash-0.2.0",
    "indexmap-2.13.0",
    "rand-0.10.0",
    "unicode-ident-1.0.19",
    "zerocopy-0.8.31",
    "smallvec-2.0.0-alpha.12",
    "typenum-1.19.0",
    "unicode-normalization-0.1.25",
    "zerocopy-0.9.0-alpha.0",
    "bytes-1.11.1",
    "clap_builder-4.5.59",
    "encoding_rs-0.8.35",
    "gimli-0.33.0",
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "traces"))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "outputs")

TIMESTAMP_PATTERN = re.compile(r"-(\d+)$")
EVENT_PATTERN = re.compile(r"E\d\([^\)]*\)|E6")

E1_PATTERN = re.compile(r"E1\(a\d+,\s*t(\d+)\)")
E2_PATTERN = re.compile(r"E2\(t(\d+),\s*t(\d+)\)")


def iter_event_tokens(path: str, chunk_size: int = 1 << 20):
    with open(path, encoding="utf-8") as f:
        tail = ""
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break

            tail += chunk
            last_end = 0
            for match in EVENT_PATTERN.finditer(tail):
                yield match.group(0)
                last_end = match.end()

            if last_end:
                tail = tail[last_end:]

        for match in EVENT_PATTERN.finditer(tail):
            yield match.group(0)


def build_timestamp_map(crate_dir: str) -> dict[str, dict[str, str | None]]:
    files = os.listdir(crate_dir)
    timestamp_map: dict[str, dict[str, str | None]] = {}

    for name in files:
        if not name.startswith("events-"):
            continue
        match = TIMESTAMP_PATTERN.search(name)
        if not match:
            continue
        ts = match.group(1)
        timestamp_map.setdefault(ts, {"events": None, "trace": None})["events"] = name

    for name in files:
        if not (name.startswith("traces-") or name.startswith("tracing-")):
            continue
        match = TIMESTAMP_PATTERN.search(name)
        if not match:
            continue
        ts = match.group(1)
        timestamp_map.setdefault(ts, {"events": None, "trace": None})["trace"] = name

    return timestamp_map


def parse_events_tree_sizes(events_path: str) -> tuple[set[int], dict[int, int]]:
    tag_root: dict[int, int] = {}
    tree_nodes: defaultdict[int, int] = defaultdict(int)
    root_tags: set[int] = set()

    for event in iter_event_tokens(events_path):
        if event.startswith("E1"):
            m = E1_PATTERN.match(event)
            if not m:
                continue
            root = int(m.group(1))
            root_tags.add(root)
            tag_root[root] = root
            tree_nodes[root] += 1
            continue

        if event.startswith("E2"):
            m = E2_PATTERN.match(event)
            if not m:
                continue
            child = int(m.group(1))
            parent = int(m.group(2))
            root = tag_root.get(parent)
            if root is None:
                continue
            tag_root[child] = root
            tree_nodes[root] += 1

    return root_tags, dict(tree_nodes)


def main() -> None:
    for crate in DEFAULT_CRATES:
        crate_dir = os.path.join(TRACE_ROOT, crate)
        if not os.path.isdir(crate_dir):
            print(f"[skip] missing crate directory: {crate_dir}")
            continue

        ts_map = build_timestamp_map(crate_dir)
        crate_dist: Counter[int] = Counter()

        for _, pair in sorted(ts_map.items()):
            events_name = pair.get("events")
            if not events_name:
                continue

            events_path = os.path.join(crate_dir, events_name)
            root_tags, tree_nodes = parse_events_tree_sizes(events_path)

            for root in root_tags:
                crate_dist[tree_nodes.get(root, 0)] += 1

        if not crate_dist:
            print(f"[skip] no tree data found: {crate}")
            continue

        output_path = os.path.join(OUTPUT_DIR, f"output_tree_size_dist_{crate}.csv")
        with open(output_path, "w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out)
            writer.writerow(["tree_size", "count"])
            for tree_size in sorted(crate_dist):
                writer.writerow([tree_size, crate_dist[tree_size]])
            out.flush()
            os.fsync(out.fileno())


if __name__ == "__main__":
    main()