#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import json
import sys


TRACE_FIELDS = (
    "pc",
    "insn",
    "length",
    "rd_we",
    "rd",
    "rd_wdata",
    "mem_addr",
    "mem_rdata",
    "mem_wdata",
    "trap",
    "trap_cause",
)


def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as trace_file:
        for line_no, line in enumerate(trace_file, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                records.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return records


def compare(expected, actual):
    if len(expected) != len(actual):
        return f"trace length mismatch: expected {len(expected)}, got {len(actual)}"

    for index, (exp, act) in enumerate(zip(expected, actual)):
        for field in TRACE_FIELDS:
            if exp.get(field) != act.get(field):
                return (
                    f"trace mismatch at item {index}, field {field}: "
                    f"expected {exp.get(field)!r}, got {act.get(field)!r}"
                )

    return None


def main():
    parser = argparse.ArgumentParser(description="Compare RV32EC JSONL traces")
    parser.add_argument("expected", help="reference ISS trace in JSONL format")
    parser.add_argument("actual", help="RTL trace in JSONL format")
    args = parser.parse_args()

    error = compare(load_jsonl(args.expected), load_jsonl(args.actual))
    if error:
        print(error, file=sys.stderr)
        return 1

    print("trace match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
