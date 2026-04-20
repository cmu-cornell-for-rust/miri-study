#!/usr/bin/env python3
import os
import re
import csv
import json
from collections import defaultdict

crates = [
"allocator-api2-0.2.21",
"either-1.11.0",
"hashbrown-0.16.1",
"foldhash-0.2.0",
"getrandom-0.4.0",
"linux-raw-sys-0.11.0",
"ppv-lite86-0.2.21",
"socket2-0.6.1",
"libc-0.2.178",
"syn-2.0.106",
"serde_core-1.0.228",
"log-0.4.29",
"rustix-1.1.3",
"proc-macro2-1.0.101",
"itertools-0.14.0",
"regex-automata-0.4.13",
"rand-0.10.0",
"indexmap-2.13.0",
"memchr-2.7.6",
"zerocopy-0.8.31",
"chacha20-0.10.0",
"unicode-ident-1.0.19",
"aho-corasick-1.1.3"
]

EVENT_NAMES = {
    "E1a": "alloc",
    "E2":  "reborrow",
    "E3":  "read",
    "E4":  "write",
    "E5":  "visits",
    "E6":  "GC",
    "E7":  "pruned",
}

DURATION_EVENTS = ["E1a", "E2", "E3", "E4", "E5", "E6", "E7"]
SPLIT_EVENTS    = ["E1a", "E2", "E3", "E4", "E5", "E7"]

header_main = [
    "crate","trees","nodes","avg_nodes","read","avg_read (max)","write","avg_write (max)",
    "visited","avg_visited (max)","skipped","avg_skipped (max)",
    "gc_invoked","gc_pruned","avg_gc_pruned",
    "loc_state","red_loc_state","transitions","red_transitions","red_trees",
    "memory_kinds",
] + [col for e in DURATION_EVENTS
       for col in (f"{EVENT_NAMES[e]} count", f"{EVENT_NAMES[e]} total (ns)", f"{EVENT_NAMES[e]} avg (ns)")] + [
    "events count", "events (ns)", "events avg (ns)",
    "red events count", "red events (ns)", "red events avg (ns)",
    "nonred events count", "nonred events (ns)", "nonred events avg (ns)",
]

header_split = ["crate"] \
    + [col for e in SPLIT_EVENTS for col in (f"red {EVENT_NAMES[e]} count",    f"red {EVENT_NAMES[e]} total (ns)",    f"red {EVENT_NAMES[e]} avg (ns)")] \
    + [col for e in SPLIT_EVENTS for col in (f"nonred {EVENT_NAMES[e]} count", f"nonred {EVENT_NAMES[e]} total (ns)", f"nonred {EVENT_NAMES[e]} avg (ns))]")]

trace_pattern = re.compile(r'\[([A-Z, ]+)\]\s+(\d+)')
empty_pattern = re.compile(r'empty_fsm=(\d+)')
noop_pattern  = re.compile(r'noop_transitions=(\d+)')
root_pattern  = re.compile(r'^t(\d+)@')

re_e1 = re.compile(r"E1\(alloc(\d+), t(\d+)\)")
re_e2 = re.compile(r"E2\(t(\d+), t(\d+), s(\d+), n(\d+)\)")
re_e3 = re.compile(r"E3\(t(\d+), n(\d+)\)")
re_e4 = re.compile(r"E4\(t(\d+), n(\d+)\)")
re_e5 = re.compile(r"E5\(t(\d+), (\d+), (\d+), n(\d+)\)")
re_e6 = re.compile(r"E6 \(n(\d+)\)")
re_e7 = re.compile(r"E7\(t(\d+), (\d+), n(\d+)\)")

def parse_e1a(e):
    inner = e[len("E1a("):-1]
    alloc_part, rest = inner.split(", ", 1)
    alloc_id = alloc_part[len("alloc"):]
    last_n = rest.rfind(", n")
    if last_n == -1:
        return None
    kind = rest[:last_n].strip()
    dur  = int(rest[last_n + len(", n"):])
    return alloc_id, kind, dur

def make_dur():
    return defaultdict(int)

def fmt(total, count):
    return f"{total:,}", f"{total/count:.1f}" if count else "0"

def fmt3(count, total, dur_count):
    """count of events, total duration, avg duration"""
    return f"{count:,}", f"{total:,}", f"{total/dur_count:.1f}" if dur_count else "0"

with open("outputs/output.csv", "w", newline="") as fmain, \
     open("outputs/output_split.csv", "w", newline="") as fsplit:

    writer_main  = csv.writer(fmain)
    writer_split = csv.writer(fsplit)
    writer_main.writerow(header_main)
    writer_split.writerow(header_split)
    fmain.flush(); fsplit.flush()

    for crate in crates:
        trees=0; nodes=0; reads=0; writes=0; visited=0; skipped=0
        gc_invoked=0; gc_pruned=0
        loc_states=0; red_loc_states=0; transitions=0; red_transitions=0
        max_nodes=max_reads=max_writes=max_visited=max_skipped=max_gc_pruned=0

        all_memory_kinds = defaultdict(int)
        root_dur      = defaultdict(make_dur)  # root -> etype -> total duration
        root_count    = defaultdict(make_dur)  # root -> etype -> num events
        e6_dur_total  = 0
        e6_dur_count  = 0  # num GC invocations with timing
        nonred_roots  = set()

        for file in sorted(os.listdir(crate)):
            if file.startswith("events-"):
                tag_root     = {}
                alloc_to_tag = {}
                tree_nodes     = defaultdict(int)
                tree_reads     = defaultdict(int)
                tree_writes    = defaultdict(int)
                tree_visited   = defaultdict(int)
                tree_skipped   = defaultdict(int)
                tree_gc_pruned = defaultdict(int)

                with open(os.path.join(crate, file)) as ef:
                    events = [line.strip() for line in ef if line.strip()]

                for e in events:
                    if e.startswith("E1a"):
                        parsed = parse_e1a(e)
                        if parsed:
                            alloc_id, kind, dur = parsed
                            tag = alloc_to_tag.get(alloc_id)
                            if tag is not None:
                                all_memory_kinds[kind] += 1
                                root = tag_root.get(tag, tag)
                                root_dur[root]["E1a"]   += dur
                                root_count[root]["E1a"] += 1

                    elif e.startswith("E1"):
                        m = re_e1.match(e)
                        if m:
                            alloc_id = m.group(1)
                            tag      = int(m.group(2))
                            alloc_to_tag[alloc_id] = tag
                            tag_root[tag] = tag
                            trees += 1
                            nodes += 1
                            tree_nodes[tag] += 1

                    elif e.startswith("E2"):
                        m = re_e2.match(e)
                        if m:
                            child  = int(m.group(1))
                            parent = int(m.group(2))
                            dur    = int(m.group(4))
                            root   = tag_root[parent]
                            tag_root[child] = root
                            nodes += 1
                            tree_nodes[root] += 1
                            root_dur[root]["E2"]   += dur
                            root_count[root]["E2"] += 1

                    elif e.startswith("E3"):
                        m = re_e3.match(e)
                        if m:
                            tag  = int(m.group(1))
                            dur  = int(m.group(2))
                            root = tag_root.get(tag)
                            if root is not None:
                                reads += 1
                                tree_reads[root] += 1
                                root_dur[root]["E3"]   += dur
                                root_count[root]["E3"] += 1

                    elif e.startswith("E4"):
                        m = re_e4.match(e)
                        if m:
                            tag  = int(m.group(1))
                            dur  = int(m.group(2))
                            root = tag_root.get(tag)
                            if root is not None:
                                writes += 1
                                tree_writes[root] += 1
                                root_dur[root]["E4"]   += dur
                                root_count[root]["E4"] += 1

                    elif e.startswith("E5"):
                        m = re_e5.match(e)
                        if m:
                            tag  = int(m.group(1))
                            v    = int(m.group(2))
                            s    = int(m.group(3))
                            dur  = int(m.group(4))
                            root = tag_root.get(tag)
                            if root is not None:
                                visited += v
                                skipped += s
                                tree_visited[root] += v
                                tree_skipped[root] += s
                                root_dur[root]["E5"]   += dur
                                root_count[root]["E5"] += 1

                    elif e.startswith("E6"):
                        m = re_e6.match(e)
                        if m:
                            gc_invoked   += 1
                            e6_dur_total += int(m.group(1))
                            e6_dur_count += 1
                        # "E6 (start)" — skip, just the opening sentinel

                    elif e.startswith("E7"):
                        m = re_e7.match(e)
                        if m:
                            tag  = int(m.group(1))
                            r    = int(m.group(2))
                            dur  = int(m.group(3))
                            root = tag_root.get(tag)
                            gc_pruned += r
                            if root is not None:
                                tree_gc_pruned[root] += r
                                root_dur[root]["E7"]   += dur
                                root_count[root]["E7"] += 1

                max_nodes     = max(max_nodes,    max(tree_nodes.values(),     default=0))
                max_reads     = max(max_reads,     max(tree_reads.values(),     default=0))
                max_writes    = max(max_writes,    max(tree_writes.values(),    default=0))
                max_visited   = max(max_visited,   max(tree_visited.values(),   default=0))
                max_skipped   = max(max_skipped,   max(tree_skipped.values(),   default=0))
                max_gc_pruned = max(max_gc_pruned, max(tree_gc_pruned.values(), default=0))

            elif file.startswith("traces-"):
                with open(os.path.join(crate, file)) as tf:
                    lines = tf.readlines()

                for line in lines:
                    if line.startswith("__STATS__"):
                        em = int(empty_pattern.search(line).group(1))
                        no = int(noop_pattern.search(line).group(1))
                        red_loc_states += em
                        red_transitions += no
                        loc_states  += em
                        transitions += no
                    else:
                        rm = root_pattern.match(line)
                        if rm:
                            nonred_roots.add(int(rm.group(1)))
                        for tr, c in trace_pattern.findall(line):
                            c = int(c)
                            n = len([x.strip() for x in tr.split(",")])
                            loc_states  += c
                            transitions += n * c

        # ── Aggregate durations ───────────────────────────────────────────────
        def sum_split(etype):
            """Returns (total_dur, dur_count, event_count,
                        red_dur, red_dur_count, red_event_count,
                        nonred_dur, nonred_dur_count, nonred_event_count)"""
            if etype == "E6":
                return e6_dur_total, e6_dur_count, gc_invoked, 0, 0, 0, 0, 0, 0
            total_dur = red_dur = nonred_dur = 0
            dur_count = red_dur_count = nonred_dur_count = 0
            evt_count = red_evt_count = nonred_evt_count = 0
            for root, durs in root_dur.items():
                d = durs.get(etype, 0)
                c = root_count[root].get(etype, 0)
                total_dur += d; dur_count += c; evt_count += c
                if root in nonred_roots:
                    nonred_dur += d; nonred_dur_count += c; nonred_evt_count += c
                else:
                    red_dur    += d; red_dur_count    += c; red_evt_count    += c
            return (total_dur, dur_count, evt_count,
                    red_dur, red_dur_count, red_evt_count,
                    nonred_dur, nonred_dur_count, nonred_evt_count)

        dur_cols = []
        all_total = all_count = all_events = 0
        red_all_total = red_all_count = red_all_events = 0
        nonred_all_total = nonred_all_count = nonred_all_events = 0
        per_event = {}

        for e in DURATION_EVENTS:
            vals = sum_split(e)
            per_event[e] = vals
            total_dur, dur_count, evt_count = vals[0], vals[1], vals[2]
            dur_cols += list(fmt3(evt_count, total_dur, dur_count))
            all_total  += total_dur; all_count  += dur_count; all_events += evt_count
            if e != "E6":
                red_all_total    += vals[3]; red_all_count    += vals[4]; red_all_events    += vals[5]
                nonred_all_total += vals[6]; nonred_all_count += vals[7]; nonred_all_events += vals[8]

        all_dur_cols = [
            *fmt3(all_events,        all_total,        all_count),
            *fmt3(red_all_events,    red_all_total,    red_all_count),
            *fmt3(nonred_all_events, nonred_all_total, nonred_all_count),
        ]

        red_dur_cols    = [col for e in SPLIT_EVENTS
                           for col in fmt3(per_event[e][5], per_event[e][3], per_event[e][4])]
        nonred_dur_cols = [col for e in SPLIT_EVENTS
                           for col in fmt3(per_event[e][8], per_event[e][6], per_event[e][7])]

        avg_nodes     = nodes     / trees if trees else 0
        avg_reads     = reads     / trees if trees else 0
        avg_writes    = writes    / trees if trees else 0
        avg_visited   = visited   / trees if trees else 0
        avg_skipped   = skipped   / trees if trees else 0
        avg_gc_pruned = gc_pruned / trees if trees else 0
        red_trees     = trees - len(nonred_roots)

        writer_main.writerow([
            crate,
            f"{trees:,}",
            f"{nodes:,}",
            f"{avg_nodes:.1f} ({max_nodes:,})",
            f"{reads:,}",
            f"{avg_reads:.1f} ({max_reads:,})",
            f"{writes:,}",
            f"{avg_writes:.1f} ({max_writes:,})",
            f"{visited:,}",
            f"{avg_visited:.1f} ({max_visited:,})",
            f"{skipped:,}",
            f"{avg_skipped:.1f} ({max_skipped:,})",
            f"{gc_invoked:,}",
            f"{gc_pruned:,}",
            f"{avg_gc_pruned:.1f} ({max_gc_pruned:,})",
            f"{loc_states:,}",
            f"{red_loc_states:,}",
            f"{transitions:,}",
            f"{red_transitions:,}",
            f"{red_trees:,}",
            json.dumps(dict(sorted(all_memory_kinds.items()))),
            *dur_cols,
            *all_dur_cols,
        ])

        writer_split.writerow([
            crate,
            *red_dur_cols,
            *nonred_dur_cols,
        ])

        fmain.flush(); fsplit.flush()