# SPDX-License-Identifier: MIT

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import completion_audit  # noqa: E402


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path, text="ok\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def closed_gap(gap_id, status="closed"):
    return {
        "id": gap_id,
        "status": status,
        "closed": True,
        "missing": [],
    }


def populate_completion_repo(tmp_path, ci_status="pass", not_closed=0):
    write_json(
        tmp_path / "result" / "verification" / "signoff.json",
        {
            "status": "pass",
            "duration_seconds": 1.0,
            "git": {
                "available": True,
                "head": "abc123",
                "branch": "main",
                "dirty": False,
                "status_porcelain": "",
            },
        },
    )
    write_json(tmp_path / "result" / "iss" / "external_iss_full" / "external_iss_full.json", {"status": "pass"})
    write_json(tmp_path / "result" / "riscv_dv" / "riscv_dv.json", {"status": "pass"})
    write_json(tmp_path / "result" / "formal" / "rvfi" / "rvfi.json", {"status": "pass"})
    write_json(tmp_path / "result" / "axi" / "axi_lite_backpressure.json", {"status": "pass"})
    write_json(tmp_path / "result" / "bench" / "benchmark_scores.json", {"status": "pass"})
    write_text(tmp_path / "result" / "verification" / "open_gaps.md")

    ci_gap = closed_gap("ci_regression")
    ci_missing = []
    if ci_status != "pass":
        ci_gap = {
            "id": "ci_regression",
            "status": "partial",
            "closed": False,
            "missing": ["No successful remote full run with uploaded artifact evidence was found."],
        }
        ci_missing = ci_gap["missing"]

    write_json(
        tmp_path / "result" / "verification" / "open_gaps.json",
        {
            "summary": {"closed": 6 - not_closed, "not_closed": not_closed, "total": 6},
            "gaps": [
                closed_gap("external_iss", "closed_composite"),
                closed_gap("riscv_dv"),
                closed_gap("rvfi_riscv_formal", "closed_with_limitations"),
                closed_gap("full_axi4", "closed_out_of_scope"),
                ci_gap,
                closed_gap("certified_benchmarks", "closed_non_certified"),
            ],
        },
    )
    write_json(
        tmp_path / "result" / "verification" / "ci_remote_evidence.json",
        {
            "status": ci_status,
            "missing": ci_missing,
            "satisfied_runs": {
                "smoke": {"run_id": 11, "url": "https://github.com/owner/repo/actions/runs/11"},
                "full": None if ci_status != "pass" else {"run_id": 22, "url": "https://github.com/owner/repo/actions/runs/22"},
            },
        },
    )


def test_completion_audit_reports_complete_when_all_items_pass(tmp_path, monkeypatch):
    populate_completion_repo(tmp_path, ci_status="pass", not_closed=0)
    monkeypatch.setattr(completion_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        completion_audit,
        "current_git_state",
        lambda: {
            "available": True,
            "head": "abc123",
            "branch": "main",
            "dirty": False,
            "status_porcelain": "",
            "error": None,
        },
    )

    report = completion_audit.build_report()
    assert report["status"] == "complete"
    assert report["missing"] == []
    assert all(item["passed"] for item in report["checklist"])


def test_completion_audit_reports_incomplete_when_remote_ci_is_missing(tmp_path, monkeypatch):
    populate_completion_repo(tmp_path, ci_status="missing", not_closed=1)
    monkeypatch.setattr(completion_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        completion_audit,
        "current_git_state",
        lambda: {
            "available": True,
            "head": "abc123",
            "branch": "main",
            "dirty": False,
            "status_porcelain": "",
            "error": None,
        },
    )

    report = completion_audit.build_report()
    assert report["status"] == "incomplete"
    failed_items = {item["name"]: item for item in report["checklist"] if not item["passed"]}
    assert set(failed_items) == {"remote_ci", "open_gap_audit"}
    assert any("remote_ci" in item for item in report["missing"])
    assert any("Open or partial gaps remain: 1 / 6" in item for item in report["missing"])


def test_completion_audit_rejects_stale_local_signoff(tmp_path, monkeypatch):
    populate_completion_repo(tmp_path, ci_status="pass", not_closed=0)
    monkeypatch.setattr(completion_audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        completion_audit,
        "current_git_state",
        lambda: {
            "available": True,
            "head": "new456",
            "branch": "main",
            "dirty": False,
            "status_porcelain": "",
            "error": None,
        },
    )

    report = completion_audit.build_report()
    assert report["status"] == "incomplete"
    failed_items = {item["name"]: item for item in report["checklist"] if not item["passed"]}
    assert set(failed_items) == {"local_signoff"}
    assert "Local signoff report was not generated from the current git HEAD." in failed_items["local_signoff"]["missing"]
