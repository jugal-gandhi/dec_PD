// Chip-level RTL simulation of soc_chip_top: pad models, four SRAM macro
// models, PicoRV32 executing firmware from an SPI flash model.
// Pass criterion: firmware writes 0xA5A5 to GPIO_OUT (pads gpio_PAD[15:0]).
`timescale 1ns/1ps

module tb_soc;
`ifndef CLK_HALF
`define CLK_HALF 20                        // 25 MHz
`endif
    reg clk = 1'b0;
    always #(`CLK_HALF) clk = ~clk;

    reg rst_n = 1'b0;
    initial begin
        repeat (20) @(posedge clk);
        rst_n = 1'b1;
    end

    wire clk_p   = clk;
    wire rst_p   = rst_n;
    wire rx_p    = 1'b1;
    wire irq5_p  = 1'b0;
    wire irq6_p  = 1'b0;
    wire ser_tx, flash_csb, flash_clk;
    wire [3:0]  fio;
    wire [15:0] gpio;

    pullup (fio[0]); pullup (fio[1]); pullup (fio[2]); pullup (fio[3]);

    soc_chip_top dut (
        .clk_PAD       (clk_p),
        .rst_n_PAD     (rst_p),
        .ser_tx_PAD    (ser_tx),
        .ser_rx_PAD    (rx_p),
        .irq5_PAD      (irq5_p),
        .irq6_PAD      (irq6_p),
        .flash_csb_PAD (flash_csb),
        .flash_clk_PAD (flash_clk),
        .flash_io_PAD  (fio),
        .gpio_PAD      (gpio)
    );

    spiflash flash (
        .csb (flash_csb), .clk (flash_clk),
        .io0 (fio[0]), .io1 (fio[1]), .io2 (fio[2]), .io3 (fio[3])
    );

    // UART receiver (firmware sets divider 104)
    localparam ser_half_period = 53;
    reg [7:0] ser_byte;
    reg [8*16-1:0] ser_text = 0;
    always begin
        @(negedge ser_tx);
        repeat (ser_half_period) @(posedge clk);
        repeat (8) begin
            repeat (2 * ser_half_period) @(posedge clk);
            ser_byte = {ser_tx, ser_byte[7:1]};
        end
        repeat (2 * ser_half_period) @(posedge clk);
        ser_text = {ser_text[8*15-1:0], ser_byte};
        $display("[%0t] UART: '%c'", $time, ser_byte);
    end

    reg [15:0] last_gpio = 16'hxxxx;
    integer cycles = 0;
    always @(posedge clk) begin
        cycles <= cycles + 1;
        if (gpio !== last_gpio) begin
            last_gpio <= gpio;
            $display("[%0t] cycle %0d GPIO_OUT = %h", $time, cycles, gpio);
        end
        if (gpio === 16'hA5A5) begin
            repeat (6000) @(posedge clk);   // let the UART message finish
            $display("SOC_SIM PASS: self-test passed after %0d cycles", cycles);
            $finish;
        end
        if (gpio[15:12] === 4'hE) begin
            $display("SOC_SIM FAIL: %0d errors reported by firmware", gpio[11:0]);
            $finish;
        end
        if (cycles > 4000000) begin
            $display("SOC_SIM FAIL: timeout, GPIO_OUT = %h", gpio);
            $finish;
        end
    end
endmodule
