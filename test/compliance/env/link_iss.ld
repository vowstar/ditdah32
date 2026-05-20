/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
/* SPDX-License-Identifier: MIT
 *
 * Linker script for the reference ISS (Sail / Spike) view of the DitDah32
 * compliance tests. Mirrors env/link.ld but places everything at the
 * standard 0x80000000 DRAM base so Sail's default RV32 config can load the
 * ELF without altering ROM/RAM placement. The test logic is identical to
 * the base-0 build consumed by the cocotb harness; only the absolute
 * addresses of tohost, the signature region, and the code differ. Signature
 * content is byte-identical between the two builds, so the compliance
 * orchestrator can compare the ISS signature dump against the cocotb DUT
 * read-back word-for-word.
 */

OUTPUT_ARCH("riscv")
ENTRY(_start)

MEMORY {
    RAM (rwx) : ORIGIN = 0x80000000, LENGTH = 64K
}

SECTIONS
{
    . = 0x80000000;
    .text : {
        *(.text.init)
        *(.text)
        *(.text.*)
    } > RAM

    .tohost 0x80000100 : {
        *(.tohost)
    } > RAM

    .signature 0x80000200 : {
        signature_start = .;
        begin_signature = .;
        *(.signature)
        signature_end = .;
        end_signature = .;
        . = . + 0x100;
    } > RAM

    /DISCARD/ : { *(.note*) *(.comment*) *(.eh_frame*) *(.riscv.attributes) }
}
