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
            "satisfied_runs": {
                "smoke": {"run_id": 11, "url": "https://github.com/owner/repo/actions/runs/11"},
                "full": {"run_id": 22, "url": "https://github.com/owner/repo/actions/runs/22"},
            },
        },
    )
    monkeypatch.setattr(open_gap_audit, "REPO_ROOT", tmp_path)

    gap = open_gap_audit.audit_ci()
    assert gap["status"] == "closed"
    assert gap["closed"] is True
    assert gap["missing"] == []


def test_audit_ci_remains_partial_when_remote_evidence_is_missing(tmp_path, monkeypatch):
    make_ci_repo(
        tmp_path,
        {
            "status": "missing",
            "missing": ["No successful remote full run with uploaded artifact evidence was found."],
            "satisfied_runs": {
                "smoke": {"run_id": 11, "url": "https://github.com/owner/repo/actions/runs/11"},
                "full": None,
            },
        },
    )
    monkeypatch.setattr(open_gap_audit, "REPO_ROOT", tmp_path)

    gap = open_gap_audit.audit_ci()
    assert gap["status"] == "partial"
    assert gap["closed"] is False
    assert gap["missing"] == ["No successful remote full run with uploaded artifact evidence was found."]
