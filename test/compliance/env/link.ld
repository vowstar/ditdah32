/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
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

    /*
     * HTIF tohost slot at 0x100. Both Spike and Sail watch a 64-bit tohost
     * symbol for non-zero writes and exit the simulation when one occurs;
     * the cocotb harness watches the same address for the same reason.
     * The symbol itself is emitted by COMPLIANCE_DATA in compliance.h so
     * the produced symbol has the size attribute (8 bytes) that the HTIF
     * detection logic in Spike/Sail looks for.
     */
    .tohost 0x00000100 : {
        *(.tohost)
    } > RAM

    .signature 0x00000200 : {
        signature_start = .;
        *(.signature)
        signature_end = .;
        . = . + 0x100;
    } > RAM

    /DISCARD/ : { *(.note*) *(.comment*) *(.eh_frame*) *(.riscv.attributes) }
}
