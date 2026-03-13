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
"gc_invoked","gc_pruned","avg_gc_pruned",
"loc_state","red_loc_state","transitions","red_transitions","red_trees"
]

event_pattern = re.compile(r'(E\d\([^\)]*\)|E6)')
trace_pattern = re.compile(r'\[([A-Z, ]+)\]\s+(\d+)')
empty_pattern = re.compile(r'empty_fsm=(\d+)')
noop_pattern = re.compile(r'noop_transitions=(\d+)')
root_pattern = re.compile(r'^t(\d+)@')

with open("output.csv","w",newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    f.flush()
    for crate in crates:
        trees=0
        nodes=0
        reads=0
        writes=0
        visited=0
        skipped=0
        gc_invoked=0
        gc_pruned=0
        loc_states=0
        red_loc_states=0
        transitions=0
        red_transitions=0
        max_nodes=max_reads=max_writes=max_visited=max_skipped=max_gc_pruned=0
        root_tags_total=0

        for file in os.listdir(crate):
            if file.startswith("events-"):
                tag_root={}
                tree_nodes=defaultdict(int)
                tree_reads=defaultdict(int)
                tree_writes=defaultdict(int)
                tree_visited=defaultdict(int)
                tree_skipped=defaultdict(int)
                tree_gc_pruned=defaultdict(int)

                with open(os.path.join(crate,file)) as ef:
                    line=ef.read().strip()
                    events=event_pattern.findall(line)

                for e in events:
                    if e.startswith("E1"):
                        m=re.match(r"E1\(a\d+, t(\d+)\)",e)
                        tag=int(m.group(1))
                        tag_root[tag]=tag
                        trees+=1
                        nodes+=1
                        tree_nodes[tag]+=1

                    elif e.startswith("E2"):
                        m=re.match(r"E2\(t(\d+), t(\d+)\)",e)
                        child=int(m.group(1))
                        parent=int(m.group(2))
                        root=tag_root[parent]
                        tag_root[child]=root
                        nodes+=1
                        tree_nodes[root]+=1

                    elif e.startswith("E3"):
                        m=re.match(r"E3\(t(\d+)\)",e)
                        tag=int(m.group(1))
                        root=tag_root.get(tag)
                        if root is not None:
                            reads+=1
                            tree_reads[root]+=1

                    elif e.startswith("E4"):
                        m=re.match(r"E4\(t(\d+)\)",e)
                        tag=int(m.group(1))
                        root=tag_root.get(tag)
                        if root is not None:
                            writes+=1
                            tree_writes[root]+=1

                    elif e.startswith("E5"):
                        m=re.match(r"E5\(t(\d+), (\d+), (\d+)\)",e)
                        tag=int(m.group(1))
                        v=int(m.group(2))
                        s=int(m.group(3))
                        root=tag_root.get(tag)
                        if root is not None:
                            visited+=v
                            skipped+=s
                            tree_visited[root]+=v
                            tree_skipped[root]+=s

                    elif e=="E6":
                        gc_invoked+=1

                    elif e.startswith("E7"):
                        m=re.match(r"E7\(t(\d+), (\d+)\)",e)
                        tag=int(m.group(1))
                        r=int(m.group(2))
                        root=tag_root.get(tag)
                        gc_pruned+=r
                        if root is not None:
                            tree_gc_pruned[root]+=r
                max_nodes = max(max_nodes, max(tree_nodes.values(), default=0))
                max_reads = max(max_reads, max(tree_reads.values(), default=0))
                max_writes = max(max_writes, max(tree_writes.values(), default=0))
                max_visited = max(max_visited, max(tree_visited.values(), default=0))
                max_skipped = max(max_skipped, max(tree_skipped.values(), default=0))
                max_gc_pruned = max(max_gc_pruned, max(tree_gc_pruned.values(), default=0))

            if file.startswith("traces-"):
                roots=set()
                with open(os.path.join(crate,file)) as tf:
                    lines=tf.readlines()

                for line in lines:
                    if line.startswith("__STATS__"):
                        em=int(empty_pattern.search(line).group(1))
                        no=int(noop_pattern.search(line).group(1))
                        red_loc_states+=em
                        red_transitions+=no
                        loc_states+=em
                        transitions+=no
                    else:
                        rm=root_pattern.match(line)
                        if rm:
                            roots.add(rm.group(1))
                        for tr,c in trace_pattern.findall(line):
                            c=int(c)
                            n=len([x.strip() for x in tr.split(",")])
                            loc_states+=c
                            transitions+=n*c
                root_tags_total+=len(roots)

        avg_nodes = nodes/trees if trees else 0
        avg_reads = reads/trees if trees else 0
        avg_writes = writes/trees if trees else 0
        avg_visited = visited/trees if trees else 0
        avg_skipped = skipped/trees if trees else 0
        avg_gc_pruned = gc_pruned/trees if trees else 0
        red_trees = trees - root_tags_total

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
            f"{gc_invoked:,}",
            f"{gc_pruned:,}",
            f"{avg_gc_pruned:.1f} ({max_gc_pruned:,})",
            f"{loc_states:,}",
            f"{red_loc_states:,}",
            f"{transitions:,}",
            f"{red_transitions:,}",
            f"{red_trees:,}"
        ])
        f.flush()
