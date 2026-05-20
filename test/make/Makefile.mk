# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

TOPLEVEL_LANG = verilog

ifndef SIM
ifeq ($(shell command -v vcs >/dev/null 2>&1 && echo yes),yes)
SIM := vcs
else ifeq ($(shell command -v xrun >/dev/null 2>&1 && echo yes),yes)
SIM := xcelium
else ifeq ($(shell command -v iverilog >/dev/null 2>&1 && echo yes),yes)
SIM := icarus
$(warning WARNING: Using Icarus Verilog. Prefer VCS or Xcelium for stronger SystemVerilog coverage.)
else
$(error No supported simulator found. Install VCS, Xcelium, or Icarus and ensure it is in PATH)
endif
endif

WAVES ?= 1

ifeq ($(strip $(DUT)),)
$(error DUT is not set)
endif

ifeq ($(strip $(DUT_DIR)),)
$(error DUT_DIR is not set)
endif

ifeq ($(strip $(TOPLEVEL)),)
$(error TOPLEVEL is not set)
endif

ifeq ($(strip $(MODULE)),)
$(error MODULE is not set)
endif

ifeq ($(strip $(VERILOG_TEST_SOURCES)),)
$(error VERILOG_TEST_SOURCES is not set)
endif

ifeq ($(strip $(VERILOG_DIR)),)
$(error VERILOG_DIR is not set)
endif

ifeq ($(strip $(VERILOG_SOURCES)),)
$(error VERILOG_SOURCES is not set)
endif

COCOTB_HDL_TIMEUNIT = 1ns
COCOTB_HDL_TIMEPRECISION = 1ps

ifeq ($(SIM), icarus)
COMPILE_ARGS += -g2012 -Dfunctional -DSIMULATION
PLUSARGS += -fst -Dfunctional -DSIMULATION
else ifeq ($(SIM), verilator)
COMPILE_ARGS += \
	-CFLAGS "-std=c++20 -fcoroutines" \
	-Wno-SELRANGE \
	-Wno-WIDTH \
	-Wno-BLKANDNBLK \
	-Wno-MINTYPMAXDLY \
	--bbox-unsup \
	--timing \
	-Dfunctional \
	-DSIMULATION

ifeq ($(WAVES), 1)
COMPILE_ARGS += --trace-fst
endif

ifeq ($(HDL_COVERAGE), 1)
COMPILE_ARGS += --coverage
SIM_ARGS += +verilator+coverage+file+$(DUT_DIR)/$(SIM_BUILD)/coverage.dat
endif
else ifeq ($(SIM), vcs)
PLUSARGS += \
	-debug_access+all \
	-debug_region=cell+lib+encrypt \
	+acc+3 \
	+incdir+$(VERILOG_DIR) \
	+incdir+$(DUT_DIR) \
	+define+functional \
	+define+SIMULATION \
	+lint=all,noVCDE,noONGS,noUI \
	-error=PCWM-L \
	-error=noZMMCM \
	+warn=noPISB \
	+rad \
	+vcs+lic+wait \
	+vc+list \
	+systemverilogext+.sv+.svi+.svh+.svt \
	+libext+.sv \
	+v2k \
	+verilog2001ext+.v95+.vt+.vp \
	+libext+.v

COMPILE_ARGS += -timescale=1ns/10ps \
	-assert svaext \
	-sverilog

ifeq ($(WAVES), 1)
VERILOG_SOURCES += $(DUT_DIR)/$(SIM_BUILD)/vcs_dump.v
COMPILE_ARGS += -top vcs_dump -lca -kdb
SIM_ARGS += +fsdb+autoflush
endif
else ifeq ($(SIM), xcelium)
PLUSARGS += \
	+define+functional \
	+define+SIMULATION \
	-ALLOWREDEFINITION
COMPILE_ARGS += \
	-sysv \
	-sysv_ext +.v \
	-vlog_ext .vp,.vs
endif

include $(shell cocotb-config --makefiles)/Makefile.sim

define DUMP_WAVE_VCS
module vcs_dump();
initial begin
    $$fsdbDumpfile("$(DUT_DIR)/$(SIM_BUILD)/$(TOPLEVEL).fsdb");
    $$fsdbDumpSVA;
    $$fsdbDumpvars(0, $(TOPLEVEL), "+all", "+power", "+struct", "+mda");
    $$fsdbDumpon;
end
final begin
    $$fsdbDumpflush;
end
endmodule
endef
export DUMP_WAVE_VCS

CUSTOM_COMPILE_DEPS += $(DUT_DIR)/$(SIM_BUILD)/sim.fl $(DUT_DIR)/$(SIM_BUILD)/vcs_dump.v

$(DUT_DIR)/$(SIM_BUILD)/sim.fl: $(VERILOG_SOURCES) | $(SIM_BUILD)
	@{ for f in $(VERILOG_SOURCES); do printf '%s\n' "$$f"; done; } > $@

$(DUT_DIR)/$(SIM_BUILD)/vcs_dump.v: | $(SIM_BUILD)
	@echo "$$DUMP_WAVE_VCS" > $@

test: sim
	@grep -i 'failed' $(DUT_DIR)/results.xml && exit 1 || exit 0

clean::
	@rm -f $(DUT_DIR)/$(SIM_BUILD)/vcs_dump.v
	@rm -f $(DUT_DIR)/$(SIM_BUILD)/sim.fl
	@rm -f $(DUT_DIR)/$(SIM_BUILD)/$(TOPLEVEL).fsdb
	@rm -f $(DUT_DIR)/novas.*
	@rm -f $(DUT_DIR)/*.log
	@rm -f $(DUT_DIR)/*.xml
	@rm -f $(DUT_DIR)/*.fst
	@rm -f $(DUT_DIR)/*.fsdb
	@rm -f $(DUT_DIR)/*.gtkw
	@rm -f $(DUT_DIR)/ucli.key
	@rm -rf $(DUT_DIR)/__pycache__
	@rm -rf $(DUT_DIR)/verdiLog
	@rm -rf $(DUT_DIR)/xrun.*

.PHONY: test
