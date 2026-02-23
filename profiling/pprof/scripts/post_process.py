import sys
from pathlib import Path
import re

def parse_crate_and_version(filepath: str):
    name = Path(filepath).stem
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1][0].isdigit():
        crate, version = parts
    else:
        crate = name
        version = ""
    return crate, version

def frame_matches_tree_borrow(line: str) -> bool:
    parts = line.split(" -> ")

    for part in parts:
        part = part.strip()

        if part.startswith("FRAME: "):
            part = part[len("FRAME: "):].strip()

        if part.startswith("<miri::borrow_tracker") or " as miri::borrow_tracker" in part:
            return True

    return False

def extract_thread_count(line: str) -> int:
    match = re.search(r"THREAD:\s*rustc\s+(\d+)", line)
    if match:
        return int(match.group(1))
    return 0

def process_log(filepath: str):
    crate, version = parse_crate_and_version(filepath)
    start_marker = "==== Miri Profiling Results ===="

    total_samples = 0
    tree_borrow_count = 0
    started = False

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip()

            if not started:
                if start_marker in line:
                    started = True
                continue

            if not line.startswith("FRAME:"):
                continue

            count = extract_thread_count(line)
            total_samples += count

            if frame_matches_tree_borrow(line):
                tree_borrow_count += count

    if total_samples == 0:
        tree_pct = 0.0
    else:
        tree_pct = (tree_borrow_count / total_samples) * 100

    total_time = total_samples / 200
    print(f"{crate}, {tree_pct:.2f}%, {total_time} seconds")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <crate_log_file>")
        sys.exit(1)

    process_log(sys.argv[1])
