# DitDah32 Requirements

## Product Statement

DitDah32 is a tiny two-stage RV32EC core for low-resource embedded systems.

## Architectural Scope

- Base ISA: RV32EC.
- Control profile: RV32EC with `Zicsr` and a minimal machine-mode privileged
  subset for direct trap entry, `MRET`, WFI, and machine software, timer, and
  external interrupts.
- XLEN: 32.
- Architectural integer registers: x0 through x15.
- x0 always reads as zero and ignores writes.
- Instructions that require x16 through x31 are illegal.
- Unsupported extensions are illegal.
- Instruction memory is little-endian.
- Data memory is little-endian.
- With the C extension enabled, instruction alignment is 16 bits.

## Pipeline Model

The core uses two in-order stages:

- IF fetches one instruction word from the instruction bus.
- EX/WB decodes, executes, performs data memory access when needed, and commits
  at most one architectural register writeback.

The architectural model is single-issue and in-order. There is no speculative
architectural commit.

## External Bus Model

The processor top level exposes one AXI-style external memory master interface.
The first implementation target is a single-beat AXI4-Lite compatible subset:

- one shared read/write AXI master port;
- 32-bit address and data width;
- at most one outstanding read;
- at most one outstanding write;
- no bursts, IDs, locks, cache attributes, QoS, or out-of-order responses.

The core microarchitecture may keep a compact internal instruction and
data request interfaces, but an internal boundary arbiter merges those requests
into the single external AXI port. AXI channel signals must remain stable while
`VALID` is asserted and `READY` is low.

Shared AXI port:

- `axi_arvalid` requests a read at `axi_araddr`.
- `axi_arready` accepts the read request.
- `axi_rvalid` marks `axi_rdata` and `axi_rresp` valid.
- `axi_rready` accepts the read response.
- `axi_awvalid/axi_awready`, `axi_wvalid/axi_wready`, and
  `axi_bvalid/axi_bready` carry writes.
- `axi_wstrb` contains byte write enables.
- `axi_arprot` is fixed to instruction access for fetch requests and data access
  for load requests.
- Load requests read the aligned 32-bit word containing the addressed byte or
  halfword. The core selects and extends the requested value internally.
- Store requests write the aligned 32-bit word containing the addressed byte or
  halfword and use `axi_wstrb` to select written lanes.
- Any accepted read or write response with a non-OKAY response code traps with
  `AXI_ERROR` and does not produce a normal architectural commit. A fetch
  response error traps at the current PC with instruction bits reported as zero.
  A load response error traps without register writeback. A store response error
  traps without a normal store commit trace.
- Misaligned load and store accesses trap before an AXI request is issued.
- A trapping load or store must not commit architectural register or memory side
  effects.

All memory accesses are byte addressed and little-endian.

## Interrupt and CSR Model

The control profile uses the standard RISC-V `Zicsr` CSR instruction extension
for CSR read-modify-write instructions. WFI is not a `Zicsr` instruction; it is
a non-CSR privileged `SYSTEM` instruction.

The first machine-mode subset is intentionally small:

- The core always runs in M-mode.
- `CSRRW`, `CSRRS`, `CSRRC`, `CSRRWI`, `CSRRSI`, and `CSRRCI` are supported.
- Implemented machine CSRs are `mstatus`, `mie`, `mip`, `mtvec`, `mscratch`,
  `mepc`, `mcause`, `mtval`, `mvendorid`, `marchid`, `mimpid`, `mhartid`, and
  `misa`.
- `mtvec` direct mode is supported. Vectored mode is not required in this
  phase.
- Interrupt inputs are machine software, machine timer, and machine external.
- An interrupt may be taken between architectural instructions when its pending
  bit is individually enabled in `mie` and global `mstatus.MIE` is set.
- Interrupt input pins are level-sensitive. Software or the integration
  environment must deassert the source before `MRET` if it should not be taken
  again immediately.
- Interrupt priority is external, then software, then timer, matching the
  project-local simplified priority order.
- Trap entry writes `mepc`, `mcause`, `mtval`, and `mstatus.MPIE/MIE/MPP`, then
  redirects `pc` to `mtvec.BASE`.
- `MRET` restores `pc` from `mepc` and restores `mstatus.MIE` from
  `mstatus.MPIE`.
- WFI commits as a privileged instruction, advances to the following PC, stops
  fetch, asserts the sleep output, and resumes when an individually enabled
  interrupt is pending. If global `mstatus.MIE` is also set at wake, the core
  takes the interrupt trap before fetching the following instruction.
- If WFI wakes while global `mstatus.MIE` is clear, execution resumes at the
  post-WFI PC without taking an interrupt trap.
- The WFI sleep decision is independent of PicoRV32 custom IRQ instructions.
  DitDah32 does not implement PicoRV32 `waitirq`, `retirq`, `maskirq`, `getq`,
  `setq`, or `timer`.

## Internal Fetch and Data Model

The internal fetch unit may request aligned 32-bit words and internally select
halfwords for compressed instruction handling:

- The fetch unit may request aligned 32-bit words and internally select the
  lower or upper halfword for compressed instruction handling.
- 16-bit instructions advance PC by 2.
- 32-bit instructions advance PC by 4.
- 32-bit instructions that straddle a 32-bit fetch word boundary require a
  second fetch word.

## Trap Model

The core must raise the trace trap flag for illegal or unsupported instructions,
environment calls, breakpoints, misaligned accesses, and interrupt trap entry.
Standard machine-mode trap entry is recoverable through `MRET`.

AXI non-OKAY response errors remain fatal terminal errors in this phase:

- `trap` remains asserted after a fatal AXI response error.
- No later instruction may commit after a fatal AXI response error.

For standard recoverable traps and interrupts, `trap` is an event indication in
the cycle that the trace trap item is emitted.

## Trace Model

Each committed or trapping instruction produces one architectural trace item:

- PC.
- next PC.
- raw instruction bits.
- instruction length in bytes.
- optional register writeback.
- optional memory access.
- trap flag and trap cause.

The trace is the primary equivalence boundary between the RTL and the reference
model.

## Current Scaffold Requirement

The current implementation establishes reset, fetch, and an EX/WB execution
slice for RV32E plus RV32EC compressed integer instructions:

- After reset, the core enters RUN state.
- While RUN is active, the shared AXI read channel requests fetch words.
- `axi_araddr` starts at `resetVector`.
- `axi_araddr` is aligned to a 32-bit fetch word.
- A selected compressed halfword increments PC by 2.
- A selected 32-bit instruction increments PC by 4.
- A 32-bit instruction starting in the upper halfword fetches the next aligned
  word and assembles the instruction from both fetch responses.
- `LUI`, `AUIPC`, `JAL`, `JALR`, RV32E branch, RV32E load, RV32E store, RV32E
  ALU-immediate, RV32E ALU-register, `FENCE`, `ECALL`, `EBREAK`, `MRET`,
  WFI, `Zicsr`, and RV32EC compressed integer instructions are decoded in RTL.
- `LUI`, `AUIPC`, RV32E load, RV32E ALU-immediate, and RV32E ALU-register
  instructions can write x1 through x15.
- RV32E and RV32EC compressed loads/stores use the shared AXI master.
- RV32E loads implement `LB`, `LH`, `LW`, `LBU`, and `LHU`; RV32EC compressed
  loads implement word loads.
- RV32E stores implement `SB`, `SH`, and `SW`; RV32EC compressed stores
  implement word stores.
- `JAL` and `JALR` write the sequential PC to x1 through x15 when `rd != x0`.
- Taken RV32E and RV32EC compressed branches redirect PC to `pc + branch_imm`;
  non-taken branches advance to the sequential PC.
- Branches do not write architectural registers.
- Aligned load/store instructions stall fetch while the shared AXI transaction is
  in progress and emit one trace item after the AXI response completes.
- Misaligned halfword or word load/store instructions trap without issuing AXI.
- Writes to x0 do not assert trace writeback and do not update state.
- `ECALL`, `EBREAK`, unknown instructions, illegal CSR accesses, and used x16
  through x31 register references trap with an explicit trace cause.
- WFI has a top-level sleep indication and does not issue AXI fetches while
  asleep.
- Software, timer, and external interrupt inputs can redirect execution through
  direct `mtvec` trap entry and return with `MRET`.
- Fetch, load, and store AXI non-OKAY responses trap with the explicit AXI error
  trace cause.
- RV32EC CoreMark profile and one-run Dhrystone benchmark binaries build with a
  freestanding runtime and pass on RTL through the shared AXI master.

## Open Requirements

- Full AXI4 burst or ID support, if a later integration requires it.
- Full RVFI compatibility with riscv-formal, if a later signoff requires the
  external RVFI protocol rather than the current RVFI-lite trace adapter.
