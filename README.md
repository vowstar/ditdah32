# DitDah32

DitDah32 is a signed-off RV32EC control core for always-on power domains and PHY control, where area and standby power matter more than throughput. It is verified by Sail and Spike differential co-simulation, riscv-formal RVFI property proofs, and a Sail-driven compliance gate. The core implements `Zicsr` and a minimal M-mode trap profile in a two-stage pipeline, written in the Zaozi EDSL.

## Scope

In-scope: RV32E with Zca compressed, `Zicsr`, direct M-mode traps, `MRET`, WFI, machine software/timer/external interrupts, single-beat AXI4-Lite memory boundary.

Out-of-scope: RV32I 32-register mode, M/A/F/D/B/V extensions, caches, MMU, PMP, debug, vectored traps, delegation, user and supervisor modes.

## Results

Process: TSMC 16FFCLL, 9-track (BWP16P90CPD), Calibre-clean LVS and DRC signoff.

Area: 14.3 kGE, 2219 um^2 standard cell (5534 combinational and 861 flops).

| Corner | Fmax | Dynamic (CoreMark) | Leakage |
| --- | ---: | ---: | ---: |
| SS 0.72 V 125 C, signoff | 314 MHz | 0.63 uW/MHz | 6.2 uW |
| TT 0.80 V 25 C, typical | 455 MHz | 0.76 uW/MHz | 0.4 uW |
| TT 0.55 V 25 C, near-threshold | 146 MHz | 0.33 uW/MHz | 0.2 uW |

Post-layout STA at typical RC; the worst path is AXI-input to register (an integration-time budget). Power from CoreMark activity, about 0.76 pJ/cycle at 0.80 V.

RV32EC has no hardware multiply or divide. Benchmark numbers are RTL cycle-accurate and frequency-normalised, not EEMBC-certified.

| Memory model | CoreMark/MHz | DMIPS/MHz |
| --- | ---: | ---: |
| 0-wait TCM (intrinsic) | 0.289 | 0.163 |
| AXI-Lite, 2 wait-states | 0.144 | 0.081 |

`make bench-score` or `nix run .#score` reproduce the performance numbers.

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
make verify-signoff        # full local signoff (ISS, RVFI, RISCV-DV, coverage)
make audit-gaps            # gap audit, writes result/verification/open_gaps.{json,md}
```

Reports land under `result/`. See `doc/verification.md` for methodology and pass criteria.

## Credits

Independent RV32EC implementation. Verification and tooling build on open-source projects whose methodology influenced this work.

- [Ibex](https://github.com/lowRISC/ibex): RTL and ISS trace-comparison verification methodology, bounded WFI and formal-pattern style.
- [PicoRV32](https://github.com/YosysHQ/picorv32): practical Verilog testbench, RVFI and riscv-formal integration as a reference pattern.
- [riscv-formal](https://github.com/YosysHQ/riscv-formal): RVFI specification, property-group framework, and the NERV reference implementation.
- [T1](https://github.com/chipsalliance/t1): Nix-driven artifact, build, run, and check separation.
- [riscv-arch-test](https://github.com/riscv-non-isa/riscv-arch-test): compile, run, dump, compare signature convention.
- [Spike](https://github.com/riscv-software-src/riscv-isa-sim) and [Sail-RISCV](https://github.com/riscv/sail-riscv): reference ISS models for differential testing and compliance signatures.
- [Zaozi](https://github.com/vowstar/uart_zaozi): Chisel and Nix project layout reference.
