#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

"""Prove the layer("DV") SVA on a commercial FPV engine over ssh.

Always exits 0 unless a reachable engine leaves a property unresolved, so a
campaign profile stays green on a machine with no host, no license, or no SVA
build.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The DUT, its bind collateral, and the bridge that resolves the probe XMRs.
# Built by `make build-sva` into its own tree. read_slang cannot parse the SVA
# firtool emits, so this must stay out of result/ proper.
SVA_DIR = "result/sva"
RTL_FILES = [
    f"{SVA_DIR}/DitDah32.sv",
    f"{SVA_DIR}/DitDah32Gpr.sv",
    f"{SVA_DIR}/DitDah32_DV.sv",
    f"{SVA_DIR}/layers-DitDah32Gpr-DV.sv",
    f"{SVA_DIR}/layers-DitDah32-DV.sv",
]
BRIDGE = "formal/riscv_formal/ditdah32/ditdah32_trace_top.sv"
INCLUDE = f"{SVA_DIR}/ref_DitDah32.sv"
TOP = "ditdah32_trace_top"

JG_TCL = """clear -all
analyze -sv12 +incdir+{rtl} {files}
elaborate -top {top}
clock dut.clock
reset dut.reset
set_prove_time_limit {limit}
prove -all
foreach p [get_property_list -include {{type {{assert cover}}}}] {{
  puts "VERDICT|$p|[get_property_info $p -list status]|[get_property_info $p -list time]"
}}
exit
"""

VCF_TCL = """set_fml_appmode FPV
read_file -top {top} -format sverilog -sva -vcs "-sverilog +incdir+{rtl} {files}"
create_clock clock -period 100
create_reset reset -sense high
sim_run -stable
sim_save_reset
check_fv -block -subtype {{property vacuity witness}}
report_fv -verbose
exit
"""


def ssh(host, command, timeout):
    # Always through a login shell: the remote paths carry a leading ~ that only
    # the remote shell can expand, and the module system needs the profile.
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, f"bash -lc {shlex.quote(command)}"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def remote_home(host):
    probe = ssh(host, "cd ~ && pwd", 60)
    return probe.stdout.strip().splitlines()[-1] if probe.returncode == 0 else ""


def engine_available(host, module, binary):
    try:
        return ssh(host, f"module load {module} && command -v {binary}", 60).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def parse_jg(stdout):
    properties = []
    for line in stdout.splitlines():
        if not line.startswith("VERDICT|"):
            continue
        _, name, status, seconds = (line.split("|") + ["", "", ""])[:4]
        properties.append(
            {
                "name": name.split(".")[-1],
                "status": status.strip(),
                "seconds": seconds.strip(),
            }
        )
    return properties


# PROP_I_RESULT: <hierarchical name>  <status>[:<n>]  [<kind>]  <hh:mm:ss>
# The status alternation is deliberately open: an unknown vendor status must
# reach resolved() and fail the run, not be dropped here. Anchored at the design
# hierarchy so a log line that merely carries one of these words cannot
# contribute a name.
VCF_ROW = re.compile(
    rf"^\s*\[Info\]\s+PROP_I_RESULT:\s+{TOP}\.\S*?"
    r"([A-Za-z_][A-Za-z0-9_$]*(?::precondition\d+)?)\s+"
    r"([a-z_]+(?::\d+)?)"
    r"\s+(?:([a-z_]+)\s+)?(\d+:\d+:\d+)\s*$"
)


def parse_vcf(stdout):
    # The same property appears once per pass, so a vacuity row and a proof row
    # both land here; keep them under separate keys rather than overwriting.
    verdicts = {}
    vacuity = {}
    for line in stdout.splitlines():
        match = VCF_ROW.match(line)
        if not match:
            continue
        name, status, kind, seconds = match.groups()
        if kind == "vacuity":
            vacuity[name] = status
        elif status != "checking":
            verdicts[name] = (status, seconds)
    return [
        {
            "name": name,
            "status": status,
            "seconds": seconds,
            "vacuity": vacuity.get(name, "unreported"),
        }
        for name, (status, seconds) in verdicts.items()
    ]


def sva_labels(dv_source):
    """Every assert and cover label the bind collateral declares."""
    return {
        name
        for name, _ in re.findall(
            r"^\s*([A-Za-z_][A-Za-z0-9_$]*):\s*\n?\s*(assert|cover) property",
            dv_source,
            re.M,
        )
    }


def run_engine(host, workdir, module, binary, invocation, tcl, log_path, timeout):
    ssh(host, f"mkdir -p {workdir} && rm -rf {workdir}/jgproj", 120)
    ssh(host, f"cat > {workdir}/{binary}.tcl <<'DITDAH32_TCL'\n{tcl}\nDITDAH32_TCL", 120)
    start = time.monotonic()
    completed = ssh(host, f"module load {module} && cd {workdir} && {invocation}", timeout)
    # The raw log stays on the host and in the local log file. Vendor banners
    # carry host and license detail, so only the parsed verdicts are published.
    log_path.write_text(completed.stdout + "\n" + completed.stderr, encoding="utf-8")
    return completed, round(time.monotonic() - start, 1)


def main():
    parser = argparse.ArgumentParser(description="Prove DitDah32 SVA on a commercial FPV engine")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "formal" / "commercial")
    parser.add_argument("--host", default=os.environ.get("DITDAH32_FPV_HOST"))
    parser.add_argument("--remote-dir", default=os.environ.get("DITDAH32_FPV_DIR"))
    parser.add_argument("--engine", choices=["jg", "vcf", "both"], default="jg")
    parser.add_argument("--time-limit", default="300s")
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()

    # resolve() collapses .. and follows symlinks, so a path that merely passes
    # through result/ cannot escape it.
    out_dir = (REPO_ROOT / args.out_dir).resolve()
    result_root = (REPO_ROOT / "result").resolve()
    if not out_dir.is_relative_to(result_root):
        raise SystemExit("--out-dir must live under result/; vendor artefacts are not tracked")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "commercial_formal.json"

    def publish(report):
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"commercial-formal {report['status']}: {os.path.relpath(report_path, REPO_ROOT)}")
        return 0 if report["status"] != "fail" else 1

    missing = [p for p in RTL_FILES + [BRIDGE, INCLUDE] if not (REPO_ROOT / p).is_file()]
    if missing:
        return publish({"status": "skipped_no_rtl", "missing": missing})

    dv = (REPO_ROOT / SVA_DIR / "DitDah32_DV.sv").read_text(encoding="utf-8")
    if "assert property" not in dv:
        return publish({"status": "skipped_no_sva", "hint": "make build-sva"})
    declared = sva_labels(dv)

    if not args.host or not args.remote_dir:
        return publish({"status": "skipped_no_host", "needs": ["DITDAH32_FPV_HOST", "DITDAH32_FPV_DIR"]})

    engines = ["jg", "vcf"] if args.engine == "both" else [args.engine]
    catalog = {
        "jg": (os.environ.get("DITDAH32_FPV_JG_MODULE", "cadence/jasper2103"), "jg"),
        "vcf": (os.environ.get("DITDAH32_FPV_VCF_MODULE", "synopsys/vc_formal-V-2023.12"), "vcf"),
    }
    reachable = [e for e in engines if engine_available(args.host, *catalog[e])]
    if not reachable:
        return publish({"status": "skipped_no_engine", "requested": engines})

    home = remote_home(args.host)
    remote_dir = args.remote_dir.replace("~", home, 1) if home else args.remote_dir
    remote_rtl = f"{remote_dir}/rtl"
    ssh(args.host, f"mkdir -p {remote_rtl}", 120)
    sources = [str(REPO_ROOT / p) for p in RTL_FILES + [BRIDGE, INCLUDE]]
    push = subprocess.run(
        ["rsync", "-a", *sources, f"{args.host}:{remote_rtl}/"],
        capture_output=True,
        text=True,
        check=False,
    )
    if push.returncode != 0:
        return publish({"status": "fail", "stage": "rsync", "returncode": push.returncode})

    names = " ".join(f"{remote_rtl}/{Path(p).name}" for p in RTL_FILES + [BRIDGE])
    results = {}
    for engine in reachable:
        module, binary = catalog[engine]
        if engine == "jg":
            tcl = JG_TCL.format(rtl=remote_rtl, files=names, top=TOP, limit=args.time_limit)
            invocation = f"jg -batch -tcl {binary}.tcl -proj jgproj"
            parse = parse_jg
        else:
            tcl = VCF_TCL.format(rtl=remote_rtl, files=names, top=TOP)
            invocation = f"vcf -batch -no_ui -fmode FPV -f {binary}.tcl"
            parse = parse_vcf
        completed, seconds = run_engine(
            args.host,
            remote_dir,
            module,
            binary,
            invocation,
            tcl,
            out_dir / f"{engine}.log",
            args.timeout,
        )
        properties = parse(completed.stdout)
        # An assert must be proven and a cover must be reachable. A green run
        # over an unreachable antecedent proves nothing.
        def resolved(p):
            if p["name"].startswith("cover") or ":precondition" in p["name"]:
                return p["status"].startswith("covered")
            # "unreported" is JasperGold, whose vacuity is carried by the
            # :precondition covers instead of a per-property field.
            return p["status"] == "proven" and p.get("vacuity", "unreported") in (
                "non_vacuous",
                "unreported",
            )

        bad = [p["name"] for p in properties if not resolved(p)]
        # A property the collateral declares but the report never mentions was
        # dropped by the tool or by the parser, and a run that cannot account
        # for every declared property is not evidence of anything.
        unreported = sorted(declared - {p["name"] for p in properties})
        results[engine] = {
            "returncode": completed.returncode,
            "seconds": seconds,
            "declared": len(declared),
            "properties": properties,
            "unresolved": bad,
            "unreported": unreported,
            "status": (
                "pass"
                if completed.returncode == 0 and properties and not bad and not unreported
                else "fail"
            ),
        }

    status = "pass" if all(r["status"] == "pass" for r in results.values()) else "fail"
    return publish({"status": status, "engines": results})


if __name__ == "__main__":
    raise SystemExit(main())
