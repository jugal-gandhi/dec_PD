// Black-box header of the hardened posit decoder macro.
(* blackbox *)
module posit_decoder_32_2 (
`ifdef USE_POWER_PINS
    inout  wire        VDD,
    inout  wire        VSS,
`endif
    input  wire [31:0] posit_in,
    output wire        S,
    output wire [5:0]  reg_O,
    output wire [1:0]  EXP_O,
    output wire        inf,
    output wire [27:0] Mantissa
);
endmodule
