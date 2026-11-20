// Posit<32,2> decoder of PERCIVAL (github.com/artecs-group/PERCIVAL, commit 16bbbd5e),
// transcribed line by line from core/pau/pau_add.vhd: entities PositFastDecoder_32_2_F50_uid4
// (Raul Murillo, 2021) and Normalizer_ZO_30_30_30_F50_uid6 (FloPoCo). The unused clock port
// is dropped. PERCIVAL is distributed under the Solderpad Hardware License v0.51.
// Used here only as a comparison baseline.

`default_nettype none

module percival_32_2 (
    input  wire [31:0] X,
    output wire        Sign,
    output wire [7:0]  SF,     // scaling factor {k[5:0], exp[1:0]}
    output wire [26:0] Frac,
    output wire        NZN     // '0' for zero and NaR
);
    wire        sgn = X[31];
    wire        rc  = X[30];
    // Normalizer_ZO_30_30_30: count and shift out the leading run of rc
    wire [29:0] level5 = X[29:0];
    wire        count4 = (level5[29:14] == {16{rc}});
    wire [29:0] level4 = count4 ? {level5[13:0], 16'b0} : level5;
    wire        count3 = (level4[29:22] == {8{rc}});
    wire [29:0] level3 = count3 ? {level4[21:0], 8'b0} : level4;
    wire        count2 = (level3[29:26] == {4{rc}});
    wire [29:0] level2 = count2 ? {level3[25:0], 4'b0} : level3;
    wire        count1 = (level2[29:28] == {2{rc}});
    wire [29:0] level1 = count1 ? {level2[27:0], 2'b0} : level2;
    wire        count0 = (level1[29] == rc);
    wire [29:0] level0 = count0 ? {level1[28:0], 1'b0} : level1;
    wire [4:0]  regLength = {count4, count3, count2, count1, count0};
    // scaling factor: regime and exponent
    wire [5:0]  k   = (rc != sgn) ? {1'b0, regLength} : {1'b1, ~regLength};
    wire [1:0]  exp = level0[28:27] ^ {2{sgn}};
    assign Sign = sgn;
    assign SF   = {k, exp};
    assign Frac = level0[26:0];
    assign NZN  = (X[30:0] != 31'b0);
endmodule

`default_nettype wire
