#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

TRACE_PORTS = [
    "trace_valid",
    "trace_pc",
    "trace_next_pc",
    "trace_instr",
    "trace_len",
    "trace_rd_we",
    "trace_rd",
    "trace_rd_wdata",
    "trace_rs1_addr",
    "trace_rs1_rdata",
    "trace_rs2_addr",
    "trace_rs2_rdata",
    "trace_mem_addr",
    "trace_mem_rmask",
    "trace_mem_wmask",
    "trace_mem_rdata",
    "trace_mem_wdata",
    "trace_csr_addr",
    "trace_csr_rmask",
    "trace_csr_wmask",
    "trace_csr_rdata",
    "trace_csr_wdata",
    "trace_trap",
    "trace_trap_cause",
]


def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def run(command, log_path, env=None):
    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return {
        "command": command,
        "duration_seconds": round(time.monotonic() - start, 3),
        "log": rel(log_path),
        "returncode": completed.returncode,
        "status": "pass" if completed.returncode == 0 else "fail",
    }


def build_config(name, trace_enabled, build_root, logs_dir):
    output_dir = build_root / name
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["OUTPUT_DIR"] = str(output_dir)
    command = ["build-ditdah32", "--trace" if trace_enabled else "--no-trace"]
    step = run(command, logs_dir / f"build_{name}.log", env=env)
    step["name"] = name
    step["trace_enabled"] = trace_enabled
    step["output_dir"] = rel(output_dir)
    step["rtl"] = rel(output_dir / "DitDah32.sv")
    step["config"] = rel(output_dir / "ditdah32_config.json")
    return step


def extract_module_header(verilog_text):
    match = re.search(r"\bmodule\s+DitDah32\s*\((.*?)\n\);", verilog_text, flags=re.DOTALL)
    if not match:
        raise ValueError("DitDah32 module header was not found.")
    return match.group(1)


def check_module_text(verilog_text, expect_trace):
    # The trace surface now lowers to the layer("DV") bind collateral, never
    # into the DitDah32 main module. The main module must therefore be free of
    # trace ports and trace state in BOTH the production and verification
    # builds; expect_trace selects whether the DV collateral is expected to
    # exist (checked separately by audit_artifact).
    header = extract_module_header(verilog_text)
    trace_ports = {
        port: bool(re.search(rf"\b{re.escape(port)}\b", header))
        for port in TRACE_PORTS
    }
    rvfi_ports = sorted(set(re.findall(r"\brvfi_[A-Za-z0-9_]*\b", header)))
    trace_tokens = sorted(
        set(re.findall(r"\btrace(?:_[A-Za-z0-9_]+|[A-Za-z0-9]*Reg)\b", verilog_text))
    )
    rvfi_tokens = sorted(set(re.findall(r"\brvfi_[A-Za-z0-9_]*\b", verilog_text)))
    present_trace_ports = [port for port, present in trace_ports.items() if present]

    missing = []
    if present_trace_ports:
        missing.append("DitDah32 main module exposes trace ports: " + ", ".join(present_trace_ports))
    if trace_tokens:
        missing.append("DitDah32 main module contains trace state or wiring: " + ", ".join(trace_tokens))
    if rvfi_ports:
        missing.append("Core top-level exposes direct RVFI ports: " + ", ".join(rvfi_ports))

    return {
        "expect_trace": expect_trace,
        "trace_ports": trace_ports,
        "rvfi_ports": rvfi_ports,
        "trace_tokens": trace_tokens,
        "rvfi_tokens": rvfi_tokens,
        "status": "pass" if not missing else "fail",
        "missing": missing,
    }


def check_dv_collateral(output_dir, expect_trace):
    # Verification builds emit the layer("DV") bind collateral carrying the
    # trace probes; production builds must not ship it.
    dv_module = output_dir / "DitDah32_DV.sv"
    ref_macros = output_dir / "ref_DitDah32.sv"
    bind_file = output_dir / "layers-DitDah32-DV.sv"
    present = dv_module.exists()
    missing = []
    if expect_trace:
        if not present:
            missing.append(f"Verification build is missing DV collateral: {rel(dv_module)}")
        elif "traceValidReg" not in dv_module.read_text(encoding="utf-8"):
            missing.append("DV collateral does not carry the trace probe registers.")
        if not ref_macros.exists():
            missing.append(f"Verification build is missing probe XMR macros: {rel(ref_macros)}")
        if not bind_file.exists():
            missing.append(f"Verification build is missing the DV bind file: {rel(bind_file)}")
    else:
        leaked = [rel(p) for p in (dv_module, ref_macros, bind_file) if p.exists()]
        if leaked:
            missing.append("Production build ships DV trace collateral: " + ", ".join(leaked))
    return {
        "status": "pass" if not missing else "fail",
        "dv_collateral_present": present,
        "missing": missing,
    }


def check_config_json(config_path, expect_trace):
    if not config_path.exists():
        return {
            "status": "fail",
            "missing": [f"Missing config file: {rel(config_path)}"],
        }

    config = json.loads(config_path.read_text(encoding="utf-8"))
    actual = bool(config.get("enableTrace"))
    missing = []
    if actual != expect_trace:
        missing.append(f"enableTrace is {actual}, expected {expect_trace}.")
    return {
        "status": "pass" if not missing else "fail",
        "enableTrace": actual,
        "missing": missing,
    }


def audit_artifact(name, rtl_path, config_path, expect_trace):
    missing = []
    checks = {}
    if rtl_path.exists():
        try:
            checks["module_header"] = check_module_text(rtl_path.read_text(encoding="utf-8"), expect_trace)
        except ValueError as exc:
            checks["module_header"] = {"status": "fail", "missing": [str(exc)]}
    else:
        checks["module_header"] = {"status": "fail", "missing": [f"Missing RTL file: {rel(rtl_path)}"]}

    checks["dv_collateral"] = check_dv_collateral(rtl_path.parent, expect_trace)
    checks["config"] = check_config_json(config_path, expect_trace)
    for check in checks.values():
        missing.extend(check.get("missing", []))
    return {
        "name": name,
        "rtl": rel(rtl_path),
        "config": rel(config_path),
        "expect_trace": expect_trace,
        "checks": checks,
        "status": "pass" if not missing else "fail",
        "missing": missing,
    }


def write_markdown(report, path):
    lines = [
        "# DitDah32 Trace Configuration Audit",
        "",
        f"Status: `{report['status']}`",
        "",
        "| configuration | expected trace | status | RTL |",
        "| --- | --- | --- | --- |",
    ]
    for artifact in report["artifacts"]:
        lines.append(
            f"| {artifact['name']} | {str(artifact['expect_trace']).lower()} | "
            f"`{artifact['status']}` | `{artifact['rtl']}` |"
        )
    if report["missing"]:
        lines.extend(["", "## Missing"])
        lines.extend(f"- {item}" for item in report["missing"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit production and verification trace/RVFI configuration")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    parser.add_argument("--build-root", type=Path, default=REPO_ROOT / "result" / "trace_config")
    parser.add_argument("--skip-build", action="store_true", help="audit existing artifacts under --build-root")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    build_root = args.build_root if args.build_root.is_absolute() else REPO_ROOT / args.build_root
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    builds = []
    if not args.skip_build:
        builds.append(build_config("production_no_trace", False, build_root, logs_dir))
        builds.append(build_config("verification_trace", True, build_root, logs_dir))

    artifacts = [
        audit_artifact(
            "production_no_trace",
            build_root / "production_no_trace" / "DitDah32.sv",
            build_root / "production_no_trace" / "ditdah32_config.json",
            False,
        ),
        audit_artifact(
            "verification_trace",
            build_root / "verification_trace" / "DitDah32.sv",
            build_root / "verification_trace" / "ditdah32_config.json",
            True,
        ),
    ]

    missing = []
    for build in builds:
        if build["status"] != "pass":
            missing.append(f"{build['name']} build failed; see {build['log']}.")
    for artifact in artifacts:
        missing.extend(artifact["missing"])

    report = {
        "profile": "trace-config",
        "equivalence_class": "build_time_interface_configuration",
        "status": "pass" if not missing else "fail",
        "builds": builds,
        "artifacts": artifacts,
        "missing": missing,
        "policy": {
            "production": "The DitDah32 main module must not expose trace_* or rvfi_* top-level ports in any build.",
            "production_internal_trace": "The DitDah32 main module must not contain trace state or trace wiring; the trace surface lives in the layer(\"DV\") bind collateral.",
            "production_collateral": "The production (--no-trace) build must not ship the DV trace collateral.",
            "verification": "The verification (--trace) build emits the DV bind collateral (DitDah32_DV.sv, ref_DitDah32.sv) carrying the trace probes consumed by cocotb and the riscv-formal flow.",
            "rvfi": "DitDah32 does not expose direct rvfi_* core ports; RVFI is provided by the formal wrapper over the DV probe XMRs.",
        },
    }

    json_path = out_dir / "trace_config.json"
    md_path = out_dir / "trace_config.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, md_path)
    print(f"trace-config {report['status']}: {rel(json_path)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
