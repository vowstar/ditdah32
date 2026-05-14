// SPDX-License-Identifier: MIT

module rvfi_wrapper (
    input clock,
    input reset,
    `RVFI_OUTPUTS
);
    (* keep *) `rvformal_rand_reg        axi_awready;
    (* keep *) `rvformal_rand_reg        axi_wready;
    (* keep *) `rvformal_rand_reg        axi_bvalid;
    (* keep *) `rvformal_rand_reg [1:0]  axi_bresp;
    (* keep *) `rvformal_rand_reg        axi_arready;
    (* keep *) `rvformal_rand_reg        axi_rvalid;
    (* keep *) `rvformal_rand_reg [31:0] axi_rdata;
    (* keep *) `rvformal_rand_reg [1:0]  axi_rresp;

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
        .irq_software(1'b0),
        .irq_timer(1'b0),
        .irq_external(1'b0),
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
        .trace_trap(trace_trap),
        .trace_trap_cause(trace_trap_cause)
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

    assign rvfi_valid = trace_valid;
    assign rvfi_order = rvfi_order_q;
    assign rvfi_insn = trace_instr;
    assign rvfi_trap = trace_trap;
    assign rvfi_halt = trap;
    assign rvfi_intr = 1'b0;
    assign rvfi_mode = 2'b11;
    assign rvfi_ixl = 2'b01;
    assign rvfi_rs1_addr = 5'd0;
    assign rvfi_rs2_addr = 5'd0;
    assign rvfi_rs1_rdata = 32'd0;
    assign rvfi_rs2_rdata = 32'd0;
    assign rvfi_rd_addr = trace_rd_we ? {1'b0, trace_rd} : 5'd0;
    assign rvfi_rd_wdata = trace_rd_we ? trace_rd_wdata : 32'd0;
    assign rvfi_pc_rdata = trace_pc;
    assign rvfi_pc_wdata = trace_next_pc;
    assign rvfi_mem_addr = 32'd0;
    assign rvfi_mem_rmask = 4'd0;
    assign rvfi_mem_wmask = 4'd0;
    assign rvfi_mem_rdata = 32'd0;
    assign rvfi_mem_wdata = 32'd0;

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
            rvfi_order_q <= 64'd0;
        end else begin
            if (trace_valid) begin
                rvfi_order_q <= rvfi_order_q + 64'd1;
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
endmodule
