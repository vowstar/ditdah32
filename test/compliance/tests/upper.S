// SPDX-License-Identifier: MIT
// RV32I upper-immediate ops: lui, auipc.

#include "compliance.h"

    COMPLIANCE_SIG_WORD(sig_lui)
    COMPLIANCE_SIG_WORD(sig_auipc_relative)

    COMPLIANCE_START

    lui     x1, 0x12345
    la      x2, sig_lui
    sw      x1, 0(x2)

    // auipc puts pc + (imm << 12) into rd. The absolute value depends on the
    // link base, but the difference between two auipc results with the same
    // immediate equals the number of bytes between them. Capture
    // (auipc2 - auipc1) so the signature is link-base independent and still
    // exercises the auipc decode + adder.
    auipc   x3, 0x0
    auipc   x4, 0x0
    sub     x5, x4, x3          // x5 = 4 (the 4 bytes between the two auipc)
    la      x6, sig_auipc_relative
    sw      x5, 0(x6)

    COMPLIANCE_HALT
