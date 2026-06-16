# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import trace_config_audit  # noqa: E402


TRACE_HEADER = """
module DitDah32(
  input clock,
  output trace_valid,
  output [31:0] trace_pc,
  output [31:0] trace_next_pc,
  output [31:0] trace_instr,
  output [2:0] trace_len,
  output trace_rd_we,
  output [3:0] trace_rd,
  output [31:0] trace_rd_wdata,
  output [4:0] trace_rs1_addr,
  output [31:0] trace_rs1_rdata,
  output [4:0] trace_rs2_addr,
  output [31:0] trace_rs2_rdata,
  output [31:0] trace_mem_addr,
  output [3:0] trace_mem_rmask,
  output [3:0] trace_mem_wmask,
  output [31:0] trace_mem_rdata,
  output [31:0] trace_mem_wdata,
  output [11:0] trace_csr_addr,
  output [31:0] trace_csr_rmask,
  output [31:0] trace_csr_wmask,
  output [31:0] trace_csr_rdata,
  output [31:0] trace_csr_wdata,
  output trace_trap,
  output [3:0] trace_trap_cause
);
endmodule
"""


NO_TRACE_HEADER = """
module DitDah32(
  input clock,
  output trap
);
endmodule
"""


def test_main_module_rejects_trace_ports_in_verification_build():
    # The trace surface lives in the DV bind collateral, so the main module
    # must be trace-free even when verification collateral is expected.
    result = trace_config_audit.check_module_text(TRACE_HEADER, expect_trace=True)

    assert result["status"] == "fail"
    assert "main module exposes trace ports" in result["missing"][0]


def test_main_module_rejects_trace_ports_in_production_build():
    result = trace_config_audit.check_module_text(TRACE_HEADER, expect_trace=False)

    assert result["status"] == "fail"
    assert "main module exposes trace ports" in result["missing"][0]


def test_clean_main_module_passes_both_builds():
    for expect_trace in (True, False):
        result = trace_config_audit.check_module_text(NO_TRACE_HEADER, expect_trace=expect_trace)
        assert result["status"] == "pass"
        assert result["missing"] == []


def test_main_module_rejects_internal_trace_state():
    verilog = """
module DitDah32(
  input clock,
  output trap
);
  reg traceValidReg;
endmodule
"""

    result = trace_config_audit.check_module_text(verilog, expect_trace=False)

    assert result["status"] == "fail"
    assert result["missing"] == ["DitDah32 main module contains trace state or wiring: traceValidReg"]


def test_header_rejects_direct_rvfi_ports():
    verilog = """
module DitDah32(
  input clock,
  output rvfi_valid
);
endmodule
"""

    result = trace_config_audit.check_module_text(verilog, expect_trace=False)

    assert result["status"] == "fail"
    assert result["missing"] == ["Core top-level exposes direct RVFI ports: rvfi_valid"]
