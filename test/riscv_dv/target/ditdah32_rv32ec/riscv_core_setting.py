# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import math

from pygen_src.riscv_instr_pkg import (
    exception_cause_t,
    mtvec_mode_t,
    privileged_mode_t,
    privileged_reg_t,
    riscv_instr_group_t,
    satp_mode_t,
)


XLEN = 32
SATP_MODE = satp_mode_t.BARE

supported_privileged_mode = [privileged_mode_t.MACHINE_MODE]
supported_interrupt_mode = [mtvec_mode_t.DIRECT]
max_interrupt_vector_num = 1

unsupported_instr = []
supported_isa = [riscv_instr_group_t.RV32I, riscv_instr_group_t.RV32C]

support_pmp = 0
support_debug_mode = 0
support_umode_trap = 0
support_sfence = 0
support_unaligned_load_store = 0

NUM_FLOAT_GPR = 0
NUM_GPR = 16
NUM_VEC_GPR = 0

VECTOR_EXTENSION_ENABLE = 0
VLEN = 512
ELEN = 32
SELEN = 8
VELEN = int(math.log(ELEN) // math.log(2)) - 3
MAX_LMUL = 1

NUM_HARTS = 1

implemented_csr = [
    privileged_reg_t.MHARTID,
    privileged_reg_t.MSTATUS,
    privileged_reg_t.MISA,
    privileged_reg_t.MTVEC,
    privileged_reg_t.MSCRATCH,
    privileged_reg_t.MEPC,
    privileged_reg_t.MCAUSE,
    privileged_reg_t.MTVAL,
]

custom_csr = []

implemented_interrupt = []

implemented_exception = [
    exception_cause_t.ILLEGAL_INSTRUCTION,
    exception_cause_t.BREAKPOINT,
    exception_cause_t.LOAD_ADDRESS_MISALIGNED,
    exception_cause_t.STORE_AMO_ADDRESS_MISALIGNED,
    exception_cause_t.ECALL_MMODE,
]
