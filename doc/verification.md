# DitDah32 Verification Plan

DitDah32 verification uses the standard RV32 methodology: directed cocotb
RTL tests, RTL/ISS trace comparison against Spike and Sail, riscv-formal
RVFI proofs, RISCV-DV constrained-random programs, a local compliance
signature gate against Sail, and Verilator HDL coverage. Gaps that are not
closed by the local campaign are tracked in `doc/open_gaps.md`. Optional JTAG
debug adds direct protocol tests, OpenOCD/GDB interoperability, and bounded proofs.

## Commands

```bash
make test-model            # Python RV32EC reference model unit tests
make test-isa              # directed ISA regression artifacts
make test-scripts          # helper-script unit tests
make verify-smoke          # fast push/PR gate
make verify-rtl            # full cocotb suite
make verify-rvfi-lite      # local RVFI-lite adapter check
make verify-rvfi           # riscv-formal RV32EC implemented profile
make verify-iss            # composite Spike + Sail external ISS closure
make verify-riscv-dv       # constrained-random programs vs reference trace
make verify-compliance     # Sail-driven compliance signature gate
make test-jtag             # direct JTAG and OpenOCD/GDB flows
make formal-jtag           # JTAG DTM and DM protocol proofs
make verify-signoff        # local CPU/JTAG campaign + coverage + gap audit
make audit-gaps            # write result/verification/open_gaps.{json,md}
make audit-trace-config    # audit all trace and JTAG combinations
make audit-jtag-ppa        # generic synthesis baseline and optional cost
```

`build-ditdah32` is the default production build and omits architectural
`trace_*` and direct `rvfi_*` top-level ports. Targets that need trace pins
depend on `build-trace`. JTAG ports and logic exist only with `enableJtag=true`.

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
- riscv-formal passes all implemented-profile groups: all 62 RV32EC
  instruction models; PC, register, order, memory, bus, and fault checks;
  implemented CSR instruction, persistence, access, and WARL checks; complete
  trap, MRET, and interrupt CSR transitions; bounded liveness and WFI wake.
- Compliance signature gate: every test under `test/compliance/tests/`
  compiles for RV32E, runs on Sail to produce a reference signature, and
  matches the DUT's AXI-RAM signature word for word.
- JTAG debug passes IDCODE/DTMCS/DMI, halt/resume/reset, GPR/CSR access,
  8/16/32-bit memory access, abstract errors, EBREAK, interrupt-masked step,
  OpenOCD/GDB, TAP/DTM formal, and DM formal checks.
- The four trace/JTAG configurations build independently; no-JTAG synthesis
  remains at the recorded production cell-count and logic-depth baseline.
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
| `result/iss/` | Spike + Sail differential |
| `result/riscv_dv/riscv_dv.json` | RISCV-DV regression |
| `result/compliance/compliance.json` | compliance signature gate |
| `result/bench/benchmark_scores.{json,md}` | local RTL timing-marker estimate |
| `result/verification/open_gaps.{json,md}` | gap audit |
| `result/verification/{trace_config,jtag_ppa}.{json,md}` | configuration and PPA proxy audits |
| `result/verification/completion_audit.{json,md}` | aggregated checklist |

## Benchmarks

CoreMark and Dhrystone bare-metal images build for `rv32ec/ilp32e` and run
on RTL through the shared AXI-Lite RAM. `make bench-score
BENCH_FREQ_MHZ=100` records local RTL timing-marker cycle counts at the
given frequency. This proves functional benchmark completion on the RTL,
but does not prove certified CoreMark or Dhrystone scores, real
post-synthesis clock timing, or long-duration benchmark stability.

## RVFI Wrapper

`formal/riscv_formal/ditdah32/wrapper.sv` adapts the DV trace to RVFI and
carries independently gated WFI, trap, interrupt, CSR access, and WARL proofs.
