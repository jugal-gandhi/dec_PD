#!/usr/bin/env bash
# Formal + simulation equivalence: Decoder_32_2.vhd (GHDL) vs src/posit_decoder_32_2.v
# Run inside the project Nix shell (provides yosys with the ghdl plugin and iverilog).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=verif/out
mkdir -p "$OUT"

# 1. Elaborate the original VHDL with GHDL and write it out as a Verilog netlist.
yosys -l "$OUT/ghdl.log" -p "
plugin -i ghdl
ghdl Decoder_32_2.vhd -e Decoder_32_2
write_verilog -noattr $OUT/gold_ghdl.v
" > /dev/null
python3 verif/make_wrap.py "$OUT/gold_ghdl.v" "$OUT/gold_wrap.v"

# 2. Formal proof: SAT miter over all 2^32 inputs.
yosys -l "$OUT/formal.log" -p "
read_verilog $OUT/gold_ghdl.v $OUT/gold_wrap.v
read_verilog src/posit_decoder_32_2.v
hierarchy
proc
opt_clean
flatten
miter -equiv -flatten -make_assert gold_wrap posit_decoder_32_2 miter
hierarchy -top miter
sat -verify -prove-asserts -show-ports miter
" > /dev/null && echo "FORMAL_EQUIV PASS: SAT proof over all 2^32 inputs" | tee "$OUT/formal_result.txt"

# 3. Simulation cross-check.
iverilog -g2005 -o "$OUT/tb_equiv.vvp" verif/tb_equiv.v "$OUT/gold_wrap.v" "$OUT/gold_ghdl.v" src/posit_decoder_32_2.v
vvp "$OUT/tb_equiv.vvp" | tee "$OUT/sim_result.txt"
grep -q "SIM_EQUIV PASS" "$OUT/sim_result.txt"
