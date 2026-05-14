#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from run_spike_iss_smoke import DEFAULT_BASE, build_elf, hex32, parse_spike_log, write_jsonl
from rv32ec_encode import ProgramImage, b_type, c_addi, c_cr, c_li, c_lui, c_lwsp, c_slli, c_swsp, csrrs, i_type, j_type, r_type, s_type
from rv32ec_model import RV32ECModel


REPO_ROOT = Path(__file__).resolve().parents[1]
CSR_MSCRATCH = 0x340


@dataclass(frozen=True)
class StrictCase:
    name: str
    words: list[int]
    description: str
    expected_trap_cause: str = "rv32e_register"


def image_words(items):
    image = ProgramImage()
    for width, value in items:
        if width == 2:
            image.add16(value)
        elif width == 4:
            image.add32(value)
        else:
            raise ValueError(f"unsupported instruction width: {width}")
    return image.words()


def strict_cases():
    return [
        StrictCase("addi_rd_x16", [i_type(1, 0, 0x0, 16)], "ADDI names x16 as rd."),
        StrictCase("addi_rs1_x16", [i_type(1, 16, 0x0, 1)], "ADDI names x16 as rs1."),
        StrictCase("add_rd_x16", [r_type(0x00, 1, 2, 0x0, 16)], "ADD names x16 as rd."),
        StrictCase("add_rs1_x16", [r_type(0x00, 1, 16, 0x0, 2)], "ADD names x16 as rs1."),
        StrictCase("add_rs2_x16", [r_type(0x00, 16, 1, 0x0, 2)], "ADD names x16 as rs2."),
        StrictCase("lw_rd_x16", [i_type(0, 1, 0x2, 16, 0x03)], "LW names x16 as rd."),
        StrictCase("lw_rs1_x16", [i_type(0, 16, 0x2, 1, 0x03)], "LW names x16 as rs1."),
        StrictCase("sw_rs1_x16", [s_type(0, 1, 16, 0x2)], "SW names x16 as rs1."),
        StrictCase("sw_rs2_x16", [s_type(0, 16, 1, 0x2)], "SW names x16 as rs2."),
        StrictCase("beq_rs1_x16", [b_type(4, 1, 16, 0x0)], "BEQ names x16 as rs1."),
        StrictCase("beq_rs2_x16", [b_type(4, 16, 1, 0x0)], "BEQ names x16 as rs2."),
        StrictCase("jal_rd_x16", [j_type(0, 16)], "JAL names x16 as rd."),
        StrictCase("jalr_rd_x16", [i_type(0, 1, 0x0, 16, 0x67)], "JALR names x16 as rd."),
        StrictCase("jalr_rs1_x16", [i_type(0, 16, 0x0, 1, 0x67)], "JALR names x16 as rs1."),
        StrictCase("csrrs_rd_x16", [csrrs(CSR_MSCRATCH, 0, 16)], "CSRRS names x16 as rd."),
        StrictCase("csrrs_rs1_x16", [csrrs(CSR_MSCRATCH, 16, 1)], "CSRRS names x16 as rs1."),
        StrictCase("c_addi_rd_x16", image_words([(2, c_addi(16, 1))]), "C.ADDI names x16 as rd/rs1."),
        StrictCase("c_li_rd_x16", image_words([(2, c_li(16, 1))]), "C.LI names x16 as rd."),
        StrictCase("c_lui_rd_x16", image_words([(2, c_lui(16, 1))]), "C.LUI names x16 as rd."),
        StrictCase("c_slli_rd_x16", image_words([(2, c_slli(16, 1))]), "C.SLLI names x16 as rd/rs1."),
        StrictCase("c_lwsp_rd_x16", image_words([(2, c_lwsp(16, 0))]), "C.LWSP names x16 as rd."),
        StrictCase("c_swsp_rs2_x16", image_words([(2, c_swsp(16, 0))]), "C.SWSP names x16 as rs2."),
        StrictCase("c_mv_rs2_x16", image_words([(2, c_cr(0, 1, 16))]), "C.MV names x16 as rs2."),
        StrictCase("c_add_rd_x16", image_words([(2, c_cr(1, 16, 1))]), "C.ADD names x16 as rd/rs1."),
        StrictCase("c_jr_rs1_x16", image_words([(2, c_cr(0, 16, 0))]), "C.JR names x16 as rs1."),
    ]


def run_model(case, base, max_steps):
    model = RV32ECModel(pc=base)
    model.load_words(case.words, base=base)
    model.run(max_steps)
    return model.trace


def split_before_trap(trace):
    for index, item in enumerate(trace):
        if item.get("trap"):
            return trace[:index], item
    return trace, None


def strip_cycle(item):
    return {key: value for key, value in item.items() if key != "cycle"}


def compare_pretrap(expected, actual):
    if len(actual) != len(expected):
        return f"Spike commit count mismatch before trap: expected {len(expected)}, got {len(actual)}"
    fields = ("pc", "insn", "length", "rd_we", "rd", "rd_wdata", "mem_addr", "mem_rdata", "mem_wdata", "trap", "trap_cause")
    for index, (exp, act) in enumerate(zip(expected, actual)):
        for field in fields:
            if exp.get(field) != act.get(field):
                return f"item {index} field {field}: expected {exp.get(field)!r}, got {act.get(field)!r}"
    return None


def run_case(case, out_dir, base, timeout_seconds):
    logs_dir = out_dir / "logs"
    traces_dir = out_dir / "traces"
    logs_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)

    expected = run_model(case, base, max_steps=8)
    expected_commits, trap_item = split_before_trap(expected)
    expected_path = traces_dir / f"{case.name}.expected.jsonl"
    spike_path = traces_dir / f"{case.name}.spike.jsonl"
    write_jsonl(expected_path, expected)

    result = {
        "name": case.name,
        "description": case.description,
        "base": hex32(base),
        "expected_trap_cause": case.expected_trap_cause,
        "expected_trace": str(expected_path.relative_to(REPO_ROOT)),
        "spike_trace": str(spike_path.relative_to(REPO_ROOT)),
    }

    if trap_item is None:
        result.update({
            "status": "fail",
            "error": "local model did not trap",
            "expected_items": len(expected),
            "spike_commit_items": 0,
        })
        spike_path.write_text("", encoding="utf-8")
        return result

    if trap_item.get("trap_cause") != case.expected_trap_cause:
        result.update({
            "status": "fail",
            "error": f"local model trap cause mismatch: expected {case.expected_trap_cause}, got {trap_item.get('trap_cause')}",
            "expected_items": len(expected),
            "spike_commit_items": 0,
        })
        spike_path.write_text("", encoding="utf-8")
        return result

    start = time.monotonic()
    spike_log_path = logs_dir / f"{case.name}.spike.log"
    spike_stderr_path = logs_dir / f"{case.name}.spike.stderr.log"
    with tempfile.TemporaryDirectory(prefix=f"ditdah32-spike-strict-{case.name}-") as temp_name:
        work_dir = Path(temp_name)
        elf_path = build_elf(case.name, case.words, work_dir, base, logs_dir)
        timeout_cmd = shutil.which("timeout")
        if timeout_cmd is None:
            raise RuntimeError("missing timeout command")
        command = [
            timeout_cmd,
            "--signal=INT",
            "--kill-after=2s",
            f"{timeout_seconds}s",
            "spike",
            "--isa=rv32ec_zicsr",
            "--priv=m",
            f"-m0x00000000:0x100000,0x{base:08x}:0x100000",
            "--log-commits",
            f"--log={spike_log_path}",
            str(elf_path),
        ]
        with spike_stderr_path.open("w", encoding="utf-8") as stderr_file:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                check=False,
            )

    actual = parse_spike_log(spike_log_path, base, len(case.words) * 4)
    write_jsonl(spike_path, actual)
    error = compare_pretrap([strip_cycle(item) for item in expected_commits], actual)
    result.update({
        "status": "pass" if error is None else "fail",
        "error": error,
        "duration_seconds": round(time.monotonic() - start, 3),
        "spike_returncode": completed.returncode,
        "spike_timed_out": completed.returncode == 124,
        "spike_log": str(spike_log_path.relative_to(REPO_ROOT)),
        "spike_stderr": str(spike_stderr_path.relative_to(REPO_ROOT)),
        "expected_items": len(expected),
        "expected_pretrap_commits": len(expected_commits),
        "spike_commit_items": len(actual),
        "local_trap": strip_cycle(trap_item),
    })
    return result


def main():
    parser = argparse.ArgumentParser(description="Run strict RV32E external ISS negative checks with Spike")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "iss" / "spike_rv32e_strict")
    parser.add_argument("--base", type=lambda text: int(text, 0), default=DEFAULT_BASE)
    parser.add_argument("--timeout-seconds", type=float, default=1.0)
    args = parser.parse_args()

    if shutil.which("spike") is None:
        print("missing spike command; run inside nix develop after flake.nix has pkgs.spike")
        return 1

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "status": "pass",
        "scope": "spike_rv32e_strict_negative_prefix_compare",
        "isa": "rv32ec_zicsr",
        "base": hex32(args.base),
        "limitations": [
            "Spike commit logs do not expose DitDah32 trap-cause names.",
            "This gate proves the local model reports rv32e_register and Spike does not commit the RV32E-illegal instruction.",
            "The check is a strict RV32E negative supplement to the legal-program Sail full matrix.",
        ],
        "artifacts": [],
        "started_unix": int(time.time()),
    }

    failed = False
    for case in strict_cases():
        print(f"[RUN] spike rv32e strict: {case.name}", flush=True)
        try:
            result = run_case(case, out_dir, args.base, args.timeout_seconds)
        except Exception as exc:
            result = {"name": case.name, "status": "fail", "error": str(exc)}
        report["artifacts"].append(result)
        failed = failed or result["status"] == "fail"
        print(f"[{result['status'].upper()}] spike rv32e strict: {case.name}", flush=True)
        if result.get("error"):
            print(result["error"], flush=True)

    report["summary"] = {
        "pass": sum(1 for item in report["artifacts"] if item["status"] == "pass"),
        "fail": sum(1 for item in report["artifacts"] if item["status"] == "fail"),
        "total": len(report["artifacts"]),
    }
    report["status"] = "fail" if failed else "pass"
    report_path = out_dir / "spike_rv32e_strict.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[REPORT] {report_path}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
