# DitDah32 Verification Plan

DitDah32 verification uses the standard RV32 methodology: directed cocotb
RTL tests, RTL/ISS trace comparison against Spike and Sail, riscv-formal
RVFI proofs, RISCV-DV constrained-random programs, a local compliance
signature gate against Sail, and Verilator HDL coverage. Gaps that are not
closed by the local campaign are tracked in `doc/open_gaps.md`.

## Commands

```bash
make test-model            # Python RV32EC reference model unit tests
make test-isa              # directed ISA regression artifacts
make test-scripts          # helper-script unit tests
make verify-smoke          # fast push/PR gate
make verify-rtl            # full cocotb suite
make verify-rvfi-lite      # local RVFI-lite adapter check
make verify-rvfi           # riscv-formal RVFI subset (Spike-compatible)
make verify-iss            # composite Spike + Sail external ISS closure
make verify-riscv-dv       # constrained-random programs vs reference trace
make verify-compliance     # Sail-driven compliance signature gate
make verify-signoff        # everything above + Verilator coverage + gap audit
make audit-gaps            # write result/verification/open_gaps.{json,md}
make audit-trace-config    # verify production omits trace pins
```

`build-ditdah32` is the default production build and omits architectural
`trace_*` and direct `rvfi_*` top-level ports. Targets that need trace pins
depend on `build-trace`.

## Pass Criteria

- Python reference model and ISA regression tests pass.
- Generated Verilog compiles.
- Directed cocotb tests cover: reset/fetch, aligned and straddled fetch,
  RV32E ALU register/immediate, branches, jumps, RVC compressed integer,
  aligned and misaligned load/store on the shared AXI-Lite port, `FENCE`,
  `ECALL`, `EBREAK`, `MRET`, WFI, `Zicsr`, recoverable AXI access faults,
  and machine software/timer/external interrupt entry.
- The shared AXI4-Lite subset is exercised for instruction fetch, aligned
  load/store, `WSTRB`, `ARPROT`, deterministic RAM, and no data request on
  misaligned traps. The initial AXI verification target is protocol-level for the shared AXI-Lite path.
- RTL JSONL traces match the Python reference model for every ISA
  artifact.
- External ISS differential: Spike and Sail diff cleanly against RTL for
  all matrix entries; non-RV32E artifacts are reported skipped, not
  silently passed.
- riscv-formal RVFI subset passes: `pc_fwd`, `pc_bwd`, `reg`, `unique`,
  `causal`, `causal_io`, `causal_mem`, `bus_imem`, `bus_dmem`,
  `bus_dmem_io_{read,write,order}`, `fault`, `bus_{i,d}mem_fault`,
  `liveness_bounded`, `wfi_wake`, `interrupt_entry_shape`,
  `trap_entry_mstatus`, `mret_exit_mstatus`, `mip_mirror`,
  `mcause_interrupt_encoding`, `mpie_swap_exception`,
  `csr_readonly_illegal_write`, `csr_warl_legalization`, `csrw_check` for
  every writable M-mode CSR (`mstatus`, `mie`, `mtvec`, `mscratch`,
  `mepc`, `mcause`, `mtval`), reserved-zero / read-only `csr_state_subset`
  checks, plus `hang`, `ill`, and `cover`. All 62 instructions in the
  `rv32ic` set pass instruction-semantic checks under a per-RVC-format
  register-restrict assume.
- Compliance signature gate: every test under `test/compliance/tests/`
  compiles for RV32E, runs on Sail to produce a reference signature, and
  matches the DUT's AXI-RAM signature word for word.
- `make audit-gaps` reports closed for every gap recorded in
  `doc/open_gaps.md`.
- Working tree must not be dirty after `make verify-signoff`.

## Reports

| Path | Producer |
|---|---|
| `result/verification/<profile>.json` | campaign runner |
| `result/rtl_trace/isa_artifacts/` | RTL ISA matrix |
| `result/coverage/` | instruction + illegal-class coverage |
| `result/axi/` | AXI backpressure stress |
| `result/formal/rvfi/rvfi.json` | riscv-formal RVFI subset |
| `result/iss/` | Spike + Sail differential |
| `result/riscv_dv/riscv_dv.json` | RISCV-DV regression |
| `result/compliance/compliance.json` | compliance signature gate |
| `result/bench/benchmark_scores.{json,md}` | local RTL timing-marker estimate |
| `result/verification/open_gaps.{json,md}` | gap audit |
| `result/verification/completion_audit.{json,md}` | aggregated checklist |

## Benchmarks

CoreMark and Dhrystone bare-metal images build for `rv32ec/ilp32e` and run
on RTL through the shared AXI-Lite RAM. `make bench-score
BENCH_FREQ_MHZ=100` records local RTL timing-marker cycle counts at the
given frequency. This proves functional benchmark completion on the RTL,
but does not prove certified CoreMark or Dhrystone scores, real
post-synthesis clock timing, or long-duration benchmark stability.

## RVFI Wrapper

`formal/riscv_formal/ditdah32/wrapper.sv` adapts DitDah32's `trace_*` and
`rvfi_*` outputs to riscv-formal. The wrapper also carries inline SVA for
the bounded WFI wake, trap-CSR invariants, read-only CSR illegal-write,
and WARL legalization proofs, gated by per-property `DITDAH32_RVFI_*`
defines so each runs as an independent SBY proof.
