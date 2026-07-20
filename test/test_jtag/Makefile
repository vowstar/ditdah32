# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

DUT = test_jtag
DUT_DIR = $(abspath $(CURDIR))
TOPLEVEL = test_jtag
MODULE = test_jtag

VERILOG_TEST_SOURCES = $(DUT_DIR)/$(DUT).v
VERILOG_DIR = $(DUT_DIR)/../../result/jtag

VERILOG_SOURCES = $(VERILOG_TEST_SOURCES)
VERILOG_SOURCES += $(VERILOG_DIR)/DitDah32.sv
VERILOG_SOURCES += $(VERILOG_DIR)/DitDah32Gpr.sv
VERILOG_SOURCES += $(VERILOG_DIR)/DitDah32DebugModule.sv
VERILOG_SOURCES += $(VERILOG_DIR)/DitDah32JtagDtm.sv

PYTHONPATH := $(DUT_DIR)/../:$(PYTHONPATH)
export PYTHONPATH

include ../make/Makefile.mk
