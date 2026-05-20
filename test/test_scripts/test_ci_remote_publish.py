# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_remote_publish  # noqa: E402


def args(repo=None, confirm_create=False, confirm_push=False):
    return SimpleNamespace(
        repo=repo,
        visibility="private",
        confirm_create=confirm_create,
        confirm_push=confirm_push,
    )


def git_success(repo_root, origin="git@github.com:owner/repo.git"):
    def fake_run_text(cmd):
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return 0, "true", ""
        if cmd == ["git", "rev-parse", "--show-toplevel"]:
            return 0, str(repo_root), ""
        if cmd == ["git", "branch", "--show-current"]:
            return 0, "main", ""
        if cmd == ["git", "rev-parse", "HEAD"]:
            return 0, "abc123", ""
        if cmd == ["git", "status", "--porcelain"]:
            return 0, "", ""
        if cmd == ["git", "remote", "get-url", "origin"]:
            if origin is None:
                return 2, "", "No such remote"
            return 0, origin, ""
        raise AssertionError(f"unexpected command: {cmd}")

    return fake_run_text


def test_ci_remote_publish_blocks_missing_repo_without_external_writes(tmp_path, monkeypatch):
    write_attempts = []

    def fake_run_text(cmd):
        if cmd[:2] in (["gh", "repo"], ["git", "push"], ["git", "remote"]):
            write_attempts.append(cmd)
        return git_success(tmp_path)(cmd)

    def fake_run_json(cmd):
        assert cmd[:4] == ["gh", "repo", "view", "owner/repo"]
        return 1, None, "not found"

    monkeypatch.setattr(ci_remote_publish, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_remote_publish.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_remote_publish, "run_text", fake_run_text)
    monkeypatch.setattr(ci_remote_publish, "run_json", fake_run_json)

    report = ci_remote_publish.build_report(args())
    assert report["status"] == "blocked"
    assert report["repository"] == "owner/repo"
    assert report["steps"] == []
    assert any("not accessible" in item for item in report["missing"])
    assert write_attempts == [["git", "remote", "get-url", "origin"]]


def test_ci_remote_publish_passes_when_remote_branch_matches_local_head(tmp_path, monkeypatch):
    def fake_run_json(cmd):
        if cmd[:4] == ["gh", "repo", "view", "owner/repo"]:
            return 0, {"nameWithOwner": "owner/repo", "url": "https://github.com/owner/repo"}, ""
        if cmd[:2] == ["gh", "api"]:
            return 0, {"object": {"sha": "abc123", "type": "commit"}}, ""
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(ci_remote_publish, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_remote_publish.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_remote_publish, "run_text", git_success(tmp_path))
    monkeypatch.setattr(ci_remote_publish, "run_json", fake_run_json)

    report = ci_remote_publish.build_report(args())
    assert report["status"] == "pass"
    assert report["missing"] == []
    assert report["remote_branch"]["sha"] == "abc123"


def test_ci_remote_publish_confirmed_create_and_push_path(tmp_path, monkeypatch):
    state = {
        "repo_exists": False,
        "branch_sha": None,
    }

    def fake_run_text(cmd):
        if cmd == ["gh", "repo", "create", "owner/repo", "--private"]:
            state["repo_exists"] = True
            return 0, "created", ""
        if cmd == ["git", "remote", "add", "origin", "git@github.com:owner/repo.git"]:
            return 0, "", ""
        if cmd == ["git", "push", "-u", "origin", "main"]:
            state["branch_sha"] = "abc123"
            return 0, "", ""
        return git_success(tmp_path, origin=None)(cmd)

    def fake_run_json(cmd):
        if cmd[:4] == ["gh", "repo", "view", "owner/repo"]:
            if not state["repo_exists"]:
                return 1, None, "not found"
            return 0, {"nameWithOwner": "owner/repo", "url": "https://github.com/owner/repo"}, ""
        if cmd[:2] == ["gh", "api"]:
            if state["branch_sha"] is None:
                return 1, None, "branch missing"
            return 0, {"object": {"sha": state["branch_sha"], "type": "commit"}}, ""
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(ci_remote_publish, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ci_remote_publish.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_remote_publish, "run_text", fake_run_text)
    monkeypatch.setattr(ci_remote_publish, "run_json", fake_run_json)

    report = ci_remote_publish.build_report(args(repo="owner/repo", confirm_create=True, confirm_push=True))
    assert report["status"] == "pass"
    assert [step["name"] for step in report["steps"]] == [
        "create_repository",
        "add_origin",
        "push_branch",
    ]
    assert report["missing"] == []
