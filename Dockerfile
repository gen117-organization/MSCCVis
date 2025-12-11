FROM python:3.12-slim

# 依存ツールと Rust toolchain をインストール
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        openjdk-21-jre-headless \
        build-essential \
        cargo \
        ruby-full \
        libgit2-dev \
        pkg-config \
        cmake \
        libssl-dev \
        libssh2-1-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Python 依存関係を先に解決してキャッシュを効かせる
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# GitHub Linguist (Ruby gem) をインストール（システムの libgit2 を利用）
RUN RUGGED_USE_SYSTEM_LIBGIT2=ON gem install --no-document github-linguist -- --use-system-libraries --with-git2-include=/usr/include --with-git2-lib=/usr/lib/x86_64-linux-gnu

# ccfindersw-parser を取得してビルド（バイナリをイメージに同梱）
ARG CCF_PARSER_REPO=https://github.com/YukiOhta0519/ccfindersw-parser.git
RUN set -eux; \
    git clone --depth 1 "$CCF_PARSER_REPO" /tmp/ccfindersw-parser; \
    cd /tmp/ccfindersw-parser; \
    cargo build --release --locked || cargo build --release; \
    install -Dm755 target/release/ccfindersw-parser /usr/local/bin/ccfindersw-parser; \
    mkdir -p /app/lib/ccfindersw-parser/target/release; \
    cp target/release/ccfindersw-parser /app/lib/ccfindersw-parser/target/release/; \
    rm -rf /tmp/ccfindersw-parser

# ソースコード一式を配置
COPY . .

# 実行時に成果物を出力するディレクトリ
RUN mkdir -p /app/dest

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
