#!/usr/bin/env bash
# Chip-level RTL simulation (run inside the Nix shell after `make clone-pdk`
# and after building firmware/firmware.hex).
set -euo pipefail
cd "$(dirname "$0")/../.."
PDK_ROOT=${PDK_ROOT:-$PWD/pdk}
PDK=${PDK:-gf180mcuD}
LIB=$PDK_ROOT/$PDK/libs.ref
OUT=verif/soc/out
mkdir -p "$OUT"
iverilog -g2012 -o "$OUT/tb_soc.vvp" -DPICOSOC_MEM=soc_sram_2kb -DFUNCTIONAL \
    -s tb_soc \
    verif/soc/tb_soc.v verif/soc/spiflash.v \
    src/soc/soc_chip_top.v src/soc/soc_top.v src/soc/soc_sram_2kb.v \
    src/soc/vendor/picosoc.v src/soc/vendor/picorv32.v \
    src/soc/vendor/spimemio.v src/soc/vendor/simpleuart.v \
    src/posit_decoder_32_2.v \
    ip/dieart/vh/dieart_tl.v ip/dieart/vh/dieart_tr.v ip/dieart/vh/dieart_bl.v ip/dieart/vh/dieart_br.v \
    "$LIB/gf180mcu_fd_io/verilog/gf180mcu_fd_io.v" \
    "$LIB/gf180mcu_fd_ip_sram/verilog/gf180mcu_fd_ip_sram__sram512x8m8wm1.v"
vvp -n "$OUT/tb_soc.vvp" +firmware=firmware/firmware.hex | tee "$OUT/sim.log"
grep -q "SOC_SIM PASS" "$OUT/sim.log"
