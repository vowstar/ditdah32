/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// RV32I memory access compliance: lb/lbu/lh/lhu/lw, sb/sh/sw.
// Stores a known pattern into the signature region and re-reads it through
// each load width / signedness combination.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_lw)
    COMPLIANCE_SIG_WORD(sig_lh)
    COMPLIANCE_SIG_WORD(sig_lhu)
    COMPLIANCE_SIG_WORD(sig_lb)
    COMPLIANCE_SIG_WORD(sig_lbu)
    COMPLIANCE_SIG_WORD(sig_sb_aggregate)
    COMPLIANCE_SIG_WORD(sig_sh_aggregate)

    COMPLIANCE_START

    // Build a 32-bit pattern 0xCAFE_F00D and store it word-aligned in a
    // scratch slot inside the .signature reserved tail.
    li      x1, 0xCAFEF00D
    la      x2, signature_end
    sw      x1, 0(x2)

    lw      x3, 0(x2)
    la      x4, sig_lw
    sw      x3, 0(x4)

    lh      x5, 0(x2)          // low halfword, sign extended
    la      x6, sig_lh
    sw      x5, 0(x6)

    lhu     x7, 0(x2)          // low halfword, zero extended
    la      x8, sig_lhu
    sw      x7, 0(x8)

    lb      x9, 0(x2)          // low byte, sign extended
    la      x10, sig_lb
    sw      x9, 0(x10)

    lbu     x11, 0(x2)         // low byte, zero extended
    la      x12, sig_lbu
    sw      x11, 0(x12)

    // sb: write four individual bytes 0x01 0x23 0x45 0x67 (little endian) -> 0x67452301.
    li      x1, 0x01
    sb      x1, 0(x2)
    li      x1, 0x23
    sb      x1, 1(x2)
    li      x1, 0x45
    sb      x1, 2(x2)
    li      x1, 0x67
    sb      x1, 3(x2)
    lw      x3, 0(x2)
    la      x4, sig_sb_aggregate
    sw      x3, 0(x4)

    // sh: write two halfwords 0xAAAA, 0x5555 -> 0x5555AAAA.
    li      x1, 0xAAAA
    sh      x1, 0(x2)
    li      x1, 0x5555
    sh      x1, 2(x2)
    lw      x3, 0(x2)
    la      x4, sig_sh_aggregate
    sw      x3, 0(x4)

    COMPLIANCE_HALT
