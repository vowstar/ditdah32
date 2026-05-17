# DitDah32 Memory Fault RVFI Contract

This document defines the architectural behavior and RVFI reporting contract
for DitDah32 memory faults caused by AXI-Lite non-`OKAY` responses. The
contract matches what the YosysHQ riscv-formal `fault` and `bus_dmem_fault`
property groups require, exposing the
`riscv-formal/cores/nerv/nerv.sv`.

## 1. Architectural behavior

AXI-Lite responses other than `OKAY` (`SLVERR = 2'b10`, `DECERR = 2'b11`) are
treated as recoverable RISC-V access faults. The core never halts; it always
traps to `mtvec` so software can observe and handle the failure.

### 1.1 Fetch fault (`mcause = 1`)

Trigger: `axi_rresp != 2'b00` on an instruction-fetch read response
(`axi_arprot[2] == 1`).

Effect at trap entry:

- `mcause` <- 32-bit `1` (instruction access fault).
- `mtval` <- faulting instruction PC.
- `mepc` <- faulting instruction PC.
- `mstatus.MPIE` <- previous `mstatus.MIE`.
- `mstatus.MIE` <- 0.
- `mstatus.MPP` <- `2'b11` (M-mode is the only privilege level).
- `pc` <- `mtvec & ~3` (direct mode).
- No register-file writeback.
- No data-memory side effect.

### 1.2 Load access fault (`mcause = 5`)

Trigger: `axi_rresp != 2'b00` on a data-load read response
(`axi_arprot[2] == 0`).

Effect at trap entry:

- `mcause` <- 32-bit `5` (load access fault).
- `mtval` <- faulting load address (`memAddr`).
- `mepc` <- PC of the load instruction.
- `mstatus` updated as in §1.1.
- `pc` <- `mtvec & ~3`.
- No `rd` writeback for the faulting load.

### 1.3 Store access fault (`mcause = 7`)

Trigger: `axi_bresp != 2'b00` on a data-store write response.

Effect at trap entry:

- `mcause` <- 32-bit `7` (store access fault).
- `mtval` <- faulting store address (`memAddr`).
- `mepc` <- PC of the store instruction.
- `mstatus` updated as in §1.1.
- `pc` <- `mtvec & ~3`.
- No retired `rvfi_mem_wmask` for the faulting store.

## 2. RVFI signal contract on the fault retire

Each fault produces one retire slot that satisfies the `rvfi_fault_check`
and `rvfi_bus_dmem_fault_check` invariants.

| RVFI signal | Fetch fault | Load fault | Store fault |
| --- | --- | --- | --- |
| `rvfi_valid` | 1 | 1 | 1 |
| `rvfi_trap` | 1 | 1 | 1 |
| `rvfi_insn` | 0 | original load encoding | original store encoding |
| `rvfi_rd_addr` | 0 | 0 | 0 |
| `rvfi_rd_wdata` | 0 | 0 | 0 |
| `rvfi_mem_addr` | `pc` (for ifetch) | faulting load address | faulting store address |
| `rvfi_mem_rmask` | 0 | 0 | 0 |
| `rvfi_mem_wmask` | 0 | 0 | 0 |
| `rvfi_mem_fault` | 1 | 1 | 1 |
| `rvfi_mem_fault_rmask` | original ifetch byte mask | original load byte mask | 0 |
| `rvfi_mem_fault_wmask` | 0 | 0 | original store byte mask |
| `rvfi_csr_mcause_wmask` | `32'hffffffff` | `32'hffffffff` | `32'hffffffff` |
| `rvfi_csr_mcause_wdata` | 1 | 5 | 7 |

The live `rvfi_mem_rmask`/`rvfi_mem_wmask` must be 0 on the fault retire; the
captured byte mask is preserved in the corresponding `*_fault_*mask` channel.
This matches the NERV pattern at
`riscv-formal/cores/nerv/nerv.sv:1236-1241`.

## 3. Bus-side contract

The wrapper's bus event stream
(`rvfi_bus_valid`, `rvfi_bus_addr`, `rvfi_bus_rmask`, `rvfi_bus_wmask`, ...)
is derived from completed AXI-Lite transactions. When `axi_rresp` or
`axi_bresp` reports a non-OKAY value, the bus event MUST still be reported,
because `bus_dmem_fault_check` relies on observing the faulting bus address.

The wrapper does not need to add a separate fault flag to the bus stream;
the riscv-formal check infers the fault by comparing the bus address against
the retire's `rvfi_mem_fault_rmask`/`rvfi_mem_fault_wmask`.

## 4. Implementation notes

- The trap-entry CSR writes (`mcause`, `mepc`, `mstatus`, `mtval`) are
  reported through the existing `trace_csr_*` interface. On a fault retire
  the trace channel reports `trace_csr_addr = 0x342` (mcause) with
  `trace_csr_wmask = 32'hffffffff` and `trace_csr_wdata` set to 1, 5, or 7
  as per §1.
- The architectural register `csrMtval` is updated atomically with `mcause`,
  using the same fault-cycle data.
- The state machine no longer enters the terminal `CoreState.TRAP` on AXI
  errors. Instead it enters `CoreState.IRQ`, which already performs the
  jump to `mtvec` plus the `rvfi_intr` shape for trap retires.
- `io.trap` still pulses high in the cycle the trap is reported; it remains
  a one-cycle handshake rather than a halt indicator.

## 5. Software-observable behavior

A handler that runs from `mtvec` can:

1. Read `mcause` (1/5/7) to dispatch on the fault type.
2. Read `mtval` for the faulting address.
3. Read `mepc` for the resumption PC.
4. Apply remediation (for example, log the address, retry, or escalate).
5. Use `mret` to resume execution at `mepc`.

If the handler chooses to immediately `mret` without remediation and the
fault source still misbehaves, the same fault re-fires; this is intentional
livelock that matches the spec rather than an architectural deadlock.

## 6. References

- RISC-V Privileged Architecture Spec v1.12 §3.1.16 (`mcause`), §3.3.1
  (trap entry).
- YosysHQ riscv-formal `checks/rvfi_fault_check.sv` and
  `checks/rvfi_bus_dmem_fault_check.sv` consumers of this contract.
