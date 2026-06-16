// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT

module rvfi_wrapper (
    input clock,
    input reset,
    `RVFI_OUTPUTS
    `RVFI_BUS_OUTPUTS
);
    (* keep *) `rvformal_rand_reg [31:0] axi_rdata;
`ifdef DITDAH32_RVFI_ENABLE_IRQ
    (* keep *) `rvformal_rand_reg irq_software;
    (* keep *) `rvformal_rand_reg irq_timer;
    (* keep *) `rvformal_rand_reg irq_external;
`else
    wire irq_software = 1'b0;
    wire irq_timer = 1'b0;
    wire irq_external = 1'b0;
`endif

    wire        axi_awvalid;
    wire [31:0] axi_awaddr;
    wire [2:0]  axi_awprot;
    wire        axi_awready;
    wire        axi_wvalid;
    wire [31:0] axi_wdata;
    wire [3:0]  axi_wstrb;
    wire        axi_wready;
    wire        axi_bvalid;
    wire        axi_bready;
    wire [1:0]  axi_bresp;
    wire        axi_arvalid;
    wire [31:0] axi_araddr;
    wire [2:0]  axi_arprot;
    wire        axi_arready;
    wire        axi_rvalid;
    wire        axi_rready;
    wire [1:0]  axi_rresp;
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
`ifdef DITDAH32_RVFI_CSR_TRACE
    wire [11:0] trace_csr_addr;
    wire [31:0] trace_csr_rmask;
    wire [31:0] trace_csr_wmask;
    wire [31:0] trace_csr_rdata;
    wire [31:0] trace_csr_wdata;
`endif
    wire        trace_trap;
    wire [3:0]  trace_trap_cause;
    wire [31:0] trace_mstatus;
    wire [31:0] trace_mstatus_pre_trap;
    wire [31:0] trace_mip;
    wire [31:0] trace_mcause;

    ditdah32_trace_top dut (
        .clock(clock),
        .reset(reset),
        .axi_awvalid(axi_awvalid),
        .axi_awaddr(axi_awaddr),
        .axi_awprot(axi_awprot),
        .axi_awready(axi_awready),
        .axi_wvalid(axi_wvalid),
        .axi_wdata(axi_wdata),
        .axi_wstrb(axi_wstrb),
        .axi_wready(axi_wready),
        .axi_bvalid(axi_bvalid),
        .axi_bready(axi_bready),
        .axi_bresp(axi_bresp),
        .axi_arvalid(axi_arvalid),
        .axi_araddr(axi_araddr),
        .axi_arprot(axi_arprot),
        .axi_arready(axi_arready),
        .axi_rvalid(axi_rvalid),
        .axi_rready(axi_rready),
        .axi_rdata(axi_rdata),
        .axi_rresp(axi_rresp),
        .irq_software(irq_software),
        .irq_timer(irq_timer),
        .irq_external(irq_external),
        .irq_pending(irq_pending),
        .trap(trap),
        .core_busy(core_busy),
        .core_sleep(core_sleep),
        // The trace surface lives in the layer("DV") bind collateral. The
        // ditdah32_trace_top bridge (read via read_slang) resolves the probe
        // XMRs and re-exposes them as ports for the riscv-formal harness.
        .trace_valid(trace_valid),
        .trace_pc(trace_pc),
        .trace_next_pc(trace_next_pc),
        .trace_instr(trace_instr),
        .trace_len(trace_len),
        .trace_rd_we(trace_rd_we),
        .trace_rd(trace_rd),
        .trace_rd_wdata(trace_rd_wdata),
        .trace_rs1_addr(trace_rs1_addr),
        .trace_rs1_rdata(trace_rs1_rdata),
        .trace_rs2_addr(trace_rs2_addr),
        .trace_rs2_rdata(trace_rs2_rdata),
        .trace_mem_addr(trace_mem_addr),
        .trace_mem_rmask(trace_mem_rmask),
        .trace_mem_wmask(trace_mem_wmask),
        .trace_mem_rdata(trace_mem_rdata),
        .trace_mem_wdata(trace_mem_wdata),
        .trace_mem_fault(trace_mem_fault),
        .trace_mem_fault_rmask(trace_mem_fault_rmask),
        .trace_mem_fault_wmask(trace_mem_fault_wmask),
`ifdef DITDAH32_RVFI_CSR_TRACE
        .trace_csr_addr(trace_csr_addr),
        .trace_csr_rmask(trace_csr_rmask),
        .trace_csr_wmask(trace_csr_wmask),
        .trace_csr_rdata(trace_csr_rdata),
        .trace_csr_wdata(trace_csr_wdata),
`endif
        .trace_trap(trace_trap),
        .trace_trap_cause(trace_trap_cause),
        .trace_mstatus(trace_mstatus),
        .trace_mstatus_pre_trap(trace_mstatus_pre_trap),
        .trace_mip(trace_mip),
        .trace_mcause(trace_mcause)
    );

    wire ar_fire = axi_arvalid && axi_arready;
    wire r_fire = axi_rvalid && axi_rready;
    wire aw_fire = axi_awvalid && axi_awready;
    wire w_fire = axi_wvalid && axi_wready;
    wire b_fire = axi_bvalid && axi_bready;

    reg read_outstanding = 1'b0;
    reg write_aw_seen = 1'b0;
    reg write_w_seen = 1'b0;
    reg write_resp_pending = 1'b0;
    reg [63:0] rvfi_order_q = 64'd0;
`ifdef RISCV_FORMAL_BUS
    reg [31:0] bus_araddr_q = 32'd0;
    reg        bus_ar_is_insn_q = 1'b0;
    reg        bus_ar_is_data_q = 1'b0;
    reg [31:0] bus_awaddr_q = 32'd0;
    reg [31:0] bus_wdata_q = 32'd0;
    reg [3:0]  bus_wstrb_q = 4'd0;
`endif

`ifdef DITDAH32_RVFI_STANDARD_INTR
    wire trace_interrupt_event =
        trace_valid &&
        trace_trap &&
        trace_trap_cause == 4'h8 &&
        trace_len == 3'd0 &&
        trace_instr == 32'd0;
    reg        rvfi_intr_pending = 1'b0;
    reg [31:0] rvfi_intr_target_q = 32'd0;
    wire       rvfi_visible_valid = trace_valid && !trace_interrupt_event;
    wire       rvfi_intr_now = rvfi_visible_valid && rvfi_intr_pending;
`else
    wire       rvfi_visible_valid = trace_valid;
    wire       rvfi_intr_now = 1'b0;
`endif

    assign axi_awready = 1'b1;
    assign axi_wready = 1'b1;
    assign axi_bvalid = write_resp_pending;
    assign axi_bresp = 2'b00;
    assign axi_arready = 1'b1;
    assign axi_rvalid = read_outstanding;
    assign axi_rresp = 2'b00;

    assign rvfi_valid = rvfi_visible_valid;
    assign rvfi_order = rvfi_order_q;
    assign rvfi_insn = trace_instr;
    assign rvfi_trap = trace_trap;
    assign rvfi_halt = trap;
    assign rvfi_intr = rvfi_intr_now;
    assign rvfi_mode = 2'b11;
    assign rvfi_ixl = 2'b01;
    assign rvfi_rs1_addr = trace_rs1_addr;
    assign rvfi_rs2_addr = trace_rs2_addr;
    assign rvfi_rs1_rdata = trace_rs1_addr == 5'd0 ? 32'd0 : trace_rs1_rdata;
    assign rvfi_rs2_rdata = trace_rs2_addr == 5'd0 ? 32'd0 : trace_rs2_rdata;
    assign rvfi_rd_addr = trace_rd_we ? {1'b0, trace_rd} : 5'd0;
    assign rvfi_rd_wdata = trace_rd_we ? trace_rd_wdata : 32'd0;
    assign rvfi_pc_rdata = trace_pc;
    assign rvfi_pc_wdata = trace_next_pc;
    assign rvfi_mem_addr = trace_mem_addr;
    assign rvfi_mem_rmask = trace_mem_rmask;
    assign rvfi_mem_wmask = trace_mem_wmask;
    assign rvfi_mem_rdata = trace_mem_rmask == 4'd0 ? 32'd0 : trace_mem_rdata;
    assign rvfi_mem_wdata = trace_mem_wmask == 4'd0 ? 32'd0 : trace_mem_wdata;
`ifdef RISCV_FORMAL_MEM_FAULT
    assign rvfi_mem_fault = trace_mem_fault;
    assign rvfi_mem_fault_rmask = trace_mem_fault_rmask;
    assign rvfi_mem_fault_wmask = trace_mem_fault_wmask;
`endif

`ifdef RISCV_FORMAL_BUS
    wire rvfi_bus_read_valid = r_fire;
    wire rvfi_bus_write_valid = b_fire;

    assign rvfi_bus_valid = rvfi_bus_read_valid || rvfi_bus_write_valid;
    assign rvfi_bus_insn = rvfi_bus_read_valid && bus_ar_is_insn_q;
    assign rvfi_bus_data = (rvfi_bus_read_valid && bus_ar_is_data_q) || rvfi_bus_write_valid;
    assign rvfi_bus_fault = rvfi_bus_read_valid ? |axi_rresp : rvfi_bus_write_valid ? |axi_bresp : 1'b0;
    assign rvfi_bus_addr = rvfi_bus_read_valid ? bus_araddr_q : rvfi_bus_write_valid ? bus_awaddr_q : 32'd0;
    assign rvfi_bus_rmask = rvfi_bus_read_valid ? 4'hf : 4'h0;
    assign rvfi_bus_wmask = rvfi_bus_write_valid ? bus_wstrb_q : 4'h0;
    assign rvfi_bus_rdata = rvfi_bus_read_valid ? axi_rdata : 32'd0;
    assign rvfi_bus_wdata = rvfi_bus_write_valid ? bus_wdata_q : 32'd0;
`endif

`ifdef DITDAH32_RVFI_CSR_TRACE
    wire [2:0] rvfi_csr_funct3 = rvfi_insn[14:12];
    wire       rvfi_is_csr = rvfi_insn[6:0] == 7'b1110011 && rvfi_csr_funct3 != 3'b000;
    wire       rvfi_csr_uses_rs1 = rvfi_is_csr && !rvfi_csr_funct3[2];

    always @(*) begin
        if (!reset && rvfi_valid && rvfi_is_csr) begin
            assume(rvfi_insn[11:7] < 5'd16);
            if (rvfi_csr_uses_rs1) begin
                assume(rvfi_insn[19:15] < 5'd16);
            end
        end
    end

`ifdef RISCV_FORMAL_CSR_MSTATUS
    assign rvfi_csr_mstatus_rmask = trace_csr_addr == 12'h300 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mstatus_wmask = trace_csr_addr == 12'h300 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mstatus_rdata = trace_csr_addr == 12'h300 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mstatus_wdata = trace_csr_addr == 12'h300 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MISA
    assign rvfi_csr_misa_rmask = trace_csr_addr == 12'h301 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_misa_wmask = trace_csr_addr == 12'h301 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_misa_rdata = trace_csr_addr == 12'h301 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_misa_wdata = trace_csr_addr == 12'h301 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MIE
    assign rvfi_csr_mie_rmask = trace_csr_addr == 12'h304 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mie_wmask = trace_csr_addr == 12'h304 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mie_rdata = trace_csr_addr == 12'h304 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mie_wdata = trace_csr_addr == 12'h304 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MTVEC
    assign rvfi_csr_mtvec_rmask = trace_csr_addr == 12'h305 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mtvec_wmask = trace_csr_addr == 12'h305 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mtvec_rdata = trace_csr_addr == 12'h305 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mtvec_wdata = trace_csr_addr == 12'h305 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MSCRATCH
    assign rvfi_csr_mscratch_rmask = trace_csr_addr == 12'h340 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mscratch_wmask = trace_csr_addr == 12'h340 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mscratch_rdata = trace_csr_addr == 12'h340 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mscratch_wdata = trace_csr_addr == 12'h340 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MEPC
    assign rvfi_csr_mepc_rmask = trace_csr_addr == 12'h341 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mepc_wmask = trace_csr_addr == 12'h341 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mepc_rdata = trace_csr_addr == 12'h341 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mepc_wdata = trace_csr_addr == 12'h341 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MCAUSE
    assign rvfi_csr_mcause_rmask = trace_csr_addr == 12'h342 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mcause_wmask = trace_csr_addr == 12'h342 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mcause_rdata = trace_csr_addr == 12'h342 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mcause_wdata = trace_csr_addr == 12'h342 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MTVAL
    assign rvfi_csr_mtval_rmask = trace_csr_addr == 12'h343 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mtval_wmask = trace_csr_addr == 12'h343 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mtval_rdata = trace_csr_addr == 12'h343 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mtval_wdata = trace_csr_addr == 12'h343 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MIP
    assign rvfi_csr_mip_rmask = trace_csr_addr == 12'h344 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mip_wmask = trace_csr_addr == 12'h344 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mip_rdata = trace_csr_addr == 12'h344 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mip_wdata = trace_csr_addr == 12'h344 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MVENDORID
    assign rvfi_csr_mvendorid_rmask = trace_csr_addr == 12'hf11 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mvendorid_wmask = trace_csr_addr == 12'hf11 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mvendorid_rdata = trace_csr_addr == 12'hf11 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mvendorid_wdata = trace_csr_addr == 12'hf11 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MARCHID
    assign rvfi_csr_marchid_rmask = trace_csr_addr == 12'hf12 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_marchid_wmask = trace_csr_addr == 12'hf12 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_marchid_rdata = trace_csr_addr == 12'hf12 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_marchid_wdata = trace_csr_addr == 12'hf12 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MIMPID
    assign rvfi_csr_mimpid_rmask = trace_csr_addr == 12'hf13 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mimpid_wmask = trace_csr_addr == 12'hf13 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mimpid_rdata = trace_csr_addr == 12'hf13 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mimpid_wdata = trace_csr_addr == 12'hf13 ? trace_csr_wdata : 32'd0;
`endif
`ifdef RISCV_FORMAL_CSR_MHARTID
    assign rvfi_csr_mhartid_rmask = trace_csr_addr == 12'hf14 ? trace_csr_rmask : 32'd0;
    assign rvfi_csr_mhartid_wmask = trace_csr_addr == 12'hf14 ? trace_csr_wmask : 32'd0;
    assign rvfi_csr_mhartid_rdata = trace_csr_addr == 12'hf14 ? trace_csr_rdata : 32'd0;
    assign rvfi_csr_mhartid_wdata = trace_csr_addr == 12'hf14 ? trace_csr_wdata : 32'd0;
`endif
`endif

    always @(*) begin
        if (!reset) begin
            assume(!(axi_rvalid && !read_outstanding && !ar_fire));
            assume(!(axi_bvalid && !write_resp_pending && !(write_aw_seen && write_w_seen)));
`ifdef DITDAH32_RVFI_STANDARD_INTR
            if (rvfi_intr_now) begin
                assert(rvfi_pc_rdata == rvfi_intr_target_q);
            end
`endif
        end
    end

    always @(posedge clock) begin
        if (reset) begin
            read_outstanding <= 1'b0;
            write_aw_seen <= 1'b0;
            write_w_seen <= 1'b0;
            write_resp_pending <= 1'b0;
            rvfi_order_q <= 64'd0;
`ifdef RISCV_FORMAL_BUS
            bus_araddr_q <= 32'd0;
            bus_ar_is_insn_q <= 1'b0;
            bus_ar_is_data_q <= 1'b0;
            bus_awaddr_q <= 32'd0;
            bus_wdata_q <= 32'd0;
            bus_wstrb_q <= 4'd0;
`endif
`ifdef DITDAH32_RVFI_STANDARD_INTR
            rvfi_intr_pending <= 1'b0;
            rvfi_intr_target_q <= 32'd0;
`endif
        end else begin
            if (rvfi_visible_valid) begin
                rvfi_order_q <= rvfi_order_q + 64'd1;
            end
`ifdef DITDAH32_RVFI_STANDARD_INTR
            if (trace_interrupt_event) begin
                rvfi_intr_pending <= 1'b1;
                rvfi_intr_target_q <= trace_next_pc;
            end else if (rvfi_visible_valid) begin
                rvfi_intr_pending <= 1'b0;
            end
`endif

            case ({ar_fire, r_fire})
                2'b10: read_outstanding <= 1'b1;
                2'b01: read_outstanding <= 1'b0;
                default: read_outstanding <= read_outstanding;
            endcase

            if (aw_fire) begin
                write_aw_seen <= 1'b1;
            end
            if (w_fire) begin
                write_w_seen <= 1'b1;
            end
`ifdef RISCV_FORMAL_BUS
            if (ar_fire) begin
                bus_araddr_q <= axi_araddr;
                bus_ar_is_insn_q <= axi_arprot[2];
                bus_ar_is_data_q <= !axi_arprot[2];
            end
            if (aw_fire) begin
                bus_awaddr_q <= axi_awaddr;
            end
            if (w_fire) begin
                bus_wdata_q <= axi_wdata;
                bus_wstrb_q <= axi_wstrb;
            end
`endif
            if ((write_aw_seen || aw_fire) && (write_w_seen || w_fire)) begin
                write_resp_pending <= 1'b1;
            end
            if (b_fire) begin
                write_aw_seen <= 1'b0;
                write_w_seen <= 1'b0;
                write_resp_pending <= 1'b0;
            end
        end
    end

`ifdef DITDAH32_RVFI_TRAP_CSR_CHECK
    // Trap-entry / mret-exit / mip / mcause / MPIE-swap invariants.
    // Priv Spec v1.12: mstatus.MIE=3 / MPIE=7 / MPP=12:11; mip MSI/MTI/MEI=3/7/11.
    wire is_mret_retire = trace_valid && (trace_instr == 32'h30200073);
    wire is_trap_entry  = trace_valid && (trace_trap || rvfi_intr);
    wire is_interrupt_entry = is_trap_entry && trace_mcause[31];
    wire is_exception_entry = is_trap_entry && !trace_mcause[31];

    always @(posedge clock) begin
        if (!reset) begin
            if (is_trap_entry) begin
                assert (trace_mstatus[3] == 1'b0);
                assert (trace_mstatus[12:11] == 2'b11);
            end
            // MPIE swap proven on exception entries only; interrupt-entry
            // proof is staged because the IRQ path is 2 cycles delayed and
            // can absorb a same-cycle CSRRW to mstatus.
            if (is_exception_entry) begin
                assert (trace_mstatus[7] == trace_mstatus_pre_trap[3]);
            end
            if (is_mret_retire) begin
                assert (trace_mstatus[7] == 1'b1);
                assert (trace_mstatus[12:11] == 2'b11);
            end
            assert (trace_mip[3]  == irq_software);
            assert (trace_mip[7]  == irq_timer);
            assert (trace_mip[11] == irq_external);
            assert ((trace_mip & ~32'h0000_0888) == 32'd0);
            if (is_interrupt_entry) begin
                assert (trace_mcause[30:0] == 31'd3
                     || trace_mcause[30:0] == 31'd7
                     || trace_mcause[30:0] == 31'd11);
            end
        end
    end
`endif

`ifdef DITDAH32_RVFI_CSR_WARL_CHECK
    // WARL per-field legalization for the writable M-mode CSRs.
    always @(posedge clock) begin
        if (!reset && trace_valid) begin
            assert (trace_mstatus[31:13] == 19'd0);
            assert (trace_mstatus[10:8]  == 3'd0);
            assert (trace_mstatus[6:4]   == 3'd0);
            assert (trace_mstatus[2:0]   == 3'd0);
            assert (trace_mstatus[12:11] == 2'b00 || trace_mstatus[12:11] == 2'b11);
            if (trace_csr_rmask != 32'd0) begin
                if (trace_csr_addr == 12'h304)
                    assert ((trace_csr_rdata & ~32'h0000_0888) == 32'd0); // mie mask
                if (trace_csr_addr == 12'h305)
                    assert (trace_csr_rdata[1:0] == 2'b00);                // mtvec MODE
                if (trace_csr_addr == 12'h341)
                    assert (trace_csr_rdata[0] == 1'b0);                   // mepc align
            end
        end
    end
`endif

`ifdef DITDAH32_RVFI_CSR_READONLY_CHECK
    // Architectural write to a CSR with addr[11:10]==11 must trap (Priv Spec §2.1).
    // Write attempt: CSRRW/CSRRWI always, others when insn[19:15] != 0.
    wire [6:0] ro_opcode  = rvfi_insn[6:0];
    wire [2:0] ro_funct3  = rvfi_insn[14:12];
    wire [11:0] ro_csr    = rvfi_insn[31:20];
    wire [4:0] ro_field   = rvfi_insn[19:15];
    wire ro_is_csr_insn   = (ro_opcode == 7'h73) && (ro_funct3 != 3'd0) && (ro_funct3 != 3'd4);
    wire ro_is_write_attempt = ro_is_csr_insn &&
                               ((ro_funct3 == 3'd1) || (ro_funct3 == 3'd5) || (ro_field != 5'd0));
    wire ro_is_readonly_addr = (ro_csr[11:10] == 2'b11);
    always @(posedge clock) begin
        if (!reset && trace_valid && ro_is_csr_insn && ro_is_write_attempt && ro_is_readonly_addr) begin
            assert (rvfi_trap[0]);
        end
    end
`endif

`ifdef DITDAH32_RVFI_WFI_WAKE_CHECK
    // Bounded-liveness: sleep must exit within DITDAH32_WFI_BOUND cycles once an
    // MIE-enabled IRQ is pending.
    localparam integer DITDAH32_WFI_BOUND = 8;
    reg [3:0] wfi_wake_counter;
    always @(posedge clock) begin
        if (reset) begin
            wfi_wake_counter <= 4'd0;
        end else if (core_sleep && irq_pending) begin
            wfi_wake_counter <= wfi_wake_counter + 4'd1;
        end else begin
            wfi_wake_counter <= 4'd0;
        end
    end
    always @(posedge clock) begin
        if (!reset) begin
            assert (wfi_wake_counter < DITDAH32_WFI_BOUND);
        end
    end
`endif
endmodule
