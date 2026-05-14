# DitDah32 Microarchitecture

## Overview

DitDah32 is a two-stage in-order RV32EC core:

- IF: instruction fetch and instruction-buffer maintenance.
- EX/WB: decode, execute, memory access, trap decision, and register writeback.

The design favors small area and simple verification over throughput. There is
no speculation beyond the next sequential fetch, and no architectural commit
from a killed instruction.

## Pipeline State

The architectural state is:

- `pc`: current instruction PC.
- `x[0..15]`: RV32E integer register file.
- minimal M-mode CSRs for trap and interrupt handling.
- fatal trap state for terminal AXI response errors.
- sleep state entered by WFI.

Microarchitectural state may include:

- fetch word buffer,
- buffered halfword valid bits,
- decoded instruction fields,
- pending data request state,
- AXI boundary arbitration state.

Microarchitectural state must not be externally visible except through the
documented AXI and trace interfaces.

## AXI Boundary

The external memory boundary is one shared AXI-style master port. The initial
implementation uses a single-beat AXI4-Lite compatible subset.

The core keeps a small compact internal request/response shape:

- IF asks for one aligned 32-bit instruction word.
- LSU asks for one load or store.
- A 2:1 boundary arbiter translates those internal requests to one AXI
  valid/ready port.

This keeps AXI timing, response, and future interconnect details out of the
decode and execute logic. The structure keeps IF and LSU
separate inside the core, but follows PicoRV32's integration style by exposing a
single external memory master. T1 and open AXI muxes are used as references for
explicit AXI channel separation and traceable memory verification, not for
vector LSU or crossbar complexity.

## IF Stage

Instruction memory is byte addressed and little-endian. Because RV32EC includes
compressed instructions, instruction alignment is 16 bits.

The IF stage fetches aligned 32-bit words through the shared AXI read channel:

- `axi_araddr` is the aligned word address.
- `axi_arvalid` stays asserted until `axi_arready`.
- `axi_arprot` marks fetch requests as instruction accesses.
- `axi_rready` accepts one 32-bit response for the accepted request.
- `pc[1]` selects the lower or upper halfword.
- If the selected halfword has low bits not equal to `2'b11`, the instruction is
  16 bits and advances PC by 2.
- If the selected halfword has low bits equal to `2'b11`, the instruction is 32
  bits and advances PC by 4.
- A 32-bit instruction at `pc[1] = 1` straddles two aligned fetch words and needs
  the next word before decode.

## EX/WB Stage

EX/WB consumes at most one decoded instruction at a time and produces at most one
architectural commit.

The stage performs:

- RV32E decode.
- RV32EC compressed decompression into the same internal operation format.
- ALU and branch decisions.
- Load/store request generation and response handling.
- Register writeback.
- Trap detection.

Taken branches and jumps flush any sequential instruction fetched after the
branch PC. The first implementation does not prefetch beyond the current
instruction, so a redirect updates `pc` before the next AXI fetch request is
issued.

## Register File

The register file has 16 entries of 32 bits.

- x0 reads as zero.
- Writes to x0 are ignored.
- x1 through x15 are writable.
- Any instruction that refers to x16 through x31 is illegal.

## Load/Store Unit

The LSU issues one request at a time into the internal IF/LSU-to-AXI arbiter.
When an LSU request is selected, request control must remain stable until the
relevant AXI address and data handshakes complete.

All initial load/store AXI accesses are single aligned 32-bit word transfers:

- byte and halfword loads read the containing word and select lanes internally;
- byte and halfword stores drive `axi_wstrb` for the affected byte lanes;
- store address and data channels may be accepted independently, but the
  instruction commits only after the write response;
- load instructions commit only after the read response.

Non-OKAY AXI responses are terminal errors in the initial halt-on-trap model.
Fetch, load, and store response errors emit one trapping trace item with the
AXI error trap cause. Load response errors suppress register writeback, and
store response errors suppress the normal store commit trace.

Misaligned access policy:

- halfword access requires `addr[0] == 0`,
- word access requires `addr[1:0] == 0`,
- misaligned access traps before a data AXI request is issued.

## Trap Handling

Standard instruction, CSR, and interrupt traps use direct machine-mode trap
entry. Trap entry writes `mepc`, `mcause`, `mtval`, and the relevant `mstatus`
fields, redirects `pc` to `mtvec.BASE`, and emits one trap trace item. `MRET`
returns to `mepc` and restores `mstatus.MIE` from `mstatus.MPIE`.

AXI response errors remain fatal. The core asserts `trap`, enters fatal trap
state, and stops committing later instructions.

WFI commits, advances `pc` to the following instruction, enters sleep, deasserts
`core_busy`, asserts the sleep output, and stops issuing fetch requests until an
individually enabled interrupt is pending. If global `mstatus.MIE` is set on
wake, the core takes the interrupt trap before fetching the following
instruction.

Trap causes:

- illegal instruction,
- unsupported extension,
- RV32E register index violation,
- misaligned instruction target,
- misaligned load,
- misaligned store,
- AXI response error,
- environment call,
- breakpoint.

CSR state:

- `mstatus`: `MIE`, `MPIE`, and `MPP` are implemented for M-mode trap entry.
- `mie`: software, timer, and external interrupt enables are implemented.
- `mip`: software, timer, and external pending bits reflect top-level IRQ
  inputs.
- `mtvec`, `mepc`, `mcause`, `mtval`, and `mscratch` are read/write machine
  CSRs.
- ID CSRs and `misa` are read-only constants.

## Trace Equivalence Boundary

RTL and reference model equivalence is architectural trace equivalence. A trace
item is emitted for each committed or trapping instruction. The initial trace
schema is defined in `doc/verification.md`.

The current Zaozi RTL connects these pins for RV32E 32-bit instructions and the
RV32EC compressed integer subset. The same interface must be kept stable as
JSONL trace extraction and ISS comparison are added.
