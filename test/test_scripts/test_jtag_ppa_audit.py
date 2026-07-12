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


def test_metrics_and_baseline():
    stats = {
        "design": {
            "num_cells": 10654,
            "num_ports": 28,
            "num_port_bits": 161,
            "num_cells_by_type": {"$_MUX_": 10, "$_SDFF_PP0_": 7},
        }
    }
    metrics = jtag_ppa_audit.metrics_from_stats(stats, 92)

    assert metrics["register_cells"] == 7
    assert jtag_ppa_audit.check_baseline(metrics)["status"] == "pass"
