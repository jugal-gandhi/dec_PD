#!/usr/bin/env bash
# Chip-level RTL simulation of soc_chip_top with the GF180 pad models, PicoRV32
# booting from an SPI flash model and the 2 KB SRAM, in two modes:
#   foundry    : PDK SRAM model (with its internal timing), 5 MHz sim clock
#   functional : datasheet functional SRAM model, 25 MHz sim clock
# Run inside the Nix shell after `make clone-pdk` and `make firmware`.
set -uo pipefail
cd "$(dirname "$0")/../.."
PDK_ROOT=${PDK_ROOT:-$PWD/pdk}
PDK=${PDK:-gf180mcuD}
LIB=$PDK_ROOT/$PDK/libs.ref
OUT=verif/soc/out
mkdir -p "$OUT"
SRC=(verif/soc/tb_soc.v verif/soc/spiflash.v
     src/soc/soc_chip_top.v src/soc/soc_top.v src/soc/soc_sram_2kb.v
     src/soc/picosoc_gf180.v src/soc/vendor/picorv32.v
     src/soc/vendor/spimemio.v src/soc/vendor/simpleuart.v
     src/posit_decoder_32_2.v
     ip/dieart/vh/dieart_tl.v ip/dieart/vh/dieart_tr.v ip/dieart/vh/dieart_bl.v ip/dieart/vh/dieart_br.v
     "$LIB/gf180mcu_fd_io/verilog/gf180mcu_fd_io.v")
status=0
run() {  # name, clk_half_ns, sram_model
  local name=$1 half=$2 model=$3
  echo "=== $name: SRAM model $(basename "$model"), clock period $((2*half)) ns"
  iverilog -g2012 -o "$OUT/tb_$name.vvp" -DPICOSOC_MEM=soc_sram_2kb -DCLK_HALF=$half \
      -s tb_soc "${SRC[@]}" "$model" 2>&1 | grep -v "Choosing typ" | head -n 20
  vvp -n "$OUT/tb_$name.vvp" +firmware=firmware/firmware.hex > "$OUT/sim_$name.log" 2>&1
  grep -v "Choosing typ" "$OUT/sim_$name.log" | tail -n 15
  grep -q "SOC_SIM PASS" "$OUT/sim_$name.log" || status=1
}
run foundry 100 "$LIB/gf180mcu_fd_ip_sram/verilog/gf180mcu_fd_ip_sram__sram512x8m8wm1.v"
run functional 20 verif/soc/sram_func.v
cat "$OUT"/sim_*.log > "$OUT/sim.log"
exit $status
