#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as json_file:
        return json.load(json_file)


def rel(path):
    return str(path.relative_to(REPO_ROOT))


def artifact(path, exists=None):
    path = REPO_ROOT / path
    return {
        "path": rel(path),
        "exists": path.exists() if exists is None else bool(exists),
    }


def names_from_report(report, required_status=None):
    names = []
    for item in (report or {}).get("artifacts", []):
        if required_status is None or item.get("status") == required_status:
            names.append(item.get("name"))
    return sorted(name for name in names if name is not None)


def count_status(report, status):
    return sum(1 for item in (report or {}).get("artifacts", []) if item.get("status") == status)


def command_probe(command):
    path = shutil.which(command)
    result = {
        "command": command,
        "path": path,
        "available": path is not None,
        "version_command": None,
        "version_output": None,
    }
    if path is None:
        return result

    for args in ([command, "--version"], [command, "-V"]):
        completed = subprocess.run(
            args,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        output = completed.stdout.strip()
        if completed.returncode == 0 and output:
            result["version_command"] = args
            result["version_output"] = output.splitlines()[0]
            break
    return result


def report_pass(report):
    return report is not None and report.get("status") == "pass"


def complete_report(report):
    return (
        report_pass(report)
        and report.get("coverage_status") == "complete_for_selected_artifacts"
        and (report.get("summary") or {}).get("fail", 1) == 0
        and (report.get("summary") or {}).get("skip", 1) == 0
        and (report.get("summary") or {}).get("pass", 0) > 0
    )


def build_report(out_dir):
    rtl_matrix = load_json(REPO_ROOT / "result" / "rtl_trace" / "isa_artifacts" / "matrix.json")
    sail_matrix = load_json(REPO_ROOT / "result" / "iss" / "sail_matrix" / "sail_smoke.json")
    spike_strict = load_json(REPO_ROOT / "result" / "iss" / "spike_rv32e_strict" / "spike_rv32e_strict.json")
    spike_highmem_rtl = load_json(REPO_ROOT / "result" / "rtl_trace" / "spike_highmem_artifacts" / "matrix.json")
    spike_highmem = load_json(REPO_ROOT / "result" / "iss" / "spike_highmem" / "spike_smoke.json")
    sail_highmem_rtl = load_json(REPO_ROOT / "result" / "rtl_trace" / "sail_highmem_artifacts" / "matrix.json")
    sail_highmem = load_json(REPO_ROOT / "result" / "iss" / "sail_highmem" / "sail_smoke.json")

    rtl_names = names_from_report(rtl_matrix, "pass")
    sail_names = names_from_report(sail_matrix, "pass")
    spike_highmem_names = names_from_report(spike_highmem, "pass")
    spike_highmem_rtl_names = names_from_report(spike_highmem_rtl, "pass")
    sail_highmem_names = names_from_report(sail_highmem, "pass")
    sail_highmem_rtl_names = names_from_report(sail_highmem_rtl, "pass")

    checks = [
        {
            "name": "rtl_generated_isa_matrix",
            "status": "pass" if report_pass(rtl_matrix) else "fail",
            "evidence": artifact("result/rtl_trace/isa_artifacts/matrix.json", report_pass(rtl_matrix)),
        },
        {
            "name": "sail_full_generated_legal_matrix",
            "status": "pass" if complete_report(sail_matrix) else "fail",
            "evidence": artifact("result/iss/sail_matrix/sail_smoke.json", complete_report(sail_matrix)),
            "summary": (sail_matrix or {}).get("summary"),
            "coverage_status": (sail_matrix or {}).get("coverage_status"),
        },
        {
            "name": "generated_artifact_name_match",
            "status": "pass" if rtl_names == sail_names and bool(rtl_names) else "fail",
            "rtl_artifacts": rtl_names,
            "sail_artifacts": sail_names,
        },
        {
            "name": "spike_strict_rv32e_negative_matrix",
            "status": "pass"
            if (
                report_pass(spike_strict)
                and (spike_strict.get("summary") or {}).get("fail", 1) == 0
                and (spike_strict.get("summary") or {}).get("pass", 0) > 0
            )
            else "fail",
            "evidence": artifact(
                "result/iss/spike_rv32e_strict/spike_rv32e_strict.json",
                report_pass(spike_strict),
            ),
            "summary": (spike_strict or {}).get("summary"),
        },
        {
            "name": "spike_highmem_external_supplement",
            "status": "pass"
            if complete_report(spike_highmem)
            and report_pass(spike_highmem_rtl)
            and spike_highmem_names == spike_highmem_rtl_names
            and bool(spike_highmem_names)
            else "fail",
            "external_summary": (spike_highmem or {}).get("summary"),
            "rtl_artifacts": spike_highmem_rtl_names,
            "spike_artifacts": spike_highmem_names,
        },
        {
            "name": "sail_highmem_external_supplement",
            "status": "pass"
            if complete_report(sail_highmem)
            and report_pass(sail_highmem_rtl)
            and sail_highmem_names == sail_highmem_rtl_names
            and bool(sail_highmem_names)
            else "fail",
            "external_summary": (sail_highmem or {}).get("summary"),
            "rtl_artifacts": sail_highmem_rtl_names,
            "sail_artifacts": sail_highmem_names,
        },
    ]

    failed_checks = [item for item in checks if item["status"] != "pass"]
    status = "fail" if failed_checks else "pass"
    report = {
        "status": status,
        "closure_status": "closed_composite" if status == "pass" else "open",
        "scope": "external_iss_composite_rv32ec_closure",
        "equivalence_class": "architectural_trace_equivalent_for_generated_legal_programs_and_strict_prefix_negative_for_rv32e_illegal_registers",
        "started_unix": int(time.time()),
        "tools": {
            "spike": command_probe("spike"),
            "sail_riscv_sim": command_probe("sail_riscv_sim"),
        },
        "checks": checks,
        "summary": {
            "checks_pass": sum(1 for item in checks if item["status"] == "pass"),
            "checks_fail": len(failed_checks),
            "generated_legal_artifacts": len(sail_names),
            "strict_negative_artifacts": count_status(spike_strict, "pass"),
            "spike_highmem_artifacts": len(spike_highmem_names),
            "sail_highmem_artifacts": len(sail_highmem_names),
        },
        "limitations": [
            "This is a composite external-ISS closure report, not a claim that one strict RV32E ISS covers every legal and illegal case.",
            "Sail is used for legal RV32E/RV32EC generated programs with an RV32IC-compatible packaged model.",
            "Spike is used as the strict RV32E negative supplement for x16-x31 register-scope checks.",
            "This report does not replace RISCV-DV or the external riscv-formal property suite.",
        ],
        "evidence": [
            artifact("result/rtl_trace/isa_artifacts/matrix.json", report_pass(rtl_matrix)),
            artifact("result/iss/sail_matrix/sail_smoke.json", complete_report(sail_matrix)),
            artifact("result/iss/spike_rv32e_strict/spike_rv32e_strict.json", report_pass(spike_strict)),
            artifact("result/rtl_trace/spike_highmem_artifacts/matrix.json", report_pass(spike_highmem_rtl)),
            artifact("result/iss/spike_highmem/spike_smoke.json", complete_report(spike_highmem)),
            artifact("result/rtl_trace/sail_highmem_artifacts/matrix.json", report_pass(sail_highmem_rtl)),
            artifact("result/iss/sail_highmem/sail_smoke.json", complete_report(sail_highmem)),
        ],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "external_iss_full.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_path, report


def main():
    parser = argparse.ArgumentParser(description="Aggregate DitDah32 external ISS closure evidence")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "iss" / "external_iss_full")
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir

    report_path, report = build_report(out_dir)
    print(f"[REPORT] {report_path}")
    print(f"external ISS composite status: {report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
