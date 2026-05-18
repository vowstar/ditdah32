#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Orchestrate the DitDah32 compliance signature gate.

Steps:
  1. Compile every .S source under test/compliance/tests/ via
     scripts/build_compliance.py.
  2. Invoke the cocotb regression with a TESTCASE filter that runs only the
     compliance_* tests in test/test_ditdah32/test_ditdah32.py. Each cocotb
     test loads the matching binary into the AXI RAM, waits for the halt
     magic, and asserts the signature words against the pre-computed
     manifest entries.
  3. Aggregate per-test outcomes into result/compliance/compliance.json plus
     a human-readable Markdown report.

Scope: this is the DitDah32 compliance signature gate. It is patterned after
the riscv-arch-test signature comparison convention (compile, run, dump
signature, compare against reference) but uses locally-developed tests that
strictly respect the RV32E x0-x15 register set. The upstream
riscv-arch-test framework macros (rvtest_setup.h, failure_code.h) reference
x16-x31 unconditionally and are therefore unusable on a strict RV32E hart
without a framework fork. Expected signatures are hand-computed from the
ISA semantics and stored in test/compliance/manifest.json; a future tier
should integrate a reference ISS (Spike or Sail) to derive them
automatically once DitDah32's reset vector can be lifted to 0x80000000 or
Spike accepts non-DRAM base addresses.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPLIANCE_ROOT = REPO_ROOT / "test" / "compliance"
COCOTB_TEST_DIR = REPO_ROOT / "test" / "test_ditdah32"
MANIFEST = COMPLIANCE_ROOT / "manifest.json"


def run(cmd, cwd=None, log=None):
    if log is not None:
        with log.open("w", encoding="utf-8") as handle:
            return subprocess.run(cmd, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT, check=False)
    return subprocess.run(cmd, cwd=cwd, check=False)


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def parse_results_xml(path: Path):
    import xml.etree.ElementTree as ET

    if not path.is_file():
        return {}
    outcomes = {}
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        name = case.get("name", "")
        if not name.startswith("compliance_"):
            continue
        failure = case.find("failure")
        outcomes[name] = {
            "status": "fail" if failure is not None else "pass",
            "duration_s": float(case.get("time", "0") or 0.0),
            "message": failure.get("error_msg") if failure is not None else None,
        }
    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="result/compliance")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse the existing compliance build artefacts instead of recompiling.",
    )
    args = parser.parse_args()

    out_dir = (REPO_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()
    steps = []

    if not args.skip_build:
        build_log = logs_dir / "build.log"
        build_result = run(
            [sys.executable, str(REPO_ROOT / "scripts" / "build_compliance.py")],
            cwd=REPO_ROOT,
            log=build_log,
        )
        steps.append({
            "name": "build",
            "status": "pass" if build_result.returncode == 0 else "fail",
            "returncode": build_result.returncode,
            "log": str(build_log.relative_to(REPO_ROOT)),
        })
        if build_result.returncode != 0:
            report = {"status": "fail", "steps": steps, "tests": []}
            (out_dir / "compliance.json").write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print("compliance build failed", file=sys.stderr)
            return 1

    # Run only the compliance_* cocotb tests. cocotb's COCOTB_TESTCASE_FILTER
    # accepts a regex pattern.
    env = os.environ.copy()
    env["COCOTB_TESTCASE_FILTER"] = "compliance_.*"
    env["COCOTB_RESULTS_FILE"] = "results_compliance.xml"

    cocotb_log = logs_dir / "cocotb.log"
    cocotb_result = run(
        ["make"],
        cwd=COCOTB_TEST_DIR,
        log=cocotb_log,
    )
    # cocotb's TESTCASE filter via env var:
    # Some Makefile.inc variants honour TESTCASE rather than the filter env.
    # If the run above ran all tests, force a second filtered run using the
    # standard cocotb TESTCASE filter.
    results_xml = COCOTB_TEST_DIR / "results_compliance.xml"
    if not results_xml.is_file():
        results_xml = COCOTB_TEST_DIR / "results.xml"

    outcomes = parse_results_xml(results_xml)
    steps.append({
        "name": "cocotb_compliance_run",
        "status": "pass" if cocotb_result.returncode == 0 else "fail",
        "returncode": cocotb_result.returncode,
        "log": str(cocotb_log.relative_to(REPO_ROOT)),
        "results_xml": str(results_xml.relative_to(REPO_ROOT)) if results_xml.is_file() else None,
    })

    test_records = []
    overall_pass = cocotb_result.returncode == 0
    for entry in manifest["tests"]:
        name = entry["name"]
        outcome = outcomes.get(f"compliance_{name}")
        if outcome is None:
            test_records.append({
                "name": name,
                "status": "missing",
                "message": "cocotb did not run this compliance test (missing testcase or filter mismatch)",
                "expected_signature": entry["signature_words"],
            })
            overall_pass = False
            continue
        test_records.append({
            "name": name,
            "status": outcome["status"],
            "duration_s": outcome["duration_s"],
            "message": outcome["message"],
            "expected_signature": entry["signature_words"],
            "description": entry.get("description", ""),
        })
        if outcome["status"] != "pass":
            overall_pass = False

    report = {
        "status": "pass" if overall_pass else "fail",
        "scope": (
            "DitDah32 compliance signature gate: signature-vs-manifest comparison "
            "on locally-developed RV32E-strict tests. Upstream riscv-arch-test "
            "act4 framework requires x16-x31 in setup macros and is not directly "
            "consumable; this gate uses the same compile/run/signature/diff "
            "pattern with tests that respect the RV32E register set. Future "
            "work: replace the hand-computed manifest with a reference ISS "
            "(Spike or Sail) signature dump."
        ),
        "steps": steps,
        "tests": test_records,
    }

    json_path = out_dir / "compliance.json"
    md_path = out_dir / "compliance.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# DitDah32 Compliance Signature Gate",
        "",
        f"Status: **{report['status']}**",
        "",
        report["scope"],
        "",
        "## Tests",
        "",
        "| Name | Status | Description |",
        "| --- | --- | --- |",
    ]
    for record in test_records:
        lines.append(f"| {record['name']} | {record['status']} | {record.get('description', '')} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"compliance {report['status']}: {json_path.relative_to(REPO_ROOT)}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
