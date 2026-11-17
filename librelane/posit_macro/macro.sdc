# Combinational macro: (CLOCK_PERIOD - slack) bounds the input-to-output delay.
current_design $::env(DESIGN_NAME)
set_units -time ns
create_clock -name vclk -period $::env(CLOCK_PERIOD)
set_input_delay  0 -clock vclk [all_inputs]
set_output_delay 0 -clock vclk [all_outputs]
set_input_transition 0.5 [all_inputs]
set_load [expr $::env(OUTPUT_CAP_LOAD) / 1000.0] [all_outputs]
set_max_fanout $::env(MAX_FANOUT_CONSTRAINT) [current_design]
if { [info exists ::env(MAX_TRANSITION_CONSTRAINT)] } {
    set_max_transition $::env(MAX_TRANSITION_CONSTRAINT) [current_design]
}
set_clock_uncertainty $::env(CLOCK_UNCERTAINTY_CONSTRAINT) [get_clocks vclk]
set_timing_derate -early [expr 1 - [expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
set_timing_derate -late  [expr 1 + [expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
