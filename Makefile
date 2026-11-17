# Posit<32,2> decoder: RTL-to-GDS on open PDKs with LibreLane.
# Run inside the Nix shell (nix develop) provided by flake.nix.

PDK_ROOT ?= $(CURDIR)/pdk
GF_PDK ?= gf180mcuD
GF_PDK_COMMIT ?= 792ef67037d74c8c51811eab3ce23cf793491296
SCL ?= gf180mcu_fd_sc_mcu7t5v0
PAD ?= gf180mcu_fd_io

GF_OPTS = --pdk $(GF_PDK) --pdk-root $(PDK_ROOT) --manual-pdk --scl $(SCL) --pad $(PAD)
GF_CONFIGS = librelane/pads.yaml librelane/config.yaml

.DEFAULT_GOAL := help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'
.PHONY: help

generate: ## Regenerate chip_top.v, pads.yaml and the die-art macros
	python3 scripts/gen_chip_top.py
	python3 scripts/make_die_art.py
.PHONY: generate

equiv: ## Prove the Verilog translation equivalent to Decoder_32_2.vhd
	bash verif/equiv.sh
.PHONY: equiv

# ciel enable with retries (the PDK mirrors occasionally return HTTP 503)
define ciel_enable
	ok=0; for i in 1 2 3 4 5; do \
	  if ciel enable $(1) --pdk-root $(PDK_ROOT) --pdk $(2) $(3); then ok=1; break; fi; \
	  echo "ciel attempt $$i failed, retrying"; sleep 60; \
	done; test $$ok = 1
endef

$(PDK_ROOT)/ciel/gf180mcu/versions/$(GF_PDK_COMMIT)/$(GF_PDK):
	$(call ciel_enable,$(GF_PDK_COMMIT),$(GF_PDK),--include-libraries all)

clone-pdk: $(PDK_ROOT)/ciel/gf180mcu/versions/$(GF_PDK_COMMIT)/$(GF_PDK) ## Fetch the GF180MCU PDK
.PHONY: clone-pdk

chip: clone-pdk ## GF180MCU chip with pad ring (LibreLane Chip flow)
	librelane --condensed $(GF_CONFIGS) $(GF_OPTS) --save-views-to $(CURDIR)/final
.PHONY: chip

sky130-pdk: ## Fetch the SKY130 PDK
	$(call ciel_enable,$(GF_PDK_COMMIT),sky130A,)
.PHONY: sky130-pdk

sky130: sky130-pdk ## SKY130 core-only hardening (LibreLane Classic flow)
	librelane --condensed librelane/sky130/config.yaml --pdk sky130A --pdk-root $(PDK_ROOT) --manual-pdk --save-views-to $(CURDIR)/final_sky130
.PHONY: sky130

macro: clone-pdk ## Stage 1: harden the posit decoder as a GF180 macro
	librelane --condensed librelane/posit_macro/config.yaml $(GF_OPTS) --save-views-to $(CURDIR)/build/posit_macro
	bash scripts/export_macro.sh build/posit_macro
.PHONY: macro

firmware: ## Build the SoC self-test firmware (needs riscv64-unknown-elf-gcc)
	bash firmware/build.sh
.PHONY: firmware

soc-sim: clone-pdk ## Chip-level RTL simulation of the SoC (pads, SRAM models, flash)
	bash verif/soc/run_sim.sh
.PHONY: soc-sim

soc: clone-pdk ## Stage 2: RISC-V SoC chip with SRAM and posit macros (Chip flow)
	librelane --condensed librelane/soc/pads.yaml librelane/soc/config.yaml $(GF_OPTS) --save-views-to $(CURDIR)/final_soc
.PHONY: soc

chip-gui: ## Open the last GF180 run in KLayout
	librelane $(GF_CONFIGS) $(GF_OPTS) --last-run --flow OpenInKLayout
.PHONY: chip-gui
