#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import re
import shutil
import time
from pathlib import Path

from ci_remote_evidence import REPO_ROOT, infer_head_sha, infer_repo, repository_probe, run_json, run_text


def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def list_runs(repo, workflow, limit):
    returncode, payload, error = run_json(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow,
            "--limit",
            str(limit),
            "--json",
            "databaseId,displayTitle,conclusion,status,event,headSha,headBranch,url,createdAt,updatedAt,workflowName",
        ]
    )
    if returncode != 0 or payload is None:
        return [], error
    return payload, ""


def run_view(repo, run_id):
    returncode, payload, error = run_json(
        [
            "gh",
            "run",
            "view",
            str(run_id),
            "--repo",
            repo,
            "--json",
            "databaseId,conclusion,status,headSha,headBranch,url,createdAt,updatedAt,workflowName,jobs",
        ]
    )
    if returncode != 0 or payload is None:
        return None, error
    return payload, ""


def normalize_profile_name(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def job_matches_profile(job, profile):
    return normalize_profile_name(job.get("name")) == normalize_profile_name(profile)


def find_profile_job(jobs, profile):
    for job in jobs or []:
        if job_matches_profile(job, profile):
            return job
    return None


def find_new_run(repo, workflow, known_ids, expected_head_sha, profile, timeout_seconds, poll_seconds, require_profile_job=False):
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    ignored = {}
    while time.monotonic() < deadline:
        runs, error = list_runs(repo, workflow, 20)
        if error:
            last_error = error
        for run in runs:
            run_id = run.get("databaseId")
            if run_id in known_ids or run_id in ignored or run.get("event") != "workflow_dispatch":
                continue
            if run.get("headSha") != expected_head_sha:
                ignored[run_id] = f"run {run_id} headSha {run.get('headSha')!r} did not match expected HEAD {expected_head_sha!r}"
                continue
            if require_profile_job:
                view, view_error = run_view(repo, run_id)
                if view_error:
                    last_error = view_error
                if view is None:
                    continue
                profile_job = find_profile_job(view.get("jobs", []), profile)
                if profile_job is None:
                    if view.get("status") == "completed":
                        ignored[run_id] = f"run {run_id} did not contain a job for profile {profile!r}"
                    continue
                run["initial_view"] = view
                run["initial_profile_job"] = profile_job
                return run, ""
        time.sleep(poll_seconds)
    ignored_text = "; ".join(ignored.values())
    return None, last_error or ignored_text or "Timed out waiting for the dispatched workflow run to appear."


def wait_for_run(repo, run_id, timeout_seconds, poll_seconds):
    deadline = time.monotonic() + timeout_seconds
    last_view = None
    last_error = ""
    while time.monotonic() < deadline:
        view, error = run_view(repo, run_id)
        if error:
            last_error = error
        if view is not None:
            last_view = view
            if view.get("status") == "completed":
                return view, ""
        time.sleep(poll_seconds)
    return last_view, last_error or "Timed out waiting for the workflow run to complete."


def dispatch_profile(repo, workflow, ref, profile, expected_head_sha, wait, appear_timeout, run_timeout, poll_seconds):
    before_runs, before_error = list_runs(repo, workflow, 50)
    before_ids = {run.get("databaseId") for run in before_runs}

    command = [
        "gh",
        "workflow",
        "run",
        workflow,
        "--repo",
        repo,
        "-f",
        f"profile={profile}",
    ]
    if ref:
        command.extend(["--ref", ref])

    returncode, stdout, stderr = run_text(command)
    step = {
        "profile": profile,
        "dispatch_command": command,
        "dispatch_returncode": returncode,
        "dispatch_stdout": stdout,
        "dispatch_stderr": stderr,
        "status": "fail",
    }
    if before_error:
        step["pre_dispatch_list_error"] = before_error
    if returncode != 0:
        step["reason"] = stderr or stdout or "gh workflow run failed."
        return step

    run, appear_error = find_new_run(
        repo,
        workflow,
        before_ids,
        expected_head_sha,
        profile,
        appear_timeout,
        poll_seconds,
        require_profile_job=wait,
    )
    if run is None:
        step["reason"] = appear_error
        return step

    step["run"] = run
    step["run_id"] = run.get("databaseId")
    step["run_url"] = run.get("url")
    if not wait:
        step["status"] = "dispatched"
        return step

    view, wait_error = wait_for_run(repo, step["run_id"], run_timeout, poll_seconds)
    step["final_run"] = view
    if view is None:
        step["reason"] = wait_error
        return step
    if view.get("headSha") != expected_head_sha:
        step["reason"] = f"completed workflow run headSha {view.get('headSha')!r} does not match expected HEAD {expected_head_sha!r}"
        return step
    profile_job = find_profile_job(view.get("jobs", []), profile)
    step["profile_job"] = profile_job
    if profile_job is None:
        step["reason"] = f"completed workflow run does not contain a job for profile {profile!r}"
        return step
    if profile_job.get("conclusion") != "success":
        step["reason"] = f"profile job {profile_job.get('name')!r} completed with conclusion {profile_job.get('conclusion')!r}"
        return step
    if view.get("conclusion") == "success":
        step["status"] = "pass"
    else:
        step["status"] = "fail"
        step["reason"] = f"workflow run completed with conclusion {view.get('conclusion')!r}"
    return step


def main():
    parser = argparse.ArgumentParser(description="Dispatch DitDah32 remote GitHub Actions profiles")
    parser.add_argument("--repo", help="GitHub repository as owner/name. Defaults to GITHUB_REPOSITORY or git origin.")
    parser.add_argument("--workflow", default="verification.yml")
    parser.add_argument("--ref", help="Branch or tag containing the workflow file. Defaults to the repository default branch.")
    parser.add_argument("--head-sha", help="Expected commit SHA for dispatched runs. Defaults to GITHUB_SHA or local git HEAD.")
    parser.add_argument("--profiles", nargs="+", default=["smoke", "ci-evidence"])
    parser.add_argument("--wait", action="store_true", help="Wait for each dispatched run to finish.")
    parser.add_argument("--appear-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--run-timeout-seconds", type=float, default=7200.0)
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    repo, repo_source = infer_repo(args.repo)
    expected_head_sha, expected_head_source = infer_head_sha(args.head_sha)
    report = {
        "status": "fail",
        "repository": repo,
        "repository_source": repo_source,
        "expected_head_sha": expected_head_sha,
        "expected_head_source": expected_head_source,
        "workflow": args.workflow,
        "ref": args.ref,
        "profiles": args.profiles,
        "wait": args.wait,
        "steps": [],
        "missing": [],
        "duration_seconds": 0.0,
    }

    if shutil.which("gh") is None:
        report["missing"].append("GitHub CLI is not available.")
    if repo is None:
        report["missing"].append("No GitHub repository could be inferred from arguments, GITHUB_REPOSITORY, or git origin.")
    if expected_head_sha is None:
        report["missing"].append("No expected commit SHA could be inferred from --head-sha, GITHUB_SHA, or local git HEAD.")

    if not report["missing"]:
        report["repository_probe"] = repository_probe(repo)
        if report["repository_probe"].get("status") != "pass":
            report["missing"].append(
                f"GitHub repository {repo} is not accessible: {report['repository_probe'].get('error')}"
            )

    if not report["missing"]:
        for profile in args.profiles:
            step = dispatch_profile(
                repo,
                args.workflow,
                args.ref,
                profile,
                expected_head_sha,
                args.wait,
                args.appear_timeout_seconds,
                args.run_timeout_seconds,
                args.poll_seconds,
            )
            report["steps"].append(step)
            if step["status"] == "fail":
                report["missing"].append(f"Remote profile {profile} did not complete successfully: {step.get('reason')}")
                break

    accepted_statuses = {"pass"} if args.wait else {"pass", "dispatched"}
    all_steps_ok = bool(report["steps"]) and all(step.get("status") in accepted_statuses for step in report["steps"])
    report["status"] = "pass" if not report["missing"] and all_steps_ok else "fail"
    report["duration_seconds"] = round(time.monotonic() - started, 3)

    report_path = out_dir / "ci_remote_dispatch.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"ci remote dispatch {report['status']}: {rel(report_path)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
