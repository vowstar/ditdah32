# RV32EC ISA Scope

## Base Rules

DitDah32 implements a small RV32EC base plus the project control profile:

- XLEN is 32.
- Integer register addresses are 4 bits wide.
- x0 through x15 exist.
- x16 through x31 do not exist architecturally.
- The control profile adds `Zicsr` plus a minimal machine-mode privileged
  subset for direct trap entry, `MRET`, WFI, and machine software, timer, and
  external interrupts.

Any instruction encoding that names x16 through x31 is illegal for this core.

## RV32E Instruction Classes

The planned RV32E classes are:

- `LUI`
- `AUIPC`
- `JAL`
- `JALR`
- conditional branches
- loads
- stores
- immediate ALU operations
- register ALU operations
- `FENCE` as a no-op ordering instruction for the initial simple memory system
- `ECALL` and `EBREAK` as traps

`FENCE.I` remains out of scope and traps as an illegal instruction.

## Zicsr and Privileged Control Scope

`Zicsr` covers only the CSR read-modify-write instructions:

- `CSRRW`, `CSRRS`, and `CSRRC`.
- `CSRRWI`, `CSRRSI`, and `CSRRCI`.

WFI is not a `Zicsr` instruction. It is a non-CSR privileged `SYSTEM`
instruction with encoding `0x10500073`.

The supported non-CSR privileged `SYSTEM` instructions are:

- `ECALL`
- `EBREAK`
- `MRET`
- `WFI`

The supported machine CSRs are:

- `mstatus`
- `mie`
- `mip`
- `mtvec`
- `mscratch`
- `mepc`
- `mcause`
- `mtval`
- `mvendorid`
- `marchid`
- `mimpid`
- `mhartid`
- `misa`

The core supports only M-mode. `mtvec` direct mode is implemented. Vectored
mode, delegation, U-mode, S-mode, debug mode, PMP, and CLIC are out of scope.
Machine software, timer, and external interrupt pins are level-sensitive. The
local priority order is external, then software, then timer.

## Compressed Instruction Scope

The RVC decoder must only emit legal RV32E architectural register references.
Compressed forms that imply or encode x16 through x31 are illegal.

The required RV32EC compressed integer subset is:

- `C.NOP`, `C.ADDI`, `C.LI`, `C.LUI`, `C.ADDI16SP`, and `C.ADDI4SPN`.
- `C.LW`, `C.SW`, `C.LWSP`, and `C.SWSP`.
- `C.J`, `C.JAL`, `C.JR`, `C.JALR`, `C.BEQZ`, and `C.BNEZ`.
- `C.SLLI`, `C.SRLI`, `C.SRAI`, `C.ANDI`, `C.SUB`, `C.XOR`, `C.OR`,
  `C.AND`, `C.MV`, and `C.ADD`.

Floating-point compressed encodings, RV64C-only encodings, and all compressed
forms that require architectural state outside RV32EC must trap.

## Illegal Instruction Policy

Illegal instructions must trap. They must not execute as NOP and must not commit
register or memory side effects.
