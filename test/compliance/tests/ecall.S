// SPDX-License-Identifier: MIT
// ecall trap compliance. Installs a minimal trap handler at mtvec, fires
// an ecall from M-mode, expects mcause = 11 (ECALL_M per Priv Spec Table
// 3.6) and a clean return through mret.

#include "compliance.h"

#define CSR_MTVEC    0x305
#define CSR_MEPC     0x341
#define CSR_MCAUSE   0x342
#define MCAUSE_ECALL_M 11

    COMPLIANCE_SIG_WORD(sig_pre_ecall)
    COMPLIANCE_SIG_WORD(sig_handler_entered)
    COMPLIANCE_SIG_WORD(sig_handler_cause)
    COMPLIANCE_SIG_WORD(sig_post_mret)

    COMPLIANCE_START

    // Install the trap handler.
    la      x1, trap_handler
    csrrw   x0, CSR_MTVEC, x1

    li      x2, 0xABCDABCD
    la      x3, sig_pre_ecall
    sw      x2, 0(x3)

    ecall

post_ecall_return:
    li      x4, 0xC0DEC0DE
    la      x5, sig_post_mret
    sw      x4, 0(x5)
    COMPLIANCE_HALT

    .align 2
trap_handler:
    // Record handler entry and the cause code (low 31 bits, mask out the
    // interrupt bit so the signature is byte-stable regardless of which
    // simulator sign-extends the cause register).
    li      x6, 0x11ECA11E
    la      x7, sig_handler_entered
    sw      x6, 0(x7)

    csrr    x8, CSR_MCAUSE
    li      x9, 0x7FFFFFFF
    and     x8, x8, x9
    la      x10, sig_handler_cause
    sw      x8, 0(x10)

    // Advance mepc past the trapping ecall (4 bytes) and return.
    csrr    x11, CSR_MEPC
    addi    x11, x11, 4
    csrrw   x0, CSR_MEPC, x11
    mret
