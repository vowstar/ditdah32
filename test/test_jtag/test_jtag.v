// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps

module test_jtag;
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

    reg  irq_software;
    reg  irq_timer;
    reg  irq_external;
    wire irq_pending;
    wire status_trap;
    wire status_busy;
    wire status_sleep;

    reg  jtag_tck;
    reg  jtag_tms;
    reg  jtag_tdi;
    wire jtag_tdo;
    reg  jtag_trstN;

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
        jtag_tck = 1'b0;
        jtag_tms = 1'b1;
        jtag_tdi = 1'b0;
        jtag_trstN = 1'b0;
    end

    DitDah32 u_ditdah32 (
        .clock               (clk),
        .reset               (reset),
        .axi_aw_valid        (axi_aw_valid),
        .axi_aw_bits_addr    (axi_aw_bits_addr),
        .axi_aw_bits_prot    (axi_aw_bits_prot),
        .axi_aw_ready        (axi_aw_ready),
        .axi_w_valid         (axi_w_valid),
        .axi_w_bits_data     (axi_w_bits_data),
        .axi_w_bits_strb     (axi_w_bits_strb),
        .axi_w_ready         (axi_w_ready),
        .axi_b_valid         (axi_b_valid),
        .axi_b_ready         (axi_b_ready),
        .axi_b_bits_resp     (axi_b_bits_resp),
        .axi_ar_valid        (axi_ar_valid),
        .axi_ar_bits_addr    (axi_ar_bits_addr),
        .axi_ar_bits_prot    (axi_ar_bits_prot),
        .axi_ar_ready        (axi_ar_ready),
        .axi_r_valid         (axi_r_valid),
        .axi_r_ready         (axi_r_ready),
        .axi_r_bits_data     (axi_r_bits_data),
        .axi_r_bits_resp     (axi_r_bits_resp),
        .irq_software        (irq_software),
        .irq_timer           (irq_timer),
        .irq_external        (irq_external),
        .irq_pending         (irq_pending),
        .status_trap         (status_trap),
        .status_busy         (status_busy),
        .status_sleep        (status_sleep),
        .jtag_tck            (jtag_tck),
        .jtag_tms            (jtag_tms),
        .jtag_tdi            (jtag_tdi),
        .jtag_tdo            (jtag_tdo),
        .jtag_trstN          (jtag_trstN)
    );
endmodule
