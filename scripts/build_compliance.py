#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile compliance tests to two variants: DUT base 0 (raw bin for the
cocotb AXI RAM) and ISS base 0x80000000 (ELF for Sail).
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
COMPLIANCE_ROOT = REPO_ROOT / "test" / "compliance"
TESTS_DIR = COMPLIANCE_ROOT / "tests"
ENV_DIR = COMPLIANCE_ROOT / "env"
LINK_SCRIPT_DUT = ENV_DIR / "link.ld"
LINK_SCRIPT_ISS = ENV_DIR / "link_iss.ld"


def find_tool(prefix: str, name: str) -> str:
    cmd = f"{prefix}{name}"
    path = shutil.which(cmd)
    if path is None:
        raise RuntimeError(f"missing toolchain command: {cmd}")
    return path


def compile_variant(src: Path, work: Path, gcc: str, objcopy: str, link_script: Path, suffix: str) -> dict[str, str]:
    """Compile one .S source against one linker script, producing ELF + bin + hex."""
    name = src.stem
    elf = work / f"{name}{suffix}.elf"
    binp = work / f"{name}{suffix}.bin"
    hexp = work / f"{name}{suffix}.hex"

    cmd = [
        gcc,
        "-march=rv32ec_zicsr",
        "-mabi=ilp32e",
        "-mcmodel=medany",
        "-mno-relax",
        "-nostdlib",
        "-nostartfiles",
        "-fno-pic",
        "-no-pie",
        f"-I{ENV_DIR}",
        f"-T{link_script}",
        "-o",
        str(elf),
        str(src),
    ]
    subprocess.run(cmd, check=True)

    subprocess.run([objcopy, "-O", "binary", str(elf), str(binp)], check=True)

    raw = binp.read_bytes()
    if len(raw) % 4:
        raw = raw + b"\x00" * (4 - (len(raw) % 4))
    words = [int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw), 4)]
    hexp.write_text("\n".join(f"0x{w:08x}" for w in words) + "\n", encoding="utf-8")

    return {
        "elf": str(elf.relative_to(REPO_ROOT)),
        "bin": str(binp.relative_to(REPO_ROOT)),
        "hex": str(hexp.relative_to(REPO_ROOT)),
        "size_bytes": len(raw),
    }


def compile_one(src: Path, out_dir: Path, gcc: str, objcopy: str) -> dict[str, str]:
    name = src.stem
    work = out_dir / name
    work.mkdir(parents=True, exist_ok=True)
    dut = compile_variant(src, work, gcc, objcopy, LINK_SCRIPT_DUT, suffix="")
    iss = compile_variant(src, work, gcc, objcopy, LINK_SCRIPT_ISS, suffix="_iss")
    return {
        "name": name,
        "src": str(src.relative_to(REPO_ROOT)),
        "dut": dut,
        "iss": iss,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="result/compliance/build")
    parser.add_argument("--toolchain-prefix", default=os.environ.get("RISCV_PREFIX", "riscv32-none-elf-"))
    parser.add_argument("--tests-dir", default=str(TESTS_DIR))
    args = parser.parse_args()

    out_dir = (REPO_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = Path(args.tests_dir).resolve()
    sources = sorted(tests_dir.glob("*.S"))
    if not sources:
        print(f"no .S sources found under {tests_dir}", file=sys.stderr)
        return 1

    gcc = find_tool(args.toolchain_prefix, "gcc")
    objcopy = find_tool(args.toolchain_prefix, "objcopy")

    artefacts = []
    for src in sources:
        artefacts.append(compile_one(src, out_dir, gcc, objcopy))

    manifest = out_dir / "compliance_build.json"
    manifest.write_text(
        json.dumps({"status": "pass", "tests": artefacts}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"compliance build pass: {manifest.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
