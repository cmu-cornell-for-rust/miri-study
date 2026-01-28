#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: sh $0 <tool>"
  echo "Example: sh $0 dhat OR sh $0 callgrind"
  exit 1
fi

TOOL="$1"

# default run
valgrind --tool="$TOOL" --trace-children=yes --trace-children-skip=*/rustc --trace-children-skip-by-arg='--crate-type' cargo test

# run with miri
export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation"
valgrind --tool="$TOOL" \
--trace-children=yes \
--trace-children-skip=*/rustc \
--trace-children-skip-by-arg='--crate-type','-vV','--print','--format-version','--error-format=json' \
--"$TOOL"-out-file="$TOOL.out.miri.%p"  \
cargo miri test

# run with treeborrows miri
export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows"
valgrind --tool="$TOOL" \
--trace-children=yes \
--trace-children-skip=*/rustc \
--trace-children-skip-by-arg='--crate-type','-vV','--print','--format-version','--error-format=json' \
--"$TOOL"-out-file="$TOOL.out.miri-tree.%p"  \
cargo miri test