#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCOPE_RE = re.compile(r"Token scopes:\s*(?P<scopes>.*)$")


def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def run_text(cmd):
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def parse_scopes(text):
    for line in text.splitlines():
        match = SCOPE_RE.search(line.strip())
        if match:
            scopes_text = match.group("scopes").replace("'", "")
            return sorted(scope.strip() for scope in scopes_text.split(",") if scope.strip())
    return []


def parse_active_account(text):
    for line in text.splitlines():
        if "Logged in to github.com account" in line:
            return line.split("account", maxsplit=1)[1].split("(", maxsplit=1)[0].strip()
    return None


def run_json(cmd):
    returncode, stdout, stderr = run_text(cmd)
    if returncode != 0:
        return returncode, None, stderr or stdout
    try:
        return returncode, json.loads(stdout), ""
    except json.JSONDecodeError as exc:
        return returncode, None, f"failed to parse JSON: {exc}"


def build_report(required_scopes):
    started = time.monotonic()
    report = {
        "status": "fail",
        "duration_seconds": 0.0,
        "required_scopes": sorted(required_scopes),
        "gh_available": shutil.which("gh") is not None,
        "authenticated": False,
        "account": None,
        "user": None,
        "scopes": [],
        "missing": [],
    }

    if not report["gh_available"]:
        report["missing"].append("GitHub CLI is not available.")
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        return report

    returncode, stdout, stderr = run_text(["gh", "auth", "status"])
    auth_text = "\n".join(part for part in (stdout, stderr) if part)
    if returncode != 0:
        report["missing"].append("GitHub CLI is not authenticated.")
        report["auth_error"] = auth_text
    else:
        report["authenticated"] = True
        report["account"] = parse_active_account(auth_text)
        report["scopes"] = parse_scopes(auth_text)

    if report["authenticated"]:
        returncode, payload, error = run_json(["gh", "api", "user"])
        if returncode == 0 and payload is not None:
            report["user"] = {
                "login": payload.get("login"),
                "id": payload.get("id"),
            }
        else:
            report["missing"].append(f"GitHub authenticated user lookup failed: {error}")

    scopes = set(report["scopes"])
    for scope in sorted(required_scopes):
        if scope not in scopes:
            report["missing"].append(f"GitHub token does not report required scope: {scope}")

    if report["authenticated"] and not report["account"]:
        report["missing"].append("Could not parse active GitHub account from gh auth status.")

    report["status"] = "pass" if not report["missing"] else "fail"
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    return report


def write_markdown(path, report):
    lines = [
        "# DitDah32 GitHub Auth Audit",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Account: `{report.get('account')}`",
        f"User: `{(report.get('user') or {}).get('login')}`",
        f"Scopes: `{', '.join(report.get('scopes', []))}`",
        "",
        "## Remaining Blockers",
        "",
    ]
    if report["missing"]:
        for entry in report["missing"]:
            lines.append(f"- {entry}")
    else:
        lines.append("None")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit GitHub CLI authentication for DitDah32 remote CI work")
    parser.add_argument("--required-scope", action="append", default=["repo"], help="Required GitHub token scope. Can be repeated.")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(set(args.required_scope))

    json_path = out_dir / "ci_github_auth.json"
    md_path = out_dir / "ci_github_auth.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_path, report)

    print(f"ci github auth {report['status']}: {rel(json_path)}")
    print(f"markdown: {rel(md_path)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
