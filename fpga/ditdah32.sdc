# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT
#
# 50 MHz template; point the clock at the core clock net of your
# top-level integration.
create_clock -name sys_clk -period 20 -waveform {0 10} [get_nets {u_core/clock}]
