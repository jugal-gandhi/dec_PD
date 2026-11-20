// Posit<32,2> decoder, component-structured form of posit_decoder_32_2.v.
// Same logic, split into named modules so a hierarchy-preserving layout run can
// report area, delay and power per component:
//   pd_andor  - AND-OR network of each stage (AND-reduce for a run of ones,
//               OR-reduce for a run of zeros)
//   pd_cmp    - boundary detection, a 1-bit comparator against the regime bit
//   pd_shift  - in-line shifter stage (2:1 multiplexers)
//   pd_outenc - regime encoding, zero/NaR check and output fields
// Equivalence to posit_decoder_32_2 is proved formally (scripts/cmp_sim.sh).

`default_nettype none

module pd_andor #(parameter W = 16) (
    input  wire [W-1:0] win,
    input  wire         rc,
    output wire         d_and
);
    assign d_and = rc ? (&win) : (|win);
endmodule

module pd_cmp (
    input  wire d_and,
    input  wire rc,
    output wire hit
);
    assign hit = (d_and == rc);
endmodule

module pd_shift #(parameter S = 16) (
    input  wire [29:0] din,
    input  wire        sel,
    output wire [29:0] dout
);
    assign dout = sel ? {din[29-S:0], {S{1'b0}}} : din;
endmodule

module pd_outenc (
    input  wire        sign,
    input  wire        rc,
    input  wire [4:0]  k,
    input  wire        hit4,
    input  wire [28:0] d0,
    output wire [5:0]  reg_O,
    output wire [1:0]  EXP_O,
    output wire        inf,
    output wire [27:0] Mantissa
);
    wire zero_check = hit4 ? sign : 1'b1;
    assign inf      = (zero_check == 1'b0) && (sign == 1'b1);
    assign reg_O    = (rc == sign) ? {1'b1, ~k} : {1'b0, k};
    assign EXP_O    = d0[28:27];
    assign Mantissa = {zero_check, d0[26:0]};
endmodule

module posit_decoder_32_2_hier (
    input  wire [31:0] posit_in,
    output wire        S,
    output wire [5:0]  reg_O,
    output wire [1:0]  EXP_O,
    output wire        inf,
    output wire [27:0] Mantissa
);
    wire        sign = posit_in[31];
    wire        rc   = posit_in[30];
    wire [29:0] d5   = posit_in[29:0];
    wire [29:0] d4, d3, d2, d1, d0;
    wire        a4, a3, a2, a1, a0;
    wire        c4, c3, c2, c1, c0;

    // Stage 4: 16-bit window, shift 16
    pd_andor #(.W(16)) u_ao4 (.win(d5[29:14]), .rc(rc), .d_and(a4));
    pd_cmp             u_bd4 (.d_and(a4), .rc(rc), .hit(c4));
    pd_shift #(.S(16)) u_sh4 (.din(d5), .sel(c4), .dout(d4));
    // Stage 3: 9-bit window, shift 8
    pd_andor #(.W(9))  u_ao3 (.win(d4[29:21]), .rc(rc), .d_and(a3));
    pd_cmp             u_bd3 (.d_and(a3), .rc(rc), .hit(c3));
    pd_shift #(.S(8))  u_sh3 (.din(d4), .sel(c3), .dout(d3));
    // Stage 2: 5-bit window, shift 4
    pd_andor #(.W(5))  u_ao2 (.win(d3[29:25]), .rc(rc), .d_and(a2));
    pd_cmp             u_bd2 (.d_and(a2), .rc(rc), .hit(c2));
    pd_shift #(.S(4))  u_sh2 (.din(d3), .sel(c2), .dout(d2));
    // Stage 1: 3-bit window, shift 2
    pd_andor #(.W(3))  u_ao1 (.win(d2[29:27]), .rc(rc), .d_and(a1));
    pd_cmp             u_bd1 (.d_and(a1), .rc(rc), .hit(c1));
    pd_shift #(.S(2))  u_sh1 (.din(d2), .sel(c1), .dout(d1));
    // Stage 0: 1-bit window, shift 1
    assign a0 = d1[29];
    pd_cmp             u_bd0 (.d_and(a0), .rc(rc), .hit(c0));
    pd_shift #(.S(1))  u_sh0 (.din(d1), .sel(c0), .dout(d0));

    assign S = sign;
    pd_outenc u_out (.sign(sign), .rc(rc), .k({c4, c3, c2, c1, c0}), .hit4(c4), .d0(d0[28:0]),
                     .reg_O(reg_O), .EXP_O(EXP_O), .inf(inf), .Mantissa(Mantissa));
endmodule

`default_nettype wire
