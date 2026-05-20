/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// Zca compressed memory ops: c.lw, c.sw, c.lwsp, c.swsp.
// Uses sp explicitly for the *sp variants; restores sp at the end.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_c_sw_reload)
    COMPLIANCE_SIG_WORD(sig_c_swsp_reload)

    COMPLIANCE_START
    .option push
    .option rvc

    // Use signature_end as scratch (.signature region is reserved 256 bytes
    // beyond the end labels, so we can safely poke 8 bytes here without
    // disturbing recorded results).
    la      x8, signature_end

    li      x9, 0xDEADBEEF
    c.sw    x9, 0(x8)           // c.sw uses rs1' / rs2' in x8..x15
    c.lw    x10, 0(x8)
    la      x11, sig_c_sw_reload
    sw      x10, 0(x11)

    // c.lwsp / c.swsp: use sp explicitly. Save caller sp then write/read.
    mv      x12, x2
    mv      x2, x8              // sp = scratch slot base
    li      x13, 0xFEEDFACE
    c.swsp  x13, 0(sp)           // sw rs2, 0(sp); rs2 from full set (x1..x15 allowed in RV32E)
    c.lwsp  x14, 0(sp)           // lw rd, 0(sp);  rd from full set (x1..x15 allowed in RV32E)
    mv      x2, x12              // restore sp before stores
    la      x11, sig_c_swsp_reload
    sw      x14, 0(x11)

    .option pop
    COMPLIANCE_HALT
