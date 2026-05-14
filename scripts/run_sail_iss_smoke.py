#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from run_spike_iss_smoke import (
    DEFAULT_ARTIFACTS,
    DEFAULT_BASE,
    build_elf,
    discover_artifacts,
    hex32,
    read_words,
    run_model,
    write_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAIL_INSTR_RE = re.compile(
    r"^\[(?P<index>\d+)\]\s+\[(?P<mode>[A-Z])\]:\s+"
    r"(?P<pc>0x[0-9a-fA-F]+)\s+"
    r"\((?P<insn>0x[0-9a-fA-F]+)\)"
)
SAIL_REG_RE = re.compile(r"^x(?P<rd>\d+)\s+<-\s+(?P<value>0x[0-9a-fA-F]+)")
SAIL_MEM_RE = re.compile(
    r"^mem\[(?P<kind>[RW]),(?P<addr>0x[0-9a-fA-F]+)\]\s+"
    r"(?P<arrow>->|<-)\s+(?P<value>0x[0-9a-fA-F]+)"
)


def artifact_supported(expected, base, allow_low_data_memory=False):
    if not expected:
        return "reference trace is empty"

    for index, item in enumerate(expected[:-1]):
        if item.get("trap"):
            return f"non-terminal trap at item {index}"
        if (
            not allow_low_data_memory
            and item.get("mem_addr") is not None
            and int(item["mem_addr"], 16) < base
        ):
            return "memory artifact uses low data addresses that are not part of the Sail compatible matrix"

    last = expected[-1]
    if last.get("trap"):
        if last.get("trap_cause") != "ebreak":
            return f"terminal trap cause is outside Sail compatible matrix: {last.get('trap_cause')!r}"
        return None

    if last.get("insn") == "0x10500073":
        return None

    if (
        not allow_low_data_memory
        and last.get("mem_addr") is not None
        and int(last["mem_addr"], 16) < base
    ):
        return "memory artifact uses low data addresses that are not part of the Sail compatible matrix"

    return "terminal ebreak trap or WFI sleep point is required for Sail prefix comparison"


def compare_sail_prefix(expected, actual, base, allow_low_data_memory=False):
    reason = artifact_supported(expected, base, allow_low_data_memory)
    if reason is not None:
        return reason

    terminal_trap = expected[-1] if expected[-1].get("trap") else None
    expected_commits = expected[:-1] if terminal_trap is not None else expected

    if len(actual) != len(expected_commits):
        return f"commit count mismatch: expected {len(expected_commits)}, got {len(actual)}"

    fields = (
        "pc",
        "insn",
        "length",
        "rd_we",
        "rd",
        "rd_wdata",
        "mem_addr",
        "mem_rdata",
        "mem_wdata",
        "trap",
        "trap_cause",
    )
    for index, (exp, act) in enumerate(zip(expected_commits, actual)):
        for field in fields:
            if exp.get(field) != act.get(field):
                return f"item {index} field {field}: expected {exp.get(field)!r}, got {act.get(field)!r}"

    return None


def make_sail_config(sail_cmd, base, memory_size, ram_base, rom_base, clint_base):
    completed = subprocess.run(
        [sail_cmd, "--print-default-config"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"failed to get Sail default config: {completed.stdout.strip()}")

    config = json.loads(completed.stdout)
    config["base"]["xlen"] = 32
    config["base"]["writable_misa"] = False
    config["memory"]["misaligned"]["supported"] = False
    config["platform"]["ram"]["base"] = ram_base
    config["platform"]["ram"]["size"] = memory_size
    config["platform"]["rom"]["base"] = rom_base
    config["platform"]["rom"]["size"] = 0x1000
    config["platform"]["reset_vector"] = rom_base
    config["platform"]["clint"]["base"] = clint_base
    config["platform"]["clint"]["size"] = 0x1000
    config["platform"]["wfi_is_nop"] = True
    for name, extension in config["extensions"].items():
        extension["supported"] = name in {"Zicsr", "Zca"}
    config["extensions"]["S"]["supported"] = False
    config["extensions"]["U"]["supported"] = False
    return config


def sail_isa_string(sail_cmd, config_path):
    completed = subprocess.run(
        [sail_cmd, "--config", str(config_path), "--print-isa-string"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def parse_sail_trace(path, base, code_bytes):
    records = []
    current = None
    code_end = base + code_bytes

    def finish_current():
        nonlocal current
        if current is not None:
            if (
                current.get("mem_addr") is not None
                and current.get("mem_wdata") is None
                and current.get("rd_wdata") is not None
            ):
                current["mem_rdata"] = current["rd_wdata"]
            records.append(current)
            current = None

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        instr_match = SAIL_INSTR_RE.match(line)
        if instr_match is not None:
            finish_current()
            pc = int(instr_match.group("pc"), 16)
            if pc < base or pc >= code_end:
                continue
            insn = int(instr_match.group("insn"), 16)
            current = {
                "pc": hex32(pc),
                "insn": hex32(insn),
                "length": 2 if (insn & 0x3) != 0x3 else 4,
                "rd_we": False,
                "rd": None,
                "rd_wdata": None,
                "mem_addr": None,
                "mem_rdata": None,
                "mem_wdata": None,
                "trap": False,
                "trap_cause": None,
            }
            continue

        if current is None:
            continue

        reg_match = SAIL_REG_RE.match(line)
        if reg_match is not None:
            rd = int(reg_match.group("rd"))
            if rd != 0:
                current["rd_we"] = True
                current["rd"] = rd
                current["rd_wdata"] = hex32(int(reg_match.group("value"), 16))
            continue

        mem_match = SAIL_MEM_RE.match(line)
        if mem_match is not None:
            current["mem_addr"] = hex32(int(mem_match.group("addr"), 16))
            value = hex32(int(mem_match.group("value"), 16))
            if mem_match.group("kind") == "R":
                current["mem_rdata"] = value
            elif mem_match.group("kind") == "W":
                current["mem_wdata"] = value

    finish_current()
    return records


def trim_sail_trace(expected, actual):
    if not expected:
        return actual

    last_expected = expected[-1]
    if last_expected.get("trap"):
        expected_commits = expected[:-1]
        if len(actual) > len(expected_commits):
            terminal = actual[len(expected_commits)]
            if (
                terminal.get("pc") == last_expected.get("pc")
                and terminal.get("insn") == last_expected.get("insn")
            ):
                return actual[: len(expected_commits)]
        return actual

    if last_expected.get("insn") == "0x10500073" and len(actual) > len(expected):
        return actual[: len(expected)]

    return actual


def run_artifact(
    name,
    isa_dir,
    out_dir,
    base,
    memory_size,
    ram_base,
    rom_base,
    clint_base,
    timeout_seconds,
    skip_unsupported=False,
    allow_low_data_memory=False,
):
    hex_path = isa_dir / f"{name}.hex"
    if not hex_path.exists():
        raise RuntimeError(f"missing artifact hex: {hex_path}")

    sail_cmd = shutil.which("sail_riscv_sim")
    if sail_cmd is None:
        raise RuntimeError("missing sail_riscv_sim command; run inside nix develop after flake.nix has pkgs.sail-riscv")

    logs_dir = out_dir / "logs"
    traces_dir = out_dir / "traces"
    logs_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)

    words = read_words(hex_path)
    expected = run_model(words, base, len(words) * 4 + 32)
    expected_path = traces_dir / f"{name}.expected.jsonl"
    actual_path = traces_dir / f"{name}.sail.jsonl"
    sail_trace_path = logs_dir / f"{name}.sail.trace"
    sail_stdout_path = logs_dir / f"{name}.sail.stdout.log"
    write_jsonl(expected_path, expected)

    skip_reason = artifact_supported(expected, base, allow_low_data_memory)
    if skip_unsupported and skip_reason is not None:
        actual_path.write_text("", encoding="utf-8")
        return {
            "name": name,
            "status": "skip",
            "reason": skip_reason,
            "base": hex32(base),
            "ram_base": hex32(ram_base),
            "ram_size": hex32(memory_size),
            "allow_low_data_memory": allow_low_data_memory,
            "expected_trace": str(expected_path.relative_to(REPO_ROOT)),
            "sail_trace": str(actual_path.relative_to(REPO_ROOT)),
            "expected_items": len(expected),
            "sail_commit_items": 0,
        }

    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"ditdah32-sail-{name}-") as temp_name:
        work_dir = Path(temp_name)
        config = make_sail_config(sail_cmd, base, memory_size, ram_base, rom_base, clint_base)
        config_path = work_dir / "sail_rv32ec_compatible_config.json"
        config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        isa_string = sail_isa_string(sail_cmd, config_path)
        elf_path = build_elf(name, words, work_dir, base, logs_dir)
        timeout_cmd = shutil.which("timeout")
        if timeout_cmd is None:
            raise RuntimeError("missing timeout command")
        command = [
            timeout_cmd,
            "--signal=INT",
            "--kill-after=2s",
            f"{timeout_seconds}s",
            sail_cmd,
            "--config",
            str(config_path),
            "--trace-instr",
            "--trace-reg",
            "--trace-mem",
            "--trace-output",
            str(sail_trace_path),
            "--inst-limit",
            str(max(len(expected) + 16, 32)),
            str(elf_path),
        ]
        with sail_stdout_path.open("w", encoding="utf-8") as stdout_file:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=stdout_file,
                stderr=subprocess.STDOUT,
                check=False,
            )
        returncode = completed.returncode
        timed_out = returncode == 124

    actual = trim_sail_trace(expected, parse_sail_trace(sail_trace_path, base, len(words) * 4))
    write_jsonl(actual_path, actual)
    error = compare_sail_prefix(expected, actual, base, allow_low_data_memory)
    status = "pass" if error is None else "fail"

    return {
        "name": name,
        "status": status,
        "error": error,
        "duration_seconds": round(time.monotonic() - start, 3),
        "base": hex32(base),
        "ram_base": hex32(ram_base),
        "ram_size": hex32(memory_size),
        "allow_low_data_memory": allow_low_data_memory,
        "timeout_seconds": timeout_seconds,
        "sail_returncode": returncode,
        "sail_timed_out": timed_out,
        "sail_isa_string": isa_string,
        "expected_trace": str(expected_path.relative_to(REPO_ROOT)),
        "sail_trace": str(actual_path.relative_to(REPO_ROOT)),
        "sail_raw_trace": str(sail_trace_path.relative_to(REPO_ROOT)),
        "sail_stdout": str(sail_stdout_path.relative_to(REPO_ROOT)),
        "expected_items": len(expected),
        "sail_commit_items": len(actual),
    }


def main():
    parser = argparse.ArgumentParser(description="Run a Sail ISS smoke check for DitDah32 ISA artifacts")
    parser.add_argument("--isa-dir", type=Path, default=REPO_ROOT / "result" / "isa")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "iss" / "sail_smoke")
    parser.add_argument("--artifact", action="append", dest="artifacts", help="artifact name without .hex; may be repeated")
    parser.add_argument("--all-compatible", action="store_true", help="run every compatible artifact and skip explicitly unsupported ones")
    parser.add_argument("--base", type=lambda text: int(text, 0), default=DEFAULT_BASE)
    parser.add_argument("--ram-base", type=lambda text: int(text, 0), default=DEFAULT_BASE)
    parser.add_argument("--memory-size", type=lambda text: int(text, 0), default=0x0010_0000)
    parser.add_argument("--rom-base", type=lambda text: int(text, 0), default=0x1000)
    parser.add_argument("--clint-base", type=lambda text: int(text, 0), default=0x0200_0000)
    parser.add_argument("--allow-low-data-memory", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=2.0)
    args = parser.parse_args()

    if shutil.which("sail_riscv_sim") is None:
        print("missing sail_riscv_sim command; run inside nix develop after flake.nix has pkgs.sail-riscv", file=sys.stderr)
        return 1

    isa_dir = args.isa_dir
    out_dir = args.out_dir
    if not isa_dir.is_absolute():
        isa_dir = REPO_ROOT / isa_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    limitations = [
        "The packaged Sail model is configured as rv32ic_zicsr_zca, not strict RV32E.",
        "This Sail gate compares legal RV32E/RV32EC programs only and does not close x16-x31 illegal-register behavior.",
        "Terminal ebreak is treated as the stop condition and is not counted as a committed Sail instruction.",
    ]
    if args.allow_low_data_memory:
        limitations.append("Low data-memory artifacts are enabled by a flat Sail RAM configuration.")
    else:
        limitations.append("Low data-memory artifacts remain outside this compatible matrix until the flat-memory strategy is enabled.")

    report = {
        "status": "pass",
        "scope": "sail_prefix_compare",
        "isa": "rv32ic_zicsr_zca_sail_model_on_rv32ec_legal_programs",
        "limitations": limitations,
        "base": hex32(args.base),
        "ram_base": hex32(args.ram_base),
        "ram_size": hex32(args.memory_size),
        "allow_low_data_memory": args.allow_low_data_memory,
        "artifacts": [],
        "started_unix": int(time.time()),
    }

    failed = False
    artifacts = discover_artifacts(isa_dir) if args.all_compatible else (args.artifacts or DEFAULT_ARTIFACTS)
    for name in artifacts:
        print(f"[RUN] sail smoke: {name}", flush=True)
        try:
            result = run_artifact(
                name,
                isa_dir,
                out_dir,
                args.base,
                args.memory_size,
                args.ram_base,
                args.rom_base,
                args.clint_base,
                args.timeout_seconds,
                skip_unsupported=args.all_compatible,
                allow_low_data_memory=args.allow_low_data_memory,
            )
        except Exception as exc:
            result = {"name": name, "status": "fail", "error": str(exc)}
        report["artifacts"].append(result)
        failed = failed or result["status"] == "fail"
        print(f"[{result['status'].upper()}] sail smoke: {name}", flush=True)
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
    report_path = out_dir / "sail_smoke.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[REPORT] {report_path}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
