# DitDah32

A tiny two-stage RV32EC core with `Zicsr` and a minimal M-mode control profile,
written in the Zaozi EDSL.

## Scope

In-scope: RV32E + Zca compressed, `Zicsr`, direct M-mode traps, `MRET`, WFI,
machine software/timer/external interrupts, single-beat AXI4-Lite memory
boundary.

Out-of-scope: RV32I 32-register mode, M/A/F/D/B/V extensions, caches, MMU,
PMP, debug, vectored traps, delegation, user/supervisor modes.

## Build

```bash
nix develop
build-ditdah32             # production, no trace ports
build-ditdah32 --trace     # verification build with trace ports
```

## Test

```bash
make test-model            # Python reference model
make test-isa              # ISA regression artifacts
cd test/test_ditdah32 && make   # cocotb RTL suite
```

## Verify

```bash
make verify-smoke          # fast push/PR gate
make verify-rvfi           # riscv-formal RVFI subset
make verify-compliance     # Sail-driven compliance signature gate
make verify-signoff        # full local signoff (ISS + RVFI + RISCV-DV + coverage)
make audit-gaps            # gap audit -> result/verification/open_gaps.{json,md}
```

Reports land under `result/`. See `doc/verification.md` for methodology and
pass criteria.

## Benchmarks

```bash
make bench                 # build CoreMark + Dhrystone images
make bench-score BENCH_FREQ_MHZ=100
```

These are functional bring-up images, not certified performance score runs.

## Layout

```text
ditdah32/src/     Zaozi RTL source
doc/              requirements, ISA scope, microarchitecture, verification
scripts/          reference model, runners, audits
test/             cocotb suite + compliance gate + ISA regression
bench/            CoreMark / Dhrystone bring-up
formal/           riscv-formal wrapper and configs
.github/          CI workflow
```

## Credits

DitDah32 is an independent RV32EC implementation. The verification campaign
and toolchain integration build on a number of open-source projects whose
methodology and code influenced this work:

- [Ibex](https://github.com/lowRISC/ibex) — RTL/ISS trace-comparison
  verification methodology and bounded WFI / formal-pattern style.
- [PicoRV32](https://github.com/YosysHQ/picorv32) — practical Verilog
  testbench plus RVFI / riscv-formal integration as a reference pattern.
- [riscv-formal](https://github.com/YosysHQ/riscv-formal) — RVFI
  specification, property-group framework, and the NERV reference
  implementation.
- [T1](https://github.com/chipsalliance/t1) — Nix-driven artifact /
  build / run / check separation.
- [riscv-arch-test](https://github.com/riscv-non-isa/riscv-arch-test) —
  compile/run/dump/compare signature convention.
- [Spike](https://github.com/riscv-software-src/riscv-isa-sim) and
  [Sail-RISCV](https://github.com/riscv/sail-riscv) — reference ISS
  models for differential testing and compliance signatures.
- [Zaozi](https://github.com/vowstar/uart_zaozi) — Chisel/Nix project
  layout reference.
