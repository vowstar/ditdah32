# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_commercial_formal as fpv  # noqa: E402


HIER = f"{fpv.TOP}.dut.sva_DitDah32"


def vcf_row(name, status, kind=None, seconds="00:00:01"):
    fields = [name, status] + ([kind] if kind else []) + [seconds]
    return "[Info] PROP_I_RESULT: " + f"{HIER}.{fields[0]}  " + "  ".join(fields[1:])


def jg_row(name, status, seconds="0.5"):
    return f"VERDICT|{HIER}.{name}|{status}|{seconds}"


def test_vcf_reports_a_proven_assert():
    (row,) = fpv.parse_vcf(vcf_row("trap_entry_saves_pc", "proven"))
    assert (row["name"], row["status"]) == ("trap_entry_saves_pc", "proven")


def test_vcf_keeps_the_counterexample_count_on_a_falsified_assert():
    (row,) = fpv.parse_vcf(vcf_row("trap_entry_saves_pc", "falsified:1"))
    assert row["status"] == "falsified:1"


def test_a_falsified_assert_is_never_resolved():
    for status in ("falsified", "falsified:1", "falsified:12"):
        assert not fpv.resolved({"name": "trap_entry_saves_pc", "status": status})


def test_an_unknown_vendor_status_is_never_resolved():
    assert not fpv.resolved({"name": "trap_entry_saves_pc", "status": "inconclusive"})


def test_a_cover_must_be_reachable():
    assert fpv.resolved({"name": "cover_wfi_wake", "status": "covered:3"})
    assert not fpv.resolved({"name": "cover_wfi_wake", "status": "unreachable"})


def test_a_precondition_cover_must_be_reachable():
    assert fpv.resolved({"name": "axi_ar_stable:precondition1", "status": "covered"})
    assert not fpv.resolved({"name": "axi_ar_stable:precondition1", "status": "unreachable"})


def test_a_vacuous_assert_is_not_resolved():
    rows = fpv.parse_vcf(
        "\n".join(
            [
                vcf_row("mret_restores_mie", "vacuous", kind="vacuity"),
                vcf_row("mret_restores_mie", "proven"),
            ]
        )
    )
    assert [r["vacuity"] for r in rows] == ["vacuous"]
    assert not fpv.resolved(rows[0])


def test_a_non_vacuous_proven_assert_is_resolved():
    rows = fpv.parse_vcf(
        "\n".join(
            [
                vcf_row("mret_restores_mie", "non_vacuous", kind="vacuity"),
                vcf_row("mret_restores_mie", "proven"),
            ]
        )
    )
    assert fpv.resolved(rows[0])


def test_an_in_progress_row_does_not_overwrite_the_verdict():
    rows = fpv.parse_vcf(
        "\n".join(
            [
                vcf_row("wfi_wake_bounded", "checking"),
                vcf_row("wfi_wake_bounded", "proven"),
                vcf_row("wfi_wake_bounded", "checking"),
            ]
        )
    )
    assert [r["status"] for r in rows] == ["proven"]


def test_a_log_line_that_merely_carries_a_status_word_is_not_a_property():
    assert fpv.parse_vcf("[Info] the run is proven to be slow 00:00:01") == []


def test_jg_verdicts_keep_the_leaf_name():
    rows = fpv.parse_jg("\n".join([jg_row("axi_ar_stable", "proven"), "noise"]))
    assert [(r["name"], r["status"]) for r in rows] == [("axi_ar_stable", "proven")]


def test_sva_labels_finds_asserts_and_covers():
    source = """
  axi_ar_stable:
    assert property (@(posedge clock) p1);
  cover_wfi_wake: cover property (@(posedge clock) p2);
  some_signal = 1;
"""
    assert fpv.sva_labels(source) == {"axi_ar_stable", "cover_wfi_wake"}
