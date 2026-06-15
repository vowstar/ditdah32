#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT
"""Reproducible RTL benchmark scoring for DitDah32.

Builds CoreMark/Dhrystone for RV32EC, runs the no-trace netlist under a
standalone Verilator harness (bench/sim/ditdah32_bench_tb.sv) against two
memory models, and emits frequency-normalised CoreMark/MHz and DMIPS/MHz.
Cycle counts are exact (simulator) between the in-program timing markers.
Scores are RTL cycle-accurate, not EEMBC-certified.
"""

import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# CoreMark performance-run seeds (validatable CRC at TOTAL_DATA_SIZE=2000).
COREMARK_SEEDS = (0, 0, 0x66)
COREMARK_TOTAL_DATA_SIZE = 2000

# (name, read wait-states, write wait-states, human description)
MEMORY_MODELS = [
    ("tcm_0ws", 0, 0, "0 wait-state tightly-coupled SRAM (intrinsic core)"),
    ("axi_2ws", 2, 2, "AXI-Lite with 2 read + 2 write wait-states"),
]

BENCH_MAGIC = 0xDD32BEEF
BENCH_IDS = {"coremark": 1, "dhrystone": 2}


def run(cmd, cwd=REPO_ROOT, **kw):
    subprocess.run(cmd, cwd=cwd, check=True, **kw)


def bin_to_hex(bin_path, hex_path):
    data = bin_path.read_bytes()
    data += b"\x00" * ((-len(data)) % 4)
    words = struct.unpack("<%dI" % (len(data) // 4), data)
    hex_path.write_text("\n".join("%08x" % w for w in words) + "\n", encoding="utf-8")


def build_benchmarks(out_dir, coremark_iterations, dhrystone_runs):
    run([
        sys.executable, "scripts/build_benchmarks.py",
        "--out-dir", str(out_dir),
        "--coremark-iterations", str(coremark_iterations),
        "--coremark-seed1", str(COREMARK_SEEDS[0]),
        "--coremark-seed2", str(COREMARK_SEEDS[1]),
        "--coremark-seed3", str(COREMARK_SEEDS[2]),
        "--coremark-total-data-size", str(COREMARK_TOTAL_DATA_SIZE),
        "--dhrystone-runs", str(dhrystone_runs),
    ])


def build_sim(netlist, tb, sim_dir):
    sim_dir.mkdir(parents=True, exist_ok=True)
    binary = sim_dir / "obj_dir" / "ditdah32_bench_sim"
    newest_src = max(netlist.stat().st_mtime, tb.stat().st_mtime)
    if binary.exists() and binary.stat().st_mtime >= newest_src:
        return binary
    run([
        "verilator", "--binary", "--timing", "-j", "0",
        "-Wno-SELRANGE", "-Wno-WIDTH", "-Wno-BLKANDNBLK", "-Wno-MINTYPMAXDLY",
        "-Wno-CASEINCOMPLETE", "-Wno-UNOPTFLAT", "--bbox-unsup", "-Wno-fatal",
        "--top-module", "ditdah32_bench_tb", "-o", "ditdah32_bench_sim",
        str(netlist), str(tb),
    ], cwd=sim_dir)
    if not binary.exists():
        raise SystemExit(f"verilator did not produce {binary}")
    return binary


def run_sim(binary, hex_path, manifest, read_latency, write_latency, max_cycles):
    out = subprocess.check_output([
        str(binary),
        f"+image={hex_path}",
        f"+result_addr={manifest['result_addr']}",
        f"+timing_addr={manifest['timing_addr']}",
        f"+read_latency={read_latency}",
        f"+write_latency={write_latency}",
        f"+max_cycles={max_cycles}",
    ], text=True)
    result, timing = None, None
    for line in out.splitlines():
        if line.startswith("BENCH_RESULT"):
            result = [int(x) for x in line.split()[1:]]
        elif line.startswith("BENCH_TIMING"):
            timing = dict(kv.split("=") for kv in line.split()[1:])
        elif line.startswith("FATAL"):
            raise SystemExit(f"sim: {line}")
    if result is None or timing is None:
        raise SystemExit(f"sim produced no result:\n{out}")
    return result, {k: int(v) for k, v in timing.items()}


def score_one(name, manifest, result, timing, freq_mhz):
    assert result[0] == BENCH_MAGIC, f"{name}: bad magic {result[0]:#x}"
    assert result[1] == BENCH_IDS[name], f"{name}: bad id {result[1]}"
    assert result[2] == 0, f"{name}: nonzero status, result={result}"
    if name == "coremark":
        assert result[5] == 1, f"{name}: CoreMark CRC not validated, result={result}"
        assert result[6] == 0, f"{name}: CoreMark reported errors, result={result}"
    assert timing["have_start"] and timing["have_stop"], f"{name}: timing markers missing"

    timed = timing["stop"] - timing["start"]
    assert timed > 0, f"{name}: nonpositive timed cycles"
    work = result[3]
    per_mhz = work * 1_000_000.0 / timed
    entry = {
        "work_units": work,
        "timed_cycles": timed,
        "cycles_to_trap": timing["total"],
        "cycles_per_work_unit": timed / work,
    }
    if name == "coremark":
        entry["coremark_per_mhz"] = per_mhz
        entry["coremark_per_second"] = per_mhz * freq_mhz
    else:
        entry["dhrystones_per_second"] = per_mhz * freq_mhz
        entry["dmips"] = per_mhz * freq_mhz / 1757.0
        entry["dmips_per_mhz"] = per_mhz / 1757.0
    return entry


def write_markdown(path, report):
    rows = []
    for model in report["memory_models"]:
        cm = report["results"][model["name"]]["coremark"]
        dh = report["results"][model["name"]]["dhrystone"]
        rows.append(
            f"| {model['description']} | {cm['coremark_per_mhz']:.3f} | "
            f"{dh['dmips_per_mhz']:.3f} |"
        )
    lines = [
        "# DitDah32 RTL benchmark scores",
        "",
        "RTL cycle-accurate, frequency-normalised. Not EEMBC-certified.",
        "",
        f"- ISA/ABI: `{report['march']}` / `{report['mabi']}` (no hardware mul/div)",
        f"- CoreMark: {report['coremark_iterations']} iterations, seeds "
        f"{report['coremark_seeds']}, TOTAL_DATA_SIZE={report['coremark_total_data_size']}",
        f"- Dhrystone: {report['dhrystone_runs']} runs",
        f"- Toolchain flags: `{report['cflags']}`",
        "",
        "| Memory model | CoreMark/MHz | DMIPS/MHz |",
        "| --- | ---: | ---: |",
        *rows,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bench-dir", type=Path, default=REPO_ROOT / "result" / "bench-score")
    p.add_argument("--netlist", type=Path, default=REPO_ROOT / "result" / "DitDah32.sv")
    p.add_argument("--coremark-iterations", type=int, default=200)
    p.add_argument("--dhrystone-runs", type=int, default=100000)
    p.add_argument("--frequency-mhz", type=float, default=100.0)
    p.add_argument("--max-cycles", type=int, default=4_000_000_000)
    p.add_argument("--skip-build-bench", action="store_true")
    args = p.parse_args()

    if not args.netlist.exists():
        raise SystemExit(f"missing {args.netlist}; run build-ditdah32 first")
    if "trace_" in args.netlist.read_text(encoding="utf-8"):
        raise SystemExit(f"{args.netlist} has trace ports; score the no-trace netlist")

    bench_dir = args.bench_dir
    if not args.skip_build_bench:
        build_benchmarks(bench_dir, args.coremark_iterations, args.dhrystone_runs)

    tb = REPO_ROOT / "bench" / "sim" / "ditdah32_bench_tb.sv"
    sim_dir = bench_dir / "sim"
    binary = build_sim(args.netlist, tb, sim_dir)

    manifests, hexes = {}, {}
    for name in BENCH_IDS:
        manifests[name] = json.loads((bench_dir / name / f"{name}.manifest.json").read_text())
        hexes[name] = sim_dir / f"{name}.hex"
        bin_to_hex(REPO_ROOT / manifests[name]["bin"], hexes[name])

    results = {}
    for model_name, rlat, wlat, _desc in MEMORY_MODELS:
        results[model_name] = {}
        for name in BENCH_IDS:
            result, timing = run_sim(
                binary, hexes[name], manifests[name], rlat, wlat, args.max_cycles)
            results[model_name][name] = score_one(
                name, manifests[name], result, timing, args.frequency_mhz)
            s = results[model_name][name]
            key = "coremark_per_mhz" if name == "coremark" else "dmips_per_mhz"
            print(f"[{model_name}] {name}: {s[key]:.4f} "
                  f"{'CoreMark/MHz' if name == 'coremark' else 'DMIPS/MHz'} "
                  f"({s['timed_cycles']} cycles)")

    report = {
        "certification_status": "rtl_cycle_accurate_not_eembc_certified",
        "march": "rv32ec",
        "mabi": "ilp32e",
        "cflags": " ".join(manifests["coremark"]["cflags"]),
        "frequency_mhz": args.frequency_mhz,
        "coremark_iterations": args.coremark_iterations,
        "coremark_seeds": list(COREMARK_SEEDS),
        "coremark_total_data_size": COREMARK_TOTAL_DATA_SIZE,
        "dhrystone_runs": args.dhrystone_runs,
        "memory_models": [
            {"name": n, "read_wait_states": r, "write_wait_states": w, "description": d}
            for n, r, w, d in MEMORY_MODELS
        ],
        "results": results,
    }
    out_json = bench_dir / "benchmark_scores.json"
    out_md = bench_dir / "benchmark_scores.md"
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(out_md, report)
    print(f"wrote {out_json.relative_to(REPO_ROOT)} and {out_md.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
