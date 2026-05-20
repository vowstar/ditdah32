# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_spike_iss_smoke  # noqa: E402


def test_spike_wfi_timeout_uses_term_signal():
    trace = [{"insn": "0x10500073"}]

    assert run_spike_iss_smoke.timeout_signal_for_trace(trace) == "TERM"


def test_spike_non_wfi_timeout_uses_int_signal():
    trace = [{"insn": "0x00100073", "trap": True, "trap_cause": "ebreak"}]

    assert run_spike_iss_smoke.timeout_signal_for_trace(trace) == "INT"
