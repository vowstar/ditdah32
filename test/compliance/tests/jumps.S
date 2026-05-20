/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// RV32I unconditional jumps: jal, jalr.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_jal_visited)
    COMPLIANCE_SIG_WORD(sig_jalr_visited)
    COMPLIANCE_SIG_WORD(sig_jal_return_marker)

    COMPLIANCE_START

    // jal sets x_ra to the address after the jal instruction and jumps to target.
    jal     x1, jal_target
    li      x3, 0xBAD0
    j       jal_finished
jal_target:
    li      x3, 0x600D
    la      x4, sig_jal_visited
    sw      x3, 0(x4)
    // x1 contains a non-zero return address (test x1 != 0 marker).
    sltu    x5, x0, x1
    la      x6, sig_jal_return_marker
    sw      x5, 0(x6)
    jr      x1
jal_finished:

    // jalr: jump to a register-held address. Use x7 = address of jalr_target.
    la      x7, jalr_target
    jalr    x0, 0(x7)
    li      x8, 0xBAD1
    j       jalr_finished
jalr_target:
    li      x8, 0xC0DE
    la      x9, sig_jalr_visited
    sw      x8, 0(x9)
jalr_finished:

    COMPLIANCE_HALT
