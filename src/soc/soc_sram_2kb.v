// 2 KB data/stack RAM for PicoSoC built from four GF180MCU foundry SRAM
// macros (gf180mcu_fd_ip_sram__sram512x8m8wm1), one per byte lane.
// Drop-in replacement for picosoc_mem (selected with PICOSOC_MEM): 512 words,
// synchronous read with one cycle of latency, byte write strobes.
//
// SRAM control pins are active low: CEN (enable), GWEN (write), WEN (bit mask).
// CEN is held high during reset (required by the macro) and asserted only on
// RAM accesses. Supply pins are tied by the flow (PDN_MACRO_CONNECTIONS).

`timescale 1ns/1ps
`default_nettype none

module soc_sram_2kb #(
    parameter integer WORDS = 512
) (
    input  wire        clk,
    input  wire        resetn,
    input  wire        en,       // RAM access this cycle
    input  wire [3:0]  wen,
    input  wire [21:0] addr,
    input  wire [31:0] wdata,
    output wire [31:0] rdata
);
    wire cen = ~(resetn & en);

    // Signals into the macros. In simulation only, a 1 ns delay stands in for
    // the hold margin that real wires and buffers provide; the foundry model
    // samples address and data shortly after the clock edge.
    wire        cen_i;
    wire [3:0]  wen_i;
    wire [8:0]  a_i;
    wire [31:0] d_i;
`ifdef SYNTHESIS
    assign cen_i = cen;
    assign wen_i = wen;
    assign a_i   = addr[8:0];
    assign d_i   = wdata;
`else
    assign #1 cen_i = cen;
    assign #1 wen_i = wen;
    assign #1 a_i   = addr[8:0];
    assign #1 d_i   = wdata;
`endif

    gf180mcu_fd_ip_sram__sram512x8m8wm1 sram0 (
        .CLK (clk), .CEN (cen_i), .GWEN (~wen_i[0]), .WEN ({8{~wen_i[0]}}),
        .A (a_i), .D (d_i[7:0]), .Q (rdata[7:0])
    );
    gf180mcu_fd_ip_sram__sram512x8m8wm1 sram1 (
        .CLK (clk), .CEN (cen_i), .GWEN (~wen_i[1]), .WEN ({8{~wen_i[1]}}),
        .A (a_i), .D (d_i[15:8]), .Q (rdata[15:8])
    );
    gf180mcu_fd_ip_sram__sram512x8m8wm1 sram2 (
        .CLK (clk), .CEN (cen_i), .GWEN (~wen_i[2]), .WEN ({8{~wen_i[2]}}),
        .A (a_i), .D (d_i[23:16]), .Q (rdata[23:16])
    );
    gf180mcu_fd_ip_sram__sram512x8m8wm1 sram3 (
        .CLK (clk), .CEN (cen_i), .GWEN (~wen_i[3]), .WEN ({8{~wen_i[3]}}),
        .A (a_i), .D (d_i[31:24]), .Q (rdata[31:24])
    );
endmodule

`default_nettype wire
