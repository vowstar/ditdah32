# Third-Party Components

DitDah32 project source is licensed under the repository root `LICENSE`.
Vendored third-party code remains under the upstream terms listed here.

| Component | Path | Version or Snapshot | Terms Kept In Tree | Use |
| --- | --- | --- | --- | --- |
| cocotb-bus subset | `test/cocotb_bus/` | Local vendored subset | `test/cocotb_bus/LICENSE` | Minimal bus helper used by the vendored cocotb AXI test code. |
| cocotbext-axi subset | `test/cocotbext/axi/` | `0.1.25` from vendored `version.py` | `test/cocotbext/axi/LICENSE` and per-file notices | Deterministic AXI-Lite RAM and bus models used by cocotb RTL tests. |
| CoreMark upstream files | `bench/coremark/upstream/` | Local benchmark source snapshot | `bench/coremark/upstream/LICENSE.md` | Functional benchmark bring-up binary. Results are local, non-certified estimates. |
| Dhrystone C 2.1 upstream files | `bench/dhrystone/upstream/` | Version 2.1 distribution text | `bench/dhrystone/upstream/README_C` and `bench/dhrystone/upstream/RATIONALE` | Functional benchmark bring-up binary. Results are local, non-certified estimates. |

The benchmark code is retained to make the local bring-up binaries
reproducible. Published performance claims must keep the non-certified status
clear unless a separate certified benchmark process is completed.
