# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import jtag_ppa_audit  # noqa: E402


def test_parse_logic_depth():
    assert jtag_ppa_audit.parse_logic_depth(
        "Longest topological path in DitDah32 (length=92):"
    ) == 92


def stats_for(baseline):
    """Yosys stats that report exactly the recorded baseline."""
    return {
        "design": {
            "num_cells": baseline["num_cells"],
            "num_ports": baseline["num_ports"],
            "num_port_bits": baseline["num_port_bits"],
            "num_cells_by_type": {"$_MUX_": 10, "$_SDFF_PP0_": 7},
        }
    }


def test_register_cells_count_only_flops():
    baseline = jtag_ppa_audit.PRODUCTION_BASELINE
    metrics = jtag_ppa_audit.metrics_from_stats(stats_for(baseline), baseline["logic_depth"])
    assert metrics["register_cells"] == 7


def test_the_recorded_baseline_passes_its_own_numbers():
    baseline = jtag_ppa_audit.PRODUCTION_BASELINE
    metrics = jtag_ppa_audit.metrics_from_stats(stats_for(baseline), baseline["logic_depth"])
    assert jtag_ppa_audit.check_baseline(metrics)["status"] == "pass"


def test_one_extra_logic_level_fails_the_baseline():
    baseline = jtag_ppa_audit.PRODUCTION_BASELINE
    metrics = jtag_ppa_audit.metrics_from_stats(stats_for(baseline), baseline["logic_depth"] + 1)
    result = jtag_ppa_audit.check_baseline(metrics)
    assert result["status"] == "fail"
    assert set(result["mismatches"]) == {"logic_depth"}


def test_one_extra_cell_fails_the_baseline():
    baseline = jtag_ppa_audit.PRODUCTION_BASELINE
    stats = stats_for(baseline)
    stats["design"]["num_cells"] += 1
    metrics = jtag_ppa_audit.metrics_from_stats(stats, baseline["logic_depth"])
    result = jtag_ppa_audit.check_baseline(metrics)
    assert result["status"] == "fail"
    assert set(result["mismatches"]) == {"num_cells"}
