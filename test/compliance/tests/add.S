// SPDX-License-Identifier: MIT
// add (RV32I/E base) compliance test.
//
// Three deterministic add computations are placed into the .signature
// region. The reference (Spike) and DUT (DitDah32) must produce identical
// signature bytes.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_add_0)
    COMPLIANCE_SIG_WORD(sig_add_1)
    COMPLIANCE_SIG_WORD(sig_add_2)

    COMPLIANCE_START
    // Case 0: positive + positive.
    li      x1, 0x12345678
    li      x2, 0x00000001
    add     x3, x1, x2
    la      x4, sig_add_0
    sw      x3, 0(x4)

    // Case 1: signed wrap around.
    li      x5, 0x7FFFFFFF
    li      x6, 0x00000001
    add     x7, x5, x6
    la      x8, sig_add_1
    sw      x7, 0(x8)

    // Case 2: x0 source forces result == rs2.
    li      x9, 0xDEADBEEF
    add     x10, x0, x9
    la      x11, sig_add_2
    sw      x10, 0(x11)

    COMPLIANCE_HALT
