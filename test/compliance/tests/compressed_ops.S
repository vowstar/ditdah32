// SPDX-License-Identifier: MIT
// Zca compressed register-register ops: c.add, c.sub, c.and, c.or, c.xor, c.mv.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_c_add)
    COMPLIANCE_SIG_WORD(sig_c_sub)
    COMPLIANCE_SIG_WORD(sig_c_and)
    COMPLIANCE_SIG_WORD(sig_c_or)
    COMPLIANCE_SIG_WORD(sig_c_xor)
    COMPLIANCE_SIG_WORD(sig_c_mv)

    COMPLIANCE_START
    .option push
    .option rvc

    li      x10, 7
    li      x11, 5
    c.add   x10, x11           // x10 += x11 -> 12
    la      x4, sig_c_add
    sw      x10, 0(x4)

    li      x8, 20
    li      x9, 3
    c.sub   x8, x9             // x8 -= x9 -> 17
    la      x4, sig_c_sub
    sw      x8, 0(x4)

    li      x8, 0xFF
    li      x9, 0x0F
    c.and   x8, x9             // 0x0F
    la      x4, sig_c_and
    sw      x8, 0(x4)

    li      x8, 0xF0
    li      x9, 0x0F
    c.or    x8, x9             // 0xFF
    la      x4, sig_c_or
    sw      x8, 0(x4)

    li      x8, 0xA5
    li      x9, 0x5A
    c.xor   x8, x9             // 0xFF
    la      x4, sig_c_xor
    sw      x8, 0(x4)

    li      x11, 0x12345
    c.mv    x12, x11           // x12 = x11
    la      x4, sig_c_mv
    sw      x12, 0(x4)

    .option pop
    COMPLIANCE_HALT
