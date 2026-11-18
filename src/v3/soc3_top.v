// soc3_top: multi-block RISC-V SoC (v3).
//
// Hard macros: cpu_core (PicoRV32), spimemio (SPI flash XIP), simpleuart,
// posit_decoder_32_2, dsp_mac x2, simd_alu, and 8 foundry SRAMs (4 KB).
// Bus glue follows PicoSoC (Claire Xenia Wolf, ISC license).
//
// Memory map
//   0x0000_0000 - 0x0000_07FF  main RAM, 2 KB (stack, data)
//   0x0001_0000 - 0x0001_07FF  scratchpad RAM, 2 KB
//   0x0010_0000 - 0x01FF_FFFF  SPI flash, execute in place
//   0x0200_0000 / 04 / 08      flash config / UART divider / UART data
//   0x0300_0000 / 04 / 08      GPIO_OUT / GPIO_OE / GPIO_IN
//   0x0300_0010 / 14 / 18      POSIT_IN / POSIT_FLD / POSIT_MANT
//   0x0400_0000 + 4*n          DSP0 register n   (see dsp_mac.v)
//   0x0400_0100 + 4*n          DSP1 register n
//   0x0500_0000 + 4*n          SIMD ALU register n (see simd_alu.v)
`default_nettype none

module soc3_top (
`ifdef USE_POWER_PINS
    inout  wire        VDD,
    inout  wire        VSS,
`endif
    input  wire        clk,
    input  wire        resetn,
    output wire        ser_tx,
    input  wire        ser_rx,
    input  wire        irq_5,
    input  wire        irq_6,
    output wire        flash_csb,
    output wire        flash_clk,
    output wire [3:0]  flash_io_oe,
    output wire [3:0]  flash_io_do,
    input  wire [3:0]  flash_io_di,
    output wire [15:0] gpio_out,
    output wire [15:0] gpio_oe,
    input  wire [15:0] gpio_in
);
    // ---------------- reset synchroniser ----------------
    reg [1:0] rst_sync;
    always @(posedge clk or negedge resetn)
        if (!resetn) rst_sync <= 2'b00;
        else         rst_sync <= {rst_sync[0], 1'b1};
    wire rst_n = rst_sync[1];

    // ---------------- CPU ----------------
    wire        mem_valid, mem_instr;
    wire        mem_ready;
    wire [31:0] mem_addr, mem_wdata, mem_rdata;
    wire [3:0]  mem_wstrb;

    cpu_core u_cpu (
`ifdef USE_POWER_PINS
        .VDD (VDD), .VSS (VSS),
`endif
        .clk (clk), .resetn (rst_n),
        .mem_valid (mem_valid), .mem_instr (mem_instr), .mem_ready (mem_ready),
        .mem_addr (mem_addr), .mem_wdata (mem_wdata), .mem_wstrb (mem_wstrb),
        .mem_rdata (mem_rdata),
        .irq ({1'b0, irq_6, irq_5, 5'b0})
    );

    // ---------------- address decode ----------------
    wire ram_hit    = (mem_addr[31:11] == 21'h0);                 // 0x0000_0000
    wire scr_hit    = (mem_addr[31:11] == 21'h20);                // 0x0001_0000
    wire flash_hit  = (mem_addr >= 32'h0010_0000) && (mem_addr < 32'h0200_0000);
    wire cfg_sel    = mem_valid && (mem_addr == 32'h0200_0000);
    wire div_sel    = mem_valid && (mem_addr == 32'h0200_0004);
    wire dat_sel    = mem_valid && (mem_addr == 32'h0200_0008);
    wire io_hit     = (mem_addr[31:24] == 8'h03) || (mem_addr[31:24] == 8'h04) || (mem_addr[31:24] == 8'h05);

    // ---------------- RAM banks ----------------
    reg  ram_ready, scr_ready;
    wire [31:0] ram_rdata, scr_rdata;
    wire ram_sel = mem_valid && !mem_ready && ram_hit;
    wire scr_sel = mem_valid && !mem_ready && scr_hit;

    always @(posedge clk) begin
        ram_ready <= rst_n && ram_sel;
        scr_ready <= rst_n && scr_sel;
    end

    soc_sram_2kb u_ram (
        .clk (clk), .resetn (rst_n), .en (ram_sel), .wen (ram_sel ? mem_wstrb : 4'b0),
        .addr (mem_addr[23:2]), .wdata (mem_wdata), .rdata (ram_rdata)
    );
    soc_sram_2kb u_scratch (
        .clk (clk), .resetn (rst_n), .en (scr_sel), .wen (scr_sel ? mem_wstrb : 4'b0),
        .addr (mem_addr[23:2]), .wdata (mem_wdata), .rdata (scr_rdata)
    );

    // ---------------- SPI flash controller (macro) ----------------
    wire        spimem_ready;
    wire [31:0] spimem_rdata, cfg_do;
    spimemio u_spi (
`ifdef USE_POWER_PINS
        .VDD (VDD), .VSS (VSS),
`endif
        .clk (clk), .resetn (rst_n),
        .valid (mem_valid && flash_hit), .ready (spimem_ready),
        .addr (mem_addr[23:0]), .rdata (spimem_rdata),
        .flash_csb (flash_csb), .flash_clk (flash_clk),
        .flash_io0_oe (flash_io_oe[0]), .flash_io1_oe (flash_io_oe[1]),
        .flash_io2_oe (flash_io_oe[2]), .flash_io3_oe (flash_io_oe[3]),
        .flash_io0_do (flash_io_do[0]), .flash_io1_do (flash_io_do[1]),
        .flash_io2_do (flash_io_do[2]), .flash_io3_do (flash_io_do[3]),
        .flash_io0_di (flash_io_di[0]), .flash_io1_di (flash_io_di[1]),
        .flash_io2_di (flash_io_di[2]), .flash_io3_di (flash_io_di[3]),
        .cfgreg_we (cfg_sel ? mem_wstrb : 4'b0), .cfgreg_di (mem_wdata), .cfgreg_do (cfg_do)
    );

    // ---------------- UART (macro) ----------------
    wire [31:0] div_do, dat_do;
    wire        dat_wait;
    simpleuart u_uart (
`ifdef USE_POWER_PINS
        .VDD (VDD), .VSS (VSS),
`endif
        .clk (clk), .resetn (rst_n),
        .ser_tx (ser_tx), .ser_rx (ser_rx),
        .reg_div_we (div_sel ? mem_wstrb : 4'b0), .reg_div_di (mem_wdata), .reg_div_do (div_do),
        .reg_dat_we (dat_sel ? mem_wstrb[0] : 1'b0), .reg_dat_re (dat_sel && !mem_wstrb),
        .reg_dat_di (mem_wdata), .reg_dat_do (dat_do), .reg_dat_wait (dat_wait)
    );

    // ---------------- accelerators (macros) ----------------
    reg  [31:0] posit_in;
    wire        p_sign, p_inf;
    wire [5:0]  p_reg;
    wire [1:0]  p_exp;
    wire [27:0] p_mant;
    posit_decoder_32_2 u_posit (
`ifdef USE_POWER_PINS
        .VDD (VDD), .VSS (VSS),
`endif
        .posit_in (posit_in), .S (p_sign), .reg_O (p_reg), .EXP_O (p_exp),
        .inf (p_inf), .Mantissa (p_mant)
    );

    reg         io_ready;
    reg  [31:0] io_rdata;
    wire        io_sel = mem_valid && !io_ready && io_hit;
    wire        io_wr  = io_sel && (mem_wstrb != 4'b0);

    wire        dsp0_hit = (mem_addr[31:24] == 8'h04) && !mem_addr[8];
    wire        dsp1_hit = (mem_addr[31:24] == 8'h04) &&  mem_addr[8];
    wire        simd_hit = (mem_addr[31:24] == 8'h05);
    wire [31:0] dsp0_rdata, dsp1_rdata, simd_rdata;

    dsp_mac u_dsp0 (
`ifdef USE_POWER_PINS
        .VDD (VDD), .VSS (VSS),
`endif
        .clk (clk), .resetn (rst_n), .wr (io_wr && dsp0_hit),
        .addr (mem_addr[5:2]), .wdata (mem_wdata), .rdata (dsp0_rdata)
    );
    dsp_mac u_dsp1 (
`ifdef USE_POWER_PINS
        .VDD (VDD), .VSS (VSS),
`endif
        .clk (clk), .resetn (rst_n), .wr (io_wr && dsp1_hit),
        .addr (mem_addr[5:2]), .wdata (mem_wdata), .rdata (dsp1_rdata)
    );
    simd_alu u_simd (
`ifdef USE_POWER_PINS
        .VDD (VDD), .VSS (VSS),
`endif
        .clk (clk), .resetn (rst_n), .wr (io_wr && simd_hit),
        .addr (mem_addr[5:2]), .wdata (mem_wdata), .rdata (simd_rdata)
    );

    // ---------------- GPIO, posit registers, I/O read mux ----------------
    reg [15:0] gpio_out_r, gpio_oe_r, gpio_in_r;
    assign gpio_out = gpio_out_r;
    assign gpio_oe  = gpio_oe_r;
    always @(posedge clk) gpio_in_r <= gpio_in;

    always @(posedge clk) begin
        if (!rst_n) begin
            io_ready   <= 1'b0;
            io_rdata   <= 32'h0;
            gpio_out_r <= 16'h0;
            gpio_oe_r  <= 16'h0;
            posit_in   <= 32'h0;
        end else begin
            io_ready <= 1'b0;
            if (io_sel) begin
                io_ready <= 1'b1;
                if (mem_addr[31:24] == 8'h03) begin
                    case (mem_addr[7:0])
                        8'h00: begin
                            io_rdata <= {16'h0, gpio_out_r};
                            if (mem_wstrb[0]) gpio_out_r[7:0]  <= mem_wdata[7:0];
                            if (mem_wstrb[1]) gpio_out_r[15:8] <= mem_wdata[15:8];
                        end
                        8'h04: begin
                            io_rdata <= {16'h0, gpio_oe_r};
                            if (mem_wstrb[0]) gpio_oe_r[7:0]  <= mem_wdata[7:0];
                            if (mem_wstrb[1]) gpio_oe_r[15:8] <= mem_wdata[15:8];
                        end
                        8'h08: io_rdata <= {16'h0, gpio_in_r};
                        8'h10: begin
                            io_rdata <= posit_in;
                            if (mem_wstrb[0]) posit_in[7:0]   <= mem_wdata[7:0];
                            if (mem_wstrb[1]) posit_in[15:8]  <= mem_wdata[15:8];
                            if (mem_wstrb[2]) posit_in[23:16] <= mem_wdata[23:16];
                            if (mem_wstrb[3]) posit_in[31:24] <= mem_wdata[31:24];
                        end
                        8'h14: io_rdata <= {22'h0, p_inf, p_sign, p_exp, p_reg};
                        8'h18: io_rdata <= {4'h0, p_mant};
                        default: io_rdata <= 32'h0;
                    endcase
                end else if (dsp0_hit) io_rdata <= dsp0_rdata;
                else if (dsp1_hit)     io_rdata <= dsp1_rdata;
                else                   io_rdata <= simd_rdata;
            end
        end
    end

    // ---------------- CPU read mux ----------------
    assign mem_ready = io_ready || spimem_ready || ram_ready || scr_ready ||
                       cfg_sel || div_sel || (dat_sel && !dat_wait);
    assign mem_rdata = io_ready     ? io_rdata :
                       spimem_ready ? spimem_rdata :
                       ram_ready    ? ram_rdata :
                       scr_ready    ? scr_rdata :
                       cfg_sel      ? cfg_do :
                       div_sel      ? div_do :
                       dat_sel      ? dat_do : 32'h0;
endmodule

`default_nettype wire
