#!/bin/bash
set -euo pipefail

build_one() {
    local src="$1"
    local stem="$2"
    echo "=== Building ${stem} from ${src} ==="
    yosys -p "read_verilog ${src}; synth_ice40 -top top -json ${stem}.json"
    nextpnr-ice40 --up5k --package sg48 --json "${stem}.json" --pcf diag.pcf --asc "${stem}.asc"
    icepack "${stem}.asc" "${stem}.bin"
}

build_one diag_a.v diag_a
build_one diag_b.v diag_b
build_one xor.v xor

echo
echo "Built diag_a.bin, diag_b.bin, and xor.bin."
