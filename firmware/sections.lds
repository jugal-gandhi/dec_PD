/* Code and constants execute in place from SPI flash; stack lives in SRAM. */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x00100000, LENGTH = 0x400000
    RAM   (xrw) : ORIGIN = 0x00000000, LENGTH = 0x800
}
SECTIONS
{
    .text : {
        KEEP(*(.text.start))
        *(.text*)
        *(.rodata*)
        *(.srodata*)
    } > FLASH
    .bss (NOLOAD) : {
        *(.sbss*) *(.bss*) *(COMMON)
    } > RAM
    /DISCARD/ : { *(.comment) *(.riscv.attributes) *(.note*) }
}
