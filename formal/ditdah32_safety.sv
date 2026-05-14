// SPDX-License-Identifier: MIT

module DitDah32Safety;
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
    wire [31:0] trace_instr;
    wire [2:0]  trace_len;
    wire        trace_rd_we;
    wire [3:0]  trace_rd;
    wire [31:0] trace_rd_wdata;
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
        .trace_instr(trace_instr),
        .trace_len(trace_len),
        .trace_rd_we(trace_rd_we),
        .trace_rd(trace_rd),
        .trace_rd_wdata(trace_rd_wdata),
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

    reg [63:0] rvfi_order = 64'd0;
    wire       rvfi_valid = trace_valid;
    wire [31:0] rvfi_insn = trace_instr;
    wire       rvfi_trap = trace_trap;
    wire [31:0] rvfi_pc_rdata = trace_pc;
    wire [4:0]  rvfi_rd_addr = {1'b0, trace_rd};
    wire [31:0] rvfi_rd_wdata = trace_rd_wdata;
    wire [3:0]  rvfi_rd_wmask = trace_rd_we ? 4'hF : 4'h0;

    reg read_outstanding = 1'b0;
    reg write_aw_seen = 1'b0;
    reg write_w_seen = 1'b0;
    reg write_resp_pending = 1'b0;
    reg fatal_trap_seen = 1'b0;

    always @(*) begin
        if (!reset) begin
            assume(!(axi_rvalid && !read_outstanding && !ar_fire));
            assume(!(axi_bvalid && !write_resp_pending && !(write_aw_seen && write_w_seen)));
        end
    end

    always @(posedge clock) begin
        if (reset) begin
            rvfi_order <= 64'd0;
            read_outstanding <= 1'b0;
            write_aw_seen <= 1'b0;
            write_w_seen <= 1'b0;
            write_resp_pending <= 1'b0;
            fatal_trap_seen <= 1'b0;
        end else begin
            if (rvfi_valid) begin
                rvfi_order <= rvfi_order + 64'd1;
            end
            if (trace_valid && trace_trap && trace_trap_cause == 4'h7) begin
                fatal_trap_seen <= 1'b1;
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
            if ($past(axi_arvalid && !axi_arready)) begin
                assert(axi_arvalid);
                assert(axi_araddr == $past(axi_araddr));
                assert(axi_arprot == $past(axi_arprot));
            end
            if ($past(axi_awvalid && !axi_awready)) begin
                assert(axi_awvalid);
                assert(axi_awaddr == $past(axi_awaddr));
                assert(axi_awprot == $past(axi_awprot));
            end
            if ($past(axi_wvalid && !axi_wready)) begin
                assert(axi_wvalid);
                assert(axi_wdata == $past(axi_wdata));
                assert(axi_wstrb == $past(axi_wstrb));
            end

            if ($past(r_fire && (axi_rresp != 2'b00))) begin
                assert(trace_valid);
                assert(trace_trap);
                assert(trace_trap_cause == 4'h7);
                assert(!trace_rd_we);
            end
            if ($past(b_fire && (axi_bresp != 2'b00))) begin
                assert(trace_valid);
                assert(trace_trap);
                assert(trace_trap_cause == 4'h7);
                assert(!trace_rd_we);
            end

            if ($past(fatal_trap_seen)) begin
                assert(trap);
                assert(!core_busy);
                assert(!trace_valid);
                assert(!axi_arvalid);
                assert(!axi_awvalid);
                assert(!axi_wvalid);
            end
        end

        if (!reset) begin
            assert(!(axi_arvalid && axi_awvalid));
            assert(!(axi_arvalid && axi_wvalid));
            if (!irq_software && !irq_timer && !irq_external) begin
                assert(!irq_pending);
            end
            if (irq_pending) begin
                assert(irq_software || irq_timer || irq_external);
            end
            assert(trace_len == 3'd0 || trace_len == 3'd2 || trace_len == 3'd4);
            if (trace_valid) begin
                assert(!(trace_trap && trace_rd_we));
                if (trace_len == 3'd0) begin
                    assert(trace_trap);
                    assert(trace_trap_cause == 4'h8);
                    assert(trace_instr == 32'd0);
                end
                if (trace_trap_cause == 4'h8) begin
                    assert(trace_trap);
                    assert(trace_len == 3'd0);
                    assert(trace_instr == 32'd0);
                end
                if (!trace_trap) begin
                    assert(trace_trap_cause == 4'h0);
                end
                if (trace_rd_we) begin
                    assert(trace_rd != 4'd0);
                end
            end
            if (rvfi_valid) begin
                assert(rvfi_rd_addr < 5'd16);
                assert(rvfi_insn == trace_instr);
                assert(rvfi_pc_rdata == trace_pc);
                assert(rvfi_rd_wdata == trace_rd_wdata);
                if (rvfi_trap) begin
                    assert(rvfi_rd_wmask == 4'h0);
                end
            end
            if (core_sleep) begin
                assert(!core_busy);
                assert(!trap);
                assert(!trace_valid);
                assert(!axi_arvalid);
                assert(!axi_awvalid);
                assert(!axi_wvalid);
            end
        end
    end
endmodule
