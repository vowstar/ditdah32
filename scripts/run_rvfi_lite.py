#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LIMITATIONS = [
    "RVFI-lite derives retirement from DitDah32 trace pins, not a complete riscv-formal RVFI implementation.",
    "rvfi_pc_wdata is driven by trace_next_pc but has not been checked by the external riscv-formal property suite.",
    "rvfi_rs1/rs2 fields are not available because the current trace interface does not expose register-read operands.",
    "rvfi_mem_* fields are not available because memory trace metadata is reconstructed in cocotb, not exposed as RTL pins.",
    "This check proves adapter consistency only; it does not run the external riscv-formal property suite.",
]


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
    parser = argparse.ArgumentParser(description="Run DitDah32 RVFI-lite adapter formal checks")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "formal" / "rvfi_lite")
    parser.add_argument("--depth", type=int, default=24)
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    smt_path = out_dir / "ditdah32_rvfi_lite.smt2"
    vcd_path = out_dir / "ditdah32_rvfi_lite.vcd"
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
                    "read_verilog -formal -sv result/DitDah32.sv formal/ditdah32_rvfi_lite.sv; "
                    "prep -top DitDah32RvfiLite; "
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
        "limitations": LIMITATIONS,
        "profile": "rvfi-lite",
        "solver": "z3",
        "status": status,
        "steps": steps,
    }
    report_path = out_dir / "rvfi_lite.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"rvfi-lite {status}: {report_path.relative_to(REPO_ROOT)}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
