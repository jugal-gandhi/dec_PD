// Self-test firmware for the v3 multi-block SoC.
// Checks: main RAM, scratchpad RAM, RV32M, posit decoder, DSP0-DSP3 MAC
// units and the SIMD ALU. GPIO_OUT = 0xA5A5 on pass, 0xE000 | errors on fail.
#include <stdint.h>
#include "../vectors.h"

#define REG(a)     (*(volatile uint32_t *)(a))
#define UART_DIV   REG(0x02000004)
#define UART_DAT   REG(0x02000008)
#define GPIO_OUT   REG(0x03000000)
#define GPIO_OE    REG(0x03000004)
#define POSIT_IN   REG(0x03000010)
#define POSIT_FLD  REG(0x03000014)
#define POSIT_MANT REG(0x03000018)
#define DSP(n, r)  REG(0x04000000 + 0x100 * (n) + 4 * (r))
#define SIMD(r)    REG(0x05000000 + 4 * (r))
#define SCRATCH    ((volatile uint32_t *)0x00010000)

static void uart_puts(const char *s)
{
    while (*s)
        UART_DAT = (uint32_t)*s++;
}

static const int16_t vx[8] = {1200, -345, 2047, -2048, 17, -999, 300, 1500};
static const int16_t vy[8] = {-7, 1234, 2000, 3, -1500, -321, 77, -2500};

static uint32_t lane(uint32_t x, int i) { return (x >> (8 * i)) & 0xFF; }

static uint32_t simd_ref(uint32_t a, uint32_t b, int op)
{
    uint32_t r = 0;
    if (op == 6) {                                  // popcount
        for (int i = 0; i < 32; i++) r += (a >> i) & 1;
        return r;
    }
    if (op == 7) {                                  // count leading zeros
        for (int i = 31; i >= 0; i--) {
            if ((a >> i) & 1) return 31 - i;
        }
        return 32;
    }
    for (int i = 0; i < 4; i++) {
        uint32_t x = lane(a, i), y = lane(b, i), v;
        uint32_t ad = x > y ? x - y : y - x;
        switch (op) {
        case 0: v = (x + y) & 0xFF; break;
        case 1: v = (x - y) & 0xFF; break;
        case 2: v = (x + y) > 0xFF ? 0xFF : x + y; break;
        case 3: v = ad; break;
        case 4: v = x < y ? x : y; break;
        case 5: v = x < y ? y : x; break;
        default: r += ad; continue;                 // op 8: SAD
        }
        r |= v << (8 * i);
    }
    return r;
}

int main(void)
{
    uint32_t err = 0;
    volatile uint32_t buf[64];

    UART_DIV = 104;
    GPIO_OE = 0xFFFF;
    GPIO_OUT = 0x0001;

    for (uint32_t i = 0; i < 64; i++) buf[i] = i * 0x9E3779B9u;          // main RAM
    for (uint32_t i = 0; i < 64; i++) if (buf[i] != i * 0x9E3779B9u) err++;
    for (uint32_t i = 0; i < 128; i++) SCRATCH[i] = ~(i * 0x01010101u) ^ 0x5A5A0000u;   // scratchpad
    for (uint32_t i = 0; i < 128; i++) if (SCRATCH[i] != (~(i * 0x01010101u) ^ 0x5A5A0000u)) err++;
    volatile uint8_t *sb = (volatile uint8_t *)SCRATCH;
    for (uint32_t i = 0; i < 32; i++) sb[i + 512] = (uint8_t)(i * 7);
    for (uint32_t i = 0; i < 32; i++) if (sb[i + 512] != (uint8_t)(i * 7)) err++;
    GPIO_OUT = 0x0002;

    volatile uint32_t a = 123457, b = 677;                                // RV32M
    if (a * b != 83580389u || (a * b) / b != a) err++;

    for (uint32_t i = 0; i < NVEC; i++) {                                 // posit decoder
        POSIT_IN = vectors[i][0];
        if (POSIT_FLD != vectors[i][1] || POSIT_MANT != vectors[i][2]) err++;
    }
    GPIO_OUT = 0x0003;

    int32_t dxy = 0, dxx = 0, dyy = 0;                                    // DSP array
    for (int i = 0; i < 8; i++) { dxy += vx[i] * vy[i]; dxx += vx[i] * vx[i]; dyy += vy[i] * vy[i]; }
    for (int n = 0; n < 4; n++) DSP(n, 2) = 0;
    for (int i = 0; i < 8; i++) {
        DSP(0, 0) = (uint32_t)(int32_t)vx[i];
        DSP(0, 1) = (uint32_t)(int32_t)vy[i];
        DSP(1, 0) = (uint32_t)(int32_t)vx[i];
        DSP(1, 1) = (uint32_t)(int32_t)vx[i];
        DSP(2, 0) = (uint32_t)(int32_t)vy[i];
        DSP(2, 1) = (uint32_t)(int32_t)vy[i];
        DSP(3, 0) = (uint32_t)(int32_t)vy[i];
        DSP(3, 1) = (uint32_t)(int32_t)vx[i];
    }
    if ((int32_t)DSP(0, 2) != dxy || DSP(0, 4) != 8) err++;
    if ((int32_t)DSP(1, 2) != dxx || DSP(1, 4) != 8) err++;
    if ((int32_t)DSP(2, 2) != dyy || DSP(2, 4) != 8) err++;
    if ((int32_t)DSP(3, 2) != dxy || DSP(3, 4) != 8) err++;
    if (DSP(0, 3) != (dxy < 0 ? 0xFFFFFFFFu : 0u)) err++;
    DSP(1, 0) = (uint32_t)(int32_t)-1234;
    DSP(1, 5) = 5678;
    if ((int32_t)DSP(1, 5) != -7006652 || (int32_t)DSP(1, 2) != -7006652 || DSP(1, 3) != 0xFFFFFFFFu) err++;
    GPIO_OUT = 0x0004;

    static const uint32_t sa[3] = {0x80FF7F10u, 0x00000001u, 0xDEADBEEFu};     // SIMD ALU
    static const uint32_t sbv[3] = {0x7F02FF20u, 0xFFFFFFFFu, 0x12345678u};
    for (int t = 0; t < 3; t++) {
        SIMD(0) = sa[t];
        SIMD(1) = sbv[t];
        for (int op = 0; op <= 8; op++) {
            SIMD(2) = (uint32_t)op;
            if (SIMD(3) != simd_ref(sa[t], sbv[t], op)) err++;
        }
    }

    GPIO_OUT = err ? (0xE000u | err) : 0xA5A5u;
    uart_puts(err ? "FAIL\n" : "PASS\n");
    for (;;)
        ;
}
