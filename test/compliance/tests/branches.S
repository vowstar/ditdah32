/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// RV32I conditional branch compliance (excluding beq): bne, blt, bge, bltu, bgeu.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_bne)
    COMPLIANCE_SIG_WORD(sig_blt)
    COMPLIANCE_SIG_WORD(sig_bge)
    COMPLIANCE_SIG_WORD(sig_bltu)
    COMPLIANCE_SIG_WORD(sig_bgeu)

    COMPLIANCE_START
    // bne taken when operands differ.
    li      x1, 1
    li      x2, 2
    bne     x1, x2, bne_taken
    li      x3, 0
    j       bne_done
bne_taken:
    li      x3, 1
bne_done:
    la      x4, sig_bne
    sw      x3, 0(x4)

    // blt: signed -1 < 0 -> branch taken.
    li      x5, -1
    li      x6, 0
    blt     x5, x6, blt_taken
    li      x7, 0
    j       blt_done
blt_taken:
    li      x7, 1
blt_done:
    la      x8, sig_blt
    sw      x7, 0(x8)

    // bge: signed 1 >= 1 -> branch taken.
    li      x9, 1
    li      x10, 1
    bge     x9, x10, bge_taken
    li      x11, 0
    j       bge_done
bge_taken:
    li      x11, 1
bge_done:
    la      x12, sig_bge
    sw      x11, 0(x12)

    // bltu: unsigned 1 < 0xFFFFFFFF -> branch taken.
    li      x1, 1
    li      x2, -1
    bltu    x1, x2, bltu_taken
    li      x3, 0
    j       bltu_done
bltu_taken:
    li      x3, 1
bltu_done:
    la      x4, sig_bltu
    sw      x3, 0(x4)

    // bgeu: unsigned 0xFFFFFFFF >= 1 -> branch taken.
    bgeu    x2, x1, bgeu_taken
    li      x5, 0
    j       bgeu_done
bgeu_taken:
    li      x5, 1
bgeu_done:
    la      x6, sig_bgeu
    sw      x5, 0(x6)

    COMPLIANCE_HALT
