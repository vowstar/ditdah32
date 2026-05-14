# DitDah32 Benchmark Bring-Up

This directory contains benchmark sources and DitDah32-specific bare-metal
runtime code for RV32EC RTL bring-up.

## Source Layout

- `coremark/upstream/` contains unmodified CoreMark files copied from the EEMBC
  CoreMark repository. Keep the upstream license file with these sources.
- `coremark/ditdah32/` contains the DitDah32 CoreMark port layer.
- `dhrystone/upstream/` contains unmodified Dhrystone 2.1 C files extracted
  from the Netlib `dhry-c` archive.
- `dhrystone/ditdah32/` contains the DitDah32 Dhrystone wrapper.
- `common/` contains the freestanding RV32EC startup, linker script, software
  integer arithmetic helpers, fixed result block, tiny heap, and libc stubs.

## Build Command

```bash
nix develop
make bench
```

`make bench` writes ELF, binary, disassembly, map, and manifest artifacts under
`result/bench/`.

The build uses `-march=rv32ec -mabi=ilp32e`, no hosted C library, and no M
extension. Multiplication and division are provided by the local software
runtime.

## RTL Pass Criteria

The cocotb benchmark tests load each benchmark binary into the deterministic
AXI-Lite RAM, run until the core traps on `EBREAK`, then read the fixed
`ditdah32_bench_result` structure from memory.

Pass requires:

- result magic equals `0xdd32beef`;
- benchmark ID matches the test;
- status equals zero;
- the final trap cause is `EBREAK`.

CoreMark currently runs the official profile parameter set:

- `TOTAL_DATA_SIZE=1200`;
- seeds `8, 8, 8`;
- one iteration.

Dhrystone currently runs one benchmark loop. These tests validate functional
benchmark completion on RV32EC RTL; they do not claim certified benchmark
scores or stable performance numbers.
