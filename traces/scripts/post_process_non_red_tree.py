#!/usr/bin/env python3
import os
import re
import csv
from collections import defaultdict

crates = [
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

header = [
"crate","trees","nodes","avg_nodes","read","avg_read (max)","write","avg_write (max)",
"visited","avg_visited (max)","skipped","avg_skipped (max)",
"loc_state","transitions","gc_invoked","gc_pruned","avg_gc_pruned"
]

event_pattern = re.compile(r'(E\d\([^\)]*\)|E6)')
trace_pattern = re.compile(r'\[([A-Z, ]+)\]\s+(\d+)')
root_pattern = re.compile(r'^t(\d+)@')
timestamp_pattern = re.compile(r'-(\d+)$')

with open("output_non_red.csv","w",newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    f.flush()

    for crate in crates:
        files = os.listdir(crate)
        event_files = [f for f in files if f.startswith("events-")]
        trace_files = [f for f in files if f.startswith("traces-")]
        timestamp_map = {}
        for ef in event_files:
            ts = timestamp_pattern.search(ef)
            if ts:
                timestamp_map[ts.group(1)] = {"events": ef, "traces": None}
        for tf in trace_files:
            ts = timestamp_pattern.search(tf)
            if ts and ts.group(1) in timestamp_map:
                timestamp_map[ts.group(1)]["traces"] = tf

        trees=0
        nodes=0
        reads=0
        writes=0
        visited=0
        skipped=0
        gc_invoked=0
        gc_pruned=0
        loc_states=0
        transitions=0

        max_nodes=0
        max_reads=0
        max_writes=0
        max_visited=0
        max_skipped=0
        max_gc_pruned=0

        for ts, files_pair in timestamp_map.items():
            ef_path = os.path.join(crate, files_pair["events"])
            tf_path = os.path.join(crate, files_pair["traces"])
            if not tf_path:
                continue

            tag_root={}
            tree_nodes=defaultdict(int)
            tree_reads=defaultdict(int)
            tree_writes=defaultdict(int)
            tree_visited=defaultdict(int)
            tree_skipped=defaultdict(int)
            tree_gc_pruned=defaultdict(int)
            root_tags_total=set()

            with open(ef_path) as ef:
                line=ef.read().strip()
                events=event_pattern.findall(line)
            for e in events:
                if e.startswith("E1"):
                    m=re.match(r"E1\(a\d+, t(\d+)\)",e)
                    tag=int(m.group(1))
                    tag_root[tag]=tag
                    tree_nodes[tag]+=1
                elif e.startswith("E2"):
                    m=re.match(r"E2\(t(\d+), t(\d+)\)",e)
                    child=int(m.group(1))
                    parent=int(m.group(2))
                    root=tag_root[parent]
                    tag_root[child]=root
                    tree_nodes[root]+=1
                elif e.startswith("E3"):
                    m=re.match(r"E3\(t(\d+)\)",e)
                    tag=int(m.group(1))
                    root=tag_root.get(tag)
                    if root is not None:
                        tree_reads[root]+=1
                elif e.startswith("E4"):
                    m=re.match(r"E4\(t(\d+)\)",e)
                    tag=int(m.group(1))
                    root=tag_root.get(tag)
                    if root is not None:
                        tree_writes[root]+=1
                elif e.startswith("E5"):
                    m=re.match(r"E5\(t(\d+), (\d+), (\d+)\)",e)
                    tag=int(m.group(1))
                    v=int(m.group(2))
                    s=int(m.group(3))
                    root=tag_root.get(tag)
                    if root is not None:
                        tree_visited[root]+=v
                        tree_skipped[root]+=s
                elif e=="E6":
                    gc_invoked+=1
                elif e.startswith("E7"):
                    m=re.match(r"E7\(t(\d+), (\d+)\)",e)
                    tag=int(m.group(1))
                    r=int(m.group(2))
                    root=tag_root.get(tag)
                    if root is not None:
                        tree_gc_pruned[root]+=r

            with open(tf_path) as tf:
                lines=tf.readlines()
            for line in lines:
                rm=root_pattern.match(line)
                if rm:
                    root_tags_total.add(int(rm.group(1)))
                for tr,c in trace_pattern.findall(line):
                    c=int(c)
                    n=len([x.strip() for x in tr.split(",")])
                    loc_states+=c
                    transitions+=n*c

            for root in root_tags_total:
                nodes += tree_nodes[root]
                reads += tree_reads[root]
                writes += tree_writes[root]
                visited += tree_visited[root]
                skipped += tree_skipped[root]
                gc_pruned += tree_gc_pruned[root]

            trees += len(root_tags_total)

            max_nodes = max(max_nodes, max((tree_nodes[r] for r in root_tags_total), default=0))
            max_reads = max(max_reads, max((tree_reads[r] for r in root_tags_total), default=0))
            max_writes = max(max_writes, max((tree_writes[r] for r in root_tags_total), default=0))
            max_visited = max(max_visited, max((tree_visited[r] for r in root_tags_total), default=0))
            max_skipped = max(max_skipped, max((tree_skipped[r] for r in root_tags_total), default=0))
            max_gc_pruned = max(max_gc_pruned, max((tree_gc_pruned[r] for r in root_tags_total), default=0))

        avg_nodes = nodes/trees if trees else 0
        avg_reads = reads/trees if trees else 0
        avg_writes = writes/trees if trees else 0
        avg_visited = visited/trees if trees else 0
        avg_skipped = skipped/trees if trees else 0
        avg_gc_pruned = gc_pruned/trees if trees else 0

        writer.writerow([
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
            f"{loc_states:,}",
            f"{transitions:,}",
            f"{gc_invoked:,}",
            f"{gc_pruned:,}",
            f"{avg_gc_pruned:.1f} ({max_gc_pruned:,})",
        ])
        f.flush()
