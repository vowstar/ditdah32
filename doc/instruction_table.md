# DitDah32 Instruction Table

## RV32E 32-Bit Instructions

The following RV32E instructions are in scope:

| Class | Instructions |
| --- | --- |
| Upper immediate | `LUI`, `AUIPC` |
| Jump | `JAL`, `JALR` |
| Branch | `BEQ`, `BNE`, `BLT`, `BGE`, `BLTU`, `BGEU` |
| Load | `LB`, `LH`, `LW`, `LBU`, `LHU` |
| Store | `SB`, `SH`, `SW` |
| ALU immediate | `ADDI`, `SLTI`, `SLTIU`, `XORI`, `ORI`, `ANDI`, `SLLI`, `SRLI`, `SRAI` |
| ALU register | `ADD`, `SUB`, `SLL`, `SLT`, `SLTU`, `XOR`, `SRL`, `SRA`, `OR`, `AND` |
| Ordering | `FENCE` |
| Trap | `ECALL`, `EBREAK` |
| CSR | `CSRRW`, `CSRRS`, `CSRRC`, `CSRRWI`, `CSRRSI`, `CSRRCI` |
| Privileged system | `MRET`, `WFI` |

`FENCE` is treated as a no-op ordering instruction for the initial single-core,
strongly ordered integration model. `FENCE.I` remains illegal. CSR instructions
are the standard `Zicsr` read-modify-write operations listed above.

## Control Profile

The control profile is intentionally smaller than a full privileged
implementation:

- Always M-mode.
- Direct `mtvec` mode only.
- Implemented CSRs: `mstatus`, `mie`, `mip`, `mtvec`, `mscratch`, `mepc`,
  `mcause`, `mtval`, `mvendorid`, `marchid`, `mimpid`, `mhartid`, and `misa`.
- Machine software, timer, and external interrupt inputs are supported.
- WFI is a privileged `SYSTEM` instruction, not a `Zicsr` CSR instruction.
- Vectored traps, delegation, U-mode, S-mode, debug, PMP, and MMU behavior are
  out of scope.

## RV32E Register Legality

RV32E has 16 architectural integer registers. For any instruction field that is
used by the instruction semantics:

- `0..15` is legal.
- `16..31` is illegal.

Unused instruction fields do not matter. For example, `LUI` uses `rd` but does
not use `rs1` or `rs2`.

## RV32EC Compressed Instructions

The following RV32EC compressed integer instruction groups are in scope:

| Group | Instructions |
| --- | --- |
| Constants and immediates | `C.NOP`, `C.ADDI`, `C.LI`, `C.LUI`, `C.ADDI16SP`, `C.ADDI4SPN` |
| Loads/stores | `C.LW`, `C.SW`, `C.LWSP`, `C.SWSP` |
| Control flow | `C.J`, `C.JAL`, `C.JR`, `C.JALR`, `C.BEQZ`, `C.BNEZ` |
| ALU | `C.SLLI`, `C.SRLI`, `C.SRAI`, `C.ANDI`, `C.SUB`, `C.XOR`, `C.OR`, `C.AND`, `C.MV`, `C.ADD` |

Compressed register fields using the compact register set map to `x8..x15` and
are naturally valid for RV32E. Other compressed forms that directly encode a
5-bit register are legal only when that register is `x0..x15`.

## RV32EC Compressed Legality Rules

- The all-zero 16-bit instruction is illegal.
- `C.ADDI4SPN` with zero immediate is illegal.
- `C.LWSP` with `rd = x0` is illegal.
- `C.JR` with `rs1 = x0` is illegal.
- `C.ADDI16SP` with zero immediate is illegal.
- `C.LUI` with zero immediate is illegal.
- RV64C-only encodings are illegal or unsupported for DitDah32.
- Floating-point compressed load/store encodings are unsupported because
  DitDah32 has no F or D extension.
- HINT encodings have no architectural effect except PC advance when their
  encoded registers are legal for RV32E.

## Reference Model Coverage

The Python reference model currently implements the RV32EC compressed integer
subset and `Zicsr` control-profile instructions listed above. It models WFI
sleep but not asynchronous interrupt injection.

RTL decode implements the RV32E 32-bit instructions listed above and the
RV32EC compressed integer subset listed above. The external memory boundary is
AXI-style; this table tracks ISA and control behavior, not AXI protocol
coverage.
