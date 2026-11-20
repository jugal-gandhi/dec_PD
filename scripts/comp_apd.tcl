# Component-wise power and critical path of the hierarchy-preserving posit decoder.
# Env: TOP, LIB, NL, SPEF, OUT, LOAD_PF, TLEF, CLEF
if {[info exists ::env(TLEF)] && $::env(TLEF) ne ""} {
  read_lef $::env(TLEF)
  read_lef $::env(CLEF)
}
read_liberty $::env(LIB)
read_verilog $::env(NL)
link_design $::env(TOP)
read_spef $::env(SPEF)
create_clock -name vclk -period 20.0
set_input_delay 0 -clock vclk [all_inputs]
set_output_delay 0 -clock vclk [all_outputs]
set_input_transition 0.5 [all_inputs]
set_load $::env(LOAD_PF) [all_outputs]
set_power_activity -input -activity 0.2
file mkdir $::env(OUT)
report_power -digits 8 > $::env(OUT)/power_total.rpt
report_power -instances [get_cells *] -digits 8 > $::env(OUT)/power_instances.rpt
report_checks -path_delay max -fields {slew cap fanout input_pins} -digits 4 > $::env(OUT)/path_max.rpt
report_checks -path_delay max -format end -group_path_count 1000 -endpoint_path_count 1 -digits 4 > $::env(OUT)/ends_max.rpt
puts "COMP_DONE"
