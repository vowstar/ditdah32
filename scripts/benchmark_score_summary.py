#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_report(path):
    if not path.exists():
        raise SystemExit(f"missing benchmark score report: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown(path, report):
    coremark = report["benchmarks"]["coremark"]
    dhrystone = report["benchmarks"]["dhrystone"]
    lines = [
        "# DitDah32 Benchmark Score Report",
        "",
        f"Status: `{report['status']}`",
        "",
        "These numbers are local RTL estimates from software timing markers. They are not certified CoreMark or Dhrystone scores.",
        "",
        "## Configuration",
        "",
        f"- Frequency: {report['frequency_mhz']:.3f} MHz",
        f"- CoreMark cycle source: `{coremark['cycle_source']}`",
        f"- Dhrystone cycle source: `{dhrystone['cycle_source']}`",
        "",
        "## Scores",
        "",
        "| Benchmark | Timed cycles | Work units | Score @ frequency | Score/MHz |",
        "| --- | ---: | ---: | ---: | ---: |",
        (
            f"| CoreMark | {coremark['timed_cycles']} | {coremark['iterations']} | "
            f"{coremark['coremark_per_second']:.6f} CoreMark/s | {coremark['coremark_per_mhz']:.6f} |"
        ),
        (
            f"| Dhrystone | {dhrystone['timed_cycles']} | {dhrystone['runs']} | "
            f"{dhrystone['dhrystones_per_second']:.6f} Dhrystones/s | {dhrystone['dmips_per_mhz']:.9f} DMIPS/MHz |"
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Summarize DitDah32 local RTL benchmark score estimates")
    parser.add_argument("--in-dir", type=Path, default=REPO_ROOT / "result" / "bench" / "scores")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "result" / "bench" / "benchmark_scores.json")
    parser.add_argument("--markdown", type=Path, default=REPO_ROOT / "result" / "bench" / "benchmark_scores.md")
    parser.add_argument("--frequency-mhz", type=float, default=100.0)
    args = parser.parse_args()

    in_dir = args.in_dir if args.in_dir.is_absolute() else REPO_ROOT / args.in_dir
    out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    markdown = args.markdown if args.markdown.is_absolute() else REPO_ROOT / args.markdown

    reports = {
        "coremark": read_report(in_dir / "coremark.json"),
        "dhrystone": read_report(in_dir / "dhrystone.json"),
    }
    for name, report in reports.items():
        if report["certification_status"] != "not_certified_local_rtl_estimate":
            raise SystemExit(f"{name}: unexpected certification status {report['certification_status']}")
        if abs(report["frequency_mhz"] - args.frequency_mhz) > 0.001:
            raise SystemExit(f"{name}: frequency mismatch {report['frequency_mhz']} != {args.frequency_mhz}")

    status = "pass" if all(report["timed_cycles"] > 0 for report in reports.values()) else "fail"
    summary = {
        "status": status,
        "frequency_mhz": args.frequency_mhz,
        "certification_status": "not_certified_local_rtl_estimate",
        "benchmarks": reports,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(markdown, summary)
    print(f"benchmark score {status}: {out.relative_to(REPO_ROOT)}")
    print(f"markdown: {markdown.relative_to(REPO_ROOT)}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
