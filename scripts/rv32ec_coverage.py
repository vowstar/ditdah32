#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Evidence:
    path: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class CoverageItem:
    item_id: str
    category: str
    scope: str
    evidence: tuple[Evidence, ...]


def ev(path, *tokens):
    return Evidence(path, tuple(tokens))


def item(item_id, category, scope, *evidence):
    return CoverageItem(item_id, category, scope, tuple(evidence))


LEGAL_RV32E = [
    item("LUI", "legal_rv32e", "upper_immediate", ev("scripts/rv32ec_isa_regress.py", "lui x1")),
    item("AUIPC", "legal_rv32e", "upper_immediate", ev("scripts/rv32ec_isa_regress.py", "auipc x2")),
    item("JAL", "legal_rv32e", "jump", ev("test/test_ditdah32/test_ditdah32.py", "j_type(8, 4)")),
    item("JALR", "legal_rv32e", "jump", ev("test/test_ditdah32/test_ditdah32.py", "i_type(8, 4, 0x0, 5, 0x67)")),
    item("BEQ", "legal_rv32e", "branch", ev("test/test_ditdah32/test_ditdah32.py", "b_type(8, 2, 1, 0x0)")),
    item("BNE", "legal_rv32e", "branch", ev("test/test_ditdah32/test_ditdah32.py", "b_type(8, 2, 1, 0x1)")),
    item("BLT", "legal_rv32e", "branch", ev("test/test_ditdah32/test_ditdah32.py", "b_type(8, 2, 3, 0x4)")),
    item("BGE", "legal_rv32e", "branch", ev("test/test_ditdah32/test_ditdah32.py", "b_type(8, 2, 3, 0x5)")),
    item("BLTU", "legal_rv32e", "branch", ev("test/test_ditdah32/test_ditdah32.py", "b_type(8, 2, 3, 0x6)")),
    item("BGEU", "legal_rv32e", "branch", ev("test/test_ditdah32/test_ditdah32.py", "b_type(8, 2, 3, 0x7)")),
    item("LB", "legal_rv32e", "load", ev("test/test_ditdah32/test_ditdah32.py", "lb x3")),
    item("LH", "legal_rv32e", "load", ev("test/test_ditdah32/test_ditdah32.py", "lh x5")),
    item("LW", "legal_rv32e", "load", ev("test/test_ditdah32/test_ditdah32.py", "lw x7")),
    item("LBU", "legal_rv32e", "load", ev("test/test_ditdah32/test_ditdah32.py", "lbu x4")),
    item("LHU", "legal_rv32e", "load", ev("test/test_ditdah32/test_ditdah32.py", "lhu x6")),
    item("SB", "legal_rv32e", "store", ev("test/test_ditdah32/test_ditdah32.py", "sb x2")),
    item("SH", "legal_rv32e", "store", ev("test/test_ditdah32/test_ditdah32.py", "sh x2")),
    item("SW", "legal_rv32e", "store", ev("scripts/rv32ec_isa_regress.py", "sw x2")),
    item("ADDI", "legal_rv32e", "alu_immediate", ev("test/test_ditdah32/test_ditdah32.py", "# addi")),
    item("SLTI", "legal_rv32e", "alu_immediate", ev("test/test_ditdah32/test_ditdah32.py", "# slti")),
    item("SLTIU", "legal_rv32e", "alu_immediate", ev("test/test_ditdah32/test_ditdah32.py", "# sltiu")),
    item("XORI", "legal_rv32e", "alu_immediate", ev("test/test_ditdah32/test_ditdah32.py", "# xori")),
    item("ORI", "legal_rv32e", "alu_immediate", ev("test/test_ditdah32/test_ditdah32.py", "# ori")),
    item("ANDI", "legal_rv32e", "alu_immediate", ev("test/test_ditdah32/test_ditdah32.py", "# andi")),
    item("SLLI", "legal_rv32e", "alu_immediate", ev("test/test_ditdah32/test_ditdah32.py", "# slli")),
    item("SRLI", "legal_rv32e", "alu_immediate", ev("test/test_ditdah32/test_ditdah32.py", "# srli")),
    item("SRAI", "legal_rv32e", "alu_immediate", ev("test/test_ditdah32/test_ditdah32.py", "# srai")),
    item("ADD", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# add")),
    item("SUB", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# sub")),
    item("SLL", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# sll")),
    item("SLT", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# slt")),
    item("SLTU", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# sltu")),
    item("XOR", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# xor")),
    item("SRL", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# srl")),
    item("SRA", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# sra")),
    item("OR", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# or")),
    item("AND", "legal_rv32e", "alu_register", ev("test/test_ditdah32/test_ditdah32.py", "# and")),
    item("FENCE", "legal_rv32e", "ordering", ev("test/test_ditdah32/test_ditdah32.py", "assert_trace(traces[19], 76, FENCE)")),
    item("ECALL", "legal_rv32e", "trap", ev("test/test_ditdah32/test_ditdah32.py", "ECALL, trap=True")),
    item("EBREAK", "legal_rv32e", "trap", ev("test/test_ditdah32/test_ditdah32.py", "EBREAK, trap=True")),
]


LEGAL_RV32EC = [
    item("C.NOP", "legal_rv32ec", "constant", ev("test/test_ditdah32/test_ditdah32.py", "compressed_halfwords_advance_pc_by_two")),
    item("C.ADDI", "legal_rv32ec", "constant", ev("scripts/rv32ec_isa_regress.py", "c.addi x1")),
    item("C.LI", "legal_rv32ec", "constant", ev("scripts/rv32ec_isa_regress.py", "c.li x8")),
    item("C.LUI", "legal_rv32ec", "constant", ev("scripts/rv32ec_isa_regress.py", "c.lui x4")),
    item("C.ADDI16SP", "legal_rv32ec", "constant", ev("scripts/rv32ec_isa_regress.py", "c.addi16sp")),
    item("C.ADDI4SPN", "legal_rv32ec", "constant", ev("scripts/rv32ec_isa_regress.py", "c.addi4spn")),
    item("C.LW", "legal_rv32ec", "load_store", ev("scripts/rv32ec_isa_regress.py", "c.lw x10")),
    item("C.SW", "legal_rv32ec", "load_store", ev("scripts/rv32ec_isa_regress.py", "c.sw x9")),
    item("C.LWSP", "legal_rv32ec", "load_store", ev("scripts/rv32ec_isa_regress.py", "c.lwsp x11")),
    item("C.SWSP", "legal_rv32ec", "load_store", ev("scripts/rv32ec_isa_regress.py", "c.swsp x10")),
    item("C.J", "legal_rv32ec", "control_flow", ev("scripts/rv32ec_isa_regress.py", "c.j +4")),
    item("C.JAL", "legal_rv32ec", "control_flow", ev("test/test_ditdah32/test_ditdah32.py", "c_j(0x1, 4)")),
    item("C.JR", "legal_rv32ec", "control_flow", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_jr_and_jalr")),
    item("C.JALR", "legal_rv32ec", "control_flow", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_jr_and_jalr")),
    item("C.BEQZ", "legal_rv32ec", "control_flow", ev("scripts/rv32ec_isa_regress.py", "c.beqz x8")),
    item("C.BNEZ", "legal_rv32ec", "control_flow", ev("scripts/rv32ec_isa_regress.py", "c.bnez x9")),
    item("C.SLLI", "legal_rv32ec", "alu", ev("scripts/rv32ec_isa_regress.py", "c.slli x2")),
    item("C.SRLI", "legal_rv32ec", "alu", ev("test/test_ditdah32/test_ditdah32.py", "c_shift_andi(0x0, 10, 1)")),
    item("C.SRAI", "legal_rv32ec", "alu", ev("test/test_ditdah32/test_ditdah32.py", "c_shift_andi(0x1, 11, 1)")),
    item("C.ANDI", "legal_rv32ec", "alu", ev("test/test_ditdah32/test_ditdah32.py", "c_shift_andi(0x2, 11, -1)")),
    item("C.SUB", "legal_rv32ec", "alu", ev("test/test_ditdah32/test_ditdah32.py", "c_ca(0x0, 8, 9)")),
    item("C.XOR", "legal_rv32ec", "alu", ev("test/test_ditdah32/test_ditdah32.py", "c_ca(0x1, 8, 9)")),
    item("C.OR", "legal_rv32ec", "alu", ev("test/test_ditdah32/test_ditdah32.py", "c_ca(0x2, 8, 9)")),
    item("C.AND", "legal_rv32ec", "alu", ev("test/test_ditdah32/test_ditdah32.py", "c_ca(0x3, 8, 9)")),
    item("C.MV", "legal_rv32ec", "alu", ev("scripts/rv32ec_isa_regress.py", "c.mv x2")),
    item("C.ADD", "legal_rv32ec", "alu", ev("scripts/rv32ec_isa_regress.py", "c.add x2")),
]


LEGAL_ZICSR = [
    item("CSRRW", "legal_zicsr", "csr", ev("test/test_ditdah32/test_ditdah32.py", "csrrw(CSR_MTVEC")),
    item("CSRRS", "legal_zicsr", "csr", ev("test/test_ditdah32/test_ditdah32.py", "csrrs(CSR_MTVEC")),
    item("CSRRC", "legal_zicsr", "csr", ev("test/test_ditdah32/test_ditdah32.py", "csrrc(CSR_MSCRATCH")),
    item("CSRRWI", "legal_zicsr", "csr", ev("test/test_ditdah32/test_ditdah32.py", "csrrwi(CSR_MSCRATCH")),
    item("CSRRSI", "legal_zicsr", "csr", ev("test/test_ditdah32/test_ditdah32.py", "csrrsi(CSR_MSTATUS")),
    item("CSRRCI", "legal_zicsr", "csr", ev("test/test_ditdah32/test_ditdah32.py", "csrrci(CSR_MSCRATCH")),
]


CONTROL_PROFILE = [
    item("MRET", "control_profile", "system", ev("test/test_ditdah32/test_ditdah32.py", "MRET")),
    item("WFI", "control_profile", "system", ev("test/test_ditdah32/test_ditdah32.py", "core_sleep")),
    item("wfi_wake_without_global_mie", "control_profile", "system", ev("test/test_ditdah32/test_ditdah32.py", "wfi_wakes_without_trap_when_global_mie_is_clear")),
    item("machine_software_interrupt", "control_profile", "interrupt", ev("test/test_ditdah32/test_ditdah32.py", "MCAUSE_IRQ_SOFTWARE")),
    item("machine_timer_interrupt", "control_profile", "interrupt", ev("test/test_ditdah32/test_ditdah32.py", "MCAUSE_IRQ_TIMER")),
    item("machine_external_interrupt", "control_profile", "interrupt", ev("test/test_ditdah32/test_ditdah32.py", "MCAUSE_IRQ_EXTERNAL")),
    item("level_sensitive_irq_reentry", "control_profile", "interrupt", ev("test/test_ditdah32/test_ditdah32.py", "level_sensitive_interrupt_reenters_after_mret_if_source_stays_high")),
    item("direct_mtvec_trap_entry", "control_profile", "trap", ev("test/test_ditdah32/test_ditdah32.py", "csrrw(CSR_MTVEC")),
    item("mtvec_mepc_low_bit_masks", "control_profile", "csr", ev("test/test_ditdah32/test_ditdah32.py", "zicsr_mtvec_and_mepc_mask_low_bits")),
    item("csr_zimm16_operand", "control_profile", "csr", ev("test/test_ditdah32/test_ditdah32.py", "zicsr_zimm16_is_not_rv32e_register_violation")),
    item("csr_reference_model", "control_profile", "model", ev("test/test_model/test_rv32ec_model.py", "test_zicsr_machine_csrs_and_wfi_model_behavior")),
    item("zicsr_isa_artifact", "control_profile", "isa_artifact", ev("scripts/rv32ec_isa_regress.py", "rv32ec_zicsr_wfi")),
]


ILLEGAL_CLASSES = [
    item("rv32e_x16_x31_register", "illegal_class", "register", ev("test/test_ditdah32/test_ditdah32.py", "rv32e_register_index_violation_traps")),
    item("unknown_32bit_instruction", "illegal_class", "decode", ev("test/test_ditdah32/test_ditdah32.py", "rv32e_unknown_32bit_instruction_traps")),
    item("fence_i", "illegal_class", "decode", ev("test/test_ditdah32/test_ditdah32.py", "rv32e_fence_i_traps")),
    item("read_only_csr_write", "illegal_class", "csr", ev("test/test_ditdah32/test_ditdah32.py", "zicsr_read_only_csr_write_traps")),
    item("unimplemented_csr_access", "illegal_class", "csr", ev("test/test_ditdah32/test_ditdah32.py", "zicsr_unimplemented_csr_access_traps")),
    item("csr_rv32e_rd_index", "illegal_class", "csr", ev("test/test_ditdah32/test_ditdah32.py", "zicsr_rv32e_rd_index_violation_traps")),
    item("csr_rv32e_rs1_index", "illegal_class", "csr", ev("test/test_ditdah32/test_ditdah32.py", "zicsr_rv32e_rs1_index_violation_traps")),
    item("load_misaligned", "illegal_class", "memory", ev("test/test_ditdah32/test_ditdah32.py", "rv32e_misaligned_load_traps_without_data_axi")),
    item("store_misaligned", "illegal_class", "memory", ev("test/test_ditdah32/test_ditdah32.py", "rv32e_misaligned_store_traps_without_data_axi")),
    item("compressed_all_zero", "illegal_class", "compressed", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_all_zero_traps")),
    item("compressed_addi4spn_zero", "illegal_class", "compressed", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_addi4spn_zero_traps")),
    item("compressed_addi16sp_zero", "illegal_class", "compressed", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_addi16sp_zero_traps")),
    item("compressed_lui_zero", "illegal_class", "compressed", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_lui_zero_traps")),
    item("compressed_lwsp_x0", "illegal_class", "compressed", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_lwsp_x0_traps")),
    item("compressed_jr_x0", "illegal_class", "compressed", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_jr_x0_traps")),
    item("compressed_rv64_shift", "illegal_class", "compressed", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_rv64_shift_encoding_traps")),
    item("compressed_floating_point", "illegal_class", "compressed", ev("test/test_ditdah32/test_ditdah32.py", "rv32ec_compressed_floating_point_encoding_traps")),
    item("axi_fetch_non_okay", "illegal_class", "axi", ev("test/test_ditdah32/test_ditdah32.py", "axi_fetch_non_okay_response_traps")),
    item("axi_load_non_okay", "illegal_class", "axi", ev("test/test_ditdah32/test_ditdah32.py", "axi_load_non_okay_response_traps_without_writeback")),
    item("axi_store_non_okay", "illegal_class", "axi", ev("test/test_ditdah32/test_ditdah32.py", "axi_store_non_okay_response_traps_without_normal_commit")),
]


ITEMS = LEGAL_RV32E + LEGAL_RV32EC + LEGAL_ZICSR + CONTROL_PROFILE + ILLEGAL_CLASSES


def read_text(path):
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return None
    return full_path.read_text(encoding="utf-8")


def check_evidence(evidence):
    text = read_text(evidence.path)
    if text is None:
        return False
    return all(token in text for token in evidence.tokens)


def item_record(coverage_item):
    evidence_records = []
    covered = False
    for evidence in coverage_item.evidence:
        evidence_ok = check_evidence(evidence)
        covered = covered or evidence_ok
        evidence_records.append(
            {
                "path": evidence.path,
                "tokens": list(evidence.tokens),
                "status": "covered" if evidence_ok else "missing",
            }
        )

    return {
        "id": coverage_item.item_id,
        "category": coverage_item.category,
        "scope": coverage_item.scope,
        "status": "covered" if covered else "missing",
        "evidence": evidence_records,
    }


def artifact_status():
    matrix_path = REPO_ROOT / "result" / "rtl_trace" / "isa_artifacts" / "matrix.json"
    if not matrix_path.exists():
        return {"rtl_isa_matrix": "missing", "path": str(matrix_path.relative_to(REPO_ROOT))}
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    return {
        "rtl_isa_matrix": matrix.get("status", "unknown"),
        "path": str(matrix_path.relative_to(REPO_ROOT)),
        "random_artifacts": sum(1 for item in matrix.get("artifacts", []) if str(item.get("name", "")).startswith("rv32ec_random_")),
        "artifacts": [
            {"name": item.get("name"), "status": item.get("status")}
            for item in matrix.get("artifacts", [])
        ],
    }


def write_markdown(path, report):
    lines = [
        "# DitDah32 RV32EC Coverage Report",
        "",
        f"Status: `{report['status']}`",
        "",
        "## Summary",
        "",
        f"- Covered: {report['summary']['covered']}",
        f"- Missing: {report['summary']['missing']}",
        f"- Total: {report['summary']['total']}",
        f"- RTL ISA matrix: `{report['artifacts']['rtl_isa_matrix']}`",
        "",
        "## Items",
        "",
        "| ID | Category | Scope | Status |",
        "| --- | --- | --- | --- |",
    ]
    for record in report["items"]:
        lines.append(
            f"| `{record['id']}` | `{record['category']}` | `{record['scope']}` | `{record['status']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate DitDah32 RV32EC functional coverage report")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "result" / "coverage")
    parser.add_argument("--require-artifacts", action="store_true")
    args = parser.parse_args()

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = [item_record(coverage_item) for coverage_item in ITEMS]
    missing = [record for record in records if record["status"] != "covered"]
    artifacts = artifact_status()
    artifact_failed = args.require_artifacts and artifacts["rtl_isa_matrix"] != "pass"
    status = "fail" if missing or artifact_failed else "pass"

    report = {
        "status": status,
        "summary": {
            "covered": len(records) - len(missing),
            "missing": len(missing),
            "total": len(records),
        },
        "artifacts": artifacts,
        "items": records,
        "missing_items": [record["id"] for record in missing],
    }

    json_path = out_dir / "rv32ec_coverage.json"
    md_path = out_dir / "rv32ec_coverage.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_path, report)

    print(f"coverage {status}: {report['summary']['covered']}/{report['summary']['total']} items covered")
    print(f"json: {json_path.relative_to(REPO_ROOT)}")
    print(f"markdown: {md_path.relative_to(REPO_ROOT)}")
    if missing:
        print("missing: " + ", ".join(report["missing_items"]), file=sys.stderr)
    if artifact_failed:
        print(f"RTL ISA matrix status is {artifacts['rtl_isa_matrix']}", file=sys.stderr)
    return 1 if status != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
