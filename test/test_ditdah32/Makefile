# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

DUT = test_ditdah32
DUT_DIR = $(abspath $(CURDIR))
TOPLEVEL = test_ditdah32
MODULE = test_ditdah32

VERILOG_TEST_SOURCES = $(DUT_DIR)/$(DUT).v
VERILOG_DIR = $(DUT_DIR)/../../result

VERILOG_SOURCES = $(VERILOG_TEST_SOURCES)
VERILOG_SOURCES += $(wildcard $(VERILOG_DIR)/*.v)
VERILOG_SOURCES += $(wildcard $(VERILOG_DIR)/*.sv)

COMPILE_ARGS += -I$(VERILOG_DIR)

PYTHONPATH := $(DUT_DIR)/../:$(PYTHONPATH)
export PYTHONPATH
export DITDAH32_ISA_ARTIFACT
export DITDAH32_ISA_DIR

include ../make/Makefile.mk
