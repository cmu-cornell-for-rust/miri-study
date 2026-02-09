FROM ubuntu:25.04 AS base
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    libunwind8 \
    libunwind-dev \
    build-essential \
    cmake \
    clang \
    clang-tidy \
    clang-format \
    ninja-build \ 
    curl \ 
    vim \
    pkg-config \ 
    libssl-dev \ 
    sudo \
    git \
    gdb \
    r-base \
    valgrind \
    elfutils \
    libdw-dev \
    libelf-dev \
    libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*
RUN update-alternatives --install /usr/bin/cc cc /usr/bin/clang 100 \
    && update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++ 100
ENV TMPDIR=/tmp
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --default-toolchain nightly -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN rustup install nightly
RUN rustup default nightly
RUN cargo install cargo-download
RUN cargo install --locked cargo-geiger
RUN rustup component add miri #TODO: add our fork of miri
RUN rustup component add rust-src