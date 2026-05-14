#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import time
from pathlib import Path

import ci_action_ref_audit
import ci_github_auth_audit
import ci_publish_readiness


REPO_ROOT = Path(__file__).resolve().parents[1]


def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def component(name, report, pass_status="pass"):
    missing = report.get("missing", [])
    return {
        "name": name,
        "status": report.get("status"),
        "passed": report.get("status") == pass_status and not missing,
        "missing": missing,
        "report": report,
    }


def build_report(repo=None, workflow=None, required_scopes=None):
    started = time.monotonic()
    workflow_path = workflow or (REPO_ROOT / ".github" / "workflows" / "verification.yml")
    scopes = required_scopes or {"repo"}
    components = [
        component("github_auth", ci_github_auth_audit.build_report(scopes)),
        component("publish_readiness", ci_publish_readiness.build_report(repo)),
        component("action_refs", ci_action_ref_audit.build_report(workflow_path)),
    ]
    missing = []
    for item in components:
        missing.extend([f"{item['name']}: {entry}" for entry in item["missing"]])
        if not item["passed"] and not item["missing"]:
            missing.append(f"{item['name']}: status is {item['status']}, expected pass.")

    return {
        "status": "pass" if not missing else "fail",
        "duration_seconds": round(time.monotonic() - started, 3),
        "repository": repo,
        "workflow": rel(workflow_path if workflow_path.is_absolute() else REPO_ROOT / workflow_path),
        "components": components,
        "missing": missing,
    }


def write_markdown(path, report):
    lines = [
        "# DitDah32 Remote CI Preflight Audit",
        "",
        f"Status: `{report['status']}`",
        "",
        "| Component | Status | Passed | Missing |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["components"]:
        missing = "<br>".join(item["missing"]) if item["missing"] else "None"
        lines.append(f"| {item['name']} | `{item['status']}` | `{str(item['passed']).lower()}` | {missing} |")
    lines.extend(["", "## Remaining Blockers", ""])
    if report["missing"]:
        for entry in report["missing"]:
            lines.append(f"- {entry}")
    else:
        lines.append("None")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run local preflight audits required before DitDah32 remote CI closure")
    parser.add_argument("--repo", help="Target GitHub repository as owner/name. Defaults to git origin in the readiness audit.")
    parser.add_argument("--workflow", type=Path, default=REPO_ROOT / ".github" / "workflows" / "verification.yml")
    parser.add_argument("--required-scope", action="append", default=["repo"], help="Required GitHub token scope. Can be repeated.")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args.repo, args.workflow, set(args.required_scope))

    json_path = out_dir / "ci_remote_preflight.json"
    md_path = out_dir / "ci_remote_preflight.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_path, report)

    print(f"ci remote preflight {report['status']}: {rel(json_path)}")
    print(f"markdown: {rel(md_path)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
