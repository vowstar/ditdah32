#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from rv32ec_model import RV32ECModel


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS = ("rv32e_alu", "rv32ec_compressed", "rv32ec_zicsr_wfi")
DEFAULT_BASE = 0x8000_0000
SPIKE_RETRY_TIMEOUT_SECONDS = 10.0
SPIKE_LOG_RE = re.compile(
    r"^core\s+\d+:\s+\d+\s+"
    r"(?P<pc>0x[0-9a-fA-F]+)\s+"
    r"\((?P<insn>0x[0-9a-fA-F]+)\)"
    r"(?:\s+x(?P<rd>\d+)\s+(?P<rd_wdata>0x[0-9a-fA-F]+))?"
    r"(?:\s+mem\s+(?P<mem_addr>0x[0-9a-fA-F]+)(?:\s+(?P<mem_wdata>0x[0-9a-fA-F]+))?)?"
)


def hex32(value):
    return f"0x{value & 0xFFFF_FFFF:08x}"


def read_words(path):
    return [int(line.strip(), 0) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def discover_artifacts(isa_dir):
    return sorted(path.name.removesuffix(".hex") for path in isa_dir.glob("*.hex"))


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


def run_checked(command, cwd, log_path):
    with log_path.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}")


def build_elf(name, words, work_dir, base, logs_dir):
    prefix = subprocess.os.environ.get("RISCV_PREFIX", "riscv32-none-elf-")
    objcopy = shutil.which(f"{prefix}objcopy")
    ld = shutil.which(f"{prefix}ld")
    if objcopy is None:
        raise RuntimeError(f"missing objcopy command: {prefix}objcopy")
    if ld is None:
        raise RuntimeError(f"missing ld command: {prefix}ld")

    bin_path = work_dir / f"{name}.bin"
    object_path = work_dir / f"{name}.o"
    elf_path = work_dir / f"{name}.elf"
    script_path = work_dir / f"{name}.ld"

    bin_path.write_bytes(b"".join(struct.pack("<I", word) for word in words))
    script_path.write_text(
        "\n".join(
            [
                "ENTRY(_start)",
                "SECTIONS {",
                f"  . = 0x{base:08x};",
                "  .text : { _start = .; *(.text*) }",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    run_checked(
        [
            objcopy,
            "-I",
            "binary",
            "-O",
            "elf32-littleriscv",
            "-B",
            "riscv:rv32",
            "--rename-section",
            ".data=.text,alloc,load,code,contents",
            str(bin_path),
            str(object_path),
        ],
        REPO_ROOT,
        logs_dir / f"{name}.objcopy.log",
    )
    run_checked(
        [
            ld,
            "-m",
            "elf32lriscv",
            "-T",
            str(script_path),
            "-o",
            str(elf_path),
            str(object_path),
        ],
        REPO_ROOT,
        logs_dir / f"{name}.ld.log",
    )
    return elf_path


def run_model(words, base, max_steps):
    model = RV32ECModel(pc=base)
    model.load_words(words, base=base)
    model.run(max_steps)
    return model.trace


def parse_spike_log(path, base, code_bytes):
    records = []
    code_end = base + code_bytes
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = SPIKE_LOG_RE.match(line)
        if match is None:
            continue
        pc = int(match.group("pc"), 16)
        if pc < base or pc >= code_end:
            continue
        insn = int(match.group("insn"), 16)
        rd_text = match.group("rd")
        rd_wdata_text = match.group("rd_wdata")
        mem_addr_text = match.group("mem_addr")
        mem_wdata_text = match.group("mem_wdata")
        rd_wdata = int(rd_wdata_text, 16) if rd_wdata_text is not None else None
        mem_addr = int(mem_addr_text, 16) if mem_addr_text is not None else None
        mem_wdata = int(mem_wdata_text, 16) if mem_wdata_text is not None else None
        record = {
            "pc": hex32(pc),
            "insn": hex32(insn),
            "length": 2 if (insn & 0x3) != 0x3 else 4,
            "rd_we": rd_text is not None,
            "rd": int(rd_text) if rd_text is not None else None,
            "rd_wdata": hex32(rd_wdata) if rd_wdata is not None else None,
            "mem_addr": hex32(mem_addr) if mem_addr is not None else None,
            "mem_rdata": hex32(rd_wdata) if mem_addr is not None and rd_wdata is not None else None,
            "mem_wdata": hex32(mem_wdata) if mem_wdata is not None else None,
            "trap": False,
            "trap_cause": None,
        }
        records.append(record)
    return records


def unsupported_reason(expected, base):
    if not expected:
        return "reference trace is empty"

    for index, item in enumerate(expected[:-1]):
        if item.get("trap"):
            return f"non-terminal trap at item {index}"
        if item.get("mem_addr") is not None and int(item["mem_addr"], 16) < base:
            return "memory artifact uses low data addresses that are not yet part of the Spike compatible matrix"

    last = expected[-1]
    if last.get("trap"):
        if last.get("trap_cause") != "ebreak":
            return f"terminal trap cause is outside Spike compatible matrix: {last.get('trap_cause')!r}"
        return None

    if last.get("insn") == "0x10500073":
        return None

    if last.get("mem_addr") is not None and int(last["mem_addr"], 16) < base:
        return "memory artifact uses low data addresses that are not yet part of the Spike compatible matrix"

    return "terminal ebreak trap or WFI sleep point is required for Spike timeout comparison"


def trace_ends_at_wfi(expected):
    return bool(expected and expected[-1].get("insn") == "0x10500073")


def timeout_signal_for_trace(expected):
    if trace_ends_at_wfi(expected):
        return "TERM"
    return "INT"


def run_spike_with_retry(timeout_cmd, timeout_signal, timeout_seconds, spike_args, spike_log_path, spike_stderr_path):
    attempt_timeouts = (timeout_seconds, max(timeout_seconds, SPIKE_RETRY_TIMEOUT_SECONDS))
    for attempt, attempt_timeout in enumerate(attempt_timeouts, start=1):
        spike_log_path.unlink(missing_ok=True)
        command = [
            timeout_cmd,
            f"--signal={timeout_signal}",
            "--kill-after=2s",
            f"{attempt_timeout}s",
            *spike_args,
        ]
        with spike_stderr_path.open("w" if attempt == 1 else "a", encoding="utf-8") as stderr_file:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                check=False,
            )
        if spike_log_path.exists() and spike_log_path.stat().st_size > 0:
            return completed, attempt
        if completed.returncode != 124:
            break

    raise RuntimeError(f"Spike did not create a commit log after {attempt} attempt(s)")


def compare_prefix(expected, actual, base):
    reason = unsupported_reason(expected, base)
    if reason is not None:
        return reason

    terminal_trap = expected[-1] if expected[-1].get("trap") else None
    if terminal_trap is not None:
        expected_commits = expected[:-1]
    else:
        expected_commits = expected

    if len(actual) != len(expected_commits):
        return f"commit count mismatch: expected {len(expected_commits)}, got {len(actual)}"

    fields = ("pc", "insn", "length", "rd_we", "rd", "rd_wdata", "mem_addr", "mem_rdata", "mem_wdata", "trap", "trap_cause")
    for index, (exp, act) in enumerate(zip(expected_commits, actual)):
        for field in fields:
            if exp.get(field) != act.get(field):
                return f"item {index} field {field}: expected {exp.get(field)!r}, got {act.get(field)!r}"

    return None


def run_artifact(name, isa_dir, out_dir, base, timeout_seconds, skip_unsupported=False):
    hex_path = isa_dir / f"{name}.hex"
    if not hex_path.exists():
        raise RuntimeError(f"missing artifact hex: {hex_path}")

    logs_dir = out_dir / "logs"
    traces_dir = out_dir / "traces"
    logs_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)

    words = read_words(hex_path)
    expected = run_model(words, base, len(words) * 4 + 32)
    effective_timeout_seconds = timeout_seconds
    terminal_wfi = trace_ends_at_wfi(expected)
    timeout_signal = timeout_signal_for_trace(expected)
    if terminal_wfi:
        effective_timeout_seconds = max(timeout_seconds, 5.0)
    expected_path = traces_dir / f"{name}.expected.jsonl"
    actual_path = traces_dir / f"{name}.spike.jsonl"
    spike_log_path = logs_dir / f"{name}.spike.log"
    spike_stderr_path = logs_dir / f"{name}.spike.stderr.log"
    write_jsonl(expected_path, expected)

    skip_reason = unsupported_reason(expected, base)
    if skip_unsupported and skip_reason is not None:
        actual_path.write_text("", encoding="utf-8")
        return {
            "name": name,
            "status": "skip",
            "reason": skip_reason,
            "base": hex32(base),
            "expected_trace": str(expected_path.relative_to(REPO_ROOT)),
            "spike_trace": str(actual_path.relative_to(REPO_ROOT)),
            "expected_items": len(expected),
            "spike_commit_items": 0,
        }

    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"ditdah32-{name}-") as temp_name:
        work_dir = Path(temp_name)
        elf_path = build_elf(name, words, work_dir, base, logs_dir)
        timeout_cmd = shutil.which("timeout")
        if timeout_cmd is None:
            raise RuntimeError("missing timeout command")
        spike_args = [
            "spike",
            "--isa=rv32ec_zicsr",
            "--priv=m",
            f"-m0x00000000:0x100000,0x{base:08x}:0x100000",
            "--log-commits",
            f"--log={spike_log_path}",
            str(elf_path),
        ]
        completed, spike_attempts = run_spike_with_retry(
            timeout_cmd,
            timeout_signal,
            effective_timeout_seconds,
            spike_args,
            spike_log_path,
            spike_stderr_path,
        )
        returncode = completed.returncode
        timed_out = returncode == 124

    actual = parse_spike_log(spike_log_path, base, len(words) * 4)
    write_jsonl(actual_path, actual)
    error = compare_prefix(expected, actual, base)
    status = "pass" if error is None else "fail"

    return {
        "name": name,
        "status": status,
        "error": error,
        "duration_seconds": round(time.monotonic() - start, 3),
        "base": hex32(base),
        "timeout_seconds": effective_timeout_seconds,
        "timeout_signal": timeout_signal,
        "spike_attempts": spike_attempts,
        "spike_returncode": returncode,
        "spike_timed_out": timed_out,
        "expected_trace": str(expected_path.relative_to(REPO_ROOT)),
        "spike_trace": str(actual_path.relative_to(REPO_ROOT)),
        "spike_log": str(spike_log_path.relative_to(REPO_ROOT)),
        "spike_stderr": str(spike_stderr_path.relative_to(REPO_ROOT)),
        "expected_items": len(expected),
        "spike_commit_items": len(actual),
    }


def main():
    parser = argparse.ArgumentParser(description="Run a small Spike ISS smoke check for DitDah32 ISA artifacts")
    parser.add_argument("--isa-dir", type=Path, default=REPO_ROOT / "result" / "isa")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "iss" / "spike_smoke")
    parser.add_argument("--artifact", action="append", dest="artifacts", help="artifact name without .hex; may be repeated")
    parser.add_argument("--all-compatible", action="store_true", help="run every compatible artifact and skip explicitly unsupported ones")
    parser.add_argument("--base", type=lambda text: int(text, 0), default=DEFAULT_BASE)
    parser.add_argument("--timeout-seconds", type=float, default=1.0)
    args = parser.parse_args()

    if shutil.which("spike") is None:
        print("missing spike command; run inside nix develop after flake.nix has pkgs.spike", file=sys.stderr)
        return 1

    isa_dir = args.isa_dir
    out_dir = args.out_dir
    if not isa_dir.is_absolute():
        isa_dir = REPO_ROOT / isa_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "status": "pass",
        "scope": "spike_smoke_prefix_compare",
        "isa": "rv32ec_zicsr",
        "base": hex32(args.base),
        "artifacts": [],
        "started_unix": int(time.time()),
    }

    failed = False
    artifacts = discover_artifacts(isa_dir) if args.all_compatible else (args.artifacts or DEFAULT_ARTIFACTS)
    for name in artifacts:
        print(f"[RUN] spike smoke: {name}", flush=True)
        try:
            result = run_artifact(name, isa_dir, out_dir, args.base, args.timeout_seconds, skip_unsupported=args.all_compatible)
        except Exception as exc:
            result = {"name": name, "status": "fail", "error": str(exc)}
        report["artifacts"].append(result)
        failed = failed or result["status"] == "fail"
        print(f"[{result['status'].upper()}] spike smoke: {name}", flush=True)
        if result.get("error"):
            print(result["error"], flush=True)
        if result.get("reason"):
            print(result["reason"], flush=True)

    report["summary"] = {
        "pass": sum(1 for item in report["artifacts"] if item["status"] == "pass"),
        "skip": sum(1 for item in report["artifacts"] if item["status"] == "skip"),
        "fail": sum(1 for item in report["artifacts"] if item["status"] == "fail"),
        "total": len(report["artifacts"]),
    }
    report["status"] = "fail" if failed else "pass"
    if report["summary"]["skip"]:
        report["coverage_status"] = "partial"
    else:
        report["coverage_status"] = "complete_for_selected_artifacts"
    report_path = out_dir / "spike_smoke.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[REPORT] {report_path}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
