#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT


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


def csr_type(csr, rs1, funct3, rd):
    return (
        ((csr & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | 0x73
    )


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


def u_type(imm, rd, opcode):
    return (imm & 0xFFFFF000) | ((rd & 0x1F) << 7) | opcode


def j_type(imm, rd, opcode=0x6F):
    imm &= 0x1FFFFF
    return (
        (((imm >> 20) & 0x1) << 31)
        | (((imm >> 1) & 0x3FF) << 21)
        | (((imm >> 11) & 0x1) << 20)
        | (((imm >> 12) & 0xFF) << 12)
        | ((rd & 0x1F) << 7)
        | opcode
    )


def c_reg(reg):
    if not 8 <= reg <= 15:
        raise ValueError(f"compressed compact register must be x8..x15, got x{reg}")
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


def c_lui(rd, imm):
    return c_ci(0x3, rd, imm)


def c_addi16sp(imm):
    return (
        (0x3 << 13)
        | (((imm >> 9) & 0x1) << 12)
        | (2 << 7)
        | (((imm >> 4) & 0x1) << 6)
        | (((imm >> 6) & 0x1) << 5)
        | (((imm >> 7) & 0x3) << 3)
        | (((imm >> 5) & 0x1) << 2)
        | 0x1
    )


def c_addi4spn(rd, imm):
    return (
        (((imm >> 4) & 0x3) << 11)
        | (((imm >> 6) & 0xF) << 7)
        | (((imm >> 2) & 0x1) << 6)
        | (((imm >> 3) & 0x1) << 5)
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
        | (((imm >> 6) & 0x3) << 7)
        | ((rs2 & 0x1F) << 2)
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


class ProgramImage:
    def __init__(self):
        self.bytes = bytearray()

    @property
    def pc(self):
        return len(self.bytes)

    def add16(self, value):
        self.bytes.extend((value & 0xFFFF).to_bytes(2, "little"))

    def add32(self, value):
        self.bytes.extend((value & 0xFFFF_FFFF).to_bytes(4, "little"))

    def words(self):
        data = bytearray(self.bytes)
        while len(data) % 4:
            data.append(0)
        return [int.from_bytes(data[index:index + 4], "little") for index in range(0, len(data), 4)]
