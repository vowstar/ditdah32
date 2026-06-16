#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_slang_so():
    slang_so = os.environ.get("SLANG_SO")
    if not slang_so or not Path(slang_so).is_file():
        raise SystemExit(
            "SLANG_SO is not set or does not point to slang.so; run inside "
            "'nix develop' so the yosys-slang plugin is available."
        )
    return slang_so


# The trace surface lives in the layer("DV") bind collateral. read_slang reads
# the core and resolves the probe XMRs through ditdah32_trace_top; the adapter
# (with anyseq inputs) is then read with yosys read_verilog -formal.
TRACE_TOP = "formal/riscv_formal/ditdah32/ditdah32_trace_top.sv"


def read_slang_dut_cmd():
    slang_so = resolve_slang_so()
    return (
        f"plugin -i {slang_so}; "
        f"read_slang -Iresult {TRACE_TOP} result/DitDah32.sv result/DitDah32_DV.sv "
        f"result/layers-DitDah32-DV.sv --top ditdah32_trace_top; "
    )


def run(cmd, log_path):
    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return {
        "command": cmd,
        "duration_seconds": round(time.monotonic() - start, 3),
        "log": str(log_path.relative_to(REPO_ROOT)),
        "returncode": completed.returncode,
        "status": "pass" if completed.returncode == 0 else "fail",
    }


def main():
    parser = argparse.ArgumentParser(description="Run DitDah32 local formal safety checks")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "formal")
    parser.add_argument("--depth", type=int, default=24)
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    smt_path = out_dir / "ditdah32_safety.smt2"
    vcd_path = out_dir / "ditdah32_safety.vcd"
    yosys_log = out_dir / "yosys.log"
    smtbmc_log = out_dir / "smtbmc.log"

    steps = []
    steps.append(
        run(
            [
                "yosys",
                "-q",
                "-p",
                (
                    read_slang_dut_cmd()
                    + "read_verilog -formal -sv formal/ditdah32_safety.sv; "
                    "prep -top DitDah32Safety; "
                    f"write_smt2 -wires {smt_path}"
                ),
            ],
            yosys_log,
        )
    )

    if steps[-1]["status"] == "pass":
        steps.append(
            run(
                [
                    "yosys-smtbmc",
                    "-s",
                    "z3",
                    "-t",
                    str(args.depth),
                    "--dump-vcd",
                    str(vcd_path),
                    str(smt_path),
                ],
                smtbmc_log,
            )
        )

    status = "pass" if all(step["status"] == "pass" for step in steps) else "fail"
    report = {
        "depth": args.depth,
        "engine": "yosys-smtbmc",
        "solver": "z3",
        "status": status,
        "steps": steps,
    }
    report_path = out_dir / "formal.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"formal {status}: {report_path.relative_to(REPO_ROOT)}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
