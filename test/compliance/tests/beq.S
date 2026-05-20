/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// beq (RV32I/E base) compliance test.
// The DUT must take the branch when rs1 == rs2 and fall through otherwise.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_beq_taken)
    COMPLIANCE_SIG_WORD(sig_beq_skipped)

    COMPLIANCE_START
    li      x1, 0x42
    li      x2, 0x42

    // Equal -> branch is taken, the "fallthrough" store must NOT execute.
    beq     x1, x2, beq_taken_target
    li      x3, 0xBAD0BAD0
    la      x4, sig_beq_taken
    sw      x3, 0(x4)
    j       beq_step2
beq_taken_target:
    li      x3, 0x600D600D
    la      x4, sig_beq_taken
    sw      x3, 0(x4)

beq_step2:
    // Unequal -> branch NOT taken, the fallthrough store must execute.
    li      x5, 0xAA
    li      x6, 0xBB
    beq     x5, x6, beq_skip_target
    li      x7, 0x600D600D
    la      x8, sig_beq_skipped
    sw      x7, 0(x8)
    j       beq_step3
beq_skip_target:
    li      x7, 0xBAD0BAD0
    la      x8, sig_beq_skipped
    sw      x7, 0(x8)

beq_step3:
    COMPLIANCE_HALT
