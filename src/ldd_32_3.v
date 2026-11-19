// Wrapper with a unique top name; it adds no logic.
module ldd_32_3 (
    input  wire [31:0]     in,
    output wire            sign,
    output wire [5:0]      regi,
    output wire [2:0] expo,
    output wire [25:0] frac,
    output wire            allone,
    output wire            allzero
);
    decoder u_dec (.sign(sign), .regi(regi), .expo(expo), .frac(frac), .allone(allone), .allzero(allzero), .in(in));
endmodule
