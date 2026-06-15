# SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
# SPDX-License-Identifier: MIT

.PHONY: audit-ci-action-refs audit-ci-github-auth audit-ci-publish-readiness audit-ci-remote audit-ci-remote-preflight audit-completion audit-gaps audit-tools audit-trace-config build build-trace bench bench-score ci-remote-closure ci-remote-dispatch ci-remote-publish coverage formal signoff-coverage test test-model test-isa test-scripts test-isa-rtl verify verify-ci-smoke verify-compliance verify-iss verify-riscv-dv verify-rvfi verify-rvfi-lite verify-sail-highmem verify-sail-matrix verify-sail-smoke verify-smoke verify-rtl verify-signoff verify-spike-highmem verify-spike-rv32e-strict verify-spike-smoke verify-spike-matrix clean

BENCH_FREQ_MHZ ?= 100
BENCH_COREMARK_ITERATIONS ?= 200
BENCH_DHRYSTONE_RUNS ?= 100000
CI_ACTION_REF_ARGS ?=
CI_GITHUB_AUTH_ARGS ?=
CI_PUBLISH_READINESS_ARGS ?=
CI_REMOTE_PREFLIGHT_ARGS ?=
CI_REMOTE_ARGS ?=
CI_REMOTE_DISPATCH_ARGS ?= --profiles smoke ci-evidence --wait
CI_REMOTE_CLOSURE_ARGS ?=
CI_REMOTE_PUBLISH_ARGS ?=

audit-tools:
	python3 scripts/tool_availability_audit.py --out-dir result/verification

audit-ci-publish-readiness:
	python3 scripts/ci_publish_readiness.py --out-dir result/verification $(CI_PUBLISH_READINESS_ARGS)

audit-ci-action-refs:
	python3 scripts/ci_action_ref_audit.py --out-dir result/verification $(CI_ACTION_REF_ARGS)

audit-ci-github-auth:
	python3 scripts/ci_github_auth_audit.py --out-dir result/verification $(CI_GITHUB_AUTH_ARGS)

audit-ci-remote-preflight:
	python3 scripts/ci_remote_preflight.py --out-dir result/verification $(CI_REMOTE_PREFLIGHT_ARGS)

audit-ci-remote:
	python3 scripts/ci_remote_evidence.py --out-dir result/verification $(CI_REMOTE_ARGS)

ci-remote-dispatch:
	python3 scripts/ci_remote_dispatch.py --out-dir result/verification $(CI_REMOTE_DISPATCH_ARGS)

ci-remote-closure:
	python3 scripts/ci_remote_closure.py --out-dir result/verification $(CI_REMOTE_CLOSURE_ARGS)

ci-remote-publish:
	python3 scripts/ci_remote_publish.py --out-dir result/verification $(CI_REMOTE_PUBLISH_ARGS)

audit-gaps: audit-tools
	python3 scripts/open_gap_audit.py --out-dir result/verification

audit-trace-config:
	python3 scripts/trace_config_audit.py --out-dir result/verification

audit-completion:
	python3 scripts/completion_audit.py --out-dir result/verification

build:
	build-ditdah32 --no-trace

build-trace:
	build-ditdah32 --trace

bench:
	python3 scripts/build_benchmarks.py --out-dir result/bench

bench-score: build
	python3 scripts/run_bench_sim.py \
		--coremark-iterations $(BENCH_COREMARK_ITERATIONS) \
		--dhrystone-runs $(BENCH_DHRYSTONE_RUNS) \
		--frequency-mhz $(BENCH_FREQ_MHZ)

coverage:
	python3 scripts/rv32ec_coverage.py --out-dir result/coverage

formal: build-trace
	python3 scripts/run_formal.py --depth 24

verify-rvfi-lite: build-trace
	python3 scripts/run_rvfi_lite.py --depth 24

verify-rvfi: build-trace
	python3 scripts/run_rvfi.py --depth 24

verify-riscv-dv: build-trace
	python3 scripts/run_riscv_dv.py --config test/riscv_dv/ditdah32_rv32ec.yaml

verify-compliance: build-trace
	python3 scripts/run_compliance.py

signoff-coverage: build-trace
	python3 scripts/run_signoff_coverage.py

test-model:
	python3 -m pytest test/test_model

test-isa:
	python3 -m pytest test/test_isa

test-scripts:
	python3 -m pytest test/test_scripts

test-isa-rtl: test-isa build-trace
	python3 scripts/rv32ec_isa_regress.py --out-dir result/isa
	python3 scripts/run_rtl_isa_matrix.py --isa-dir result/isa --out-dir result/rtl_trace/isa_artifacts

test: test-model test-isa test-scripts bench build-trace
	$(MAKE) -C test/test_ditdah32

verify:
	python3 scripts/run_verification_campaign.py --profile full

verify-ci-smoke:
	python3 scripts/run_verification_campaign.py --profile ci-smoke

verify-signoff:
	python3 scripts/run_verification_campaign.py --profile signoff

verify-iss: test-isa build-trace
	python3 scripts/rv32ec_isa_regress.py --out-dir result/isa
	python3 scripts/run_rtl_isa_matrix.py --isa-dir result/isa --out-dir result/rtl_trace/isa_artifacts
	python3 scripts/run_sail_iss_smoke.py --isa-dir result/isa --out-dir result/iss/sail_matrix --all-compatible --ram-base 0x0 --memory-size 0x80100000 --rom-base 0x90000000 --clint-base 0xa0000000 --allow-low-data-memory
	python3 scripts/run_spike_rv32e_strict.py --out-dir result/iss/spike_rv32e_strict
	python3 scripts/rv32ec_isa_regress.py --out-dir result/iss/spike_artifacts --spike-compatible
	python3 scripts/run_rtl_isa_matrix.py --isa-dir result/iss/spike_artifacts --out-dir result/rtl_trace/spike_highmem_artifacts
	python3 scripts/run_spike_iss_smoke.py --isa-dir result/iss/spike_artifacts --out-dir result/iss/spike_highmem --all-compatible
	python3 scripts/rv32ec_isa_regress.py --out-dir result/iss/sail_artifacts --spike-compatible
	python3 scripts/run_rtl_isa_matrix.py --isa-dir result/iss/sail_artifacts --out-dir result/rtl_trace/sail_highmem_artifacts
	python3 scripts/run_sail_iss_smoke.py --isa-dir result/iss/sail_artifacts --out-dir result/iss/sail_highmem --all-compatible
	python3 scripts/external_iss_full_report.py --out-dir result/iss/external_iss_full

verify-spike-smoke: test-isa
	python3 scripts/run_spike_iss_smoke.py --isa-dir result/isa --out-dir result/iss/spike_smoke

verify-spike-matrix: test-isa
	python3 scripts/run_spike_iss_smoke.py --isa-dir result/isa --out-dir result/iss/spike_matrix --all-compatible

verify-spike-highmem: test-isa build-trace
	python3 scripts/rv32ec_isa_regress.py --out-dir result/iss/spike_artifacts --spike-compatible
	python3 scripts/run_rtl_isa_matrix.py --isa-dir result/iss/spike_artifacts --out-dir result/rtl_trace/spike_highmem_artifacts
	python3 scripts/run_spike_iss_smoke.py --isa-dir result/iss/spike_artifacts --out-dir result/iss/spike_highmem --all-compatible

verify-spike-rv32e-strict:
	python3 scripts/run_spike_rv32e_strict.py --out-dir result/iss/spike_rv32e_strict

verify-sail-smoke: test-isa
	python3 scripts/run_sail_iss_smoke.py --isa-dir result/isa --out-dir result/iss/sail_smoke

verify-sail-matrix: test-isa
	python3 scripts/run_sail_iss_smoke.py --isa-dir result/isa --out-dir result/iss/sail_matrix --all-compatible --ram-base 0x0 --memory-size 0x80100000 --rom-base 0x90000000 --clint-base 0xa0000000 --allow-low-data-memory

verify-sail-highmem: test-isa build-trace
	python3 scripts/rv32ec_isa_regress.py --out-dir result/iss/sail_artifacts --spike-compatible
	python3 scripts/run_rtl_isa_matrix.py --isa-dir result/iss/sail_artifacts --out-dir result/rtl_trace/sail_highmem_artifacts
	python3 scripts/run_sail_iss_smoke.py --isa-dir result/iss/sail_artifacts --out-dir result/iss/sail_highmem --all-compatible

verify-smoke:
	python3 scripts/run_verification_campaign.py --profile smoke

verify-rtl:
	python3 scripts/run_verification_campaign.py --profile rtl

clean:
	rm -rf result
	$(MAKE) -C test/test_ditdah32 clean || true
