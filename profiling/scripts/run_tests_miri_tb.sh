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

    unset MIRIFLAGS

    echo "--- Running native cargo test ---"
    cargo test --no-run --quiet > /dev/null 2>> "../$ERR_LOG"
    TEST_TIME=$(/usr/bin/time -f "%e" -o /dev/stdout \
        sh -c 'cargo test --quiet > /dev/null 2>> "../'"$ERR_LOG"'" || true')
    
    echo "--- Running cargo miri test (stacked borrows disabled) ---"
    export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-disable-stacked-borrows"
    cargo miri test --no-run --quiet > /dev/null 2>> "../$ERR_LOG"
    MIRI_TIME=$(/usr/bin/time -f "%e" -o /dev/stdout \
        sh -c 'cargo miri test --quiet > /dev/null 2>> "../'"$ERR_LOG"'" || true')

    echo "--- Running cargo miri test (tree borrows) ---"
    export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows"
    cargo clean > /dev/null 2>> "../$ERR_LOG"
    cargo miri test --no-run --quiet > /dev/null 2>> "../$ERR_LOG"
    TREE_TIME=$(/usr/bin/time -f "%e" -o /dev/stdout \
        sh -c 'cargo miri test --quiet > /dev/null 2>> "../'"$ERR_LOG"'" || true')

    echo "${crate},${TEST_TIME},${MIRI_TIME},${TREE_TIME}" >> ../"$RESULTS_FILE"
    cd - > /dev/null
done

echo "All tests completed."
