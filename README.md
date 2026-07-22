# DitDah32

DitDah32 is a signed-off RV32EC control core for always-on power domains and PHY control, where area and standby power matter more than throughput. It is verified by Sail and Spike differential co-simulation, riscv-formal RVFI property proofs, and a Sail-driven compliance gate. The core implements `Zicsr` and a minimal M-mode trap profile in a two-stage pipeline, written in the Zaozi EDSL.

## Scope

In-scope: RV32E with Zca compressed, `Zicsr`, direct M-mode traps, `MRET`, WFI, machine software/timer/external interrupts, single-beat AXI4-Lite memory boundary, and optional single-hart RISC-V Debug v1.0 over JTAG.

Out-of-scope: RV32I 32-register mode, M/A/F/D/B/V extensions, caches, MMU, PMP, debug authentication, triggers, Program Buffer, system bus access, multi-hart debug, vectored traps, delegation, user and supervisor modes.

JTAG is disabled by default; enabling it exposes machine state and memory without authentication, so production integration must secure or disable the port.

## Architecture

[![DitDah32 microarchitecture](doc/ditdah32_microarchitecture.drawio.svg)](doc/microarchitecture.md)

See `doc/microarchitecture.md` for the pipeline and unit contracts.

## Results

Process: TSMC 16FFCLL, 9-track (BWP16P90CPD), Calibre-clean LVS and DRC signoff for the default no-JTAG configuration. Silicon numbers below are from the v1.2.0 signoff netlist; re-signoff of the current fetch-overlap core is pending.

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
| 0-wait TCM (intrinsic) | 0.382 | 0.192 |
| AXI-Lite, 2 wait-states | 0.193 | 0.097 |

`make bench-score` or `nix run .#score` reproduce the performance numbers.

## Build

```bash
nix build .#default --no-link  # production package beside local reports
nix develop
build-ditdah32             # production, no trace ports
build-ditdah32 --trace     # verification trace collateral
build-ditdah32 --jtag      # optional JTAG debug configuration
```

The default IDCODE is an integration placeholder; set `jtagIdcode` to an assigned value before hardware release.

## Release

Tag releases provide `ditdah32-vX.Y.Z.tar.gz` and the optional
`ditdah32-vX.Y.Z-jtag.tar.gz`; both disable trace and include a manifest,
filelist, and license. `make package-release RELEASE_TAG=vX.Y.Z` reproduces
the assets locally.

## Test

```bash
make test-model            # Python reference model
make test-isa              # ISA regression artifacts
cd test/test_ditdah32 && make   # cocotb RTL suite
make test-jtag             # direct JTAG plus OpenOCD/GDB
```

## Verify

```bash
make verify-smoke          # fast push/PR gate
make verify-rvfi           # riscv-formal RV32EC implemented profile
make verify-compliance     # Sail-driven compliance signature gate
make verify-signoff        # local CPU/JTAG campaign; compliance is separate
make formal-jtag            # JTAG DTM and DM protocol proofs
make audit-jtag-ppa         # disabled baseline and optional area proxy
make audit-gaps            # gap audit, writes result/verification/open_gaps.{json,md}
```

Reports land under `result/`. See `doc/verification.md` for methodology and pass criteria.

## Credits

Independent RV32EC implementation. Verification and tooling build on open-source projects whose methodology influenced this work.

- [Ibex](https://github.com/lowRISC/ibex) and its demo system: core/debug boundary, OpenOCD integration, and verification methodology.
- [PicoRV32](https://github.com/YosysHQ/picorv32): practical Verilog testbench, RVFI and riscv-formal integration as a reference pattern.
- [Rocket Chip](https://github.com/chipsalliance/rocket-chip): configurable JTAG DTM handshake and reset behavior.
- [RISC-V Debug Specification](https://github.com/riscv/riscv-debug-spec): JTAG DTM, DMI, Debug Module, abstract command, and run-control contracts.
- [riscv-formal](https://github.com/YosysHQ/riscv-formal): RVFI specification, property-group framework, and the NERV reference implementation.
- [T1](https://github.com/chipsalliance/t1): Nix-driven artifact, build, run, and check separation.
- [riscv-arch-test](https://github.com/riscv-non-isa/riscv-arch-test): compile, run, dump, compare signature convention.
- [Spike](https://github.com/riscv-software-src/riscv-isa-sim) and [Sail-RISCV](https://github.com/riscv/sail-riscv): reference ISS models for differential testing and compliance signatures.
- [Zaozi](https://github.com/vowstar/uart_zaozi): Chisel and Nix project layout reference.
