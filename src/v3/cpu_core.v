// cpu_core: PicoRV32 (RV32IMC) hardened as its own macro.
// Native memory interface only; PCPI, trace and look-ahead ports stay inside.
`default_nettype none

module cpu_core (
`ifdef USE_POWER_PINS
    inout  wire        VDD,
    inout  wire        VSS,
`endif
    input  wire        clk,
    input  wire        resetn,
    output wire        mem_valid,
    output wire        mem_instr,
    input  wire        mem_ready,
    output wire [31:0] mem_addr,
    output wire [31:0] mem_wdata,
    output wire [3:0]  mem_wstrb,
    input  wire [31:0] mem_rdata,
    input  wire [7:0]  irq
);
    picorv32 #(
        .STACKADDR       (32'h0000_0800),
        .PROGADDR_RESET  (32'h0010_0000),
        .PROGADDR_IRQ    (32'h0010_0000),
        .BARREL_SHIFTER  (1),
        .COMPRESSED_ISA  (1),
        .ENABLE_COUNTERS (1),
        .ENABLE_MUL      (1),
        .ENABLE_DIV      (1),
        .ENABLE_IRQ      (1),
        .ENABLE_IRQ_QREGS(0)
    ) cpu (
        .clk       (clk),
        .resetn    (resetn),
        .mem_valid (mem_valid),
        .mem_instr (mem_instr),
        .mem_ready (mem_ready),
        .mem_addr  (mem_addr),
        .mem_wdata (mem_wdata),
        .mem_wstrb (mem_wstrb),
        .mem_rdata (mem_rdata),
        .irq       ({24'b0, irq})
    );
endmodule

`default_nettype wire
