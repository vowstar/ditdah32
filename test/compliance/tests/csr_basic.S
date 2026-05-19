// SPDX-License-Identifier: MIT
// Zicsr basic CSR access compliance: csrrw, csrrs, csrrc plus their
// immediate variants. Uses mscratch only so the signature is independent
// of the simulator's mstatus/mie/mtvec WARL layout (DitDah32 forces a
// tighter field set than Sail's default rv32d config).

#include "compliance.h"

#define CSR_MSCRATCH 0x340

    COMPLIANCE_SIG_WORD(sig_csrrw_old)
    COMPLIANCE_SIG_WORD(sig_csrrw_new)
    COMPLIANCE_SIG_WORD(sig_csrrs)
    COMPLIANCE_SIG_WORD(sig_csrrc)
    COMPLIANCE_SIG_WORD(sig_csrrwi)
    COMPLIANCE_SIG_WORD(sig_csrrsi)
    COMPLIANCE_SIG_WORD(sig_csrrci)

    COMPLIANCE_START

    // csrrw: write x1 to mscratch, capture the pre-write value into x2.
    li      x1, 0x12345678
    csrrw   x0, CSR_MSCRATCH, x1     // initialise mscratch (rd=x0 still triggers write)
    li      x3, 0xABCDABCD
    csrrw   x2, CSR_MSCRATCH, x3     // x2 <- previous (0x12345678), mscratch <- 0xABCDABCD
    la      x4, sig_csrrw_old
    sw      x2, 0(x4)
    csrr    x5, CSR_MSCRATCH         // pseudo for csrrs rd, csr, x0
    la      x4, sig_csrrw_new
    sw      x5, 0(x4)

    // csrrs: OR bits into mscratch, capture pre-set value.
    li      x1, 0x000000FF
    csrrw   x0, CSR_MSCRATCH, x1
    li      x3, 0x0000FF00
    csrrs   x2, CSR_MSCRATCH, x3     // mscratch <- 0xFFFF, x2 <- 0x00FF
    la      x4, sig_csrrs
    csrr    x5, CSR_MSCRATCH
    sw      x5, 0(x4)

    // csrrc: clear bits in mscratch.
    li      x1, 0x0000FFFF
    csrrw   x0, CSR_MSCRATCH, x1
    li      x3, 0x000000FF
    csrrc   x2, CSR_MSCRATCH, x3     // mscratch <- 0xFF00
    la      x4, sig_csrrc
    csrr    x5, CSR_MSCRATCH
    sw      x5, 0(x4)

    // csrrwi: 5-bit immediate (zero-extended to XLEN).
    csrrwi  x0, CSR_MSCRATCH, 0x1F   // mscratch <- 0x1F
    la      x4, sig_csrrwi
    csrr    x5, CSR_MSCRATCH
    sw      x5, 0(x4)

    // csrrsi: set bits.
    csrrwi  x0, CSR_MSCRATCH, 0x10
    csrrsi  x2, CSR_MSCRATCH, 0x07   // mscratch <- 0x17
    la      x4, sig_csrrsi
    csrr    x5, CSR_MSCRATCH
    sw      x5, 0(x4)

    // csrrci: clear bits.
    csrrwi  x0, CSR_MSCRATCH, 0x1F
    csrrci  x2, CSR_MSCRATCH, 0x0A   // mscratch <- 0x15
    la      x4, sig_csrrci
    csrr    x5, CSR_MSCRATCH
    sw      x5, 0(x4)

    COMPLIANCE_HALT
