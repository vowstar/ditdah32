# SPDX-License-Identifier: MIT

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_publish_readiness  # noqa: E402


WORKFLOW_YAML = """\
name: DitDah32 Verification

on:
  push:
  pull_request:
  workflow_dispatch:
    inputs:
      profile:
        type: choice
        options:
          - smoke
          - full
          - signoff
          - spike-matrix
          - ci-evidence

permissions:
  contents: read
  actions: read

jobs:
  smoke:
    steps:
      - uses: actions/checkout@v6
      - run: nix develop --option sandbox false -c sh -c 'make verify-smoke && make audit-gaps'
      - uses: actions/upload-artifact@v6
        with:
          name: ditdah32-smoke-${{ github.run_id }}
          path: |
            result/verification/**
  full:
    steps:
      - uses: actions/checkout@v6
      - run: nix develop --option sandbox false -c sh -c 'make verify && make audit-gaps'
      - uses: actions/upload-artifact@v6
        with:
          name: ditdah32-full-${{ github.run_id }}
          path: |
            result/verification/**
            result/rtl_trace/**
            result/coverage/**
            result/formal/**
            result/iss/**
            result/isa/**
  signoff:
    steps:
      - run: nix develop --option sandbox false -c make verify-signoff
  spike-matrix:
    steps:
      - run: nix develop --option sandbox false -c make verify-spike-matrix
  ci-evidence:
    steps:
      - uses: actions/checkout@v6
      - run: nix develop --option sandbox false -c sh -c 'make audit-ci-remote && make audit-gaps'
      - uses: actions/upload-artifact@v6
        with:
          name: ditdah32-ci-evidence-${{ github.run_id }}
          path: |
            result/verification/**
"""


MAKEFILE_TEXT = """\
audit-ci-remote:
\tpython3 scripts/ci_remote_evidence.py --out-dir result/verification
ci-remote-dispatch:
\tpython3 scripts/ci_remote_dispatch.py --out-dir result/verification
ci-remote-closure:
\tpython3 scripts/ci_remote_closure.py --out-dir result/verification
audit-gaps:
\tpython3 scripts/open_gap_audit.py --out-dir result/verification
audit-completion:
\tpython3 scripts/completion_audit.py --out-dir result/verification
verify-smoke:
\tpython3 scripts/run_verification_campaign.py --profile smoke
verify:
\tpython3 scripts/run_verification_campaign.py --profile full
"""


GITIGNORE_TEXT = """\
/result/
/test/**/sim_build/
__pycache__/
.pytest_cache/
/result-*
"""

THIRD_PARTY_TEXT = """\
# Third-Party Components

- cocotb-bus
- cocotbext-axi
- CoreMark
- Dhrystone
- non-certified
"""


REMOTE_CI_CONTRACT_FILES = {
    "scripts/ci_remote_evidence.py": """\
parser.add_argument("--head-sha")
expected_head_sha = "head"
expected_head_source = "argument"
def find_profile_job(jobs, profile):
    return None
job_conclusion = "success"
artifact_present = True
""",
    "scripts/ci_remote_dispatch.py": """\
parser.add_argument("--head-sha")
expected_head_sha = "head"
def find_profile_job(jobs, profile):
    return None
require_profile_job = True
initial_profile_job = {}
""",
    "scripts/ci_remote_closure.py": """\
parser.add_argument("--head-sha")
expected_head_sha = "head"
expected_head_source = "argument"
""",
    "scripts/completion_audit.py": """\
expected_head_sha = "head"
message = "Remote CI evidence was not collected for the current git HEAD"
message = "Remote {profile} evidence does not match the current git HEAD"
""",
    "scripts/open_gap_audit.py": """\
expected_head_sha = "head"
message = "Remote CI evidence was not collected for the current git HEAD"
message = "Remote {profile} evidence does not match the current git HEAD"
""",
    "doc/ci_remote_closure.md": """\
# Remote CI Closure

The report records expected_head_sha.
Each required profile job must pass.
The expected commit must match the current local git HEAD.
""",
}


def populate_project(path, workflow_text=WORKFLOW_YAML):
    (path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (path / "doc").mkdir(parents=True, exist_ok=True)
    (path / "scripts").mkdir(parents=True, exist_ok=True)
    (path / "test" / "cocotb_bus").mkdir(parents=True, exist_ok=True)
    (path / "test" / "cocotbext" / "axi").mkdir(parents=True, exist_ok=True)
    (path / "bench" / "coremark" / "upstream").mkdir(parents=True, exist_ok=True)
    (path / "bench" / "dhrystone" / "upstream").mkdir(parents=True, exist_ok=True)
    (path / ".github" / "workflows" / "verification.yml").write_text(workflow_text, encoding="utf-8")
    (path / "Makefile").write_text(MAKEFILE_TEXT, encoding="utf-8")
    (path / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
    (path / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    (path / "doc" / "third_party.md").write_text(THIRD_PARTY_TEXT, encoding="utf-8")
    (path / "test" / "cocotb_bus" / "LICENSE").write_text("BSD-3-Clause\n", encoding="utf-8")
    (path / "test" / "cocotbext" / "axi" / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    (path / "bench" / "coremark" / "upstream" / "LICENSE.md").write_text("Apache License\n", encoding="utf-8")
    (path / "bench" / "dhrystone" / "upstream" / "README_C").write_text("Dhrystone\n", encoding="utf-8")
    (path / "bench" / "dhrystone" / "upstream" / "RATIONALE").write_text("Measurement Rules\n", encoding="utf-8")
    for rel_path, text in REMOTE_CI_CONTRACT_FILES.items():
        (path / rel_path).write_text(text, encoding="utf-8")


def fake_git_success(repo_root):
    def fake_run_text(cmd, cwd=repo_root):
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return 0, "true", ""
        if cmd == ["git", "rev-parse", "--show-toplevel"]:
            return 0, str(repo_root), ""
        if cmd == ["git", "status", "--porcelain"]:
            return 0, "", ""
        if cmd == ["git", "remote", "get-url", "origin"]:
            return 0, "https://github.com/owner/repo.git", ""
        raise AssertionError(f"unexpected command: {cmd}")

    return fake_run_text


def test_ci_publish_readiness_passes_for_ready_git_checkout(tmp_path, monkeypatch):
    populate_project(tmp_path)
    monkeypatch.setattr(ci_publish_readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_publish_readiness, "run_text", fake_git_success(tmp_path))

    report = ci_publish_readiness.build_report()
    assert report["status"] == "pass"
    assert report["missing"] == []
    git_item = next(item for item in report["checklist"] if item["name"] == "git_state")
    assert git_item["evidence"]["target_repository"] == "owner/repo"
    assert all(item["passed"] for item in report["checklist"])


def test_ci_publish_readiness_reports_non_git_workspace(tmp_path, monkeypatch):
    populate_project(tmp_path)

    def fake_run_text(cmd, cwd=tmp_path):
        assert cmd == ["git", "rev-parse", "--is-inside-work-tree"]
        return 128, "", "fatal: not a git repository"

    monkeypatch.setattr(ci_publish_readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_publish_readiness, "run_text", fake_run_text)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_publish_readiness.py",
            "--repo",
            "owner/repo",
            "--out-dir",
            str(tmp_path / "result" / "verification"),
        ],
    )

    assert ci_publish_readiness.main() == 1
    report = json.loads((tmp_path / "result" / "verification" / "ci_publish_readiness.json").read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert any("not a git repository" in item for item in report["missing"])
    assert all(item["passed"] for item in report["checklist"] if item["name"] != "git_state")


def test_ci_publish_readiness_catches_missing_full_artifact_path(tmp_path, monkeypatch):
    workflow = WORKFLOW_YAML.replace("            result/formal/**\n", "")
    populate_project(tmp_path, workflow_text=workflow)
    monkeypatch.setattr(ci_publish_readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_publish_readiness, "run_text", fake_git_success(tmp_path))

    report = ci_publish_readiness.build_report()
    assert report["status"] == "blocked"
    workflow_item = next(item for item in report["checklist"] if item["name"] == "github_workflow")
    assert not workflow_item["passed"]
    assert "Full artifact does not upload result/formal/**." in workflow_item["missing"]


def test_ci_publish_readiness_catches_missing_third_party_manifest(tmp_path, monkeypatch):
    populate_project(tmp_path)
    (tmp_path / "doc" / "third_party.md").unlink()
    monkeypatch.setattr(ci_publish_readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_publish_readiness, "run_text", fake_git_success(tmp_path))

    report = ci_publish_readiness.build_report()
    assert report["status"] == "blocked"
    notices_item = next(item for item in report["checklist"] if item["name"] == "third_party_notices")
    assert not notices_item["passed"]
    assert any("doc/third_party.md" in item for item in notices_item["missing"])


def test_ci_publish_readiness_catches_missing_remote_ci_contract(tmp_path, monkeypatch):
    populate_project(tmp_path)
    evidence_path = tmp_path / "scripts" / "ci_remote_evidence.py"
    evidence_path.write_text("def find_profile_job(jobs, profile):\n    return None\n", encoding="utf-8")
    monkeypatch.setattr(ci_publish_readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_publish_readiness, "run_text", fake_git_success(tmp_path))

    report = ci_publish_readiness.build_report()
    assert report["status"] == "blocked"
    contract_item = next(item for item in report["checklist"] if item["name"] == "remote_ci_contract")
    assert not contract_item["passed"]
    assert any("scripts/ci_remote_evidence.py" in item and "--head-sha" in item for item in contract_item["missing"])
    assert any("scripts/ci_remote_evidence.py" in item and "expected_head_sha" in item for item in contract_item["missing"])
