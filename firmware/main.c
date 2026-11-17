// Self-test firmware for the RISC-V + posit SoC.
// Checks the 2 KB SRAM (word and byte writes), the RV32M unit and the
// posit decoder accelerator, then reports on GPIO and UART:
//   GPIO_OUT = 0xA5A5 on pass, 0xE000 | error_count on failure.
#include <stdint.h>
#include "vectors.h"

#define REG(a)     (*(volatile uint32_t *)(a))
#define UART_DIV   REG(0x02000004)
#define UART_DAT   REG(0x02000008)
#define GPIO_OUT   REG(0x03000000)
#define GPIO_OE    REG(0x03000004)
#define POSIT_IN   REG(0x03000010)
#define POSIT_FLD  REG(0x03000014)
#define POSIT_MANT REG(0x03000018)

static void uart_puts(const char *s)
{
    while (*s)
        UART_DAT = (uint32_t)*s++;
}

int main(void)
{
    uint32_t err = 0;
    volatile uint32_t buf[96];
    volatile uint8_t *bytes = (volatile uint8_t *)buf;

    UART_DIV = 104;
    GPIO_OE = 0xFFFF;
    GPIO_OUT = 0x0001;                         // stage 1: running from flash

    for (uint32_t i = 0; i < 96; i++)          // SRAM word access
        buf[i] = i * 0x9E3779B9u;
    for (uint32_t i = 0; i < 96; i++)
        if (buf[i] != i * 0x9E3779B9u)
            err++;
    for (uint32_t i = 0; i < 64; i++)          // SRAM byte lanes
        bytes[i] = (uint8_t)(i ^ 0x5A);
    for (uint32_t i = 0; i < 64; i++)
        if (bytes[i] != (uint8_t)(i ^ 0x5A))
            err++;
    GPIO_OUT = 0x0002;                         // stage 2: SRAM done

    volatile uint32_t a = 123457, b = 677;     // RV32M multiply/divide
    if (a * b != 83580389u || (a * b) / b != a || (a * b) % 1000u != 389u)
        err++;
    GPIO_OUT = 0x0003;                         // stage 3: MUL/DIV done

    for (uint32_t i = 0; i < NVEC; i++) {      // posit decoder accelerator
        POSIT_IN = vectors[i][0];
        if (POSIT_FLD != vectors[i][1] || POSIT_MANT != vectors[i][2])
            err++;
    }

    GPIO_OUT = err ? (0xE000u | err) : 0xA5A5u;
    uart_puts(err ? "FAIL\n" : "PASS\n");
    for (;;)
        ;
}
