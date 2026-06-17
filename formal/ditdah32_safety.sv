// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT

module DitDah32Safety;
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
    wire [31:0] trace_instr;
    wire [2:0]  trace_len;
    wire        trace_rd_we;
    wire [3:0]  trace_rd;
    wire [31:0] trace_rd_wdata;
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

    wire ar_fire = axi_ar_valid && axi_ar_ready;
    wire r_fire = axi_r_valid && axi_r_ready;
    wire aw_fire = axi_aw_valid && axi_aw_ready;
    wire w_fire = axi_w_valid && axi_w_ready;
    wire b_fire = axi_b_valid && axi_b_ready;

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
            assume(!(axi_r_valid && !read_outstanding && !ar_fire));
            assume(!(axi_b_valid && !write_resp_pending && !(write_aw_seen && write_w_seen)));
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
            if ($past(axi_ar_valid && !axi_ar_ready)) begin
                assert(axi_ar_valid);
                assert(axi_ar_bits_addr == $past(axi_ar_bits_addr));
                assert(axi_ar_bits_prot == $past(axi_ar_bits_prot));
            end
            if ($past(axi_aw_valid && !axi_aw_ready)) begin
                assert(axi_aw_valid);
                assert(axi_aw_bits_addr == $past(axi_aw_bits_addr));
                assert(axi_aw_bits_prot == $past(axi_aw_bits_prot));
            end
            if ($past(axi_w_valid && !axi_w_ready)) begin
                assert(axi_w_valid);
                assert(axi_w_bits_data == $past(axi_w_bits_data));
                assert(axi_w_bits_strb == $past(axi_w_bits_strb));
            end

            if ($past(r_fire && (axi_r_bits_resp != 2'b00))) begin
                assert(trace_valid);
                assert(trace_trap);
                assert(trace_trap_cause == 4'h7);
                assert(!trace_rd_we);
            end
            if ($past(b_fire && (axi_b_bits_resp != 2'b00))) begin
                assert(trace_valid);
                assert(trace_trap);
                assert(trace_trap_cause == 4'h7);
                assert(!trace_rd_we);
            end

            if ($past(fatal_trap_seen)) begin
                assert(status_trap);
                assert(!status_busy);
                assert(!trace_valid);
                assert(!axi_ar_valid);
                assert(!axi_aw_valid);
                assert(!axi_w_valid);
            end
        end

        if (!reset) begin
            assert(!(axi_ar_valid && axi_aw_valid));
            assert(!(axi_ar_valid && axi_w_valid));
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
            if (status_sleep) begin
                assert(!status_busy);
                assert(!status_trap);
                assert(!trace_valid);
                assert(!axi_ar_valid);
                assert(!axi_aw_valid);
                assert(!axi_w_valid);
            end
        end
    end
endmodule
