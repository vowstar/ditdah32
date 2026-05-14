# SPDX-License-Identifier: MIT

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_github_auth_audit  # noqa: E402


AUTH_STATUS = """\
github.com
  ✓ Logged in to github.com account vowstar (/home/vowstar/.config/gh/hosts.yml)
  - Active account: true
  - Git operations protocol: ssh
  - Token: gho_************************************
  - Token scopes: 'admin:public_key', 'gist', 'read:org', 'repo'
"""


def test_ci_github_auth_audit_passes_with_repo_scope(monkeypatch):
    def fake_run_text(cmd):
        if cmd == ["gh", "auth", "status"]:
            return 0, AUTH_STATUS, ""
        raise AssertionError(f"unexpected text command: {cmd}")

    def fake_run_json(cmd):
        assert cmd == ["gh", "api", "user"]
        return 0, {"login": "vowstar", "id": 394260}, ""

    monkeypatch.setattr(ci_github_auth_audit.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_github_auth_audit, "run_text", fake_run_text)
    monkeypatch.setattr(ci_github_auth_audit, "run_json", fake_run_json)

    report = ci_github_auth_audit.build_report({"repo"})
    assert report["status"] == "pass"
    assert report["account"] == "vowstar"
    assert report["user"]["login"] == "vowstar"
    assert "repo" in report["scopes"]
    assert "gho_" not in str(report)


def test_ci_github_auth_audit_reports_missing_gh(monkeypatch):
    monkeypatch.setattr(ci_github_auth_audit.shutil, "which", lambda name: None)

    report = ci_github_auth_audit.build_report({"repo"})
    assert report["status"] == "fail"
    assert "GitHub CLI is not available." in report["missing"]


def test_ci_github_auth_audit_reports_missing_required_scope(monkeypatch):
    def fake_run_text(cmd):
        if cmd == ["gh", "auth", "status"]:
            return 0, AUTH_STATUS, ""
        raise AssertionError(f"unexpected text command: {cmd}")

    def fake_run_json(cmd):
        assert cmd == ["gh", "api", "user"]
        return 0, {"login": "vowstar", "id": 394260}, ""

    monkeypatch.setattr(ci_github_auth_audit.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_github_auth_audit, "run_text", fake_run_text)
    monkeypatch.setattr(ci_github_auth_audit, "run_json", fake_run_json)

    report = ci_github_auth_audit.build_report({"repo", "workflow"})
    assert report["status"] == "fail"
    assert "GitHub token does not report required scope: workflow" in report["missing"]
