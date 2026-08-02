#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
native_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
source_file="$native_dir/src/qlab_remote_helper.c"
include_dir="$native_dir/include"
dist_dir="$native_dir/dist/remote"
zig=${ZIG:-zig}

if ! command -v "$zig" >/dev/null 2>&1; then
  echo "Building the Linux remote helpers requires Zig (set ZIG or install zig)." >&2
  exit 127
fi

build_one() {
  tuple=$1
  target=$2
  output_dir="$dist_dir/$tuple"
  output="$output_dir/qlab-remote"
  mkdir -p "$output_dir"
  "$zig" cc \
    -target "$target" \
    -static \
    -O2 -std=c17 -Wall -Wextra -Wpedantic -Werror \
    -I"$include_dir" \
    "$source_file" \
    -o "$output"
  chmod 0755 "$output"
}

build_one linux-x86_64-static x86_64-linux-musl
build_one linux-aarch64-static aarch64-linux-musl

echo "Built static Linux remote helpers in $dist_dir"
