/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// Fence and nop sanity checks. fence and c.nop must execute without trapping
// and must not perturb visible architectural state.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_pre_fence)
    COMPLIANCE_SIG_WORD(sig_post_fence)
    COMPLIANCE_SIG_WORD(sig_pre_cnop)
    COMPLIANCE_SIG_WORD(sig_post_cnop)

    COMPLIANCE_START

    li      x1, 0x1234ABCD
    la      x2, sig_pre_fence
    sw      x1, 0(x2)
    fence   iorw, iorw
    la      x2, sig_post_fence
    sw      x1, 0(x2)

    .option push
    .option rvc
    li      x3, 0x5566CCDD
    la      x4, sig_pre_cnop
    sw      x3, 0(x4)
    c.nop
    c.nop
    la      x4, sig_post_cnop
    sw      x3, 0(x4)
    .option pop

    COMPLIANCE_HALT
