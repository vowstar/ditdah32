# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import logging
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.handle import Immediate
from cocotb.triggers import ClockCycles, RisingEdge, Timer
from cocotbext.axi import AxiLiteBus, AxiLiteRam
from cocotbext.axi.axil_channels import (
    AxiLiteARBus,
    AxiLiteAWBus,
    AxiLiteBBus,
    AxiLiteRBus,
    AxiLiteWBus,
)


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


def axil_bus(dut):
    return AxiLiteBus.from_channels(
        _AWBus.from_prefix(dut, "axi"),
        _WBus.from_prefix(dut, "axi"),
        _BBus.from_prefix(dut, "axi"),
        _ARBus.from_prefix(dut, "axi"),
        _RBus.from_prefix(dut, "axi"),
    )


class JtagDtm:
    IR_IDCODE = 0x01
    IR_DTMCS = 0x10
    IR_DMI = 0x11

    def __init__(self, dut):
        self.dut = dut

    async def cycle(self, tms, tdi=0):
        self.dut.jtag_tms.value = tms
        self.dut.jtag_tdi.value = tdi
        await Timer(1, unit="ns")
        tdo = int(self.dut.jtag_tdo.value)
        await Timer(3, unit="ns")
        self.dut.jtag_tck.value = 1
        await Timer(5, unit="ns")
        self.dut.jtag_tck.value = 0
        await Timer(1, unit="ns")
        return tdo

    async def reset(self):
        self.dut.jtag_trstN.value = 0
        await self.cycle(1)
        self.dut.jtag_trstN.value = 1
        for _ in range(5):
            await self.cycle(1)
        await self.cycle(0)

    async def scan_ir(self, value):
        await self.cycle(1)
        await self.cycle(1)
        await self.cycle(0)
        await self.cycle(0)
        captured = 0
        for bit in range(5):
            captured |= (await self.cycle(bit == 4, (value >> bit) & 1)) << bit
        await self.cycle(1)
        await self.cycle(0)
        return captured

    async def scan_dr(self, value, width):
        await self.cycle(1)
        await self.cycle(0)
        await self.cycle(0)
        captured = 0
        for bit in range(width):
            captured |= (await self.cycle(bit == width - 1, (value >> bit) & 1)) << bit
        await self.cycle(1)
        await self.cycle(0)
        return captured

    async def idle(self, cycles=10):
        for _ in range(cycles):
            await self.cycle(0)

    async def dmi(self, op, address, data=0):
        request = ((address & 0x7F) << 34) | ((data & 0xFFFF_FFFF) << 2) | op
        await self.scan_dr(request, 41)
        await self.idle()
        response = await self.scan_dr(0, 41)
        status = response & 0x3
        assert status == 0, f"DMI status {status} at address 0x{address:02x}"
        return (response >> 2) & 0xFFFF_FFFF

    async def read(self, address):
        return await self.dmi(1, address)

    async def write(self, address, data):
        await self.dmi(2, address, data)


DM_DATA0 = 0x04
DM_DATA1 = 0x05
DM_CONTROL = 0x10
DM_STATUS = 0x11
DM_ABSTRACTCS = 0x16
DM_COMMAND = 0x17

DM_ACTIVE = 1 << 0
DM_SET_RESET_HALT = 1 << 3
DM_HART_RESET = 1 << 29
DM_RESUME_REQ = 1 << 30
DM_HALT_REQ = 1 << 31

STATUS_ALL_HAVE_RESET = 1 << 19
STATUS_ALL_RESUME_ACK = 1 << 17
STATUS_ALL_RUNNING = 1 << 11
STATUS_ALL_HALTED = 1 << 9

CMD_ACCESS_REGISTER = 0 << 24
CMD_ACCESS_MEMORY = 2 << 24
CMD_SIZE_32 = 2 << 20
CMD_TRANSFER = 1 << 17
CMD_WRITE = 1 << 16
CSR_DCSR = 0x7B0
CSR_DPC = 0x7B1
CSR_MSTATUS = 0x300
CSR_MIE = 0x304
CSR_MSCRATCH = 0x340

NOP = 0x00000013
EBREAK = 0x00100073


async def wait_status(dtm, mask, limit=100):
    for _ in range(limit):
        value = await dtm.read(DM_STATUS)
        if value & mask == mask:
            return value
    raise AssertionError(f"DM status did not set 0x{mask:08x}")


class RemoteBitbangServer:
    def __init__(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.listener.listen(1)
        self.listener.setblocking(False)
        self.connection = None
        self.closed = False

    def close(self):
        self.closed = True
        if self.connection is not None:
            self.connection.close()
        self.listener.close()


def unused_tcp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return handle.getsockname()[1]


async def serve_remote_bitbang(dut, server):
    while not server.closed:
        if server.connection is None:
            try:
                server.connection, _ = server.listener.accept()
                server.connection.setblocking(False)
            except BlockingIOError:
                time.sleep(0.001)
                await Timer(1, unit="ns")
                continue

        try:
            payload = server.connection.recv(4096)
        except BlockingIOError:
            time.sleep(0.001)
            await Timer(1, unit="ns")
            continue
        if not payload:
            return

        for value in payload:
            command = chr(value)
            if "0" <= command <= "7":
                bits = ord(command) - ord("0")
                dut.jtag_tck.value = (bits >> 2) & 1
                dut.jtag_tms.value = (bits >> 1) & 1
                dut.jtag_tdi.value = bits & 1
            elif command == "R":
                await Timer(1, unit="ns")
                response = b"1" if int(dut.jtag_tdo.value) else b"0"
                while True:
                    try:
                        if server.connection.send(response) == 1:
                            break
                    except BlockingIOError:
                        time.sleep(0.001)
                    await Timer(1, unit="ns")
            elif "r" <= command <= "u":
                bits = ord(command) - ord("r")
                dut.jtag_trstN.value = 0 if bits & 2 else 1
                dut.reset.value = 1 if bits & 1 else 0
            elif command == "Q":
                return
            await Timer(1, unit="ns")


async def wait_process_ready(process, log_path, marker, limit=20000):
    for _ in range(limit):
        if process.poll() is not None:
            break
        if log_path.exists() and marker in log_path.read_text(errors="replace"):
            return
        await Timer(100, unit="ns")
    output = log_path.read_text(errors="replace") if log_path.exists() else ""
    raise AssertionError(f"process did not become ready: {output[-4000:]}")


async def wait_process_exit(process, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return process.returncode
        await Timer(1, unit="us")
    process.kill()
    process.wait(timeout=10)
    raise AssertionError("process did not exit")


async def wait_abstract(dtm, limit=100):
    for _ in range(limit):
        value = await dtm.read(DM_ABSTRACTCS)
        if not value & (1 << 12):
            error = (value >> 8) & 0x7
            assert error == 0, f"abstract command error {error}"
            return
    raise AssertionError("abstract command remained busy")


async def wait_abstract_error(dtm, expected, limit=100):
    for _ in range(limit):
        value = await dtm.read(DM_ABSTRACTCS)
        if not value & (1 << 12):
            assert (value >> 8) & 0x7 == expected
            return
    raise AssertionError("abstract command remained busy")


async def clear_abstract_error(dtm, error):
    await dtm.write(DM_ABSTRACTCS, error << 8)
    assert (await dtm.read(DM_ABSTRACTCS) >> 8) & 0x7 == 0


async def abstract_read_register(dtm, regno):
    await dtm.write(DM_COMMAND, CMD_ACCESS_REGISTER | CMD_SIZE_32 | CMD_TRANSFER | regno)
    await wait_abstract(dtm)
    return await dtm.read(DM_DATA0)


async def abstract_write_register(dtm, regno, value):
    await dtm.write(DM_DATA0, value)
    await dtm.write(
        DM_COMMAND,
        CMD_ACCESS_REGISTER | CMD_SIZE_32 | CMD_TRANSFER | CMD_WRITE | regno,
    )
    await wait_abstract(dtm)


async def abstract_memory(dtm, address, size, write=False, value=0):
    await dtm.write(DM_DATA1, address)
    if write:
        await dtm.write(DM_DATA0, value)
    command = CMD_ACCESS_MEMORY | (size << 20) | (CMD_WRITE if write else 0)
    await dtm.write(DM_COMMAND, command)
    await wait_abstract(dtm)
    return await dtm.read(DM_DATA0)


@cocotb.test()
async def test_jtag_debug_flow(dut):
    logging.getLogger("cocotb.test_jtag.axi").setLevel(logging.WARNING)
    dut.clk.value = Immediate(0)
    dut.reset.value = Immediate(1)
    dut.jtag_tck.value = Immediate(0)
    dut.jtag_tms.value = Immediate(1)
    dut.jtag_tdi.value = Immediate(0)
    dut.jtag_trstN.value = Immediate(0)
    dut.irq_software.value = 0
    dut.irq_timer.value = 0
    dut.irq_external.value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await ClockCycles(dut.clk, 2)

    memory = AxiLiteRam(axil_bus(dut), dut.clk, size=4096)
    memory.write(0, b"".join(NOP.to_bytes(4, "little") for _ in range(64)))
    memory.write(0x80, EBREAK.to_bytes(4, "little"))

    await ClockCycles(dut.clk, 5)
    dut.reset.value = 0
    await RisingEdge(dut.clk)

    dtm = JtagDtm(dut)
    await dtm.reset()

    idcode = await dtm.scan_dr(0, 32)
    assert idcode == 1
    assert await dtm.scan_ir(JtagDtm.IR_DTMCS) & 0x3 == 1
    dtmcs = await dtm.scan_dr(0, 32)
    assert dtmcs & 0xF == 1
    assert (dtmcs >> 4) & 0x3F == 7

    await dtm.scan_ir(JtagDtm.IR_DMI)
    await dtm.scan_dr(3, 41)
    await dtm.scan_ir(JtagDtm.IR_DTMCS)
    assert (await dtm.scan_dr(0, 32) >> 10) & 0x3 == 2
    await dtm.scan_dr(1 << 16, 32)
    assert (await dtm.scan_dr(0, 32) >> 10) & 0x3 == 0
    await dtm.scan_ir(JtagDtm.IR_DMI)
    await dtm.scan_dr(3, 41)
    for _ in range(5):
        await dtm.cycle(1)
    await dtm.cycle(0)
    assert await dtm.scan_dr(0, 32) == 1

    await dtm.scan_ir(0x1F)
    assert await dtm.scan_dr(1, 1) == 0
    assert await dtm.scan_dr(0, 1) == 1

    await dtm.scan_ir(JtagDtm.IR_DMI)
    await dtm.write(DM_CONTROL, DM_ACTIVE)
    status = await dtm.read(DM_STATUS)
    assert status & 0xF == 3
    assert status & (1 << 7)

    await dtm.write(DM_CONTROL, DM_ACTIVE | DM_HALT_REQ)
    await wait_status(dtm, STATUS_ALL_HALTED)

    await abstract_write_register(dtm, 0x1001, 0x1234_5678)
    assert await abstract_read_register(dtm, 0x1001) == 0x1234_5678
    await abstract_write_register(dtm, CSR_MSCRATCH, 0xA5A5_5A5A)
    assert await abstract_read_register(dtm, CSR_MSCRATCH) == 0xA5A5_5A5A

    await abstract_memory(dtm, 0x100, 2, write=True, value=0xCAFE_BABE)
    assert await abstract_memory(dtm, 0x100, 2) == 0xCAFE_BABE
    await abstract_memory(dtm, 0x105, 0, write=True, value=0x5A)
    assert await abstract_memory(dtm, 0x105, 0) & 0xFF == 0x5A
    await abstract_memory(dtm, 0x106, 1, write=True, value=0xBEEF)
    assert await abstract_memory(dtm, 0x106, 1) & 0xFFFF == 0xBEEF

    await dtm.write(DM_COMMAND, CMD_ACCESS_REGISTER | CMD_SIZE_32 | CMD_TRANSFER | 0x1010)
    await wait_abstract_error(dtm, 3)
    await clear_abstract_error(dtm, 3)
    await dtm.write(DM_DATA1, 0x101)
    await dtm.write(DM_COMMAND, CMD_ACCESS_MEMORY | CMD_SIZE_32)
    await wait_abstract_error(dtm, 5)
    await clear_abstract_error(dtm, 5)

    await abstract_write_register(dtm, CSR_DPC, 0x40)
    await abstract_write_register(dtm, CSR_MSTATUS, 1 << 3)
    await abstract_write_register(dtm, CSR_MIE, 1 << 7)
    dut.irq_timer.value = 1
    await abstract_write_register(dtm, CSR_DCSR, 1 << 2)
    await dtm.write(DM_CONTROL, DM_ACTIVE | DM_RESUME_REQ)
    await wait_status(dtm, STATUS_ALL_HALTED)
    stepped_dpc = await abstract_read_register(dtm, CSR_DPC)
    assert stepped_dpc == 0x44
    dcsr = await abstract_read_register(dtm, CSR_DCSR)
    assert (dcsr >> 6) & 0x7 == 4
    dut.irq_timer.value = 0
    await abstract_write_register(dtm, CSR_MSTATUS, 0)
    await abstract_write_register(dtm, CSR_MIE, 0)

    await abstract_write_register(dtm, CSR_DCSR, 1 << 15)
    await abstract_write_register(dtm, CSR_DPC, 0x80)
    await dtm.write(DM_CONTROL, DM_ACTIVE | DM_RESUME_REQ)
    await wait_status(dtm, STATUS_ALL_HALTED)
    assert await abstract_read_register(dtm, CSR_DPC) == 0x80
    dcsr = await abstract_read_register(dtm, CSR_DCSR)
    assert (dcsr >> 6) & 0x7 == 1

    await abstract_write_register(dtm, CSR_DPC, 0x84)
    await dtm.write(DM_CONTROL, DM_ACTIVE | DM_RESUME_REQ)
    await wait_status(dtm, STATUS_ALL_RUNNING | STATUS_ALL_RESUME_ACK)

    await dtm.write(DM_CONTROL, DM_ACTIVE | DM_SET_RESET_HALT)
    await dtm.write(DM_CONTROL, DM_ACTIVE | DM_HART_RESET)
    await ClockCycles(dut.clk, 4)
    await dtm.write(DM_CONTROL, DM_ACTIVE)
    await wait_status(dtm, STATUS_ALL_HAVE_RESET | STATUS_ALL_HALTED)
    assert await abstract_read_register(dtm, CSR_DPC) == 0


@cocotb.test()
async def test_openocd_gdb_flow(dut):
    logging.getLogger("cocotb.test_jtag.axi").setLevel(logging.WARNING)
    openocd = shutil.which("openocd")
    gdb = shutil.which("riscv32-none-elf-gdb")
    assert openocd is not None
    assert gdb is not None

    dut.clk.value = Immediate(0)
    dut.reset.value = Immediate(1)
    dut.jtag_tck.value = Immediate(0)
    dut.jtag_tms.value = Immediate(1)
    dut.jtag_tdi.value = Immediate(0)
    dut.jtag_trstN.value = Immediate(1)
    dut.irq_software.value = 0
    dut.irq_timer.value = 0
    dut.irq_external.value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await ClockCycles(dut.clk, 2)

    memory = AxiLiteRam(axil_bus(dut), dut.clk, size=4096)
    memory.write(0, b"".join(NOP.to_bytes(4, "little") for _ in range(64)))
    await ClockCycles(dut.clk, 5)
    dut.reset.value = 0
    await RisingEdge(dut.clk)

    server = RemoteBitbangServer()
    bridge = cocotb.start_soon(serve_remote_bitbang(dut, server))
    gdb_port = unused_tcp_port()
    test_dir = Path(__file__).resolve().parent
    openocd_log = test_dir / "openocd.log"
    openocd_log.unlink(missing_ok=True)
    environment = os.environ.copy()
    environment["DITDAH32_RBB_PORT"] = str(server.port)
    environment["DITDAH32_GDB_PORT"] = str(gdb_port)

    openocd_process = None
    try:
        with openocd_log.open("w") as log_handle:
            openocd_process = subprocess.Popen(
                [openocd, "-f", str(test_dir / "openocd.cfg")],
                env=environment,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
        await wait_process_ready(
            openocd_process,
            openocd_log,
            f"Listening on port {gdb_port} for gdb connections",
        )

        gdb_process = subprocess.Popen(
            [
                gdb,
                "-q",
                "-nx",
                "-batch",
                "-ex",
                "set remotetimeout 120",
                "-ex",
                "set remote fetch-register-packet on",
                "-ex",
                "set remote set-register-packet on",
                "-ex",
                f"target remote 127.0.0.1:{gdb_port}",
                "-ex",
                "set $ra = 0x12345678",
                "-ex",
                "p/x $ra",
                "-ex",
                "set {unsigned int}0x100 = 0xcafebabe",
                "-ex",
                "x/1wx 0x100",
                "-ex",
                "set $pc = 0",
                "-ex",
                "stepi",
                "-ex",
                "p/x $pc",
                "-ex",
                "detach",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        returncode = await wait_process_exit(gdb_process)
        gdb_output, _ = gdb_process.communicate()
        assert returncode == 0, gdb_output
        assert "0x12345678" in gdb_output
        assert "0xcafebabe" in gdb_output.lower()
        assert "0x4" in gdb_output
    finally:
        if openocd_process is not None and openocd_process.poll() is None:
            openocd_process.terminate()
            await wait_process_exit(openocd_process, timeout=10)
        server.close()
        bridge.cancel()
