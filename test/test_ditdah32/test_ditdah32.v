// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps

module test_ditdah32;
    reg clk;
    reg reset;

    wire        axi_aw_valid;
    wire [31:0] axi_aw_bits_addr;
    wire [2:0]  axi_aw_bits_prot;
    reg         axi_aw_ready;
    wire        axi_w_valid;
    wire [31:0] axi_w_bits_data;
    wire [3:0]  axi_w_bits_strb;
    reg         axi_w_ready;
    reg         axi_b_valid;
    wire        axi_b_ready;
    reg  [1:0]  axi_b_bits_resp;
    wire        axi_ar_valid;
    wire [31:0] axi_ar_bits_addr;
    wire [2:0]  axi_ar_bits_prot;
    reg         axi_ar_ready;
    reg         axi_r_valid;
    wire        axi_r_ready;
    reg  [31:0] axi_r_bits_data;
    reg  [1:0]  axi_r_bits_resp;

    reg         irq_software;
    reg         irq_timer;
    reg         irq_external;
    wire        irq_pending;
    wire        status_trap;
    wire        status_busy;
    wire        status_sleep;
    wire        trace_valid;
    wire [31:0] trace_pc;
    wire [31:0] trace_next_pc;
    wire [31:0] trace_instr;
    wire [2:0]  trace_len;
    wire        trace_rd_we;
    wire [3:0]  trace_rd;
    wire [31:0] trace_rd_wdata;
    wire [4:0]  trace_rs1_addr;
    wire [31:0] trace_rs1_rdata;
    wire [4:0]  trace_rs2_addr;
    wire [31:0] trace_rs2_rdata;
    wire [31:0] trace_mem_addr;
    wire [3:0]  trace_mem_rmask;
    wire [3:0]  trace_mem_wmask;
    wire [31:0] trace_mem_rdata;
    wire [31:0] trace_mem_wdata;
    wire        trace_mem_fault;
    wire [3:0]  trace_mem_fault_rmask;
    wire [3:0]  trace_mem_fault_wmask;
    wire [11:0] trace_csr_addr;
    wire [31:0] trace_csr_rmask;
    wire [31:0] trace_csr_wmask;
    wire [31:0] trace_csr_rdata;
    wire [31:0] trace_csr_wdata;
    wire        trace_trap;
    wire [3:0]  trace_trap_cause;
    wire [31:0] trace_mstatus;
    wire [31:0] trace_mstatus_post_commit;
    wire [31:0] trace_mstatus_pre_trap;
    wire [31:0] trace_mie;
    wire [31:0] trace_mtvec;
    wire [31:0] trace_mepc;
    wire [31:0] trace_mtval;
    wire [31:0] trace_mip;
    wire [31:0] trace_mcause;
    wire [31:0] trace_irq_pending_mask;

    initial begin
        clk = 1'b0;
        reset = 1'b1;
        axi_aw_ready = 1'b0;
        axi_w_ready = 1'b0;
        axi_b_valid = 1'b0;
        axi_b_bits_resp = 2'b00;
        axi_ar_ready = 1'b0;
        axi_r_valid = 1'b0;
        axi_r_bits_data = 32'b0;
        axi_r_bits_resp = 2'b00;
        irq_software = 1'b0;
        irq_timer = 1'b0;
        irq_external = 1'b0;
    end

    DitDah32 u_ditdah32 (
        .clock          (clk),
        .reset          (reset),
        .axi_aw_valid    (axi_aw_valid),
        .axi_aw_bits_addr     (axi_aw_bits_addr),
        .axi_aw_bits_prot     (axi_aw_bits_prot),
        .axi_aw_ready    (axi_aw_ready),
        .axi_w_valid     (axi_w_valid),
        .axi_w_bits_data      (axi_w_bits_data),
        .axi_w_bits_strb      (axi_w_bits_strb),
        .axi_w_ready     (axi_w_ready),
        .axi_b_valid     (axi_b_valid),
        .axi_b_ready     (axi_b_ready),
        .axi_b_bits_resp      (axi_b_bits_resp),
        .axi_ar_valid    (axi_ar_valid),
        .axi_ar_bits_addr     (axi_ar_bits_addr),
        .axi_ar_bits_prot     (axi_ar_bits_prot),
        .axi_ar_ready    (axi_ar_ready),
        .axi_r_valid     (axi_r_valid),
        .axi_r_ready     (axi_r_ready),
        .axi_r_bits_data      (axi_r_bits_data),
        .axi_r_bits_resp      (axi_r_bits_resp),
        .irq_software   (irq_software),
        .irq_timer      (irq_timer),
        .irq_external   (irq_external),
        .irq_pending    (irq_pending),
        .status_trap           (status_trap),
        .status_busy      (status_busy),
        .status_sleep     (status_sleep)
    );

    // The trace surface lives in the layer("DV") bind instance dV under the
    // DUT. Resolve each signal through that hierarchical path so the cocotb
    // tests keep reading dut.trace_* unchanged.
    assign trace_valid           = u_ditdah32.dV.traceValidReg;
    assign trace_pc              = u_ditdah32.dV.tracePcReg;
    assign trace_next_pc         = u_ditdah32.dV.traceNextPcReg;
    assign trace_instr           = u_ditdah32.dV.traceInstrReg;
    assign trace_len             = u_ditdah32.dV.traceLenReg;
    assign trace_rd_we           = u_ditdah32.dV.traceRdWeReg;
    assign trace_rd              = u_ditdah32.dV.traceRdReg;
    assign trace_rd_wdata        = u_ditdah32.dV.traceRdWdataReg;
    assign trace_rs1_addr        = u_ditdah32.dV.traceRs1AddrReg;
    assign trace_rs1_rdata       = u_ditdah32.dV.traceRs1RdataReg;
    assign trace_rs2_addr        = u_ditdah32.dV.traceRs2AddrReg;
    assign trace_rs2_rdata       = u_ditdah32.dV.traceRs2RdataReg;
    assign trace_mem_addr        = u_ditdah32.dV.traceMemAddrReg;
    assign trace_mem_rmask       = u_ditdah32.dV.traceMemRmaskReg;
    assign trace_mem_wmask       = u_ditdah32.dV.traceMemWmaskReg;
    assign trace_mem_rdata       = u_ditdah32.dV.traceMemRdataReg;
    assign trace_mem_wdata       = u_ditdah32.dV.traceMemWdataReg;
    assign trace_mem_fault       = u_ditdah32.dV.traceMemFaultReg;
    assign trace_mem_fault_rmask = u_ditdah32.dV.traceMemFaultRmaskReg;
    assign trace_mem_fault_wmask = u_ditdah32.dV.traceMemFaultWmaskReg;
    assign trace_csr_addr        = u_ditdah32.dV.traceCsrAddrReg;
    assign trace_csr_rmask       = u_ditdah32.dV.traceCsrRmaskReg;
    assign trace_csr_wmask       = u_ditdah32.dV.traceCsrWmaskReg;
    assign trace_csr_rdata       = u_ditdah32.dV.traceCsrRdataReg;
    assign trace_csr_wdata       = u_ditdah32.dV.traceCsrWdataReg;
    assign trace_trap            = u_ditdah32.dV.traceTrapReg;
    assign trace_trap_cause      = u_ditdah32.dV.traceTrapCauseReg;
    assign trace_mstatus         = u_ditdah32.dV.traceMstatusWire;
    assign trace_mstatus_post_commit = u_ditdah32.dV.tracePostCommitMstatusReg;
    assign trace_mstatus_pre_trap = u_ditdah32.dV.tracePreTrapMstatusReg;
    assign trace_mie             = u_ditdah32.dV.traceMieWire;
    assign trace_mtvec           = u_ditdah32.dV.traceMtvecWire;
    assign trace_mepc            = u_ditdah32.dV.traceMepcWire;
    assign trace_mtval           = u_ditdah32.dV.traceMtvalWire;
    assign trace_mip             = u_ditdah32.dV.traceMipWire;
    assign trace_mcause          = u_ditdah32.dV.traceMcauseWire;
    assign trace_irq_pending_mask = u_ditdah32.dV.traceIrqPendingMaskReg;
endmodule
