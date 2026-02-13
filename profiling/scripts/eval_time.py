#!/usr/bin/env python3
import glob
import json
import tarfile
import csv
import os

MICROSECONDS_TO_SECONDS = 1000 * 1000

def process_file(f):
    stack = []
    outermost_events = {}

    for line in f:
        line = line.decode("utf-8").strip()
        if not line or line in ("[", "]"):
            continue
        try:
            entry = json.loads(line.rstrip(","))
        except json.JSONDecodeError:
            continue

        ph = entry.get("ph")
        args = entry.get("args", {})
        event_type = args.get("borrow_tracker")

        if ph not in ("B", "E") or event_type is None:
            continue
        if ph == "B":
            stack.append((event_type, entry["ts"]))
        elif ph == "E":
            if not stack:
                continue
            last_event, start_ts = stack.pop()
            if last_event != event_type:
                print(f"Warning: B/E mismatch: B={last_event}, E={event_type}", flush=True)
                continue
            if not stack:
                if event_type not in outermost_events:
                    outermost_events[event_type] = {"total_us": 0.0, "count": 0}
                outermost_events[event_type]["total_us"] += entry["ts"] - start_ts
                outermost_events[event_type]["count"] += 1

    return outermost_events

def main():
    tar_files = sorted(f for f in os.listdir(".") if f.endswith("-traces.tar.gz"))
    if not tar_files:
        print("No *-traces.tar.gz found in current directory.", flush=True)
        return

    crate_times = {}
    with open("results.csv") as f:
        reader = csv.reader(f)
        for row in reader:
            crate_times[row[0].strip()] = float(row[1])

    for tar_path in tar_files:
        crate_name = tar_path.replace("-traces.tar.gz","")
        aggregate_stats = {}
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in sorted(tar.getmembers(), key=lambda x: x.name):
                if member.isfile() and member.name.startswith("traces/trace") and member.name.endswith(".json"):
                    f = tar.extractfile(member)
                    if f:
                        file_stats = process_file(f)
                        for event, stats in file_stats.items():
                            if event not in aggregate_stats:
                                aggregate_stats[event] = {"total_us": 0.0, "count": 0}
                            aggregate_stats[event]["total_us"] += stats["total_us"]
                            aggregate_stats[event]["count"] += stats["count"]

        crate_total_time = crate_times.get(crate_name, 0.0)
        print(f"Crate: {crate_name}, total time: {crate_total_time:.2f} seconds", flush=True)
        for event, stats in sorted(aggregate_stats.items()):
            seconds = stats["total_us"] / MICROSECONDS_TO_SECONDS
            pct = (seconds / crate_total_time * 100) if crate_total_time else 0.0
            print(f"{event}: {seconds:.2f} seconds, {stats['count']:,} events, {pct:.2f}%", flush=True)

        total_seconds = sum(stats["total_us"] for stats in aggregate_stats.values()) / MICROSECONDS_TO_SECONDS
        total_pct = (total_seconds / crate_total_time * 100) if crate_total_time else 0.0
        print(f"[Total] {total_seconds:.2f} seconds, {total_pct:.2f}% of crate total\n", flush=True)

if __name__ == "__main__":
    main()
