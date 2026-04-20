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
    linux-perf \
    python3 \
    python3-pip \
    python3-venv \
    python3-ipykernel \
    && rm -rf /var/lib/apt/lists/*
RUN update-alternatives --install /usr/bin/cc cc /usr/bin/clang 100 \
    && update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++ 100
    
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --default-toolchain nightly-2026-03-12 -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN rustup default nightly-2026-03-12
RUN rustup component add rust-src --toolchain nightly-2026-03-12
RUN NIGHTLY_COMMIT=$(rustc --version --verbose | grep "commit-hash" | awk '{print $2}') \
    && mkdir /rust-src \
    && cd /rust-src \
    && git init \
    && git remote add origin https://github.com/rust-lang/rust.git \
    && git fetch --depth 1 origin $NIGHTLY_COMMIT \
    && git checkout FETCH_HEAD

COPY bootstrap.toml /rust-src/bootstrap.toml
WORKDIR /rust-src
RUN ./x.py build --stage 2 compiler/rustc library cargo src/tools/miri
# Install cargo tools using nightly cargo before switching PATH
RUN cargo install cargo-download
RUN cargo install --locked cargo-geiger
RUN cargo install samply
RUN rustup component add rust-src