// dsp_mac: 16x16 signed multiply-accumulate unit with a 40-bit accumulator.
//
// Register map (word index = addr):
//   0  A      rw  signed 16-bit operand
//   1  MAC    w   acc <= acc + A * wdata[15:0];  r: last B operand
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
    reg signed [15:0] a_q, b_q;
    reg signed [31:0] prod_q;
    reg signed [39:0] acc_q;
    reg        [15:0] count_q;

    wire signed [15:0] b_in = wdata[15:0];
    wire signed [31:0] product = a_q * b_in;          // 16x16 multiplier array
    wire signed [39:0] acc_sum = acc_q + {{8{product[31]}}, product};  // 40-bit accumulator adder

    always @(posedge clk) begin
        if (!resetn) begin
            a_q <= 0; b_q <= 0; prod_q <= 0; acc_q <= 0; count_q <= 0;
        end else if (wr) begin
            case (addr)
                4'd0: a_q <= wdata[15:0];
                4'd1: begin b_q <= b_in; prod_q <= product; acc_q <= acc_sum; count_q <= count_q + 1'b1; end
                4'd2: begin acc_q <= 0; count_q <= 0; end
                4'd5: begin b_q <= b_in; prod_q <= product; acc_q <= {{8{product[31]}}, product}; end
                default: ;
            endcase
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
