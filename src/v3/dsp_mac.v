// dsp_mac: 16x16 signed multiply-accumulate unit with a 40-bit accumulator.
//
// Register map (word index = addr):
//   0  A      rw  signed 16-bit operand
//   1  MAC    w   acc <= acc + A * wdata[15:0];  r: last B operand
//                 (pipelined: acc updates two cycles after the write)
//   2  CLEAR  w   acc <= 0, count <= 0;          r: acc[31:0]
//   3  ACCHI  r   sign-extended acc[39:32]
//   4  COUNT  r   number of MAC operations since CLEAR
//   5  MUL    w   acc <= A * wdata[15:0] (no accumulate); r: product of last MUL/MAC
`default_nettype none

module dsp_mac (
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
    reg signed [15:0] a_q, b_q, a_s;
    reg signed [31:0] prod_q;
    reg signed [39:0] acc_q;
    reg        [15:0] count_q;
    // Two-stage pipeline: stage 1 multiplies the captured operands, stage 2
    // accumulates. A new MAC/MUL can start every cycle; results land in acc
    // two cycles after the write, well before the CPU can read them back.
    reg        v1, v2;      // stage valid flags
    reg        m1, m2;      // stage holds a MUL (load) rather than a MAC

    wire signed [31:0] product = a_s * b_q;                              // 16x16 multiplier array
    wire signed [39:0] prod_x  = {{8{prod_q[31]}}, prod_q};
    wire signed [39:0] acc_sum = acc_q + prod_x;                         // 40-bit accumulator adder

    always @(posedge clk) begin
        if (!resetn) begin
            a_q <= 0; b_q <= 0; a_s <= 0; prod_q <= 0; acc_q <= 0; count_q <= 0;
            v1 <= 1'b0; v2 <= 1'b0; m1 <= 1'b0; m2 <= 1'b0;
        end else begin
            // Stage 0: capture operands on a MAC or MUL write
            v1 <= wr && (addr == 4'd1 || addr == 4'd5);
            m1 <= (addr == 4'd5);
            if (wr && (addr == 4'd1 || addr == 4'd5)) begin
                a_s <= a_q;
                b_q <= wdata[15:0];
            end
            // Stage 1: multiply
            v2 <= v1;
            m2 <= m1;
            if (v1)
                prod_q <= product;
            // Stage 2: accumulate (or load for MUL)
            if (wr && addr == 4'd2) begin
                acc_q   <= 0;
                count_q <= 0;
            end else if (v2) begin
                acc_q <= m2 ? prod_x : acc_sum;
                if (!m2)
                    count_q <= count_q + 1'b1;
            end
            if (wr && addr == 4'd0)
                a_q <= wdata[15:0];
        end
    end

    always @(*) begin
        case (addr)
            4'd0: rdata = {{16{a_q[15]}}, a_q};
            4'd1: rdata = {{16{b_q[15]}}, b_q};
            4'd2: rdata = acc_q[31:0];
            4'd3: rdata = {{24{acc_q[39]}}, acc_q[39:32]};
            4'd4: rdata = {16'b0, count_q};
            4'd5: rdata = prod_q;
            default: rdata = 32'h0;
        endcase
    end
endmodule

`default_nettype wire
