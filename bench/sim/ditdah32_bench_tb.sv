// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
//
// Standalone Verilator benchmark testbench: drives the DitDah32 AXI-Lite
// master against a behavioural memory whose access latency models the two
// reported memory systems (0-wait tightly-coupled SRAM vs. AXI with wait
// states). Cycle count comes from the simulator between the in-program
// timing markers; runs until the EBREAK status_trap. Configured via plusargs so a
// single compiled binary scores every benchmark and memory model.

`timescale 1ns / 1ps

module ditdah32_bench_tb;
  localparam int MEM_WORDS = 65536;  // 256 KiB, matches bench/common/link.ld

  // Plusarg configuration.
  string        image_hex;
  int unsigned  timing_addr;
  int unsigned  result_addr;
  int unsigned  read_latency;
  int unsigned  write_latency;
  longint unsigned max_cycles;

  logic        clock = 0;
  logic        reset = 1;

  logic        axi_aw_valid;
  logic [31:0] axi_aw_bits_addr;
  logic [2:0]  axi_aw_bits_prot;
  logic        axi_aw_ready;
  logic        axi_w_valid;
  logic [31:0] axi_w_bits_data;
  logic [3:0]  axi_w_bits_strb;
  logic        axi_w_ready;
  logic        axi_b_valid;
  logic        axi_b_ready;
  logic [1:0]  axi_b_bits_resp;
  logic        axi_ar_valid;
  logic [31:0] axi_ar_bits_addr;
  logic [2:0]  axi_ar_bits_prot;
  logic        axi_ar_ready;
  logic        axi_r_valid;
  logic        axi_r_ready;
  logic [31:0] axi_r_bits_data;
  logic [1:0]  axi_r_bits_resp;
  logic        irq_software = 0;
  logic        irq_timer = 0;
  logic        irq_external = 0;
  logic        irq_pending;
  logic        status_trap;
  logic        status_busy;
  logic        status_sleep;

  DitDah32 dut (
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
    .status_sleep(status_sleep)
  );

  logic [31:0] mem [0:MEM_WORDS-1];

  longint unsigned cycle = 0;
  longint unsigned start_cycle = 0;
  longint unsigned stop_cycle = 0;
  bit have_start = 0;
  bit have_stop = 0;

  always #5 clock = ~clock;  // 100 MHz nominal; score is frequency-normalised

  always @(posedge clock) if (!reset) cycle <= cycle + 1;

  // ---- read channel: registered-output single-outstanding slave ----
  localparam int R_IDLE = 0, R_WAIT = 1, R_RESP = 2;
  int unsigned rstate = R_IDLE;
  int unsigned rcnt = 0;
  logic [31:0] raddr_q = 0;

  always @(posedge clock) begin
    if (reset) begin
      rstate      <= R_IDLE;
      axi_ar_ready <= 0;
      axi_r_valid  <= 0;
      axi_r_bits_data   <= 0;
      axi_r_bits_resp   <= 0;
    end else begin
      case (rstate)
        R_IDLE: begin
          axi_r_valid  <= 0;
          axi_ar_ready <= 1;
          if (axi_ar_valid && axi_ar_ready) begin
            raddr_q     <= axi_ar_bits_addr;
            axi_ar_ready <= 0;
            if (read_latency == 0) begin
              axi_r_bits_data  <= mem[axi_ar_bits_addr[17:2]];
              axi_r_bits_resp  <= 0;
              axi_r_valid <= 1;
              rstate     <= R_RESP;
            end else begin
              rcnt   <= read_latency;
              rstate <= R_WAIT;
            end
          end
        end
        R_WAIT: begin
          if (rcnt <= 1) begin
            axi_r_bits_data  <= mem[raddr_q[17:2]];
            axi_r_bits_resp  <= 0;
            axi_r_valid <= 1;
            rstate     <= R_RESP;
          end else begin
            rcnt <= rcnt - 1;
          end
        end
        R_RESP: begin
          if (axi_r_valid && axi_r_ready) begin
            axi_r_valid  <= 0;
            axi_ar_ready <= 1;
            rstate      <= R_IDLE;
          end
        end
      endcase
    end
  end

  // ---- write channel: latch AW and W independently, then respond ----
  localparam int W_ACCEPT = 0, W_WAIT = 1, W_RESP = 2;
  int unsigned wstate = W_ACCEPT;
  int unsigned wcnt = 0;
  logic [31:0] waddr_q = 0;
  logic [31:0] wdata_q = 0;
  logic [3:0]  wstrb_q = 0;
  bit aw_seen = 0;
  bit w_seen = 0;

  function automatic void do_write(input logic [31:0] addr,
                                   input logic [31:0] data,
                                   input logic [3:0] strb);
    logic [31:0] cur;
    cur = mem[addr[17:2]];
    if (strb[0]) cur[7:0]   = data[7:0];
    if (strb[1]) cur[15:8]  = data[15:8];
    if (strb[2]) cur[23:16] = data[23:16];
    if (strb[3]) cur[31:24] = data[31:24];
    mem[addr[17:2]] = cur;
    if (addr == timing_addr) begin
      if (data == 32'h53544152 && !have_start) begin  // "STAR"
        start_cycle = cycle;
        have_start  = 1;
      end
      if (data == 32'h53544f50) begin                 // "STOP"
        stop_cycle = cycle;
        have_stop  = 1;
      end
    end
  endfunction

  always @(posedge clock) begin
    if (reset) begin
      wstate      <= W_ACCEPT;
      axi_aw_ready <= 0;
      axi_w_ready  <= 0;
      axi_b_valid  <= 0;
      axi_b_bits_resp   <= 0;
      aw_seen     <= 0;
      w_seen      <= 0;
    end else begin
      case (wstate)
        W_ACCEPT: begin
          axi_b_valid  <= 0;
          axi_aw_ready <= !aw_seen;
          axi_w_ready  <= !w_seen;
          if (axi_aw_valid && axi_aw_ready) begin
            waddr_q     <= axi_aw_bits_addr;
            aw_seen     <= 1;
            axi_aw_ready <= 0;
          end
          if (axi_w_valid && axi_w_ready) begin
            wdata_q    <= axi_w_bits_data;
            wstrb_q    <= axi_w_bits_strb;
            w_seen     <= 1;
            axi_w_ready <= 0;
          end
          if ((aw_seen || (axi_aw_valid && axi_aw_ready)) &&
              (w_seen  || (axi_w_valid  && axi_w_ready))) begin
            logic [31:0] aaddr;
            logic [31:0] adata;
            logic [3:0]  astrb;
            aaddr = aw_seen ? waddr_q : axi_aw_bits_addr;
            adata = w_seen  ? wdata_q : axi_w_bits_data;
            astrb = w_seen  ? wstrb_q : axi_w_bits_strb;
            do_write(aaddr, adata, astrb);
            aw_seen <= 0;
            w_seen  <= 0;
            if (write_latency == 0) begin
              axi_b_bits_resp  <= 0;
              axi_b_valid <= 1;
              wstate     <= W_RESP;
            end else begin
              wcnt   <= write_latency;
              wstate <= W_WAIT;
            end
          end
        end
        W_WAIT: begin
          if (wcnt <= 1) begin
            axi_b_bits_resp  <= 0;
            axi_b_valid <= 1;
            wstate     <= W_RESP;
          end else begin
            wcnt <= wcnt - 1;
          end
        end
        W_RESP: begin
          if (axi_b_valid && axi_b_ready) begin
            axi_b_valid <= 0;
            wstate     <= W_ACCEPT;
          end
        end
      endcase
    end
  end

  initial begin
    for (int i = 0; i < MEM_WORDS; i++) mem[i] = 32'h0;

    if (!$value$plusargs("image=%s", image_hex)) begin
      $display("FATAL: +image=<hex> required");
      $finish;
    end
    if (!$value$plusargs("timing_addr=%d", timing_addr)) timing_addr = 0;
    if (!$value$plusargs("result_addr=%d", result_addr)) result_addr = 0;
    if (!$value$plusargs("read_latency=%d", read_latency)) read_latency = 0;
    if (!$value$plusargs("write_latency=%d", write_latency)) write_latency = 0;
    if (!$value$plusargs("max_cycles=%d", max_cycles)) max_cycles = 4_000_000_000;

    $readmemh(image_hex, mem);

    repeat (8) @(posedge clock);
    reset <= 0;

    forever begin
      @(posedge clock);
      if (status_trap) begin
        // result struct: magic, id, status, value0..value3 (7 words)
        $display("BENCH_RESULT %0d %0d %0d %0d %0d %0d %0d",
                 mem[(result_addr >> 2) + 0], mem[(result_addr >> 2) + 1],
                 mem[(result_addr >> 2) + 2], mem[(result_addr >> 2) + 3],
                 mem[(result_addr >> 2) + 4], mem[(result_addr >> 2) + 5],
                 mem[(result_addr >> 2) + 6]);
        $display("BENCH_TIMING start=%0d stop=%0d have_start=%0d have_stop=%0d total=%0d",
                 start_cycle, stop_cycle, have_start, have_stop, cycle);
        $finish;
      end
      if (cycle > max_cycles) begin
        $display("FATAL: max_cycles %0d exceeded without status_trap", max_cycles);
        $finish;
      end
    end
  end
endmodule
