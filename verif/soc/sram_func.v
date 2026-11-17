// Functional model of gf180mcu_fd_ip_sram__sram512x8m8wm1 from its datasheet
// truth table (no timing): rising-edge synchronous, active-low CEN/GWEN/WEN,
// Q holds its value on standby and write cycles.
`timescale 1ns/1ps
module gf180mcu_fd_ip_sram__sram512x8m8wm1 (
    input  wire       CLK,
    input  wire       CEN,
    input  wire       GWEN,
    input  wire [7:0] WEN,
    input  wire [8:0] A,
    input  wire [7:0] D,
    output reg  [7:0] Q,
    inout  wire       VDD,
    inout  wire       VSS
);
    reg [7:0] mem [0:511];
    integer i;
    always @(posedge CLK) begin
        if (!CEN) begin
            if (!GWEN) begin
                for (i = 0; i < 8; i = i + 1)
                    if (!WEN[i]) mem[A][i] <= D[i];
            end else begin
                Q <= mem[A];
            end
        end
    end
endmodule
