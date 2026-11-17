// RISC-V SoC with a posit<32,2> decoder accelerator.
//
//   PicoSoC (PicoRV32 RV32IMC, SPI flash XIP, UART) + 2 KB SRAM (4 macros)
//   + memory-mapped posit decoder (hard macro) + 16-bit GPIO.
//
// Memory map
//   0x0000_0000 - 0x0000_07FF  SRAM (2 KB, stack and data)
//   0x0010_0000 - ...          SPI flash (firmware, execute in place)
//   0x0200_0000                SPI flash config      (PicoSoC)
//   0x0200_0004 / 0x0200_0008  UART divider / data   (PicoSoC)
//   0x0300_0000  GPIO_OUT   rw
//   0x0300_0004  GPIO_OE    rw   (1 = drive pad)
//   0x0300_0008  GPIO_IN    ro
//   0x0300_0010  POSIT_IN   rw   32-bit posit<32,2> operand
//   0x0300_0014  POSIT_FLD  ro   {22'b0, inf, sign, exp[1:0], reg[5:0]}
//   0x0300_0018  POSIT_MANT ro   {4'b0, mantissa[27:0]}

`default_nettype none

module soc_top (
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
    // ------------------------------------------------------------------
    // Reset synchroniser
    // ------------------------------------------------------------------
    reg [1:0] rst_sync;
    always @(posedge clk or negedge resetn)
        if (!resetn) rst_sync <= 2'b00;
        else         rst_sync <= {rst_sync[0], 1'b1};
    wire rst_n = rst_sync[1];

    // ------------------------------------------------------------------
    // PicoSoC
    // ------------------------------------------------------------------
    wire        iomem_valid;
    reg         iomem_ready;
    wire [3:0]  iomem_wstrb;
    wire [31:0] iomem_addr;
    wire [31:0] iomem_wdata;
    reg  [31:0] iomem_rdata;

    picosoc #(
        .MEM_WORDS (512)
    ) soc (
        .clk          (clk),
        .resetn       (rst_n),
        .iomem_valid  (iomem_valid),
        .iomem_ready  (iomem_ready),
        .iomem_wstrb  (iomem_wstrb),
        .iomem_addr   (iomem_addr),
        .iomem_wdata  (iomem_wdata),
        .iomem_rdata  (iomem_rdata),
        .irq_5        (irq_5),
        .irq_6        (irq_6),
        .irq_7        (1'b0),
        .ser_tx       (ser_tx),
        .ser_rx       (ser_rx),
        .flash_csb    (flash_csb),
        .flash_clk    (flash_clk),
        .flash_io0_oe (flash_io_oe[0]),
        .flash_io1_oe (flash_io_oe[1]),
        .flash_io2_oe (flash_io_oe[2]),
        .flash_io3_oe (flash_io_oe[3]),
        .flash_io0_do (flash_io_do[0]),
        .flash_io1_do (flash_io_do[1]),
        .flash_io2_do (flash_io_do[2]),
        .flash_io3_do (flash_io_do[3]),
        .flash_io0_di (flash_io_di[0]),
        .flash_io1_di (flash_io_di[1]),
        .flash_io2_di (flash_io_di[2]),
        .flash_io3_di (flash_io_di[3])
    );

    // ------------------------------------------------------------------
    // Posit decoder accelerator (hard macro)
    // ------------------------------------------------------------------
    reg  [31:0] posit_in;
    wire        p_sign, p_inf;
    wire [5:0]  p_reg;
    wire [1:0]  p_exp;
    wire [27:0] p_mant;

    posit_decoder_32_2 u_posit (
`ifdef USE_POWER_PINS
        .VDD      (VDD),
        .VSS      (VSS),
`endif
        .posit_in (posit_in),
        .S        (p_sign),
        .reg_O    (p_reg),
        .EXP_O    (p_exp),
        .inf      (p_inf),
        .Mantissa (p_mant)
    );

    // ------------------------------------------------------------------
    // GPIO and register file on the iomem bus (0x03xx_xxxx)
    // ------------------------------------------------------------------
    reg [15:0] gpio_out_r, gpio_oe_r, gpio_in_r;
    assign gpio_out = gpio_out_r;
    assign gpio_oe  = gpio_oe_r;

    always @(posedge clk) gpio_in_r <= gpio_in;

    wire sel = iomem_valid && !iomem_ready && (iomem_addr[31:24] == 8'h03);

    always @(posedge clk) begin
        if (!rst_n) begin
            iomem_ready <= 1'b0;
            iomem_rdata <= 32'h0;
            gpio_out_r  <= 16'h0;
            gpio_oe_r   <= 16'h0;
            posit_in    <= 32'h0;
        end else begin
            iomem_ready <= 1'b0;
            if (sel) begin
                iomem_ready <= 1'b1;
                case (iomem_addr[7:0])
                    8'h00: begin
                        iomem_rdata <= {16'h0, gpio_out_r};
                        if (iomem_wstrb[0]) gpio_out_r[7:0]  <= iomem_wdata[7:0];
                        if (iomem_wstrb[1]) gpio_out_r[15:8] <= iomem_wdata[15:8];
                    end
                    8'h04: begin
                        iomem_rdata <= {16'h0, gpio_oe_r};
                        if (iomem_wstrb[0]) gpio_oe_r[7:0]  <= iomem_wdata[7:0];
                        if (iomem_wstrb[1]) gpio_oe_r[15:8] <= iomem_wdata[15:8];
                    end
                    8'h08: iomem_rdata <= {16'h0, gpio_in_r};
                    8'h10: begin
                        iomem_rdata <= posit_in;
                        if (iomem_wstrb[0]) posit_in[7:0]   <= iomem_wdata[7:0];
                        if (iomem_wstrb[1]) posit_in[15:8]  <= iomem_wdata[15:8];
                        if (iomem_wstrb[2]) posit_in[23:16] <= iomem_wdata[23:16];
                        if (iomem_wstrb[3]) posit_in[31:24] <= iomem_wdata[31:24];
                    end
                    8'h14: iomem_rdata <= {22'h0, p_inf, p_sign, p_exp, p_reg};
                    8'h18: iomem_rdata <= {4'h0, p_mant};
                    default: iomem_rdata <= 32'h0;
                endcase
            end
        end
    end
endmodule

`default_nettype wire
