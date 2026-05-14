# SPDX-License-Identifier: MIT

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from rv32ec_model import RV32ECModel  # noqa: E402
from rv32ec_trace_check import compare, load_jsonl  # noqa: E402


def r_type(funct7, rs2, rs1, funct3, rd, opcode=0x33):
    return (
        ((funct7 & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | opcode
    )


def i_type(imm, rs1, funct3, rd, opcode=0x13):
    return (
        ((imm & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | opcode
    )


def s_type(imm, rs2, rs1, funct3, opcode=0x23):
    imm &= 0xFFF
    return (
        (((imm >> 5) & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((imm & 0x1F) << 7)
        | opcode
    )


def csr_type(csr, rs1, funct3, rd):
    return ((csr & 0xFFF) << 20) | ((rs1 & 0x1F) << 15) | ((funct3 & 0x7) << 12) | ((rd & 0x1F) << 7) | 0x73


def csrrw(csr, rs1, rd):
    return csr_type(csr, rs1, 0x1, rd)


def csrrs(csr, rs1, rd):
    return csr_type(csr, rs1, 0x2, rd)


def csrrc(csr, rs1, rd):
    return csr_type(csr, rs1, 0x3, rd)


def csrrwi(csr, zimm, rd):
    return csr_type(csr, zimm, 0x5, rd)


def csrrsi(csr, zimm, rd):
    return csr_type(csr, zimm, 0x6, rd)


def csrrci(csr, zimm, rd):
    return csr_type(csr, zimm, 0x7, rd)


def b_type(imm, rs2, rs1, funct3, opcode=0x63):
    imm &= 0x1FFF
    return (
        (((imm >> 12) & 0x1) << 31)
        | (((imm >> 5) & 0x3F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | (((imm >> 1) & 0xF) << 8)
        | (((imm >> 11) & 0x1) << 7)
        | opcode
    )


def c_reg(reg):
    assert 8 <= reg <= 15
    return reg - 8


def c_ci(funct3, rd, imm):
    return (
        ((funct3 & 0x7) << 13)
        | (((imm >> 5) & 0x1) << 12)
        | ((rd & 0x1F) << 7)
        | ((imm & 0x1F) << 2)
        | 0x1
    )


def c_addi(rd, imm):
    return c_ci(0x0, rd, imm)


def c_li(rd, imm):
    return c_ci(0x2, rd, imm)


def c_addi4spn(rd, imm):
    return (
        ((imm >> 4) & 0x3) << 11
        | ((imm >> 6) & 0xF) << 7
        | ((imm >> 2) & 0x1) << 6
        | ((imm >> 3) & 0x1) << 5
        | (c_reg(rd) << 2)
    )


def c_lw(rd, rs1, imm):
    return (
        (0x2 << 13)
        | (((imm >> 3) & 0x7) << 10)
        | (c_reg(rs1) << 7)
        | (((imm >> 2) & 0x1) << 6)
        | (((imm >> 6) & 0x1) << 5)
        | (c_reg(rd) << 2)
    )


def c_sw(rs2, rs1, imm):
    return (
        (0x6 << 13)
        | (((imm >> 3) & 0x7) << 10)
        | (c_reg(rs1) << 7)
        | (((imm >> 2) & 0x1) << 6)
        | (((imm >> 6) & 0x1) << 5)
        | (c_reg(rs2) << 2)
    )


def c_lwsp(rd, imm):
    return (
        (0x2 << 13)
        | (((imm >> 5) & 0x1) << 12)
        | ((rd & 0x1F) << 7)
        | (((imm >> 2) & 0x7) << 4)
        | (((imm >> 6) & 0x3) << 2)
        | 0x2
    )


def c_swsp(rs2, imm):
    return (
        (0x6 << 13)
        | (((imm >> 2) & 0xF) << 9)
        | ((rs2 & 0x1F) << 2)
        | (((imm >> 6) & 0x3) << 7)
        | 0x2
    )


def c_j(funct3, imm):
    return (
        (funct3 << 13)
        | (((imm >> 11) & 0x1) << 12)
        | (((imm >> 4) & 0x1) << 11)
        | (((imm >> 8) & 0x3) << 9)
        | (((imm >> 10) & 0x1) << 8)
        | (((imm >> 6) & 0x1) << 7)
        | (((imm >> 7) & 0x1) << 6)
        | (((imm >> 1) & 0x7) << 3)
        | (((imm >> 5) & 0x1) << 2)
        | 0x1
    )


def c_branch(funct3, rs1, imm):
    return (
        (funct3 << 13)
        | (((imm >> 8) & 0x1) << 12)
        | (((imm >> 3) & 0x3) << 10)
        | (c_reg(rs1) << 7)
        | (((imm >> 6) & 0x3) << 5)
        | (((imm >> 1) & 0x3) << 3)
        | (((imm >> 5) & 0x1) << 2)
        | 0x1
    )


def c_slli(rd, shamt):
    return (0x0 << 13) | ((rd & 0x1F) << 7) | ((shamt & 0x1F) << 2) | 0x2


def c_ca(op, rd, rs2):
    return (0x4 << 13) | (0x3 << 10) | (c_reg(rd) << 7) | (op << 5) | (c_reg(rs2) << 2) | 0x1


def c_cr(bit12, rd, rs2):
    return (0x4 << 13) | ((bit12 & 0x1) << 12) | ((rd & 0x1F) << 7) | ((rs2 & 0x1F) << 2) | 0x2


def c_ebreak():
    return c_cr(1, 0, 0)


def pack_halfwords(halfwords):
    words = []
    for index in range(0, len(halfwords), 2):
        lower = halfwords[index] & 0xFFFF
        upper = halfwords[index + 1] & 0xFFFF if index + 1 < len(halfwords) else 0
        words.append(lower | (upper << 16))
    return words


def run_program(words, max_steps=20):
    model = RV32ECModel()
    model.load_words(words)
    model.run(max_steps)
    return model


def run_halfwords(halfwords, max_steps=20):
    return run_program(pack_halfwords(halfwords), max_steps=max_steps)


def test_rv32e_alu_and_x0_behavior():
    model = run_program(
        [
            i_type(5, 0, 0x0, 1),       # addi x1, x0, 5
            i_type(-1, 1, 0x0, 2),      # addi x2, x1, -1
            r_type(0x00, 2, 1, 0x0, 3), # add x3, x1, x2
            i_type(99, 0, 0x0, 0),      # addi x0, x0, 99
            0x00100073,                 # ebreak
        ]
    )

    assert model.regs[0] == 0
    assert model.regs[1] == 5
    assert model.regs[2] == 4
    assert model.regs[3] == 9
    assert model.trace[0]["rd_we"] is True
    assert model.trace[0]["rd"] == 1
    assert model.trace[3]["rd_we"] is False
    assert model.trace[3]["rd"] is None
    assert model.trace[-1]["trap"] is True
    assert model.trace[-1]["trap_cause"] == "ebreak"


def test_rv32e_rejects_x16_register_reference():
    model = run_program(
        [
            i_type(1, 0, 0x0, 16), # addi x16, x0, 1
        ],
        max_steps=1,
    )

    assert model.halted is True
    assert model.trace[0]["trap"] is True
    assert model.trace[0]["trap_cause"] == "rv32e_register"


def test_little_endian_load_store_and_sign_extension():
    model = run_program(
        [
            i_type(64, 0, 0x0, 1),       # addi x1, x0, 64
            i_type(-1, 0, 0x0, 2),       # addi x2, x0, -1
            s_type(0, 2, 1, 0x0),        # sb x2, 0(x1)
            i_type(0, 1, 0x0, 3, 0x03),  # lb x3, 0(x1)
            i_type(0, 1, 0x4, 4, 0x03),  # lbu x4, 0(x1)
            0x00100073,
        ]
    )

    assert model.load_u8_raw(64) == 0xFF
    assert model.regs[3] == 0xFFFF_FFFF
    assert model.regs[4] == 0x0000_00FF
    assert model.trace[2]["mem_addr"] == "0x00000040"
    assert model.trace[2]["mem_wdata"] == "0x000000ff"


def test_branch_taken_and_not_taken():
    model = run_program(
        [
            i_type(1, 0, 0x0, 1),        # addi x1, x0, 1
            b_type(8, 0, 1, 0x0),        # beq x1, x0, +8
            i_type(2, 0, 0x0, 2),        # addi x2, x0, 2
            b_type(8, 0, 1, 0x1),        # bne x1, x0, +8
            i_type(3, 0, 0x0, 2),        # skipped
            i_type(4, 0, 0x0, 3),        # addi x3, x0, 4
            0x00100073,
        ]
    )

    assert model.regs[2] == 2
    assert model.regs[3] == 4
    assert model.trace[3]["pc"] == "0x0000000c"
    assert model.trace[4]["pc"] == "0x00000014"


def test_misaligned_store_traps_without_memory_side_effect():
    model = run_program(
        [
            i_type(65, 0, 0x0, 1), # addi x1, x0, 65
            i_type(1, 0, 0x0, 2),  # addi x2, x0, 1
            s_type(0, 2, 1, 0x1),  # sh x2, 0(x1)
        ],
        max_steps=3,
    )

    assert model.halted is True
    assert model.trace[-1]["trap_cause"] == "store_misaligned"
    assert model.memory.get(65, 0) == 0


def test_trace_checker_accepts_model_trace(tmp_path):
    model = run_program([i_type(1, 0, 0x0, 1), 0x00100073])
    expected = tmp_path / "expected.jsonl"
    actual = tmp_path / "actual.jsonl"

    lines = [json.dumps(item, sort_keys=True) + "\n" for item in model.trace]
    expected.write_text("".join(lines), encoding="utf-8")
    actual.write_text("".join(lines), encoding="utf-8")

    assert compare(load_jsonl(expected), load_jsonl(actual)) is None


def test_zicsr_machine_csrs_and_wfi_model_behavior():
    model = run_program(
        [
            i_type(64, 0, 0x0, 1),
            csrrw(0x305, 1, 0),
            csrrs(0x305, 0, 2),
            csrrwi(0x340, 5, 3),
            csrrs(0x340, 0, 4),
            csrrci(0x340, 1, 5),
            i_type(4, 0, 0x0, 6),
            csrrc(0x340, 6, 7),
            csrrsi(0x340, 2, 8),
            0x10500073,
            i_type(1, 0, 0x0, 5),
        ],
        max_steps=20,
    )

    assert model.regs[2] == 64
    assert model.regs[3] == 0
    assert model.regs[4] == 5
    assert model.regs[5] == 5
    assert model.regs[7] == 4
    assert model.regs[8] == 0
    assert model.sleeping is True
    assert len(model.trace) == 10
    assert model.trace[-1]["insn"] == "0x10500073"


def test_zicsr_read_only_write_traps_in_model():
    model = run_program([csrrwi(0x301, 1, 1)], max_steps=1)

    assert model.halted is True
    assert model.trace[0]["trap"] is True
    assert model.trace[0]["trap_cause"] == "illegal_instruction"


def test_compressed_ci_cr_and_ca_integer_ops():
    model = run_halfwords(
        [
            c_li(1, 5),       # c.li x1, 5
            c_addi(1, 3),     # c.addi x1, 3
            c_cr(0, 2, 1),    # c.mv x2, x1
            c_cr(1, 2, 1),    # c.add x2, x1
            c_slli(2, 1),     # c.slli x2, 1
            c_li(8, 6),       # c.li x8, 6
            c_li(9, 3),       # c.li x9, 3
            c_ca(0x0, 8, 9),  # c.sub x8, x9
            c_ebreak(),
        ]
    )

    assert model.regs[1] == 8
    assert model.regs[2] == 32
    assert model.regs[8] == 3
    assert model.trace[0]["length"] == 2
    assert model.trace[-1]["trap_cause"] == "ebreak"


def test_compressed_load_store_forms():
    model = RV32ECModel()
    model.regs[2] = 64
    model.load_words(
        pack_halfwords(
            [
                c_addi4spn(8, 16),  # c.addi4spn x8, sp, 16
                c_li(9, 7),         # c.li x9, 7
                c_sw(9, 8, 0),      # c.sw x9, 0(x8)
                c_lw(10, 8, 0),     # c.lw x10, 0(x8)
                c_swsp(10, 4),      # c.swsp x10, 4(sp)
                c_lwsp(11, 4),      # c.lwsp x11, 4(sp)
                c_ebreak(),
            ]
        )
    )
    model.run(20)

    assert model.regs[8] == 80
    assert model.regs[10] == 7
    assert model.regs[11] == 7
    assert model.load_u32_raw(80) == 7
    assert model.load_u32_raw(68) == 7


def test_compressed_control_flow():
    model = run_halfwords(
        [
            c_li(8, 0),          # 0x00
            c_branch(0x6, 8, 4), # 0x02: c.beqz x8, +4
            c_li(1, 1),          # 0x04: skipped
            c_li(1, 2),          # 0x06
            c_j(0x5, 4),         # 0x08: c.j +4
            c_li(2, 3),          # 0x0a: skipped
            c_j(0x1, 4),         # 0x0c: c.jal +4
            c_li(3, 4),          # 0x0e: skipped
            c_ebreak(),          # 0x10
        ]
    )

    assert model.regs[1] == 0x0E
    assert model.regs[2] == 0
    assert model.regs[3] == 0
    assert [item["pc"] for item in model.trace[:6]] == [
        "0x00000000",
        "0x00000002",
        "0x00000006",
        "0x00000008",
        "0x0000000c",
        "0x00000010",
    ]


def test_compressed_direct_x16_register_is_illegal_for_rv32e():
    model = run_halfwords([c_lwsp(16, 0)], max_steps=1)

    assert model.halted is True
    assert model.trace[0]["trap"] is True
    assert model.trace[0]["trap_cause"] == "rv32e_register"


def test_compressed_unsupported_floating_point_encoding_traps():
    c_fld = (0x1 << 13) | 0x0
    model = run_halfwords([c_fld], max_steps=1)

    assert model.halted is True
    assert model.trace[0]["trap_cause"] == "unsupported_extension"
