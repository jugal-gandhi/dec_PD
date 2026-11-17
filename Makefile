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

$(PDK_ROOT)/ciel/gf180mcu/versions/$(GF_PDK_COMMIT)/$(GF_PDK):
	ciel enable $(GF_PDK_COMMIT) --pdk-root $(PDK_ROOT) --pdk $(GF_PDK) --include-libraries all

clone-pdk: $(PDK_ROOT)/ciel/gf180mcu/versions/$(GF_PDK_COMMIT)/$(GF_PDK) ## Fetch the GF180MCU PDK
.PHONY: clone-pdk

chip: clone-pdk ## GF180MCU chip with pad ring (LibreLane Chip flow)
	librelane --condensed $(GF_CONFIGS) $(GF_OPTS) --save-views-to $(CURDIR)/final
.PHONY: chip

sky130: ## SKY130 core-only hardening (LibreLane Classic flow)
	librelane --condensed librelane/sky130/config.yaml --pdk sky130A --save-views-to $(CURDIR)/final_sky130
.PHONY: sky130

chip-gui: ## Open the last GF180 run in KLayout
	librelane $(GF_CONFIGS) $(GF_OPTS) --last-run --flow OpenInKLayout
.PHONY: chip-gui
