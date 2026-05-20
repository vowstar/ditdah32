/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// Zca compressed jumps: c.j, c.jal, c.jr, c.jalr.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_c_j_visited)
    COMPLIANCE_SIG_WORD(sig_c_jal_visited)
    COMPLIANCE_SIG_WORD(sig_c_jr_visited)
    COMPLIANCE_SIG_WORD(sig_c_jalr_visited)

    COMPLIANCE_START
    .option push
    .option rvc

    c.j     cj_target
    li      x3, 0xBAD0
    j       cj_finished
cj_target:
    li      x3, 0x600D
    la      x4, sig_c_j_visited
    sw      x3, 0(x4)
cj_finished:

    // c.jal jumps and writes return address into x1 (always).
    c.jal   cjal_target
    j       cjal_finished
cjal_target:
    li      x3, 0xC0DE
    la      x4, sig_c_jal_visited
    sw      x3, 0(x4)
    c.jr    x1                  // c.jr returns through x1
cjal_finished:
    la      x4, sig_c_jr_visited
    li      x3, 0x600D
    sw      x3, 0(x4)

    la      x5, cjalr_target
    c.jalr  x5                  // jumps to x5, writes return addr to x1
    j       cjalr_finished
cjalr_target:
    li      x3, 0xC0DE
    la      x4, sig_c_jalr_visited
    sw      x3, 0(x4)
    c.jr    x1
cjalr_finished:

    .option pop
    COMPLIANCE_HALT
