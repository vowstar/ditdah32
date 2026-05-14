# SPDX-License-Identifier: MIT

from types import MethodType

from pygen_src.ditdah32_overlay import load_upstream_module
from pygen_src.riscv_instr_pkg import riscv_reg_t


_upstream = load_upstream_module("pygen_src.riscv_instr_gen_config", __file__)
for _name in dir(_upstream):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_upstream, _name)


_original_post_randomize = riscv_instr_gen_config.post_randomize


def _ditdah32_post_randomize(self):
    self.sp = riscv_reg_t.SP
    self.tp = riscv_reg_t.TP
    self.ra = riscv_reg_t.RA
    self.scratch_reg = riscv_reg_t.A4
    self.pmp_reg = riscv_reg_t.A3
    self.stack_len = 128
    self.kernel_stack_len = 128
    self.reserved_regs.clear()
    _original_post_randomize(self)


riscv_instr_gen_config.post_randomize = _ditdah32_post_randomize
cfg.post_randomize = MethodType(_ditdah32_post_randomize, cfg)
