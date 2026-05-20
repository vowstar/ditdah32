# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from rv32ec_isa_regress import directed_programs, run_program  # noqa: E402
from rv32ec_trace_check import compare, load_jsonl  # noqa: E402


def test_directed_program_final_state():
    results = {program.name: run_program(program) for program in directed_programs()}

    alu = results["rv32e_alu"]
    assert alu.regs[1] == 0x12345678
    assert alu.regs[4] == 0x7FFFFFFF
    assert alu.regs[5] == 0xFFFFFFFF
    assert alu.regs[8] == 0x80000000
    assert alu.trace[-1]["trap_cause"] == "ebreak"

    branch_memory = results["rv32e_branch_memory"]
    assert branch_memory.regs[3] == 0xFFFFFFFF
    assert branch_memory.regs[4] == 0
    assert branch_memory.regs[5] == 28
    assert branch_memory.trace[-1]["pc"] == "0x00000020"

    compressed = results["rv32ec_compressed"]
    assert compressed.regs[1] == 5
    assert compressed.regs[2] == 20
    assert compressed.regs[3] == 0
    assert compressed.regs[4] == 0x1000
    assert compressed.regs[9] == 1
    assert all(item["length"] == 2 for item in compressed.trace)

    compressed_memory = results["rv32ec_compressed_memory"]
    assert compressed_memory.regs[8] == 80
    assert compressed_memory.regs[10] == 7
    assert compressed_memory.regs[11] == 7
    assert compressed_memory.load_u32_raw(68) == 7

    zicsr_wfi = results["rv32ec_zicsr_wfi"]
    assert zicsr_wfi.regs[2] == 64
    assert zicsr_wfi.regs[7] == 4
    assert zicsr_wfi.regs[8] == 0
    assert zicsr_wfi.sleeping is True
    assert zicsr_wfi.trace[-1]["insn"] == "0x10500073"


def test_regression_cli_writes_hex_and_trace_artifacts(tmp_path):
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "rv32ec_isa_regress.py"), "--out-dir", str(tmp_path)],
        check=True,
        cwd=ROOT,
    )

    trace_path = tmp_path / "rv32ec_compressed.trace.jsonl"
    hex_path = tmp_path / "rv32ec_compressed.hex"

    assert trace_path.exists()
    assert hex_path.exists()

    trace = load_jsonl(trace_path)
    assert compare(trace, trace) is None
    assert json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])["trap_cause"] == "ebreak"
