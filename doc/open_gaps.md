# DitDah32 Open Verification Gaps

Gap status is also produced as `result/verification/open_gaps.{json,md}` by
`make audit-gaps`. A gap is closed only when the requirement, implementation,
test or property, command, and machine-readable evidence all agree.

## Status

| Gap | Status | Closure command |
|---|---|---|
| External ISS differential testing (Spike + Sail) | closed | `make verify-iss` |
| RISCV-DV constrained-random regression | closed | `make verify-riscv-dv` |
| Standard RVFI / riscv-formal | closed | `make verify-rvfi` |
| Full AXI4 burst / ID support | closed out-of-scope | n/a |
| Continuous integration regression | partial | `make audit-ci-remote` |
| Certified benchmark scoring | open | external certification |
| Compliance signature gate | closed (Sail differential) | `make verify-compliance` |
| Optional JTAG debug | closed | `make test-jtag && make formal-jtag` |

## External ISS Differential

Spike runs the Spike-compatible matrix, Sail a flat-RAM matrix plus the
compliance signature gate. Unhandled memory artifacts are reported skipped,
not silently passed. `make verify-spike-rv32e-strict` adds RV32E x16-x31
negative checks. `make verify-iss` writes
`result/iss/external_iss_full/external_iss_full.json`.

## RISCV-DV

Fixed-seed RV32EC programs are filtered for legality, compiled, run on RTL,
and trace-compared against the Python reference. Non-RV32EC programs are
rejected before RTL execution.

## RVFI / riscv-formal

`make verify-rvfi` enables every property group; none is disabled. Five
assumptions narrow what they see: the instruction models exclude trapping and
interrupted retirements and constrain register fields to x0-x15, CSR
persistence excludes traps and MRET, and liveness excludes WFI. They are
load-bearing: removing the WFI one fails `liveness_ch0`, and removing the CSR
one fails `csrc_any_{mstatus,mepc,mcause,mtval}`, because
`rvfi_csrc_any_check` cannot model the CSR writes a trap or MRET performs.

## Unbounded Proof

`make verify-commercial` proves 38 `layer("DV")` assertions without a depth
bound on JasperGold and VC Formal, with a reachability cover per antecedent.
They include the trap-entry, MRET, interrupt-priority and WFI-wake cases those
assumptions exclude, plus the single-outstanding AXI model `wrapper.sv` needs.

## Full AXI4

The target is a single-beat AXI4-Lite compatible subset. Burst and ID support
wait for an integration that requires them.

## Continuous Integration

The hosted `verify-ci-smoke` profile must show a successful run with uploaded
artifacts for the current `git HEAD`. See `doc/ci_remote_closure.md` for the
exact closure procedure.

## Certified Benchmarks

CoreMark and Dhrystone build and run on RTL with local timing-marker cycle
counts at a user-supplied frequency. They are not certified scores. Closure
requires an external certification run.

## Compliance Signature Gate

`make verify-compliance` compiles every `test/compliance/tests/*.S` in two
variants (base 0 for cocotb, base 0x80000000 for Sail), runs Sail for a
reference signature, and asserts the DUT signature matches it word for word.

## Optional JTAG Debug

The default build has no JTAG ports or debug logic. The optional single-hart
configuration passes run-control and abstract-access tests, OpenOCD/GDB,
bounded DTM/DM proofs, four-configuration isolation, and a synthesis baseline
audit. Authentication, triggers, Program Buffer, system bus access, and
multi-hart debug remain out of scope.
