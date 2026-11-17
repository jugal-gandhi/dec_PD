// Wraps the GHDL-elaborated VHDL netlist (lower-case names) with the port
// names of src/posit_decoder_32_2.v so that a Yosys miter can pair them.
module gold_wrap (
    input  wire [31:0] posit_in,
    output wire        S,
    output wire [5:0]  reg_O,
    output wire [1:0]  EXP_O,
    output wire        inf,
    output wire [27:0] Mantissa
);
    decoder_32_2 u_gold (
        .\input   (posit_in),
        .s        (S),
        .reg_o    (reg_O),
        .exp_o    (EXP_O),
        .inf      (inf),
        .mantissa (Mantissa)
    );
endmodule
