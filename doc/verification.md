# DitDah32 Verification Plan

DitDah32 verification uses the standard RV32 methodology: directed cocotb RTL
tests, RTL/ISS comparison against Spike and Sail, riscv-formal RVFI proofs,
RISCV-DV programs, a Sail compliance signature gate, and Verilator coverage.
Gaps the campaign does not close are tracked in `doc/open_gaps.md`. Optional
JTAG debug adds protocol tests and OpenOCD/GDB interoperability.

## Commands

```bash
make test-model            # Python RV32EC reference model unit tests
make test-isa              # directed ISA regression artifacts
make test-scripts          # helper-script unit tests
make verify-smoke          # fast push/PR gate
make verify-rtl            # full cocotb suite
make verify-rvfi-lite      # RVFI well-formedness over the trace surface
make verify-rvfi           # riscv-formal RV32EC implemented profile
make verify-iss            # composite Spike + Sail external ISS closure
make verify-riscv-dv       # constrained-random programs vs reference trace
make verify-compliance     # Sail-driven compliance signature gate
make test-jtag             # direct JTAG and OpenOCD/GDB flows
make formal              # AXI, trap, and quiescence bounded proofs
make formal-jtag           # JTAG DTM and DM bounded proofs
make verify-commercial     # unbounded proof of the layer("DV") SVA
make verify-signoff        # local CPU/JTAG campaign + coverage + gap audit
make audit-gaps            # write result/verification/open_gaps.{json,md}
make audit-trace-config    # audit all trace and JTAG combinations
make audit-jtag-ppa        # generic synthesis baseline and optional cost
make package-release RELEASE_TAG=vX.Y.Z  # package trace-free RTL assets
```

`build-ditdah32` is the default production build and omits architectural
`trace_*` and direct `rvfi_*` top-level ports. Targets that need trace pins
depend on `build-trace`. JTAG ports and logic exist only with `enableJtag=true`.

## Pass Criteria

- Python reference model and ISA regression tests pass.
- Generated Verilog compiles.
- Directed cocotb tests cover reset/fetch, aligned and straddled fetch, RV32E
  ALU register/immediate, branches, jumps, RVC, aligned and misaligned
  load/store on the shared AXI-Lite port, `FENCE`, `ECALL`, `EBREAK`, `MRET`,
  WFI, `Zicsr`, AXI faults, and software/timer/external interrupt entry.
- The shared AXI4-Lite subset is exercised for instruction fetch, aligned
  load/store, `WSTRB`, `ARPROT`, deterministic RAM, and no data request on
  misaligned traps. The AXI target is protocol-level.
- RTL JSONL traces match the Python reference model for every ISA
  artifact.
- External ISS differential: Spike and Sail diff cleanly against RTL for all
  matrix entries. Non-RV32E artifacts are reported skipped, not silently
  passed.
- riscv-formal passes every implemented-profile group. Five assumptions
  narrow what they see: the instruction models run on non-trapping,
  non-interrupted retirements under per-format x0-x15 register constraints,
  CSR persistence assumes no trap or MRET between write and read, and
  liveness excludes WFI. Those cases are proven unbounded in the SVA layer.
- Compliance signature gate: every test under `test/compliance/tests/`
  compiles for RV32E, runs on Sail to produce a reference signature, and
  matches the DUT's AXI-RAM signature word for word.
- JTAG debug passes IDCODE/DTMCS/DMI, halt/resume/reset, GPR/CSR access,
  8/16/32-bit memory access, abstract errors, EBREAK, interrupt-masked step,
  OpenOCD/GDB, and bounded TAP/DTM and DM protocol proofs.
- The four trace/JTAG configurations build independently, and no-JTAG
  synthesis holds the recorded cell-count and logic-depth baseline.
- Release archives disable trace and compile from their packaged filelists.
- `make audit-gaps` reproduces the statuses in `doc/open_gaps.md`.
- `make verify-signoff` introduces no tracked working-tree changes.

## Reports

| Path | Producer |
|---|---|
| `result/verification/<profile>.json` | campaign runner |
| `result/rtl_trace/isa_artifacts/` | RTL ISA matrix |
| `result/coverage/` | instruction + illegal-class coverage |
| `result/axi/` | AXI backpressure stress |
| `result/formal/rvfi/rvfi.json` | riscv-formal RV32EC implemented profile |
| `result/formal/jtag/jtag.json` | JTAG DTM and DM bounded proofs |
| `result/formal/commercial/` | unbounded FPV verdicts and cover reachability |
| `result/iss/` | Spike + Sail differential |
| `result/riscv_dv/riscv_dv.json` | RISCV-DV regression |
| `result/compliance/compliance.json` | compliance signature gate |
| `result/bench/benchmark_scores.{json,md}` | local RTL timing-marker estimate |
| `result/verification/open_gaps.{json,md}` | gap audit |
| `result/verification/{trace_config,jtag_ppa}.{json,md}` | configuration and PPA proxy audits |
| `result/verification/completion_audit.{json,md}` | aggregated checklist |
| `result/release/` | standard and JTAG release archives |

## Benchmarks

CoreMark and Dhrystone bare-metal images build for `rv32ec/ilp32e` and run on
RTL through the shared AXI-Lite RAM. `make bench-score BENCH_FREQ_MHZ=100`
records local timing-marker cycle counts at that frequency. It proves
functional completion on RTL, not certified scores, post-synthesis timing, or
long-duration stability.

## Local SVA

`ditdah32/src/DitDah32Sva.scala` states 38 assertions and 19 covers inside
`layer("DV")`, so they reach `result/sva/DitDah32_DV.sv` as SVA and the
production module stays assertion-free. They cover AXI stability and
single-outstanding behaviour, bus faults, sleep quiescence, RV32E register
range, trap entry and MRET CSR transitions, interrupt cause priority, WARL
legalization, and WFI wake. Every antecedent carries a reachability cover.

`make verify-commercial` proves all 38 without a depth bound on JasperGold and
VC Formal, and fails the run if any declared property goes unreported or any
antecedent is unreachable. The SymbiYosys targets build without the SVA,
because yosys-slang rejects the per-atom clocking firtool emits.

Proven is not sufficient, and nothing here measures whether these 38 would
catch a design fault. No target reports the mutation coverage of the property
set, so its reach over the design is unmeasured and no figure is published.

## RVFI Wrapper

`formal/riscv_formal/ditdah32/wrapper.sv` adapts the DV trace to RVFI and
carries independently gated WFI, trap, interrupt, CSR access, and WARL proofs.
