(* blackbox *)
module spimemio (
`ifdef USE_POWER_PINS
    inout  wire        VDD,
    inout  wire        VSS,
`endif
    input  wire        clk,
    input  wire        resetn,
    input  wire        valid,
    output wire        ready,
    input  wire [23:0] addr,
    output wire [31:0] rdata,
    output wire        flash_csb,
    output wire        flash_clk,
    output wire        flash_io0_oe,
    output wire        flash_io1_oe,
    output wire        flash_io2_oe,
    output wire        flash_io3_oe,
    output wire        flash_io0_do,
    output wire        flash_io1_do,
    output wire        flash_io2_do,
    output wire        flash_io3_do,
    input  wire        flash_io0_di,
    input  wire        flash_io1_di,
    input  wire        flash_io2_di,
    input  wire        flash_io3_di,
    input  wire [3:0]  cfgreg_we,
    input  wire [31:0] cfgreg_di,
    output wire [31:0] cfgreg_do
);
endmodule
