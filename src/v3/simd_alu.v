// simd_alu: 4-lane 8-bit SIMD ALU with bit-manipulation units.
//
// Register map (word index = addr):
//   0  A       rw  operand A (4 x 8-bit lanes)
//   1  B       rw  operand B
//   2  OP      w   compute op on A, B and latch RESULT;  r: last op
//   3  RESULT  r
// Ops: 0 ADD8  1 SUB8  2 ADDSAT8 (unsigned)  3 ABSDIFF8  4 MIN8U  5 MAX8U
//      6 POPCNT32(A)  7 CLZ32(A)  8 SAD8 (sum of |A_i - B_i|)
`default_nettype none

// One 8-bit lane: adder/subtractor, saturation and comparison.
module simd_lane (
    input  wire [7:0] a,
    input  wire [7:0] b,
    output wire [7:0] add,
    output wire [7:0] sub,
    output wire [7:0] addsat,
    output wire [7:0] absdiff,
    output wire [7:0] minv,
    output wire [7:0] maxv
);
    wire [8:0] sum  = {1'b0, a} + {1'b0, b};
    wire [8:0] diff = {1'b0, a} - {1'b0, b};
    wire       a_lt = diff[8];
    assign add     = sum[7:0];
    assign sub     = diff[7:0];
    assign addsat  = sum[8] ? 8'hFF : sum[7:0];
    assign absdiff = a_lt ? (b - a) : diff[7:0];
    assign minv    = a_lt ? a : b;
    assign maxv    = a_lt ? b : a;
endmodule

module simd_popcount (input wire [31:0] x, output wire [5:0] count);
    integer i;
    reg [5:0] c;
    always @(*) begin
        c = 6'd0;
        for (i = 0; i < 32; i = i + 1) c = c + x[i];
    end
    assign count = c;
endmodule

module simd_clz (input wire [31:0] x, output reg [5:0] count);
    integer i;
    reg found;
    always @(*) begin
        count = 6'd32;
        found = 1'b0;
        for (i = 31; i >= 0; i = i - 1)
            if (!found && x[i]) begin
                count = 6'd31 - i;
                found = 1'b1;
            end
    end
endmodule

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
    output reg  [31:0] rdata
);
    reg [31:0] a_q, b_q, res_q;
    reg [3:0]  op_q;

    wire [7:0] add0, add1, add2, add3, sub0, sub1, sub2, sub3;
    wire [7:0] sat0, sat1, sat2, sat3, ad0, ad1, ad2, ad3;
    wire [7:0] mn0, mn1, mn2, mn3, mx0, mx1, mx2, mx3;

    simd_lane lane0 (.a(a_q[7:0]),   .b(b_q[7:0]),   .add(add0), .sub(sub0), .addsat(sat0), .absdiff(ad0), .minv(mn0), .maxv(mx0));
    simd_lane lane1 (.a(a_q[15:8]),  .b(b_q[15:8]),  .add(add1), .sub(sub1), .addsat(sat1), .absdiff(ad1), .minv(mn1), .maxv(mx1));
    simd_lane lane2 (.a(a_q[23:16]), .b(b_q[23:16]), .add(add2), .sub(sub2), .addsat(sat2), .absdiff(ad2), .minv(mn2), .maxv(mx2));
    simd_lane lane3 (.a(a_q[31:24]), .b(b_q[31:24]), .add(add3), .sub(sub3), .addsat(sat3), .absdiff(ad3), .minv(mn3), .maxv(mx3));

    wire [5:0] popcnt, clz;
    simd_popcount u_popcount (.x(a_q), .count(popcnt));
    simd_clz      u_clz      (.x(a_q), .count(clz));

    wire [9:0] sad = {2'b0, ad0} + {2'b0, ad1} + {2'b0, ad2} + {2'b0, ad3};   // SAD adder tree

    reg [31:0] result;
    always @(*) begin
        case (wdata[3:0])
            4'd0: result = {add3, add2, add1, add0};
            4'd1: result = {sub3, sub2, sub1, sub0};
            4'd2: result = {sat3, sat2, sat1, sat0};
            4'd3: result = {ad3, ad2, ad1, ad0};
            4'd4: result = {mn3, mn2, mn1, mn0};
            4'd5: result = {mx3, mx2, mx1, mx0};
            4'd6: result = {26'b0, popcnt};
            4'd7: result = {26'b0, clz};
            4'd8: result = {22'b0, sad};
            default: result = 32'h0;
        endcase
    end

    always @(posedge clk) begin
        if (!resetn) begin
            a_q <= 0; b_q <= 0; res_q <= 0; op_q <= 0;
        end else if (wr) begin
            case (addr)
                4'd0: a_q <= wdata;
                4'd1: b_q <= wdata;
                4'd2: begin op_q <= wdata[3:0]; res_q <= result; end
                default: ;
            endcase
        end
    end

    always @(*) begin
        case (addr)
            4'd0: rdata = a_q;
            4'd1: rdata = b_q;
            4'd2: rdata = {28'b0, op_q};
            4'd3: rdata = res_q;
            default: rdata = 32'h0;
        endcase
    end
endmodule

`default_nettype wire
