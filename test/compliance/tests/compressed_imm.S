// SPDX-License-Identifier: MIT
// Zca compressed immediate ops: c.li, c.lui, c.slli, c.srli, c.srai, c.andi,
// c.addi16sp, c.addi4spn. (c.addi covered separately.)

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_c_li)
    COMPLIANCE_SIG_WORD(sig_c_lui)
    COMPLIANCE_SIG_WORD(sig_c_slli)
    COMPLIANCE_SIG_WORD(sig_c_srli)
    COMPLIANCE_SIG_WORD(sig_c_srai)
    COMPLIANCE_SIG_WORD(sig_c_andi)
    COMPLIANCE_SIG_WORD(sig_c_addi16sp)
    COMPLIANCE_SIG_WORD(sig_c_addi4spn)

    COMPLIANCE_START
    .option push
    .option rvc

    c.li    x4, -2             // sign-extended
    la      x3, sig_c_li
    sw      x4, 0(x3)

    c.lui   x4, 0x10           // x4 = 0x10000
    la      x3, sig_c_lui
    sw      x4, 0(x3)

    li      x4, 1
    c.slli  x4, 12             // x4 = 0x1000
    la      x3, sig_c_slli
    sw      x4, 0(x3)

    li      x8, 0x10000
    c.srli  x8, 4              // x8 = 0x1000  (CB-format: rs1'=rd' in {x8..x15})
    la      x3, sig_c_srli
    sw      x8, 0(x3)

    li      x8, 0x80000000
    c.srai  x8, 4              // sign-extend right shift
    la      x3, sig_c_srai
    sw      x8, 0(x3)

    li      x8, 0xFFFF
    c.andi  x8, 0x0F           // 0x0F
    la      x3, sig_c_andi
    sw      x8, 0(x3)

    // c.addi16sp: sp += imm * 16 with imm != 0, range -512..+496.
    // Save sp, manipulate, then snapshot result and restore.
    mv      x4, x2
    li      x2, 0x1000          // assume nothing else cares about sp
    c.addi16sp x2, 16            // sp = 0x1010
    mv      x5, x2
    la      x3, sig_c_addi16sp
    sw      x5, 0(x3)
    mv      x2, x4               // restore caller sp

    // c.addi4spn: x_rd' = sp + imm*4 with imm != 0, range 4..1020.
    li      x2, 0x1000           // sp = 0x1000
    c.addi4spn x8, x2, 16        // x8 = sp + 16 = 0x1010 (CIW: rs1=sp, rd' in {x8..x15})
    la      x3, sig_c_addi4spn
    sw      x8, 0(x3)
    mv      x2, x4               // restore caller sp

    .option pop
    COMPLIANCE_HALT
