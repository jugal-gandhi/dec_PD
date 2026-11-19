// Compare an LDD comparison design with the reference vectors from cmp_golden.py.
`timescale 1ns/1ps
module tb_cmp;
    localparam FS = 29 - `ES;
    reg  [31:0] in;
    wire sign, allone, allzero;
    wire [5:0] regi;
    wire [`ES-1:0] expo;
    wire [FS-1:0] frac;
    `TOP dut (.in(in), .sign(sign), .regi(regi), .expo(expo), .frac(frac), .allone(allone), .allzero(allzero));
    reg [31:0] vin  [0:`NV-1];
    reg [37:0] vexp [0:`NV-1];
    integer i, err;
    initial begin
        $readmemh(`VIN, vin);
        $readmemh(`VEXP, vexp);
        err = 0;
        for (i = 0; i < `NV; i = i + 1) begin
            in = vin[i];
            #1;
            if ({sign, regi, expo, frac, allone, allzero} !== vexp[i]) begin
                err = err + 1;
                if (err <= 20) $display("MISMATCH in=%h got=%h exp=%h", in, {sign, regi, expo, frac, allone, allzero}, vexp[i]);
            end
        end
        $display("RESULT tests=%0d errors=%0d", `NV, err);
        $finish;
    end
endmodule
