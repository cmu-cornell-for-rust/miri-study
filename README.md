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