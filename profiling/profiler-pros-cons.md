## measureme
### Pros
- Built in to Miri  (`export MIRIFLAGS="-Zmiri-tree-borrows -Zmiri-disable-data-race-detector -Zmiri-measureme=./profile-tree-borrow"`)
- `crox` visualizer/flame graph is helpful
### Cons
- Function-level timings only
- Low-level Miri borrowtag fns not present?
- Doesn't run on uninstrumented/regular code without Miri?

## DHAT
### How to
without miri:
```
valgrind --tool=dhat --trace-children=yes cargo test --test mod --release
```
with miri:
```
valgrind --tool=dhat --trace-children=yes cargo miri test --test mod --release
```
with treeborrows miri:
```
export MIRIFLAGS="-Zmiri-tree-borrows"
valgrind --tool=dhat --trace-children=yes cargo miri test --test mod --release
unset MIRIFLAGS
```
### Pros
- Produces separate files for instrumentation and test execution
- Explicit instruction and allocation-level memory consumption data

### Cons
- `--trace-children=yes` is incredibly slow, but necessary to run on `cargo` commands
- Unhelpful default filenames (dhat.out.PID), and produces a lot of files
