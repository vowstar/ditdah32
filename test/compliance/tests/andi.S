/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// andi (RV32I/E base) compliance test.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_andi_0)
    COMPLIANCE_SIG_WORD(sig_andi_1)
    COMPLIANCE_SIG_WORD(sig_andi_2)

    COMPLIANCE_START
    li      x1, 0xFFFFFFFF
    andi    x2, x1, 0x0F0
    la      x3, sig_andi_0
    sw      x2, 0(x3)

    li      x4, 0xA5A5A5A5
    andi    x5, x4, -1          // sign extend imm = 0xFFFFFFFF
    la      x6, sig_andi_1
    sw      x5, 0(x6)

    andi    x7, x0, 0x7FF
    la      x8, sig_andi_2
    sw      x7, 0(x8)

    COMPLIANCE_HALT
