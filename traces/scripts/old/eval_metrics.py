#!/usr/bin/env python3
import glob
import json
import tarfile
import os
import re
import csv

NEW_ALLOC_RE = re.compile(r"New allocation (.+) has rpot tag <(\d+)>")
REBORROW_RE = re.compile(r"reborrow: reference <(\d+)> derived from <(\d+)> .* size (\d+)")
ACCESS_RE = re.compile(r"(read|write) access with tag <(\d+)>")
MEMORY_VISIT_RE = re.compile(r"(Normal|Wildcard) access .* tag <(\d+)>: visited (\d+) nodes, skipped (\d+) nodes")

def process_trace_file(f):
    tag_to_root = {}
    root_tag_sizes = {}
    reborrow_sizes = {}
    tree_nodes_count = {}
    total_nodes = 0
    total_location_states = 0
    total_read_access = 0
    total_write_access = 0
    nodes_visited = 0
    nodes_skipped = 0
    per_tree_read = {}
    per_tree_write = {}
    per_tree_visited = {}
    per_tree_skipped = {}
    allocid_to_size = {}
    allocid_to_root = {}

    for line in f:
        line = line.decode("utf-8").strip()
        if not line or line in ("[", "]"):
            continue
        try:
            entry = json.loads(line.rstrip(","))
        except json.JSONDecodeError:
            continue
        args = entry.get("args", {})
        msg = args.get("message", "")
        bt = args.get("borrow_tracker")

        m = NEW_ALLOC_RE.search(msg)
        if m:
            alloc_id_msg = m.group(1)
            root_tag = int(m.group(2))
            tag_to_root[root_tag] = root_tag
            tree_nodes_count[root_tag] = 1
            per_tree_read[root_tag] = 0
            per_tree_write[root_tag] = 0
            per_tree_visited[root_tag] = 0
            per_tree_skipped[root_tag] = 0
            if alloc_id_msg in allocid_to_size:
                size = allocid_to_size.pop(alloc_id_msg)
                root_tag_sizes[root_tag] = size
                total_location_states += size
            else:
                allocid_to_root[alloc_id_msg] = root_tag
            continue

        if bt == "new_allocation":
            alloc_id = args.get("id")
            size_val = args.get("alloc_size")
            if size_val and size_val.startswith("Size("):
                size = int(size_val.split()[0][5:])
            else:
                size = 0
            if alloc_id in allocid_to_root:
                root_tag = allocid_to_root[alloc_id]
                root_tag_sizes[root_tag] = size
                total_location_states += size
            else:
                allocid_to_size[alloc_id] = size
            continue

        m = REBORROW_RE.search(msg)
        if m:
            new_tag = int(m.group(1))
            derived_tag = int(m.group(2))
            size = int(m.group(3))
            root_tag = tag_to_root.get(derived_tag)
            if root_tag is None:
                continue
            tag_to_root[new_tag] = root_tag
            tree_nodes_count[root_tag] += 1
            total_nodes += 1
            total_location_states += size
            reborrow_sizes[root_tag] = reborrow_sizes.get(root_tag, 0) + size
            continue

        m = ACCESS_RE.search(msg)
        if m:
            access_type = m.group(1)
            tag = int(m.group(2))
            root_tag = tag_to_root.get(tag)
            if root_tag is None:
                continue
            if access_type == "read":
                total_read_access += 1
                per_tree_read[root_tag] += 1
            else:
                total_write_access += 1
                per_tree_write[root_tag] += 1
            continue

        m = MEMORY_VISIT_RE.search(msg)
        if m:
            tag = int(m.group(2))
            visited = int(m.group(3))
            skipped = int(m.group(4))
            root_tag = tag_to_root.get(tag)
            if root_tag is None:
                continue
            nodes_visited += visited
            nodes_skipped += skipped
            per_tree_visited[root_tag] += visited
            per_tree_skipped[root_tag] += skipped
            continue

    num_trees = len(tree_nodes_count)
    total_nodes = sum(tree_nodes_count.values())

    max_nodes_per_tree = max(tree_nodes_count.values()) if tree_nodes_count else 0
    max_location_states_per_tree = max(
        (root_tag_sizes.get(rt, 0) + reborrow_sizes.get(rt, 0)) for rt in tree_nodes_count
    ) if tree_nodes_count else 0

    max_read_per_tree = max(per_tree_read.values()) if per_tree_read else 0
    max_write_per_tree = max(per_tree_write.values()) if per_tree_write else 0
    max_visited_per_tree = max(per_tree_visited.values()) if per_tree_visited else 0
    max_skipped_per_tree = max(per_tree_skipped.values()) if per_tree_skipped else 0

    return {
        "num_trees": num_trees,
        "total_nodes": total_nodes,
        "total_location_states": total_location_states,
        "total_read_access": total_read_access,
        "total_write_access": total_write_access,
        "nodes_visited": nodes_visited,
        "nodes_skipped": nodes_skipped,
        "max_nodes_per_tree": max_nodes_per_tree,
        "max_location_states_per_tree": max_location_states_per_tree,
        "max_read_per_tree": max_read_per_tree,
        "max_write_per_tree": max_write_per_tree,
        "max_visited_per_tree": max_visited_per_tree,
        "max_skipped_per_tree": max_skipped_per_tree
    }

def process_crate(crate_tar_path):
    crate_name = os.path.basename(crate_tar_path).replace("-traces.tar.gz","")
    all_metrics = []
    with tarfile.open(crate_tar_path, "r:gz") as tar:
        for member in sorted(tar.getmembers(), key=lambda x: x.name):
            if member.isfile() and member.name.startswith("traces/trace") and member.name.endswith(".json"):
                f = tar.extractfile(member)
                if f:
                    metrics = process_trace_file(f)
                    if metrics:
                        all_metrics.append(metrics)
    if not all_metrics:
        return None

    agg = {}
    total_trees = sum(m["num_trees"] for m in all_metrics)

    for k in all_metrics[0]:
        if k.startswith("max_"):
            agg[k] = max(m[k] for m in all_metrics)
        else:
            agg[k] = sum(m[k] for m in all_metrics)

    if total_trees:
        agg["avg_nodes_per_tree"] = agg["total_nodes"] / total_trees
        agg["avg_location_states_per_tree"] = agg["total_location_states"] / total_trees
        agg["avg_read_per_tree"] = agg["total_read_access"] / total_trees
        agg["avg_write_per_tree"] = agg["total_write_access"] / total_trees
        agg["avg_nodes_visited_per_tree"] = agg["nodes_visited"] / total_trees
        agg["avg_nodes_skipped_per_tree"] = agg["nodes_skipped"] / total_trees
    else:
        agg["avg_nodes_per_tree"] = 0
        agg["avg_location_states_per_tree"] = 0
        agg["avg_read_per_tree"] = 0
        agg["avg_write_per_tree"] = 0
        agg["avg_nodes_visited_per_tree"] = 0
        agg["avg_nodes_skipped_per_tree"] = 0

    return crate_name, agg

def main():
    results_tree = []
    results_access = []
    for tar_path in sorted(glob.glob("*-traces.tar.gz")):
        crate_result = process_crate(tar_path)
        if crate_result:
            crate_name, metrics = crate_result
            results_tree.append((crate_name, metrics))
            results_access.append((crate_name, metrics))

    with open("results_tree.csv", "w", newline="") as f:
        writer = csv.writer(f)
        header = ["crate","trees","nodes","avg_nodes","loc_states","avg_loc_states"]
        writer.writerow(header)
        for crate_name, metrics in results_tree:
            writer.writerow([
                crate_name,
                metrics["num_trees"],
                metrics["total_nodes"],
                f"{metrics['avg_nodes_per_tree']:.2f} ({metrics['max_nodes_per_tree']})",
                metrics["total_location_states"],
                f"{metrics['avg_location_states_per_tree']:.2f} ({metrics['max_location_states_per_tree']})"
            ])

    with open("results_access.csv", "w", newline="") as f:
        writer = csv.writer(f)
        header = ["crate","read","avg_read","write","avg_write","visited","avg_visited","skipped","avg_skipped"]
        writer.writerow(header)
        for crate_name, metrics in results_access:
            writer.writerow([
                crate_name,
                metrics["total_read_access"],
                f"{metrics['avg_read_per_tree']:.2f} ({metrics['max_read_per_tree']})",
                metrics["total_write_access"],
                f"{metrics['avg_write_per_tree']:.2f} ({metrics['max_write_per_tree']})",
                metrics["nodes_visited"],
                f"{metrics['avg_nodes_visited_per_tree']:.2f} ({metrics['max_visited_per_tree']})",
                metrics["nodes_skipped"],
                f"{metrics['avg_nodes_skipped_per_tree']:.2f} ({metrics['max_skipped_per_tree']})"
            ])

if __name__ == "__main__":
    main()

