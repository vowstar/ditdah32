/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// Zca compressed branches: c.beqz, c.bnez. CB-format requires rs1' in x8..x15.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_c_beqz_taken)
    COMPLIANCE_SIG_WORD(sig_c_beqz_skipped)
    COMPLIANCE_SIG_WORD(sig_c_bnez_taken)
    COMPLIANCE_SIG_WORD(sig_c_bnez_skipped)

    COMPLIANCE_START
    .option push
    .option rvc

    // c.beqz: rs1==0 -> branch taken.
    li      x8, 0
    c.beqz  x8, c_beqz_taken
    li      x9, 0xBAD0
    j       c_beqz_step2
c_beqz_taken:
    li      x9, 0x600D
c_beqz_step2:
    la      x10, sig_c_beqz_taken
    sw      x9, 0(x10)

    // c.beqz: rs1!=0 -> branch NOT taken.
    li      x8, 5
    c.beqz  x8, c_beqz_skip_target
    li      x9, 0x600D
    j       c_beqz_step3
c_beqz_skip_target:
    li      x9, 0xBAD0
c_beqz_step3:
    la      x10, sig_c_beqz_skipped
    sw      x9, 0(x10)

    // c.bnez: rs1!=0 -> branch taken.
    li      x8, 1
    c.bnez  x8, c_bnez_taken
    li      x9, 0xBAD0
    j       c_bnez_step2
c_bnez_taken:
    li      x9, 0x600D
c_bnez_step2:
    la      x10, sig_c_bnez_taken
    sw      x9, 0(x10)

    // c.bnez: rs1==0 -> branch NOT taken.
    li      x8, 0
    c.bnez  x8, c_bnez_skip_target
    li      x9, 0x600D
    j       c_bnez_done
c_bnez_skip_target:
    li      x9, 0xBAD0
c_bnez_done:
    la      x10, sig_c_bnez_skipped
    sw      x9, 0(x10)

    .option pop
    COMPLIANCE_HALT
