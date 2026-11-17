// 2 KB data/stack RAM for PicoSoC built from four GF180MCU foundry SRAM
// macros (gf180mcu_fd_ip_sram__sram512x8m8wm1), one per byte lane.
// Drop-in replacement for picosoc_mem (selected with PICOSOC_MEM): 512 words,
// synchronous read with one cycle of latency, byte write strobes.
//
// SRAM control pins are active low: CEN (enable), GWEN (write), WEN (bit mask).
// CEN is held high during reset (required by the macro) and asserted only on
// RAM accesses. Supply pins are tied by the flow (PDN_MACRO_CONNECTIONS).

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

    gf180mcu_fd_ip_sram__sram512x8m8wm1 sram0 (
        .CLK (clk), .CEN (cen), .GWEN (~wen[0]), .WEN ({8{~wen[0]}}),
        .A (addr[8:0]), .D (wdata[7:0]), .Q (rdata[7:0])
    );
    gf180mcu_fd_ip_sram__sram512x8m8wm1 sram1 (
        .CLK (clk), .CEN (cen), .GWEN (~wen[1]), .WEN ({8{~wen[1]}}),
        .A (addr[8:0]), .D (wdata[15:8]), .Q (rdata[15:8])
    );
    gf180mcu_fd_ip_sram__sram512x8m8wm1 sram2 (
        .CLK (clk), .CEN (cen), .GWEN (~wen[2]), .WEN ({8{~wen[2]}}),
        .A (addr[8:0]), .D (wdata[23:16]), .Q (rdata[23:16])
    );
    gf180mcu_fd_ip_sram__sram512x8m8wm1 sram3 (
        .CLK (clk), .CEN (cen), .GWEN (~wen[3]), .WEN ({8{~wen[3]}}),
        .A (addr[8:0]), .D (wdata[31:24]), .Q (rdata[31:24])
    );
endmodule

`default_nettype wire
