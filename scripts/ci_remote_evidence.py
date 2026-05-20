#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def run_json(cmd, cwd=REPO_ROOT):
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode, None, completed.stderr.strip() or completed.stdout.strip()
    try:
        return completed.returncode, json.loads(completed.stdout), ""
    except json.JSONDecodeError as exc:
        return completed.returncode, None, f"failed to parse JSON: {exc}"


def run_text(cmd, cwd=REPO_ROOT):
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def infer_repo(cli_repo):
    if cli_repo:
        return cli_repo, "argument"
    env_repo = os.environ.get("GITHUB_REPOSITORY")
    if env_repo:
        return env_repo, "GITHUB_REPOSITORY"

    returncode, stdout, _stderr = run_text(["git", "remote", "get-url", "origin"])
    if returncode != 0:
        return None, "missing"

    remote = stdout.removesuffix(".git")
    if remote.startswith("git@github.com:"):
        return remote.removeprefix("git@github.com:"), "git_remote"
    if remote.startswith("https://github.com/"):
        return remote.removeprefix("https://github.com/"), "git_remote"
    return None, "unsupported_remote"


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


def artifact_names(repo, run_id):
    returncode, payload, error = run_json(
        [
            "gh",
            "api",
            f"repos/{repo}/actions/runs/{run_id}/artifacts",
        ]
    )
    if returncode != 0 or payload is None:
        return [], error
    return [artifact.get("name") for artifact in payload.get("artifacts", []) if artifact.get("name")], ""


def repository_probe(repo):
    returncode, payload, error = run_json(
        [
            "gh",
            "repo",
            "view",
            repo,
            "--json",
            "nameWithOwner,url,defaultBranchRef,visibility",
        ]
    )
    if returncode != 0 or payload is None:
        return {
            "status": "missing",
            "error": error,
        }
    return {
        "status": "pass",
        "name_with_owner": payload.get("nameWithOwner"),
        "url": payload.get("url"),
        "default_branch": ((payload.get("defaultBranchRef") or {}).get("name")),
        "visibility": payload.get("visibility"),
    }


def job_summary(repo, run_id):
    returncode, payload, error = run_json(
        [
            "gh",
            "run",
            "view",
            str(run_id),
            "--repo",
            repo,
            "--json",
            "jobs",
        ]
    )
    if returncode != 0 or payload is None:
        return [], error
    return [
        {
            "name": job.get("name"),
            "status": job.get("status"),
            "conclusion": job.get("conclusion"),
        }
        for job in payload.get("jobs", [])
    ], ""


def normalize_profile_name(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def job_matches_profile(job, profile):
    return normalize_profile_name(job.get("name")) == normalize_profile_name(profile)


def find_profile_job(jobs, profile):
    for job in jobs or []:
        if job_matches_profile(job, profile):
            return job
    return None


def classify_run(run, jobs, artifacts):
    artifact_text = " ".join(artifacts).lower()
    title = str(run.get("displayTitle", "")).lower()
    event = str(run.get("event", "")).lower()

    classifications = []
    for profile in ("smoke", "full", "signoff"):
        job = find_profile_job(jobs, profile)
        has_artifact = profile in artifact_text
        title_matches = profile in title
        if job or has_artifact or title_matches or (profile == "smoke" and event in {"push", "pull_request"}):
            classifications.append(
                {
                    "profile": profile,
                    "job_conclusion": (job or {}).get("conclusion"),
                    "job_status": (job or {}).get("status"),
                    "artifact_present": has_artifact,
                    "title_matches": title_matches,
                }
            )
    return classifications


def main():
    parser = argparse.ArgumentParser(description="Collect remote GitHub Actions evidence for DitDah32 verification")
    parser.add_argument("--repo", help="GitHub repository as owner/name. Defaults to GITHUB_REPOSITORY or git origin.")
    parser.add_argument("--workflow", default="verification.yml")
    parser.add_argument("--head-sha", help="Expected commit SHA for closing remote evidence. Defaults to GITHUB_SHA or local git HEAD.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    repo, repo_source = infer_repo(args.repo)
    expected_head_sha, expected_head_source = infer_head_sha(args.head_sha)
    report = {
        "status": "missing",
        "repository": repo,
        "repository_source": repo_source,
        "expected_head_sha": expected_head_sha,
        "expected_head_source": expected_head_source,
        "workflow": args.workflow,
        "required_profiles": ["smoke"],
        "optional_profiles": ["full", "signoff"],
        "repository_probe": None,
        "runs": [],
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
        returncode, runs, error = run_json(
            [
                "gh",
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                args.workflow,
                "--limit",
                str(args.limit),
                "--json",
                "databaseId,displayTitle,conclusion,status,event,headSha,headBranch,url,createdAt,updatedAt,workflowName",
            ]
        )
        if returncode != 0 or runs is None:
            report["missing"].append(f"Failed to list workflow runs: {error}")
        else:
            for run in runs:
                run_id = run.get("databaseId")
                jobs, jobs_error = job_summary(repo, run_id)
                artifacts, artifacts_error = artifact_names(repo, run_id)
                entry = {
                    "run_id": run_id,
                    "url": run.get("url"),
                    "event": run.get("event"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "head_sha": run.get("headSha"),
                    "head_branch": run.get("headBranch"),
                    "created_at": run.get("createdAt"),
                    "updated_at": run.get("updatedAt"),
                    "jobs": jobs,
                    "artifacts": artifacts,
                    "classifications": classify_run(run, jobs, artifacts),
                }
                if jobs_error:
                    entry["jobs_error"] = jobs_error
                if artifacts_error:
                    entry["artifacts_error"] = artifacts_error
                report["runs"].append(entry)

    satisfied = {}
    for profile in report["required_profiles"]:
        satisfied[profile] = None
        for run in report["runs"]:
            if run.get("conclusion") != "success" or run.get("status") != "completed":
                continue
            if run.get("head_sha") != expected_head_sha:
                continue
            for item in run.get("classifications", []):
                if (
                    item.get("profile") == profile
                    and item.get("artifact_present")
                    and item.get("job_conclusion") == "success"
                ):
                    satisfied[profile] = run
                    break
            if satisfied[profile] is not None:
                break
        if satisfied[profile] is None:
            report["missing"].append(
                f"No successful remote {profile} run for expected HEAD {expected_head_sha} with uploaded artifact evidence was found."
            )

    report["satisfied_runs"] = {
        profile: None if run is None else {
            "run_id": run.get("run_id"),
            "url": run.get("url"),
            "head_sha": run.get("head_sha"),
            "created_at": run.get("created_at"),
        }
        for profile, run in satisfied.items()
    }
    report["status"] = "pass" if not report["missing"] else "missing"
    report["duration_seconds"] = round(time.monotonic() - started, 3)

    report_path = out_dir / "ci_remote_evidence.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"ci remote evidence {report['status']}: {rel(report_path)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
