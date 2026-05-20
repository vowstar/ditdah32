/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
// SPDX-License-Identifier: MIT
// mret control-flow compliance. Programs mepc to a known target and
// verifies mret transfers control there. Uses ecall to enter the trap
// handler legitimately, then has the handler set mepc to a separate
// second-step label and return via mret.

#include "compliance.h"

#define CSR_MTVEC    0x305
#define CSR_MEPC     0x341

    COMPLIANCE_SIG_WORD(sig_first_path)
    COMPLIANCE_SIG_WORD(sig_diverted_path)
    COMPLIANCE_SIG_WORD(sig_post_finish)

    COMPLIANCE_START

    la      x1, trap_handler
    csrrw   x0, CSR_MTVEC, x1

    li      x2, 0xAA55AA55
    la      x3, sig_first_path
    sw      x2, 0(x3)

    ecall

    // This label MUST NOT execute when the handler diverts mret. If the
    // DUT mret returns to the original mepc (post-ecall+4) instead of the
    // handler-installed target, this store would tag the signature with
    // a wrong marker and the diff against Sail would fail.
must_not_execute:
    li      x4, 0xDEADBAD0
    la      x5, sig_diverted_path
    sw      x4, 0(x5)
    j       finish_path

    .align 2
diverted_target:
    li      x6, 0xC0DECAFE
    la      x7, sig_diverted_path
    sw      x6, 0(x7)

finish_path:
    li      x8, 0x600D600D
    la      x9, sig_post_finish
    sw      x8, 0(x9)
    COMPLIANCE_HALT

    .align 2
trap_handler:
    // Redirect mret to the explicit diverted_target instead of returning
    // to the instruction after ecall. Exercises mepc as a fully writable
    // CSR plus mret's "load PC from mepc" semantics.
    la      x10, diverted_target
    csrrw   x0, CSR_MEPC, x10
    mret
