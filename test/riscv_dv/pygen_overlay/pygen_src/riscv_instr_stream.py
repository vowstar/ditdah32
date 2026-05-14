# SPDX-License-Identifier: MIT

import vsc

from pygen_src.ditdah32_overlay import load_upstream_module


_upstream = load_upstream_module("pygen_src.riscv_instr_stream", __file__)
for _name in dir(_upstream):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_upstream, _name)


_RV32E_GPRS = (
    riscv_reg_t.ZERO,
    riscv_reg_t.RA,
    riscv_reg_t.SP,
    riscv_reg_t.GP,
    riscv_reg_t.TP,
    riscv_reg_t.T0,
    riscv_reg_t.T1,
    riscv_reg_t.T2,
    riscv_reg_t.S0,
    riscv_reg_t.S1,
    riscv_reg_t.A0,
    riscv_reg_t.A1,
    riscv_reg_t.A2,
    riscv_reg_t.A3,
    riscv_reg_t.A4,
    riscv_reg_t.A5,
)


def _ditdah32_randomize_gpr(self, instr):
    with instr.randomize_with() as it:
        with vsc.if_then(instr.has_rs1):
            instr.rs1.inside(vsc.rangelist(*_RV32E_GPRS))
        with vsc.if_then(instr.has_rs2):
            instr.rs2.inside(vsc.rangelist(*_RV32E_GPRS))
        with vsc.if_then(instr.has_rd):
            instr.rd.inside(vsc.rangelist(*_RV32E_GPRS))
        with vsc.if_then(self.avail_regs.size > 0):
            with vsc.if_then(instr.has_rs1):
                instr.rs1.inside(vsc.rangelist(self.avail_regs))
            with vsc.if_then(instr.has_rs2):
                instr.rs2.inside(vsc.rangelist(self.avail_regs))
            with vsc.if_then(instr.has_rd):
                instr.rd.inside(vsc.rangelist(self.avail_regs))
        with vsc.foreach(self.reserved_rd, idx=True) as i:
            with vsc.if_then(instr.has_rd):
                instr.rd != self.reserved_rd[i]
            with vsc.if_then(instr.format == riscv_instr_format_t.CB_FORMAT):
                instr.rs1 != self.reserved_rd[i]
        with vsc.foreach(cfg.reserved_regs, idx=True) as i:
            with vsc.if_then(instr.has_rd):
                instr.rd != cfg.reserved_regs[i]
            with vsc.if_then(instr.format == riscv_instr_format_t.CB_FORMAT):
                instr.rs1 != cfg.reserved_regs[i]
    return instr


riscv_rand_instr_stream.randomize_gpr = _ditdah32_randomize_gpr
