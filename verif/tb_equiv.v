// Random and directed simulation: VHDL (via GHDL netlist) vs Verilog RTL.
`timescale 1ns/1ps
module tb_equiv;
    reg  [31:0] x;
    wire        s_g, s_r, inf_g, inf_r;
    wire [5:0]  reg_g, reg_r;
    wire [1:0]  exp_g, exp_r;
    wire [27:0] man_g, man_r;

    gold_wrap          g (.posit_in(x), .S(s_g), .reg_O(reg_g), .EXP_O(exp_g), .inf(inf_g), .Mantissa(man_g));
    posit_decoder_32_2 r (.posit_in(x), .S(s_r), .reg_O(reg_r), .EXP_O(exp_r), .inf(inf_r), .Mantissa(man_r));

    integer i, run, errors, total, seed;
    reg [31:0] tail;

    task check;
        begin
            #1;
            total = total + 1;
            if ({s_g, reg_g, exp_g, inf_g, man_g} !== {s_r, reg_r, exp_r, inf_r, man_r}) begin
                errors = errors + 1;
                if (errors < 10)
                    $display("MISMATCH x=%h gold=%b rtl=%b", x,
                             {s_g, reg_g, exp_g, inf_g, man_g}, {s_r, reg_r, exp_r, inf_r, man_r});
            end
        end
    endtask

    initial begin
        errors = 0; total = 0; seed = 2026;
        // Directed: every sign, first regime bit and regime run length.
        for (i = 0; i < 4; i = i + 1)
            for (run = 0; run <= 30; run = run + 1) begin
                tail = $random(seed);
                x[31] = i[1];
                x[30] = i[0];
                x[29:0] = i[0] ? ~(30'h3FFFFFFF >> run) : (30'h3FFFFFFF >> run);
                x[29:0] = x[29:0] ^ (tail[29:0] & (30'h3FFFFFFF >> (run + 1)));
                check;
            end
        // Corner values.
        x = 32'h00000000; check;  x = 32'h80000000; check;
        x = 32'h7FFFFFFF; check;  x = 32'hFFFFFFFF; check;
        x = 32'h40000000; check;  x = 32'hC0000000; check;
        // Random.
        for (i = 0; i < 500000; i = i + 1) begin
            x = $random(seed);
            check;
        end
        if (errors == 0) $display("SIM_EQUIV PASS: %0d vectors, 0 mismatches", total);
        else             $display("SIM_EQUIV FAIL: %0d mismatches in %0d vectors", errors, total);
        $finish;
    end
endmodule
