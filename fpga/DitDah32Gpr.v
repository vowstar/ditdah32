// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
//
// Distributed-RAM register file for Anlogic EG4 FPGAs. Compile this file
// instead of the generated DitDah32Gpr.sv. No-JTAG configuration only:
// the core ties raddr3 and clearAll low, and reset-to-zero is not
// architecturally required, so both are no-ops here.
module DitDah32Gpr(
  input         clock,
  input         reset,
  input  [4:0]  raddr1,
  output [31:0] rdata1,
  input  [4:0]  raddr2,
  output [31:0] rdata2,
  input  [4:0]  raddr3,
  output [31:0] rdata3,
  input         we,
  input  [4:0]  waddr,
  input  [31:0] wdata,
  input         clearAll
);
  wire wr = we & (waddr >= 5'd1) & (waddr <= 5'd15);

  wire [4:0]  ra [0:2];
  wire [31:0] q  [0:2];
  assign ra[0] = raddr1;
  assign ra[1] = raddr2;
  assign ra[2] = raddr3;

  genvar p, b;
  generate
    for (p = 0; p < 3; p = p + 1) begin : rport
      for (b = 0; b < 4; b = b + 1) begin : lane
        EG_LOGIC_DRAM #(
          .INIT_FILE   ("NONE"),
          .DATA_WIDTH_W(8),
          .ADDR_WIDTH_W(4),
          .DATA_DEPTH_W(16),
          .DATA_WIDTH_R(8),
          .ADDR_WIDTH_R(4),
          .DATA_DEPTH_R(16)
        ) u_dram (
          .di   (wdata[b*8 +: 8]),
          .waddr(waddr[3:0]),
          .wclk (clock),
          .we   (wr),
          .do   (q[p][b*8 +: 8]),
          .raddr(ra[p][3:0])
        );
      end
    end
  endgenerate

  assign rdata1 = ((raddr1 >= 5'd1) & (raddr1 <= 5'd15)) ? q[0] : 32'b0;
  assign rdata2 = ((raddr2 >= 5'd1) & (raddr2 <= 5'd15)) ? q[1] : 32'b0;
  assign rdata3 = ((raddr3 >= 5'd1) & (raddr3 <= 5'd15)) ? q[2] : 32'b0;
endmodule
