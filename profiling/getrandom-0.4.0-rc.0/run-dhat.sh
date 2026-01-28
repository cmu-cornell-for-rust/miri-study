#!/bin/bash

# default run
valgrind --tool=dhat --trace-children=yes --trace-children-skip=*/rustc --trace-children-skip-by-arg='--crate-type' cargo test

# run with miri
export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation"
valgrind --tool=dhat \
    --trace-children=yes \
    --trace-children-skip=*/rustc \
    --trace-children-skip-by-arg='--crate-type','-vV','--print','--format-version','--error-format=json' \
    --dhat-out-file="dhat.out.miri.%p"  \
    cargo miri test

# run with treeborrows miri
export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows"
valgrind --tool=dhat \
    --trace-children=yes \
    --trace-children-skip=*/rustc \
    --trace-children-skip-by-arg='--crate-type','-vV','--print','--format-version','--error-format=json' \
    --dhat-out-file="dhat.out.miri-tree.%p"  \
    cargo miri test