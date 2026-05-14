# SPDX-License-Identifier: MIT

from pygen_src.ditdah32_overlay import load_upstream_module


_upstream = load_upstream_module("pygen_src.riscv_asm_program_gen", __file__)
for _name in dir(_upstream):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_upstream, _name)


def _ditdah32_gen_program_header(self):
    if cfg.num_of_harts != 1:
        return _upstream.riscv_asm_program_gen.gen_program_header(self)
    self.instr_stream.extend((".include \"user_define.h\"", ".globl _start", ".section .text"))
    if cfg.disable_compressed_instr:
        self.instr_stream.append(".option norvc;")
    self.gen_section(
        "_start",
        [
            ".include \"user_init.s\"",
            "la x14, h0_start",
            "jalr x0, x14, 0",
        ],
    )


def _ditdah32_gen_program_end(self, hart):
    if hart == 0:
        self.gen_section("_exit", ["ebreak"])


def _ditdah32_gen_test_done(self):
    self.instr_stream.extend((
        pkg_ins.format_string("test_done:", pkg_ins.LABEL_STR_LEN),
        pkg_ins.indent + "ebreak",
    ))


riscv_asm_program_gen.gen_program_header = _ditdah32_gen_program_header
riscv_asm_program_gen.gen_program_end = _ditdah32_gen_program_end
riscv_asm_program_gen.gen_test_done = _ditdah32_gen_test_done
