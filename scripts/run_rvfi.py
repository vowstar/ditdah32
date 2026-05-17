#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def rel(path):
    return str(path.relative_to(REPO_ROOT))


def run(cmd, log_path, cwd=REPO_ROOT):
    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return {
        "command": cmd,
        "duration_seconds": round(time.monotonic() - start, 3),
        "log": rel(log_path),
        "returncode": completed.returncode,
        "status": "pass" if completed.returncode == 0 else "fail",
    }


def capture(cmd, log_path, cwd=REPO_ROOT):
    start = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        log_file.write(completed.stdout)
    return {
        "command": cmd,
        "duration_seconds": round(time.monotonic() - start, 3),
        "log": rel(log_path),
        "returncode": completed.returncode,
        "status": "pass" if completed.returncode == 0 else "fail",
        "stdout": completed.stdout.strip(),
    }


def command_probe(command):
    path = shutil.which(command)
    return {
        "command": command,
        "path": path,
        "available": path is not None,
    }


def make_writable(path):
    if not path.exists():
        return
    for item in path.rglob("*"):
        if item.is_symlink():
            continue
        mode = item.stat().st_mode
        if item.is_dir():
            item.chmod(mode | 0o700)
        else:
            item.chmod(mode | 0o600)
    if not path.is_symlink():
        path.chmod(path.stat().st_mode | 0o700)


def copy_riscv_formal_suite(source, destination):
    make_writable(destination)
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / "checks", destination / "checks", symlinks=True)
    shutil.copytree(source / "insns", destination / "insns", symlinks=True)
    (destination / "cores").mkdir(parents=True, exist_ok=True)
    make_writable(destination)


def collect_check_statuses(checks_dir):
    statuses = []
    for status_file in sorted(checks_dir.glob("*/status")):
        check_name = status_file.parent.name
        text = status_file.read_text(encoding="utf-8", errors="replace").strip()
        statuses.append(
            {
                "check": check_name,
                "status_file": rel(status_file),
                "status": text,
            }
        )
    return statuses


WFI_WAKE_SBY_TEMPLATE = """[options]
mode bmc
expect pass,fail
append 0
depth {depth_plus}
skip {depth}

[engines]
smtbmc z3

[script]
read -sv wfi_wake_ch0.sv {wrapper_sv} {dut_sv}
prep -flatten -nordff -top rvfi_testbench
chformal -early

[files]
{macros_vh}
{channel_sv}
{testbench_sv}
{checker_sv}

[file defines.sv]
`define RISCV_FORMAL
`define RISCV_FORMAL_NRET 1
`define RISCV_FORMAL_XLEN 32
`define RISCV_FORMAL_ILEN 32
`define RISCV_FORMAL_CHECKER rvfi_cover_check
`define RISCV_FORMAL_RESET_CYCLES 1
`define RISCV_FORMAL_CHECK_CYCLE {depth}
`define YOSYS
`define RISCV_FORMAL_ALIGNED_MEM
`define RISCV_FORMAL_VALIDADDR(addr) 1'b1
`define DITDAH32_RVFI_ENABLE_IRQ
`define DITDAH32_RVFI_WFI_WAKE_CHECK
`include "rvfi_macros.vh"

[file wfi_wake_ch0.sv]
`include "defines.sv"
`include "rvfi_channel.sv"
`include "rvfi_testbench.sv"
`include "rvfi_cover_check.sv"

[file cover_stmts.vh]
always @* if (!reset) cover (1'b1);
"""


def run_wfi_wake_suite(core_dir, source, logs_dir):
    """Run the WFI bounded-wake proof outside the genchecks pipeline.

    The proof relies on a counter and assertion inside formal/riscv_formal/
    ditdah32/wrapper.sv guarded by DITDAH32_RVFI_WFI_WAKE_CHECK. genchecks has
    no built-in template for this property, so we emit a hand-rolled SBY file
    that elaborates the wrapper under symbolic IRQ inputs and runs BMC to
    sufficient depth for the in-wrapper invariant to be checked.
    """
    suite = {
        "name": "riscv_formal_liveness_wfi_wake",
        "config": "wfi_wake.sby",
        "checks_dir": rel(core_dir / "checks_wfi_wake"),
        "property_groups": ["wfi_wake"],
        "status": "fail",
    }
    bound = 8
    depth = bound + 4
    sby_dir = core_dir / "checks_wfi_wake"
    if sby_dir.exists():
        make_writable(sby_dir)
        shutil.rmtree(sby_dir, ignore_errors=True)
    sby_dir.mkdir(parents=True, exist_ok=True)
    checks_root = source / "checks"
    sby_text = WFI_WAKE_SBY_TEMPLATE.format(
        depth=depth,
        depth_plus=depth + 1,
        wrapper_sv=str((core_dir / "wrapper.sv").resolve()),
        dut_sv=str((core_dir / "DitDah32.sv").resolve()),
        macros_vh=str((checks_root / "rvfi_macros.vh").resolve()),
        channel_sv=str((checks_root / "rvfi_channel.sv").resolve()),
        testbench_sv=str((checks_root / "rvfi_testbench.sv").resolve()),
        checker_sv=str((checks_root / "rvfi_cover_check.sv").resolve()),
    )
    sby_path = sby_dir / "wfi_wake_ch0.sby"
    sby_path.write_text(sby_text, encoding="utf-8")
    suite["generated_checks"] = ["wfi_wake_ch0"]
    sby_step = run(
        ["sby", "-f", "-d", "wfi_wake_ch0", str(sby_path)],
        logs_dir / "riscv_formal_liveness_wfi_wake_sby.log",
        cwd=sby_dir,
    )
    suite["sby"] = sby_step
    status_path = sby_dir / "wfi_wake_ch0" / "status"
    if status_path.exists():
        status_text = status_path.read_text(encoding="utf-8", errors="replace").strip()
        suite["check_statuses"] = [
            {
                "check": "wfi_wake_ch0",
                "status_file": rel(status_path),
                "status": status_text,
            }
        ]
        if status_text.upper().startswith(("PASS", "DONE")) and sby_step["status"] == "pass":
            suite["status"] = "pass"
        else:
            suite["reason"] = f"wfi_wake_ch0 status: {status_text}"
    else:
        suite["check_statuses"] = []
        suite["reason"] = "wfi_wake_ch0 did not produce a status file."
    return suite


def run_external_riscv_formal(out_dir, logs_dir):
    probe = command_probe("riscv-formal")
    step = {
        "name": "external_riscv_formal_suite",
        "status": "missing",
        "tool": probe,
        "property_groups": [
            "pc_fwd",
            "pc_bwd",
            "reg",
            "csr_selected",
            "csr_state_subset",
            "unique",
            "causal",
            "causal_io",
            "causal_mem",
            "bus_imem",
            "bus_dmem",
            "bus_dmem_io_read",
            "bus_dmem_io_write",
            "bus_dmem_io_order",
            "fault",
            "bus_dmem_fault",
            "bus_imem_fault",
            "interrupt_entry_shape",
            "liveness_bounded",
            "wfi_wake",
            "hang",
            "ill",
            "cover",
        ],
        "disabled_property_groups": {
            "instruction_semantics": "The pinned riscv-formal suite has no RV32E instruction model list for isa rv32ec.",
            "csr_full": "CSR instruction checks (csrw_check) are enabled for the writable M-mode CSRs mstatus, mie, mtvec, mscratch, mepc, mcause, and mtval, alongside the CSR state subset for reserved-zero and read-only constant fields; read-only illegal-write trap behavior and full trap-entry CSR side effects remain staged for a future custom SVA layer.",
            "interrupt_full_csr_side_effects": "The interrupt-entry RVFI shape suite is enabled; full interrupt CSR side-effect and interrupt-fairness proofs remain staged.",
        },
    }
    if not probe["available"]:
        step["reason"] = "riscv-formal command is not available in PATH."
        return step

    path_result = capture(["riscv-formal", "--path"], logs_dir / "riscv_formal_path.log")
    step["path_probe"] = {key: value for key, value in path_result.items() if key != "stdout"}
    if path_result["status"] != "pass":
        step["status"] = "fail"
        step["reason"] = "riscv-formal --path failed."
        return step

    source = Path(path_result["stdout"].splitlines()[-1]).resolve()
    if not (source / "checks" / "genchecks.py").exists():
        step["status"] = "fail"
        step["source_path"] = str(source)
        step["reason"] = "riscv-formal source path does not contain checks/genchecks.py."
        return step

    work_root = out_dir / "riscv-formal"
    core_dir = work_root / "cores" / "ditdah32"
    copy_riscv_formal_suite(source, work_root)
    core_dir.mkdir(parents=True, exist_ok=True)

    config_dir = REPO_ROOT / "formal" / "riscv_formal" / "ditdah32"
    shutil.copy2(config_dir / "checks.cfg", core_dir / "checks.cfg")
    shutil.copy2(config_dir / "checks_bus.cfg", core_dir / "checks_bus.cfg")
    shutil.copy2(config_dir / "checks_csr.cfg", core_dir / "checks_csr.cfg")
    shutil.copy2(config_dir / "checks_csr_state.cfg", core_dir / "checks_csr_state.cfg")
    shutil.copy2(config_dir / "checks_liveness.cfg", core_dir / "checks_liveness.cfg")
    shutil.copy2(config_dir / "checks_order.cfg", core_dir / "checks_order.cfg")
    shutil.copy2(config_dir / "checks_fault.cfg", core_dir / "checks_fault.cfg")
    shutil.copy2(config_dir / "checks_interrupt.cfg", core_dir / "checks_interrupt.cfg")
    shutil.copy2(config_dir / "wrapper.sv", core_dir / "wrapper.sv")
    shutil.copy2(REPO_ROOT / "result" / "DitDah32.sv", core_dir / "DitDah32.sv")

    step["source_path"] = str(source)
    step["work_root"] = rel(work_root)
    step["core_dir"] = rel(core_dir)

    def run_config(config_name, checks_name, log_prefix, property_groups):
        gen_command = ["riscv-formal", "genchecks"]
        if config_name != "checks":
            gen_command.append(config_name)
        gen_step = run(gen_command, logs_dir / f"{log_prefix}_genchecks.log", cwd=core_dir)
        suite = {
            "name": log_prefix,
            "config": f"{config_name}.cfg",
            "checks_dir": rel(core_dir / checks_name),
            "property_groups": property_groups,
            "genchecks": gen_step,
            "status": "fail",
        }
        if gen_step["status"] != "pass":
            suite["reason"] = "riscv-formal genchecks failed."
            return suite

        checks_dir = core_dir / checks_name
        generated_sby = sorted(checks_dir.glob("*.sby"))
        make_step = run(["make", "-C", checks_name, "-j1"], logs_dir / f"{log_prefix}_make.log", cwd=core_dir)
        statuses = collect_check_statuses(checks_dir)
        failed_checks = [
            check for check in statuses
            if not check["status"].upper().startswith(("PASS", "DONE"))
        ]
        suite["make"] = make_step
        suite["generated_checks"] = [path.stem for path in generated_sby]
        suite["check_statuses"] = statuses

        if make_step["status"] == "pass" and generated_sby and not failed_checks:
            suite["status"] = "pass"
        elif not generated_sby:
            suite["reason"] = "No riscv-formal checks were generated."
        elif failed_checks:
            suite["reason"] = "One or more generated riscv-formal checks did not pass."
        else:
            suite["reason"] = "Generated riscv-formal make step failed."
        return suite

    suites = [
        run_config(
            "checks",
            "checks",
            "riscv_formal_consistency",
            ["pc_fwd", "pc_bwd", "reg", "unique", "causal_mem", "cover"],
        ),
        run_config(
            "checks_bus",
            "checks_bus",
            "riscv_formal_bus_nonfault",
            ["bus_imem", "bus_dmem", "bus_dmem_io_read", "bus_dmem_io_write", "bus_dmem_io_order"],
        ),
        run_config(
            "checks_csr",
            "checks_csr",
            "riscv_formal_csr_selected",
            ["csrw_selected"],
        ),
        run_config(
            "checks_csr_state",
            "checks_csr_state",
            "riscv_formal_csr_state_subset",
            ["csr_state_subset"],
        ),
        run_config(
            "checks_liveness",
            "checks_liveness",
            "riscv_formal_liveness_bounded",
            ["liveness_bounded"],
        ),
        run_wfi_wake_suite(core_dir, source, logs_dir),
        run_config(
            "checks_interrupt",
            "checks_interrupt",
            "riscv_formal_interrupt_entry_shape",
            ["interrupt_entry_shape"],
        ),
        run_config(
            "checks_order",
            "checks_order",
            "riscv_formal_order_and_illegal",
            ["causal", "causal_io", "hang", "ill"],
        ),
        run_config(
            "checks_fault",
            "checks_fault",
            "riscv_formal_memory_fault",
            ["fault", "bus_dmem_fault", "bus_imem_fault"],
        ),
    ]
    step["suites"] = suites
    step["generated_checks"] = [
        check
        for suite in suites
        for check in suite.get("generated_checks", [])
    ]
    step["check_statuses"] = [
        {**check, "suite": suite["name"]}
        for suite in suites
        for check in suite.get("check_statuses", [])
    ]

    failed_suites = [suite for suite in suites if suite["status"] != "pass"]
    if suites and not failed_suites:
        step["status"] = "pass"
    else:
        step["status"] = "fail"
        step["reason"] = "One or more riscv-formal suites did not pass."
    return step


def main():
    parser = argparse.ArgumentParser(description="Run DitDah32 standard RVFI verification gate")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "formal" / "rvfi")
    parser.add_argument("--depth", type=int, default=24)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="return success when local RVFI-lite passes but external riscv-formal is unavailable",
    )
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    steps = []
    steps.append(
        run(
            [
                "python3",
                "scripts/run_rvfi_lite.py",
                "--depth",
                str(args.depth),
                "--out-dir",
                "result/formal/rvfi_lite",
            ],
            logs_dir / "rvfi_lite.log",
        )
    )

    external_step = run_external_riscv_formal(out_dir, logs_dir)
    steps.append(external_step)

    lite_pass = steps[0]["status"] == "pass"
    external_pass = external_step["status"] == "pass"
    status = "pass" if lite_pass and external_pass else "fail"
    if lite_pass and not external_pass and args.allow_partial:
        status = "partial"
    if not lite_pass:
        status = "fail"

    report = {
        "depth": args.depth,
        "status": status,
        "profile": "standard-rvfi",
        "equivalence_class": "external_riscv_formal_consistency_subset",
        "steps": steps,
        "limitations": [
            "This is a passing external riscv-formal consistency subset, not full instruction-semantic RVFI closure.",
            "The enabled external property groups are pc_fwd, pc_bwd, reg, CSR instruction checks for all writable M-mode CSRs, CSR state subset checks, unique, causal, causal_io, causal_mem, non-faulting RVFI_BUS instruction/data/IO read/write/order checks, the fault/bus_dmem_fault/bus_imem_fault memory-fault checks under the recoverable AXI access-fault contract, interrupt entry shape, bounded liveness for non-WFI retires, bounded WFI wake under MIE-enabled IRQs, hang, ill, and cover.",
            "Instruction-semantic checks are disabled because the pinned riscv-formal suite has no RV32E instruction model list for isa rv32ec.",
            "Instruction-semantic, arbitrary WARL CSR writes, read-only illegal-write behavior, trap-entry CSR side effects, and full interrupt CSR side-effect/fairness remain disabled until DitDah32 exposes the remaining RVFI fields and environment contracts.",
        ],
    }
    report_path = out_dir / "rvfi.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"rvfi {status}: {report_path.relative_to(REPO_ROOT)}")

    if status == "pass" or (args.allow_partial and status == "partial"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
