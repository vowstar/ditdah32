// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
//
// DitDah32 compliance gate macros. Provides minimal
// RVTEST_BEGIN / RVMODEL_HALT / RVTEST_SIGUPD-style macros but restricted to
// x0-x15 so the framework actually runs on a strict RV32E hart. Every
// macro is self-contained; no model_test.h or rvtest_setup.h is needed.
//
// Memory map (matches env/link.ld):
//   .text       starts at 0x00000000 (DitDah32 reset vector)
//   .tohost     anchored at 0x00000100 (HTIF tohost slot used by Spike/Sail)
//   signature   starts at 0x00000200, 256 bytes
//
// Halt convention: write 1 to the tohost symbol then spin on a tight loop.
// Spike and Sail both interpret a non-zero write to tohost as an HTIF exit
// (bit 0 set => "test pass") and end the simulation, dumping the requested
// signature region if --test-signature is provided. The cocotb harness
// watches the same address and stops once a non-zero value appears.

#ifndef DITDAH32_COMPLIANCE_H
#define DITDAH32_COMPLIANCE_H

#define SIG_BASE 0x200

// Wrap a section .signature labeled by name plus the offset, declare it as
// 32-bit wide, so the assembler reserves space deterministically.
#define COMPLIANCE_SIG_WORD(name) \
    .pushsection .signature, "aw", @progbits ;\
    .global name ;\
    name: .word 0 ;\
    .popsection

// Compliance halt: write 1 to tohost then spin. The non-zero value triggers
// HTIF exit in Spike and Sail; the spin keeps the DUT on a stable PC for
// cocotb's polling watchdog after the cocotb harness observes the write.
#define COMPLIANCE_HALT \
    li      x10, 1 ;\
    la      x11, tohost ;\
    sw      x10, 0(x11) ;\
    sw      x0, 4(x11) ;\
1:  j       1b

#define COMPLIANCE_START \
    .pushsection .tohost, "aw", @progbits ;\
    .align 3 ;\
    .global tohost ;\
    .type tohost, @object ;\
    .size tohost, 8 ;\
    tohost: .dword 0 ;\
    .align 3 ;\
    .global fromhost ;\
    .type fromhost, @object ;\
    .size fromhost, 8 ;\
    fromhost: .dword 0 ;\
    .popsection ;\
    .section .text.init ;\
    .global _start ;\
    _start:

#endif // DITDAH32_COMPLIANCE_H
