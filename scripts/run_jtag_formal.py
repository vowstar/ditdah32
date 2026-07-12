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
RTL_FILES = [
    "result/jtag/DitDah32JtagDtm.sv",
    "result/jtag/DitDah32DebugModule.sv",
]
HARNESS = "formal/ditdah32_jtag.sv"
PROBE_TOP = "formal/ditdah32_jtag_top.sv"
PROOFS = [
    ("dtm_protocol", "DitDah32JtagDtmFormal", "ditdah32_jtag_dtm_top"),
    ("dm_protocol", "DitDah32DebugModuleFormal", "ditdah32_debug_module_top"),
]


def run(command, log_path):
    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return {
        "command": command,
        "duration_seconds": round(time.monotonic() - start, 3),
        "log": str(log_path.relative_to(REPO_ROOT)),
        "returncode": completed.returncode,
        "status": "pass" if completed.returncode == 0 else "fail",
    }


def resolve_slang_so():
    slang_so = os.environ.get("SLANG_SO")
    if not slang_so or not Path(slang_so).is_file():
        raise SystemExit("SLANG_SO is unavailable; run inside nix develop")
    return slang_so


def run_proof(name, top, probe_top, depth, out_dir, slang_so):
    proof_dir = out_dir / name
    proof_dir.mkdir(parents=True, exist_ok=True)
    smt_path = proof_dir / f"{name}.smt2"
    vcd_path = proof_dir / f"{name}.vcd"
    read_files = " ".join([PROBE_TOP] + RTL_FILES)
    steps = [
        run(
            [
                "yosys",
                "-q",
                "-p",
                (
                    f"plugin -i {slang_so}; "
                    f"read_slang {read_files} --top {probe_top}; "
                    f"read_verilog -formal -sv {HARNESS}; "
                    f"prep -top {top}; write_smt2 -wires {smt_path}"
                ),
            ],
            proof_dir / "yosys.log",
        )
    ]
    if steps[-1]["status"] == "pass":
        steps.append(
            run(
                [
                    "yosys-smtbmc",
                    "-s",
                    "z3",
                    "-t",
                    str(depth),
                    "--dump-vcd",
                    str(vcd_path),
                    str(smt_path),
                ],
                proof_dir / "smtbmc.log",
            )
        )
    return {
        "name": name,
        "top": top,
        "status": "pass" if all(step["status"] == "pass" for step in steps) else "fail",
        "steps": steps,
    }


def main():
    parser = argparse.ArgumentParser(description="Run JTAG debug protocol formal checks")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "formal" / "jtag")
    parser.add_argument("--depth", type=int, default=32)
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    missing = [path for path in RTL_FILES if not (REPO_ROOT / path).is_file()]
    if missing:
        raise SystemExit("missing generated JTAG RTL: " + ", ".join(missing))

    slang_so = resolve_slang_so()
    proofs = [
        run_proof(name, top, probe_top, args.depth, out_dir, slang_so)
        for name, top, probe_top in PROOFS
    ]
    status = "pass" if all(proof["status"] == "pass" for proof in proofs) else "fail"
    report = {
        "depth": args.depth,
        "engine": "yosys-smtbmc",
        "solver": "z3",
        "status": status,
        "proofs": proofs,
    }
    report_path = out_dir / "jtag.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"jtag-formal {status}: {report_path.relative_to(REPO_ROOT)}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
