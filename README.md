# miri-study

This repository contains profiling data on Miri using external tools. See [cmu-cornell-for-rust/miri](https://github.com/cmu-cornell-for-rust/miri) for profiling via internal tracing.

## February Tasks

This month we worked on automating profiler execution and analysis.

To execute a crate with a particular profiling tool, navigate to the [`profiling`](/profiling) folder and run this script. Outputs can be found in [`profiling/outputs/`](/profiling/outputs/):

```
python3 run_indiv_tests.py <tool> <project>
```

If you'd like to manually run and analyze specific cases, refer to the steps below.

### Running Miri

By default, test cases can be executed while in the project directory with `cargo test`. Going from native execution to running miri is as easy as inserting `miri` between `cargo` and `test`.

If you'd like to run an entire test suite:
```
cargo miri test
```

If you want to run a single specific test case without spawning extra processes:
```
cargo miri test <test file> <test name> -- --exact
```

Be sure to set the correct flags (listed below) before executing. We disable data race detection and validation, and stacked borrows is enabled by default.

**With Stacked Borrows**: 
```
export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation"
```

**With Tree Borrows**:
```
export MIRIFLAGS="-Zmiri-disable-data-race-detector -Zmiri-disable-validation -Zmiri-tree-borrows"
```

### Running Profilers

#### Valgrind (DHAT and Callgrind):

Both DHAT and Callgrind are executed through Valgrind. They create different output files for each module containing tests and the parent process cargo call. The following two commands also filter out non-execution processes (e.g. compiling and building dependencies) with `--trace-children-skip`.

You only need to modify the last line to specify tool and command.

Default:
```
valgrind --trace-children=yes \
         --time-stamp=yes \
         --trace-children-skip=*/rustc,*/build-script-build \
         --trace-children-skip-by-arg='--crate-type' \
         --tool=<tool> <cargo command>
```

Miri:
```
valgrind --trace-children=yes \
         --time-stamp=yes \
         --trace-children-skip=*/rustc \
         --trace-children-skip-by-arg='--crate-type','-vV','--print','--format-version','--error-format=json' \
         --tool=<tool> <cargo command>
```

#### Perf:

Executing perf is even simpler and takes significantly less time to execute. It creates one `perf.dat` file:
```
perf record --call-graph dwarf -F 99 -e cycles <cargo command>
```

### Interpreting Profiler Output

#### DHAT:

DHAT profiles memory consumption by breaking execution down into Program Points (PP) for every allocation and providing relevant stack traces that led up to the allocation.

DHAT output can be viewed with [dh_view.html](https://nnethercote.github.io/dh_view/dh_view.html).

#### Callgrind:

Callgrind is a call graph and instruction read profiler.
A GUI is provided by [KCachegrind](https://kcachegrind.sourceforge.net/html/Home.html) or QCachegrind on Mac (`brew install qcachegrind`).

Callgrind calculates a "cost" metric based on event counts in a function (data reads, cache misses, etc):
- *Inclusive costs* are those that *include* the costs of functions it calls.
    - e.g. `main` should be around 100% of the total program cost.
- *Exclusive costs* do not count the functions it calls.

#### Perf:

Perf is a lightweight time profiler.
With samply (`cargo install samply`), we can view an html dashboard of time profiling data including the call tree and a flamegraph:
```
samply import perf.dat
```

## January Tasks
- [x] Pull top 30 crates on crates.io
```curl 'https://crates.io/api/v1/crates?sort=downloads&per_page=30' | python3 -m json.tool > top_crates.json```

- [x] Run cargo-geiger to find crates containing unsafe (14):
    - getrandom-0.4.0
    - hashbrown
    - indexmap
    - itertools
    - libc-1.0.0
    - log
    - memchr
    - proc-macro2
    - rand-0.10.0
    - regex-automata
    - rustix
    - socket2
    - syn
    - unicode-ident

Test the following profilers ([pros and cons](profiling/profiler-pros-cons.md)):
- [x] [measureme](https://github.com/rust-lang/measureme/blob/master/crox/README.md)
- [x] [DHAT](https://valgrind.org/docs/manual/dh-manual.html)
- [x] [heaptrack](https://github.com/KDE/heaptrack)
- [x] [Bytehound](https://github.com/koute/bytehound)
- [x] [Gungraun](https://github.com/gungraun/gungraun)
- [x] [Callgrind](https://valgrind.org/docs/manual/cl-manual.html)
- [ ] [Coz](https://github.com/plasma-umass/coz)