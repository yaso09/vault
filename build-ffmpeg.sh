#!/bin/bash
set -e

FFMPEG_WASI_DIR="./FFmpeg-WASI"
BINARIES_DIR="./binaries"

# Dizin varsa ve boşsa sil
if [ -d "$FFMPEG_WASI_DIR" ] && [ -z "$(ls -A "$FFMPEG_WASI_DIR")" ]; then
    rm -rf "$FFMPEG_WASI_DIR"
fi

# Dizin yoksa submodule güncelle
if [ ! -d "$FFMPEG_WASI_DIR" ]; then
    git submodule update --init --recursive
fi

FIRST_DIR=$(pwd)

cd "$FFMPEG_WASI_DIR"
chmod +x build.sh
./build.sh

cd "$FIRST_DIR"

mkdir -p "$BINARIES_DIR"

cp "$FFMPEG_WASI_DIR/ffmpeg.wasm"  "$BINARIES_DIR/ffmpeg.wasm"
cp "$FFMPEG_WASI_DIR/ffprobe.wasm" "$BINARIES_DIR/ffprobe.wasm"

echo "Build tamamlandı: ffmpeg.wasm ve ffprobe.wasm → $BINARIES_DIR"