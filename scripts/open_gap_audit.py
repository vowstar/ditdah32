#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as json_file:
        return json.load(json_file)


def load_tool_audit():
    return load_json(REPO_ROOT / "result" / "verification" / "tool_availability.json")


def tool_capability(tool_report, name):
    return bool((tool_report or {}).get("capabilities", {}).get(name, False))


def run_text(command):
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def current_git_head():
    returncode, stdout, _stderr = run_text(["git", "rev-parse", "HEAD"])
    if returncode == 0 and stdout:
        return stdout
    return None


def command_available(command):
    return shutil.which(command) is not None


def nix_attr_available(attr):
    completed = subprocess.run(
        ["nix", "eval", "--option", "sandbox", "false", "--raw", f"nixpkgs#{attr}.pname"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def rel(path):
    return str(path.relative_to(REPO_ROOT))


def artifact(path, exists=None):
    path = REPO_ROOT / path
    return {
        "path": rel(path),
        "exists": path.exists() if exists is None else bool(exists),
    }


def make_gap(gap_id, title, status, evidence, missing, closure_command, closure_criteria):
    return {
        "id": gap_id,
        "title": title,
        "status": status,
        "closed": status.startswith("closed"),
        "evidence": evidence,
        "missing": missing,
        "closure_command": closure_command,
        "closure_criteria": closure_criteria,
    }


def audit_external_iss():
    tool_report = load_tool_audit()
    spike_smoke = load_json(REPO_ROOT / "result" / "iss" / "spike_smoke" / "spike_smoke.json")
    spike_matrix = load_json(REPO_ROOT / "result" / "iss" / "spike_matrix" / "spike_smoke.json")
    sail_matrix = load_json(REPO_ROOT / "result" / "iss" / "sail_matrix" / "sail_smoke.json")
    spike_strict = load_json(REPO_ROOT / "result" / "iss" / "spike_rv32e_strict" / "spike_rv32e_strict.json")
    spike_highmem = load_json(REPO_ROOT / "result" / "iss" / "spike_highmem" / "spike_smoke.json")
    spike_highmem_rtl = load_json(REPO_ROOT / "result" / "rtl_trace" / "spike_highmem_artifacts" / "matrix.json")
    sail_highmem = load_json(REPO_ROOT / "result" / "iss" / "sail_highmem" / "sail_smoke.json")
    sail_highmem_rtl = load_json(REPO_ROOT / "result" / "rtl_trace" / "sail_highmem_artifacts" / "matrix.json")
    external_full = load_json(REPO_ROOT / "result" / "iss" / "external_iss_full" / "external_iss_full.json")

    smoke_pass = spike_smoke is not None and spike_smoke.get("status") == "pass"
    matrix_pass = spike_matrix is not None and spike_matrix.get("status") == "pass"
    matrix_summary = (spike_matrix or {}).get("summary", {})
    matrix_partial = (spike_matrix or {}).get("coverage_status") == "partial"
    sail_matrix_pass = sail_matrix is not None and sail_matrix.get("status") == "pass"
    sail_matrix_summary = (sail_matrix or {}).get("summary", {})
    sail_matrix_complete = (
        sail_matrix_pass
        and sail_matrix_summary.get("skip", 1) == 0
        and (sail_matrix or {}).get("coverage_status") == "complete_for_selected_artifacts"
    )
    spike_strict_pass = spike_strict is not None and spike_strict.get("status") == "pass"
    spike_strict_summary = (spike_strict or {}).get("summary", {})
    highmem_pass = spike_highmem is not None and spike_highmem.get("status") == "pass"
    highmem_summary = (spike_highmem or {}).get("summary", {})
    highmem_rtl_pass = spike_highmem_rtl is not None and spike_highmem_rtl.get("status") == "pass"
    sail_highmem_pass = sail_highmem is not None and sail_highmem.get("status") == "pass"
    sail_highmem_summary = (sail_highmem or {}).get("summary", {})
    sail_highmem_rtl_pass = sail_highmem_rtl is not None and sail_highmem_rtl.get("status") == "pass"
    external_full_pass = external_full is not None and external_full.get("status") == "pass"
    spike_available = (
        tool_capability(tool_report, "spike_external_iss")
        if tool_report is not None
        else command_available("spike") or nix_attr_available("spike")
    )
    sail_available = tool_capability(tool_report, "sail_external_iss_candidate")

    evidence = [
        artifact("flake.nix"),
        artifact("result/verification/tool_availability.json", tool_report is not None),
        artifact("scripts/run_spike_iss_smoke.py"),
        artifact("scripts/run_sail_iss_smoke.py"),
        artifact("result/iss/spike_smoke/spike_smoke.json", smoke_pass),
        artifact("result/iss/spike_matrix/spike_smoke.json", matrix_pass),
        artifact("result/iss/sail_matrix/sail_smoke.json", sail_matrix_pass),
        artifact("result/iss/spike_rv32e_strict/spike_rv32e_strict.json", spike_strict_pass),
        artifact("result/rtl_trace/spike_highmem_artifacts/matrix.json", highmem_rtl_pass),
        artifact("result/iss/spike_highmem/spike_smoke.json", highmem_pass),
        artifact("result/rtl_trace/sail_highmem_artifacts/matrix.json", sail_highmem_rtl_pass),
        artifact("result/iss/sail_highmem/sail_smoke.json", sail_highmem_pass),
        artifact("result/iss/external_iss_full/external_iss_full.json", external_full_pass),
        {
            "spike_available": spike_available,
            "sail_external_iss_candidate": sail_available,
            "spike_matrix_summary": matrix_summary,
            "spike_matrix_coverage_status": (spike_matrix or {}).get("coverage_status"),
            "sail_matrix_summary": sail_matrix_summary,
            "sail_matrix_coverage_status": (sail_matrix or {}).get("coverage_status"),
            "spike_rv32e_strict_summary": spike_strict_summary,
            "spike_rv32e_strict_limitations": (spike_strict or {}).get("limitations", []),
            "spike_highmem_summary": highmem_summary,
            "spike_highmem_coverage_status": (spike_highmem or {}).get("coverage_status"),
            "spike_highmem_rtl_artifacts": len((spike_highmem_rtl or {}).get("artifacts", [])),
            "sail_highmem_summary": sail_highmem_summary,
            "sail_highmem_coverage_status": (sail_highmem or {}).get("coverage_status"),
            "sail_highmem_rtl_artifacts": len((sail_highmem_rtl or {}).get("artifacts", [])),
            "sail_limitations": (sail_highmem or {}).get("limitations", []),
            "external_iss_full_closure_status": (external_full or {}).get("closure_status"),
            "external_iss_full_summary": (external_full or {}).get("summary"),
            "external_iss_full_limitations": (external_full or {}).get("limitations", []),
        },
    ]
    missing = []
    if tool_report is None:
        missing.append("Tool availability audit is missing.")
    if not spike_available:
        missing.append("Spike is not available according to the tool audit.")
    if not sail_available:
        missing.append("Sail is not available according to the tool audit.")
    if not smoke_pass:
        missing.append("Spike smoke report is missing or not passing.")
    if not matrix_pass:
        missing.append("Spike-compatible matrix report is missing or not passing.")
    if not sail_matrix_pass:
        missing.append("Sail full generated ISA matrix report is missing or not passing.")
    elif not sail_matrix_complete:
        missing.append("Sail full generated ISA matrix still has skipped artifacts.")
    if not spike_strict_pass:
        missing.append("Spike strict RV32E negative matrix report is missing or not passing.")
    if not highmem_pass:
        missing.append("Spike high-memory supplemental matrix report is missing or not passing.")
    elif highmem_summary.get("skip", 0) != 0:
        missing.append("Spike high-memory supplemental matrix still has skipped artifacts.")
    if not highmem_rtl_pass:
        missing.append("Spike high-memory supplemental RTL matrix report is missing or not passing.")
    if not sail_highmem_pass:
        missing.append("Sail high-memory supplemental matrix report is missing or not passing.")
    elif sail_highmem_summary.get("skip", 0) != 0:
        missing.append("Sail high-memory supplemental matrix still has skipped artifacts.")
    if not sail_highmem_rtl_pass:
        missing.append("Sail high-memory supplemental RTL matrix report is missing or not passing.")
    if not external_full_pass:
        missing.append("Composite external ISS closure report is missing or not passing.")
        if matrix_partial:
            missing.append("Spike-compatible matrix has skipped artifacts; Spike is not the full external ISS matrix.")
        if not sail_matrix_complete:
            missing.append("Some generated ISA artifacts are not compared against an external ISS.")
            missing.append("Current generated low-data-memory artifacts need a Spike/Sail-compatible flat-memory strategy.")
        elif not spike_strict_pass:
            missing.append("Sail full matrix uses an RV32IC-compatible model, not a strict RV32E external model.")

    status = "closed_composite" if external_full_pass else "partial" if smoke_pass and matrix_pass and highmem_pass and sail_highmem_pass and spike_strict_pass else "open"

    return make_gap(
        "external_iss",
        "External ISS differential testing",
        status,
        evidence,
        missing,
        "make verify-iss",
        [
            "Every generated legal ISA artifact runs on the selected external ISS legal matrix.",
            "The generated RTL artifact matrix and external ISS legal matrix cover the same artifact names.",
            "Strict RV32E illegal-register negative checks pass against Spike.",
            "The JSON report records tool availability, artifact list, status, and unsupported classes.",
        ],
    )


def audit_riscv_dv():
    tool_report = load_tool_audit()
    has_target = "verify-riscv-dv:" in (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    has_config = (REPO_ROOT / "test" / "riscv_dv" / "ditdah32_rv32ec.yaml").exists()
    riscv_dv_report = load_json(REPO_ROOT / "result" / "riscv_dv" / "riscv_dv.json")
    has_report = riscv_dv_report is not None and riscv_dv_report.get("status") in {"pass", "partial"}
    riscv_dv_available = (
        tool_capability(tool_report, "riscv_dv_generator")
        if tool_report is not None
        else command_available("run.py") or command_available("riscv-dv")
    )
    flake_markers = (tool_report or {}).get("flake_dev_shell_markers", {})
    riscv_dv_in_devshell = bool(flake_markers.get("riscv-dv", False))
    riscv_dv_steps = (riscv_dv_report or {}).get("steps", [])
    generation_steps = [
        step for step in riscv_dv_steps
        if step.get("name", "").startswith("generate_and_scan_seed_")
    ]
    generation_statuses = [
        {
            "name": step.get("name"),
            "status": step.get("status"),
            "generator_status": (step.get("generator") or {}).get("status"),
            "rv32ec_scan_status": (step.get("rv32ec_legality_scan") or {}).get("status"),
        }
        for step in generation_steps
    ]
    generation_clean = bool(generation_steps) and all(
        step.get("status") == "pass" for step in generation_steps
    )
    trace_compare_status = ((riscv_dv_report or {}).get("trace_compare") or {}).get("status")
    evidence = [
        artifact("scripts/rv32ec_isa_regress.py"),
        artifact("scripts/run_riscv_dv.py"),
        artifact("test/riscv_dv/ditdah32_rv32ec.yaml", has_config),
        artifact("result/riscv_dv/riscv_dv.json", has_report),
        artifact("result/verification/tool_availability.json", tool_report is not None),
        {"riscv_dv_tool_available": riscv_dv_available},
        {"riscv_dv_in_devshell": riscv_dv_in_devshell},
        {"make_target_present": has_target},
        {"riscv_dv_report_status": (riscv_dv_report or {}).get("status")},
        {"riscv_dv_generation_statuses": generation_statuses},
        {"riscv_dv_trace_compare_status": trace_compare_status},
    ]
    missing = []
    if tool_report is None:
        missing.append("Tool availability audit is missing.")
    if not riscv_dv_available or not riscv_dv_in_devshell:
        missing.append("RISCV-DV is not integrated into the reproducible tool environment.")
    if not has_config:
        missing.append("No DitDah32 RV32EC RISCV-DV configuration exists.")
    if not has_target or not has_report:
        missing.append("No make verify-riscv-dv target or JSON report exists.")
    if has_report and not generation_clean:
        missing.append("RISCV-DV generated assembly is not RV32EC-clean.")
    if has_report and trace_compare_status != "pass":
        missing.append("RISCV-DV generated programs are not trace-compared against the reference model.")
    if has_report and riscv_dv_report.get("status") != "pass":
        missing.append("No passing RISCV-DV generated-program regression report exists.")
    status = "closed" if riscv_dv_available and riscv_dv_in_devshell and has_config and has_target and has_report and riscv_dv_report.get("status") == "pass" else "partial" if has_config and has_target and has_report else "open"
    return make_gap(
        "riscv_dv",
        "RISCV-DV constrained-random flow",
        status,
        evidence,
        missing,
        "make verify-riscv-dv",
        [
            "Fixed seeds are reproducible.",
            "Generated legal programs compare cleanly against the reference trace.",
            "Illegal programs are rejected or classified before RTL execution.",
        ],
    )


def audit_rvfi():
    tool_report = load_tool_audit()
    formal_report = load_json(REPO_ROOT / "result" / "formal" / "formal.json")
    rvfi_lite_report = load_json(REPO_ROOT / "result" / "formal" / "rvfi_lite" / "rvfi_lite.json")
    rvfi_report = load_json(REPO_ROOT / "result" / "formal" / "rvfi" / "rvfi.json")
    local_formal_pass = formal_report is not None and formal_report.get("status") == "pass"
    rvfi_lite_pass = rvfi_lite_report is not None and rvfi_lite_report.get("status") == "pass"
    rvfi_report_present = rvfi_report is not None and rvfi_report.get("status") in {"pass", "partial"}
    rvfi_report_pass = rvfi_report is not None and rvfi_report.get("status") == "pass"
    external_step = next(
        (
            step for step in (rvfi_report or {}).get("steps", [])
            if step.get("name") == "external_riscv_formal_suite"
        ),
        {},
    )
    external_property_groups = external_step.get("property_groups", [])
    disabled_property_groups = external_step.get("disabled_property_groups", {})
    has_rvfi_target = "verify-rvfi:" in (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    has_rvfi_lite_target = "verify-rvfi-lite:" in (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    has_rvfi_lite_file = (REPO_ROOT / "formal" / "ditdah32_rvfi_lite.sv").exists()
    has_riscv_formal_wrapper = (REPO_ROOT / "formal" / "riscv_formal" / "ditdah32" / "wrapper.sv").exists()
    has_riscv_formal_cfg = (REPO_ROOT / "formal" / "riscv_formal" / "ditdah32" / "checks.cfg").exists()
    has_riscv_formal_bus_cfg = (REPO_ROOT / "formal" / "riscv_formal" / "ditdah32" / "checks_bus.cfg").exists()
    has_riscv_formal_csr_cfg = (REPO_ROOT / "formal" / "riscv_formal" / "ditdah32" / "checks_csr.cfg").exists()
    has_riscv_formal_csr_state_cfg = (REPO_ROOT / "formal" / "riscv_formal" / "ditdah32" / "checks_csr_state.cfg").exists()
    has_riscv_formal_liveness_cfg = (REPO_ROOT / "formal" / "riscv_formal" / "ditdah32" / "checks_liveness.cfg").exists()
    has_riscv_formal_order_cfg = (REPO_ROOT / "formal" / "riscv_formal" / "ditdah32" / "checks_order.cfg").exists()
    has_riscv_formal_interrupt_cfg = (REPO_ROOT / "formal" / "riscv_formal" / "ditdah32" / "checks_interrupt.cfg").exists()
    has_riscv_formal_fault_cfg = (REPO_ROOT / "formal" / "riscv_formal" / "ditdah32" / "checks_fault.cfg").exists()
    riscv_formal_available = tool_capability(tool_report, "riscv_formal_suite")
    symbiyosys_available = tool_capability(tool_report, "symbiyosys_available")
    evidence = [
        artifact("result/verification/tool_availability.json", tool_report is not None),
        artifact("formal/ditdah32_safety.sv"),
        artifact("formal/ditdah32_rvfi_lite.sv", has_rvfi_lite_file),
        artifact("formal/riscv_formal/ditdah32/wrapper.sv", has_riscv_formal_wrapper),
        artifact("formal/riscv_formal/ditdah32/checks.cfg", has_riscv_formal_cfg),
        artifact("formal/riscv_formal/ditdah32/checks_bus.cfg", has_riscv_formal_bus_cfg),
        artifact("formal/riscv_formal/ditdah32/checks_csr.cfg", has_riscv_formal_csr_cfg),
        artifact("formal/riscv_formal/ditdah32/checks_csr_state.cfg", has_riscv_formal_csr_state_cfg),
        artifact("formal/riscv_formal/ditdah32/checks_liveness.cfg", has_riscv_formal_liveness_cfg),
        artifact("formal/riscv_formal/ditdah32/checks_order.cfg", has_riscv_formal_order_cfg),
        artifact("formal/riscv_formal/ditdah32/checks_interrupt.cfg", has_riscv_formal_interrupt_cfg),
        artifact("formal/riscv_formal/ditdah32/checks_fault.cfg", has_riscv_formal_fault_cfg),
        artifact("scripts/run_formal.py"),
        artifact("scripts/run_rvfi_lite.py"),
        artifact("scripts/run_rvfi.py"),
        artifact("result/formal/formal.json", local_formal_pass),
        artifact("result/formal/rvfi_lite/rvfi_lite.json", rvfi_lite_pass),
        artifact("result/formal/rvfi/rvfi.json", rvfi_report_pass),
        {"make_target_present": has_rvfi_target},
        {"make_rvfi_lite_target_present": has_rvfi_lite_target},
        {"rvfi_lite_file_present": has_rvfi_lite_file},
        {"riscv_formal_wrapper_present": has_riscv_formal_wrapper},
        {"riscv_formal_config_present": has_riscv_formal_cfg},
        {"riscv_formal_bus_config_present": has_riscv_formal_bus_cfg},
        {"riscv_formal_csr_config_present": has_riscv_formal_csr_cfg},
        {"riscv_formal_csr_state_config_present": has_riscv_formal_csr_state_cfg},
        {"riscv_formal_liveness_config_present": has_riscv_formal_liveness_cfg},
        {"riscv_formal_order_config_present": has_riscv_formal_order_cfg},
        {"riscv_formal_interrupt_config_present": has_riscv_formal_interrupt_cfg},
        {"symbiyosys_available": symbiyosys_available},
        {"riscv_formal_suite_available": riscv_formal_available},
        {"rvfi_lite_limitations": (rvfi_lite_report or {}).get("limitations", [])},
        {"rvfi_report_status": (rvfi_report or {}).get("status")},
        {"rvfi_external_property_groups": external_property_groups},
        {"rvfi_disabled_property_groups": disabled_property_groups},
        {"rvfi_report_limitations": (rvfi_report or {}).get("limitations", [])},
    ]
    missing = []
    if tool_report is None:
        missing.append("Tool availability audit is missing.")
    if not local_formal_pass:
        missing.append("Local formal safety report is missing or not passing.")
    if not rvfi_lite_pass:
        missing.append("RVFI-lite adapter report is missing or not passing.")
    if not has_rvfi_lite_file:
        missing.append("RVFI-lite adapter file is missing.")
    if not has_riscv_formal_wrapper:
        missing.append("No DitDah32 riscv-formal wrapper exists.")
    if not has_riscv_formal_cfg:
        missing.append("No DitDah32 riscv-formal checks.cfg exists.")
    if not has_riscv_formal_bus_cfg:
        missing.append("No DitDah32 riscv-formal checks_bus.cfg exists.")
    if not has_riscv_formal_csr_cfg:
        missing.append("No DitDah32 riscv-formal checks_csr.cfg exists.")
    if not has_riscv_formal_csr_state_cfg:
        missing.append("No DitDah32 riscv-formal checks_csr_state.cfg exists.")
    if not has_riscv_formal_liveness_cfg:
        missing.append("No DitDah32 riscv-formal checks_liveness.cfg exists.")
    if not has_riscv_formal_order_cfg:
        missing.append("No DitDah32 riscv-formal checks_order.cfg exists.")
    if not has_riscv_formal_interrupt_cfg:
        missing.append("No DitDah32 riscv-formal checks_interrupt.cfg exists.")
    if not has_rvfi_lite_target:
        missing.append("No make verify-rvfi-lite target exists.")
    if not has_rvfi_target:
        missing.append("No full make verify-rvfi target exists.")
    if has_rvfi_target and not rvfi_report_present:
        missing.append("Standard RVFI status report is missing.")
    if not riscv_formal_available:
        missing.append("External riscv-formal property suite is not integrated.")
    if rvfi_report_present and not rvfi_report_pass:
        missing.append("No passing external riscv-formal report exists.")
    if rvfi_report_pass and not external_property_groups:
        missing.append("Passing RVFI report does not list enabled external property groups.")
    if rvfi_report_pass and "csr_selected" not in external_property_groups:
        missing.append("Passing RVFI report does not list the selected CSR property group.")
    if rvfi_report_pass and "csr_state_subset" not in external_property_groups:
        missing.append("Passing RVFI report does not list the CSR state subset property group.")
    if rvfi_report_pass and "liveness_bounded" not in external_property_groups:
        missing.append("Passing RVFI report does not list the bounded liveness property group.")
    if rvfi_report_pass and "wfi_wake" not in external_property_groups:
        missing.append("Passing RVFI report does not list the WFI bounded-wake property group.")
    if rvfi_report_pass and "trap_entry_mstatus" not in external_property_groups:
        missing.append("Passing RVFI report does not list the trap entry mstatus invariant property group.")
    if rvfi_report_pass and "mret_exit_mstatus" not in external_property_groups:
        missing.append("Passing RVFI report does not list the mret exit mstatus invariant property group.")
    if rvfi_report_pass and "interrupt_entry_shape" not in external_property_groups:
        missing.append("Passing RVFI report does not list the interrupt entry shape property group.")
    for group in [
        "causal",
        "causal_io",
        "bus_imem",
        "bus_dmem",
        "bus_dmem_io_read",
        "bus_dmem_io_write",
        "bus_dmem_io_order",
        "fault",
        "bus_dmem_fault",
        "bus_imem_fault",
        "hang",
        "ill",
    ]:
        if rvfi_report_pass and group not in external_property_groups:
            missing.append(f"Passing RVFI report does not list the {group} property group.")
    if rvfi_report_pass and not disabled_property_groups:
        missing.append("Passing RVFI report does not document disabled property groups.")
    for group in [
        "instruction_semantics",
        "csr_full",
        "interrupt_full_csr_side_effects",
    ]:
        if rvfi_report_pass and group not in disabled_property_groups:
            missing.append(f"Passing RVFI report does not document the disabled {group} property group.")
    closed = (
        local_formal_pass
        and rvfi_lite_pass
        and has_rvfi_target
        and has_rvfi_lite_target
        and has_riscv_formal_wrapper
        and has_riscv_formal_cfg
        and has_riscv_formal_bus_cfg
        and has_riscv_formal_csr_cfg
        and has_riscv_formal_csr_state_cfg
        and has_riscv_formal_liveness_cfg
        and has_riscv_formal_order_cfg
        and has_riscv_formal_interrupt_cfg
        and has_riscv_formal_fault_cfg
        and riscv_formal_available
        and symbiyosys_available
        and rvfi_report_pass
        and bool(external_property_groups)
        and "csr_selected" in external_property_groups
        and "csr_state_subset" in external_property_groups
        and "liveness_bounded" in external_property_groups
        and "wfi_wake" in external_property_groups
        and "trap_entry_mstatus" in external_property_groups
        and "mret_exit_mstatus" in external_property_groups
        and "interrupt_entry_shape" in external_property_groups
        and all(
            group in external_property_groups
            for group in [
                "causal",
                "causal_io",
                "bus_imem",
                "bus_dmem",
                "bus_dmem_io_read",
                "bus_dmem_io_write",
                "bus_dmem_io_order",
                "fault",
                "bus_dmem_fault",
                "bus_imem_fault",
                "hang",
                "ill",
            ]
        )
        and all(
            group in disabled_property_groups
            for group in [
                "instruction_semantics",
                "csr_full",
                "interrupt_full_csr_side_effects",
            ]
        )
    )
    return make_gap(
        "rvfi_riscv_formal",
        "Standard RVFI and riscv-formal integration",
        "closed_with_limitations" if closed else "partial" if local_formal_pass and rvfi_lite_pass else "open",
        evidence,
        missing,
        "make verify-rvfi",
        [
            "RVFI wrapper elaborates against generated RTL.",
            "riscv-formal checks pass at documented depths.",
            "Unsupported checks are explicitly disabled with written reasons.",
        ],
    )


def audit_axi4():
    requirements = (REPO_ROOT / "doc" / "requirements.md").read_text(encoding="utf-8")
    verification = (REPO_ROOT / "doc" / "verification.md").read_text(encoding="utf-8")
    axi_lite_documented = "AXI4-Lite" in requirements or "AXI-Lite" in verification
    full_axi4_documented = "Full AXI4 burst or ID support, if a later integration requires it." in requirements
    current_subset_documented = (
        "single-beat AXI4-Lite compatible subset" in requirements
        and "initial AXI verification target is protocol-level for the shared AXI-Lite" in verification
    )
    closed_out_of_scope = axi_lite_documented and full_axi4_documented and current_subset_documented
    evidence = [
        artifact("doc/requirements.md"),
        artifact("doc/verification.md"),
        artifact("result/axi/axi_lite_backpressure.json"),
        {"axi_lite_documented": axi_lite_documented},
        {"full_axi4_documented": full_axi4_documented},
        {"current_subset_documented": current_subset_documented},
    ]
    missing = [] if closed_out_of_scope else [
        "Full AXI4 burst, ID, and multiple-outstanding behavior are outside the current documented bus profile.",
        "No full AXI4 monitor or full AXI4 randomized regression exists.",
    ]
    return make_gap(
        "full_axi4",
        "Full AXI4 protocol surface",
        "closed_out_of_scope" if closed_out_of_scope else "out_of_scope_open",
        evidence,
        missing,
        "none until requirements expand",
        [
            "Requirements define the exact full AXI4 subset.",
            "A monitor observes every supported burst, ID, ordering, and outstanding-transaction feature.",
            "Directed and randomized full AXI4 tests pass with a protocol report.",
        ],
    )


def audit_ci():
    tool_report = load_tool_audit()
    ci_remote_report = load_json(REPO_ROOT / "result" / "verification" / "ci_remote_evidence.json")
    git_head = current_git_head()
    workflow_path = REPO_ROOT / ".github" / "workflows" / "verification.yml"
    workflow_ok = False
    workflow_jobs = []
    if workflow_path.exists():
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        workflow_jobs = sorted((workflow.get("jobs") or {}).keys())
        workflow_ok = {"smoke", "full", "signoff", "spike-matrix", "ci-evidence"}.issubset(set(workflow_jobs))
    evidence = [
        artifact("result/verification/tool_availability.json", tool_report is not None),
        artifact(".github/workflows/verification.yml", workflow_ok),
        artifact("result/verification/ci_remote_evidence.json", ci_remote_report is not None),
        {"workflow_jobs": workflow_jobs},
        {"github_cli_available": tool_capability(tool_report, "github_cli")},
        {"local_github_actions_runner_available": tool_capability(tool_report, "local_github_actions_runner")},
        {"ci_remote_status": (ci_remote_report or {}).get("status")},
        {"ci_remote_expected_head_sha": (ci_remote_report or {}).get("expected_head_sha")},
        {"current_git_head": git_head},
        {"ci_remote_satisfied_runs": (ci_remote_report or {}).get("satisfied_runs")},
    ]
    missing = []
    if not workflow_ok:
        missing.append("Workflow file is missing required verification jobs.")
    remote_ci_status_pass = ci_remote_report is not None and ci_remote_report.get("status") == "pass"
    remote_ci_missing = []
    if remote_ci_status_pass:
        expected_head = ci_remote_report.get("expected_head_sha")
        satisfied_runs = ci_remote_report.get("satisfied_runs") or {}
        required_profiles = ci_remote_report.get("required_profiles") or ["smoke"]
        if git_head is None:
            remote_ci_missing.append("Current git HEAD is not available for remote CI freshness checking.")
        if expected_head != git_head:
            remote_ci_missing.append("Remote CI evidence was not collected for the current git HEAD.")
        for profile in required_profiles:
            run = satisfied_runs.get(profile) or {}
            if run.get("head_sha") != git_head:
                remote_ci_missing.append(f"Remote {profile} evidence does not match the current git HEAD.")
    remote_ci_pass = remote_ci_status_pass and not remote_ci_missing
    evidence.append({"ci_remote_report_pass": remote_ci_pass})
    if not remote_ci_pass:
        remote_missing = remote_ci_missing or (ci_remote_report or {}).get("missing", [])
        if remote_missing:
            missing.extend(remote_missing)
        else:
            missing.append("No remote GitHub Actions run evidence is available in this local workspace.")
    return make_gap(
        "ci_regression",
        "Continuous integration and long-run regression",
        "closed" if workflow_ok and remote_ci_pass else "partial" if workflow_ok else "open",
        evidence,
        missing,
        "GitHub Actions workflow run",
        [
            "Push or pull request fast smoke job passes remotely.",
            "Longer full and signoff profiles remain manual or local runs.",
            "Artifacts include result/verification/*.json and related coverage/report outputs.",
        ],
    )


def audit_certified_benchmarks():
    scores = load_json(REPO_ROOT / "result" / "bench" / "benchmark_scores.json")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    verification = (REPO_ROOT / "doc" / "verification.md").read_text(encoding="utf-8")
    readme_flat = " ".join(readme.split())
    verification_flat = " ".join(verification.split())
    score_pass = scores is not None and scores.get("status") == "pass"
    non_certified = scores is not None and scores.get("certification_status") == "not_certified_local_rtl_estimate"
    docs_state_non_certified = (
        "not certified performance score runs" in readme_flat
        and "does not prove certified CoreMark or Dhrystone scores" in verification_flat
    )
    closed_non_certified = score_pass and non_certified and docs_state_non_certified
    evidence = [
        artifact("result/bench/benchmark_scores.json", score_pass),
        artifact("result/bench/benchmark_scores.md", score_pass),
        {"certification_status": (scores or {}).get("certification_status")},
        {"frequency_mhz": (scores or {}).get("frequency_mhz")},
        {"docs_state_non_certified": docs_state_non_certified},
    ]
    missing = []
    if not score_pass:
        missing.append("Local benchmark score report is missing or not passing.")
    if not non_certified:
        missing.append("Benchmark certification status is missing or ambiguous.")
    if not docs_state_non_certified:
        missing.append("Project documentation does not clearly classify local RTL benchmark numbers as non-certified estimates.")
    if score_pass and non_certified and not closed_non_certified:
        missing.append("Benchmark scores are local RTL estimates, not certified benchmark claims.")
    return make_gap(
        "certified_benchmarks",
        "Certified CoreMark and Dhrystone scoring",
        "closed_non_certified" if closed_non_certified else "open",
        evidence,
        missing,
        "certification-specific benchmark flow",
        [
            "A real implementation frequency is selected and timing is closed.",
            "Benchmark iterations, compiler flags, sources, and clock source meet certification rules.",
            "The report states certified status with exact toolchain and configuration.",
        ],
    )


def write_markdown(path, report):
    lines = [
        "# DitDah32 Open Gap Audit",
        "",
        f"Status: `{report['status']}`",
        f"Open or partial gaps: {report['summary']['not_closed']} / {report['summary']['total']}",
        "",
        "| Gap | Status | Missing Items |",
        "| --- | --- | --- |",
    ]
    for gap in report["gaps"]:
        missing = "<br>".join(gap["missing"]) if gap["missing"] else "None"
        lines.append(f"| {gap['title']} | `{gap['status']}` | {missing} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit DitDah32 open verification gaps")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    parser.add_argument("--fail-on-unclosed", action="store_true")
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    gaps = [
        audit_external_iss(),
        audit_riscv_dv(),
        audit_rvfi(),
        audit_axi4(),
        audit_ci(),
        audit_certified_benchmarks(),
    ]
    not_closed = sum(1 for gap in gaps if not gap["closed"])
    report = {
        "status": "closed" if not_closed == 0 else "open_gaps_present",
        "generated_unix": int(time.time()),
        "gaps": gaps,
        "summary": {
            "closed": len(gaps) - not_closed,
            "not_closed": not_closed,
            "total": len(gaps),
        },
    }

    json_path = out_dir / "open_gaps.json"
    markdown_path = out_dir / "open_gaps.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(markdown_path, report)
    print(f"open gap audit: {report['status']}")
    print(f"json: {json_path}")
    print(f"markdown: {markdown_path}")

    if args.fail_on_unclosed and not_closed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
