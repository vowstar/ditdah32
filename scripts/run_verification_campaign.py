#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    description: str


SMOKE_STEPS = [
    Step(
        "model_pytest",
        ["python3", "-m", "pytest", "test/test_model"],
        "Run directed Python reference model tests.",
    ),
    Step(
        "isa_pytest",
        ["python3", "-m", "pytest", "test/test_isa"],
        "Run directed ISA regression unit tests.",
    ),
    Step(
        "script_pytest",
        ["python3", "-m", "pytest", "test/test_scripts"],
        "Run unit tests for repository helper scripts.",
    ),
    Step(
        "isa_artifacts",
        ["python3", "scripts/rv32ec_isa_regress.py", "--out-dir", "result/isa"],
        "Regenerate reusable ISA hex and JSONL trace artifacts.",
    ),
    Step(
        "benchmark_build",
        ["python3", "scripts/build_benchmarks.py", "--out-dir", "result/bench"],
        "Build RV32EC CoreMark and Dhrystone benchmark images.",
    ),
    Step(
        "rtl_build",
        ["build-ditdah32", "--trace"],
        "Generate trace-enabled DitDah32 Verilog from Zaozi source for RTL verification.",
    ),
]


CI_SMOKE_STEPS = SMOKE_STEPS[:4]


RTL_MATRIX_STEPS = [
    Step(
        "formal_safety",
        ["python3", "scripts/run_formal.py", "--depth", "24"],
        "Run local Yosys SMTBMC safety checks over the generated RTL and formal harness.",
    ),
    Step(
        "rvfi_lite",
        ["python3", "scripts/run_rvfi_lite.py", "--depth", "24"],
        "Run RVFI-lite adapter consistency checks over the generated RTL trace pins.",
    ),
    Step(
        "rtl_generated_isa_matrix",
        [
            "python3",
            "scripts/run_rtl_isa_matrix.py",
            "--isa-dir",
            "result/isa",
            "--out-dir",
            "result/rtl_trace/isa_artifacts",
        ],
        "Run every generated ISA artifact on RTL and compare JSONL traces against the Python ISS.",
    ),
    Step(
        "coverage_matrix",
        [
            "python3",
            "scripts/rv32ec_coverage.py",
            "--out-dir",
            "result/coverage",
            "--require-artifacts",
        ],
        "Generate RV32EC instruction and illegal-class coverage report.",
    ),
    Step(
        "axi_backpressure_stress",
        [
            "make",
            "-C",
            "test/test_ditdah32",
            "TESTCASE=axi_lite_backpressure_event_log_stays_protocol_clean",
        ],
        "Run deterministic randomized AXI-Lite backpressure stress with event-log protocol checks.",
    ),
]


FULL_STEPS = [
    Step(
        "rtl_cocotb_full",
        ["make", "-C", "test/test_ditdah32"],
        "Run the full directed cocotb RTL suite, including benchmark completion tests.",
    ),
]

SIGNOFF_STEPS = [
    Step(
        "spike_compatible_matrix",
        [
            "python3",
            "scripts/run_spike_iss_smoke.py",
            "--isa-dir",
            "result/isa",
            "--out-dir",
            "result/iss/spike_matrix",
            "--all-compatible",
        ],
        "Run the Spike-compatible external ISS matrix and explicitly report skipped unsupported artifacts.",
    ),
    Step(
        "sail_full_isa_matrix",
        [
            "python3",
            "scripts/run_sail_iss_smoke.py",
            "--isa-dir",
            "result/isa",
            "--out-dir",
            "result/iss/sail_matrix",
            "--all-compatible",
            "--ram-base",
            "0x0",
            "--memory-size",
            "0x80100000",
            "--rom-base",
            "0x90000000",
            "--clint-base",
            "0xa0000000",
            "--allow-low-data-memory",
        ],
        "Run the full generated ISA artifact matrix through Sail with a flat low-memory-compatible RAM map.",
    ),
    Step(
        "spike_rv32e_strict_negative",
        [
            "python3",
            "scripts/run_spike_rv32e_strict.py",
            "--out-dir",
            "result/iss/spike_rv32e_strict",
        ],
        "Run strict RV32E x16-x31 negative checks against Spike and the local trap model.",
    ),
    Step(
        "spike_highmem_artifacts",
        [
            "python3",
            "scripts/rv32ec_isa_regress.py",
            "--out-dir",
            "result/iss/spike_artifacts",
            "--spike-compatible",
        ],
        "Generate high-memory RV32EC ISA artifacts for Spike external ISS load/store comparison.",
    ),
    Step(
        "spike_highmem_matrix",
        [
            "python3",
            "scripts/run_rtl_isa_matrix.py",
            "--isa-dir",
            "result/iss/spike_artifacts",
            "--out-dir",
            "result/rtl_trace/spike_highmem_artifacts",
        ],
        "Run the high-memory supplemental RV32EC artifacts on RTL and compare against the Python ISS trace.",
    ),
    Step(
        "spike_highmem_external_iss",
        [
            "python3",
            "scripts/run_spike_iss_smoke.py",
            "--isa-dir",
            "result/iss/spike_artifacts",
            "--out-dir",
            "result/iss/spike_highmem",
            "--all-compatible",
        ],
        "Run Spike external ISS comparison over the high-memory supplemental RV32EC artifact set.",
    ),
    Step(
        "sail_highmem_artifacts",
        [
            "python3",
            "scripts/rv32ec_isa_regress.py",
            "--out-dir",
            "result/iss/sail_artifacts",
            "--spike-compatible",
        ],
        "Generate high-memory RV32EC ISA artifacts for Sail external ISS load/store comparison.",
    ),
    Step(
        "sail_highmem_matrix",
        [
            "python3",
            "scripts/run_rtl_isa_matrix.py",
            "--isa-dir",
            "result/iss/sail_artifacts",
            "--out-dir",
            "result/rtl_trace/sail_highmem_artifacts",
        ],
        "Run the Sail high-memory supplemental RV32EC artifacts on RTL and compare against the Python ISS trace.",
    ),
    Step(
        "sail_highmem_external_iss",
        [
            "python3",
            "scripts/run_sail_iss_smoke.py",
            "--isa-dir",
            "result/iss/sail_artifacts",
            "--out-dir",
            "result/iss/sail_highmem",
            "--all-compatible",
        ],
        "Run Sail external ISS comparison over legal high-memory RV32EC artifact programs.",
    ),
    Step(
        "external_iss_full_report",
        [
            "python3",
            "scripts/external_iss_full_report.py",
            "--out-dir",
            "result/iss/external_iss_full",
        ],
        "Aggregate full external ISS evidence from Sail legal matrices and Spike strict RV32E negative checks.",
    ),
    Step(
        "riscv_dv",
        [
            "python3",
            "scripts/run_riscv_dv.py",
            "--config",
            "test/riscv_dv/ditdah32_rv32ec.yaml",
        ],
        "Run the checked-in RISCV-DV RV32EC target/testlist through generation, legality scan, compile, and RTL trace comparison.",
    ),
    Step(
        "rvfi_standard",
        ["python3", "scripts/run_rvfi.py", "--depth", "24"],
        "Run the external riscv-formal consistency, selected CSR, CSR state, non-faulting RVFI_BUS, interrupt entry shape, bounded liveness, causal, hang, and illegal-instruction subsets and record disabled property groups.",
    ),
    Step(
        "trace_config_audit",
        ["python3", "scripts/trace_config_audit.py", "--out-dir", "result/verification"],
        "Build and audit production no-trace and verification trace-enabled RTL configurations.",
    ),
    Step(
        "signoff_coverage",
        ["python3", "scripts/run_signoff_coverage.py"],
        "Run Verilator HDL line and branch coverage gates over the full cocotb suite.",
    ),
    Step(
        "tool_availability_audit",
        ["python3", "scripts/tool_availability_audit.py", "--out-dir", "result/verification"],
        "Record reproducible availability evidence for local and planned verification tools.",
    ),
    Step(
        "open_gap_audit",
        ["python3", "scripts/open_gap_audit.py", "--out-dir", "result/verification"],
        "Write machine-readable open verification gap status.",
    ),
]


PROFILES = {
    "ci-smoke": CI_SMOKE_STEPS,
    "smoke": SMOKE_STEPS,
    "rtl": SMOKE_STEPS + RTL_MATRIX_STEPS,
    "full": SMOKE_STEPS + RTL_MATRIX_STEPS + FULL_STEPS,
    "signoff": SMOKE_STEPS + RTL_MATRIX_STEPS + FULL_STEPS + SIGNOFF_STEPS,
}


def run_text(command):
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def git_metadata():
    metadata = {
        "available": False,
        "head": None,
        "branch": None,
        "dirty": None,
        "status_porcelain": None,
        "error": None,
    }

    returncode, stdout, stderr = run_text(["git", "rev-parse", "--is-inside-work-tree"])
    if returncode != 0 or stdout != "true":
        metadata["error"] = stderr or stdout or "not inside a git work tree"
        return metadata

    metadata["available"] = True
    for key, command in (
        ("head", ["git", "rev-parse", "HEAD"]),
        ("branch", ["git", "branch", "--show-current"]),
    ):
        returncode, stdout, stderr = run_text(command)
        if returncode == 0:
            metadata[key] = stdout
        else:
            metadata["error"] = stderr or stdout

    returncode, stdout, stderr = run_text(["git", "status", "--porcelain"])
    if returncode == 0:
        metadata["status_porcelain"] = stdout
        metadata["dirty"] = bool(stdout)
    else:
        metadata["dirty"] = None
        metadata["error"] = stderr or stdout
    return metadata


def run_step(step, logs_dir):
    start = time.monotonic()
    log_path = logs_dir / f"{step.name}.log"
    print(f"[RUN] {step.name}: {' '.join(step.command)}", flush=True)

    with log_path.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            step.command,
            cwd=REPO_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )

    duration = time.monotonic() - start
    status = "pass" if completed.returncode == 0 else "fail"
    print(f"[{status.upper()}] {step.name}: {duration:.2f}s, log={log_path}", flush=True)
    return {
        "name": step.name,
        "description": step.description,
        "command": step.command,
        "returncode": completed.returncode,
        "status": status,
        "duration_seconds": round(duration, 3),
        "log": str(log_path.relative_to(REPO_ROOT)),
    }


def main():
    parser = argparse.ArgumentParser(description="Run DitDah32 verification campaign profiles")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="full")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    parser.add_argument("--keep-going", action="store_true", help="continue running steps after a failure")
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    logs_dir = out_dir / args.profile / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "profile": args.profile,
        "repo": str(REPO_ROOT),
        "git": git_metadata(),
        "started_unix": int(time.time()),
        "steps": [],
    }

    campaign_start = time.monotonic()
    failed = False
    for step in PROFILES[args.profile]:
        result = run_step(step, logs_dir)
        report["steps"].append(result)
        failed = failed or result["status"] != "pass"
        if failed and not args.keep_going:
            break

    report["duration_seconds"] = round(time.monotonic() - campaign_start, 3)
    report["status"] = "fail" if failed else "pass"

    report_path = out_dir / f"{args.profile}.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[REPORT] {report_path}", flush=True)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
