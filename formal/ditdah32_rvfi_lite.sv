// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT

module DitDah32RvfiLite;
    reg clock = 1'b0;
    always #1 clock = !clock;

    reg reset = 1'b1;
    always @(posedge clock) begin
        reset <= 1'b0;
    end

    (* anyseq *) reg        axi_aw_ready;
    (* anyseq *) reg        axi_w_ready;
    (* anyseq *) reg        axi_b_valid;
    (* anyseq *) reg [1:0]  axi_b_bits_resp;
    (* anyseq *) reg        axi_ar_ready;
    (* anyseq *) reg        axi_r_valid;
    (* anyseq *) reg [31:0] axi_r_bits_data;
    (* anyseq *) reg [1:0]  axi_r_bits_resp;
    (* anyseq *) reg        irq_software;
    (* anyseq *) reg        irq_timer;
    (* anyseq *) reg        irq_external;

    wire        irq_pending;
    wire        axi_aw_valid;
    wire [31:0] axi_aw_bits_addr;
    wire [2:0]  axi_aw_bits_prot;
    wire        axi_w_valid;
    wire [31:0] axi_w_bits_data;
    wire [3:0]  axi_w_bits_strb;
    wire        axi_b_ready;
    wire        axi_ar_valid;
    wire [31:0] axi_ar_bits_addr;
    wire [2:0]  axi_ar_bits_prot;
    wire        axi_r_ready;
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
    wire [11:0] trace_csr_addr;
    wire [31:0] trace_csr_rmask;
    wire [31:0] trace_csr_wmask;
    wire [31:0] trace_csr_rdata;
    wire [31:0] trace_csr_wdata;
    wire        trace_trap;
    wire [3:0]  trace_trap_cause;

    // Trace ports are resolved from the DV layer bind collateral by the
    // ditdah32_trace_top bridge (read via read_slang).
    ditdah32_trace_top dut (
        .clock(clock),
        .reset(reset),
        .axi_aw_valid(axi_aw_valid),
        .axi_aw_bits_addr(axi_aw_bits_addr),
        .axi_aw_bits_prot(axi_aw_bits_prot),
        .axi_aw_ready(axi_aw_ready),
        .axi_w_valid(axi_w_valid),
        .axi_w_bits_data(axi_w_bits_data),
        .axi_w_bits_strb(axi_w_bits_strb),
        .axi_w_ready(axi_w_ready),
        .axi_b_valid(axi_b_valid),
        .axi_b_ready(axi_b_ready),
        .axi_b_bits_resp(axi_b_bits_resp),
        .axi_ar_valid(axi_ar_valid),
        .axi_ar_bits_addr(axi_ar_bits_addr),
        .axi_ar_bits_prot(axi_ar_bits_prot),
        .axi_ar_ready(axi_ar_ready),
        .axi_r_valid(axi_r_valid),
        .axi_r_ready(axi_r_ready),
        .axi_r_bits_data(axi_r_bits_data),
        .axi_r_bits_resp(axi_r_bits_resp),
        .irq_software(irq_software),
        .irq_timer(irq_timer),
        .irq_external(irq_external),
        .irq_pending(irq_pending),
        .status_trap(status_trap),
        .status_busy(status_busy),
        .status_sleep(status_sleep),
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

    wire ar_fire = axi_ar_valid && axi_ar_ready;
    wire r_fire = axi_r_valid && axi_r_ready;
    wire aw_fire = axi_aw_valid && axi_aw_ready;
    wire w_fire = axi_w_valid && axi_w_ready;
    wire b_fire = axi_b_valid && axi_b_ready;

    reg read_outstanding = 1'b0;
    reg write_aw_seen = 1'b0;
    reg write_w_seen = 1'b0;
    reg write_resp_pending = 1'b0;

    reg [63:0] rvfi_order = 64'd0;
    wire       rvfi_valid = trace_valid;
    wire [63:0] rvfi_order_out = rvfi_order;
    wire [31:0] rvfi_insn = trace_instr;
    wire       rvfi_trap = trace_trap;
    wire       rvfi_halt = status_trap;
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
            assume(!(axi_r_valid && !read_outstanding && !ar_fire));
            assume(!(axi_b_valid && !write_resp_pending && !(write_aw_seen && write_w_seen)));
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
