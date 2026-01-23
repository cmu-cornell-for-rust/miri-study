# miri-study

### January Tasks
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

- Test the following profilers ([pros and cons](profiling/profiler-pros-cons.md)):
- [x] [measureme](https://github.com/rust-lang/measureme/blob/master/crox/README.md)
- [x] [DHAT](https://valgrind.org/docs/manual/dh-manual.html)
- [ ] [heaptrack](https://github.com/KDE/heaptrack)
- [ ] [Gungraun](https://github.com/gungraun/gungraun)
- [ ] [Coz](https://github.com/plasma-umass/coz)