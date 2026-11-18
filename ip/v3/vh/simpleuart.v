(* blackbox *)
module simpleuart (
`ifdef USE_POWER_PINS
    inout  wire        VDD,
    inout  wire        VSS,
`endif
    input  wire        clk,
    input  wire        resetn,
    output wire        ser_tx,
    input  wire        ser_rx,
    input  wire [3:0]  reg_div_we,
    input  wire [31:0] reg_div_di,
    output wire [31:0] reg_div_do,
    input  wire        reg_dat_we,
    input  wire        reg_dat_re,
    input  wire [31:0] reg_dat_di,
    output wire [31:0] reg_dat_do,
    output wire        reg_dat_wait
);
endmodule
