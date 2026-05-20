# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import open_gap_audit  # noqa: E402


WORKFLOW = """
name: DitDah32 Verification
permissions:
  contents: read
  actions: read
jobs:
  smoke: {}
  full: {}
  signoff: {}
  spike-matrix: {}
  ci-evidence: {}
"""


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_ci_repo(tmp_path, ci_report):
    workflow_path = tmp_path / ".github" / "workflows" / "verification.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(WORKFLOW, encoding="utf-8")
    write_json(
        tmp_path / "result" / "verification" / "tool_availability.json",
        {
            "capabilities": {
                "github_cli": True,
                "local_github_actions_runner": False,
            }
        },
    )
    write_json(tmp_path / "result" / "verification" / "ci_remote_evidence.json", ci_report)


def test_audit_ci_closes_when_remote_evidence_passes(tmp_path, monkeypatch):
    make_ci_repo(
        tmp_path,
        {
            "status": "pass",
            "expected_head_sha": "abc123",
            "required_profiles": ["smoke"],
            "satisfied_runs": {
                "smoke": {"run_id": 11, "url": "https://github.com/owner/repo/actions/runs/11", "head_sha": "abc123"},
            },
        },
    )
    monkeypatch.setattr(open_gap_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(open_gap_audit, "current_git_head", lambda: "abc123")

    gap = open_gap_audit.audit_ci()
    assert gap["status"] == "closed"
    assert gap["closed"] is True
    assert gap["missing"] == []


def test_audit_ci_remains_partial_when_remote_evidence_is_missing(tmp_path, monkeypatch):
    make_ci_repo(
        tmp_path,
        {
            "status": "missing",
            "missing": ["No successful remote smoke run with uploaded artifact evidence was found."],
            "required_profiles": ["smoke"],
            "satisfied_runs": {
                "smoke": None,
            },
        },
    )
    monkeypatch.setattr(open_gap_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(open_gap_audit, "current_git_head", lambda: "abc123")

    gap = open_gap_audit.audit_ci()
    assert gap["status"] == "partial"
    assert gap["closed"] is False
    assert gap["missing"] == ["No successful remote smoke run with uploaded artifact evidence was found."]


def test_audit_ci_rejects_remote_evidence_from_stale_head(tmp_path, monkeypatch):
    make_ci_repo(
        tmp_path,
        {
            "status": "pass",
            "expected_head_sha": "old456",
            "required_profiles": ["smoke"],
            "satisfied_runs": {
                "smoke": {"run_id": 11, "url": "https://github.com/owner/repo/actions/runs/11", "head_sha": "old456"},
            },
        },
    )
    monkeypatch.setattr(open_gap_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(open_gap_audit, "current_git_head", lambda: "abc123")

    gap = open_gap_audit.audit_ci()
    assert gap["status"] == "partial"
    assert gap["closed"] is False
    assert "Remote CI evidence was not collected for the current git HEAD." in gap["missing"]
    assert "Remote smoke evidence does not match the current git HEAD." in gap["missing"]
