#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
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


def run_text(cmd):
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def run_json(cmd):
    returncode, stdout, stderr = run_text(cmd)
    if returncode != 0:
        return returncode, None, stderr or stdout
    try:
        return returncode, json.loads(stdout), ""
    except json.JSONDecodeError as exc:
        return returncode, None, f"failed to parse JSON: {exc}"


def parse_github_repo(remote):
    remote = remote.removesuffix(".git")
    if remote.startswith("git@github.com:"):
        return remote.removeprefix("git@github.com:")
    if remote.startswith("https://github.com/"):
        return remote.removeprefix("https://github.com/")
    return None


def expected_origin(repo):
    return f"git@github.com:{repo}.git"


def git_text(cmd):
    return run_text(["git", *cmd])


def git_state(cli_repo):
    state = {
        "inside_work_tree": False,
        "git_root": None,
        "branch": None,
        "head": None,
        "status_porcelain": None,
        "origin_remote": None,
        "origin_repository": None,
        "target_repository": cli_repo,
        "target_repository_source": "argument" if cli_repo else None,
        "missing": [],
    }

    returncode, stdout, stderr = git_text(["rev-parse", "--is-inside-work-tree"])
    if returncode != 0 or stdout != "true":
        state["missing"].append("The workspace is not a git repository.")
        state["git_error"] = stderr or stdout
        return state
    state["inside_work_tree"] = True

    returncode, stdout, stderr = git_text(["rev-parse", "--show-toplevel"])
    if returncode == 0:
        state["git_root"] = stdout
        if Path(stdout).resolve() != REPO_ROOT.resolve():
            state["missing"].append(f"Git top-level path is {stdout}, not {REPO_ROOT}.")
    else:
        state["missing"].append(f"Could not read git top-level path: {stderr or stdout}")

    returncode, stdout, stderr = git_text(["branch", "--show-current"])
    if returncode == 0 and stdout:
        state["branch"] = stdout
    else:
        state["missing"].append("Detached HEAD or unnamed branch is not supported for remote publication.")

    returncode, stdout, stderr = git_text(["rev-parse", "HEAD"])
    if returncode == 0:
        state["head"] = stdout
    else:
        state["missing"].append(f"Could not read local HEAD: {stderr or stdout}")

    returncode, stdout, stderr = git_text(["status", "--porcelain"])
    if returncode == 0:
        state["status_porcelain"] = stdout
        if stdout:
            state["missing"].append("The git workspace has uncommitted changes.")
    else:
        state["missing"].append(f"Could not read git status: {stderr or stdout}")

    returncode, stdout, _stderr = git_text(["remote", "get-url", "origin"])
    if returncode == 0:
        state["origin_remote"] = stdout
        state["origin_repository"] = parse_github_repo(stdout)
        if cli_repo is None and state["origin_repository"]:
            state["target_repository"] = state["origin_repository"]
            state["target_repository_source"] = "git_remote"
    elif cli_repo is None:
        state["missing"].append("No git origin remote exists and no --repo argument was provided.")

    if state["target_repository"] is None:
        state["missing"].append("No target GitHub repository could be inferred.")

    return state


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


def remote_branch(repo, branch):
    returncode, payload, error = run_json(
        [
            "gh",
            "api",
            f"repos/{repo}/git/ref/heads/{branch}",
        ]
    )
    if returncode != 0 or payload is None:
        return {
            "status": "missing",
            "error": error,
        }
    return {
        "status": "pass",
        "sha": (payload.get("object") or {}).get("sha"),
        "object_type": (payload.get("object") or {}).get("type"),
    }


def run_step(name, command):
    started = time.monotonic()
    returncode, stdout, stderr = run_text(command)
    return {
        "name": name,
        "command": command,
        "returncode": returncode,
        "status": "pass" if returncode == 0 else "fail",
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def ensure_origin_step(repo, current_origin):
    target = expected_origin(repo)
    if current_origin is None:
        return run_step("add_origin", ["git", "remote", "add", "origin", target])
    if current_origin != target:
        return run_step("set_origin", ["git", "remote", "set-url", "origin", target])
    return {
        "name": "origin_already_configured",
        "command": [],
        "returncode": 0,
        "status": "pass",
        "stdout": "",
        "stderr": "",
        "duration_seconds": 0.0,
    }


def build_report(args):
    started = time.monotonic()
    report = {
        "status": "blocked",
        "duration_seconds": 0.0,
        "repository": None,
        "visibility": args.visibility,
        "git": None,
        "repository_probe": None,
        "remote_branch": None,
        "steps": [],
        "missing": [],
    }

    if shutil.which("gh") is None:
        report["missing"].append("GitHub CLI is not available.")

    git = git_state(args.repo)
    report["git"] = git
    report["repository"] = git.get("target_repository")
    report["missing"].extend(git.get("missing", []))

    repo = report["repository"]
    if repo is None or report["missing"]:
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        return report

    repo_probe = repository_probe(repo)
    report["repository_probe"] = repo_probe
    if repo_probe.get("status") != "pass":
        if args.confirm_create:
            create_step = run_step("create_repository", ["gh", "repo", "create", repo, f"--{args.visibility}"])
            report["steps"].append(create_step)
            if create_step["status"] != "pass":
                report["missing"].append(f"Failed to create GitHub repository {repo}: {create_step['stderr'] or create_step['stdout']}")
                report["duration_seconds"] = round(time.monotonic() - started, 3)
                return report
            repo_probe = repository_probe(repo)
            report["repository_probe"] = repo_probe
            if repo_probe.get("status") != "pass":
                report["missing"].append(f"GitHub repository {repo} is still not accessible after creation.")
                report["duration_seconds"] = round(time.monotonic() - started, 3)
                return report
        else:
            report["missing"].append(
                f"GitHub repository {repo} is not accessible. Rerun with --confirm-create only after publication is authorized."
            )
            report["duration_seconds"] = round(time.monotonic() - started, 3)
            return report

    origin_expected = expected_origin(repo)
    origin_current = git.get("origin_remote")
    if origin_current != origin_expected:
        if args.confirm_push:
            origin_step = ensure_origin_step(repo, origin_current)
            report["steps"].append(origin_step)
            if origin_step["status"] != "pass":
                report["missing"].append(f"Failed to configure git origin: {origin_step['stderr'] or origin_step['stdout']}")
                report["duration_seconds"] = round(time.monotonic() - started, 3)
                return report
        else:
            report["missing"].append(
                f"Git origin is not configured as {origin_expected}. Rerun with --confirm-push only after publication is authorized."
            )
            report["duration_seconds"] = round(time.monotonic() - started, 3)
            return report

    branch = git.get("branch")
    branch_report = remote_branch(repo, branch)
    report["remote_branch"] = branch_report
    remote_sha = branch_report.get("sha")
    if remote_sha != git.get("head"):
        if args.confirm_push:
            push_step = run_step("push_branch", ["git", "push", "-u", "origin", branch])
            report["steps"].append(push_step)
            if push_step["status"] != "pass":
                report["missing"].append(f"Failed to push branch {branch}: {push_step['stderr'] or push_step['stdout']}")
                report["duration_seconds"] = round(time.monotonic() - started, 3)
                return report
            branch_report = remote_branch(repo, branch)
            report["remote_branch"] = branch_report
            remote_sha = branch_report.get("sha")
        else:
            report["missing"].append(
                f"Remote branch {branch} is missing or not at local HEAD. Rerun with --confirm-push only after publication is authorized."
            )
            report["duration_seconds"] = round(time.monotonic() - started, 3)
            return report

    if remote_sha != git.get("head"):
        report["missing"].append(f"Remote branch {branch} does not match local HEAD after publish attempt.")

    report["status"] = "pass" if not report["missing"] else "blocked"
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    return report


def write_markdown(path, report):
    lines = [
        "# DitDah32 Remote Publish Audit",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Repository: `{report.get('repository')}`",
        f"Local branch: `{(report.get('git') or {}).get('branch')}`",
        f"Local HEAD: `{(report.get('git') or {}).get('head')}`",
        "",
        "| Step | Status |",
        "| --- | --- |",
    ]
    for step in report["steps"]:
        lines.append(f"| `{step['name']}` | `{step['status']}` |")
    if not report["steps"]:
        lines.append("| None | None |")
    lines.extend(["", "## Remaining Blockers", ""])
    if report["missing"]:
        for entry in report["missing"]:
            lines.append(f"- {entry}")
    else:
        lines.append("None")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit and optionally publish DitDah32 to the configured GitHub repository")
    parser.add_argument("--repo", help="Target GitHub repository as owner/name. Defaults to git origin.")
    parser.add_argument("--visibility", choices=("private", "public"), default="private")
    parser.add_argument("--confirm-create", action="store_true", help="Actually create the GitHub repository if it is missing.")
    parser.add_argument("--confirm-push", action="store_true", help="Actually configure origin and push the current branch if needed.")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args)

    json_path = out_dir / "ci_remote_publish.json"
    md_path = out_dir / "ci_remote_publish.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_path, report)

    print(f"ci remote publish {report['status']}: {rel(json_path)}")
    print(f"markdown: {rel(md_path)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
