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
    output        axi_aw_valid,
    output [31:0] axi_aw_bits_addr,
    output [2:0]  axi_aw_bits_prot,
    input         axi_aw_ready,
    output        axi_w_valid,
    output [31:0] axi_w_bits_data,
    output [3:0]  axi_w_bits_strb,
    input         axi_w_ready,
    input         axi_b_valid,
    output        axi_b_ready,
    input  [1:0]  axi_b_bits_resp,
    output        axi_ar_valid,
    output [31:0] axi_ar_bits_addr,
    output [2:0]  axi_ar_bits_prot,
    input         axi_ar_ready,
    input         axi_r_valid,
    output        axi_r_ready,
    input  [31:0] axi_r_bits_data,
    input  [1:0]  axi_r_bits_resp,
    input         irq_software,
    input         irq_timer,
    input         irq_external,
    output        irq_pending,
    output        status_trap,
    output        status_busy,
    output        status_sleep,
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
        .axi_aw_valid  (axi_aw_valid),
        .axi_aw_bits_addr   (axi_aw_bits_addr),
        .axi_aw_bits_prot   (axi_aw_bits_prot),
        .axi_aw_ready  (axi_aw_ready),
        .axi_w_valid   (axi_w_valid),
        .axi_w_bits_data    (axi_w_bits_data),
        .axi_w_bits_strb    (axi_w_bits_strb),
        .axi_w_ready   (axi_w_ready),
        .axi_b_valid   (axi_b_valid),
        .axi_b_ready   (axi_b_ready),
        .axi_b_bits_resp    (axi_b_bits_resp),
        .axi_ar_valid  (axi_ar_valid),
        .axi_ar_bits_addr   (axi_ar_bits_addr),
        .axi_ar_bits_prot   (axi_ar_bits_prot),
        .axi_ar_ready  (axi_ar_ready),
        .axi_r_valid   (axi_r_valid),
        .axi_r_ready   (axi_r_ready),
        .axi_r_bits_data    (axi_r_bits_data),
        .axi_r_bits_resp    (axi_r_bits_resp),
        .irq_software (irq_software),
        .irq_timer    (irq_timer),
        .irq_external (irq_external),
        .irq_pending  (irq_pending),
        .status_trap         (status_trap),
        .status_busy    (status_busy),
        .status_sleep   (status_sleep)
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
