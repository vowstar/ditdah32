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


def run_step(name, command, out_dir):
    start = time.monotonic()
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{name}.log"
    with log_path.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return {
        "name": name,
        "command": command,
        "duration_seconds": round(time.monotonic() - start, 3),
        "returncode": completed.returncode,
        "status": "pass" if completed.returncode == 0 else "fail",
        "log": rel(log_path),
    }


def read_status(path):
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return None
    with full_path.open("r", encoding="utf-8") as json_file:
        return json.load(json_file).get("status")


def write_fail_report(out_dir, started, steps, reason):
    status = "fail"
    report = {
        "status": status,
        "duration_seconds": round(time.monotonic() - started, 3),
        "steps": steps,
        "reason": reason,
        "ci_remote_preflight_status": read_status("result/verification/ci_remote_preflight.json"),
        "ci_remote_status": read_status("result/verification/ci_remote_evidence.json"),
        "open_gap_status": read_status("result/verification/open_gaps.json"),
        "completion_status": read_status("result/verification/completion_audit.json"),
    }
    report_path = out_dir / "ci_remote_closure.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"ci remote closure {status}: {rel(report_path)}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Run the remote CI closure sequence for DitDah32")
    parser.add_argument("--repo", help="GitHub repository as owner/name. Defaults to GITHUB_REPOSITORY or git origin in child tools.")
    parser.add_argument("--workflow", default="verification.yml")
    parser.add_argument("--ref", help="Branch or tag containing the workflow file.")
    parser.add_argument("--skip-dispatch", action="store_true", help="Only collect evidence and audit existing remote runs.")
    parser.add_argument("--dispatch-timeout-seconds", type=float, default=7200.0)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    steps = []
    repo_args = ["--repo", args.repo] if args.repo else []
    workflow_args = ["--workflow", args.workflow]
    local_workflow_args = ["--workflow", args.workflow] if (REPO_ROOT / args.workflow).exists() else []
    ref_args = ["--ref", args.ref] if args.ref else []

    steps.append(
        run_step(
            "ci_remote_preflight",
            [
                "python3",
                "scripts/ci_remote_preflight.py",
                "--out-dir",
                "result/verification",
                *repo_args,
                *local_workflow_args,
            ],
            out_dir,
        )
    )
    if steps[-1]["status"] != "pass":
        return write_fail_report(out_dir, started, steps, "Remote CI preflight failed.")

    if not args.skip_dispatch:
        steps.append(
            run_step(
                "ci_remote_dispatch",
                [
                    "python3",
                    "scripts/ci_remote_dispatch.py",
                    "--out-dir",
                    "result/verification",
                    *repo_args,
                    *workflow_args,
                    *ref_args,
                    "--profiles",
                    "smoke",
                    "full",
                    "ci-evidence",
                    "--wait",
                    "--run-timeout-seconds",
                    str(args.dispatch_timeout_seconds),
                ],
                out_dir,
            )
        )
        if steps[-1]["status"] != "pass":
            return write_fail_report(out_dir, started, steps, "Remote workflow dispatch or wait failed.")

    steps.append(
        run_step(
            "ci_remote_evidence",
            [
                "python3",
                "scripts/ci_remote_evidence.py",
                "--out-dir",
                "result/verification",
                *repo_args,
                *workflow_args,
            ],
            out_dir,
        )
    )
    steps.append(run_step("open_gap_audit", ["python3", "scripts/open_gap_audit.py", "--out-dir", "result/verification"], out_dir))
    steps.append(run_step("completion_audit", ["python3", "scripts/completion_audit.py", "--out-dir", "result/verification"], out_dir))

    status = "pass" if all(step["status"] == "pass" for step in steps) else "fail"
    report = {
        "status": status,
        "duration_seconds": round(time.monotonic() - started, 3),
        "steps": steps,
        "ci_remote_preflight_status": read_status("result/verification/ci_remote_preflight.json"),
        "ci_remote_status": read_status("result/verification/ci_remote_evidence.json"),
        "open_gap_status": read_status("result/verification/open_gaps.json"),
        "completion_status": read_status("result/verification/completion_audit.json"),
    }
    report_path = out_dir / "ci_remote_closure.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"ci remote closure {status}: {rel(report_path)}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
