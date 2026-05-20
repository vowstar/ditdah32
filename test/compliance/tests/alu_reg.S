/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// RV32I register-register ALU compliance test:
// sub, sll, srl, sra, or, xor, slt, sltu. (add covered separately.)

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_sub)
    COMPLIANCE_SIG_WORD(sig_sll)
    COMPLIANCE_SIG_WORD(sig_srl)
    COMPLIANCE_SIG_WORD(sig_sra)
    COMPLIANCE_SIG_WORD(sig_or)
    COMPLIANCE_SIG_WORD(sig_xor)
    COMPLIANCE_SIG_WORD(sig_slt)
    COMPLIANCE_SIG_WORD(sig_sltu)

    COMPLIANCE_START

    li      x1, 0x10
    li      x2, 0x03
    sub     x3, x1, x2
    la      x4, sig_sub
    sw      x3, 0(x4)

    li      x5, 1
    li      x6, 4
    sll     x7, x5, x6
    la      x8, sig_sll
    sw      x7, 0(x8)

    li      x9, 0x80000000
    li      x10, 4
    srl     x11, x9, x10
    la      x12, sig_srl
    sw      x11, 0(x12)

    li      x9, 0x80000000
    sra     x11, x9, x10
    la      x12, sig_sra
    sw      x11, 0(x12)

    li      x1, 0x0F0F
    li      x2, 0xF0F0
    or      x3, x1, x2
    la      x4, sig_or
    sw      x3, 0(x4)

    xor     x3, x1, x2
    la      x4, sig_xor
    sw      x3, 0(x4)

    li      x5, -1
    li      x6, 1
    slt     x7, x5, x6
    la      x8, sig_slt
    sw      x7, 0(x8)

    sltu    x7, x5, x6
    la      x8, sig_sltu
    sw      x7, 0(x8)

    COMPLIANCE_HALT
