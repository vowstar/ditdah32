// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT

module DitDah32RvfiLite;
    reg clock = 1'b0;
    always #1 clock = !clock;

    reg reset = 1'b1;
    always @(posedge clock) begin
        reset <= 1'b0;
    end

    (* anyseq *) reg        axi_awready;
    (* anyseq *) reg        axi_wready;
    (* anyseq *) reg        axi_bvalid;
    (* anyseq *) reg [1:0]  axi_bresp;
    (* anyseq *) reg        axi_arready;
    (* anyseq *) reg        axi_rvalid;
    (* anyseq *) reg [31:0] axi_rdata;
    (* anyseq *) reg [1:0]  axi_rresp;
    (* anyseq *) reg        irq_software;
    (* anyseq *) reg        irq_timer;
    (* anyseq *) reg        irq_external;

    wire        irq_pending;
    wire        axi_awvalid;
    wire [31:0] axi_awaddr;
    wire [2:0]  axi_awprot;
    wire        axi_wvalid;
    wire [31:0] axi_wdata;
    wire [3:0]  axi_wstrb;
    wire        axi_bready;
    wire        axi_arvalid;
    wire [31:0] axi_araddr;
    wire [2:0]  axi_arprot;
    wire        axi_rready;
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
    wire [11:0] trace_csr_addr;
    wire [31:0] trace_csr_rmask;
    wire [31:0] trace_csr_wmask;
    wire [31:0] trace_csr_rdata;
    wire [31:0] trace_csr_wdata;
    wire        trace_trap;
    wire [3:0]  trace_trap_cause;

    DitDah32 dut (
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
        .trace_csr_addr(trace_csr_addr),
        .trace_csr_rmask(trace_csr_rmask),
        .trace_csr_wmask(trace_csr_wmask),
        .trace_csr_rdata(trace_csr_rdata),
        .trace_csr_wdata(trace_csr_wdata),
        .trace_trap(trace_trap),
        .trace_trap_cause(trace_trap_cause)
    );

    reg f_past_valid = 1'b0;
    always @(posedge clock) begin
        f_past_valid <= 1'b1;
    end

    wire ar_fire = axi_arvalid && axi_arready;
    wire r_fire = axi_rvalid && axi_rready;
    wire aw_fire = axi_awvalid && axi_awready;
    wire w_fire = axi_wvalid && axi_wready;
    wire b_fire = axi_bvalid && axi_bready;

    reg read_outstanding = 1'b0;
    reg write_aw_seen = 1'b0;
    reg write_w_seen = 1'b0;
    reg write_resp_pending = 1'b0;

    reg [63:0] rvfi_order = 64'd0;
    wire       rvfi_valid = trace_valid;
    wire [63:0] rvfi_order_out = rvfi_order;
    wire [31:0] rvfi_insn = trace_instr;
    wire       rvfi_trap = trace_trap;
    wire       rvfi_halt = trap;
    wire       rvfi_intr = trace_valid && trace_trap && trace_trap_cause == 4'h8;
    wire [1:0] rvfi_mode = 2'b11;
    wire [1:0] rvfi_ixl = 2'b01;
    wire [4:0] rvfi_rs1_addr = trace_rs1_addr;
    wire [4:0] rvfi_rs2_addr = trace_rs2_addr;
    wire [31:0] rvfi_rs1_rdata = trace_rs1_addr == 5'd0 ? 32'd0 : trace_rs1_rdata;
    wire [31:0] rvfi_rs2_rdata = trace_rs2_addr == 5'd0 ? 32'd0 : trace_rs2_rdata;
    wire [4:0] rvfi_rd_addr = trace_rd_we ? {1'b0, trace_rd} : 5'd0;
    wire [31:0] rvfi_rd_wdata = trace_rd_we ? trace_rd_wdata : 32'd0;
    wire [31:0] rvfi_pc_rdata = trace_pc;
    wire [31:0] rvfi_pc_wdata = trace_next_pc;
    wire [31:0] rvfi_mem_addr = trace_mem_addr;
    wire [3:0] rvfi_mem_rmask = trace_mem_rmask;
    wire [3:0] rvfi_mem_wmask = trace_mem_wmask;
    wire [31:0] rvfi_mem_rdata = trace_mem_rmask == 4'd0 ? 32'd0 : trace_mem_rdata;
    wire [31:0] rvfi_mem_wdata = trace_mem_wmask == 4'd0 ? 32'd0 : trace_mem_wdata;

    always @(*) begin
        if (!reset) begin
            assume(!(axi_rvalid && !read_outstanding && !ar_fire));
            assume(!(axi_bvalid && !write_resp_pending && !(write_aw_seen && write_w_seen)));
        end
    end

    always @(posedge clock) begin
        if (reset) begin
            read_outstanding <= 1'b0;
            write_aw_seen <= 1'b0;
            write_w_seen <= 1'b0;
            write_resp_pending <= 1'b0;
            rvfi_order <= 64'd0;
        end else begin
            if (rvfi_valid) begin
                rvfi_order <= rvfi_order + 64'd1;
            end

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

    always @(posedge clock) begin
        if (f_past_valid && !$past(reset)) begin
            if ($past(rvfi_valid)) begin
                assert(rvfi_order_out == $past(rvfi_order_out) + 64'd1);
            end else begin
                assert(rvfi_order_out == $past(rvfi_order_out));
            end
        end

        if (!reset) begin
            assert(rvfi_valid == trace_valid);
            assert(rvfi_insn == trace_instr);
            assert(rvfi_trap == trace_trap);
            assert(rvfi_pc_rdata == trace_pc);
            assert(rvfi_pc_wdata == trace_next_pc);
            assert(rvfi_mode == 2'b11);
            assert(rvfi_ixl == 2'b01);
            assert(rvfi_rs1_addr == trace_rs1_addr);
            assert(rvfi_rs2_addr == trace_rs2_addr);
            assert(rvfi_rs1_rdata == (trace_rs1_addr == 5'd0 ? 32'd0 : trace_rs1_rdata));
            assert(rvfi_rs2_rdata == (trace_rs2_addr == 5'd0 ? 32'd0 : trace_rs2_rdata));
            assert(rvfi_mem_addr == trace_mem_addr);
            assert(rvfi_mem_rmask == trace_mem_rmask);
            assert(rvfi_mem_wmask == trace_mem_wmask);
            assert(rvfi_mem_rdata == (trace_mem_rmask == 4'd0 ? 32'd0 : trace_mem_rdata));
            assert(rvfi_mem_wdata == (trace_mem_wmask == 4'd0 ? 32'd0 : trace_mem_wdata));

            if (rvfi_valid) begin
                assert(trace_len == 3'd0 || trace_len == 3'd2 || trace_len == 3'd4);
                assert(rvfi_pc_wdata[0] == 1'b0);
                assert(!(rvfi_trap && trace_rd_we));
                assert(rvfi_rd_addr < 5'd16);
                assert(rvfi_rs1_addr < 5'd16);
                assert(rvfi_rs2_addr < 5'd16);
                assert(!(rvfi_mem_rmask != 4'd0 && rvfi_mem_wmask != 4'd0));
                if (rvfi_mem_rmask == 4'd0) begin
                    assert(rvfi_mem_rdata == 32'd0);
                end
                if (rvfi_mem_wmask == 4'd0) begin
                    assert(rvfi_mem_wdata == 32'd0);
                end
                if (rvfi_rs1_addr == 5'd0) begin
                    assert(rvfi_rs1_rdata == 32'd0);
                end
                if (rvfi_rs2_addr == 5'd0) begin
                    assert(rvfi_rs2_rdata == 32'd0);
                end
                if (trace_rd_we) begin
                    assert(rvfi_rd_addr != 5'd0);
                    assert(rvfi_rd_wdata == trace_rd_wdata);
                end else begin
                    assert(rvfi_rd_addr == 5'd0);
                    assert(rvfi_rd_wdata == 32'd0);
                end
                if (rvfi_intr) begin
                    assert(rvfi_trap);
                    assert(trace_len == 3'd0);
                    assert(trace_instr == 32'd0);
                end
                if (rvfi_trap) begin
                    assert(!trace_rd_we);
                end
            end
        end
    end
endmodule
