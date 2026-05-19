// SPDX-License-Identifier: MIT
// ebreak trap compliance. Mirrors ecall.S but expects cause = 3
// (BREAKPOINT). Handler advances mepc past the ebreak and resumes.

#include "compliance.h"

#define CSR_MTVEC    0x305
#define CSR_MEPC     0x341
#define CSR_MCAUSE   0x342

    COMPLIANCE_SIG_WORD(sig_pre_ebreak)
    COMPLIANCE_SIG_WORD(sig_handler_entered)
    COMPLIANCE_SIG_WORD(sig_handler_cause)
    COMPLIANCE_SIG_WORD(sig_post_mret)

    COMPLIANCE_START

    la      x1, trap_handler
    csrrw   x0, CSR_MTVEC, x1

    li      x2, 0xDEADC0DE
    la      x3, sig_pre_ebreak
    sw      x2, 0(x3)

    // Force the 32-bit ebreak so the trap handler's "advance mepc by 4"
    // matches the encoded instruction width regardless of the assembler's
    // RVC compression decision.
    .option push
    .option norvc
    ebreak
    .option pop

post_ebreak_return:
    li      x4, 0x12345678
    la      x5, sig_post_mret
    sw      x4, 0(x5)
    COMPLIANCE_HALT

    .align 2
trap_handler:
    li      x6, 0xBEEFBEEF
    la      x7, sig_handler_entered
    sw      x6, 0(x7)

    csrr    x8, CSR_MCAUSE
    li      x9, 0x7FFFFFFF
    and     x8, x8, x9
    la      x10, sig_handler_cause
    sw      x8, 0(x10)

    csrr    x11, CSR_MEPC
    addi    x11, x11, 4
    csrrw   x0, CSR_MEPC, x11
    mret
