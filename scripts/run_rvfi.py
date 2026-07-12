#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_slang_so():
    """Locate the yosys-slang plugin (read_slang) provided by the dev shell."""
    slang_so = os.environ.get("SLANG_SO")
    if not slang_so or not Path(slang_so).is_file():
        raise SystemExit(
            "SLANG_SO is not set or does not point to slang.so; run inside "
            "'nix develop' so the yosys-slang plugin is available."
        )
    return slang_so


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
plugin -i {slang_so}
read_slang -I{core_dir} {trace_top_sv} {dut_sv} {dv_sv} {layers_sv} --top ditdah32_trace_top
read -sv {check_basename}.sv {wrapper_sv}
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
{extra_defines}
`include "rvfi_macros.vh"

[file {check_basename}.sv]
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
        check_basename="wfi_wake_ch0",
        extra_defines="`define DITDAH32_RVFI_ENABLE_IRQ\n`define DITDAH32_RVFI_WFI_WAKE_CHECK",
        slang_so=resolve_slang_so(),
        core_dir=str(core_dir.resolve()),
        wrapper_sv=str((core_dir / "wrapper.sv").resolve()),
        trace_top_sv=str((core_dir / "ditdah32_trace_top.sv").resolve()),
        dut_sv=str((core_dir / "DitDah32.sv").resolve()),
        dv_sv=str((core_dir / "DitDah32_DV.sv").resolve()),
        layers_sv=str((core_dir / "layers-DitDah32-DV.sv").resolve()),
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


def run_trap_csr_suite(core_dir, source, logs_dir):
    """Run the trap-entry and mret CSR transition proof."""
    suite = {
        "name": "riscv_formal_trap_csr",
        "config": "trap_csr.sby",
        "checks_dir": rel(core_dir / "checks_trap_csr"),
        "property_groups": [
            "trap_csr_side_effects",
            "trap_entry_mstatus",
            "mret_exit_mstatus",
            "mip_mirror",
            "interrupt_cause_priority",
            "mpie_swap_all_traps",
            "interrupt_full_csr_side_effects",
        ],
        "status": "fail",
    }
    depth = 16
    sby_dir = core_dir / "checks_trap_csr"
    if sby_dir.exists():
        make_writable(sby_dir)
        shutil.rmtree(sby_dir, ignore_errors=True)
    sby_dir.mkdir(parents=True, exist_ok=True)
    checks_root = source / "checks"
    sby_text = WFI_WAKE_SBY_TEMPLATE.format(
        depth=depth,
        depth_plus=depth + 1,
        check_basename="trap_csr_ch0",
        extra_defines="`define DITDAH32_RVFI_ENABLE_IRQ\n`define DITDAH32_RVFI_TRAP_CSR_CHECK",
        slang_so=resolve_slang_so(),
        core_dir=str(core_dir.resolve()),
        wrapper_sv=str((core_dir / "wrapper.sv").resolve()),
        trace_top_sv=str((core_dir / "ditdah32_trace_top.sv").resolve()),
        dut_sv=str((core_dir / "DitDah32.sv").resolve()),
        dv_sv=str((core_dir / "DitDah32_DV.sv").resolve()),
        layers_sv=str((core_dir / "layers-DitDah32-DV.sv").resolve()),
        macros_vh=str((checks_root / "rvfi_macros.vh").resolve()),
        channel_sv=str((checks_root / "rvfi_channel.sv").resolve()),
        testbench_sv=str((checks_root / "rvfi_testbench.sv").resolve()),
        checker_sv=str((checks_root / "rvfi_cover_check.sv").resolve()),
    )
    sby_path = sby_dir / "trap_csr_ch0.sby"
    sby_path.write_text(sby_text, encoding="utf-8")
    suite["generated_checks"] = ["trap_csr_ch0"]
    sby_step = run(
        ["sby", "-f", "-d", "trap_csr_ch0", str(sby_path)],
        logs_dir / "riscv_formal_trap_csr_sby.log",
        cwd=sby_dir,
    )
    suite["sby"] = sby_step
    status_path = sby_dir / "trap_csr_ch0" / "status"
    if status_path.exists():
        status_text = status_path.read_text(encoding="utf-8", errors="replace").strip()
        suite["check_statuses"] = [
            {
                "check": "trap_csr_ch0",
                "status_file": rel(status_path),
                "status": status_text,
            }
        ]
        if status_text.upper().startswith(("PASS", "DONE")) and sby_step["status"] == "pass":
            suite["status"] = "pass"
        else:
            suite["reason"] = f"trap_csr_ch0 status: {status_text}"
    else:
        suite["check_statuses"] = []
        suite["reason"] = "trap_csr_ch0 did not produce a status file."
    return suite


def run_csr_warl_suite(core_dir, source, logs_dir):
    """Run the WARL per-field CSR legalization proof.

    Drives the inline SVA in formal/riscv_formal/ditdah32/wrapper.sv guarded
    by DITDAH32_RVFI_CSR_WARL_CHECK. Proves that the writable M-mode CSRs
    only ever expose legal field values to software (reserved-zero bits stay
    zero, mstatus.MPP is forced 11, mtvec.MODE=00, mepc[0]=0, mie writes
    outside MSI/MTI/MEI do not stick).
    """
    suite = {
        "name": "riscv_formal_csr_warl",
        "config": "csr_warl.sby",
        "checks_dir": rel(core_dir / "checks_csr_warl"),
        "property_groups": ["csr_warl_legalization"],
        "status": "fail",
    }
    depth = 16
    sby_dir = core_dir / "checks_csr_warl"
    if sby_dir.exists():
        make_writable(sby_dir)
        shutil.rmtree(sby_dir, ignore_errors=True)
    sby_dir.mkdir(parents=True, exist_ok=True)
    checks_root = source / "checks"
    sby_text = WFI_WAKE_SBY_TEMPLATE.format(
        depth=depth,
        depth_plus=depth + 1,
        check_basename="csr_warl_ch0",
        extra_defines="`define DITDAH32_RVFI_ENABLE_IRQ\n`define DITDAH32_RVFI_CSR_WARL_CHECK",
        slang_so=resolve_slang_so(),
        core_dir=str(core_dir.resolve()),
        wrapper_sv=str((core_dir / "wrapper.sv").resolve()),
        trace_top_sv=str((core_dir / "ditdah32_trace_top.sv").resolve()),
        dut_sv=str((core_dir / "DitDah32.sv").resolve()),
        dv_sv=str((core_dir / "DitDah32_DV.sv").resolve()),
        layers_sv=str((core_dir / "layers-DitDah32-DV.sv").resolve()),
        macros_vh=str((checks_root / "rvfi_macros.vh").resolve()),
        channel_sv=str((checks_root / "rvfi_channel.sv").resolve()),
        testbench_sv=str((checks_root / "rvfi_testbench.sv").resolve()),
        checker_sv=str((checks_root / "rvfi_cover_check.sv").resolve()),
    )
    sby_path = sby_dir / "csr_warl_ch0.sby"
    sby_path.write_text(sby_text, encoding="utf-8")
    suite["generated_checks"] = ["csr_warl_ch0"]
    sby_step = run(
        ["sby", "-f", "-d", "csr_warl_ch0", str(sby_path)],
        logs_dir / "riscv_formal_csr_warl_sby.log",
        cwd=sby_dir,
    )
    suite["sby"] = sby_step
    status_path = sby_dir / "csr_warl_ch0" / "status"
    if status_path.exists():
        status_text = status_path.read_text(encoding="utf-8", errors="replace").strip()
        suite["check_statuses"] = [
            {
                "check": "csr_warl_ch0",
                "status_file": rel(status_path),
                "status": status_text,
            }
        ]
        if status_text.upper().startswith(("PASS", "DONE")) and sby_step["status"] == "pass":
            suite["status"] = "pass"
        else:
            suite["reason"] = f"csr_warl_ch0 status: {status_text}"
    else:
        suite["check_statuses"] = []
        suite["reason"] = "csr_warl_ch0 did not produce a status file."
    return suite


def run_csr_access_suite(core_dir, source, logs_dir):
    """Run implemented-address and read-only CSR access proofs."""
    suite = {
        "name": "riscv_formal_csr_access",
        "config": "csr_access.sby",
        "checks_dir": rel(core_dir / "checks_csr_access"),
        "property_groups": ["csr_access_legality"],
        "status": "fail",
    }
    depth = 16
    sby_dir = core_dir / "checks_csr_access"
    if sby_dir.exists():
        make_writable(sby_dir)
        shutil.rmtree(sby_dir, ignore_errors=True)
    sby_dir.mkdir(parents=True, exist_ok=True)
    checks_root = source / "checks"
    sby_text = WFI_WAKE_SBY_TEMPLATE.format(
        depth=depth,
        depth_plus=depth + 1,
        check_basename="csr_access_ch0",
        extra_defines=(
            "`define DITDAH32_RVFI_ENABLE_IRQ\n"
            "`define DITDAH32_RVFI_CSR_TRACE\n"
            "`define DITDAH32_RVFI_CSR_READONLY_CHECK"
        ),
        slang_so=resolve_slang_so(),
        core_dir=str(core_dir.resolve()),
        wrapper_sv=str((core_dir / "wrapper.sv").resolve()),
        trace_top_sv=str((core_dir / "ditdah32_trace_top.sv").resolve()),
        dut_sv=str((core_dir / "DitDah32.sv").resolve()),
        dv_sv=str((core_dir / "DitDah32_DV.sv").resolve()),
        layers_sv=str((core_dir / "layers-DitDah32-DV.sv").resolve()),
        macros_vh=str((checks_root / "rvfi_macros.vh").resolve()),
        channel_sv=str((checks_root / "rvfi_channel.sv").resolve()),
        testbench_sv=str((checks_root / "rvfi_testbench.sv").resolve()),
        checker_sv=str((checks_root / "rvfi_cover_check.sv").resolve()),
    )
    sby_path = sby_dir / "csr_access_ch0.sby"
    sby_path.write_text(sby_text, encoding="utf-8")
    suite["generated_checks"] = ["csr_access_ch0"]
    sby_step = run(
        ["sby", "-f", "-d", "csr_access_ch0", str(sby_path)],
        logs_dir / "riscv_formal_csr_access_sby.log",
        cwd=sby_dir,
    )
    suite["sby"] = sby_step
    status_path = sby_dir / "csr_access_ch0" / "status"
    if status_path.exists():
        status_text = status_path.read_text(encoding="utf-8", errors="replace").strip()
        suite["check_statuses"] = [
            {
                "check": "csr_access_ch0",
                "status_file": rel(status_path),
                "status": status_text,
            }
        ]
        if status_text.upper().startswith(("PASS", "DONE")) and sby_step["status"] == "pass":
            suite["status"] = "pass"
        else:
            suite["reason"] = f"csr_access_ch0 status: {status_text}"
    else:
        suite["check_statuses"] = []
        suite["reason"] = "csr_access_ch0 did not produce a status file."
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
            "csr_instruction_semantics",
            "csr_state_persistence",
            "csr_state_invariants",
            "csr_access_legality",
            "csr_full",
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
            "bus_dmem_io_read_fault",
            "bus_dmem_io_write_fault",
            "interrupt_entry_shape",
            "liveness_bounded",
            "wfi_wake",
            "trap_entry_mstatus",
            "mret_exit_mstatus",
            "mip_mirror",
            "interrupt_cause_priority",
            "mpie_swap_all_traps",
            "trap_csr_side_effects",
            "interrupt_full_csr_side_effects",
            "csr_warl_legalization",
            "instruction_semantics_rv32ec",
            "hang",
            "ill",
            "cover",
        ],
        "disabled_property_groups": {},
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
    slang_so = resolve_slang_so()
    for cfg_name in (
        "checks.cfg", "checks_bus.cfg", "checks_csr.cfg", "checks_csr_state.cfg",
        "checks_liveness.cfg", "checks_order.cfg", "checks_fault.cfg",
        "checks_insns.cfg", "checks_interrupt.cfg",
    ):
        cfg_text = (config_dir / cfg_name).read_text(encoding="utf-8")
        cfg_text = cfg_text.replace("@SLANG_SO@", slang_so)
        (core_dir / cfg_name).write_text(cfg_text, encoding="utf-8")
    shutil.copy2(config_dir / "wrapper.sv", core_dir / "wrapper.sv")
    shutil.copy2(config_dir / "ditdah32_trace_top.sv", core_dir / "ditdah32_trace_top.sv")
    # The DV layer collateral is read alongside the core so read_slang can
    # resolve the trace probe XMRs.
    for collateral in ("DitDah32.sv", "DitDah32_DV.sv", "layers-DitDah32-DV.sv", "ref_DitDah32.sv"):
        shutil.copy2(REPO_ROOT / "result" / collateral, core_dir / collateral)

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
            "riscv_formal_csr_instruction_semantics",
            ["csr_instruction_semantics"],
        ),
        run_config(
            "checks_csr_state",
            "checks_csr_state",
            "riscv_formal_csr_state",
            ["csr_state_persistence", "csr_state_invariants"],
        ),
        run_config(
            "checks_liveness",
            "checks_liveness",
            "riscv_formal_liveness_bounded",
            ["liveness_bounded"],
        ),
        run_wfi_wake_suite(core_dir, source, logs_dir),
        run_trap_csr_suite(core_dir, source, logs_dir),
        run_csr_access_suite(core_dir, source, logs_dir),
        run_csr_warl_suite(core_dir, source, logs_dir),
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
            [
                "fault",
                "bus_dmem_fault",
                "bus_imem_fault",
                "bus_dmem_io_read_fault",
                "bus_dmem_io_write_fault",
            ],
        ),
        run_config(
            "checks_insns",
            "checks_insns",
            "riscv_formal_rv32ec_instruction_semantics",
            ["instruction_semantics_rv32ec"],
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
        "equivalence_class": "external_riscv_formal_rv32ec_implemented_profile",
        "steps": steps,
        "limitations": [
            "Closure covers the implemented RV32EC, Zicsr, M-only direct-trap, and machine software/timer/external interrupt profile.",
            "All checks are bounded at their configured depths; CSR persistence assumes no trap or MRET between the selected software write and read, while those transitions are proven independently.",
            "All 62 RV32EC instructions pass the rv32ic models under per-format x0-x15 register constraints.",
            "External memory contents remain environmental; RVFI_BUS checks prove core retire-to-AXI consistency, including normal and faulting accesses.",
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
