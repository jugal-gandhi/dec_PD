// Posit<32,2> decoder: Verilog translation of Decoder_32_2.vhd (Behavioral).
// The structure follows the VHDL line by line: a five-stage regime detector
// (16/8/4/2/1-bit windows) that left-shifts the regime run out of the word.
// Equivalence to the VHDL source is checked formally in verif/equiv.sh.

`default_nettype none

module posit_decoder_32_2 (
    input  wire [31:0] posit_in,   // VHDL: INPUT
    output wire        S,          // sign
    output wire [5:0]  reg_O,      // regime value
    output wire [1:0]  EXP_O,      // exponent (es = 2)
    output wire        inf,        // NaR flag
    output wire [27:0] Mantissa    // {zero_check, fraction[26:0]}
);
    wire        sign    = posit_in[31];
    wire        r_check = posit_in[30];
    wire [29:0] d5      = posit_in[29:0];

    // Stage 4: 16-bit window
    wire        d_and_4 = r_check ? (&d5[29:14]) : (|d5[29:14]);
    wire        count4  = (d_and_4 == r_check);
    wire [29:0] d4      = count4 ? {d5[13:0], 16'b0} : d5;

    // Stage 3: 8-bit window (VHDL tests 9 bits: 29 downto 21)
    wire        d_and_3 = r_check ? (&d4[29:21]) : (|d4[29:21]);
    wire        count3  = (d_and_3 == r_check);
    wire [29:0] d3      = count3 ? {d4[21:0], 8'b0} : d4;

    // Stage 2: 4-bit window (VHDL tests 5 bits: 29 downto 25)
    wire        d_and_2 = r_check ? (&d3[29:25]) : (|d3[29:25]);
    wire        count2  = (d_and_2 == r_check);
    wire [29:0] d2      = count2 ? {d3[25:0], 4'b0} : d3;

    // Stage 1: 2-bit window (VHDL tests 3 bits: 29 downto 27)
    wire        d_and_1 = r_check ? (&d2[29:27]) : (|d2[29:27]);
    wire        count1  = (d_and_1 == r_check);
    wire [29:0] d1      = count1 ? {d2[27:0], 2'b0} : d2;

    // Stage 0: 1-bit window
    wire        d_and_0 = d1[29];
    wire        count0  = (d_and_0 == r_check);
    wire [29:0] d0      = count0 ? {d1[28:0], 1'b0} : d1;

    wire [4:0]  k = {count4, count3, count2, count1, count0};

    // Zero / infinity check
    wire zero_check = (d_and_4 == r_check) ? posit_in[31] : 1'b1;
    assign inf = (zero_check == 1'b0) && (sign == 1'b1);

    assign S        = sign;
    assign reg_O    = (r_check == sign) ? {1'b1, ~k} : {1'b0, k};
    assign EXP_O    = d0[28:27];
    assign Mantissa = {zero_check, d0[26:0]};
endmodule

`default_nettype wire
