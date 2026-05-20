#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT
"""Run Sail on each compliance ISS ELF and dump begin/end_signature regions
to result/compliance/sail_signatures/<name>/signature.txt.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = REPO_ROOT / "result" / "compliance" / "build"
SIG_OUT_ROOT = REPO_ROOT / "result" / "compliance" / "sail_signatures"
DEFAULT_CONFIG = (
    Path("/nix/store/gfmzkrwdaxxvgs15src1q0g6hm9dl4cx-sail-riscv-0.8/share/sail-riscv/config/rv32d.json")
)


def run(cmd, cwd=None, timeout=60):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--sail", default="sail_riscv_sim")
    parser.add_argument("--out-dir", default=str(SIG_OUT_ROOT))
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    sail = shutil.which(args.sail)
    if sail is None:
        print(f"missing sail simulator: {args.sail}", file=sys.stderr)
        return 1
    config = Path(args.config)
    if not config.is_file():
        print(f"missing Sail config: {config}", file=sys.stderr)
        return 1

    manifest_path = BUILD_DIR / "compliance_build.json"
    if not manifest_path.is_file():
        print("no compliance build manifest; run scripts/build_compliance.py first.", file=sys.stderr)
        return 1
    build_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    records = []
    overall_pass = True

    for entry in build_manifest["tests"]:
        name = entry["name"]
        iss_artifact = entry.get("iss", {})
        elf_rel = iss_artifact.get("elf")
        if not elf_rel:
            records.append({"name": name, "status": "missing", "reason": "no iss elf in build manifest"})
            overall_pass = False
            continue
        elf_path = REPO_ROOT / elf_rel
        sig_dir = out_dir / name
        sig_dir.mkdir(parents=True, exist_ok=True)
        sig_path = sig_dir / "signature.txt"

        completed = run(
            [
                sail,
                "--config", str(config),
                "--test-signature", str(sig_path),
                str(elf_path),
            ],
            timeout=args.timeout,
        )
        log_path = log_dir / f"{name}.log"
        log_path.write_text(
            "STDOUT:\n" + completed.stdout + "\n\nSTDERR:\n" + completed.stderr,
            encoding="utf-8",
        )

        if completed.returncode != 0:
            records.append({
                "name": name,
                "status": "fail",
                "reason": f"sail exit {completed.returncode}",
                "log": str(log_path.relative_to(REPO_ROOT)),
            })
            overall_pass = False
            continue

        if not sig_path.is_file():
            records.append({
                "name": name,
                "status": "fail",
                "reason": "Sail did not produce a signature file (probably begin/end_signature symbols missing)",
                "log": str(log_path.relative_to(REPO_ROOT)),
            })
            overall_pass = False
            continue

        words = [line.strip() for line in sig_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        records.append({
            "name": name,
            "status": "pass",
            "signature_file": str(sig_path.relative_to(REPO_ROOT)),
            "signature_words": words,
            "log": str(log_path.relative_to(REPO_ROOT)),
        })

    report = {
        "status": "pass" if overall_pass else "fail",
        "sail_binary": sail,
        "config": str(config),
        "tests": records,
    }
    out_json = out_dir / "sail_signatures.json"
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"sail signatures {report['status']}: {out_json.relative_to(REPO_ROOT)}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
