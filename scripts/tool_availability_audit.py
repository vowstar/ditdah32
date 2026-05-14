#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

COMMAND_CHECKS = [
    {
        "name": "build-ditdah32",
        "required_for": ["rtl_build"],
        "version_args": [],
    },
    {
        "name": "scala-cli",
        "required_for": ["rtl_build"],
        "version_args": ["--version"],
    },
    {
        "name": "firtool",
        "required_for": ["rtl_build"],
        "version_args": ["--version"],
    },
    {
        "name": "riscv32-none-elf-gcc",
        "required_for": ["benchmarks"],
        "version_args": ["--version"],
    },
    {
        "name": "riscv32-none-elf-objcopy",
        "required_for": ["benchmarks"],
        "version_args": ["--version"],
    },
    {
        "name": "riscv32-none-elf-objdump",
        "required_for": ["benchmarks"],
        "version_args": ["--version"],
    },
    {
        "name": "iverilog",
        "required_for": ["cocotb_rtl"],
        "version_args": ["-V"],
    },
    {
        "name": "verilator",
        "required_for": ["signoff_coverage"],
        "version_args": ["--version"],
    },
    {
        "name": "yosys",
        "required_for": ["formal"],
        "version_args": ["-V"],
    },
    {
        "name": "yosys-smtbmc",
        "required_for": ["formal"],
        "version_args": ["--version"],
    },
    {
        "name": "z3",
        "required_for": ["formal"],
        "version_args": ["--version"],
    },
    {
        "name": "sby",
        "required_for": ["riscv_formal"],
        "version_args": ["--version"],
    },
    {
        "name": "spike",
        "required_for": ["external_iss"],
        "version_args": ["--version"],
    },
    {
        "name": "sail",
        "required_for": ["external_iss_candidate"],
        "version_args": ["--version"],
    },
    {
        "name": "riscv_sim_RV32",
        "required_for": ["external_iss_candidate"],
        "version_args": ["--help"],
    },
    {
        "name": "sail_riscv_sim",
        "required_for": ["external_iss_candidate"],
        "version_args": ["--help"],
    },
    {
        "name": "riscv-dv",
        "required_for": ["riscv_dv"],
        "version_args": ["--help"],
    },
    {
        "name": "run.py",
        "required_for": ["riscv_dv"],
        "version_args": ["--help"],
    },
    {
        "name": "riscv-formal",
        "required_for": ["riscv_formal"],
        "version_args": ["--help"],
    },
    {
        "name": "gh",
        "required_for": ["ci_evidence"],
        "version_args": ["--version"],
    },
    {
        "name": "act",
        "required_for": ["ci_local_dry_run"],
        "version_args": ["--version"],
    },
]

NIX_ATTR_CHECKS = [
    {"attr": "spike", "required_for": ["external_iss"]},
    {"attr": "sail-riscv", "required_for": ["external_iss_candidate"]},
    {"attr": "riscv-dv", "required_for": ["riscv_dv"]},
    {"attr": "riscvdv", "required_for": ["riscv_dv"]},
    {"attr": "riscv-formal", "required_for": ["riscv_formal"]},
    {"attr": "riscvFormal", "required_for": ["riscv_formal"]},
]

DEVSHELL_MARKERS = {
    "spike": "pkgs.spike",
    "sail-riscv": "pkgs.sail-riscv",
    "riscv-dv": "riscv-dv",
    "riscv-formal": "riscv-formal",
    "yosys": "pkgs.yosys",
    "z3": "pkgs.z3",
    "verilator": "pkgs.verilator",
    "iverilog": "pkgs.iverilog",
}


def run_capture(command, timeout=20):
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        return {
            "returncode": None,
            "output_first_line": "",
            "error": str(err),
        }

    output = completed.stdout.strip().splitlines()
    return {
        "returncode": completed.returncode,
        "output_first_line": output[0] if output else "",
    }


def audit_command(entry):
    path = shutil.which(entry["name"])
    result = {
        "name": entry["name"],
        "available": path is not None,
        "path": path,
        "required_for": entry["required_for"],
    }
    if path is not None and entry["version_args"]:
        result["version_probe"] = run_capture([entry["name"], *entry["version_args"]])
    return result


def audit_nix_attr(entry):
    if shutil.which("nix") is None:
        return {
            "attr": entry["attr"],
            "available": False,
            "required_for": entry["required_for"],
            "error": "nix command is not available",
        }

    command = [
        "nix",
        "eval",
        "--option",
        "sandbox",
        "false",
        "--raw",
        f"nixpkgs#{entry['attr']}.pname",
    ]
    probe = run_capture(command, timeout=60)
    return {
        "attr": entry["attr"],
        "available": probe["returncode"] == 0,
        "required_for": entry["required_for"],
        "probe": probe,
    }


def command_available(commands, name):
    return any(tool["name"] == name and tool["available"] for tool in commands)


def nix_attr_available(attrs, name):
    return any(attr["attr"] == name and attr["available"] for attr in attrs)


def flake_markers():
    flake = REPO_ROOT / "flake.nix"
    text = flake.read_text(encoding="utf-8") if flake.exists() else ""
    return {
        name: marker in text
        for name, marker in DEVSHELL_MARKERS.items()
    }


def build_capabilities(commands, nix_attrs):
    return {
        "rtl_build_toolchain": all(
            command_available(commands, name)
            for name in ["build-ditdah32", "scala-cli", "firtool"]
        ),
        "riscv_embedded_toolchain": all(
            command_available(commands, name)
            for name in [
                "riscv32-none-elf-gcc",
                "riscv32-none-elf-objcopy",
                "riscv32-none-elf-objdump",
            ]
        ),
        "cocotb_rtl_toolchain": command_available(commands, "iverilog"),
        "coverage_toolchain": command_available(commands, "verilator"),
        "local_formal_engine": all(
            command_available(commands, name)
            for name in ["yosys", "yosys-smtbmc", "z3"]
        ),
        "symbiyosys_available": command_available(commands, "sby"),
        "spike_external_iss": command_available(commands, "spike")
        or nix_attr_available(nix_attrs, "spike"),
        "sail_external_iss_candidate": any(
            command_available(commands, name)
            for name in ["sail", "riscv_sim_RV32", "sail_riscv_sim"]
        )
        or nix_attr_available(nix_attrs, "sail-riscv"),
        "riscv_dv_generator": any(
            command_available(commands, name)
            for name in ["riscv-dv", "run.py"]
        )
        or nix_attr_available(nix_attrs, "riscv-dv")
        or nix_attr_available(nix_attrs, "riscvdv"),
        "riscv_formal_suite": command_available(commands, "riscv-formal")
        or nix_attr_available(nix_attrs, "riscv-formal")
        or nix_attr_available(nix_attrs, "riscvFormal"),
        "github_cli": command_available(commands, "gh"),
        "local_github_actions_runner": command_available(commands, "act"),
    }


def write_markdown(path, report):
    lines = [
        "# DitDah32 Tool Availability Audit",
        "",
        f"Status: `{report['status']}`",
        f"Current local toolchain: `{report['current_local_toolchain_status']}`",
        f"Planned closure toolchain: `{report['planned_closure_toolchain_status']}`",
        "",
        "## Capabilities",
        "",
        "| Capability | Available |",
        "| --- | --- |",
    ]
    for name, available in sorted(report["capabilities"].items()):
        lines.append(f"| `{name}` | `{str(available).lower()}` |")

    lines.extend([
        "",
        "## Commands",
        "",
        "| Command | Available | Path |",
        "| --- | --- | --- |",
    ])
    for tool in report["commands"]:
        lines.append(
            f"| `{tool['name']}` | `{str(tool['available']).lower()}` | "
            f"{tool['path'] or ''} |"
        )

    lines.extend([
        "",
        "## Nix Attributes",
        "",
        "| Attribute | Available |",
        "| --- | --- |",
    ])
    for attr in report["nix_attrs"]:
        lines.append(f"| `{attr['attr']}` | `{str(attr['available']).lower()}` |")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit DitDah32 verification tool availability")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "verification")
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    commands = [audit_command(entry) for entry in COMMAND_CHECKS]
    nix_attrs = [audit_nix_attr(entry) for entry in NIX_ATTR_CHECKS]
    capabilities = build_capabilities(commands, nix_attrs)

    blocking_capabilities = [
        "rtl_build_toolchain",
        "riscv_embedded_toolchain",
        "cocotb_rtl_toolchain",
        "coverage_toolchain",
        "local_formal_engine",
        "spike_external_iss",
    ]
    missing_blocking = [
        name for name in blocking_capabilities
        if not capabilities.get(name, False)
    ]
    planned_closure_capabilities = [
        "sail_external_iss_candidate",
        "riscv_dv_generator",
        "riscv_formal_suite",
        "symbiyosys_available",
        "github_cli",
    ]
    missing_planned_closure = [
        name for name in planned_closure_capabilities
        if not capabilities.get(name, False)
    ]

    report = {
        "status": "pass" if not missing_blocking and not missing_planned_closure else "partial",
        "current_local_toolchain_status": "pass" if not missing_blocking else "partial",
        "planned_closure_toolchain_status": "pass" if not missing_planned_closure else "partial",
        "generated_unix": int(time.time()),
        "commands": commands,
        "nix_attrs": nix_attrs,
        "flake_dev_shell_markers": flake_markers(),
        "capabilities": capabilities,
        "missing_blocking_capabilities": missing_blocking,
        "missing_planned_closure_capabilities": missing_planned_closure,
    }

    json_path = out_dir / "tool_availability.json"
    markdown_path = out_dir / "tool_availability.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(markdown_path, report)
    print(f"tool availability audit: {report['status']}")
    print(f"json: {json_path}")
    print(f"markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
