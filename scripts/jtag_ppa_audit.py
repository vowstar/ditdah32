#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import re
import shlex
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_BASELINE = {
    "num_cells": 11669,
    "num_ports": 28,
    "num_port_bits": 161,
    "logic_depth": 94,
}


def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def parse_logic_depth(log_text):
    match = re.search(r"Longest topological path in DitDah32 \(length=(\d+)\)", log_text)
    if not match:
        raise ValueError("DitDah32 logic depth was not reported")
    return int(match.group(1))


def metrics_from_stats(stats, logic_depth):
    design = stats["design"]
    cell_types = design["num_cells_by_type"]
    register_cells = sum(
        count for cell_type, count in cell_types.items() if "DFF" in cell_type
    )
    return {
        "num_cells": design["num_cells"],
        "num_ports": design["num_ports"],
        "num_port_bits": design["num_port_bits"],
        "register_cells": register_cells,
        "logic_depth": logic_depth,
    }


def synthesize(name, sources, out_dir):
    stats_path = out_dir / f"{name}_stats.json"
    log_path = out_dir / "logs" / f"{name}_synthesis.log"
    quoted_sources = " ".join(shlex.quote(source) for source in sources)
    script = (
        f"read_verilog -sv {quoted_sources}; "
        "synth -flatten -top DitDah32; "
        f"tee -o {shlex.quote(rel(stats_path))} stat -json; "
        "ltp -noff"
    )
    start = time.monotonic()
    completed = subprocess.run(
        ["yosys", "-q", "-l", rel(log_path), "-p", script],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        check=False,
    )
    result = {
        "name": name,
        "duration_seconds": round(time.monotonic() - start, 3),
        "log": rel(log_path),
        "returncode": completed.returncode,
        "status": "pass" if completed.returncode == 0 else "fail",
    }
    if completed.returncode == 0:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        result["metrics"] = metrics_from_stats(
            stats, parse_logic_depth(log_path.read_text(encoding="utf-8"))
        )
    return result


def check_baseline(metrics):
    mismatches = {
        key: {"expected": expected, "actual": metrics.get(key)}
        for key, expected in PRODUCTION_BASELINE.items()
        if metrics.get(key) != expected
    }
    return {
        "status": "pass" if not mismatches else "fail",
        "expected": PRODUCTION_BASELINE,
        "mismatches": mismatches,
    }


def write_markdown(report, path):
    production = report["production"].get("metrics", {})
    jtag = report["jtag"].get("metrics", {})
    lines = [
        "# DitDah32 JTAG PPA Proxy Audit",
        "",
        f"Status: `{report['status']}`",
        "",
        "| configuration | cells | registers | logic depth |",
        "| --- | ---: | ---: | ---: |",
        f"| production | {production.get('num_cells', '-')} | "
        f"{production.get('register_cells', '-')} | {production.get('logic_depth', '-')} |",
        f"| JTAG | {jtag.get('num_cells', '-')} | "
        f"{jtag.get('register_cells', '-')} | {jtag.get('logic_depth', '-')} |",
        "",
        "Generic Yosys synthesis is an area and logic-depth proxy, not technology signoff.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit optional JTAG generic synthesis cost")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    parser.add_argument("--build-root", type=Path, default=REPO_ROOT / "result" / "trace_config")
    args = parser.parse_args()

    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    build_root = args.build_root if args.build_root.is_absolute() else REPO_ROOT / args.build_root
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)

    production = synthesize(
        "production",
        [rel(build_root / "production" / "DitDah32.sv"), rel(build_root / "production" / "DitDah32Gpr.sv")],
        out_dir,
    )
    jtag = synthesize(
        "jtag",
        [
            rel(build_root / "jtag_only" / "DitDah32.sv"),
            rel(build_root / "jtag_only" / "DitDah32Gpr.sv"),
            rel(build_root / "jtag_only" / "DitDah32DebugModule.sv"),
            rel(build_root / "jtag_only" / "DitDah32JtagDtm.sv"),
        ],
        out_dir,
    )
    baseline = check_baseline(production.get("metrics", {}))
    status = "pass" if all(
        item["status"] == "pass" for item in (production, jtag, baseline)
    ) else "fail"

    overhead = {}
    if production.get("metrics") and jtag.get("metrics"):
        production_cells = production["metrics"]["num_cells"]
        jtag_cells = jtag["metrics"]["num_cells"]
        overhead = {
            "cell_delta": jtag_cells - production_cells,
            "cell_percent": round((jtag_cells - production_cells) * 100 / production_cells, 3),
            "logic_depth_delta": (
                jtag["metrics"]["logic_depth"] - production["metrics"]["logic_depth"]
            ),
        }

    report = {
        "profile": "jtag-ppa-proxy",
        "status": status,
        "production": production,
        "jtag": jtag,
        "production_baseline": baseline,
        "overhead": overhead,
    }
    json_path = out_dir / "jtag_ppa.json"
    md_path = out_dir / "jtag_ppa.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, md_path)
    print(f"jtag-ppa {status}: {rel(json_path)}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
