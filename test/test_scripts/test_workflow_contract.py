# SPDX-License-Identifier: MIT

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_verification_workflow_contains_required_ci_contract():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "verification.yml").read_text(encoding="utf-8"))

    jobs = workflow["jobs"]
    assert {"smoke", "full", "signoff", "spike-matrix", "ci-evidence"}.issubset(jobs)

    permissions = workflow["permissions"]
    assert permissions["contents"] == "read"
    assert permissions["actions"] == "read"

    dispatch_options = workflow[True]["workflow_dispatch"]["inputs"]["profile"]["options"]
    assert {"smoke", "full", "signoff", "spike-matrix", "ci-evidence"}.issubset(dispatch_options)

    smoke_run = jobs["smoke"]["steps"][2]["run"]
    full_run = jobs["full"]["steps"][2]["run"]
    signoff_run = jobs["signoff"]["steps"][2]["run"]
    ci_evidence_run = jobs["ci-evidence"]["steps"][2]["run"]
    assert "make verify-smoke" in smoke_run
    assert "make verify" in full_run
    assert "make verify-signoff" in signoff_run
    assert "make audit-ci-remote" in ci_evidence_run
    assert "make audit-gaps" in ci_evidence_run

    signoff_artifact_paths = jobs["signoff"]["steps"][3]["with"]["path"]
    ci_evidence_artifact_paths = jobs["ci-evidence"]["steps"][3]["with"]["path"]
    assert "result/verification/**" in signoff_artifact_paths
    assert "result/riscv_dv/**" in signoff_artifact_paths
    assert "result/iss/**" in signoff_artifact_paths
    assert "result/verification/**" in ci_evidence_artifact_paths
