// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
//
// Standalone Verilator benchmark testbench: drives the DitDah32 AXI-Lite
// master against a behavioural memory whose access latency models the two
// reported memory systems (0-wait tightly-coupled SRAM vs. AXI with wait
// states). Cycle count comes from the simulator between the in-program
// timing markers; runs until the EBREAK trap. Configured via plusargs so a
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

  logic        axi_awvalid;
  logic [31:0] axi_awaddr;
  logic [2:0]  axi_awprot;
  logic        axi_awready;
  logic        axi_wvalid;
  logic [31:0] axi_wdata;
  logic [3:0]  axi_wstrb;
  logic        axi_wready;
  logic        axi_bvalid;
  logic        axi_bready;
  logic [1:0]  axi_bresp;
  logic        axi_arvalid;
  logic [31:0] axi_araddr;
  logic [2:0]  axi_arprot;
  logic        axi_arready;
  logic        axi_rvalid;
  logic        axi_rready;
  logic [31:0] axi_rdata;
  logic [1:0]  axi_rresp;
  logic        irq_software = 0;
  logic        irq_timer = 0;
  logic        irq_external = 0;
  logic        irq_pending;
  logic        trap;
  logic        core_busy;
  logic        core_sleep;

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
    .core_sleep(core_sleep)
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
      axi_arready <= 0;
      axi_rvalid  <= 0;
      axi_rdata   <= 0;
      axi_rresp   <= 0;
    end else begin
      case (rstate)
        R_IDLE: begin
          axi_rvalid  <= 0;
          axi_arready <= 1;
          if (axi_arvalid && axi_arready) begin
            raddr_q     <= axi_araddr;
            axi_arready <= 0;
            if (read_latency == 0) begin
              axi_rdata  <= mem[axi_araddr[17:2]];
              axi_rresp  <= 0;
              axi_rvalid <= 1;
              rstate     <= R_RESP;
            end else begin
              rcnt   <= read_latency;
              rstate <= R_WAIT;
            end
          end
        end
        R_WAIT: begin
          if (rcnt <= 1) begin
            axi_rdata  <= mem[raddr_q[17:2]];
            axi_rresp  <= 0;
            axi_rvalid <= 1;
            rstate     <= R_RESP;
          end else begin
            rcnt <= rcnt - 1;
          end
        end
        R_RESP: begin
          if (axi_rvalid && axi_rready) begin
            axi_rvalid  <= 0;
            axi_arready <= 1;
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
      axi_awready <= 0;
      axi_wready  <= 0;
      axi_bvalid  <= 0;
      axi_bresp   <= 0;
      aw_seen     <= 0;
      w_seen      <= 0;
    end else begin
      case (wstate)
        W_ACCEPT: begin
          axi_bvalid  <= 0;
          axi_awready <= !aw_seen;
          axi_wready  <= !w_seen;
          if (axi_awvalid && axi_awready) begin
            waddr_q     <= axi_awaddr;
            aw_seen     <= 1;
            axi_awready <= 0;
          end
          if (axi_wvalid && axi_wready) begin
            wdata_q    <= axi_wdata;
            wstrb_q    <= axi_wstrb;
            w_seen     <= 1;
            axi_wready <= 0;
          end
          if ((aw_seen || (axi_awvalid && axi_awready)) &&
              (w_seen  || (axi_wvalid  && axi_wready))) begin
            logic [31:0] aaddr;
            logic [31:0] adata;
            logic [3:0]  astrb;
            aaddr = aw_seen ? waddr_q : axi_awaddr;
            adata = w_seen  ? wdata_q : axi_wdata;
            astrb = w_seen  ? wstrb_q : axi_wstrb;
            do_write(aaddr, adata, astrb);
            aw_seen <= 0;
            w_seen  <= 0;
            if (write_latency == 0) begin
              axi_bresp  <= 0;
              axi_bvalid <= 1;
              wstate     <= W_RESP;
            end else begin
              wcnt   <= write_latency;
              wstate <= W_WAIT;
            end
          end
        end
        W_WAIT: begin
          if (wcnt <= 1) begin
            axi_bresp  <= 0;
            axi_bvalid <= 1;
            wstate     <= W_RESP;
          end else begin
            wcnt <= wcnt - 1;
          end
        end
        W_RESP: begin
          if (axi_bvalid && axi_bready) begin
            axi_bvalid <= 0;
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
      if (trap) begin
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
        $display("FATAL: max_cycles %0d exceeded without trap", max_cycles);
        $finish;
      end
    end
  end
endmodule
