#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: sh $0 <tool> <project dir>"
  echo "Example: sh $0 dhat libc\n\t sh $0 callgrind libc"
  exit 1
fi

TOOL="$1"
PROJECT_DIR="$2"

cd "$PROJECT_DIR" || { echo "Error: Cannot cd to $PROJECT_DIR"; exit 1; }

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
unset MIRIFLAGS

# run with treeborrows miri
export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows"
valgrind --tool="$TOOL" \
--trace-children=yes \
--trace-children-skip=*/rustc \
--trace-children-skip-by-arg='--crate-type','-vV','--print','--format-version','--error-format=json' \
--"$TOOL"-out-file="$TOOL.out.miri-tree.%p"  \
cargo miri test
unset MIRIFLAGS