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

Spike runs the Spike-compatible matrix; Sail runs a flat-RAM matrix plus the
compliance signature gate. Memory artifacts that are not yet handled by the
Spike-compatible matrix are reported skipped, not silently passed.

`make verify-spike-rv32e-strict` adds RV32E x16-x31 negative checks.
`make verify-iss` writes the composite report to
`result/iss/external_iss_full/external_iss_full.json`.

## RISCV-DV

Fixed-seed RV32EC programs are filtered for legality, compiled, run on RTL,
and trace-compared against the Python reference. Non-RV32EC programs are
rejected before RTL execution.

## RVFI / riscv-formal

`make verify-rvfi` enables every property group in the implemented RV32EC,
Zicsr, and M-mode direct-trap profile; no report group is disabled.

## Full AXI4

The current target is a single-beat AXI4-Lite compatible subset.
Full AXI4 burst or ID support, if a later integration requires it.

## Continuous Integration

The hosted `verify-ci-smoke` profile must show a successful run with uploaded
artifacts for the current `git HEAD`. See `doc/ci_remote_closure.md` for the
exact closure procedure.

## Certified Benchmarks

CoreMark and Dhrystone images build and run on RTL, with local RTL
timing-marker cycle counts at a user-supplied frequency. They are not
certified scores; closure requires an external certification run.

## Compliance Signature Gate

`make verify-compliance` compiles every `test/compliance/tests/*.S` in two
variants (base 0 for cocotb, base 0x80000000 for Sail), runs Sail to produce
a reference signature, and asserts the cocotb DUT signature matches Sail
word for word.

## Optional JTAG Debug

The default build has no JTAG ports or debug logic. The optional single-hart
configuration passes direct run-control and abstract-access tests, OpenOCD/GDB,
bounded DTM/DM proofs, four-configuration isolation, and a generic synthesis
baseline audit. Authentication, triggers, Program Buffer, system bus access,
and multi-hart debug remain out of scope.
