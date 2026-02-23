#!/usr/bin/env bash
set -euo pipefail

CRATES=(
    "getrandom-0.4.0"
    "chacha20-0.10.0"	
    "hashbrown-0.16.1"
    "memchr-2.7.6"
    "rand-0.10.0"
    "unicode-ident-1.0.19"
    "zerocopy-0.8.31"
    "serde_json-1.0.149"
    "sha2-0.11.0-rc.5"
    "smallvec-2.0.0-alpha.12"
    "strsim-0.11.1"
    "typenum-1.19.0"
    "unicode-normalization-0.1.25"
    "unicode-xid-0.2.6"
    "zerocopy-0.9.0-alpha.0"
)

RESULTS="$(pwd)/results.csv"
echo "crate, tree_borrow%, total_time" > "$RESULTS"

for CRATE_VER in "${CRATES[@]}"; do
    NAME="$(sed -E 's/-[0-9].*$//' <<< "$CRATE_VER")"
    VERSION="$(sed -E 's/^.*-([0-9].*)$/\1/' <<< "$CRATE_VER")"

    echo "Processing $NAME==${VERSION} ..."
    cargo download "${NAME}==${VERSION}" -x

    cd "${NAME}-${VERSION}"

    export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-deterministic-concurrency -Zmiri-disable-stacked-borrows"
    NO_TB_LOG="${NAME}_no_tb-${VERSION}.log"

    echo "Running cargo miri test (no tree-borrows)"
    rm -f profile.log
    cargo clean > /dev/null 2>&1
    cargo miri test --lib --tests > /dev/null 2>&1 || echo "cargo miri test (no tree-borrows) failed for $NAME==$VERSION"
    mv profile.log "$NO_TB_LOG"

    echo "Parsing log..."
    python3 ../post_process.py "$NO_TB_LOG" >> "$RESULTS"

    export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-deterministic-concurrency -Zmiri-tree-borrows"
    TB_LOG="${NAME}-${VERSION}.log"

    echo "Running cargo miri test (with tree-borrows)"
    rm -f profile.log
    cargo clean > /dev/null 2>&1
    cargo miri test --lib --tests > /dev/null 2>&1 || echo "cargo miri test (with tree-borrows) failed for $NAME==$VERSION"
    mv profile.log "$TB_LOG"

    echo "Parsing log..."
    python3 ../post_process.py "$TB_LOG" >> "$RESULTS"

    cd ..
done
echo "All crates processed. Results are in $RESULTS."
