(* blackbox *)
module simd_alu (
`ifdef USE_POWER_PINS
    inout  wire        VDD,
    inout  wire        VSS,
`endif
    input  wire        clk,
    input  wire        resetn,
    input  wire        wr,
    input  wire [3:0]  addr,
    input  wire [31:0] wdata,
    output wire [31:0] rdata
);
endmodule
