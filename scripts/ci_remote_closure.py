#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import os
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


def infer_head_sha(cli_head_sha):
    if cli_head_sha:
        return cli_head_sha, "argument"
    env_sha = os.environ.get("GITHUB_SHA")
    if env_sha:
        return env_sha, "GITHUB_SHA"
    returncode, stdout, _stderr = run_text(["git", "rev-parse", "HEAD"])
    if returncode == 0 and stdout:
        return stdout, "git_head"
    return None, "missing"


def read_report(path):
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return {}
    with full_path.open("r", encoding="utf-8") as json_file:
        return json.load(json_file)


def read_status(path):
    return read_report(path).get("status")


def dedupe(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def collect_missing():
    missing = []
    for label, path in (
        ("remote_ci", "result/verification/ci_remote_evidence.json"),
        ("open_gap_audit", "result/verification/open_gaps.json"),
        ("completion_audit", "result/verification/completion_audit.json"),
    ):
        report = read_report(path)
        for entry in report.get("missing", []):
            missing.append(f"{label}: {entry}")
    return dedupe(missing)


def remote_repository():
    ci_remote = read_report("result/verification/ci_remote_evidence.json")
    return ci_remote.get("repository")


def authorized_next_commands(repo):
    closure_args = f'--repo {repo}' if repo else "--repo owner/repo"
    return [
        'make ci-remote-publish CI_REMOTE_PUBLISH_ARGS="--confirm-create --confirm-push"',
        f'make ci-remote-closure CI_REMOTE_CLOSURE_ARGS="{closure_args}"',
    ]


def needs_publish_authorization(missing):
    return any("repository" in entry and ("not accessible" in entry or "Could not resolve" in entry) for entry in missing)


def write_fail_report(out_dir, started, steps, reason, expected_head_sha=None, expected_head_source=None):
    status = "fail"
    missing = collect_missing()
    repo = remote_repository()
    report = {
        "status": status,
        "duration_seconds": round(time.monotonic() - started, 3),
        "expected_head_sha": expected_head_sha,
        "expected_head_source": expected_head_source,
        "steps": steps,
        "reason": reason,
        "missing": missing,
        "next_authorized_commands": authorized_next_commands(repo) if needs_publish_authorization(missing) else [],
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
    parser.add_argument("--head-sha", help="Expected commit SHA for remote dispatch and evidence closure. Defaults to GITHUB_SHA or local git HEAD.")
    parser.add_argument("--skip-dispatch", action="store_true", help="Only collect evidence and audit existing remote runs.")
    parser.add_argument("--dispatch-timeout-seconds", type=float, default=7200.0)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    steps = []
    expected_head_sha, expected_head_source = infer_head_sha(args.head_sha)
    if expected_head_sha is None:
        return write_fail_report(out_dir, started, steps, "Expected commit SHA inference failed.", expected_head_sha, expected_head_source)

    repo_args = ["--repo", args.repo] if args.repo else []
    workflow_args = ["--workflow", args.workflow]
    local_workflow_args = ["--workflow", args.workflow] if (REPO_ROOT / args.workflow).exists() else []
    ref_args = ["--ref", args.ref] if args.ref else []
    head_args = ["--head-sha", expected_head_sha]

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
        return write_fail_report(out_dir, started, steps, "Remote CI preflight failed.", expected_head_sha, expected_head_source)

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
                    *head_args,
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
            return write_fail_report(out_dir, started, steps, "Remote workflow dispatch or wait failed.", expected_head_sha, expected_head_source)

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
                *head_args,
            ],
            out_dir,
        )
    )
    steps.append(run_step("open_gap_audit", ["python3", "scripts/open_gap_audit.py", "--out-dir", "result/verification"], out_dir))
    steps.append(run_step("completion_audit", ["python3", "scripts/completion_audit.py", "--out-dir", "result/verification"], out_dir))

    status = "pass" if all(step["status"] == "pass" for step in steps) else "fail"
    missing = collect_missing()
    repo = remote_repository()
    report = {
        "status": status,
        "duration_seconds": round(time.monotonic() - started, 3),
        "expected_head_sha": expected_head_sha,
        "expected_head_source": expected_head_source,
        "steps": steps,
        "reason": None if status == "pass" else "Remote CI closure incomplete.",
        "missing": [] if status == "pass" else missing,
        "next_authorized_commands": authorized_next_commands(repo) if status != "pass" and needs_publish_authorization(missing) else [],
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
