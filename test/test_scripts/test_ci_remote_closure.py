# SPDX-License-Identifier: MIT

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import ci_remote_closure  # noqa: E402


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def completed(cmd, returncode=0):
    return subprocess.CompletedProcess(cmd, returncode)


def test_ci_remote_closure_skip_dispatch_collects_and_audits_existing_runs(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    verification_dir = repo_root / "result" / "verification"
    out_dir = tmp_path / "closure"
    commands = []

    def fake_run(cmd, cwd, stdout, stderr, check):
        assert cwd == repo_root
        assert stderr == subprocess.STDOUT
        assert check is False
        commands.append(cmd)
        script = Path(cmd[1]).name
        if script == "ci_remote_preflight.py":
            write_json(verification_dir / "ci_remote_preflight.json", {"status": "pass"})
        elif script == "ci_remote_evidence.py":
            write_json(verification_dir / "ci_remote_evidence.json", {"status": "pass"})
        elif script == "open_gap_audit.py":
            write_json(verification_dir / "open_gaps.json", {"status": "no_open_gaps"})
        elif script == "completion_audit.py":
            write_json(verification_dir / "completion_audit.json", {"status": "complete"})
        else:
            raise AssertionError(f"unexpected command: {cmd}")
        return completed(cmd)

    monkeypatch.setattr(ci_remote_closure, "REPO_ROOT", repo_root)
    monkeypatch.setattr(ci_remote_closure.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_remote_closure.py",
            "--repo",
            "owner/repo",
            "--head-sha",
            "abc123",
            "--skip-dispatch",
            "--out-dir",
            str(out_dir),
        ],
    )

    assert ci_remote_closure.main() == 0
    report = json.loads((out_dir / "ci_remote_closure.json").read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["expected_head_sha"] == "abc123"
    assert [step["name"] for step in report["steps"]] == [
        "ci_remote_preflight",
        "ci_remote_evidence",
        "open_gap_audit",
        "completion_audit",
    ]
    assert [Path(cmd[1]).name for cmd in commands] == [
        "ci_remote_preflight.py",
        "ci_remote_evidence.py",
        "open_gap_audit.py",
        "completion_audit.py",
    ]
    evidence_command = commands[1]
    assert evidence_command[evidence_command.index("--head-sha") + 1] == "abc123"
    assert report["ci_remote_preflight_status"] == "pass"
    assert report["ci_remote_status"] == "pass"
    assert report["open_gap_status"] == "no_open_gaps"
    assert report["completion_status"] == "complete"


def test_ci_remote_closure_stops_when_dispatch_fails(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    out_dir = tmp_path / "closure"
    commands = []

    def fake_run(cmd, cwd, stdout, stderr, check):
        assert cwd == repo_root
        commands.append(cmd)
        script = Path(cmd[1]).name
        if script == "ci_remote_preflight.py":
            return completed(cmd)
        if script == "ci_remote_dispatch.py":
            return completed(cmd, returncode=1)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(ci_remote_closure, "REPO_ROOT", repo_root)
    monkeypatch.setattr(ci_remote_closure.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_remote_closure.py",
            "--repo",
            "owner/missing",
            "--head-sha",
            "def456",
            "--dispatch-timeout-seconds",
            "1",
            "--out-dir",
            str(out_dir),
        ],
    )

    assert ci_remote_closure.main() == 1
    report = json.loads((out_dir / "ci_remote_closure.json").read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["expected_head_sha"] == "def456"
    assert report["reason"] == "Remote workflow dispatch or wait failed."
    assert [step["name"] for step in report["steps"]] == ["ci_remote_preflight", "ci_remote_dispatch"]
    assert report["steps"][0]["status"] == "pass"
    assert report["steps"][1]["status"] == "fail"
    assert [Path(cmd[1]).name for cmd in commands] == ["ci_remote_preflight.py", "ci_remote_dispatch.py"]
    dispatch_command = commands[1]
    assert dispatch_command[dispatch_command.index("--head-sha") + 1] == "def456"


def test_ci_remote_closure_stops_when_preflight_fails(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    out_dir = tmp_path / "closure"
    commands = []

    def fake_run(cmd, cwd, stdout, stderr, check):
        assert cwd == repo_root
        commands.append(cmd)
        assert Path(cmd[1]).name == "ci_remote_preflight.py"
        return completed(cmd, returncode=1)

    monkeypatch.setattr(ci_remote_closure, "REPO_ROOT", repo_root)
    monkeypatch.setattr(ci_remote_closure.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ci_remote_closure.py",
            "--repo",
            "owner/repo",
            "--head-sha",
            "fedcba",
            "--out-dir",
            str(out_dir),
        ],
    )

    assert ci_remote_closure.main() == 1
    report = json.loads((out_dir / "ci_remote_closure.json").read_text(encoding="utf-8"))
    assert report["status"] == "fail"
    assert report["expected_head_sha"] == "fedcba"
    assert report["reason"] == "Remote CI preflight failed."
    assert [step["name"] for step in report["steps"]] == ["ci_remote_preflight"]
    assert [Path(cmd[1]).name for cmd in commands] == ["ci_remote_preflight.py"]
