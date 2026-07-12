# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_spike_iss_smoke  # noqa: E402


def test_spike_wfi_timeout_uses_term_signal():
    trace = [{"insn": "0x10500073"}]

    assert run_spike_iss_smoke.timeout_signal_for_trace(trace) == "TERM"


def test_spike_non_wfi_timeout_uses_int_signal():
    trace = [{"insn": "0x00100073", "trap": True, "trap_cause": "ebreak"}]

    assert run_spike_iss_smoke.timeout_signal_for_trace(trace) == "INT"


def test_spike_log_retry_discards_stale_log(monkeypatch, tmp_path):
    spike_log = tmp_path / "spike.log"
    spike_stderr = tmp_path / "spike.stderr.log"
    spike_log.write_text("stale\n", encoding="utf-8")
    commands = []
    run_kwargs = []

    def fake_run(command, **kwargs):
        commands.append(command)
        run_kwargs.append(kwargs)
        if len(commands) == 2:
            spike_log.write_text("commit\n", encoding="utf-8")
        return SimpleNamespace(returncode=124)

    monkeypatch.setattr(run_spike_iss_smoke.subprocess, "run", fake_run)

    completed, attempts = run_spike_iss_smoke.run_spike_with_retry(
        "timeout",
        "INT",
        1.0,
        ["spike"],
        spike_log,
        spike_stderr,
    )

    assert completed.returncode == 124
    assert attempts == 2
    assert commands[0][3] == "1.0s"
    assert commands[1][3] == "10.0s"
    assert run_kwargs[0]["stdin"] is run_spike_iss_smoke.subprocess.DEVNULL
    assert spike_log.read_text(encoding="utf-8") == "commit\n"
