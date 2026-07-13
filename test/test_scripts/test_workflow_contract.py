# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
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

    smoke_run = "\n".join(str(step.get("run", "")) for step in jobs["smoke"]["steps"])
    full_run = "\n".join(str(step.get("run", "")) for step in jobs["full"]["steps"])
    signoff_run = "\n".join(str(step.get("run", "")) for step in jobs["signoff"]["steps"])
    ci_evidence_run = "\n".join(str(step.get("run", "")) for step in jobs["ci-evidence"]["steps"])
    assert "make verify-ci-smoke" in smoke_run
    assert "make verify" in full_run
    assert "make verify-signoff" in signoff_run
    assert "make audit-ci-remote" in ci_evidence_run
    assert "make audit-gaps" in ci_evidence_run

    signoff_artifact_paths = next(step for step in jobs["signoff"]["steps"] if "upload-artifact" in step.get("uses", ""))["with"]["path"]
    ci_evidence_artifact_paths = next(step for step in jobs["ci-evidence"]["steps"] if "upload-artifact" in step.get("uses", ""))["with"]["path"]
    assert "result/verification/**" in signoff_artifact_paths
    assert "result/riscv_dv/**" in signoff_artifact_paths
    assert "result/iss/**" in signoff_artifact_paths
    assert "result/verification/**" in ci_evidence_artifact_paths


def test_release_workflow_packages_and_publishes_two_rtl_variants():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )

    assert workflow[True]["push"]["tags"] == ["v*"]
    assert workflow["permissions"]["contents"] == "read"
    assert set(workflow["jobs"]) == {"build", "publish"}

    build = workflow["jobs"]["build"]
    publish = workflow["jobs"]["publish"]
    assert publish["needs"] == "build"
    assert publish["permissions"]["contents"] == "write"
    assert publish["env"]["GH_REPO"] == "${{ github.repository }}"

    build_run = "\n".join(str(step.get("run", "")) for step in build["steps"])
    publish_run = "\n".join(str(step.get("run", "")) for step in publish["steps"])
    assert "nix build .#release-inputs" in build_run
    assert "scripts/package_release.py" in build_run
    assert "--verify" in build_run
    assert "ditdah32-${RELEASE_TAG}.tar.gz" in publish_run
    assert "ditdah32-${RELEASE_TAG}-jtag.tar.gz" in publish_run
    assert "gh release create" in publish_run
    assert "--draft" in publish_run
    assert "--generate-notes" in publish_run
    assert "--verify-tag" in publish_run
    assert "gh release edit" in publish_run

    cache_step = next(
        step for step in build["steps"] if "cache-nix-action" in step.get("uses", "")
    )
    assert cache_step["with"]["save"] is False
    upload_paths = next(
        step for step in build["steps"] if "upload-artifact" in step.get("uses", "")
    )["with"]["path"]
    assert "result/release/ditdah32-*.tar.gz" in upload_paths
    assert "result/release/SHA256SUMS" in upload_paths


def test_release_cache_is_scoped_to_trusted_default_branch_updates():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "release-cache.yml").read_text(
            encoding="utf-8"
        )
    )

    trigger = workflow[True]
    assert trigger["push"]["branches"] == ["main"]
    assert {"flake.nix", "flake.lock", "nix/**"}.issubset(trigger["push"]["paths"])
    assert workflow["permissions"]["contents"] == "read"

    warm = workflow["jobs"]["warm"]
    cache_step = next(
        step for step in warm["steps"] if "cache-nix-action" in step.get("uses", "")
    )
    assert cache_step["with"]["gc-max-store-size-linux"] == "14G"
    assert cache_step["with"]["purge"] is True
    warm_run = "\n".join(str(step.get("run", "")) for step in warm["steps"])
    assert "nix build .#release-inputs" in warm_run
