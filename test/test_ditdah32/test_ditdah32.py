# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import json
import logging
import os
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.handle import Immediate
from cocotb.triggers import ClockCycles, RisingEdge, Timer, with_timeout
from cocotbext.axi import AxiLiteBus, AxiLiteRam
from cocotbext.axi.axil_channels import (
    AxiLiteAWBus, AxiLiteWBus, AxiLiteBBus, AxiLiteARBus, AxiLiteRBus)


# DitDah32 exposes AXI4-Lite as Decoupled channels (<ch>_valid/_ready/_bits_<f>),
# so remap the BFM's flat AXI attrs onto those port names.
class _AWBus(AxiLiteAWBus):
    _signals = {"awaddr": "aw_bits_addr", "awvalid": "aw_valid", "awready": "aw_ready"}
    _optional_signals = {"awprot": "aw_bits_prot"}


class _WBus(AxiLiteWBus):
    _signals = {"wdata": "w_bits_data", "wvalid": "w_valid", "wready": "w_ready"}
    _optional_signals = {"wstrb": "w_bits_strb"}


class _BBus(AxiLiteBBus):
    _signals = {"bvalid": "b_valid", "bready": "b_ready"}
    _optional_signals = {"bresp": "b_bits_resp"}


class _ARBus(AxiLiteARBus):
    _signals = {"araddr": "ar_bits_addr", "arvalid": "ar_valid", "arready": "ar_ready"}
    _optional_signals = {"arprot": "ar_bits_prot"}


class _RBus(AxiLiteRBus):
    _signals = {"rdata": "r_bits_data", "rvalid": "r_valid", "rready": "r_ready"}
    _optional_signals = {"rresp": "r_bits_resp"}


def axil_channel_bus(dut, prefix):
    return AxiLiteBus.from_channels(
        _AWBus.from_prefix(dut, prefix), _WBus.from_prefix(dut, prefix),
        _BBus.from_prefix(dut, prefix), _ARBus.from_prefix(dut, prefix),
        _RBus.from_prefix(dut, prefix))


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rv32ec_encode import ProgramImage  # noqa: E402
from rv32ec_isa_regress import (  # noqa: E402
    rv32e_alu_program,
    rv32e_branch_memory_program,
    rv32ec_compressed_program,
)
from rv32ec_model import RV32ECModel  # noqa: E402
from rv32ec_trace_check import compare, load_jsonl  # noqa: E402


BENCH_MAGIC = 0xDD32_BEEF
BENCH_COREMARK = 1
BENCH_DHRYSTONE = 2
BENCH_TIMING_START = 0x53544152
BENCH_TIMING_STOP = 0x53544F50
NOP = 0x00000013
C_NOP = 0x0001
ADDI_X1_X0_5 = 0x00500093
ADDI_X2_X1_3 = 0x00308113
LUI_X3_12345 = 0x123451B7
FENCE = 0x0000000F
ECALL = 0x00000073
EBREAK = 0x00100073
WFI = 0x10500073
MRET = 0x30200073
AXI_OKAY = 0
AXI_SLVERR = 2
AXI_ERROR_CAUSE = 7
INTERRUPT_CAUSE = 8
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
CSR_UNIMPLEMENTED = 0x7C0
CSR_FULL_MASK = 0xFFFF_FFFF
MSTATUS_MIE = 1 << 3
MSTATUS_MPIE = 1 << 7
MSTATUS_MPP = 3 << 11
IRQ_SOFTWARE = 1 << 3
IRQ_TIMER = 1 << 7
IRQ_EXTERNAL = 1 << 11
MCAUSE_IRQ_SOFTWARE = 0x80000003
MCAUSE_IRQ_TIMER = 0x80000007
MCAUSE_IRQ_EXTERNAL = 0x8000000B
TRACE_UNCHECKED = object()


def u32(value):
    return value & 0xFFFF_FFFF


def hex32(value):
    return f"0x{value & 0xFFFF_FFFF:08x}"


def is_one(handle):
    try:
        return int(handle.value) == 1
    except ValueError:
        return False


def i_type(imm, rs1, funct3, rd, opcode=0x13):
    return (
        ((imm & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | opcode
    )


def r_type(funct7, rs2, rs1, funct3, rd, opcode=0x33):
    return (
        ((funct7 & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | opcode
    )


def s_type(imm, rs2, rs1, funct3, opcode=0x23):
    return (
        (((imm >> 5) & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((imm & 0x1F) << 7)
        | opcode
    )


def u_type(imm, rd, opcode):
    return (imm & 0xFFFFF000) | ((rd & 0x1F) << 7) | opcode


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


def j_type(imm, rd, opcode=0x6F):
    imm &= 0x1F_FFFF
    return (
        (((imm >> 20) & 0x1) << 31)
        | (((imm >> 1) & 0x3FF) << 21)
        | (((imm >> 11) & 0x1) << 20)
        | (((imm >> 12) & 0xFF) << 12)
        | ((rd & 0x1F) << 7)
        | opcode
    )


def pack_words(words):
    data = bytearray()
    for word in words:
        data.extend((word & 0xFFFF_FFFF).to_bytes(4, "little"))
    return bytes(data)


def pack_halfwords(halfwords):
    data = bytearray()
    for halfword in halfwords:
        data.extend((halfword & 0xFFFF).to_bytes(2, "little"))
    return bytes(data)


def c_reg(reg):
    if not 8 <= reg <= 15:
        raise ValueError(f"compact compressed register must be x8..x15, got x{reg}")
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
        ((funct3 & 0x7) << 13)
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
        ((funct3 & 0x7) << 13)
        | (((imm >> 8) & 0x1) << 12)
        | (((imm >> 3) & 0x3) << 10)
        | (c_reg(rs1) << 7)
        | (((imm >> 6) & 0x3) << 5)
        | (((imm >> 1) & 0x3) << 3)
        | (((imm >> 5) & 0x1) << 2)
        | 0x1
    )


def c_shift_andi(subop, rd, imm):
    return (
        (0x4 << 13)
        | (((imm >> 5) & 0x1) << 12)
        | ((subop & 0x3) << 10)
        | (c_reg(rd) << 7)
        | ((imm & 0x1F) << 2)
        | 0x1
    )


def c_slli(rd, shamt):
    return (0x0 << 13) | ((rd & 0x1F) << 7) | ((shamt & 0x1F) << 2) | 0x2


def c_ca(op, rd, rs2):
    return (0x4 << 13) | (0x3 << 10) | (c_reg(rd) << 7) | ((op & 0x3) << 5) | (c_reg(rs2) << 2) | 0x1


def c_cr(bit12, rd, rs2):
    return (0x4 << 13) | ((bit12 & 0x1) << 12) | ((rd & 0x1F) << 7) | ((rs2 & 0x1F) << 2) | 0x2


def c_ebreak():
    return c_cr(1, 0, 0)


def sparse_image(entries):
    entries = list(entries)
    size = max(addr + len(data) for addr, data in entries)
    image = bytearray(size)
    for addr, data in entries:
        image[addr:addr + len(data)] = data
    return bytes(image)


def drive_axi_slave_idle(dut):
    dut.axi_aw_ready.value = 0
    dut.axi_w_ready.value = 0
    dut.axi_b_valid.value = 0
    dut.axi_b_bits_resp.value = AXI_OKAY
    dut.axi_ar_ready.value = 0
    dut.axi_r_valid.value = 0
    dut.axi_r_bits_data.value = 0
    dut.axi_r_bits_resp.value = AXI_OKAY


def drive_irq_idle(dut):
    dut.irq_software.value = 0
    dut.irq_timer.value = 0
    dut.irq_external.value = 0


async def start_core_without_axi_slave(dut):
    logging.getLogger("cocotb.test_ditdah32.axi").setLevel(logging.WARNING)
    dut.clk.value = Immediate(0)
    dut.reset.value = Immediate(1)
    drive_axi_slave_idle(dut)
    drive_irq_idle(dut)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await ClockCycles(dut.clk, 2)
    dut.reset.value = 1
    drive_axi_slave_idle(dut)
    drive_irq_idle(dut)
    await ClockCycles(dut.clk, 5)
    dut.reset.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


async def start_core(
    dut,
    image=b"",
    size=4096,
    axi_events=None,
    axi_monitor_cycles=400,
    axi_protocol_events=None,
    axi_pause_generators=None,
):
    logging.getLogger("cocotb.test_ditdah32.axi").setLevel(logging.WARNING)
    dut.clk.value = Immediate(0)
    dut.reset.value = Immediate(1)
    drive_irq_idle(dut)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await ClockCycles(dut.clk, 2)

    memory = AxiLiteRam(axil_channel_bus(dut, "axi"), dut.clk, size=size)
    if image:
        memory.write(0, image)
    if axi_pause_generators is not None:
        apply_axi_pause_generators(memory, axi_pause_generators)

    monitors = []
    if axi_events is not None:
        monitors.append(cocotb.start_soon(monitor_axi(dut, axi_events, cycles=axi_monitor_cycles)))
    if axi_protocol_events is not None:
        monitors.append(cocotb.start_soon(monitor_axi_protocol(dut, axi_protocol_events, cycles=axi_monitor_cycles)))

    dut.reset.value = 1
    await ClockCycles(dut.clk, 5)
    dut.reset.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    if monitors:
        return memory, monitors[0] if len(monitors) == 1 else monitors
    return memory


async def accept_axi_read_request(dut, expected_addr=None, expected_prot=None, max_cycles=100):
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if is_one(dut.axi_ar_valid):
            addr = int(dut.axi_ar_bits_addr.value)
            prot = int(dut.axi_ar_bits_prot.value)
            if expected_addr is not None:
                assert addr == expected_addr
            if expected_prot is not None:
                assert prot == expected_prot
            dut.axi_ar_ready.value = 1
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            dut.axi_ar_ready.value = 0
            return {"addr": addr, "prot": prot}
    raise AssertionError("timed out waiting for AXI read request")


async def send_axi_read_response(dut, data, resp=AXI_OKAY, max_cycles=100):
    dut.axi_r_bits_data.value = data & 0xFFFF_FFFF
    dut.axi_r_bits_resp.value = resp & 0x3
    dut.axi_r_valid.value = 1
    for _ in range(max_cycles):
        if is_one(dut.axi_r_ready):
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            dut.axi_r_valid.value = 0
            dut.axi_r_bits_resp.value = AXI_OKAY
            dut.axi_r_bits_data.value = 0
            return
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
    raise AssertionError("timed out waiting for AXI read response acceptance")


async def drive_axi_read(dut, expected_addr, data, expected_prot=None, resp=AXI_OKAY):
    request = await accept_axi_read_request(dut, expected_addr=expected_addr, expected_prot=expected_prot)
    await send_axi_read_response(dut, data, resp=resp)
    return request


async def accept_axi_write_address(dut, expected_addr=None, expected_prot=None, max_cycles=100):
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if is_one(dut.axi_aw_valid):
            addr = int(dut.axi_aw_bits_addr.value)
            prot = int(dut.axi_aw_bits_prot.value)
            if expected_addr is not None:
                assert addr == expected_addr
            if expected_prot is not None:
                assert prot == expected_prot
            dut.axi_aw_ready.value = 1
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            dut.axi_aw_ready.value = 0
            return {"addr": addr, "prot": prot}
    raise AssertionError("timed out waiting for AXI write address")


async def accept_axi_write_data(dut, expected_data=None, expected_strb=None, max_cycles=100):
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if is_one(dut.axi_w_valid):
            data = int(dut.axi_w_bits_data.value)
            strb = int(dut.axi_w_bits_strb.value)
            if expected_data is not None:
                assert data == (expected_data & 0xFFFF_FFFF)
            if expected_strb is not None:
                assert strb == expected_strb
            dut.axi_w_ready.value = 1
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            dut.axi_w_ready.value = 0
            return {"data": data, "strb": strb}
    raise AssertionError("timed out waiting for AXI write data")


async def send_axi_write_response(dut, resp=AXI_OKAY, max_cycles=100):
    dut.axi_b_bits_resp.value = resp & 0x3
    dut.axi_b_valid.value = 1
    for _ in range(max_cycles):
        if is_one(dut.axi_b_ready):
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            dut.axi_b_valid.value = 0
            dut.axi_b_bits_resp.value = AXI_OKAY
            return
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
    raise AssertionError("timed out waiting for AXI write response acceptance")


async def collect_trace(dut, count, max_cycles=400):
    traces = []
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if is_one(dut.trace_valid):
            traces.append(
                {
                    "pc": int(dut.trace_pc.value),
                    "next_pc": int(dut.trace_next_pc.value),
                    "instr": int(dut.trace_instr.value),
                    "len": int(dut.trace_len.value),
                    "rd_we": int(dut.trace_rd_we.value),
                    "rd": int(dut.trace_rd.value),
                    "rd_wdata": int(dut.trace_rd_wdata.value),
                    "rs1_addr": int(dut.trace_rs1_addr.value),
                    "rs1_rdata": int(dut.trace_rs1_rdata.value),
                    "rs2_addr": int(dut.trace_rs2_addr.value),
                    "rs2_rdata": int(dut.trace_rs2_rdata.value),
                    "mem_addr": int(dut.trace_mem_addr.value),
                    "mem_rmask": int(dut.trace_mem_rmask.value),
                    "mem_wmask": int(dut.trace_mem_wmask.value),
                    "mem_rdata": int(dut.trace_mem_rdata.value),
                    "mem_wdata": int(dut.trace_mem_wdata.value),
                    "csr_addr": int(dut.trace_csr_addr.value),
                    "csr_rmask": int(dut.trace_csr_rmask.value),
                    "csr_wmask": int(dut.trace_csr_wmask.value),
                    "csr_rdata": int(dut.trace_csr_rdata.value),
                    "csr_wdata": int(dut.trace_csr_wdata.value),
                    "trap": int(dut.trace_trap.value),
                    "cause": int(dut.trace_trap_cause.value),
                }
            )
            if len(traces) == count:
                return traces
    raise AssertionError(f"timed out waiting for {count} trace items, got {len(traces)}")


async def monitor_axi(dut, events, cycles=400):
    pending_reads = []
    for _ in range(cycles):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if int(dut.axi_ar_valid.value) and int(dut.axi_ar_ready.value):
            event = {
                "kind": "read_addr",
                "addr": int(dut.axi_ar_bits_addr.value),
                "prot": int(dut.axi_ar_bits_prot.value),
            }
            events.append(event)
            pending_reads.append(event)
        if int(dut.axi_r_valid.value) and int(dut.axi_r_ready.value) and pending_reads:
            read_event = pending_reads.pop(0)
            events.append(
                {
                    "kind": "read_data",
                    "addr": read_event["addr"],
                    "prot": read_event["prot"],
                    "data": int(dut.axi_r_bits_data.value),
                }
            )
        if int(dut.axi_aw_valid.value) and int(dut.axi_aw_ready.value):
            events.append(
                {
                    "kind": "write_addr",
                    "addr": int(dut.axi_aw_bits_addr.value),
                    "prot": int(dut.axi_aw_bits_prot.value),
                }
            )
        if int(dut.axi_w_valid.value) and int(dut.axi_w_ready.value):
            events.append(
                {
                    "kind": "write_data",
                    "data": int(dut.axi_w_bits_data.value),
                    "strb": int(dut.axi_w_bits_strb.value),
                }
            )


def seeded_pause_generator(seed, pause_percent=40, max_pause_run=2):
    rng = random.Random(seed)
    pause_run = 0
    while True:
        if pause_run >= max_pause_run:
            pause = False
        else:
            pause = rng.randrange(100) < pause_percent
        pause_run = pause_run + 1 if pause else 0
        yield pause


def axi_backpressure_generators():
    return {
        "ar": seeded_pause_generator(0xA11A_0001, pause_percent=55),
        "r": seeded_pause_generator(0xA11A_0002, pause_percent=45),
        "aw": seeded_pause_generator(0xA11A_0003, pause_percent=55),
        "w": seeded_pause_generator(0xA11A_0004, pause_percent=55),
        "b": seeded_pause_generator(0xA11A_0005, pause_percent=45),
    }


def apply_axi_pause_generators(memory, generators):
    channels = {
        "ar": memory.read_if.ar_channel,
        "r": memory.read_if.r_channel,
        "aw": memory.write_if.aw_channel,
        "w": memory.write_if.w_channel,
        "b": memory.write_if.b_channel,
    }
    for name, generator in generators.items():
        channels[name].set_pause_generator(generator)


def axi_payload(dut, channel):
    if channel == "ar":
        return {"addr": int(dut.axi_ar_bits_addr.value), "prot": int(dut.axi_ar_bits_prot.value)}
    if channel == "aw":
        return {"addr": int(dut.axi_aw_bits_addr.value), "prot": int(dut.axi_aw_bits_prot.value)}
    if channel == "w":
        return {"data": int(dut.axi_w_bits_data.value), "strb": int(dut.axi_w_bits_strb.value)}
    raise ValueError(f"unknown AXI channel {channel}")


def axi_valid_ready(dut, channel):
    if channel == "ar":
        return int(dut.axi_ar_valid.value), int(dut.axi_ar_ready.value)
    if channel == "aw":
        return int(dut.axi_aw_valid.value), int(dut.axi_aw_ready.value)
    if channel == "w":
        return int(dut.axi_w_valid.value), int(dut.axi_w_ready.value)
    raise ValueError(f"unknown AXI channel {channel}")


def append_axi_violation(events, cycle, message, channel=None):
    event = {"kind": "violation", "cycle": cycle, "message": message}
    if channel is not None:
        event["channel"] = channel
    events.append(event)


async def monitor_axi_protocol(dut, events, cycles=400):
    holds = {"ar": None, "aw": None, "w": None}
    outstanding_reads = 0
    aw_seen = False
    w_seen = False
    b_waiting = False

    for cycle in range(cycles):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if int(dut.reset.value) == 1:
            holds = {"ar": None, "aw": None, "w": None}
            outstanding_reads = 0
            aw_seen = False
            w_seen = False
            b_waiting = False
            continue

        for channel in ("ar", "aw", "w"):
            valid, ready = axi_valid_ready(dut, channel)
            payload = axi_payload(dut, channel)
            hold = holds[channel]
            if hold is not None:
                if not valid:
                    append_axi_violation(events, cycle, "VALID dropped before READY", channel)
                elif payload != hold["payload"]:
                    append_axi_violation(events, cycle, "payload changed while VALID waited for READY", channel)

            if valid and ready:
                holds[channel] = None
            elif valid and not ready:
                if hold is None:
                    events.append({"kind": "stall", "cycle": cycle, "channel": channel, **payload})
                holds[channel] = {"payload": payload}
            elif not valid:
                holds[channel] = None

        if int(dut.axi_ar_valid.value) and int(dut.axi_ar_ready.value):
            outstanding_reads += 1
            events.append(
                {
                    "kind": "read_addr",
                    "cycle": cycle,
                    "addr": int(dut.axi_ar_bits_addr.value),
                    "prot": int(dut.axi_ar_bits_prot.value),
                    "outstanding_reads": outstanding_reads,
                }
            )
            if outstanding_reads > 1:
                append_axi_violation(events, cycle, "more than one outstanding read", "ar")

        if int(dut.axi_r_valid.value) and int(dut.axi_r_ready.value):
            events.append(
                {
                    "kind": "read_data",
                    "cycle": cycle,
                    "data": int(dut.axi_r_bits_data.value),
                    "resp": int(dut.axi_r_bits_resp.value),
                    "outstanding_reads": outstanding_reads,
                }
            )
            if outstanding_reads == 0:
                append_axi_violation(events, cycle, "read response without outstanding read", "r")
            else:
                outstanding_reads -= 1

        if int(dut.axi_aw_valid.value) and int(dut.axi_aw_ready.value):
            events.append(
                {
                    "kind": "write_addr",
                    "cycle": cycle,
                    "addr": int(dut.axi_aw_bits_addr.value),
                    "prot": int(dut.axi_aw_bits_prot.value),
                }
            )
            if aw_seen or b_waiting:
                append_axi_violation(events, cycle, "second AW before write response", "aw")
            aw_seen = True

        if int(dut.axi_w_valid.value) and int(dut.axi_w_ready.value):
            events.append(
                {
                    "kind": "write_data",
                    "cycle": cycle,
                    "data": int(dut.axi_w_bits_data.value),
                    "strb": int(dut.axi_w_bits_strb.value),
                }
            )
            if w_seen or b_waiting:
                append_axi_violation(events, cycle, "second W before write response", "w")
            w_seen = True

        if aw_seen and w_seen:
            b_waiting = True

        if int(dut.axi_b_valid.value) and int(dut.axi_b_ready.value):
            events.append(
                {
                    "kind": "write_resp",
                    "cycle": cycle,
                    "resp": int(dut.axi_b_bits_resp.value),
                    "b_waiting": b_waiting,
                }
            )
            if not b_waiting:
                append_axi_violation(events, cycle, "write response without accepted AW and W", "b")
            aw_seen = False
            w_seen = False
            b_waiting = False


def axi_violations(events):
    return [event for event in events if event["kind"] == "violation"]


def write_axi_event_report(name, events):
    out_dir = REPO_ROOT / "result" / "axi"
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    stalls = {}
    for event in events:
        counts[event["kind"]] = counts.get(event["kind"], 0) + 1
        if event["kind"] == "stall":
            stalls[event["channel"]] = stalls.get(event["channel"], 0) + 1

    report = {
        "name": name,
        "status": "fail" if axi_violations(events) else "pass",
        "counts": counts,
        "stalls": stalls,
        "violations": axi_violations(events),
        "events": events,
    }
    path = out_dir / f"{name}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def assert_trace(
    trace,
    pc,
    instr,
    length=4,
    rd=None,
    rd_wdata=0,
    rs1=TRACE_UNCHECKED,
    rs1_rdata=0,
    rs2=TRACE_UNCHECKED,
    rs2_rdata=0,
    mem_addr=TRACE_UNCHECKED,
    mem_rmask=TRACE_UNCHECKED,
    mem_wmask=TRACE_UNCHECKED,
    mem_rdata=0,
    mem_wdata=0,
    csr_addr=TRACE_UNCHECKED,
    csr_rmask=TRACE_UNCHECKED,
    csr_wmask=TRACE_UNCHECKED,
    csr_rdata=0,
    csr_wdata=0,
    trap=False,
    cause=0,
    next_pc=None,
):
    assert trace["pc"] == pc
    if next_pc is not None:
        assert trace["next_pc"] == next_pc
    assert trace["instr"] == instr
    assert trace["len"] == length
    assert trace["trap"] == int(trap)
    assert trace["cause"] == cause
    if rd is None:
        assert trace["rd_we"] == 0
    else:
        assert trace["rd_we"] == 1
        assert trace["rd"] == rd
        assert trace["rd_wdata"] == u32(rd_wdata)
    if rs1 is not TRACE_UNCHECKED:
        assert trace["rs1_addr"] == rs1
        assert trace["rs1_rdata"] == u32(rs1_rdata)
    if rs2 is not TRACE_UNCHECKED:
        assert trace["rs2_addr"] == rs2
        assert trace["rs2_rdata"] == u32(rs2_rdata)
    if mem_addr is not TRACE_UNCHECKED:
        assert trace["mem_addr"] == u32(mem_addr)
    if mem_rmask is not TRACE_UNCHECKED:
        assert trace["mem_rmask"] == mem_rmask
        assert trace["mem_rdata"] == (0 if mem_rmask == 0 else u32(mem_rdata))
    if mem_wmask is not TRACE_UNCHECKED:
        assert trace["mem_wmask"] == mem_wmask
        assert trace["mem_wdata"] == (0 if mem_wmask == 0 else u32(mem_wdata))
    if csr_addr is not TRACE_UNCHECKED:
        assert trace["csr_addr"] == csr_addr
    if csr_rmask is not TRACE_UNCHECKED:
        assert trace["csr_rmask"] == u32(csr_rmask)
        assert trace["csr_rdata"] == (0 if csr_rmask == 0 else u32(csr_rdata))
    if csr_wmask is not TRACE_UNCHECKED:
        assert trace["csr_wmask"] == u32(csr_wmask)
        assert trace["csr_wdata"] == (0 if csr_wmask == 0 else u32(csr_wdata))


def trap_cause_name(cause):
    return {
        1: "illegal_instruction",
        2: "ebreak",
        3: "rv32e_register",
        4: "ecall",
        5: "load_misaligned",
        6: "store_misaligned",
        7: "axi_error",
        8: "interrupt",
    }.get(cause)


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def load_hex_words(path):
    words = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        try:
            words.append(int(text, 0) & 0xFFFF_FFFF)
        except ValueError as exc:
            raise AssertionError(f"{path}:{line_no}: invalid hex word {text!r}") from exc
    if not words:
        raise AssertionError(f"{path}: no words loaded")
    return words


def load_isa_artifact():
    name = os.environ.get("DITDAH32_ISA_ARTIFACT")
    if not name:
        raise AssertionError("DITDAH32_ISA_ARTIFACT is required")

    isa_dir = Path(os.environ.get("DITDAH32_ISA_DIR", REPO_ROOT / "result" / "isa"))
    if not isa_dir.is_absolute():
        isa_dir = REPO_ROOT / isa_dir

    hex_path = isa_dir / f"{name}.hex"
    trace_path = isa_dir / f"{name}.trace.jsonl"
    if not hex_path.exists():
        raise AssertionError(f"missing ISA hex artifact: {hex_path}")
    if not trace_path.exists():
        raise AssertionError(f"missing ISA trace artifact: {trace_path}")

    return name, load_hex_words(hex_path), load_jsonl(trace_path)


def load_benchmark_manifest(name):
    manifest_path = REPO_ROOT / "result" / "bench" / name / f"{name}.manifest.json"
    if not manifest_path.exists():
        raise AssertionError(f"missing benchmark manifest: {manifest_path}; run make bench")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def read_benchmark_result(memory, addr):
    return [
        memory.read_dword(addr + 4 * index, byteorder="little")
        for index in range(7)
    ]


def benchmark_frequency_mhz():
    return float(os.environ.get("DITDAH32_BENCH_FREQ_MHZ", "100"))


def write_benchmark_score(name, manifest, result, cycles, timing):
    freq_mhz = benchmark_frequency_mhz()
    timed_cycles = timing.get("stop_cycle", 0) - timing.get("start_cycle", 0)
    if timed_cycles <= 0:
        timed_cycles = cycles
        cycle_source = "whole_program_to_trap"
    else:
        cycle_source = "software_timing_markers"

    work_units = result[3]
    per_second = (work_units * freq_mhz * 1_000_000.0) / timed_cycles
    per_mhz = (work_units * 1_000_000.0) / timed_cycles
    report = {
        "benchmark": name,
        "certification_status": "not_certified_local_rtl_estimate",
        "cycle_source": cycle_source,
        "cycles_to_trap": cycles,
        "timed_cycles": timed_cycles,
        "frequency_mhz": freq_mhz,
        "result_words": [hex32(value) for value in result],
        "manifest": manifest,
    }
    if name == "coremark":
        report.update(
            {
                "iterations": work_units,
                "coremark_per_second": per_second,
                "coremark_per_mhz": per_mhz,
            }
        )
    elif name == "dhrystone":
        report.update(
            {
                "runs": work_units,
                "dhrystones_per_second": per_second,
                "dmips": per_second / 1757.0,
                "dmips_per_mhz": per_mhz / 1757.0,
            }
        )

    out_dir = REPO_ROOT / "result" / "bench" / "scores"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


async def run_benchmark_until_trap(dut, name, benchmark_id, max_cycles):
    manifest = load_benchmark_manifest(name)
    image = (REPO_ROOT / manifest["bin"]).read_bytes()
    memory = await start_core(dut, image, size=manifest["memory_size"])

    trapped = False
    cycles = 0
    pending_write_addrs = []
    pending_write_data = []
    timing = {}
    timing_addr = manifest.get("timing_addr")

    for cycle in range(1, max_cycles + 1):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        cycles = cycle
        if int(dut.axi_aw_valid.value) and int(dut.axi_aw_ready.value):
            pending_write_addrs.append(int(dut.axi_aw_bits_addr.value))
        if int(dut.axi_w_valid.value) and int(dut.axi_w_ready.value):
            pending_write_data.append(int(dut.axi_w_bits_data.value))
        while pending_write_addrs and pending_write_data:
            addr = pending_write_addrs.pop(0)
            data = pending_write_data.pop(0)
            if timing_addr is not None and addr == timing_addr:
                if data == BENCH_TIMING_START and "start_cycle" not in timing:
                    timing["start_cycle"] = cycle
                if data == BENCH_TIMING_STOP:
                    timing["stop_cycle"] = cycle
        if int(dut.status_trap.value) == 1:
            trapped = True
            break

    assert trapped, f"{name} did not reach trap/exit within {max_cycles} cycles"
    result = read_benchmark_result(memory, manifest["result_addr"])

    assert result[0] == BENCH_MAGIC
    assert result[1] == benchmark_id
    assert result[2] == 0, f"{name} failed with result words {[hex(value) for value in result]}"
    assert int(dut.trace_trap.value) == 1
    assert int(dut.trace_trap_cause.value) == 2
    write_benchmark_score(name, manifest, result, cycles, timing)
    return result


def rtl_trace_schema(raw_trace, axi_events, expected_trace):
    data_reads = [
        event for event in axi_events
        if event["kind"] == "read_data" and event["prot"] == 2
    ]
    write_addrs = [
        event for event in axi_events
        if event["kind"] == "write_addr" and event["prot"] == 2
    ]
    write_data = [
        event for event in axi_events
        if event["kind"] == "write_data"
    ]

    read_index = 0
    write_index = 0
    records = []
    for trace, expected in zip(raw_trace, expected_trace):
        record = {
            "pc": hex32(trace["pc"]),
            "insn": hex32(trace["instr"]),
            "length": trace["len"],
            "rd_we": bool(trace["rd_we"]),
            "rd": trace["rd"] if trace["rd_we"] else None,
            "rd_wdata": hex32(trace["rd_wdata"]) if trace["rd_we"] else None,
            "mem_addr": None,
            "mem_rdata": None,
            "mem_wdata": None,
            "trap": bool(trace["trap"]),
            "trap_cause": trap_cause_name(trace["cause"]) if trace["trap"] else None,
        }

        if expected.get("mem_rdata") is not None:
            read_event = data_reads[read_index]
            read_index += 1
            expected_addr = int(expected["mem_addr"], 16)
            assert read_event["addr"] == (expected_addr & ~0x3)
            record["mem_addr"] = expected["mem_addr"]
            record["mem_rdata"] = expected["mem_rdata"]

        if expected.get("mem_wdata") is not None:
            addr_event = write_addrs[write_index]
            _data_event = write_data[write_index]
            write_index += 1
            expected_addr = int(expected["mem_addr"], 16)
            assert addr_event["addr"] == (expected_addr & ~0x3)
            record["mem_addr"] = expected["mem_addr"]
            record["mem_wdata"] = expected["mem_wdata"]

        records.append(record)

    return records


class TraceProgram:
    def __init__(self, name, image, max_steps):
        self.name = name
        self.image = image
        self.max_steps = max_steps


def rv32ec_compressed_memory_rtl_program():
    image = ProgramImage()
    image.add32(i_type(64, 0, 0x0, 2))
    image.add16(c_addi4spn(8, 16))
    image.add16(c_li(9, 7))
    image.add16(c_sw(9, 8, 0))
    image.add16(c_lw(10, 8, 0))
    image.add16(c_swsp(10, 4))
    image.add16(c_lwsp(11, 4))
    image.add16(c_ebreak())
    return TraceProgram("rv32ec_compressed_memory_rtl", image, 16)


def model_trace_for(program):
    model = RV32ECModel()
    model.load_words(program.image.words())
    model.run(program.max_steps)
    return model.trace


async def assert_rtl_trace_matches_model(dut, program):
    expected_trace = model_trace_for(program)
    axi_events = []
    await start_core(dut, pack_words(program.image.words()), axi_events=axi_events)

    raw_trace = await with_timeout(collect_trace(dut, len(expected_trace), max_cycles=1200), 40, "us")
    actual_trace = rtl_trace_schema(raw_trace, axi_events, expected_trace)

    trace_dir = REPO_ROOT / "result" / "rtl_trace"
    write_jsonl(trace_dir / f"{program.name}.expected.jsonl", expected_trace)
    write_jsonl(trace_dir / f"{program.name}.actual.jsonl", actual_trace)

    error = compare(expected_trace, actual_trace)
    assert error is None, f"{program.name}: {error}"


async def assert_rtl_trace_matches_artifact(dut, name, words, expected_trace):
    axi_events = []
    max_cycles = max(1200, len(expected_trace) * 120)
    memory_size = 4096
    for item in expected_trace:
        mem_addr = item.get("mem_addr")
        if mem_addr is not None and int(mem_addr, 16) >= memory_size:
            memory_size = 2**32
            break
    _, monitor = await start_core(
        dut,
        pack_words(words),
        size=memory_size,
        axi_events=axi_events,
        axi_monitor_cycles=max_cycles,
    )

    raw_trace = await with_timeout(
        collect_trace(dut, len(expected_trace), max_cycles=max_cycles),
        max(40, len(expected_trace) * 2),
        "us",
    )
    monitor.cancel()
    actual_trace = rtl_trace_schema(raw_trace, axi_events, expected_trace)

    trace_dir = REPO_ROOT / "result" / "rtl_trace" / "isa_artifacts"
    write_jsonl(trace_dir / f"{name}.expected.jsonl", expected_trace)
    write_jsonl(trace_dir / f"{name}.actual.jsonl", actual_trace)

    error = compare(expected_trace, actual_trace)
    assert error is None, f"{name}: {error}"


@cocotb.test()
async def reset_and_fetch_nops(dut):
    axi_events = []
    image = pack_words([NOP, NOP, NOP])
    _, monitor = await start_core(dut, image, axi_events=axi_events)

    traces = await with_timeout(collect_trace(dut, 3), 10, "us")
    monitor.cancel()

    for index, trace in enumerate(traces):
        assert_trace(trace, index * 4, NOP)

    instruction_reads = [
        event for event in axi_events
        if event["kind"] == "read_addr" and (event["prot"] & 0x4)
    ]
    assert [event["addr"] for event in instruction_reads[:3]] == [0, 4, 8]
    assert int(dut.status_trap.value) == 0


@cocotb.test()
async def rvfi_source_register_trace_reports_retired_operands(dut):
    program = [
        i_type(0x100, 0, 0x0, 1),
        i_type(0x55, 0, 0x0, 2),
        r_type(0x00, 2, 1, 0x0, 3),
        s_type(0, 2, 1, 0x2),
        i_type(0, 1, 0x2, 4, 0x03),
        EBREAK,
    ]
    memory = await start_core(dut, pack_words(program))

    traces = await with_timeout(collect_trace(dut, len(program), max_cycles=500), 20, "us")

    assert_trace(traces[0], 0, program[0], rd=1, rd_wdata=0x100)
    assert_trace(traces[1], 4, program[1], rd=2, rd_wdata=0x55)
    assert_trace(traces[2], 8, program[2], rd=3, rd_wdata=0x155, rs1=1, rs1_rdata=0x100, rs2=2, rs2_rdata=0x55)
    assert_trace(
        traces[3],
        12,
        program[3],
        rs1=1,
        rs1_rdata=0x100,
        rs2=2,
        rs2_rdata=0x55,
        mem_addr=0x100,
        mem_rmask=0x0,
        mem_wmask=0xF,
        mem_wdata=0x55,
    )
    assert_trace(
        traces[4],
        16,
        program[4],
        rd=4,
        rd_wdata=0x55,
        rs1=1,
        rs1_rdata=0x100,
        mem_addr=0x100,
        mem_rmask=0xF,
        mem_wmask=0x0,
        mem_rdata=0x55,
    )
    assert_trace(traces[5], 20, EBREAK, trap=True, cause=2)
    assert memory.read_dword(0x100, byteorder="little") == 0x55


@cocotb.test()
async def compressed_halfwords_advance_pc_by_two(dut):
    image = pack_halfwords([C_NOP, C_NOP])
    await start_core(dut, image)

    traces = await with_timeout(collect_trace(dut, 2), 10, "us")

    assert_trace(traces[0], 0, C_NOP, length=2)
    assert_trace(traces[1], 2, C_NOP, length=2)
    assert int(dut.status_trap.value) == 0


@cocotb.test()
async def straddled_32_bit_instruction_fetches_next_word(dut):
    image = pack_halfwords([C_NOP]) + pack_words([NOP])
    await start_core(dut, image)

    traces = await with_timeout(collect_trace(dut, 2), 10, "us")

    assert_trace(traces[0], 0, C_NOP, length=2)
    assert_trace(traces[1], 2, NOP, length=4)
    assert int(dut.status_trap.value) == 0


@cocotb.test()
async def rv32ec_compressed_integer_ops_execute(dut):
    program = [
        c_li(1, 5),
        c_addi(1, 3),
        c_cr(0, 2, 1),
        c_cr(1, 2, 1),
        c_slli(2, 1),
        c_li(8, 6),
        c_li(9, 3),
        c_ca(0x0, 8, 9),
        c_ca(0x1, 8, 9),
        c_ca(0x2, 8, 9),
        c_ca(0x3, 8, 9),
        c_li(10, -4),
        c_shift_andi(0x0, 10, 1),
        c_li(11, -4),
        c_shift_andi(0x1, 11, 1),
        c_shift_andi(0x2, 11, -1),
        c_ebreak(),
    ]
    expected = [
        (1, 5),
        (1, 8),
        (2, 8),
        (2, 16),
        (2, 32),
        (8, 6),
        (9, 3),
        (8, 3),
        (8, 0),
        (8, 3),
        (8, 3),
        (10, 0xFFFF_FFFC),
        (10, 0x7FFF_FFFE),
        (11, 0xFFFF_FFFC),
        (11, 0xFFFF_FFFE),
        (11, 0xFFFF_FFFE),
    ]
    await start_core(dut, pack_halfwords(program))

    traces = await with_timeout(collect_trace(dut, len(program)), 20, "us")

    for index, (rd, rd_wdata) in enumerate(expected):
        assert_trace(traces[index], index * 2, program[index], length=2, rd=rd, rd_wdata=rd_wdata)
    assert_trace(traces[-1], 32, program[-1], length=2, trap=True, cause=2)
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def rv32ec_compressed_load_store_forms_use_axi_ram(dut):
    program = pack_words([i_type(64, 0, 0x0, 2)]) + pack_halfwords(
        [
            c_addi4spn(8, 16),
            c_li(9, 7),
            c_sw(9, 8, 0),
            c_lw(10, 8, 0),
            c_swsp(10, 4),
            c_lwsp(11, 4),
            c_ebreak(),
        ]
    )
    axi_events = []
    memory, monitor = await start_core(dut, program, axi_events=axi_events)

    traces = await with_timeout(collect_trace(dut, 8), 20, "us")
    monitor.cancel()

    assert_trace(traces[0], 0, i_type(64, 0, 0x0, 2), rd=2, rd_wdata=64)
    assert_trace(traces[1], 4, c_addi4spn(8, 16), length=2, rd=8, rd_wdata=80)
    assert_trace(traces[2], 6, c_li(9, 7), length=2, rd=9, rd_wdata=7)
    assert_trace(traces[3], 8, c_sw(9, 8, 0), length=2)
    assert_trace(traces[4], 10, c_lw(10, 8, 0), length=2, rd=10, rd_wdata=7)
    assert_trace(traces[5], 12, c_swsp(10, 4), length=2)
    assert_trace(traces[6], 14, c_lwsp(11, 4), length=2, rd=11, rd_wdata=7)
    assert_trace(traces[7], 16, c_ebreak(), length=2, trap=True, cause=2)

    assert memory.read_dword(80, byteorder="little") == 7
    assert memory.read_dword(68, byteorder="little") == 7
    data_write_addrs = [
        event["addr"] for event in axi_events
        if event["kind"] == "write_addr" and event["prot"] == 2
    ]
    assert data_write_addrs == [80, 68]


@cocotb.test()
async def rv32ec_compressed_control_flow_and_link_registers(dut):
    program = [
        c_li(8, 0),
        c_branch(0x6, 8, 4),
        c_li(1, 1),
        c_li(1, 2),
        c_j(0x5, 4),
        c_li(2, 3),
        c_j(0x1, 4),
        c_li(3, 4),
        c_ebreak(),
    ]
    await start_core(dut, pack_halfwords(program))

    traces = await with_timeout(collect_trace(dut, 6), 20, "us")

    assert [trace["pc"] for trace in traces] == [0, 2, 6, 8, 12, 16]
    assert_trace(traces[0], 0, program[0], length=2, rd=8, rd_wdata=0)
    assert_trace(traces[1], 2, program[1], length=2)
    assert_trace(traces[2], 6, program[3], length=2, rd=1, rd_wdata=2)
    assert_trace(traces[3], 8, program[4], length=2)
    assert_trace(traces[4], 12, program[6], length=2, rd=1, rd_wdata=14)
    assert_trace(traces[5], 16, program[8], length=2, trap=True, cause=2)


@cocotb.test()
async def rv32ec_compressed_jr_and_jalr(dut):
    program = [
        c_li(4, 8),
        c_cr(0, 4, 0),
        c_li(1, 1),
        c_li(1, 2),
        c_li(5, 14),
        c_cr(1, 5, 0),
        c_li(2, 3),
        c_ebreak(),
    ]
    await start_core(dut, pack_halfwords(program))

    traces = await with_timeout(collect_trace(dut, 5), 20, "us")

    assert [trace["pc"] for trace in traces] == [0, 2, 8, 10, 14]
    assert_trace(traces[0], 0, program[0], length=2, rd=4, rd_wdata=8)
    assert_trace(traces[1], 2, program[1], length=2)
    assert_trace(traces[2], 8, program[4], length=2, rd=5, rd_wdata=14)
    assert_trace(traces[3], 10, program[5], length=2, rd=1, rd_wdata=12)
    assert_trace(traces[4], 14, program[7], length=2, trap=True, cause=2)


@cocotb.test()
async def rv32ec_compressed_direct_x16_register_traps(dut):
    bad_program = [c_lwsp(16, 0)]
    await start_core(dut, pack_halfwords(bad_program))

    bad_trace = await with_timeout(collect_trace(dut, 1), 10, "us")

    assert_trace(bad_trace[0], 0, bad_program[0], length=2, trap=True, cause=3)


async def assert_single_compressed_trap(dut, insn, cause):
    await start_core(dut, pack_halfwords([insn]))

    trace = await with_timeout(collect_trace(dut, 1), 10, "us")

    assert_trace(trace[0], 0, insn, length=2, trap=True, cause=cause)
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def rv32ec_compressed_all_zero_traps(dut):
    await assert_single_compressed_trap(dut, 0x0000, 1)


@cocotb.test()
async def rv32ec_compressed_addi4spn_zero_traps(dut):
    await assert_single_compressed_trap(dut, c_addi4spn(8, 0), 1)


@cocotb.test()
async def rv32ec_compressed_addi16sp_zero_traps(dut):
    await assert_single_compressed_trap(dut, c_ci(0x3, 2, 0), 1)


@cocotb.test()
async def rv32ec_compressed_lui_zero_traps(dut):
    await assert_single_compressed_trap(dut, c_ci(0x3, 3, 0), 1)


@cocotb.test()
async def rv32ec_compressed_lwsp_x0_traps(dut):
    await assert_single_compressed_trap(dut, c_lwsp(0, 0), 1)


@cocotb.test()
async def rv32ec_compressed_jr_x0_traps(dut):
    await assert_single_compressed_trap(dut, c_cr(0, 0, 0), 1)


@cocotb.test()
async def rv32ec_compressed_rv64_shift_encoding_traps(dut):
    await assert_single_compressed_trap(dut, c_shift_andi(0x0, 8, 32), 1)


@cocotb.test()
async def rv32ec_compressed_floating_point_encoding_traps(dut):
    c_fld = 0x1 << 13
    await assert_single_compressed_trap(dut, c_fld, 1)


@cocotb.test()
async def rv32e_alu_rtl_trace_matches_reference_model(dut):
    await assert_rtl_trace_matches_model(dut, rv32e_alu_program())


@cocotb.test()
async def rv32e_branch_memory_rtl_trace_matches_reference_model(dut):
    await assert_rtl_trace_matches_model(dut, rv32e_branch_memory_program())


@cocotb.test()
async def rv32ec_compressed_rtl_trace_matches_reference_model(dut):
    await assert_rtl_trace_matches_model(dut, rv32ec_compressed_program())


@cocotb.test()
async def rv32ec_compressed_memory_rtl_trace_matches_reference_model(dut):
    await assert_rtl_trace_matches_model(dut, rv32ec_compressed_memory_rtl_program())


if os.environ.get("DITDAH32_ISA_ARTIFACT"):
    @cocotb.test()
    async def isa_artifact_rtl_trace_matches_reference_model(dut):
        name, words, expected_trace = load_isa_artifact()
        await assert_rtl_trace_matches_artifact(dut, name, words, expected_trace)


@cocotb.test()
async def coremark_profile_binary_passes_on_rtl(dut):
    result = await run_benchmark_until_trap(dut, "coremark", BENCH_COREMARK, max_cycles=2_000_000)

    assert result[3] == 1
    assert result[4] == 10
    assert result[5] == 1
    assert result[6] == 0


@cocotb.test()
async def dhrystone_one_run_binary_passes_on_rtl(dut):
    result = await run_benchmark_until_trap(dut, "dhrystone", BENCH_DHRYSTONE, max_cycles=200_000)

    assert result[3] == 1
    assert result[4] == 11
    assert result[5] == 0


@cocotb.test()
async def minimal_ex_wb_writes_registers_and_traps_on_ebreak(dut):
    program = [ADDI_X1_X0_5, ADDI_X2_X1_3, LUI_X3_12345, EBREAK]
    await start_core(dut, pack_words(program))

    traces = await with_timeout(collect_trace(dut, len(program)), 10, "us")

    assert_trace(traces[0], 0, ADDI_X1_X0_5, rd=1, rd_wdata=5)
    assert_trace(traces[1], 4, ADDI_X2_X1_3, rd=2, rd_wdata=8)
    assert_trace(traces[2], 8, LUI_X3_12345, rd=3, rd_wdata=0x12345000)
    assert_trace(traces[3], 12, EBREAK, trap=True, cause=2)
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def rv32e_alu_immediate_and_register_ops(dut):
    program = [
        i_type(-1, 0, 0x0, 1),                # addi
        i_type(1, 1, 0x5, 2),                 # srli
        i_type((0x20 << 5) | 1, 1, 0x5, 3),  # srai
        i_type(4, 3, 0x1, 4),                 # slli
        i_type(0, 1, 0x2, 5),                 # slti
        i_type(0, 1, 0x3, 6),                 # sltiu
        i_type(0x0FF, 4, 0x4, 7),             # xori
        i_type(0x0F0, 7, 0x6, 8),             # ori
        i_type(0x0F0, 8, 0x7, 9),             # andi
        r_type(0x00, 9, 9, 0x0, 10),          # add
        r_type(0x20, 9, 10, 0x0, 11),         # sub
        r_type(0x00, 5, 11, 0x1, 12),         # sll
        r_type(0x00, 0, 1, 0x2, 13),          # slt
        r_type(0x00, 0, 1, 0x3, 14),          # sltu
        r_type(0x00, 11, 12, 0x4, 15),        # xor
        r_type(0x00, 11, 15, 0x6, 10),        # or
        r_type(0x00, 12, 10, 0x7, 11),        # and
        r_type(0x00, 5, 1, 0x5, 12),          # srl
        r_type(0x20, 5, 1, 0x5, 13),          # sra
        FENCE,
        ECALL,
    ]
    expected = [
        (1, 0xFFFF_FFFF),
        (2, 0x7FFF_FFFF),
        (3, 0xFFFF_FFFF),
        (4, 0xFFFF_FFF0),
        (5, 1),
        (6, 0),
        (7, 0xFFFF_FF0F),
        (8, 0xFFFF_FFFF),
        (9, 0x0000_00F0),
        (10, 0x0000_01E0),
        (11, 0x0000_00F0),
        (12, 0x0000_01E0),
        (13, 1),
        (14, 0),
        (15, 0x0000_0110),
        (10, 0x0000_01F0),
        (11, 0x0000_01E0),
        (12, 0x7FFF_FFFF),
        (13, 0xFFFF_FFFF),
    ]
    await start_core(dut, pack_words(program))

    traces = await with_timeout(collect_trace(dut, len(program)), 20, "us")

    for index, (rd, rd_wdata) in enumerate(expected):
        assert_trace(traces[index], index * 4, program[index], rd=rd, rd_wdata=rd_wdata)
    assert_trace(traces[19], 76, FENCE)
    assert_trace(traces[20], 80, ECALL, trap=True, cause=4)
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def rv32e_register_index_violation_traps(dut):
    program = [i_type(1, 0, 0x0, 16)]
    await start_core(dut, pack_words(program))

    traces = await with_timeout(collect_trace(dut, 1), 10, "us")

    assert_trace(traces[0], 0, program[0], trap=True, cause=3)
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def rv32e_unknown_32bit_instruction_traps(dut):
    program = [0xFFFF_FFFF]
    await start_core(dut, pack_words(program))

    traces = await with_timeout(collect_trace(dut, 1), 10, "us")

    assert_trace(traces[0], 0, program[0], trap=True, cause=1)
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def rv32e_fence_i_traps(dut):
    fence_i = 0x0000_100F

    await start_core(dut, pack_words([fence_i]))
    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(traces[0], 0, fence_i, trap=True, cause=1)


@cocotb.test()
async def zicsr_machine_csrs_read_write_and_immediate_ops(dut):
    program = [
        i_type(0x40, 0, 0x0, 1),
        csrrw(CSR_MTVEC, 1, 0),
        csrrs(CSR_MTVEC, 0, 2),
        csrrwi(CSR_MSCRATCH, 5, 3),
        csrrs(CSR_MSCRATCH, 0, 4),
        csrrci(CSR_MSCRATCH, 1, 5),
        csrrs(CSR_MSCRATCH, 0, 6),
        i_type(4, 0, 0x0, 7),
        csrrc(CSR_MSCRATCH, 7, 8),
        csrrs(CSR_MSCRATCH, 0, 9),
        EBREAK,
    ]

    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, len(program)), 20, "us")

    assert_trace(traces[0], 0, program[0], rd=1, rd_wdata=0x40)
    assert_trace(
        traces[1],
        4,
        program[1],
        csr_addr=CSR_MTVEC,
        csr_rmask=CSR_FULL_MASK,
        csr_rdata=0,
        csr_wmask=CSR_FULL_MASK,
        csr_wdata=0x40,
    )
    assert_trace(
        traces[2],
        8,
        program[2],
        rd=2,
        rd_wdata=0x40,
        csr_addr=CSR_MTVEC,
        csr_rmask=CSR_FULL_MASK,
        csr_rdata=0x40,
        csr_wmask=0,
    )
    assert_trace(
        traces[3],
        12,
        program[3],
        rd=3,
        rd_wdata=0,
        csr_addr=CSR_MSCRATCH,
        csr_rmask=CSR_FULL_MASK,
        csr_rdata=0,
        csr_wmask=CSR_FULL_MASK,
        csr_wdata=5,
    )
    assert_trace(
        traces[4],
        16,
        program[4],
        rd=4,
        rd_wdata=5,
        csr_addr=CSR_MSCRATCH,
        csr_rmask=CSR_FULL_MASK,
        csr_rdata=5,
        csr_wmask=0,
    )
    assert_trace(
        traces[5],
        20,
        program[5],
        rd=5,
        rd_wdata=5,
        csr_addr=CSR_MSCRATCH,
        csr_rmask=CSR_FULL_MASK,
        csr_rdata=5,
        csr_wmask=CSR_FULL_MASK,
        csr_wdata=4,
    )
    assert_trace(
        traces[6],
        24,
        program[6],
        rd=6,
        rd_wdata=4,
        csr_addr=CSR_MSCRATCH,
        csr_rmask=CSR_FULL_MASK,
        csr_rdata=4,
        csr_wmask=0,
    )
    assert_trace(traces[7], 28, program[7], rd=7, rd_wdata=4)
    assert_trace(
        traces[8],
        32,
        program[8],
        rd=8,
        rd_wdata=4,
        csr_addr=CSR_MSCRATCH,
        csr_rmask=CSR_FULL_MASK,
        csr_rdata=4,
        csr_wmask=CSR_FULL_MASK,
        csr_wdata=0,
    )
    assert_trace(
        traces[9],
        36,
        program[9],
        rd=9,
        rd_wdata=0,
        csr_addr=CSR_MSCRATCH,
        csr_rmask=CSR_FULL_MASK,
        csr_rdata=0,
        csr_wmask=0,
    )
    assert_trace(traces[10], 40, program[10], trap=True, cause=2)


@cocotb.test()
async def zicsr_read_only_csr_write_traps(dut):
    program = [csrrwi(CSR_MISA, 1, 1)]

    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(traces[0], 0, program[0], trap=True, cause=1)


async def _expect_readonly_csrrw_traps(dut, csr):
    program = [csrrw(csr, 0, 1)]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(traces[0], 0, program[0], trap=True, cause=1)


@cocotb.test()
async def zicsr_read_only_csr_csrrw_misa_traps(dut):
    await _expect_readonly_csrrw_traps(dut, CSR_MISA)


@cocotb.test()
async def zicsr_read_only_csr_csrrw_mip_traps(dut):
    await _expect_readonly_csrrw_traps(dut, CSR_MIP)


@cocotb.test()
async def zicsr_read_only_csr_csrrw_mvendorid_traps(dut):
    await _expect_readonly_csrrw_traps(dut, CSR_MVENDORID)


@cocotb.test()
async def zicsr_read_only_csr_csrrw_marchid_traps(dut):
    await _expect_readonly_csrrw_traps(dut, CSR_MARCHID)


@cocotb.test()
async def zicsr_read_only_csr_csrrw_mimpid_traps(dut):
    await _expect_readonly_csrrw_traps(dut, CSR_MIMPID)


@cocotb.test()
async def zicsr_read_only_csr_csrrw_mhartid_traps(dut):
    await _expect_readonly_csrrw_traps(dut, CSR_MHARTID)


@cocotb.test()
async def zicsr_read_only_csr_csrrs_nonzero_rs1_traps(dut):
    # CSRRS with rs1 != x0 is an architectural write attempt even when the
    # runtime value of rs1 is zero. Verifies the fix to csrWriteEnable using
    # rs1Index instead of the runtime operand.
    program = [
        i_type(0, 0, 0x0, 5),     # addi x5, x0, 0  (set rs5 = 0 at runtime)
        csrrs(CSR_MISA, 5, 1),    # CSRRS x1, misa, x5  (rs5=0 but rs1 != x0)
    ]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 2), 10, "us")
    assert_trace(traces[0], 0, program[0], rd=5, rd_wdata=0)
    assert_trace(traces[1], 4, program[1], trap=True, cause=1)


@cocotb.test()
async def zicsr_read_only_csr_csrrs_x0_no_trap(dut):
    # CSRRS rs1=x0 is a pure read on the read-only CSR; must not trap. Reads
    # the misa value (RV32EC = 0x40000014: MXL=01, C+E bits set).
    program = [csrrs(CSR_MISA, 0, 1), EBREAK]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 2), 10, "us")
    assert_trace(traces[0], 0, program[0], rd=1, rd_wdata=0x40000014)
    assert_trace(traces[1], 4, EBREAK, trap=True, cause=2)


@cocotb.test()
async def zicsr_read_only_csr_csrrc_x0_no_trap(dut):
    # CSRRC rs1=x0 is a pure read on the read-only CSR; must not trap.
    program = [csrrc(CSR_MHARTID, 0, 1), EBREAK]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 2), 10, "us")
    assert_trace(traces[0], 0, program[0], rd=1, rd_wdata=0)
    assert_trace(traces[1], 4, EBREAK, trap=True, cause=2)


@cocotb.test()
async def zicsr_read_only_csr_csrrsi_zero_imm_no_trap(dut):
    # CSRRSI uimm=0 is a pure read on the read-only CSR; must not trap.
    program = [csrrsi(CSR_MVENDORID, 0, 1), EBREAK]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 2), 10, "us")
    assert_trace(traces[0], 0, program[0], rd=1, rd_wdata=0)
    assert_trace(traces[1], 4, EBREAK, trap=True, cause=2)


@cocotb.test()
async def zicsr_read_only_csr_csrrsi_nonzero_imm_traps(dut):
    # CSRRSI uimm != 0 is a write attempt on a read-only CSR; must trap.
    program = [csrrsi(CSR_MARCHID, 1, 1)]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(traces[0], 0, program[0], trap=True, cause=1)


@cocotb.test()
async def zicsr_read_only_csr_csrrci_nonzero_imm_traps(dut):
    # CSRRCI uimm != 0 is a write attempt on a read-only CSR; must trap.
    program = [csrrci(CSR_MIMPID, 1, 1)]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(traces[0], 0, program[0], trap=True, cause=1)


@cocotb.test()
async def zicsr_unimplemented_csr_access_traps(dut):
    program = [csrrs(CSR_UNIMPLEMENTED, 0, 1)]

    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(traces[0], 0, program[0], trap=True, cause=1)


@cocotb.test()
async def zicsr_rv32e_rd_index_violation_traps(dut):
    program = [csrrs(CSR_MSCRATCH, 0, 16)]

    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(traces[0], 0, program[0], trap=True, cause=3)


@cocotb.test()
async def zicsr_rv32e_rs1_index_violation_traps(dut):
    program = [csrrw(CSR_MSCRATCH, 16, 1)]

    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    assert_trace(traces[0], 0, program[0], trap=True, cause=3)


@cocotb.test()
async def zicsr_zimm16_is_not_rv32e_register_violation(dut):
    program = [csrrwi(CSR_MSCRATCH, 16, 1), EBREAK]

    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, 2), 10, "us")
    assert_trace(traces[0], 0, program[0], rd=1, rd_wdata=0)
    assert_trace(traces[1], 4, EBREAK, trap=True, cause=2)


@cocotb.test()
async def zicsr_mtvec_and_mepc_mask_low_bits(dut):
    program = [
        i_type(0x43, 0, 0x0, 1),
        csrrw(CSR_MTVEC, 1, 0),
        csrrs(CSR_MTVEC, 0, 2),
        i_type(0x15, 0, 0x0, 3),
        csrrw(CSR_MEPC, 3, 0),
        csrrs(CSR_MEPC, 0, 4),
        EBREAK,
    ]

    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, len(program)), 20, "us")

    assert_trace(traces[2], 8, program[2], rd=2, rd_wdata=0x40)
    assert_trace(traces[5], 20, program[5], rd=4, rd_wdata=0x14)
    assert_trace(traces[6], 24, program[6], trap=True, cause=2)


@cocotb.test()
async def zicsr_warl_mstatus_mpp_forced_m_mode(dut):
    # Software writes MPP=10 (U-mode) and reserved bits to mstatus, then reads
    # back. The WARL legalization must force MPP=11 (M-mode) for this M-only
    # core and zero the reserved bits.
    program = [
        # lui x1, 0xFFFFF; addi x1, x1, -1 -> x1 = 0xFFFFFFFF
        u_type(0xFFFFF000, 1, 0x37),
        i_type(-1 & 0xFFF, 1, 0x0, 1),
        csrrw(CSR_MSTATUS, 1, 0),
        csrrs(CSR_MSTATUS, 0, 2),
        EBREAK,
    ]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, len(program)), 20, "us")
    # After writing all-ones to mstatus, only MIE (bit 3), MPIE (bit 7), and
    # MPP forced 11 (bits 12:11) should remain. Reserved bits read 0.
    expected = (1 << 3) | (1 << 7) | (3 << 11)
    assert_trace(traces[3], 12, program[3], rd=2, rd_wdata=expected)


@cocotb.test()
async def zicsr_warl_mstatus_clears_to_only_mpp(dut):
    # Software writes 0 to mstatus, expecting MPP to read back as 11 anyway.
    program = [
        csrrw(CSR_MSTATUS, 0, 0),
        csrrs(CSR_MSTATUS, 0, 1),
        EBREAK,
    ]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, len(program)), 10, "us")
    assert_trace(traces[1], 4, program[1], rd=1, rd_wdata=(3 << 11))


@cocotb.test()
async def zicsr_warl_mie_masks_to_msi_mti_mei(dut):
    # mie is WARL: only bits 3, 7, 11 (MSI/MTI/MEI) are writable in DitDah32.
    # All other bits must read back as 0.
    program = [
        u_type(0xFFFFF000, 1, 0x37),
        i_type(-1 & 0xFFF, 1, 0x0, 1),
        csrrw(CSR_MIE, 1, 0),
        csrrs(CSR_MIE, 0, 2),
        EBREAK,
    ]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, len(program)), 20, "us")
    assert_trace(traces[3], 12, program[3], rd=2, rd_wdata=0x888)


@cocotb.test()
async def zicsr_warl_mtvec_mode_forced_direct(dut):
    # mtvec.MODE (bits 1:0) must read back as 0 (direct), regardless of write.
    # Test with MODE=01 (vectored) and 11 (reserved).
    program = [
        u_type(0xABCDE000, 1, 0x37),  # x1 = 0xABCDE000
        i_type(0x3, 1, 0x6, 1),       # ori x1, x1, 0x3 -> x1 = 0xABCDE003
        csrrw(CSR_MTVEC, 1, 0),
        csrrs(CSR_MTVEC, 0, 2),
        EBREAK,
    ]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, len(program)), 20, "us")
    # mtvec.BASE keeps upper 30 bits, MODE forced 00 -> 0xABCDE000.
    assert_trace(traces[3], 12, program[3], rd=2, rd_wdata=0xABCDE000)


@cocotb.test()
async def zicsr_warl_mepc_low_bit_forced_zero(dut):
    # mepc must always be at least 2-byte aligned (RVC), so bit 0 reads back
    # as 0 regardless of the value written.
    program = [
        u_type(0x12345000, 1, 0x37),  # x1 = 0x12345000
        i_type(0x77, 1, 0x6, 1),      # ori x1, x1, 0x77 -> x1 = 0x12345077
        csrrw(CSR_MEPC, 1, 0),
        csrrs(CSR_MEPC, 0, 2),
        EBREAK,
    ]
    await start_core(dut, pack_words(program))
    traces = await with_timeout(collect_trace(dut, len(program)), 20, "us")
    # Bit 0 cleared: 0x12345077 -> 0x12345076.
    assert_trace(traces[3], 12, program[3], rd=2, rd_wdata=0x12345076)


@cocotb.test()
async def wfi_sleeps_until_enabled_software_interrupt_and_mret_returns(dut):
    program_by_pc = {
        0x00: i_type(0x40, 0, 0x0, 1),
        0x04: csrrw(CSR_MTVEC, 1, 0),
        0x08: csrrsi(CSR_MIE, 8, 0),
        0x0C: csrrsi(CSR_MSTATUS, 8, 0),
        0x10: WFI,
        0x14: i_type(1, 0, 0x0, 2),
        0x18: EBREAK,
        0x40: csrrs(CSR_MCAUSE, 0, 3),
        0x44: csrrs(CSR_MEPC, 0, 4),
        0x48: MRET,
    }
    image = sparse_image((pc, pack_words([instr])) for pc, instr in program_by_pc.items())
    await start_core(dut, image)

    prefix = await with_timeout(collect_trace(dut, 5), 20, "us")
    assert_trace(prefix[0], 0x00, program_by_pc[0x00], rd=1, rd_wdata=0x40)
    assert_trace(prefix[4], 0x10, WFI)

    for _ in range(5):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.status_sleep.value) == 1
        assert int(dut.axi_ar_valid.value) == 0

    dut.irq_software.value = 1
    suffix = await with_timeout(collect_trace(dut, 3, max_cycles=200), 20, "us")
    dut.irq_software.value = 0
    tail = await with_timeout(collect_trace(dut, 2, max_cycles=120), 20, "us")

    assert_trace(suffix[0], 0x14, 0, length=0, trap=True, cause=INTERRUPT_CAUSE)
    assert_trace(suffix[1], 0x40, program_by_pc[0x40], rd=3, rd_wdata=MCAUSE_IRQ_SOFTWARE)
    assert_trace(suffix[2], 0x44, program_by_pc[0x44], rd=4, rd_wdata=0x14)
    assert_trace(tail[0], 0x48, MRET)
    assert_trace(tail[1], 0x14, program_by_pc[0x14], rd=2, rd_wdata=1)


@cocotb.test()
async def wfi_sleeps_until_enabled_machine_timer_interrupt_and_mret_returns(dut):
    program_by_pc = {
        0x00: i_type(0x40, 0, 0x0, 1),
        0x04: csrrw(CSR_MTVEC, 1, 0),
        0x08: i_type(0x80, 0, 0x0, 2),
        0x0C: csrrw(CSR_MIE, 2, 0),
        0x10: csrrsi(CSR_MSTATUS, 8, 0),
        0x14: WFI,
        0x18: i_type(1, 0, 0x0, 3),
        0x1C: EBREAK,
        0x40: csrrs(CSR_MCAUSE, 0, 4),
        0x44: csrrs(CSR_MEPC, 0, 5),
        0x48: MRET,
    }
    image = sparse_image((pc, pack_words([instr])) for pc, instr in program_by_pc.items())
    await start_core(dut, image)

    prefix = await with_timeout(collect_trace(dut, 6), 20, "us")
    assert_trace(prefix[5], 0x14, WFI)

    for _ in range(5):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.status_sleep.value) == 1
        assert int(dut.axi_ar_valid.value) == 0

    dut.irq_timer.value = 1
    suffix = await with_timeout(collect_trace(dut, 3, max_cycles=200), 20, "us")
    dut.irq_timer.value = 0
    tail = await with_timeout(collect_trace(dut, 2, max_cycles=120), 20, "us")

    assert_trace(suffix[0], 0x18, 0, length=0, trap=True, cause=INTERRUPT_CAUSE)
    assert_trace(suffix[1], 0x40, program_by_pc[0x40], rd=4, rd_wdata=MCAUSE_IRQ_TIMER)
    assert_trace(suffix[2], 0x44, program_by_pc[0x44], rd=5, rd_wdata=0x18)
    assert_trace(tail[0], 0x48, MRET)
    assert_trace(tail[1], 0x18, program_by_pc[0x18], rd=3, rd_wdata=1)


@cocotb.test()
async def wfi_sleeps_until_enabled_machine_external_interrupt_and_mret_returns(dut):
    program_by_pc = {
        0x00: i_type(0x40, 0, 0x0, 1),
        0x04: csrrw(CSR_MTVEC, 1, 0),
        0x08: u_type(0x1000, 2, 0x37),
        0x0C: i_type(-0x800, 2, 0x0, 2),
        0x10: csrrw(CSR_MIE, 2, 0),
        0x14: csrrsi(CSR_MSTATUS, 8, 0),
        0x18: WFI,
        0x1C: i_type(1, 0, 0x0, 3),
        0x20: EBREAK,
        0x40: csrrs(CSR_MCAUSE, 0, 4),
        0x44: csrrs(CSR_MEPC, 0, 5),
        0x48: MRET,
    }
    image = sparse_image((pc, pack_words([instr])) for pc, instr in program_by_pc.items())
    await start_core(dut, image)

    prefix = await with_timeout(collect_trace(dut, 7), 20, "us")
    assert_trace(prefix[6], 0x18, WFI)

    for _ in range(5):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.status_sleep.value) == 1
        assert int(dut.axi_ar_valid.value) == 0

    dut.irq_external.value = 1
    suffix = await with_timeout(collect_trace(dut, 3, max_cycles=200), 20, "us")
    dut.irq_external.value = 0
    tail = await with_timeout(collect_trace(dut, 2, max_cycles=120), 20, "us")

    assert_trace(suffix[0], 0x1C, 0, length=0, trap=True, cause=INTERRUPT_CAUSE)
    assert_trace(suffix[1], 0x40, program_by_pc[0x40], rd=4, rd_wdata=MCAUSE_IRQ_EXTERNAL)
    assert_trace(suffix[2], 0x44, program_by_pc[0x44], rd=5, rd_wdata=0x1C)
    assert_trace(tail[0], 0x48, MRET)
    assert_trace(tail[1], 0x1C, program_by_pc[0x1C], rd=3, rd_wdata=1)


@cocotb.test()
async def wfi_wakes_without_trap_when_global_mie_is_clear(dut):
    program_by_pc = {
        0x00: i_type(0x40, 0, 0x0, 1),
        0x04: csrrw(CSR_MTVEC, 1, 0),
        0x08: csrrsi(CSR_MIE, 8, 0),
        0x0C: WFI,
        0x10: i_type(1, 0, 0x0, 2),
        0x14: EBREAK,
        0x40: i_type(2, 0, 0x0, 3),
    }
    image = sparse_image((pc, pack_words([instr])) for pc, instr in program_by_pc.items())
    await start_core(dut, image)

    prefix = await with_timeout(collect_trace(dut, 4), 20, "us")
    assert_trace(prefix[3], 0x0C, WFI)

    for _ in range(5):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.status_sleep.value) == 1
        assert int(dut.axi_ar_valid.value) == 0

    dut.irq_software.value = 1
    suffix = await with_timeout(collect_trace(dut, 2, max_cycles=160), 20, "us")
    dut.irq_software.value = 0

    assert_trace(suffix[0], 0x10, program_by_pc[0x10], rd=2, rd_wdata=1)
    assert_trace(suffix[1], 0x14, program_by_pc[0x14], trap=True, cause=2)


@cocotb.test()
async def level_sensitive_interrupt_reenters_after_mret_if_source_stays_high(dut):
    program_by_pc = {
        0x00: i_type(0x40, 0, 0x0, 1),
        0x04: csrrw(CSR_MTVEC, 1, 0),
        0x08: csrrsi(CSR_MIE, 8, 0),
        0x0C: csrrsi(CSR_MSTATUS, 8, 0),
        0x10: WFI,
        0x14: i_type(1, 0, 0x0, 2),
        0x40: csrrs(CSR_MCAUSE, 0, 3),
        0x44: csrrs(CSR_MEPC, 0, 4),
        0x48: MRET,
    }
    image = sparse_image((pc, pack_words([instr])) for pc, instr in program_by_pc.items())
    await start_core(dut, image)

    prefix = await with_timeout(collect_trace(dut, 5), 20, "us")
    assert_trace(prefix[4], 0x10, WFI)

    dut.irq_software.value = 1
    traces = await with_timeout(collect_trace(dut, 6, max_cycles=240), 20, "us")
    dut.irq_software.value = 0

    assert_trace(traces[0], 0x14, 0, length=0, trap=True, cause=INTERRUPT_CAUSE)
    assert_trace(traces[1], 0x40, program_by_pc[0x40], rd=3, rd_wdata=MCAUSE_IRQ_SOFTWARE)
    assert_trace(traces[2], 0x44, program_by_pc[0x44], rd=4, rd_wdata=0x14)
    assert_trace(traces[3], 0x48, MRET)
    assert_trace(traces[4], 0x14, 0, length=0, trap=True, cause=INTERRUPT_CAUSE)
    assert_trace(traces[5], 0x40, program_by_pc[0x40], rd=3, rd_wdata=MCAUSE_IRQ_SOFTWARE)


@cocotb.test()
async def timer_interrupt_redirects_through_direct_mtvec(dut):
    program_by_pc = {
        0x00: i_type(0x40, 0, 0x0, 1),
        0x04: csrrw(CSR_MTVEC, 1, 0),
        0x08: i_type(0x80, 0, 0x0, 2),
        0x0C: csrrw(CSR_MIE, 2, 0),
        0x10: csrrsi(CSR_MSTATUS, 8, 0),
        0x14: i_type(1, 0, 0x0, 5),
        0x40: csrrs(CSR_MCAUSE, 0, 3),
        0x44: csrrs(CSR_MEPC, 0, 4),
    }
    image = sparse_image((pc, pack_words([instr])) for pc, instr in program_by_pc.items())
    await start_core(dut, image)
    dut.irq_timer.value = 1

    traces = await with_timeout(collect_trace(dut, 8, max_cycles=200), 20, "us")
    dut.irq_timer.value = 0

    assert_trace(traces[5], 0x14, 0, length=0, trap=True, cause=INTERRUPT_CAUSE)
    assert_trace(traces[6], 0x40, program_by_pc[0x40], rd=3, rd_wdata=MCAUSE_IRQ_TIMER)
    assert_trace(traces[7], 0x44, program_by_pc[0x44], rd=4, rd_wdata=0x14)


@cocotb.test()
async def external_interrupt_has_priority_over_software_and_timer(dut):
    program_by_pc = {
        0x00: i_type(0x40, 0, 0x0, 1),
        0x04: csrrw(CSR_MTVEC, 1, 0),
        0x08: u_type(0x1000, 2, 0x37),
        0x0C: i_type(-0x778, 2, 0x0, 2),
        0x10: csrrw(CSR_MIE, 2, 0),
        0x14: csrrsi(CSR_MSTATUS, 8, 0),
        0x18: i_type(1, 0, 0x0, 5),
        0x40: csrrs(CSR_MCAUSE, 0, 3),
        0x44: csrrs(CSR_MEPC, 0, 4),
    }
    image = sparse_image((pc, pack_words([instr])) for pc, instr in program_by_pc.items())
    await start_core(dut, image)
    dut.irq_software.value = 1
    dut.irq_timer.value = 1
    dut.irq_external.value = 1

    traces = await with_timeout(collect_trace(dut, 9, max_cycles=240), 20, "us")
    dut.irq_software.value = 0
    dut.irq_timer.value = 0
    dut.irq_external.value = 0

    assert_trace(traces[6], 0x18, 0, length=0, trap=True, cause=INTERRUPT_CAUSE)
    assert_trace(traces[7], 0x40, program_by_pc[0x40], rd=3, rd_wdata=MCAUSE_IRQ_EXTERNAL)
    assert_trace(traces[8], 0x44, program_by_pc[0x44], rd=4, rd_wdata=0x18)


@cocotb.test()
async def rv32e_control_flow_updates_pc_and_link_registers(dut):
    program_by_pc = {
        0: i_type(1, 0, 0x0, 1),
        4: i_type(1, 0, 0x0, 2),
        8: b_type(8, 2, 1, 0x0),
        12: EBREAK,
        16: i_type(-1, 0, 0x0, 3),
        20: b_type(8, 2, 3, 0x4),
        24: EBREAK,
        28: b_type(8, 2, 3, 0x6),
        32: b_type(8, 2, 3, 0x7),
        36: EBREAK,
        40: b_type(8, 2, 1, 0x1),
        44: b_type(8, 2, 3, 0x5),
        48: j_type(8, 4),
        52: EBREAK,
        56: i_type(8, 4, 0x0, 5, 0x67),
        60: EBREAK,
    }
    image = sparse_image((pc, pack_words([instr])) for pc, instr in program_by_pc.items())
    await start_core(dut, image)

    traces = await with_timeout(collect_trace(dut, 12), 20, "us")

    expected_pcs = [0, 4, 8, 16, 20, 28, 32, 40, 44, 48, 56, 60]
    expected_next_pcs = [4, 8, 16, 20, 28, 32, 40, 44, 48, 56, 60, 0]
    assert [trace["pc"] for trace in traces] == expected_pcs
    assert [trace["next_pc"] for trace in traces] == expected_next_pcs
    assert_trace(traces[0], 0, program_by_pc[0], rd=1, rd_wdata=1, next_pc=4)
    assert_trace(traces[1], 4, program_by_pc[4], rd=2, rd_wdata=1, next_pc=8)
    assert_trace(traces[3], 16, program_by_pc[16], rd=3, rd_wdata=0xFFFF_FFFF, next_pc=20)
    assert_trace(traces[9], 48, program_by_pc[48], rd=4, rd_wdata=52, next_pc=56)
    assert_trace(traces[10], 56, program_by_pc[56], rd=5, rd_wdata=60, next_pc=60)
    assert_trace(traces[11], 60, EBREAK, trap=True, cause=2, next_pc=0)


@cocotb.test()
async def rv32e_load_store_uses_shared_axi_lite_ram(dut):
    program = [
        i_type(0x100, 0, 0x0, 1),
        i_type(0x123, 0, 0x0, 2),
        s_type(19, 2, 1, 0x0),          # sb x2, 19(x1)
        s_type(18, 2, 1, 0x1),          # sh x2, 18(x1)
        s_type(16, 2, 1, 0x2),          # sw x2, 16(x1)
        i_type(5, 1, 0x0, 3, 0x03),     # lb x3, 5(x1)
        i_type(5, 1, 0x4, 4, 0x03),     # lbu x4, 5(x1)
        i_type(10, 1, 0x1, 5, 0x03),    # lh x5, 10(x1)
        i_type(10, 1, 0x5, 6, 0x03),    # lhu x6, 10(x1)
        i_type(0, 1, 0x2, 7, 0x03),     # lw x7, 0(x1)
        EBREAK,
    ]
    image = sparse_image(
        [
            (0, pack_words(program)),
            (0x100, pack_words([0x89ABCDEF])),
            (0x104, pack_words([0x00008000])),
            (0x108, pack_words([0x80000000])),
        ]
    )
    axi_events = []
    memory, monitor = await start_core(dut, image, axi_events=axi_events)

    traces = await with_timeout(collect_trace(dut, len(program)), 20, "us")
    monitor.cancel()

    assert_trace(traces[0], 0, program[0], rd=1, rd_wdata=0x100)
    assert_trace(traces[1], 4, program[1], rd=2, rd_wdata=0x123)
    assert_trace(traces[2], 8, program[2])
    assert_trace(traces[3], 12, program[3])
    assert_trace(traces[4], 16, program[4])
    assert_trace(traces[5], 20, program[5], rd=3, rd_wdata=0xFFFF_FF80)
    assert_trace(traces[6], 24, program[6], rd=4, rd_wdata=0x80)
    assert_trace(traces[7], 28, program[7], rd=5, rd_wdata=0xFFFF_8000)
    assert_trace(traces[8], 32, program[8], rd=6, rd_wdata=0x8000)
    assert_trace(traces[9], 36, program[9], rd=7, rd_wdata=0x89ABCDEF)
    assert_trace(traces[10], 40, EBREAK, trap=True, cause=2)

    assert memory.read_dword(0x110, byteorder="little") == 0x123
    assert memory.read_dword(0x104, byteorder="little") == 0x00008000
    assert memory.read_dword(0x108, byteorder="little") == 0x80000000

    writes = [event for event in axi_events if event["kind"] == "write_addr"]
    write_data = [event for event in axi_events if event["kind"] == "write_data"]
    assert writes == [
        {"kind": "write_addr", "addr": 0x110, "prot": 2},
        {"kind": "write_addr", "addr": 0x110, "prot": 2},
        {"kind": "write_addr", "addr": 0x110, "prot": 2},
    ]
    assert write_data == [
        {"kind": "write_data", "data": 0x23000000, "strb": 0x8},
        {"kind": "write_data", "data": 0x01230000, "strb": 0xC},
        {"kind": "write_data", "data": 0x00000123, "strb": 0xF},
    ]


@cocotb.test()
async def axi_lite_backpressure_event_log_stays_protocol_clean(dut):
    program = [
        i_type(0x100, 0, 0x0, 1),
        i_type(0x123, 0, 0x0, 2),
        s_type(19, 2, 1, 0x0),
        s_type(18, 2, 1, 0x1),
        s_type(16, 2, 1, 0x2),
        i_type(5, 1, 0x0, 3, 0x03),
        i_type(5, 1, 0x4, 4, 0x03),
        i_type(10, 1, 0x1, 5, 0x03),
        i_type(10, 1, 0x5, 6, 0x03),
        i_type(0, 1, 0x2, 7, 0x03),
        EBREAK,
    ]
    image = sparse_image(
        [
            (0, pack_words(program)),
            (0x100, pack_words([0x89ABCDEF])),
            (0x104, pack_words([0x00008000])),
            (0x108, pack_words([0x80000000])),
        ]
    )
    axi_events = []
    memory, monitor = await start_core(
        dut,
        image,
        axi_protocol_events=axi_events,
        axi_pause_generators=axi_backpressure_generators(),
        axi_monitor_cycles=5000,
    )

    traces = await with_timeout(collect_trace(dut, len(program), max_cycles=5000), 120, "us")
    await ClockCycles(dut.clk, 2)
    monitor.cancel()
    report = write_axi_event_report("axi_lite_backpressure", axi_events)

    assert_trace(traces[10], 40, EBREAK, trap=True, cause=2)
    assert memory.read_dword(0x110, byteorder="little") == 0x123
    assert not report["violations"], report["violations"]
    assert {"ar", "aw", "w"}.issubset(set(report["stalls"]))
    assert report["counts"].get("read_addr", 0) >= 10
    assert report["counts"].get("read_data", 0) >= 10
    assert report["counts"].get("write_addr", 0) == 3
    assert report["counts"].get("write_data", 0) == 3
    assert report["counts"].get("write_resp", 0) == 3


@cocotb.test()
async def axi_fetch_non_okay_response_takes_recoverable_access_fault(dut):
    await start_core_without_axi_slave(dut)
    trace_task = cocotb.start_soon(collect_trace(dut, 1, max_cycles=80))

    await drive_axi_read(dut, 0, 0, expected_prot=6, resp=AXI_SLVERR)
    traces = await with_timeout(trace_task, 10, "us")

    # Recoverable instruction access fault, mcause=1, mtval=PC, insn=0.
    assert_trace(
        traces[0],
        0,
        0,
        trap=True,
        cause=AXI_ERROR_CAUSE,
        csr_addr=CSR_MCAUSE,
        csr_rmask=CSR_FULL_MASK,
        csr_wmask=CSR_FULL_MASK,
        csr_wdata=1,
    )
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def axi_load_non_okay_response_takes_recoverable_access_fault(dut):
    program = [
        i_type(0x100, 0, 0x0, 1),
        i_type(0, 1, 0x2, 2, 0x03),
    ]
    await start_core_without_axi_slave(dut)
    trace_task = cocotb.start_soon(collect_trace(dut, len(program), max_cycles=160))

    await drive_axi_read(dut, 0, program[0], expected_prot=6)
    await drive_axi_read(dut, 4, program[1], expected_prot=6)
    await drive_axi_read(dut, 0x100, 0xDEAD_BEEF, expected_prot=2, resp=AXI_SLVERR)
    traces = await with_timeout(trace_task, 20, "us")

    assert_trace(traces[0], 0, program[0], rd=1, rd_wdata=0x100)
    # Recoverable load access fault, mcause=5, original load encoding preserved.
    assert_trace(
        traces[1],
        4,
        program[1],
        trap=True,
        cause=AXI_ERROR_CAUSE,
        csr_addr=CSR_MCAUSE,
        csr_rmask=CSR_FULL_MASK,
        csr_wmask=CSR_FULL_MASK,
        csr_wdata=5,
    )
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def axi_store_non_okay_response_takes_recoverable_access_fault(dut):
    program = [
        i_type(0x100, 0, 0x0, 1),
        i_type(0x55, 0, 0x0, 2),
        s_type(0, 2, 1, 0x2),
    ]
    await start_core_without_axi_slave(dut)
    trace_task = cocotb.start_soon(collect_trace(dut, len(program), max_cycles=220))

    await drive_axi_read(dut, 0, program[0], expected_prot=6)
    await drive_axi_read(dut, 4, program[1], expected_prot=6)
    await drive_axi_read(dut, 8, program[2], expected_prot=6)
    await accept_axi_write_address(dut, expected_addr=0x100, expected_prot=2)
    await accept_axi_write_data(dut, expected_data=0x55, expected_strb=0xF)
    await send_axi_write_response(dut, resp=AXI_SLVERR)
    traces = await with_timeout(trace_task, 30, "us")

    assert_trace(traces[0], 0, program[0], rd=1, rd_wdata=0x100)
    assert_trace(traces[1], 4, program[1], rd=2, rd_wdata=0x55)
    # Recoverable store access fault, mcause=7, original store encoding preserved.
    assert_trace(
        traces[2],
        8,
        program[2],
        trap=True,
        cause=AXI_ERROR_CAUSE,
        csr_addr=CSR_MCAUSE,
        csr_rmask=CSR_FULL_MASK,
        csr_wmask=CSR_FULL_MASK,
        csr_wdata=7,
    )
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def rv32e_misaligned_load_traps_without_data_axi(dut):
    program = [i_type(1, 0, 0x1, 1, 0x03)]
    axi_events = []
    _, monitor = await start_core(dut, pack_words(program), axi_events=axi_events)

    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    monitor.cancel()

    assert_trace(traces[0], 0, program[0], trap=True, cause=5)
    data_events = [
        event for event in axi_events
        if event["kind"] not in ("read_addr", "read_data") or not (event["prot"] & 0x4)
    ]
    assert data_events == []
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


@cocotb.test()
async def rv32e_misaligned_store_traps_without_data_axi(dut):
    program = [s_type(1, 0, 0, 0x1)]
    axi_events = []
    _, monitor = await start_core(dut, pack_words(program), axi_events=axi_events)

    traces = await with_timeout(collect_trace(dut, 1), 10, "us")
    monitor.cancel()

    assert_trace(traces[0], 0, program[0], trap=True, cause=6)
    data_events = [
        event for event in axi_events
        if event["kind"] not in ("read_addr", "read_data") or not (event["prot"] & 0x4)
    ]
    assert data_events == []
    await ClockCycles(dut.clk, 1)
    assert int(dut.status_trap.value) == 1


# ---------------------------------------------------------------------------
# Compliance gate: signature comparison against pre-computed expectations.
# Each test program writes its computed result words into a fixed signature
# region starting at 0x200, then stores a halt magic to 0x100 and loops on a
# branch-to-self. The cocotb harness polls the AXI RAM for the magic value
# and then reads back the signature words for assertion against the manifest.

COMPLIANCE_BUILD_DIR = REPO_ROOT / "result" / "compliance" / "build"
COMPLIANCE_MANIFEST = REPO_ROOT / "test" / "compliance" / "manifest.json"
COMPLIANCE_REFERENCE = REPO_ROOT / "result" / "compliance" / "reference.json"
COMPLIANCE_TOHOST_ADDR = 0x100
COMPLIANCE_SIG_BASE = 0x200


def _compliance_manifest_entry(name):
    # Prefer the auto-generated reference signature (produced by Sail at
    # orchestrator time) when available; fall back to the hand-computed
    # manifest so the cocotb tests still work when run in isolation.
    source = COMPLIANCE_REFERENCE if COMPLIANCE_REFERENCE.is_file() else COMPLIANCE_MANIFEST
    data = json.loads(source.read_text(encoding="utf-8"))
    for entry in data["tests"]:
        if entry["name"] == name:
            return entry
    raise AssertionError(f"compliance reference {source} has no entry for {name!r}")


def _compliance_image_bytes(name):
    bin_path = COMPLIANCE_BUILD_DIR / name / f"{name}.bin"
    assert bin_path.is_file(), (
        f"compliance binary missing: {bin_path}. "
        "Run scripts/build_compliance.py before invoking compliance cocotb tests."
    )
    return bin_path.read_bytes()


async def _await_compliance_halt(memory, timeout_us=20):
    deadline_ns = int(timeout_us * 1000)
    elapsed = 0
    step_ns = 100
    while elapsed < deadline_ns:
        await Timer(step_ns, unit="ns")
        elapsed += step_ns
        value = int.from_bytes(memory.read(COMPLIANCE_TOHOST_ADDR, 4), "little")
        if value != 0:
            return value
    raise AssertionError(
        f"compliance program did not write a non-zero tohost at 0x{COMPLIANCE_TOHOST_ADDR:08X} "
        f"within {timeout_us} us"
    )


async def _run_compliance_program(dut, name):
    entry = _compliance_manifest_entry(name)
    image = _compliance_image_bytes(name)
    memory = await start_core(dut, image)
    await _await_compliance_halt(memory)
    expected = [int(word, 0) for word in entry["signature_words"]]
    actual = []
    for index in range(len(expected)):
        word_bytes = memory.read(COMPLIANCE_SIG_BASE + index * 4, 4)
        actual.append(int.from_bytes(word_bytes, "little"))
    assert actual == expected, (
        f"compliance {name!r} signature mismatch: "
        f"expected={[f'0x{w:08X}' for w in expected]}, "
        f"actual={[f'0x{w:08X}' for w in actual]}"
    )


@cocotb.test()
async def compliance_add(dut):
    await _run_compliance_program(dut, "add")


@cocotb.test()
async def compliance_andi(dut):
    await _run_compliance_program(dut, "andi")


@cocotb.test()
async def compliance_beq(dut):
    await _run_compliance_program(dut, "beq")


@cocotb.test()
async def compliance_c_addi(dut):
    await _run_compliance_program(dut, "c_addi")


@cocotb.test()
async def compliance_alu_reg(dut):
    await _run_compliance_program(dut, "alu_reg")


@cocotb.test()
async def compliance_alu_imm(dut):
    await _run_compliance_program(dut, "alu_imm")


@cocotb.test()
async def compliance_branches(dut):
    await _run_compliance_program(dut, "branches")


@cocotb.test()
async def compliance_jumps(dut):
    await _run_compliance_program(dut, "jumps")


@cocotb.test()
async def compliance_upper(dut):
    await _run_compliance_program(dut, "upper")


@cocotb.test()
async def compliance_memory(dut):
    await _run_compliance_program(dut, "memory")


@cocotb.test()
async def compliance_compressed_ops(dut):
    await _run_compliance_program(dut, "compressed_ops")


@cocotb.test()
async def compliance_compressed_imm(dut):
    await _run_compliance_program(dut, "compressed_imm")


@cocotb.test()
async def compliance_compressed_branch(dut):
    await _run_compliance_program(dut, "compressed_branch")


@cocotb.test()
async def compliance_compressed_jump(dut):
    await _run_compliance_program(dut, "compressed_jump")


@cocotb.test()
async def compliance_compressed_mem(dut):
    await _run_compliance_program(dut, "compressed_mem")


@cocotb.test()
async def compliance_fence_nop(dut):
    await _run_compliance_program(dut, "fence_nop")


@cocotb.test()
async def compliance_csr_basic(dut):
    await _run_compliance_program(dut, "csr_basic")


@cocotb.test()
async def compliance_ecall(dut):
    await _run_compliance_program(dut, "ecall")


@cocotb.test()
async def compliance_ebreak(dut):
    await _run_compliance_program(dut, "ebreak")


@cocotb.test()
async def compliance_mret_return(dut):
    await _run_compliance_program(dut, "mret_return")
