/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// RV32I register-immediate ALU compliance:
// addi, slli, srli, srai, ori, xori, slti, sltiu. (andi covered separately.)

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_addi)
    COMPLIANCE_SIG_WORD(sig_slli)
    COMPLIANCE_SIG_WORD(sig_srli)
    COMPLIANCE_SIG_WORD(sig_srai)
    COMPLIANCE_SIG_WORD(sig_ori)
    COMPLIANCE_SIG_WORD(sig_xori)
    COMPLIANCE_SIG_WORD(sig_slti)
    COMPLIANCE_SIG_WORD(sig_sltiu)

    COMPLIANCE_START

    li      x1, 100
    addi    x2, x1, -50
    la      x3, sig_addi
    sw      x2, 0(x3)

    li      x1, 1
    slli    x2, x1, 30
    la      x3, sig_slli
    sw      x2, 0(x3)

    li      x1, 0x80000000
    srli    x2, x1, 8
    la      x3, sig_srli
    sw      x2, 0(x3)

    srai    x2, x1, 8
    la      x3, sig_srai
    sw      x2, 0(x3)

    li      x1, 0x0F0
    ori     x2, x1, 0x60F
    la      x3, sig_ori
    sw      x2, 0(x3)

    xori    x2, x1, -1
    la      x3, sig_xori
    sw      x2, 0(x3)

    li      x1, -5
    slti    x2, x1, 0
    la      x3, sig_slti
    sw      x2, 0(x3)

    sltiu   x2, x1, 0
    la      x3, sig_sltiu
    sw      x2, 0(x3)

    COMPLIANCE_HALT
