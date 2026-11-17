# Clocked SoC: 25 MHz from the clk pad (Schmitt-trigger input).
current_design $::env(DESIGN_NAME)
set_units -time ns

create_clock [get_pins $::env(CLOCK_NET)] -name clk -period $::env(CLOCK_PERIOD)
set clocks [get_clocks clk]

set io_delay [expr $::env(CLOCK_PERIOD) * $::env(IO_DELAY_CONSTRAINT) / 100]

set bidir [get_ports {flash_io_PAD[*] gpio_PAD[*]}]
set ins   [get_ports {rst_n_PAD ser_rx_PAD irq5_PAD irq6_PAD}]
set outs  [get_ports {ser_tx_PAD flash_csb_PAD flash_clk_PAD}]

set_input_delay -min 0 -clock $clocks $bidir
set_input_delay -max $io_delay -clock $clocks $bidir
set_output_delay $io_delay -clock $clocks $bidir
set_input_delay -min 0 -clock $clocks $ins
set_input_delay -max $io_delay -clock $clocks $ins
set_output_delay $io_delay -clock $clocks $outs

set_max_fanout $::env(MAX_FANOUT_CONSTRAINT) [current_design]
if { [info exists ::env(MAX_TRANSITION_CONSTRAINT)] } {
    set_max_transition $::env(MAX_TRANSITION_CONSTRAINT) [current_design]
}
# No design-level set_max_capacitance: it would land on the bond-pad ports.

set_load [expr $::env(OUTPUT_CAP_LOAD) / 1000.0] [all_outputs]
set_clock_uncertainty $::env(CLOCK_UNCERTAINTY_CONSTRAINT) $clocks
set_clock_transition $::env(CLOCK_TRANSITION_CONSTRAINT) $clocks
set_timing_derate -early [expr 1 - [expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
set_timing_derate -late  [expr 1 + [expr $::env(TIME_DERATING_CONSTRAINT) / 100]]

if { [info exists ::env(OPENLANE_SDC_IDEAL_CLOCKS)] && $::env(OPENLANE_SDC_IDEAL_CLOCKS) } {
    unset_propagated_clock [all_clocks]
} else {
    set_propagated_clock [all_clocks]
}
