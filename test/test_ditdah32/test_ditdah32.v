// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps

module test_ditdah32;
    reg clk;
    reg reset;

    wire        axi_awvalid;
    wire [31:0] axi_awaddr;
    wire [2:0]  axi_awprot;
    reg         axi_awready;
    wire        axi_wvalid;
    wire [31:0] axi_wdata;
    wire [3:0]  axi_wstrb;
    reg         axi_wready;
    reg         axi_bvalid;
    wire        axi_bready;
    reg  [1:0]  axi_bresp;
    wire        axi_arvalid;
    wire [31:0] axi_araddr;
    wire [2:0]  axi_arprot;
    reg         axi_arready;
    reg         axi_rvalid;
    wire        axi_rready;
    reg  [31:0] axi_rdata;
    reg  [1:0]  axi_rresp;

    reg         irq_software;
    reg         irq_timer;
    reg         irq_external;
    wire        irq_pending;
    wire        trap;
    wire        core_busy;
    wire        core_sleep;
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
    wire [31:0] trace_mstatus_pre_trap;
    wire [31:0] trace_mip;
    wire [31:0] trace_mcause;

    initial begin
        clk = 1'b0;
        reset = 1'b1;
        axi_awready = 1'b0;
        axi_wready = 1'b0;
        axi_bvalid = 1'b0;
        axi_bresp = 2'b00;
        axi_arready = 1'b0;
        axi_rvalid = 1'b0;
        axi_rdata = 32'b0;
        axi_rresp = 2'b00;
        irq_software = 1'b0;
        irq_timer = 1'b0;
        irq_external = 1'b0;
    end

    DitDah32 u_ditdah32 (
        .clock          (clk),
        .reset          (reset),
        .axi_awvalid    (axi_awvalid),
        .axi_awaddr     (axi_awaddr),
        .axi_awprot     (axi_awprot),
        .axi_awready    (axi_awready),
        .axi_wvalid     (axi_wvalid),
        .axi_wdata      (axi_wdata),
        .axi_wstrb      (axi_wstrb),
        .axi_wready     (axi_wready),
        .axi_bvalid     (axi_bvalid),
        .axi_bready     (axi_bready),
        .axi_bresp      (axi_bresp),
        .axi_arvalid    (axi_arvalid),
        .axi_araddr     (axi_araddr),
        .axi_arprot     (axi_arprot),
        .axi_arready    (axi_arready),
        .axi_rvalid     (axi_rvalid),
        .axi_rready     (axi_rready),
        .axi_rdata      (axi_rdata),
        .axi_rresp      (axi_rresp),
        .irq_software   (irq_software),
        .irq_timer      (irq_timer),
        .irq_external   (irq_external),
        .irq_pending    (irq_pending),
        .trap           (trap),
        .core_busy      (core_busy),
        .core_sleep     (core_sleep)
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
    assign trace_mstatus_pre_trap = u_ditdah32.dV.tracePreTrapMstatusReg;
    assign trace_mip             = u_ditdah32.dV.traceMipWire;
    assign trace_mcause          = u_ditdah32.dV.traceMcauseWire;
endmodule
