#!/bin/bash

crates=(
    "allocator-api2-0.2.21"
    "chacha20-0.10.0"
    "either-1.11.0"
    "foldhash-0.2.0"
    "getrandom-0.4.0"
    "hashbrown-0.16.1"
    "indexmap-2.13.0"
    "itertools-0.14.0"
    "libc-0.2.178"
    "linux-raw-sys-0.11.0"
    "log-0.4.29"
    "aho-corasick-1.1.3"
    "memchr-2.7.6"
    "ppv-lite86-0.2.21"
    "proc-macro2-1.0.101"
    "rand-0.10.0"
    "regex-automata-0.4.13"
    "rustix-1.1.3"
    "serde_core-1.0.228"
    "socket2-0.6.1"
    "syn-2.0.106"
    "unicode-ident-1.0.19"
    "zerocopy-0.8.31"
)

RESULTS_FILE="results.csv"
ERR_LOG="stderr.log"

> "$RESULTS_FILE"
touch "$ERR_LOG"

for crate in "${crates[@]}"; do
    echo "=== Processing $crate ==="
    cd "$crate" || { echo "Failed to enter $crate"; continue; }

    export MIRI_TRACING=1
    export MIRI_LOG=miri::borrow_tracker=info
    export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows"

    cargo clean > /dev/null 2>&1
    cargo miri test --no-run --quiet > /dev/null 2>> "../$ERR_LOG"
    TREE_TIME=$(/usr/bin/time -f "%e" -o /dev/stdout \
        sh -c 'cargo miri test --quiet > /dev/null 2>&1 || true')

    if [ -e trace*.json ]; then
        mkdir -p traces
        mv trace*.json traces/
        tar -czf "${crate}-traces.tar.gz" traces
        rm -rf traces
    fi

    echo "${crate},${TREE_TIME}" >> ../"$RESULTS_FILE"
    cd - > /dev/null
done

echo "All tests (with tracing) completed."
