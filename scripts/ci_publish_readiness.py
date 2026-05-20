#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import subprocess
import time
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


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


def parse_github_repo(remote):
    remote = remote.removesuffix(".git")
    if remote.startswith("git@github.com:"):
        return remote.removeprefix("git@github.com:")
    if remote.startswith("https://github.com/"):
        return remote.removeprefix("https://github.com/")
    return None


def check_item(name, passed, evidence=None, missing=None):
    return {
        "name": name,
        "passed": bool(passed),
        "evidence": evidence or {},
        "missing": missing or [],
    }


def workflow_trigger(workflow):
    return workflow.get("on", workflow.get(True, {}))


def find_upload_step(job):
    for step in job.get("steps", []):
        if "actions/upload-artifact" in str(step.get("uses", "")):
            return step
    return {}


def find_run_text(job):
    return "\n".join(str(step.get("run", "")) for step in job.get("steps", []))


def audit_git_state(cli_repo=None):
    returncode, inside, error = run_text(["git", "rev-parse", "--is-inside-work-tree"])
    if returncode != 0 or inside != "true":
        return check_item(
            "git_state",
            False,
            {"inside_work_tree": False, "target_repository": cli_repo},
            ["The workspace is not a git repository."],
        )

    root_returncode, root_stdout, root_error = run_text(["git", "rev-parse", "--show-toplevel"])
    status_returncode, status_stdout, status_error = run_text(["git", "status", "--porcelain"])
    remote_returncode, remote_stdout, remote_error = run_text(["git", "remote", "get-url", "origin"])

    repo = cli_repo
    repo_source = "argument" if cli_repo else None
    parsed_remote = None
    if remote_returncode == 0:
        parsed_remote = parse_github_repo(remote_stdout)
        if repo is None and parsed_remote is not None:
            repo = parsed_remote
            repo_source = "git_remote"

    missing = []
    if root_returncode != 0:
        missing.append(f"Could not read git top-level path: {root_error}")
    elif Path(root_stdout).resolve() != REPO_ROOT.resolve():
        missing.append(f"Git top-level path is {root_stdout}, not {REPO_ROOT}.")
    if status_returncode != 0:
        missing.append(f"Could not read git status: {status_error}")
    if remote_returncode != 0 and cli_repo is None:
        missing.append("No git origin remote exists and no --repo argument was provided.")
    if remote_returncode == 0 and parsed_remote is None and cli_repo is None:
        missing.append("Git origin is not a supported GitHub remote.")
    if repo is None:
        missing.append("No target GitHub repository could be inferred.")

    return check_item(
        "git_state",
        not missing,
        {
            "inside_work_tree": True,
            "git_root": root_stdout if root_returncode == 0 else None,
            "status_porcelain": status_stdout,
            "origin_remote": remote_stdout if remote_returncode == 0 else None,
            "origin_error": remote_error if remote_returncode != 0 else None,
            "target_repository": repo,
            "target_repository_source": repo_source,
            "workspace_dirty": bool(status_stdout),
        },
        missing,
    )


def audit_gitignore():
    path = REPO_ROOT / ".gitignore"
    if not path.exists():
        return check_item("gitignore", False, {"path": rel(path), "exists": False}, [".gitignore is missing."])

    lines = {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required = {
        "/result/",
        "/test/**/sim_build/",
        "__pycache__/",
        ".pytest_cache/",
        "/result-*",
    }
    missing = [f".gitignore does not contain required pattern: {pattern}" for pattern in sorted(required - lines)]
    return check_item(
        "gitignore",
        not missing,
        {"path": rel(path), "required_patterns": sorted(required), "present_patterns": sorted(lines)},
        missing,
    )


def audit_makefile():
    path = REPO_ROOT / "Makefile"
    if not path.exists():
        return check_item("makefile_targets", False, {"path": rel(path), "exists": False}, ["Makefile is missing."])

    text = path.read_text(encoding="utf-8")
    required_targets = {
        "audit-ci-remote",
        "ci-remote-dispatch",
        "ci-remote-closure",
        "audit-gaps",
        "audit-completion",
        "verify-ci-smoke",
        "verify-smoke",
        "verify",
    }
    required_commands = {
        "scripts/ci_remote_evidence.py",
        "scripts/ci_remote_dispatch.py",
        "scripts/ci_remote_closure.py",
        "scripts/open_gap_audit.py",
        "scripts/completion_audit.py",
        "scripts/run_verification_campaign.py --profile ci-smoke",
        "scripts/run_verification_campaign.py --profile smoke",
        "scripts/run_verification_campaign.py --profile full",
    }
    missing = []
    for target in sorted(required_targets):
        if f"{target}:" not in text:
            missing.append(f"Makefile target is missing: {target}")
    for command in sorted(required_commands):
        if command not in text:
            missing.append(f"Makefile command is missing: {command}")
    return check_item(
        "makefile_targets",
        not missing,
        {"path": rel(path), "required_targets": sorted(required_targets)},
        missing,
    )


def audit_third_party_notices():
    required_paths = {
        "root_project_license": REPO_ROOT / "LICENSE",
        "third_party_manifest": REPO_ROOT / "doc" / "third_party.md",
        "cocotb_bus_license": REPO_ROOT / "test" / "cocotb_bus" / "LICENSE",
        "cocotbext_axi_license": REPO_ROOT / "test" / "cocotbext" / "axi" / "LICENSE",
        "coremark_license": REPO_ROOT / "bench" / "coremark" / "upstream" / "LICENSE.md",
        "dhrystone_readme": REPO_ROOT / "bench" / "dhrystone" / "upstream" / "README_C",
        "dhrystone_rationale": REPO_ROOT / "bench" / "dhrystone" / "upstream" / "RATIONALE",
    }
    missing = [
        f"Required license or third-party notice file is missing: {rel(path)}"
        for path in required_paths.values()
        if not path.exists()
    ]

    manifest = required_paths["third_party_manifest"]
    manifest_text = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
    required_manifest_terms = [
        "cocotb-bus",
        "cocotbext-axi",
        "CoreMark",
        "Dhrystone",
        "non-certified",
    ]
    for term in required_manifest_terms:
        if term not in manifest_text:
            missing.append(f"Third-party manifest does not mention {term}.")

    return check_item(
        "third_party_notices",
        not missing,
        {
            "required_files": {name: rel(path) for name, path in required_paths.items()},
        },
        missing,
    )


def audit_workflow():
    path = REPO_ROOT / ".github" / "workflows" / "verification.yml"
    if not path.exists():
        return check_item("github_workflow", False, {"path": rel(path), "exists": False}, ["Verification workflow is missing."])

    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    trigger = workflow_trigger(workflow)
    jobs = workflow.get("jobs", {})
    permissions = workflow.get("permissions", {})
    dispatch = ((trigger or {}).get("workflow_dispatch") or {}).get("inputs", {}).get("profile", {})
    dispatch_options = set(dispatch.get("options", []))
    required_jobs = {"smoke", "full", "signoff", "spike-matrix", "ci-evidence"}
    required_dispatch_options = {"smoke", "full", "signoff", "spike-matrix", "ci-evidence"}
    missing = []

    for job in sorted(required_jobs - set(jobs)):
        missing.append(f"Workflow job is missing: {job}")
    for option in sorted(required_dispatch_options - dispatch_options):
        missing.append(f"workflow_dispatch profile option is missing: {option}")
    if permissions.get("contents") != "read":
        missing.append("Workflow permissions.contents must be read.")
    if permissions.get("actions") != "read":
        missing.append("Workflow permissions.actions must be read.")

    smoke_run = find_run_text(jobs.get("smoke", {}))
    full_run = find_run_text(jobs.get("full", {}))
    ci_run = find_run_text(jobs.get("ci-evidence", {}))
    if "make verify-ci-smoke" not in smoke_run:
        missing.append("Smoke workflow job does not run make verify-ci-smoke.")
    if "make verify" not in full_run:
        missing.append("Full workflow job does not run make verify.")
    if "make audit-ci-remote" not in ci_run:
        missing.append("CI evidence workflow job does not run make audit-ci-remote.")
    if "make audit-gaps" not in ci_run:
        missing.append("CI evidence workflow job does not run make audit-gaps.")

    smoke_upload = find_upload_step(jobs.get("smoke", {})).get("with", {})
    full_upload = find_upload_step(jobs.get("full", {})).get("with", {})
    ci_upload = find_upload_step(jobs.get("ci-evidence", {})).get("with", {})
    smoke_name = str(smoke_upload.get("name", ""))
    full_name = str(full_upload.get("name", ""))
    smoke_paths = str(smoke_upload.get("path", ""))
    full_paths = str(full_upload.get("path", ""))
    ci_paths = str(ci_upload.get("path", ""))
    if "smoke" not in smoke_name:
        missing.append("Smoke artifact name does not contain smoke.")
    if "full" not in full_name:
        missing.append("Full artifact name does not contain full.")
    if "result/verification/**" not in smoke_paths:
        missing.append("Smoke artifact does not upload result/verification/**.")
    for required_path in (
        "result/verification/**",
        "result/rtl_trace/**",
        "result/coverage/**",
        "result/formal/**",
        "result/iss/**",
        "result/isa/**",
    ):
        if required_path not in full_paths:
            missing.append(f"Full artifact does not upload {required_path}.")
    if "result/verification/**" not in ci_paths:
        missing.append("CI evidence artifact does not upload result/verification/**.")

    return check_item(
        "github_workflow",
        not missing,
        {
            "path": rel(path),
            "jobs": sorted(jobs),
            "dispatch_options": sorted(dispatch_options),
            "permissions": permissions,
            "smoke_artifact_name": smoke_name,
            "full_artifact_name": full_name,
        },
        missing,
    )


def audit_remote_ci_contract():
    required_terms = {
        "scripts/ci_remote_evidence.py": [
            "--head-sha",
            "expected_head_sha",
            "expected_head_source",
            "find_profile_job",
            "job_conclusion",
            "artifact_present",
        ],
        "scripts/ci_remote_dispatch.py": [
            "--head-sha",
            "expected_head_sha",
            "find_profile_job",
            "require_profile_job",
            "initial_profile_job",
        ],
        "scripts/ci_remote_closure.py": [
            "--head-sha",
            "expected_head_sha",
            "expected_head_source",
        ],
        "scripts/completion_audit.py": [
            "expected_head_sha",
            "Remote CI evidence was not collected for the current git HEAD",
            "Remote {profile} evidence does not match the current git HEAD",
        ],
        "scripts/open_gap_audit.py": [
            "expected_head_sha",
            "Remote CI evidence was not collected for the current git HEAD",
            "Remote {profile} evidence does not match the current git HEAD",
        ],
        "doc/ci_remote_closure.md": [
            "expected_head_sha",
            "profile job",
            "current local git HEAD",
        ],
    }

    missing = []
    evidence = {"required_terms": required_terms, "files": {}}
    for rel_path, terms in required_terms.items():
        path = REPO_ROOT / rel_path
        if not path.exists():
            missing.append(f"Remote CI contract file is missing: {rel_path}")
            evidence["files"][rel_path] = {"exists": False, "missing_terms": terms}
            continue

        text = path.read_text(encoding="utf-8")
        missing_terms = [term for term in terms if term not in text]
        if missing_terms:
            for term in missing_terms:
                missing.append(f"{rel_path} does not contain required remote CI contract term: {term}")
        evidence["files"][rel_path] = {"exists": True, "missing_terms": missing_terms}

    return check_item(
        "remote_ci_contract",
        not missing,
        evidence,
        missing,
    )


def build_report(repo=None):
    started = time.monotonic()
    checklist = [
        audit_git_state(repo),
        audit_gitignore(),
        audit_makefile(),
        audit_third_party_notices(),
        audit_workflow(),
        audit_remote_ci_contract(),
    ]
    missing = []
    for item in checklist:
        missing.extend([f"{item['name']}: {entry}" for entry in item["missing"]])
    return {
        "status": "pass" if not missing else "blocked",
        "duration_seconds": round(time.monotonic() - started, 3),
        "checklist": checklist,
        "missing": missing,
    }


def write_markdown(path, report):
    lines = [
        "# DitDah32 CI Publish Readiness Audit",
        "",
        f"Status: `{report['status']}`",
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
    parser = argparse.ArgumentParser(description="Audit local readiness for publishing DitDah32 remote CI evidence")
    parser.add_argument("--repo", help="Target GitHub repository as owner/name when no git origin is available.")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args.repo)

    json_path = out_dir / "ci_publish_readiness.json"
    md_path = out_dir / "ci_publish_readiness.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_path, report)

    print(f"ci publish readiness {report['status']}: {rel(json_path)}")
    print(f"markdown: {rel(md_path)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
