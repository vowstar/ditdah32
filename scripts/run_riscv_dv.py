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

from rv32ec_model import RV32ECModel


REPO_ROOT = Path(__file__).resolve().parents[1]


LEGAL_REG_NUMS = set(range(16))
ALIAS_TO_REG = {
    "zero": 0,
    "ra": 1,
    "sp": 2,
    "gp": 3,
    "tp": 4,
    "t0": 5,
    "t1": 6,
    "t2": 7,
    "s0": 8,
    "fp": 8,
    "s1": 9,
    "a0": 10,
    "a1": 11,
    "a2": 12,
    "a3": 13,
    "a4": 14,
    "a5": 15,
    "a6": 16,
    "a7": 17,
    "s2": 18,
    "s3": 19,
    "s4": 20,
    "s5": 21,
    "s6": 22,
    "s7": 23,
    "s8": 24,
    "s9": 25,
    "s10": 26,
    "s11": 27,
    "t3": 28,
    "t4": 29,
    "t5": 30,
    "t6": 31,
}
REG_TOKEN_RE = re.compile(
    r"\b("
    r"x(?:[0-9]|[12][0-9]|3[01])|"
    r"zero|ra|sp|gp|tp|fp|"
    r"t[0-6]|s(?:10|11|[0-9])|a[0-7]"
    r")\b"
)
LABEL_RE = re.compile(r"^\s*(?:[A-Za-z_.$][A-Za-z0-9_.$]*|\d+):\s*")
FORBIDDEN_MNEMONIC_RE = re.compile(
    r"^(?:"
    r"csr|"
    r"mul|mulh|mulhsu|mulhu|div|divu|rem|remu|"
    r"lr(?:\.|$)|sc(?:\.|$)|amo|"
    r"flw|fsw|fld|fsd|flq|fsq|fadd|fsub|fmul|fdiv|fsqrt|fsgnj|fmin|fmax|"
    r"fcvt|fmv|fclass|feq|flt|fle|"
    r"c\.fl|c\.fs|"
    r"fence|mret|sret|uret|dret|wfi|ecall"
    r")"
)


def rel(path):
    return str(path.relative_to(REPO_ROOT))


def command_probe(command):
    path = shutil.which(command)
    return {
        "command": command,
        "path": path,
        "available": path is not None,
    }


def command_output(command):
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "output": completed.stdout.strip().splitlines()[:20],
    }


def load_yaml(path):
    with path.open("r", encoding="utf-8") as yaml_file:
        return yaml.safe_load(yaml_file)


def strip_comment(line):
    line = line.split("#", 1)[0]
    line = line.split("//", 1)[0]
    return line.rstrip()


def get_mnemonic(line):
    text = strip_comment(line).strip()
    while True:
        match = LABEL_RE.match(text)
        if not match:
            break
        text = text[match.end():].strip()
    if not text or text.startswith("."):
        return None
    return text.split(None, 1)[0].lower()


def token_to_reg_num(token):
    token = token.lower()
    if token.startswith("x") and token[1:].isdigit():
        return int(token[1:])
    return ALIAS_TO_REG.get(token)


def scan_asm_for_rv32ec(path, max_examples=20):
    illegal_registers = []
    forbidden_mnemonics = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_no, line in enumerate(lines, start=1):
        code = strip_comment(line)
        for match in REG_TOKEN_RE.finditer(code):
            token = match.group(1)
            reg_num = token_to_reg_num(token)
            if reg_num is not None and reg_num not in LEGAL_REG_NUMS:
                illegal_registers.append({
                    "line": line_no,
                    "token": token,
                    "register": f"x{reg_num}",
                    "text": line.strip(),
                })
        mnemonic = get_mnemonic(line)
        if mnemonic and FORBIDDEN_MNEMONIC_RE.match(mnemonic):
            forbidden_mnemonics.append({
                "line": line_no,
                "mnemonic": mnemonic,
                "text": line.strip(),
            })

    violations = []
    if illegal_registers:
        violations.append({
            "class": "rv32e_illegal_register",
            "count": len(illegal_registers),
            "examples": illegal_registers[:max_examples],
        })
    if forbidden_mnemonics:
        violations.append({
            "class": "unsupported_instruction_for_legal_rv32ec_random_profile",
            "count": len(forbidden_mnemonics),
            "examples": forbidden_mnemonics[:max_examples],
        })

    return {
        "path": rel(path),
        "status": "pass" if not violations else "fail",
        "line_count": len(lines),
        "violations": violations,
    }


def run_command(command, log_path, timeout_seconds):
    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log_file:
        try:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout_seconds,
            )
            return {
                "command": command,
                "duration_seconds": round(time.monotonic() - start, 3),
                "log": rel(log_path),
                "returncode": completed.returncode,
                "status": "pass" if completed.returncode == 0 else "fail",
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "duration_seconds": round(time.monotonic() - start, 3),
                "log": rel(log_path),
                "returncode": None,
                "status": "timeout",
            }


def write_hex(path, words):
    path.write_text("\n".join(f"0x{word:08x}" for word in words) + "\n", encoding="utf-8")


def write_trace(path, trace):
    path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in trace), encoding="utf-8")


def binary_to_words(path):
    data = bytearray(path.read_bytes())
    while len(data) % 4:
        data.append(0)
    return [
        int.from_bytes(data[index:index + 4], "little")
        for index in range(0, len(data), 4)
    ]


def run_reference_model(words, max_steps):
    model = RV32ECModel()
    model.load_words(words)
    model.run(max_steps)
    if not model.halted and not model.sleeping:
        return {
            "status": "fail",
            "trace": model.trace,
            "reason": f"reference model did not halt or sleep within {max_steps} steps",
        }
    return {
        "status": "pass",
        "trace": model.trace,
        "halted": model.halted,
        "sleeping": model.sleeping,
        "trace_items": len(model.trace),
    }


def write_toolchain_files(build_dir):
    include_dir = build_dir / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    (include_dir / "user_define.h").write_text("", encoding="utf-8")
    (include_dir / "user_init.s").write_text("", encoding="utf-8")
    linker_script = build_dir / "ditdah32_riscv_dv.ld"
    linker_script.write_text(
        "\n".join(
            [
                "OUTPUT_ARCH(riscv)",
                "ENTRY(_start)",
                "SECTIONS",
                "{",
                "  . = 0x0;",
                "  .text : { *(.text*) }",
                "  . = ALIGN(4);",
                "  .rodata : { *(.rodata*) }",
                "  . = ALIGN(4);",
                "  .data : { *(.data*) *(.sdata*) }",
                "  . = ALIGN(4);",
                "  .user_stack : { *(.user_stack*) }",
                "  . = ALIGN(4);",
                "  .bss : { *(.bss*) *(COMMON) }",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return include_dir, linker_script


def compile_and_trace_asm(asm_path, name, args):
    gcc = shutil.which("riscv32-none-elf-gcc")
    objcopy = shutil.which("riscv32-none-elf-objcopy")
    if gcc is None or objcopy is None:
        return {
            "name": name,
            "asm": rel(asm_path),
            "status": "fail",
            "reason": "RISC-V embedded GCC or objcopy is unavailable.",
            "gcc_available": gcc is not None,
            "objcopy_available": objcopy is not None,
        }

    build_dir = args.out_dir / "build" / name
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    include_dir, linker_script = write_toolchain_files(build_dir)
    logs_dir = args.out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    elf_path = build_dir / f"{name}.elf"
    bin_path = build_dir / f"{name}.bin"
    hex_path = args.isa_out_dir / f"{name}.hex"
    trace_path = args.isa_out_dir / f"{name}.trace.jsonl"

    compile_result = run_command(
        [
            gcc,
            "-nostdlib",
            "-nostartfiles",
            "-march=rv32ec",
            "-mabi=ilp32e",
            "-Wl,--no-relax",
            "-Wl,--build-id=none",
            f"-T{linker_script}",
            f"-I{include_dir}",
            "-o",
            str(elf_path),
            str(asm_path),
        ],
        logs_dir / f"{name}_compile.log",
        args.timeout_seconds,
    )
    if compile_result["status"] != "pass":
        return {
            "name": name,
            "asm": rel(asm_path),
            "status": "fail",
            "compile": compile_result,
        }

    objcopy_result = run_command(
        [objcopy, "-O", "binary", str(elf_path), str(bin_path)],
        logs_dir / f"{name}_objcopy.log",
        args.timeout_seconds,
    )
    if objcopy_result["status"] != "pass":
        return {
            "name": name,
            "asm": rel(asm_path),
            "status": "fail",
            "compile": compile_result,
            "objcopy": objcopy_result,
        }

    words = binary_to_words(bin_path)
    reference = run_reference_model(words, args.max_reference_steps)
    if reference["status"] == "pass":
        write_hex(hex_path, words)
        write_trace(trace_path, reference["trace"])
    return {
        "name": name,
        "asm": rel(asm_path),
        "status": "pass" if reference["status"] == "pass" else "fail",
        "compile": compile_result,
        "objcopy": objcopy_result,
        "hex": rel(hex_path) if hex_path.exists() else None,
        "trace": rel(trace_path) if trace_path.exists() else None,
        "word_count": len(words),
        "reference": {key: value for key, value in reference.items() if key != "trace"},
    }


def compile_and_trace_generation_steps(args, generation_steps):
    args.isa_out_dir.mkdir(parents=True, exist_ok=True)
    for old_artifact in args.isa_out_dir.glob("*"):
        if old_artifact.is_file():
            old_artifact.unlink()
    artifacts = []
    for step in generation_steps:
        if step.get("status") != "pass":
            continue
        seed = step["seed"]
        for index, asm_file in enumerate(step.get("asm_files", [])):
            asm_path = REPO_ROOT / asm_file
            name = f"{args.target}_seed_{seed}_{index}"
            artifacts.append(compile_and_trace_asm(asm_path, name, args))
    return {
        "name": "compile_and_reference_trace_riscv_dv_artifacts",
        "status": "pass" if artifacts and all(item["status"] == "pass" for item in artifacts) else "fail",
        "isa_dir": rel(args.isa_out_dir),
        "artifacts": artifacts,
    }


def run_rtl_trace_compare(args, compile_step):
    if compile_step["status"] != "pass":
        return {
            "name": "rtl_trace_compare_riscv_dv_artifacts",
            "status": "not_run",
            "reason": "No compiled RISCV-DV artifact set is available.",
        }
    args.rtl_out_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.out_dir / "logs" / "riscv_dv_rtl_trace_compare.log"
    result = run_command(
        [
            "python3",
            "scripts/run_rtl_isa_matrix.py",
            "--isa-dir",
            str(args.isa_out_dir),
            "--out-dir",
            str(args.rtl_out_dir),
        ],
        log_path,
        args.rtl_timeout_seconds,
    )
    return {
        "name": "rtl_trace_compare_riscv_dv_artifacts",
        "status": result["status"],
        "result": result,
        "rtl_out_dir": rel(args.rtl_out_dir),
    }


def run_generator_for_seed(args, seed, generator_command):
    seed_dir = args.out_dir / "generated" / f"seed_{seed}"
    if seed_dir.exists():
        shutil.rmtree(seed_dir)
    seed_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = args.out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    command = [
        generator_command,
        "--target",
        args.target,
        "--custom_target",
        str(args.custom_target),
        "--test",
        args.test,
        "--iterations",
        str(args.iterations),
        "--simulator",
        "pyflow",
        "--steps",
        "gen",
        "--seed",
        str(seed),
        "-o",
        str(seed_dir),
    ]
    run_result = run_command(command, logs_dir / f"riscv_dv_seed_{seed}.log", args.timeout_seconds)
    asm_paths = sorted((seed_dir / "asm_test").glob("*.S")) if (seed_dir / "asm_test").exists() else []
    asm_scans = [scan_asm_for_rv32ec(path) for path in asm_paths]
    scan_status = "pass" if asm_scans and all(scan["status"] == "pass" for scan in asm_scans) else "fail"
    if run_result["status"] != "pass":
        scan_status = "not_run"
    return {
        "name": f"generate_and_scan_seed_{seed}",
        "status": "pass" if run_result["status"] == "pass" and scan_status == "pass" else "fail",
        "seed": seed,
        "output_dir": rel(seed_dir),
        "generator": run_result,
        "asm_files": [rel(path) for path in asm_paths],
        "rv32ec_legality_scan": {
            "status": scan_status,
            "files": asm_scans,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run or audit the DitDah32 RISCV-DV flow")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "test" / "riscv_dv" / "ditdah32_rv32ec.yaml")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "riscv_dv")
    parser.add_argument("--target", default="ditdah32_rv32ec")
    parser.add_argument("--test", default="ditdah32_rv32ec_smoke")
    parser.add_argument("--custom-target", type=Path, default=REPO_ROOT / "test" / "riscv_dv" / "target" / "ditdah32_rv32ec")
    parser.add_argument("--isa-out-dir", type=Path, default=REPO_ROOT / "result" / "riscv_dv" / "isa")
    parser.add_argument("--rtl-out-dir", type=Path, default=REPO_ROOT / "result" / "rtl_trace" / "riscv_dv")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--seed", type=int, action="append", dest="seeds", default=[1])
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--rtl-timeout-seconds", type=int, default=600)
    parser.add_argument("--max-reference-steps", type=int, default=512)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="return success when the flow produces a partial integration report",
    )
    args = parser.parse_args()

    config_path = args.config
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path
    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    args.out_dir = out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    custom_target = args.custom_target
    if not custom_target.is_absolute():
        custom_target = REPO_ROOT / custom_target
    args.custom_target = custom_target
    isa_out_dir = args.isa_out_dir
    if not isa_out_dir.is_absolute():
        isa_out_dir = REPO_ROOT / isa_out_dir
    args.isa_out_dir = isa_out_dir
    rtl_out_dir = args.rtl_out_dir
    if not rtl_out_dir.is_absolute():
        rtl_out_dir = REPO_ROOT / rtl_out_dir
    args.rtl_out_dir = rtl_out_dir

    config = None
    config_error = None
    if config_path.exists():
        try:
            config = load_yaml(config_path)
        except Exception as exc:
            config_error = str(exc)
    else:
        config_error = f"missing config: {config_path}"

    run_py = command_probe("run.py")
    riscv_dv = command_probe("riscv-dv")
    generator_command = "riscv-dv" if riscv_dv["available"] else "run.py"
    generator_available = riscv_dv["available"] or run_py["available"]

    steps = []
    if config is None:
        steps.append({
            "name": "load_ditdah32_rv32ec_config",
            "status": "fail",
            "error": config_error,
        })
    else:
        steps.append({
            "name": "load_ditdah32_rv32ec_config",
            "status": "pass",
            "config": rel(config_path),
            "isa": config.get("isa", {}),
            "disabled_extensions": config.get("disabled_extensions", []),
        })

    if generator_available:
        steps.append({
            "name": "riscv_dv_generator_available",
            "status": "pass",
            "run_py": run_py,
            "riscv_dv": riscv_dv,
            "selected_command": generator_command,
        })
        probe = command_output(["run.py", "--help"]) if run_py["available"] else command_output(["riscv-dv", "--help"])
    else:
        steps.append({
            "name": "riscv_dv_generator_available",
            "status": "missing",
            "run_py": run_py,
            "riscv_dv": riscv_dv,
            "reason": "RISCV-DV is not integrated into the reproducible tool environment.",
        })
        probe = None

    if generator_available and config is not None:
        for seed in args.seeds:
            steps.append(run_generator_for_seed(args, seed, generator_command))

    generation_steps = [step for step in steps if step["name"].startswith("generate_and_scan_seed_")]
    generation_clean = bool(generation_steps) and all(step["status"] == "pass" for step in generation_steps)
    compile_step = None
    rtl_step = None
    if generation_clean:
        compile_step = compile_and_trace_generation_steps(args, generation_steps)
        steps.append(compile_step)
        rtl_step = run_rtl_trace_compare(args, compile_step)
        steps.append(rtl_step)
    compile_clean = compile_step is not None and compile_step["status"] == "pass"
    rtl_clean = rtl_step is not None and rtl_step["status"] == "pass"
    if config is None:
        status = "fail"
    elif not generator_available:
        status = "partial"
    elif not generation_clean:
        status = "partial"
    elif not compile_clean:
        status = "partial"
    elif not rtl_clean:
        status = "partial"
    else:
        status = "pass"

    report = {
        "status": status,
        "profile": "riscv-dv-rv32ec",
        "config": rel(config_path) if config_path.exists() else str(config_path),
        "target": args.target,
        "custom_target": rel(custom_target) if custom_target.exists() else str(custom_target),
        "test": args.test,
        "iterations": args.iterations,
        "seeds": args.seeds,
        "started_unix": int(time.time()),
        "steps": steps,
        "generator_probe": probe,
        "trace_compare": {
            "status": "pass" if rtl_clean else "not_run" if rtl_step is None else rtl_step["status"],
            "reason": None if rtl_clean else "Generated RISCV-DV assembly is not yet fully passing the RTL/reference trace comparator.",
        },
        "limitations": [
            "This is a RISCV-DV integration status report, not a passing generated-program regression.",
            "The generation stage must produce RV32EC-clean assembly before programs are accepted for RTL execution.",
            "A future passing flow must compile accepted programs, run them on RTL, and compare traces against the selected reference model.",
        ],
    }
    report_path = out_dir / "riscv_dv.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"riscv-dv {status}: {report_path.relative_to(REPO_ROOT)}")

    if status == "pass" or (args.allow_partial and status == "partial"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
