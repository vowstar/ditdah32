# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_action_ref_audit  # noqa: E402


WORKFLOW = """\
name: Test Workflow
on:
  workflow_dispatch:
jobs:
  smoke:
    steps:
      - uses: actions/checkout@v6
      - uses: cachix/install-nix-action@v31
"""


def write_workflow(path, text=WORKFLOW):
    workflow_path = path / ".github" / "workflows" / "verification.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(text, encoding="utf-8")
    return workflow_path


def test_ci_action_ref_audit_passes_when_action_tags_resolve(tmp_path, monkeypatch):
    workflow_path = write_workflow(tmp_path)

    def fake_run_json(cmd):
        assert cmd[:2] == ["gh", "api"]
        return 0, {"object": {"sha": "abc123", "type": "commit"}}, ""

    monkeypatch.setattr(ci_action_ref_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_action_ref_audit.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_action_ref_audit, "run_json", fake_run_json)

    report = ci_action_ref_audit.build_report(workflow_path)
    assert report["status"] == "pass"
    assert report["missing"] == []
    assert {item["uses"] for item in report["refs"]} == {
        "actions/checkout@v6",
        "cachix/install-nix-action@v31",
    }
    assert all(item["check"]["status"] == "pass" for item in report["refs"])


def test_ci_action_ref_audit_reports_missing_reference(tmp_path, monkeypatch):
    workflow_path = write_workflow(tmp_path)

    def fake_run_json(cmd):
        if cmd[2].endswith("/tags/v6"):
            return 1, None, "not found"
        if cmd[2].endswith("/heads/v6"):
            return 1, None, "not found"
        return 0, {"object": {"sha": "def456", "type": "tag"}}, ""

    monkeypatch.setattr(ci_action_ref_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_action_ref_audit.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_action_ref_audit, "run_json", fake_run_json)

    report = ci_action_ref_audit.build_report(workflow_path)
    assert report["status"] == "fail"
    assert any("actions/checkout@v6" in item for item in report["missing"])


def test_ci_action_ref_audit_writes_report_for_unsupported_reference(tmp_path, monkeypatch):
    workflow_path = write_workflow(
        tmp_path,
        """\
name: Test Workflow
on:
  workflow_dispatch:
jobs:
  smoke:
    steps:
      - uses: ./local-action
""",
    )
    out_dir = tmp_path / "result" / "verification"

    monkeypatch.setattr(ci_action_ref_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_action_ref_audit.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_action_ref_audit.py",
            "--workflow",
            str(workflow_path),
            "--out-dir",
            str(out_dir),
        ],
    )

    assert ci_action_ref_audit.main() == 1
    report = json.loads((out_dir / "ci_action_refs.json").read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert any("Unsupported action reference syntax" in item for item in report["missing"])
