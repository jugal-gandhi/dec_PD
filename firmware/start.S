# Minimal boot code: the stack pointer is set by PicoRV32 (STACKADDR = 2 KB).
.section .text.start
.global _start
_start:
    li   sp, 0x800
    call main
1:  j    1b
