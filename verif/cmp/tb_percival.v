// Check the PERCIVAL decoder transcription against cmp_golden.py (mode percival).
`timescale 1ns/1ps
module tb_percival;
    reg  [31:0] X;
    wire Sign, NZN;
    wire [7:0] SF;
    wire [26:0] Frac;
    percival_32_2 dut (.X(X), .Sign(Sign), .SF(SF), .Frac(Frac), .NZN(NZN));
    reg [31:0] vin  [0:`NV-1];
    reg [36:0] vexp [0:`NV-1];
    integer i, err;
    initial begin
        $readmemh(`VIN, vin);
        $readmemh(`VEXP, vexp);
        err = 0;
        for (i = 0; i < `NV; i = i + 1) begin
            X = vin[i];
            #1;
            if ({Sign, SF, Frac, NZN} !== vexp[i]) begin
                err = err + 1;
                if (err <= 20) $display("MISMATCH X=%h got=%h exp=%h", X, {Sign, SF, Frac, NZN}, vexp[i]);
            end
        end
        $display("RESULT tests=%0d errors=%0d", `NV, err);
        $finish;
    end
endmodule
