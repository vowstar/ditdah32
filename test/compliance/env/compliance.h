// SPDX-License-Identifier: MIT
//
// DitDah32 compliance gate macros. Provides minimal
// RVTEST_BEGIN / RVMODEL_HALT / RVTEST_SIGUPD-style macros but restricted to
// x0-x15 so the framework actually runs on a strict RV32E hart. Every
// macro is self-contained; no model_test.h or rvtest_setup.h is needed.
//
// Memory map (matches env/link.ld):
//   .text       starts at 0x00000000 (DitDah32 reset vector)
//   signature   starts at 0x00000200, 256 bytes
//
// Halt convention: EBREAK with mtvec=0 traps to address 0 by default. To
// avoid an infinite trap loop the test installs a tight loop at mtvec
// before issuing EBREAK so the simulator sees a stable PC that the
// cocotb/Spike harnesses can detect.

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

// Compliance halt: write 0xC0DEC0DE to address 0x100 (halt magic), then loop.
// The cocotb harness watches the AXI bus for a store to 0x100 of the magic
// value and stops the simulation. Spike sees the magic store too via memory
// inspection at end of run.
#define COMPLIANCE_HALT \
    li      x10, 0xC0DEC0DE ;\
    li      x11, 0x100 ;\
    sw      x10, 0(x11) ;\
1:  j       1b

#define COMPLIANCE_START \
    .section .text.init ;\
    .global _start ;\
    _start:

#endif // DITDAH32_COMPLIANCE_H
