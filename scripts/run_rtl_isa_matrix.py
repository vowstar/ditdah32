#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = REPO_ROOT / "test" / "test_ditdah32"
TESTCASE = "isa_artifact_rtl_trace_matches_reference_model"


def discover_artifacts(isa_dir):
    artifacts = []
    for trace_path in sorted(isa_dir.glob("*.trace.jsonl")):
        name = trace_path.name.removesuffix(".trace.jsonl")
        hex_path = isa_dir / f"{name}.hex"
        if not hex_path.exists():
            raise SystemExit(f"missing hex file for ISA trace artifact: {trace_path}")
        artifacts.append(name)
    if not artifacts:
        raise SystemExit(f"no ISA trace artifacts found in {isa_dir}")
    return artifacts


def run_one(name, isa_dir, logs_dir):
    log_path = logs_dir / f"{name}.log"
    cmd = [
        "make",
        "-C",
        str(TEST_DIR.relative_to(REPO_ROOT)),
        f"TESTCASE={TESTCASE}",
        f"DITDAH32_ISA_ARTIFACT={name}",
        f"DITDAH32_ISA_DIR={isa_dir.relative_to(REPO_ROOT) if isa_dir.is_relative_to(REPO_ROOT) else isa_dir}",
    ]

    start = time.monotonic()
    print(f"[RUN] {name}: {' '.join(str(part) for part in cmd)}", flush=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            [str(part) for part in cmd],
            cwd=REPO_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )

    duration = time.monotonic() - start
    status = "pass" if completed.returncode == 0 else "fail"
    print(f"[{status.upper()}] {name}: {duration:.2f}s, log={log_path}", flush=True)
    return {
        "name": name,
        "command": [str(part) for part in cmd],
        "duration_seconds": round(duration, 3),
        "log": str(log_path.relative_to(REPO_ROOT)),
        "returncode": completed.returncode,
        "status": status,
    }


def main():
    parser = argparse.ArgumentParser(description="Run all generated RV32EC ISA artifacts on RTL")
    parser.add_argument("--isa-dir", type=Path, default=REPO_ROOT / "result" / "isa")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "rtl_trace" / "isa_artifacts")
    parser.add_argument("--keep-going", action="store_true", help="continue after an artifact fails")
    args = parser.parse_args()

    isa_dir = args.isa_dir
    out_dir = args.out_dir
    if not isa_dir.is_absolute():
        isa_dir = REPO_ROOT / isa_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir

    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "isa_dir": str(isa_dir.relative_to(REPO_ROOT) if isa_dir.is_relative_to(REPO_ROOT) else isa_dir),
        "out_dir": str(out_dir.relative_to(REPO_ROOT) if out_dir.is_relative_to(REPO_ROOT) else out_dir),
        "started_unix": int(time.time()),
        "testcase": TESTCASE,
        "artifacts": [],
    }

    failed = False
    start = time.monotonic()
    for name in discover_artifacts(isa_dir):
        result = run_one(name, isa_dir, logs_dir)
        report["artifacts"].append(result)
        failed = failed or result["status"] != "pass"
        if failed and not args.keep_going:
            break

    report["duration_seconds"] = round(time.monotonic() - start, 3)
    report["status"] = "fail" if failed else "pass"

    report_path = out_dir / "matrix.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[REPORT] {report_path}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
