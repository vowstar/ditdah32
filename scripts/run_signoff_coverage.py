#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = REPO_ROOT / "test" / "test_ditdah32"


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


def parse_lcov(path):
    records = []
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SF:"):
            current = {"source": line[3:], "lines": {}, "branches": []}
        elif line.startswith("DA:") and current is not None:
            line_no, count = line[3:].split(",")[:2]
            current["lines"][int(line_no)] = int(count)
        elif line.startswith("BRDA:") and current is not None:
            parts = line[5:].split(",")
            taken = parts[3]
            current["branches"].append(0 if taken == "-" else int(taken))
        elif line == "end_of_record" and current is not None:
            records.append(current)
            current = None

    merged = {"line_total": 0, "line_hit": 0, "branch_total": 0, "branch_hit": 0}
    for record in records:
        if not record["source"].endswith("result/DitDah32.sv"):
            continue
        merged["line_total"] += len(record["lines"])
        merged["line_hit"] += sum(1 for count in record["lines"].values() if count > 0)
        merged["branch_total"] += len(record["branches"])
        merged["branch_hit"] += sum(1 for count in record["branches"] if count > 0)

    merged["line_percent"] = round(100.0 * merged["line_hit"] / merged["line_total"], 2) if merged["line_total"] else 0.0
    merged["branch_percent"] = (
        round(100.0 * merged["branch_hit"] / merged["branch_total"], 2)
        if merged["branch_total"]
        else 0.0
    )
    return merged


def main():
    parser = argparse.ArgumentParser(description="Run DitDah32 Verilator HDL coverage signoff gate")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "coverage" / "signoff")
    parser.add_argument("--line-threshold", type=float, default=80.0)
    parser.add_argument("--branch-threshold", type=float, default=55.0)
    parser.add_argument("--testcase", default=None)
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    logs_dir = out_dir / "logs"
    annotated_dir = out_dir / "annotated"
    logs_dir.mkdir(parents=True, exist_ok=True)
    annotated_dir.mkdir(parents=True, exist_ok=True)

    steps = []
    steps.append(run(["make", "-C", "test/test_ditdah32", "clean"], logs_dir / "clean.log"))
    cmd = [
        "make",
        "-C",
        "test/test_ditdah32",
        "SIM=verilator",
        "WAVES=0",
        "HDL_COVERAGE=1",
    ]
    if args.testcase:
        cmd.append(f"TESTCASE={args.testcase}")
    steps.append(run(cmd, logs_dir / "verilator_cocotb.log"))

    coverage_dat = TEST_DIR / "sim_build" / "coverage.dat"
    copied_dat = out_dir / "coverage.dat"
    info_path = out_dir / "coverage.info"
    if steps[-1]["status"] == "pass" and coverage_dat.exists():
        shutil.copy2(coverage_dat, copied_dat)
        steps.append(
            run(
                ["verilator_coverage", "--write-info", str(info_path), str(copied_dat)],
                logs_dir / "verilator_coverage_info.log",
            )
        )
        steps.append(
            run(
                ["verilator_coverage", "--annotate", str(annotated_dir), str(copied_dat)],
                logs_dir / "verilator_coverage_annotate.log",
            )
        )

    metrics = parse_lcov(info_path) if info_path.exists() else {
        "line_total": 0,
        "line_hit": 0,
        "line_percent": 0.0,
        "branch_total": 0,
        "branch_hit": 0,
        "branch_percent": 0.0,
    }
    gates = {
        "line_percent": {
            "actual": metrics["line_percent"],
            "threshold": args.line_threshold,
            "status": "pass" if metrics["line_percent"] >= args.line_threshold else "fail",
        },
        "branch_percent": {
            "actual": metrics["branch_percent"],
            "threshold": args.branch_threshold,
            "status": "pass" if metrics["branch_percent"] >= args.branch_threshold else "fail",
        },
    }
    status = "pass" if all(step["status"] == "pass" for step in steps) and all(gate["status"] == "pass" for gate in gates.values()) else "fail"
    report = {
        "status": status,
        "simulator": "verilator",
        "metrics": metrics,
        "gates": gates,
        "steps": steps,
    }
    report_path = out_dir / "signoff_coverage.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "signoff coverage "
        f"{status}: line {metrics['line_percent']}%, branch {metrics['branch_percent']}%, "
        f"report {report_path.relative_to(REPO_ROOT)}"
    )
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
