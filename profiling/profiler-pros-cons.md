## measureme
### Pros
- Built in to Miri  (`export MIRIFLAGS="-Zmiri-tree-borrows -Zmiri-disable-data-race-detector -Zmiri-measureme=./profile-tree-borrow"`)
- `crox` visualizer/flame graph is helpful
### Cons
- Function-level timings only
- Doesn't run on uninstrumented/regular code without Miri