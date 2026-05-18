/* SPDX-License-Identifier: MIT
 *
 * Linker script for the DitDah32 compliance gate. Boots the test program
 * from the DitDah32 reset vector (PC = 0x0) and places a fixed-size signature
 * region at 0x200, which is high enough to avoid the test code and low
 * enough to fit inside the default 4 KiB cocotb AXI-Lite RAM image. The
 * signature region is bracketed by signature_start and signature_end labels
 * so the same .S sources can be
 * adapted for upstream framework consumption later.
 */

OUTPUT_ARCH("riscv")
ENTRY(_start)

MEMORY {
    RAM (rwx) : ORIGIN = 0x00000000, LENGTH = 4K
}

SECTIONS
{
    . = 0x00000000;
    .text : {
        *(.text.init)
        *(.text)
        *(.text.*)
    } > RAM

    .signature 0x00000200 : {
        signature_start = .;
        *(.signature)
        signature_end = .;
        . = 0x00000300;
    } > RAM

    /DISCARD/ : { *(.note*) *(.comment*) *(.eh_frame*) *(.riscv.attributes) }
}
