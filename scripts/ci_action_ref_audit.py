#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
USES_RE = re.compile(r"^(?P<owner>[^/\s]+)/(?P<repo>[^@\s]+)@(?P<ref>[^\s]+)$")


def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def run_json(cmd):
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode, None, completed.stderr.strip() or completed.stdout.strip()
    try:
        return completed.returncode, json.loads(completed.stdout), ""
    except json.JSONDecodeError as exc:
        return completed.returncode, None, f"failed to parse JSON: {exc}"


def workflow_trigger(workflow):
    return workflow.get("on", workflow.get(True, {}))


def collect_uses(workflow):
    refs = []
    for job_name, job in (workflow.get("jobs") or {}).items():
        for index, step in enumerate(job.get("steps", [])):
            uses = step.get("uses")
            if not uses:
                continue
            match = USES_RE.match(str(uses))
            refs.append(
                {
                    "job": job_name,
                    "step_index": index,
                    "uses": uses,
                    "parsed": None if match is None else match.groupdict(),
                }
            )
    return refs


def check_ref(parsed):
    owner = parsed["owner"]
    repo = parsed["repo"]
    ref = parsed["ref"]
    for ref_type in ("tags", "heads"):
        returncode, payload, error = run_json(
            [
                "gh",
                "api",
                f"repos/{owner}/{repo}/git/ref/{ref_type}/{ref}",
            ]
        )
        if returncode == 0 and payload is not None:
            return {
                "status": "pass",
                "ref_type": ref_type,
                "sha": (payload.get("object") or {}).get("sha"),
                "object_type": (payload.get("object") or {}).get("type"),
            }
        last_error = error
    return {
        "status": "missing",
        "error": last_error,
    }


def build_report(workflow_path):
    started = time.monotonic()
    workflow_full_path = workflow_path if workflow_path.is_absolute() else REPO_ROOT / workflow_path
    report = {
        "status": "fail",
        "workflow": rel(workflow_full_path),
        "trigger_keys": [],
        "refs": [],
        "missing": [],
        "duration_seconds": 0.0,
    }

    if not workflow_full_path.exists():
        report["missing"].append(f"Workflow file is missing: {rel(workflow_full_path)}")
    elif shutil.which("gh") is None:
        report["missing"].append("GitHub CLI is not available.")
    else:
        workflow = yaml.safe_load(workflow_full_path.read_text(encoding="utf-8"))
        trigger = workflow_trigger(workflow) or {}
        report["trigger_keys"] = sorted(str(key) for key in trigger)
        for item in collect_uses(workflow):
            if item["parsed"] is None:
                item["check"] = {"status": "unsupported"}
                report["missing"].append(f"Unsupported action reference syntax: {item['uses']}")
            else:
                item["check"] = check_ref(item["parsed"])
                if item["check"].get("status") != "pass":
                    report["missing"].append(f"Action reference is not resolvable: {item['uses']}")
            report["refs"].append(item)

    if not report["refs"] and not report["missing"]:
        report["missing"].append("Workflow contains no action references to audit.")
    report["status"] = "pass" if not report["missing"] else "fail"
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    return report


def write_markdown(path, report):
    lines = [
        "# DitDah32 CI Action Reference Audit",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Workflow: `{report['workflow']}`",
        "",
        "| Reference | Status | Type | SHA |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["refs"]:
        check = item.get("check") or {}
        lines.append(
            f"| `{item['uses']}` | `{check.get('status')}` | `{check.get('ref_type', '')}` | `{check.get('sha', '')}` |"
        )
    lines.extend(["", "## Remaining Blockers", ""])
    if report["missing"]:
        for entry in report["missing"]:
            lines.append(f"- {entry}")
    else:
        lines.append("None")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit GitHub Actions references used by the DitDah32 workflow")
    parser.add_argument("--workflow", type=Path, default=REPO_ROOT / ".github" / "workflows" / "verification.yml")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args.workflow)

    json_path = out_dir / "ci_action_refs.json"
    md_path = out_dir / "ci_action_refs.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_path, report)

    print(f"ci action refs {report['status']}: {rel(json_path)}")
    print(f"markdown: {rel(md_path)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
