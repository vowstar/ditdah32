/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// c.addi (RV32C / Zca) compliance test.
// Exercises the compressed add-immediate using only the RV32E register set.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_c_addi_0)
    COMPLIANCE_SIG_WORD(sig_c_addi_1)

    COMPLIANCE_START
    .option push
    .option rvc

    c.li    x1, 5           // 16-bit compressed load immediate
    c.addi  x1, 31          // x1 += 31 -> 36
    la      x4, sig_c_addi_0
    sw      x1, 0(x4)

    li      x2, 0x10000     // 32-bit li expands to lui+addi; use 32-bit immediate
    c.addi  x2, -1
    la      x5, sig_c_addi_1
    sw      x2, 0(x5)

    .option pop
    COMPLIANCE_HALT
