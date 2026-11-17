# Combinational design: a virtual clock bounds the pad-to-pad path.
# Input and output delays are zero, so (CLOCK_PERIOD - worst slack) equals the
# critical pad-to-pad propagation delay, including the input pad buffer,
# the decoder logic and the 24 mA output driver.
current_design $::env(DESIGN_NAME)
set_units -time ns

create_clock -name vclk -period $::env(CLOCK_PERIOD)

set in_ports  [get_ports {posit_PAD[*]}]
set out_ports [get_ports {sign_PAD reg_PAD[*] exp_PAD[*] inf_PAD mant_PAD[*]}]

set_input_delay  0 -clock vclk $in_ports
set_output_delay 0 -clock vclk $out_ports
set_input_transition 0.5 $in_ports

set cap_load [expr $::env(OUTPUT_CAP_LOAD) / 1000.0]
puts "\[INFO] Output load: $cap_load pF"
set_load $cap_load $out_ports

set_max_fanout $::env(MAX_FANOUT_CONSTRAINT) [current_design]
if { [info exists ::env(MAX_TRANSITION_CONSTRAINT)] } {
    set_max_transition $::env(MAX_TRANSITION_CONSTRAINT) [current_design]
}
if { [info exists ::env(MAX_CAPACITANCE_CONSTRAINT)] } {
    set_max_capacitance $::env(MAX_CAPACITANCE_CONSTRAINT) [current_design]
}

set_clock_uncertainty $::env(CLOCK_UNCERTAINTY_CONSTRAINT) [get_clocks vclk]
set_timing_derate -early [expr 1 - [expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
set_timing_derate -late  [expr 1 + [expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
