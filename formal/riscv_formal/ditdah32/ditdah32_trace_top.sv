// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT

// Trace bridge for the formal flow. The architectural trace surface lives in
// the CIRCT layer("DV") bind collateral (DitDah32_DV / ref_DitDah32.sv), not on
// the DitDah32 port list. read_slang resolves the probe XMRs here and re-exposes
// them as ordinary ports so the riscv-formal harness, read with yosys read -sv,
// can drive RVFI from plain port connections (preserving $anyseq / $initstate).
`include "ref_DitDah32.sv"

module ditdah32_trace_top (
    input         clock,
    input         reset,
    output        axi_awvalid,
    output [31:0] axi_awaddr,
    output [2:0]  axi_awprot,
    input         axi_awready,
    output        axi_wvalid,
    output [31:0] axi_wdata,
    output [3:0]  axi_wstrb,
    input         axi_wready,
    input         axi_bvalid,
    output        axi_bready,
    input  [1:0]  axi_bresp,
    output        axi_arvalid,
    output [31:0] axi_araddr,
    output [2:0]  axi_arprot,
    input         axi_arready,
    input         axi_rvalid,
    output        axi_rready,
    input  [31:0] axi_rdata,
    input  [1:0]  axi_rresp,
    input         irq_software,
    input         irq_timer,
    input         irq_external,
    output        irq_pending,
    output        trap,
    output        core_busy,
    output        core_sleep,
    output        trace_valid,
    output [31:0] trace_pc,
    output [31:0] trace_next_pc,
    output [31:0] trace_instr,
    output [2:0]  trace_len,
    output        trace_rd_we,
    output [4:0]  trace_rd,
    output [31:0] trace_rd_wdata,
    output [4:0]  trace_rs1_addr,
    output [31:0] trace_rs1_rdata,
    output [4:0]  trace_rs2_addr,
    output [31:0] trace_rs2_rdata,
    output [31:0] trace_mem_addr,
    output [3:0]  trace_mem_rmask,
    output [3:0]  trace_mem_wmask,
    output [31:0] trace_mem_rdata,
    output [31:0] trace_mem_wdata,
    output        trace_mem_fault,
    output [3:0]  trace_mem_fault_rmask,
    output [3:0]  trace_mem_fault_wmask,
    output [11:0] trace_csr_addr,
    output [31:0] trace_csr_rmask,
    output [31:0] trace_csr_wmask,
    output [31:0] trace_csr_rdata,
    output [31:0] trace_csr_wdata,
    output        trace_trap,
    output [3:0]  trace_trap_cause,
    output [31:0] trace_mstatus,
    output [31:0] trace_mstatus_pre_trap,
    output [31:0] trace_mip,
    output [31:0] trace_mcause
);
    DitDah32 dut (
        .clock        (clock),
        .reset        (reset),
        .axi_awvalid  (axi_awvalid),
        .axi_awaddr   (axi_awaddr),
        .axi_awprot   (axi_awprot),
        .axi_awready  (axi_awready),
        .axi_wvalid   (axi_wvalid),
        .axi_wdata    (axi_wdata),
        .axi_wstrb    (axi_wstrb),
        .axi_wready   (axi_wready),
        .axi_bvalid   (axi_bvalid),
        .axi_bready   (axi_bready),
        .axi_bresp    (axi_bresp),
        .axi_arvalid  (axi_arvalid),
        .axi_araddr   (axi_araddr),
        .axi_arprot   (axi_arprot),
        .axi_arready  (axi_arready),
        .axi_rvalid   (axi_rvalid),
        .axi_rready   (axi_rready),
        .axi_rdata    (axi_rdata),
        .axi_rresp    (axi_rresp),
        .irq_software (irq_software),
        .irq_timer    (irq_timer),
        .irq_external (irq_external),
        .irq_pending  (irq_pending),
        .trap         (trap),
        .core_busy    (core_busy),
        .core_sleep   (core_sleep)
    );

    assign trace_valid           = dut.`ref_DitDah32_trace_valid;
    assign trace_pc              = dut.`ref_DitDah32_trace_pc;
    assign trace_next_pc         = dut.`ref_DitDah32_trace_next_pc;
    assign trace_instr           = dut.`ref_DitDah32_trace_instr;
    assign trace_len             = dut.`ref_DitDah32_trace_len;
    assign trace_rd_we           = dut.`ref_DitDah32_trace_rd_we;
    assign trace_rd              = dut.`ref_DitDah32_trace_rd;
    assign trace_rd_wdata        = dut.`ref_DitDah32_trace_rd_wdata;
    assign trace_rs1_addr        = dut.`ref_DitDah32_trace_rs1_addr;
    assign trace_rs1_rdata       = dut.`ref_DitDah32_trace_rs1_rdata;
    assign trace_rs2_addr        = dut.`ref_DitDah32_trace_rs2_addr;
    assign trace_rs2_rdata       = dut.`ref_DitDah32_trace_rs2_rdata;
    assign trace_mem_addr        = dut.`ref_DitDah32_trace_mem_addr;
    assign trace_mem_rmask       = dut.`ref_DitDah32_trace_mem_rmask;
    assign trace_mem_wmask       = dut.`ref_DitDah32_trace_mem_wmask;
    assign trace_mem_rdata       = dut.`ref_DitDah32_trace_mem_rdata;
    assign trace_mem_wdata       = dut.`ref_DitDah32_trace_mem_wdata;
    assign trace_mem_fault       = dut.`ref_DitDah32_trace_mem_fault;
    assign trace_mem_fault_rmask = dut.`ref_DitDah32_trace_mem_fault_rmask;
    assign trace_mem_fault_wmask = dut.`ref_DitDah32_trace_mem_fault_wmask;
    assign trace_csr_addr        = dut.`ref_DitDah32_trace_csr_addr;
    assign trace_csr_rmask       = dut.`ref_DitDah32_trace_csr_rmask;
    assign trace_csr_wmask       = dut.`ref_DitDah32_trace_csr_wmask;
    assign trace_csr_rdata       = dut.`ref_DitDah32_trace_csr_rdata;
    assign trace_csr_wdata       = dut.`ref_DitDah32_trace_csr_wdata;
    assign trace_trap            = dut.`ref_DitDah32_trace_trap;
    assign trace_trap_cause      = dut.`ref_DitDah32_trace_trap_cause;
    assign trace_mstatus         = dut.`ref_DitDah32_trace_mstatus;
    assign trace_mstatus_pre_trap = dut.`ref_DitDah32_trace_mstatus_pre_trap;
    assign trace_mip             = dut.`ref_DitDah32_trace_mip;
    assign trace_mcause          = dut.`ref_DitDah32_trace_mcause;
endmodule
