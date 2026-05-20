#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


COMMON_CFLAGS = [
    "-march=rv32ec",
    "-mabi=ilp32e",
    "-mcmodel=medlow",
    "-mstrict-align",
    "-msmall-data-limit=0",
    "-Os",
    "-ffreestanding",
    "-fno-builtin",
    "-fno-common",
    "-fno-pic",
    "-fno-asynchronous-unwind-tables",
    "-fno-unwind-tables",
    "-nostartfiles",
    "-nostdlib",
    "-Wall",
    "-Wextra",
]


def tool(prefix, name):
    candidate = os.environ.get(f"RISCV_{name.upper()}")
    if candidate:
        return candidate
    path = shutil.which(f"{prefix}{name}")
    if path:
        return path
    raise SystemExit(f"missing RISC-V tool: {prefix}{name}")


def run(cmd):
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def read_symbol(nm, elf, name):
    output = subprocess.check_output([nm, "-g", str(elf)], cwd=REPO_ROOT, text=True)
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[2] == name:
            return int(fields[0], 16)
    raise SystemExit(f"symbol {name} not found in {elf}")


def binary_size(path):
    return path.stat().st_size


def build_one(name, sources, extra_cflags, defines, args):
    out_dir = args.out_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)

    gcc = tool(args.prefix, "gcc")
    objcopy = tool(args.prefix, "objcopy")
    objdump = tool(args.prefix, "objdump")
    nm = tool(args.prefix, "nm")

    elf = out_dir / f"{name}.elf"
    binary = out_dir / f"{name}.bin"
    disasm = out_dir / f"{name}.disasm"
    manifest = out_dir / f"{name}.manifest.json"

    cmd = [
        gcc,
        *COMMON_CFLAGS,
        *extra_cflags,
        "-Ibench/common",
        "-Ibench/coremark/ditdah32",
        "-Ibench/coremark/upstream",
        "-Ibench/dhrystone/ditdah32",
        "-Ibench/dhrystone/upstream",
        *[f"-D{key}={value}" for key, value in defines.items()],
        "-Wl,-T,bench/common/link.ld",
        "-Wl,-Map," + str(out_dir / f"{name}.map"),
        "-o",
        str(elf),
        "bench/common/start.S",
        "bench/common/runtime.c",
        "bench/common/soft_arith.c",
        *sources,
    ]
    run(cmd)
    run([objcopy, "-O", "binary", str(elf), str(binary)])

    with disasm.open("w", encoding="utf-8") as disasm_file:
        subprocess.run([objdump, "-d", str(elf)], cwd=REPO_ROOT, check=True, stdout=disasm_file)

    result_addr = read_symbol(nm, elf, "ditdah32_bench_result")
    timing_addr = read_symbol(nm, elf, "ditdah32_bench_timing_state")
    image_end = read_symbol(nm, elf, "__image_end")

    manifest.write_text(
        json.dumps(
            {
                "name": name,
                "elf": str(elf.relative_to(REPO_ROOT)),
                "bin": str(binary.relative_to(REPO_ROOT)),
                "disasm": str(disasm.relative_to(REPO_ROOT)),
                "result_addr": result_addr,
                "timing_addr": timing_addr,
                "image_end": image_end,
                "binary_size": binary_size(binary),
                "memory_size": args.memory_size,
                "cflags": COMMON_CFLAGS + extra_cflags,
                "defines": defines,
                "sources": sources,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="Build DitDah32 RV32EC benchmark images")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "bench")
    parser.add_argument("--prefix", default=os.environ.get("RISCV_PREFIX", "riscv32-unknown-elf-"))
    parser.add_argument("--coremark-iterations", type=int, default=1)
    parser.add_argument("--coremark-total-data-size", type=int, default=1200)
    parser.add_argument("--coremark-seed1", type=int, default=8)
    parser.add_argument("--coremark-seed2", type=int, default=8)
    parser.add_argument("--coremark-seed3", type=int, default=8)
    parser.add_argument("--dhrystone-runs", type=int, default=1)
    parser.add_argument("--memory-size", type=int, default=262144)
    args = parser.parse_args()

    if not args.out_dir.is_absolute():
        args.out_dir = REPO_ROOT / args.out_dir
    args.out_dir.mkdir(parents=True, exist_ok=True)

    build_one(
        "coremark",
        [
            "bench/coremark/ditdah32/core_portme.c",
            "bench/coremark/upstream/core_list_join.c",
            "bench/coremark/upstream/core_main.c",
            "bench/coremark/upstream/core_matrix.c",
            "bench/coremark/upstream/core_state.c",
            "bench/coremark/upstream/core_util.c",
        ],
        ["-std=gnu99"],
        {
            "DITDAH32_COREMARK_ITERATIONS": args.coremark_iterations,
            "DITDAH32_COREMARK_SEED1": args.coremark_seed1,
            "DITDAH32_COREMARK_SEED2": args.coremark_seed2,
            "DITDAH32_COREMARK_SEED3": args.coremark_seed3,
            "TOTAL_DATA_SIZE": args.coremark_total_data_size,
            "main": "ditdah32_main",
        },
        args,
    )

    build_one(
        "dhrystone",
        [
            "bench/dhrystone/ditdah32/main.c",
            "bench/dhrystone/upstream/dhry_1.c",
            "bench/dhrystone/upstream/dhry_2.c",
        ],
        [
            "-std=gnu89",
            "-Wno-implicit-int",
            "-Wno-implicit-function-declaration",
            "-Wno-return-type",
            "-Wno-builtin-declaration-mismatch",
        ],
        {
            "DITDAH32_DHRYSTONE_RUNS": args.dhrystone_runs,
            "main": "dhrystone_upstream_main",
            "printf": "bench_printf",
            "scanf": "bench_scanf",
            "malloc": "bench_malloc",
            "time": "bench_time",
            "TIME": "1",
            "float": "int",
            "HZ": "1",
        },
        args,
    )


if __name__ == "__main__":
    main()
