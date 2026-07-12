# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import runpy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_static_coverage_evidence_is_complete():
    coverage = runpy.run_path(REPO_ROOT / "scripts" / "rv32ec_coverage.py")
    records = [coverage["item_record"](item) for item in coverage["ITEMS"]]
    missing = [record["id"] for record in records if record["status"] != "covered"]

    assert missing == []
