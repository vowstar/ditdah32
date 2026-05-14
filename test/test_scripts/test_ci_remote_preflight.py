# SPDX-License-Identifier: MIT

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_remote_preflight  # noqa: E402


def report(status="pass", missing=None):
    return {
        "status": status,
        "missing": missing or [],
    }


def test_ci_remote_preflight_passes_when_components_pass(tmp_path, monkeypatch):
    workflow = tmp_path / "verification.yml"
    workflow.write_text("name: test\n", encoding="utf-8")
    monkeypatch.setattr(ci_remote_preflight, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_remote_preflight.ci_github_auth_audit, "build_report", lambda scopes: report())
    monkeypatch.setattr(ci_remote_preflight.ci_publish_readiness, "build_report", lambda repo: report())
    monkeypatch.setattr(ci_remote_preflight.ci_action_ref_audit, "build_report", lambda workflow_path: report())

    result = ci_remote_preflight.build_report("owner/repo", workflow, {"repo"})
    assert result["status"] == "pass"
    assert result["missing"] == []
    assert [item["name"] for item in result["components"]] == [
        "github_auth",
        "publish_readiness",
        "action_refs",
    ]
    assert all(item["passed"] for item in result["components"])


def test_ci_remote_preflight_prefixes_component_missing_items(tmp_path, monkeypatch):
    workflow = tmp_path / "verification.yml"
    workflow.write_text("name: test\n", encoding="utf-8")
    monkeypatch.setattr(ci_remote_preflight, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_remote_preflight.ci_github_auth_audit, "build_report", lambda scopes: report())
    monkeypatch.setattr(
        ci_remote_preflight.ci_publish_readiness,
        "build_report",
        lambda repo: report("blocked", ["The workspace is not a git repository."]),
    )
    monkeypatch.setattr(ci_remote_preflight.ci_action_ref_audit, "build_report", lambda workflow_path: report())

    result = ci_remote_preflight.build_report("owner/repo", workflow, {"repo"})
    assert result["status"] == "fail"
    assert result["missing"] == ["publish_readiness: The workspace is not a git repository."]
    readiness = next(item for item in result["components"] if item["name"] == "publish_readiness")
    assert not readiness["passed"]


def test_ci_remote_preflight_writes_reports(tmp_path, monkeypatch):
    workflow = tmp_path / "verification.yml"
    workflow.write_text("name: test\n", encoding="utf-8")
    out_dir = tmp_path / "result" / "verification"
    monkeypatch.setattr(ci_remote_preflight, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_remote_preflight.ci_github_auth_audit, "build_report", lambda scopes: report())
    monkeypatch.setattr(ci_remote_preflight.ci_publish_readiness, "build_report", lambda repo: report())
    monkeypatch.setattr(ci_remote_preflight.ci_action_ref_audit, "build_report", lambda workflow_path: report())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_remote_preflight.py",
            "--repo",
            "owner/repo",
            "--workflow",
            str(workflow),
            "--out-dir",
            str(out_dir),
        ],
    )

    assert ci_remote_preflight.main() == 0
    result = json.loads((out_dir / "ci_remote_preflight.json").read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert (out_dir / "ci_remote_preflight.md").exists()
