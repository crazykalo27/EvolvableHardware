#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

build_one() {
  local name="$1"
  echo "Building ${name}..."
  yosys -q -p "synth_ice40 -top top -json ${name}.json" "${name}.v"
  nextpnr-ice40 --up5k --package sg48 --json "${name}.json" --pcf wirecheck.pcf --asc "${name}.asc" --quiet
  icepack "${name}.asc" "${name}.bin"
  echo "  wrote ${name}.bin"
}

build_one wirecheck_high
build_one wirecheck_follow
echo "Done."
