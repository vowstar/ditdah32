#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path

from rv32ec_encode import (
    ProgramImage,
    b_type,
    c_addi,
    c_addi16sp,
    c_addi4spn,
    c_branch,
    c_ca,
    c_cr,
    c_ebreak,
    c_j,
    c_li,
    c_lui,
    c_lw,
    c_lwsp,
    c_slli,
    c_sw,
    c_swsp,
    csrrc,
    csrrci,
    csrrs,
    csrrsi,
    csrrw,
    csrrwi,
    i_type,
    j_type,
    r_type,
    s_type,
    u_type,
)
from rv32ec_model import RV32ECModel
from rv32ec_trace_check import compare


CSR_MTVEC = 0x305
CSR_MSCRATCH = 0x340
SPIKE_COMPATIBLE_DATA_BASE = 0x8000_1000


@dataclass
class DirectedProgram:
    name: str
    image: ProgramImage
    max_steps: int


def load_u32_constant(image, reg, value):
    value &= 0xFFFF_FFFF
    if value <= 0x7FF:
        image.add32(i_type(value, 0, 0x0, reg))
        return 1

    upper = (value + 0x800) & 0xFFFF_F000
    lower = (value - upper) & 0xFFF
    image.add32(u_type(upper, reg, 0x37))
    if lower:
        image.add32(i_type(lower, reg, 0x0, reg))
        return 2
    return 1


def rv32e_alu_program():
    image = ProgramImage()
    image.add32(u_type(0x12345000, 1, 0x37))       # lui x1, 0x12345
    image.add32(i_type(0x678, 1, 0x0, 1))          # addi x1, x1, 0x678
    image.add32(u_type(0x00001000, 2, 0x17))       # auipc x2, 0x1
    image.add32(i_type(-1, 0, 0x0, 3))             # addi x3, x0, -1
    image.add32(i_type(1, 3, 0x5, 4))              # srli x4, x3, 1
    image.add32(i_type((0x20 << 5) | 1, 3, 0x5, 5))# srai x5, x3, 1
    image.add32(r_type(0x00, 5, 4, 0x7, 6))        # and x6, x4, x5
    image.add32(r_type(0x00, 5, 4, 0x6, 7))        # or x7, x4, x5
    image.add32(r_type(0x20, 4, 7, 0x0, 8))        # sub x8, x7, x4
    image.add32(0x00100073)                        # ebreak
    return DirectedProgram("rv32e_alu", image, 16)


def rv32e_branch_memory_program():
    image = ProgramImage()
    image.add32(i_type(128, 0, 0x0, 1))      # addi x1, x0, 128
    image.add32(i_type(-1, 0, 0x0, 2))       # addi x2, x0, -1
    image.add32(s_type(0, 2, 1, 0x2))        # sw x2, 0(x1)
    image.add32(i_type(0, 1, 0x2, 3, 0x03))  # lw x3, 0(x1)
    image.add32(b_type(8, 2, 3, 0x0))        # beq x3, x2, +8
    image.add32(i_type(1, 0, 0x0, 4))        # skipped
    image.add32(j_type(8, 5))                # jal x5, +8
    image.add32(i_type(2, 0, 0x0, 4))        # skipped
    image.add32(0x00100073)                  # ebreak
    return DirectedProgram("rv32e_branch_memory", image, 16)


def rv32e_branch_memory_highmem_program(data_base=SPIKE_COMPATIBLE_DATA_BASE):
    image = ProgramImage()
    setup_steps = load_u32_constant(image, 1, data_base)
    image.add32(i_type(-1, 0, 0x0, 2))       # addi x2, x0, -1
    image.add32(s_type(0, 2, 1, 0x2))        # sw x2, 0(x1)
    image.add32(i_type(0, 1, 0x2, 3, 0x03))  # lw x3, 0(x1)
    image.add32(b_type(8, 2, 3, 0x0))        # beq x3, x2, +8
    image.add32(i_type(1, 0, 0x0, 4))        # skipped
    image.add32(j_type(8, 5))                # jal x5, +8
    image.add32(i_type(2, 0, 0x0, 4))        # skipped
    image.add32(0x00100073)                  # ebreak
    return DirectedProgram("rv32e_branch_memory_highmem", image, setup_steps + 16)


def rv32ec_compressed_program():
    image = ProgramImage()
    image.add16(c_addi16sp(16))     # c.addi16sp x2, +16
    image.add16(c_lui(4, 1))        # c.lui x4, 1
    image.add16(c_li(8, 0))          # c.li x8, 0
    image.add16(c_branch(0x6, 8, 4)) # c.beqz x8, +4
    image.add16(c_li(1, 1))          # skipped
    image.add16(c_li(9, 1))          # c.li x9, 1
    image.add16(c_branch(0x7, 9, 4)) # c.bnez x9, +4
    image.add16(c_li(3, 7))          # skipped
    image.add16(c_li(1, 2))          # c.li x1, 2
    image.add16(c_addi(1, 3))        # c.addi x1, 3
    image.add16(c_cr(0, 2, 1))       # c.mv x2, x1
    image.add16(c_cr(1, 2, 1))       # c.add x2, x1
    image.add16(c_slli(2, 1))        # c.slli x2, 1
    image.add16(c_j(0x5, 4))         # c.j +4
    image.add16(c_li(3, 7))          # skipped
    image.add16(c_ebreak())          # c.ebreak
    return DirectedProgram("rv32ec_compressed", image, 16)


def rv32ec_compressed_memory_program():
    image = ProgramImage()
    image.add32(i_type(64, 0, 0x0, 2))  # addi x2, x0, 64
    image.add16(c_addi4spn(8, 16)) # c.addi4spn x8, sp, 16
    image.add16(c_li(9, 7))        # c.li x9, 7
    image.add16(c_sw(9, 8, 0))     # c.sw x9, 0(x8)
    image.add16(c_lw(10, 8, 0))    # c.lw x10, 0(x8)
    image.add16(c_swsp(10, 4))     # c.swsp x10, 4(sp)
    image.add16(c_lwsp(11, 4))     # c.lwsp x11, 4(sp)
    image.add16(c_ebreak())
    return DirectedProgram("rv32ec_compressed_memory", image, 16)


def rv32ec_compressed_memory_highmem_program(data_base=SPIKE_COMPATIBLE_DATA_BASE):
    image = ProgramImage()
    setup_steps = load_u32_constant(image, 2, data_base)
    image.add16(c_addi4spn(8, 16)) # c.addi4spn x8, sp, 16
    image.add16(c_li(9, 7))        # c.li x9, 7
    image.add16(c_sw(9, 8, 0))     # c.sw x9, 0(x8)
    image.add16(c_lw(10, 8, 0))    # c.lw x10, 0(x8)
    image.add16(c_swsp(10, 4))     # c.swsp x10, 4(sp)
    image.add16(c_lwsp(11, 4))     # c.lwsp x11, 4(sp)
    image.add16(c_ebreak())
    return DirectedProgram("rv32ec_compressed_memory_highmem", image, setup_steps + 16)


def rv32ec_zicsr_wfi_program():
    image = ProgramImage()
    image.add32(i_type(64, 0, 0x0, 1))       # addi x1, x0, 64
    image.add32(csrrw(CSR_MTVEC, 1, 0))      # csrw mtvec, x1
    image.add32(csrrs(CSR_MTVEC, 0, 2))      # csrr x2, mtvec
    image.add32(csrrwi(CSR_MSCRATCH, 5, 3))  # csrrwi x3, mscratch, 5
    image.add32(csrrs(CSR_MSCRATCH, 0, 4))   # csrr x4, mscratch
    image.add32(csrrci(CSR_MSCRATCH, 1, 5))  # csrrci x5, mscratch, 1
    image.add32(i_type(4, 0, 0x0, 6))        # addi x6, x0, 4
    image.add32(csrrc(CSR_MSCRATCH, 6, 7))   # csrrc x7, mscratch, x6
    image.add32(csrrsi(CSR_MSCRATCH, 2, 8))  # csrrsi x8, mscratch, 2
    image.add32(0x10500073)                  # wfi
    image.add32(0x00100073)                  # not reached without an interrupt
    return DirectedProgram("rv32ec_zicsr_wfi", image, 16)


def directed_programs():
    return [
        rv32e_alu_program(),
        rv32e_branch_memory_program(),
        rv32ec_compressed_program(),
        rv32ec_compressed_memory_program(),
        rv32ec_zicsr_wfi_program(),
    ]


def aligned_offset(rng, size):
    if size == 4:
        return rng.randrange(0, 64, 4)
    if size == 2:
        return rng.randrange(0, 64, 2)
    return rng.randrange(0, 64)


def random_rv32ec_program(seed, index, steps, data_base=0x400, name_prefix="rv32ec_random"):
    rng = random.Random(seed)
    image = ProgramImage()
    data_regs = [reg for reg in range(1, 16) if reg not in (2, 8)]
    compact_regs = list(range(9, 16))

    setup_steps = 0
    setup_steps += load_u32_constant(image, 2, data_base)
    setup_steps += load_u32_constant(image, 8, data_base)
    for reg in data_regs:
        image.add32(i_type(rng.randint(-32, 31), 0, 0x0, reg))

    for _ in range(steps):
        op = rng.choice(
            [
                "addi",
                "slti",
                "sltiu",
                "xori",
                "ori",
                "andi",
                "slli",
                "srli",
                "srai",
                "add",
                "sub",
                "sll",
                "slt",
                "sltu",
                "xor",
                "srl",
                "sra",
                "or",
                "and",
                "load",
                "store",
                "c_addi",
                "c_li",
                "c_slli",
                "c_mv",
                "c_add",
                "c_lw",
                "c_sw",
                "c_lwsp",
                "c_swsp",
            ]
        )
        rd = rng.choice(data_regs)
        rs1 = rng.choice(data_regs)
        rs2 = rng.choice(data_regs)

        if op == "addi":
            image.add32(i_type(rng.randint(-128, 127), rs1, 0x0, rd))
        elif op == "slti":
            image.add32(i_type(rng.randint(-128, 127), rs1, 0x2, rd))
        elif op == "sltiu":
            image.add32(i_type(rng.randint(-128, 127), rs1, 0x3, rd))
        elif op == "xori":
            image.add32(i_type(rng.randint(-128, 127), rs1, 0x4, rd))
        elif op == "ori":
            image.add32(i_type(rng.randint(-128, 127), rs1, 0x6, rd))
        elif op == "andi":
            image.add32(i_type(rng.randint(-128, 127), rs1, 0x7, rd))
        elif op == "slli":
            image.add32(i_type(rng.randrange(32), rs1, 0x1, rd))
        elif op == "srli":
            image.add32(i_type(rng.randrange(32), rs1, 0x5, rd))
        elif op == "srai":
            image.add32(i_type((0x20 << 5) | rng.randrange(32), rs1, 0x5, rd))
        elif op == "add":
            image.add32(r_type(0x00, rs2, rs1, 0x0, rd))
        elif op == "sub":
            image.add32(r_type(0x20, rs2, rs1, 0x0, rd))
        elif op == "sll":
            image.add32(r_type(0x00, rs2, rs1, 0x1, rd))
        elif op == "slt":
            image.add32(r_type(0x00, rs2, rs1, 0x2, rd))
        elif op == "sltu":
            image.add32(r_type(0x00, rs2, rs1, 0x3, rd))
        elif op == "xor":
            image.add32(r_type(0x00, rs2, rs1, 0x4, rd))
        elif op == "srl":
            image.add32(r_type(0x00, rs2, rs1, 0x5, rd))
        elif op == "sra":
            image.add32(r_type(0x20, rs2, rs1, 0x5, rd))
        elif op == "or":
            image.add32(r_type(0x00, rs2, rs1, 0x6, rd))
        elif op == "and":
            image.add32(r_type(0x00, rs2, rs1, 0x7, rd))
        elif op == "load":
            funct3, size = rng.choice([(0x0, 1), (0x1, 2), (0x2, 4), (0x4, 1), (0x5, 2)])
            image.add32(i_type(aligned_offset(rng, size), 8, funct3, rd, 0x03))
        elif op == "store":
            funct3, size = rng.choice([(0x0, 1), (0x1, 2), (0x2, 4)])
            image.add32(s_type(aligned_offset(rng, size), rs2, 8, funct3))
        elif op == "c_addi":
            image.add16(c_addi(rd, rng.choice([value for value in range(-32, 32) if value != 0])))
        elif op == "c_li":
            image.add16(c_li(rd, rng.randint(-32, 31)))
        elif op == "c_slli":
            image.add16(c_slli(rd, rng.randrange(1, 32)))
        elif op == "c_mv":
            image.add16(c_cr(0, rd, rs2))
        elif op == "c_add":
            image.add16(c_cr(1, rd, rs2))
        elif op == "c_lw":
            image.add16(c_lw(rng.choice(compact_regs), 8, rng.randrange(0, 64, 4)))
        elif op == "c_sw":
            image.add16(c_sw(rng.choice(compact_regs), 8, rng.randrange(0, 64, 4)))
        elif op == "c_lwsp":
            image.add16(c_lwsp(rd, rng.randrange(0, 64, 4)))
        elif op == "c_swsp":
            image.add16(c_swsp(rs2, rng.randrange(0, 64, 4)))

    image.add16(c_ebreak())
    return DirectedProgram(f"{name_prefix}_{index:02d}", image, steps + len(data_regs) + setup_steps + 2)


def random_programs(count=8, steps=64, seed_base=0xD17DA400, data_base=0x400, name_prefix="rv32ec_random"):
    return [
        random_rv32ec_program(seed_base + index, index, steps, data_base, name_prefix)
        for index in range(count)
    ]


def regression_programs(random_count=8, random_steps=64, random_seed_base=0xD17DA400):
    return directed_programs() + random_programs(random_count, random_steps, random_seed_base)


def spike_compatible_programs(random_count=8, random_steps=64, random_seed_base=0xD17DA400):
    return [
        rv32e_alu_program(),
        rv32e_branch_memory_highmem_program(),
        rv32ec_compressed_program(),
        rv32ec_compressed_memory_highmem_program(),
        rv32ec_zicsr_wfi_program(),
    ] + random_programs(
        random_count,
        random_steps,
        random_seed_base,
        data_base=SPIKE_COMPATIBLE_DATA_BASE,
        name_prefix="rv32ec_random_highmem",
    )


def run_program(program):
    model = RV32ECModel()
    model.load_words(program.image.words())
    model.run(program.max_steps)
    return model


def write_hex(path, words):
    path.write_text("\n".join(f"0x{word:08x}" for word in words) + "\n", encoding="utf-8")


def write_trace(path, trace):
    path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in trace), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run DitDah32 directed RV32EC ISA regressions")
    parser.add_argument("--out-dir", type=Path, default=None, help="optional directory for hex and trace artifacts")
    parser.add_argument("--random-count", type=int, default=8)
    parser.add_argument("--random-steps", type=int, default=64)
    parser.add_argument("--random-seed-base", type=lambda text: int(text, 0), default=0xD17DA400)
    parser.add_argument("--spike-compatible", action="store_true", help="emit high-memory artifacts suitable for Spike ISS comparison")
    args = parser.parse_args()

    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)

    failures = []
    if args.spike_compatible:
        programs = spike_compatible_programs(args.random_count, args.random_steps, args.random_seed_base)
    else:
        programs = regression_programs(args.random_count, args.random_steps, args.random_seed_base)

    for program in programs:
        model = run_program(program)
        trace_error = compare(model.trace, model.trace)
        if trace_error:
            failures.append((program.name, trace_error))

        if args.out_dir is not None:
            write_hex(args.out_dir / f"{program.name}.hex", program.image.words())
            write_trace(args.out_dir / f"{program.name}.trace.jsonl", model.trace)

        print(f"{program.name}: {len(model.trace)} trace items")

    if failures:
        for name, error in failures:
            print(f"{name}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
