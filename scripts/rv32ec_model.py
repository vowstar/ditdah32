#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
from dataclasses import dataclass, field


MASK32 = 0xFFFF_FFFF
CSR_MSTATUS = 0x300
CSR_MISA = 0x301
CSR_MIE = 0x304
CSR_MTVEC = 0x305
CSR_MSCRATCH = 0x340
CSR_MEPC = 0x341
CSR_MCAUSE = 0x342
CSR_MTVAL = 0x343
CSR_MIP = 0x344
CSR_MVENDORID = 0xF11
CSR_MARCHID = 0xF12
CSR_MIMPID = 0xF13
CSR_MHARTID = 0xF14
CSR_WRITABLE = {CSR_MSTATUS, CSR_MIE, CSR_MTVEC, CSR_MSCRATCH, CSR_MEPC, CSR_MCAUSE, CSR_MTVAL}
CSR_READ_ONLY = {CSR_MISA, CSR_MIP, CSR_MVENDORID, CSR_MARCHID, CSR_MIMPID, CSR_MHARTID}
MSTATUS_MIE = 1 << 3
MSTATUS_MPIE = 1 << 7
MSTATUS_MPP = 3 << 11
MISA_RV32EC = 0x40000014


class Trap(Exception):
    def __init__(self, cause):
        super().__init__(cause)
        self.cause = cause


def u32(value):
    return value & MASK32


def s32(value):
    value &= MASK32
    return value - (1 << 32) if value & (1 << 31) else value


def sext(value, bits):
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def hex32(value):
    return f"0x{value & MASK32:08x}"


def bit_range(value, high, low):
    return (value >> low) & ((1 << (high - low + 1)) - 1)


def require_rv32e_reg(index):
    if index > 15:
        raise Trap("rv32e_register")


def compressed_reg(index):
    return 8 + index


def c_imm6(insn):
    return sext((bit_range(insn, 12, 12) << 5) | bit_range(insn, 6, 2), 6)


def c_addi4spn_imm(insn):
    return (
        (bit_range(insn, 12, 11) << 4)
        | (bit_range(insn, 10, 7) << 6)
        | (bit_range(insn, 6, 6) << 2)
        | (bit_range(insn, 5, 5) << 3)
    )


def c_lw_imm(insn):
    return (
        (bit_range(insn, 5, 5) << 6)
        | (bit_range(insn, 12, 10) << 3)
        | (bit_range(insn, 6, 6) << 2)
    )


def c_lwsp_imm(insn):
    return (
        (bit_range(insn, 3, 2) << 6)
        | (bit_range(insn, 12, 12) << 5)
        | (bit_range(insn, 6, 4) << 2)
    )


def c_swsp_imm(insn):
    return (bit_range(insn, 8, 7) << 6) | (bit_range(insn, 12, 9) << 2)


def c_addi16sp_imm(insn):
    imm = (
        (bit_range(insn, 12, 12) << 9)
        | (bit_range(insn, 4, 3) << 7)
        | (bit_range(insn, 5, 5) << 6)
        | (bit_range(insn, 2, 2) << 5)
        | (bit_range(insn, 6, 6) << 4)
    )
    return sext(imm, 10)


def c_branch_imm(insn):
    imm = (
        (bit_range(insn, 12, 12) << 8)
        | (bit_range(insn, 6, 5) << 6)
        | (bit_range(insn, 11, 10) << 3)
        | (bit_range(insn, 4, 3) << 1)
        | (bit_range(insn, 2, 2) << 5)
    )
    return sext(imm, 9)


def c_jump_imm(insn):
    imm = (
        (bit_range(insn, 12, 12) << 11)
        | (bit_range(insn, 11, 11) << 4)
        | (bit_range(insn, 10, 9) << 8)
        | (bit_range(insn, 8, 8) << 10)
        | (bit_range(insn, 7, 7) << 6)
        | (bit_range(insn, 6, 6) << 7)
        | (bit_range(insn, 5, 3) << 1)
        | (bit_range(insn, 2, 2) << 5)
    )
    return sext(imm, 12)


@dataclass
class RV32ECModel:
    pc: int = 0
    memory: dict[int, int] = field(default_factory=dict)
    regs: list[int] = field(default_factory=lambda: [0] * 16)
    cycle: int = 0
    halted: bool = False
    sleeping: bool = False
    trace: list[dict] = field(default_factory=list)
    csrs: dict[int, int] = field(default_factory=dict)

    def load_words(self, words, base=0):
        addr = base
        for word in words:
            self.store_u32_raw(addr, word)
            addr += 4

    def store_u32_raw(self, addr, value):
        for offset in range(4):
            self.memory[addr + offset] = (value >> (8 * offset)) & 0xFF

    def load_u8_raw(self, addr):
        return self.memory.get(addr, 0)

    def load_u16_raw(self, addr):
        return self.load_u8_raw(addr) | (self.load_u8_raw(addr + 1) << 8)

    def load_u32_raw(self, addr):
        return (
            self.load_u8_raw(addr)
            | (self.load_u8_raw(addr + 1) << 8)
            | (self.load_u8_raw(addr + 2) << 16)
            | (self.load_u8_raw(addr + 3) << 24)
        )

    def read_reg(self, index):
        require_rv32e_reg(index)
        if index == 0:
            return 0
        return self.regs[index]

    def write_reg(self, index, value):
        require_rv32e_reg(index)
        if index != 0:
            self.regs[index] = u32(value)
            return index, hex32(value)
        return None, None

    def read_csr(self, addr):
        if addr == CSR_MISA:
            return MISA_RV32EC
        if addr in (CSR_MIP, CSR_MVENDORID, CSR_MARCHID, CSR_MIMPID, CSR_MHARTID):
            return 0
        if addr in CSR_WRITABLE:
            return self.csrs.get(addr, 0)
        raise Trap("illegal_instruction")

    def write_csr(self, addr, value):
        value = u32(value)
        if addr in CSR_READ_ONLY:
            raise Trap("illegal_instruction")
        if addr == CSR_MSTATUS:
            self.csrs[addr] = value & (MSTATUS_MIE | MSTATUS_MPIE | MSTATUS_MPP)
        elif addr == CSR_MIE:
            self.csrs[addr] = value & ((1 << 3) | (1 << 7) | (1 << 11))
        elif addr == CSR_MTVEC:
            self.csrs[addr] = value & ~0x3
        elif addr == CSR_MEPC:
            self.csrs[addr] = value & ~0x1
        elif addr in (CSR_MSCRATCH, CSR_MCAUSE, CSR_MTVAL):
            self.csrs[addr] = value
        else:
            raise Trap("illegal_instruction")

    def load_data(self, addr, size, signed):
        if size == 2 and (addr & 0x1):
            raise Trap("load_misaligned")
        if size == 4 and (addr & 0x3):
            raise Trap("load_misaligned")

        if size == 1:
            value = self.load_u8_raw(addr)
            return sext(value, 8) if signed else value
        if size == 2:
            value = self.load_u16_raw(addr)
            return sext(value, 16) if signed else value
        if size == 4:
            return self.load_u32_raw(addr)
        raise Trap("illegal_instruction")

    def store_data(self, addr, size, value):
        if size == 2 and (addr & 0x1):
            raise Trap("store_misaligned")
        if size == 4 and (addr & 0x3):
            raise Trap("store_misaligned")

        for offset in range(size):
            self.memory[addr + offset] = (value >> (8 * offset)) & 0xFF

    def fetch(self):
        if self.pc & 0x1:
            raise Trap("instruction_misaligned")

        halfword = self.load_u16_raw(self.pc)
        if (halfword & 0x3) != 0x3:
            return halfword, 2

        return self.load_u32_raw(self.pc), 4

    def make_trace(
        self,
        pc,
        insn,
        length,
        rd_we=False,
        rd=None,
        rd_wdata=None,
        mem_addr=None,
        mem_rdata=None,
        mem_wdata=None,
        trap=False,
        trap_cause=None,
    ):
        return {
            "cycle": self.cycle,
            "pc": hex32(pc),
            "insn": hex32(insn),
            "length": length,
            "rd_we": rd_we,
            "rd": rd,
            "rd_wdata": rd_wdata,
            "mem_addr": hex32(mem_addr) if mem_addr is not None else None,
            "mem_rdata": hex32(mem_rdata) if mem_rdata is not None else None,
            "mem_wdata": hex32(mem_wdata) if mem_wdata is not None else None,
            "trap": trap,
            "trap_cause": trap_cause,
        }

    def step(self):
        if self.halted or self.sleeping:
            return None

        pc = self.pc
        insn = 0
        length = 4
        try:
            insn, length = self.fetch()
            if length == 2:
                trace = self.execute_compressed(pc, insn)
            else:
                trace = self.execute(pc, insn, length)
        except Trap as trap:
            trace = self.make_trace(
                pc,
                insn,
                length,
                trap=True,
                trap_cause=trap.cause,
            )
            self.halted = True

        self.trace.append(trace)
        self.regs[0] = 0
        self.cycle += 1
        return trace

    def run(self, max_steps):
        for _ in range(max_steps):
            if self.halted or self.sleeping:
                break
            self.step()
        return self.trace

    def noop_trace(self, pc, insn, length=2):
        self.pc = u32(pc + length)
        return self.make_trace(pc, insn, length)

    def execute_compressed(self, pc, insn):
        quadrant = insn & 0x3
        funct3 = bit_range(insn, 15, 13)
        rd_rs1 = bit_range(insn, 11, 7)
        rs2 = bit_range(insn, 6, 2)
        rd_prime = compressed_reg(bit_range(insn, 4, 2))
        rs1_prime = compressed_reg(bit_range(insn, 9, 7))
        rs2_prime = compressed_reg(bit_range(insn, 4, 2))
        next_pc = u32(pc + 2)
        rd_out = None
        rd_wdata = None
        mem_addr = None
        mem_rdata = None
        mem_wdata = None

        if insn == 0:
            raise Trap("illegal_instruction")

        if quadrant == 0:
            if funct3 == 0x0:
                imm = c_addi4spn_imm(insn)
                if imm == 0:
                    raise Trap("illegal_instruction")
                rd_out, rd_wdata = self.write_reg(rd_prime, self.read_reg(2) + imm)
            elif funct3 == 0x2:
                addr = u32(self.read_reg(rs1_prime) + c_lw_imm(insn))
                value = u32(self.load_data(addr, 4, True))
                mem_addr = addr
                mem_rdata = value
                rd_out, rd_wdata = self.write_reg(rd_prime, value)
            elif funct3 == 0x6:
                addr = u32(self.read_reg(rs1_prime) + c_lw_imm(insn))
                value = self.read_reg(rs2_prime)
                self.store_data(addr, 4, value)
                mem_addr = addr
                mem_wdata = value
            elif funct3 in (0x1, 0x3, 0x5, 0x7):
                raise Trap("unsupported_extension")
            else:
                raise Trap("illegal_instruction")

        elif quadrant == 1:
            if funct3 == 0x0:
                imm = c_imm6(insn)
                require_rv32e_reg(rd_rs1)
                if rd_rs1 != 0 and imm != 0:
                    rd_out, rd_wdata = self.write_reg(rd_rs1, self.read_reg(rd_rs1) + imm)
            elif funct3 == 0x1:
                next_pc = u32(pc + c_jump_imm(insn))
                rd_out, rd_wdata = self.write_reg(1, pc + 2)
            elif funct3 == 0x2:
                imm = c_imm6(insn)
                require_rv32e_reg(rd_rs1)
                if rd_rs1 != 0:
                    rd_out, rd_wdata = self.write_reg(rd_rs1, imm)
            elif funct3 == 0x3:
                imm = c_imm6(insn)
                require_rv32e_reg(rd_rs1)
                if rd_rs1 == 0:
                    if imm != 0:
                        pass
                    else:
                        raise Trap("illegal_instruction")
                elif rd_rs1 == 2:
                    imm16 = c_addi16sp_imm(insn)
                    if imm16 == 0:
                        raise Trap("illegal_instruction")
                    rd_out, rd_wdata = self.write_reg(2, self.read_reg(2) + imm16)
                else:
                    if imm == 0:
                        raise Trap("illegal_instruction")
                    rd_out, rd_wdata = self.write_reg(rd_rs1, imm << 12)
            elif funct3 == 0x4:
                subop = bit_range(insn, 11, 10)
                if subop == 0x0:
                    shamt = (bit_range(insn, 12, 12) << 5) | bit_range(insn, 6, 2)
                    if bit_range(insn, 12, 12):
                        raise Trap("unsupported_extension")
                    if shamt != 0:
                        rd_out, rd_wdata = self.write_reg(rs1_prime, self.read_reg(rs1_prime) >> shamt)
                elif subop == 0x1:
                    shamt = (bit_range(insn, 12, 12) << 5) | bit_range(insn, 6, 2)
                    if bit_range(insn, 12, 12):
                        raise Trap("unsupported_extension")
                    if shamt != 0:
                        rd_out, rd_wdata = self.write_reg(rs1_prime, s32(self.read_reg(rs1_prime)) >> shamt)
                elif subop == 0x2:
                    rd_out, rd_wdata = self.write_reg(rs1_prime, self.read_reg(rs1_prime) & u32(c_imm6(insn)))
                else:
                    if bit_range(insn, 12, 12):
                        raise Trap("unsupported_extension")
                    lhs = self.read_reg(rs1_prime)
                    rhs = self.read_reg(rs2_prime)
                    ca_op = bit_range(insn, 6, 5)
                    if ca_op == 0x0:
                        result = lhs - rhs
                    elif ca_op == 0x1:
                        result = lhs ^ rhs
                    elif ca_op == 0x2:
                        result = lhs | rhs
                    else:
                        result = lhs & rhs
                    rd_out, rd_wdata = self.write_reg(rs1_prime, result)
            elif funct3 == 0x5:
                next_pc = u32(pc + c_jump_imm(insn))
            elif funct3 == 0x6:
                if self.read_reg(rs1_prime) == 0:
                    next_pc = u32(pc + c_branch_imm(insn))
            elif funct3 == 0x7:
                if self.read_reg(rs1_prime) != 0:
                    next_pc = u32(pc + c_branch_imm(insn))
            else:
                raise Trap("illegal_instruction")

        elif quadrant == 2:
            if funct3 == 0x0:
                shamt = (bit_range(insn, 12, 12) << 5) | bit_range(insn, 6, 2)
                if bit_range(insn, 12, 12):
                    raise Trap("unsupported_extension")
                require_rv32e_reg(rd_rs1)
                if rd_rs1 != 0 and shamt != 0:
                    rd_out, rd_wdata = self.write_reg(rd_rs1, self.read_reg(rd_rs1) << shamt)
            elif funct3 == 0x2:
                require_rv32e_reg(rd_rs1)
                if rd_rs1 == 0:
                    raise Trap("illegal_instruction")
                addr = u32(self.read_reg(2) + c_lwsp_imm(insn))
                value = u32(self.load_data(addr, 4, True))
                mem_addr = addr
                mem_rdata = value
                rd_out, rd_wdata = self.write_reg(rd_rs1, value)
            elif funct3 == 0x4:
                bit12 = bit_range(insn, 12, 12)
                require_rv32e_reg(rd_rs1)
                require_rv32e_reg(rs2)
                if bit12 == 0 and rs2 == 0:
                    if rd_rs1 == 0:
                        raise Trap("illegal_instruction")
                    next_pc = self.read_reg(rd_rs1) & ~1
                elif bit12 == 0:
                    if rd_rs1 != 0:
                        rd_out, rd_wdata = self.write_reg(rd_rs1, self.read_reg(rs2))
                elif rs2 == 0:
                    if rd_rs1 == 0:
                        raise Trap("ebreak")
                    next_pc = self.read_reg(rd_rs1) & ~1
                    rd_out, rd_wdata = self.write_reg(1, pc + 2)
                else:
                    if rd_rs1 != 0:
                        rd_out, rd_wdata = self.write_reg(rd_rs1, self.read_reg(rd_rs1) + self.read_reg(rs2))
            elif funct3 == 0x6:
                require_rv32e_reg(rs2)
                addr = u32(self.read_reg(2) + c_swsp_imm(insn))
                value = self.read_reg(rs2)
                self.store_data(addr, 4, value)
                mem_addr = addr
                mem_wdata = value
            elif funct3 in (0x1, 0x3, 0x5, 0x7):
                raise Trap("unsupported_extension")
            else:
                raise Trap("illegal_instruction")

        else:
            raise Trap("illegal_instruction")

        self.pc = next_pc
        return self.make_trace(
            pc,
            insn,
            2,
            rd_we=rd_out is not None,
            rd=rd_out,
            rd_wdata=rd_wdata,
            mem_addr=mem_addr,
            mem_rdata=mem_rdata,
            mem_wdata=mem_wdata,
        )

    def execute(self, pc, insn, length):
        opcode = insn & 0x7F
        rd = bit_range(insn, 11, 7)
        funct3 = bit_range(insn, 14, 12)
        rs1 = bit_range(insn, 19, 15)
        rs2 = bit_range(insn, 24, 20)
        funct7 = bit_range(insn, 31, 25)

        next_pc = u32(pc + length)
        rd_out = None
        rd_wdata = None
        mem_addr = None
        mem_rdata = None
        mem_wdata = None

        if opcode == 0x37:
            require_rv32e_reg(rd)
            rd_out, rd_wdata = self.write_reg(rd, insn & 0xFFFFF000)

        elif opcode == 0x17:
            require_rv32e_reg(rd)
            rd_out, rd_wdata = self.write_reg(rd, pc + (insn & 0xFFFFF000))

        elif opcode == 0x6F:
            require_rv32e_reg(rd)
            imm = (
                (bit_range(insn, 31, 31) << 20)
                | (bit_range(insn, 19, 12) << 12)
                | (bit_range(insn, 20, 20) << 11)
                | (bit_range(insn, 30, 21) << 1)
            )
            next_pc = u32(pc + sext(imm, 21))
            if next_pc & 0x1:
                raise Trap("instruction_misaligned")
            rd_out, rd_wdata = self.write_reg(rd, pc + length)

        elif opcode == 0x67:
            if funct3 != 0:
                raise Trap("illegal_instruction")
            require_rv32e_reg(rd)
            require_rv32e_reg(rs1)
            imm = sext(bit_range(insn, 31, 20), 12)
            next_pc = u32(self.read_reg(rs1) + imm) & ~1
            rd_out, rd_wdata = self.write_reg(rd, pc + length)

        elif opcode == 0x63:
            require_rv32e_reg(rs1)
            require_rv32e_reg(rs2)
            imm = (
                (bit_range(insn, 31, 31) << 12)
                | (bit_range(insn, 7, 7) << 11)
                | (bit_range(insn, 30, 25) << 5)
                | (bit_range(insn, 11, 8) << 1)
            )
            lhs = self.read_reg(rs1)
            rhs = self.read_reg(rs2)
            taken = {
                0x0: lhs == rhs,
                0x1: lhs != rhs,
                0x4: s32(lhs) < s32(rhs),
                0x5: s32(lhs) >= s32(rhs),
                0x6: lhs < rhs,
                0x7: lhs >= rhs,
            }.get(funct3)
            if taken is None:
                raise Trap("illegal_instruction")
            if taken:
                next_pc = u32(pc + sext(imm, 13))
                if next_pc & 0x1:
                    raise Trap("instruction_misaligned")

        elif opcode == 0x03:
            require_rv32e_reg(rd)
            require_rv32e_reg(rs1)
            addr = u32(self.read_reg(rs1) + sext(bit_range(insn, 31, 20), 12))
            load_map = {
                0x0: (1, True),
                0x1: (2, True),
                0x2: (4, True),
                0x4: (1, False),
                0x5: (2, False),
            }
            if funct3 not in load_map:
                raise Trap("illegal_instruction")
            size, signed = load_map[funct3]
            value = u32(self.load_data(addr, size, signed))
            mem_addr = addr
            mem_rdata = value
            rd_out, rd_wdata = self.write_reg(rd, value)

        elif opcode == 0x23:
            require_rv32e_reg(rs1)
            require_rv32e_reg(rs2)
            imm = (bit_range(insn, 31, 25) << 5) | bit_range(insn, 11, 7)
            addr = u32(self.read_reg(rs1) + sext(imm, 12))
            store_map = {
                0x0: 1,
                0x1: 2,
                0x2: 4,
            }
            if funct3 not in store_map:
                raise Trap("illegal_instruction")
            size = store_map[funct3]
            value = self.read_reg(rs2)
            self.store_data(addr, size, value)
            mem_addr = addr
            mem_wdata = value & ((1 << (8 * size)) - 1)

        elif opcode == 0x13:
            require_rv32e_reg(rd)
            require_rv32e_reg(rs1)
            lhs = self.read_reg(rs1)
            imm = sext(bit_range(insn, 31, 20), 12)
            shamt = bit_range(insn, 24, 20)
            if funct3 == 0x0:
                result = lhs + imm
            elif funct3 == 0x2:
                result = 1 if s32(lhs) < imm else 0
            elif funct3 == 0x3:
                result = 1 if lhs < u32(imm) else 0
            elif funct3 == 0x4:
                result = lhs ^ u32(imm)
            elif funct3 == 0x6:
                result = lhs | u32(imm)
            elif funct3 == 0x7:
                result = lhs & u32(imm)
            elif funct3 == 0x1:
                if funct7 != 0x00:
                    raise Trap("illegal_instruction")
                result = lhs << shamt
            elif funct3 == 0x5:
                if funct7 == 0x00:
                    result = lhs >> shamt
                elif funct7 == 0x20:
                    result = s32(lhs) >> shamt
                else:
                    raise Trap("illegal_instruction")
            else:
                raise Trap("illegal_instruction")
            rd_out, rd_wdata = self.write_reg(rd, result)

        elif opcode == 0x33:
            require_rv32e_reg(rd)
            require_rv32e_reg(rs1)
            require_rv32e_reg(rs2)
            lhs = self.read_reg(rs1)
            rhs = self.read_reg(rs2)
            shamt = rhs & 0x1F
            if funct3 == 0x0 and funct7 == 0x00:
                result = lhs + rhs
            elif funct3 == 0x0 and funct7 == 0x20:
                result = lhs - rhs
            elif funct3 == 0x1 and funct7 == 0x00:
                result = lhs << shamt
            elif funct3 == 0x2 and funct7 == 0x00:
                result = 1 if s32(lhs) < s32(rhs) else 0
            elif funct3 == 0x3 and funct7 == 0x00:
                result = 1 if lhs < rhs else 0
            elif funct3 == 0x4 and funct7 == 0x00:
                result = lhs ^ rhs
            elif funct3 == 0x5 and funct7 == 0x00:
                result = lhs >> shamt
            elif funct3 == 0x5 and funct7 == 0x20:
                result = s32(lhs) >> shamt
            elif funct3 == 0x6 and funct7 == 0x00:
                result = lhs | rhs
            elif funct3 == 0x7 and funct7 == 0x00:
                result = lhs & rhs
            else:
                raise Trap("illegal_instruction")
            rd_out, rd_wdata = self.write_reg(rd, result)

        elif opcode == 0x0F:
            if funct3 != 0x0:
                raise Trap("illegal_instruction")

        elif opcode == 0x73:
            if insn == 0x00000073:
                raise Trap("ecall")
            if insn == 0x00100073:
                raise Trap("ebreak")
            if insn == 0x10500073:
                self.pc = next_pc
                self.sleeping = True
                return self.make_trace(pc, insn, length)
            if insn == 0x30200073:
                self.pc = self.read_csr(CSR_MEPC)
                mstatus = self.read_csr(CSR_MSTATUS)
                mie = MSTATUS_MIE if (mstatus & MSTATUS_MPIE) else 0
                self.write_csr(CSR_MSTATUS, mie | MSTATUS_MPIE | MSTATUS_MPP)
                return self.make_trace(pc, insn, length)
            if funct3 == 0x0 or funct3 == 0x4:
                raise Trap("illegal_instruction")

            csr_addr = bit_range(insn, 31, 20)
            csr_old = self.read_csr(csr_addr)
            csr_imm = bool(funct3 & 0x4)
            operand = rs1 if csr_imm else self.read_reg(rs1)
            csr_write = funct3 in (0x1, 0x5) or (funct3 in (0x2, 0x3, 0x6, 0x7) and operand != 0)

            if funct3 in (0x1, 0x5):
                csr_new = operand
            elif funct3 in (0x2, 0x6):
                csr_new = csr_old | operand
            elif funct3 in (0x3, 0x7):
                csr_new = csr_old & ~operand
            else:
                raise Trap("illegal_instruction")

            if csr_write:
                self.write_csr(csr_addr, csr_new)
            rd_out, rd_wdata = self.write_reg(rd, csr_old)

        else:
            raise Trap("illegal_instruction")

        self.pc = next_pc
        return self.make_trace(
            pc,
            insn,
            length,
            rd_we=rd_out is not None,
            rd=rd_out,
            rd_wdata=rd_wdata,
            mem_addr=mem_addr,
            mem_rdata=mem_rdata,
            mem_wdata=mem_wdata,
        )


def parse_hex_words(path):
    words = []
    current_addr = 0
    segments = []
    with open(path, "r", encoding="utf-8") as hex_file:
        for line_no, line in enumerate(hex_file, start=1):
            text = line.split("#", 1)[0].strip()
            if not text:
                continue
            for token in text.replace(",", " ").split():
                if token.startswith("@"):
                    current_addr = int(token[1:], 0)
                    continue
                try:
                    word = int(token, 0)
                except ValueError as exc:
                    raise SystemExit(f"{path}:{line_no}: invalid token {token!r}") from exc
                if word < 0 or word > MASK32:
                    raise SystemExit(f"{path}:{line_no}: word out of range {token!r}")
                segments.append((current_addr, word))
                current_addr += 4

    if not segments:
        return []
    return segments


def main():
    parser = argparse.ArgumentParser(description="Run the DitDah32 RV32EC reference model")
    parser.add_argument("hex_words", help="text file with 32-bit hex words and optional @addr markers")
    parser.add_argument("--pc", type=lambda text: int(text, 0), default=0)
    parser.add_argument("--max-steps", type=int, default=100)
    args = parser.parse_args()

    model = RV32ECModel(pc=args.pc)
    for addr, word in parse_hex_words(args.hex_words):
        model.store_u32_raw(addr, word)

    for item in model.run(args.max_steps):
        print(json.dumps(item, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
