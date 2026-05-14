# SPDX-License-Identifier: MIT

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_remote_dispatch  # noqa: E402
import ci_remote_evidence  # noqa: E402


def test_ci_remote_evidence_passes_with_smoke_and_full_artifacts(tmp_path, monkeypatch):
    def fake_run_json(cmd, cwd=ROOT):
        if cmd[:3] == ["gh", "repo", "view"]:
            return 0, {
                "nameWithOwner": "owner/repo",
                "url": "https://github.com/owner/repo",
                "defaultBranchRef": {"name": "main"},
                "visibility": "PRIVATE",
            }, ""
        if cmd[:3] == ["gh", "run", "list"]:
            return 0, [
                {
                    "databaseId": 11,
                    "displayTitle": "Smoke",
                    "conclusion": "success",
                    "status": "completed",
                    "event": "workflow_dispatch",
                    "headSha": "abc",
                    "headBranch": "main",
                    "url": "https://github.com/owner/repo/actions/runs/11",
                    "createdAt": "2026-05-15T00:00:00Z",
                    "updatedAt": "2026-05-15T00:01:00Z",
                    "workflowName": "DitDah32 Verification",
                },
                {
                    "databaseId": 22,
                    "displayTitle": "Full",
                    "conclusion": "success",
                    "status": "completed",
                    "event": "workflow_dispatch",
                    "headSha": "abc",
                    "headBranch": "main",
                    "url": "https://github.com/owner/repo/actions/runs/22",
                    "createdAt": "2026-05-15T00:02:00Z",
                    "updatedAt": "2026-05-15T00:03:00Z",
                    "workflowName": "DitDah32 Verification",
                },
            ], ""
        if cmd[:3] == ["gh", "run", "view"]:
            run_id = cmd[3]
            name = "Smoke" if run_id == "11" else "Full"
            return 0, {"jobs": [{"name": name, "status": "completed", "conclusion": "success"}]}, ""
        if cmd[:2] == ["gh", "api"]:
            artifact_name = "ditdah32-smoke-11" if "/11/" in cmd[2] else "ditdah32-full-22"
            return 0, {"artifacts": [{"name": artifact_name}]}, ""
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(ci_remote_evidence.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_remote_evidence, "run_json", fake_run_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_remote_evidence.py",
            "--repo",
            "owner/repo",
            "--out-dir",
            str(tmp_path),
        ],
    )

    assert ci_remote_evidence.main() == 0
    report = json.loads((tmp_path / "ci_remote_evidence.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["satisfied_runs"]["smoke"]["run_id"] == 11
    assert report["satisfied_runs"]["full"]["run_id"] == 22


def test_ci_remote_evidence_reports_missing_repository(tmp_path, monkeypatch):
    calls = []

    def fake_run_json(cmd, cwd=ROOT):
        calls.append(cmd)
        if cmd[:3] == ["gh", "repo", "view"]:
            return 1, None, "repository not found"
        raise AssertionError(f"unexpected command after repository probe failed: {cmd}")

    monkeypatch.setattr(ci_remote_evidence.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_remote_evidence, "run_json", fake_run_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_remote_evidence.py",
            "--repo",
            "owner/missing",
            "--out-dir",
            str(tmp_path),
        ],
    )

    assert ci_remote_evidence.main() == 1
    report = json.loads((tmp_path / "ci_remote_evidence.json").read_text(encoding="utf-8"))
    assert report["status"] == "missing"
    assert report["repository_probe"]["status"] == "missing"
    assert any("not accessible" in item for item in report["missing"])
    assert calls == [["gh", "repo", "view", "owner/missing", "--json", "nameWithOwner,url,defaultBranchRef,visibility"]]


def test_ci_remote_dispatch_does_not_dispatch_when_repository_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ci_remote_dispatch.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(ci_remote_dispatch, "repository_probe", lambda repo: {"status": "missing", "error": "not found"})
    monkeypatch.setattr(
        ci_remote_dispatch,
        "run_text",
        lambda cmd: (_ for _ in ()).throw(AssertionError(f"dispatch should not run: {cmd}")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_remote_dispatch.py",
            "--repo",
            "owner/missing",
            "--profiles",
            "smoke",
            "--out-dir",
            str(tmp_path),
        ],
    )

    assert ci_remote_dispatch.main() == 1
    report = json.loads((tmp_path / "ci_remote_dispatch.json").read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["steps"] == []
    assert any("not accessible" in item for item in report["missing"])


def test_ci_remote_dispatch_runs_profiles_in_order_and_waits(tmp_path, monkeypatch):
    dispatches = []
    list_calls = 0
    view_calls = {}

    run_ids = {
        "smoke": 101,
        "full": 202,
        "ci-evidence": 303,
    }

    def fake_run_text(cmd):
        assert cmd[:4] == ["gh", "workflow", "run", "verification.yml"]
        profile = cmd[cmd.index("-f") + 1].split("=", maxsplit=1)[1]
        dispatches.append(profile)
        return 0, "", ""

    def fake_run_json(cmd, cwd=ROOT):
        nonlocal list_calls
        if cmd[:3] == ["gh", "run", "list"]:
            list_calls += 1
            runs = []
            for profile in dispatches:
                runs.append(
                    {
                        "databaseId": run_ids[profile],
                        "displayTitle": profile,
                        "conclusion": None,
                        "status": "queued",
                        "event": "workflow_dispatch",
                        "headSha": "abc",
                        "headBranch": "main",
                        "url": f"https://github.com/owner/repo/actions/runs/{run_ids[profile]}",
                        "createdAt": "2026-05-15T00:00:00Z",
                        "updatedAt": "2026-05-15T00:00:00Z",
                        "workflowName": "DitDah32 Verification",
                    }
                )
            return 0, runs, ""
        if cmd[:3] == ["gh", "run", "view"]:
            run_id = int(cmd[3])
            view_calls[run_id] = view_calls.get(run_id, 0) + 1
            return 0, {
                "databaseId": run_id,
                "conclusion": "success",
                "status": "completed",
                "headSha": "abc",
                "headBranch": "main",
                "url": f"https://github.com/owner/repo/actions/runs/{run_id}",
                "createdAt": "2026-05-15T00:00:00Z",
                "updatedAt": "2026-05-15T00:01:00Z",
                "workflowName": "DitDah32 Verification",
            }, ""
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(ci_remote_dispatch.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(
        ci_remote_dispatch,
        "repository_probe",
        lambda repo: {
            "status": "pass",
            "name_with_owner": repo,
            "url": f"https://github.com/{repo}",
            "default_branch": "main",
            "visibility": "PRIVATE",
        },
    )
    monkeypatch.setattr(ci_remote_dispatch, "run_text", fake_run_text)
    monkeypatch.setattr(ci_remote_dispatch, "run_json", fake_run_json)
    monkeypatch.setattr(ci_remote_dispatch.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_remote_dispatch.py",
            "--repo",
            "owner/repo",
            "--profiles",
            "smoke",
            "full",
            "ci-evidence",
            "--wait",
            "--out-dir",
            str(tmp_path),
        ],
    )

    assert ci_remote_dispatch.main() == 0
    report = json.loads((tmp_path / "ci_remote_dispatch.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert dispatches == ["smoke", "full", "ci-evidence"]
    assert [step["status"] for step in report["steps"]] == ["pass", "pass", "pass"]
    assert [step["run_id"] for step in report["steps"]] == [101, 202, 303]
    assert list_calls >= 6
    assert view_calls == {101: 1, 202: 1, 303: 1}
