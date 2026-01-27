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

## heaptrack

### Pros
- Gives a timeline of memory usage
### Cons
- [Can only be run on Rust binaries](https://github.com/KDE/heaptrack?tab=readme-ov-file#running-heaptrack-on-a-rust-binary), (miri doesn't generate a binary)
- Results can only be visualized with their GUI app, which is [unable to compile on Mac anymore](https://www.mail-archive.com/kde-bugs-dist@kde.org/msg993204.html)
    - older versions have annoying deprecated build dependencies
    - todo: run in a VM or use a tool like `XQuartz` to open a window in docker

## bytehound

### Pros
- Same as above
- Web-based UI

### Cons
- not supported on aarch64
- unclear if it only supports Rust binaries or not
- todo: run in a VM

## Gungran

### Pros
- Leverages multiple different profilers (including DHAT)
- Specific to Rust

### Cons
- Only runs on benchmarks ([unsupported by Miri](https://github.com/bheisler/criterion.rs/issues/778))