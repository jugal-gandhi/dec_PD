#!/usr/bin/env bash
# Build firmware.hex (Verilog hex at flash offset 1 MB) with a RISC-V GCC.
set -euo pipefail
cd "$(dirname "$0")"
CROSS=${CROSS:-riscv64-unknown-elf-}
python3 gen_vectors.py vectors.h
${CROSS}gcc -march=rv32imc -mabi=ilp32 -Os -ffreestanding -fno-builtin -nostdlib \
    -mno-relax -Wall -Wl,-T,sections.lds -Wl,--no-relax -o firmware.elf start.S main.c
${CROSS}objcopy -O verilog firmware.elf firmware.hex
${CROSS}size firmware.elf
${CROSS}objdump -d firmware.elf | grep -c -E "\s(mul|divu|remu)\s" | xargs echo "M-extension instructions:"
