#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_json(path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as json_file:
        return json.load(json_file)


def artifact(path, exists=None):
    full_path = REPO_ROOT / path
    return {
        "path": rel(full_path),
        "exists": full_path.exists() if exists is None else bool(exists),
    }


def status_from_report(path):
    report = load_json(REPO_ROOT / path)
    return None if report is None else report.get("status")


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


def current_git_state():
    state = {
        "available": False,
        "head": None,
        "branch": None,
        "dirty": None,
        "status_porcelain": None,
        "error": None,
    }
    returncode, stdout, stderr = run_text(["git", "rev-parse", "--is-inside-work-tree"])
    if returncode != 0 or stdout != "true":
        state["error"] = stderr or stdout or "not inside a git work tree"
        return state

    state["available"] = True
    for key, command in (
        ("head", ["git", "rev-parse", "HEAD"]),
        ("branch", ["git", "branch", "--show-current"]),
    ):
        returncode, stdout, stderr = run_text(command)
        if returncode == 0:
            state[key] = stdout
        else:
            state["error"] = stderr or stdout

    returncode, stdout, stderr = run_text(["git", "status", "--porcelain"])
    if returncode == 0:
        state["status_porcelain"] = stdout
        state["dirty"] = bool(stdout)
    else:
        state["error"] = stderr or stdout
    return state


def checklist_item(name, requirement, evidence, passed, missing=None):
    return {
        "name": name,
        "requirement": requirement,
        "evidence": evidence,
        "passed": bool(passed),
        "missing": missing or [],
    }


def build_report():
    signoff = load_json(REPO_ROOT / "result" / "verification" / "signoff.json")
    open_gaps = load_json(REPO_ROOT / "result" / "verification" / "open_gaps.json")
    ci_remote = load_json(REPO_ROOT / "result" / "verification" / "ci_remote_evidence.json")
    ci_remote_preflight = load_json(REPO_ROOT / "result" / "verification" / "ci_remote_preflight.json")
    git_state = current_git_state()
    started = time.time()

    open_gap_summary = (open_gaps or {}).get("summary", {})
    gap_statuses = {
        gap.get("id"): {
            "status": gap.get("status"),
            "closed": gap.get("closed"),
            "missing": gap.get("missing", []),
        }
        for gap in (open_gaps or {}).get("gaps", [])
    }

    signoff_pass = signoff is not None and signoff.get("status") == "pass"
    signoff_git = (signoff or {}).get("git") or {}
    signoff_missing = []
    if not signoff_pass:
        signoff_missing.append("Local signoff report is missing or not passing.")
    if not git_state.get("available"):
        signoff_missing.append("Current git state is not available for signoff freshness checking.")
    if signoff_pass and not signoff_git:
        signoff_missing.append("Local signoff report does not record git metadata.")
    if signoff_git and signoff_git.get("head") != git_state.get("head"):
        signoff_missing.append("Local signoff report was not generated from the current git HEAD.")
    if signoff_git and signoff_git.get("dirty") is not False:
        signoff_missing.append("Local signoff report was generated from a dirty git workspace.")
    if git_state.get("dirty") is not False:
        signoff_missing.append("Current git workspace has uncommitted changes after local signoff.")
    signoff_fresh = signoff_pass and not signoff_missing
    preflight_pass = ci_remote_preflight is not None and ci_remote_preflight.get("status") == "pass"
    ci_pass = ci_remote is not None and ci_remote.get("status") == "pass"
    all_gaps_closed = open_gap_summary.get("not_closed") == 0

    checklist = [
        checklist_item(
            "local_signoff",
            "The strongest local signoff profile passes on the current workspace state.",
            [
                artifact("result/verification/signoff.json", signoff_pass),
                {"signoff_status": (signoff or {}).get("status")},
                {"signoff_duration_seconds": (signoff or {}).get("duration_seconds")},
                {"signoff_git": signoff_git},
                {"current_git": git_state},
            ],
            signoff_fresh,
            signoff_missing,
        ),
        checklist_item(
            "external_iss",
            "External ISS differential testing is closed by composite Spike/Sail evidence.",
            [
                artifact("result/iss/external_iss_full/external_iss_full.json"),
                {"gap_status": gap_statuses.get("external_iss")},
            ],
            gap_statuses.get("external_iss", {}).get("closed") is True,
            gap_statuses.get("external_iss", {}).get("missing", []),
        ),
        checklist_item(
            "riscv_dv",
            "RISCV-DV fixed-seed generated program flow passes legality scan, compile, reference trace, and RTL trace comparison.",
            [
                artifact("result/riscv_dv/riscv_dv.json", status_from_report("result/riscv_dv/riscv_dv.json") == "pass"),
                {"gap_status": gap_statuses.get("riscv_dv")},
            ],
            gap_statuses.get("riscv_dv", {}).get("closed") is True,
            gap_statuses.get("riscv_dv", {}).get("missing", []),
        ),
        checklist_item(
            "rvfi_riscv_formal",
            "External riscv-formal consistency subset passes and disabled property groups are documented.",
            [
                artifact("result/formal/rvfi/rvfi.json", status_from_report("result/formal/rvfi/rvfi.json") == "pass"),
                {"gap_status": gap_statuses.get("rvfi_riscv_formal")},
            ],
            gap_statuses.get("rvfi_riscv_formal", {}).get("closed") is True,
            gap_statuses.get("rvfi_riscv_formal", {}).get("missing", []),
        ),
        checklist_item(
            "bus_scope",
            "Full AXI4 is closed as out of scope and the supported AXI-Lite subset is documented and tested.",
            [
                artifact("result/axi/axi_lite_backpressure.json"),
                {"gap_status": gap_statuses.get("full_axi4")},
            ],
            gap_statuses.get("full_axi4", {}).get("closed") is True,
            gap_statuses.get("full_axi4", {}).get("missing", []),
        ),
        checklist_item(
            "benchmark_scope",
            "CoreMark and Dhrystone are closed as non-certified local RTL estimates.",
            [
                artifact("result/bench/benchmark_scores.json"),
                {"gap_status": gap_statuses.get("certified_benchmarks")},
            ],
            gap_statuses.get("certified_benchmarks", {}).get("closed") is True,
            gap_statuses.get("certified_benchmarks", {}).get("missing", []),
        ),
        checklist_item(
            "remote_preflight",
            "Local remote-CI preflight passes for GitHub auth, publish readiness, and workflow action references.",
            [
                artifact("result/verification/ci_remote_preflight.json", ci_remote_preflight is not None),
                artifact("result/verification/ci_remote_preflight.md", (REPO_ROOT / "result" / "verification" / "ci_remote_preflight.md").exists()),
                {"ci_remote_preflight_status": (ci_remote_preflight or {}).get("status")},
                {"components": [
                    {
                        "name": item.get("name"),
                        "status": item.get("status"),
                        "passed": item.get("passed"),
                        "missing": item.get("missing", []),
                    }
                    for item in (ci_remote_preflight or {}).get("components", [])
                ]},
            ],
            preflight_pass,
            [] if preflight_pass else ((ci_remote_preflight or {}).get("missing", []) or ["Remote CI preflight report is missing or not passing."]),
        ),
        checklist_item(
            "remote_ci",
            "Remote GitHub Actions smoke and full runs pass with uploaded artifact evidence.",
            [
                artifact("result/verification/ci_remote_evidence.json", ci_remote is not None),
                {"ci_remote_status": (ci_remote or {}).get("status")},
                {"ci_remote_satisfied_runs": (ci_remote or {}).get("satisfied_runs")},
                {"gap_status": gap_statuses.get("ci_regression")},
            ],
            ci_pass and gap_statuses.get("ci_regression", {}).get("closed") is True,
            (ci_remote or {}).get("missing", []) or gap_statuses.get("ci_regression", {}).get("missing", []),
        ),
        checklist_item(
            "open_gap_audit",
            "The open-gap audit reports zero open or partial gaps.",
            [
                artifact("result/verification/open_gaps.json", open_gaps is not None),
                artifact("result/verification/open_gaps.md", (REPO_ROOT / "result" / "verification" / "open_gaps.md").exists()),
                {"summary": open_gap_summary},
            ],
            all_gaps_closed,
            [] if all_gaps_closed else [f"Open or partial gaps remain: {open_gap_summary.get('not_closed')} / {open_gap_summary.get('total')}"],
        ),
    ]

    missing = []
    for item in checklist:
        missing.extend([f"{item['name']}: {entry}" for entry in item["missing"]])

    return {
        "objective": "Implement and sufficiently verify the RV32EC processor plan discussed in this thread.",
        "status": "complete" if all(item["passed"] for item in checklist) else "incomplete",
        "generated_unix": int(started),
        "checklist": checklist,
        "missing": missing,
    }


def write_markdown(path, report):
    lines = [
        "# DitDah32 Completion Audit",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Objective: {report['objective']}",
        "",
        "| Item | Passed | Missing |",
        "| --- | --- | --- |",
    ]
    for item in report["checklist"]:
        missing = "<br>".join(item["missing"]) if item["missing"] else "None"
        lines.append(f"| {item['name']} | `{str(item['passed']).lower()}` | {missing} |")
    lines.extend(["", "## Remaining Blockers", ""])
    if report["missing"]:
        for entry in report["missing"]:
            lines.append(f"- {entry}")
    else:
        lines.append("None")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Write DitDah32 active-goal completion audit")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report()

    json_path = out_dir / "completion_audit.json"
    md_path = out_dir / "completion_audit.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_path, report)

    print(f"completion audit {report['status']}: {rel(json_path)}")
    print(f"markdown: {rel(md_path)}")
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
