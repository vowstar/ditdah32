// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
package com.vowstar.ditdah32

import me.jiuyang.zaozi.*
import me.jiuyang.zaozi.default.{*, given}
import me.jiuyang.zaozi.ltltpe.*
import me.jiuyang.zaozi.reftpe.*
import me.jiuyang.zaozi.valuetpe.*
import org.llvm.mlir.scalalib.capi.ir.{Block, Context}

import java.lang.foreign.Arena

// The architectural trace surface, gathered so the property set can name it
// without a twenty-argument signature.
case class DitDah32TraceRefs(
    valid: Referable[Bool],
    trap: Referable[Bool],
    trapCause: Referable[UInt],
    rdWe: Referable[Bool],
    pc: Referable[UInt],
    nextPc: Referable[UInt],
    instr: Referable[UInt],
    rs1Addr: Referable[UInt],
    rs2Addr: Referable[UInt],
    preTrapMstatus: Referable[UInt],
    postCommitMstatus: Referable[UInt],
    irqPendingMask: Referable[UInt],
    mstatus: Referable[UInt],
    mie: Referable[UInt],
    mtvec: Referable[UInt],
    mepc: Referable[UInt],
    mtval: Referable[UInt],
    mip: Referable[UInt],
    mcause: Referable[UInt]
)

// Temporal properties over the AXI channels, the trap and interrupt CSR
// transitions, and the trace shadow. Stated inside layer("DV") so they reach
// DitDah32_DV.sv as SVA and the production module stays assertion-free. The
// shadow registers stand in for $past, which the zaozi LTL surface does not
// bind. Every assertion carries a reachability cover for its antecedent.
object DitDah32Sva:

  def apply(
      parameter: DitDah32Parameter,
      io: Interface[DitDah32IO],
      trace: DitDah32TraceRefs
  )(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext,
      ClockScope,
      ResetScope,
      TypeImpl
  ): Unit =
    given ClockEvent = posedge(io.clock)

    val xlen = parameter.xlen
    val zero = 0.B(xlen)
    val mipMask = BigInt("00000888", 16).B(xlen)
    val mipMaskInv = BigInt("fffff777", 16).B(xlen)
    val mstatusReserved = BigInt("ffffe777", 16).B(xlen)
    val mret = BigInt("30200073", 16).U(xlen)

    val ar = io.axi.ar
    val aw = io.axi.aw
    val w  = io.axi.w
    val r  = io.axi.r
    val b  = io.axi.b

    val arFire = ar.valid & ar.ready
    val awFire = aw.valid & aw.ready
    val rFire  = r.valid & r.ready
    val bFire  = b.valid & b.ready

    val arAddrPast = RegInit(0.U(xlen))
    val arProtPast = RegInit(0.U(3))
    val awAddrPast = RegInit(0.U(xlen))
    val awProtPast = RegInit(0.U(3))
    val wDataPast  = RegInit(0.U(xlen))
    val wStrbPast  = RegInit(0.U(4))
    arAddrPast := ar.bits.addr
    arProtPast := ar.bits.prot
    awAddrPast := aw.bits.addr
    awProtPast := aw.bits.prot
    wDataPast  := w.bits.data
    wStrbPast  := w.bits.strb

    val arStalled = ar.valid & !ar.ready
    val awStalled = aw.valid & !aw.ready
    val wStalled  = w.valid & !w.ready
    Assert(
      arStalled.S |=> (ar.valid & (ar.bits.addr === arAddrPast) & (ar.bits.prot === arProtPast)).S,
      "axi_ar_stable"
    )
    Assert(
      awStalled.S |=> (aw.valid & (aw.bits.addr === awAddrPast) & (aw.bits.prot === awProtPast)).S,
      "axi_aw_stable"
    )
    Assert(
      wStalled.S |=> (w.valid & (w.bits.data === wDataPast) & (w.bits.strb === wStrbPast)).S,
      "axi_w_stable"
    )

    // The single-outstanding memory model in the riscv-formal wrapper holds one
    // read and one write in flight. Nothing asserted that the core obeys it.
    // A zero-latency slave completes the request and the response in the same
    // cycle, which leaves the net count unchanged, so both shadows move only
    // when exactly one side fires.
    val readOutstanding = RegInit(false.B)
    when(arFire & !rFire) {
      readOutstanding := true.B
    }
    when(rFire & !arFire) {
      readOutstanding := false.B
    }
    Assert(always((readOutstanding & !rFire).S |-> (!ar.valid).S), "axi_single_outstanding_read")

    val writePending = RegInit(false.B)
    when(awFire & !bFire) {
      writePending := true.B
    }
    when(bFire & !awFire) {
      writePending := false.B
    }
    Assert(always((writePending & !bFire).S |-> (!aw.valid).S), "axi_single_outstanding_write")

    val busFault = trace.valid & trace.trap & (trace.trapCause === 7.U(4)) & !trace.rdWe
    val rError = r.valid & r.ready & (r.bits.resp =/= 0.U(2))
    val bError = b.valid & b.ready & (b.bits.resp =/= 0.U(2))
    Assert(rError.S |=> busFault.S, "axi_read_error_traps")
    Assert(bError.S |=> busFault.S, "axi_write_error_traps")

    // Anchored on the fatal-trap retire cycle. The same conjuncts on a sticky
    // latch are false, because the core resumes and fetches the handler.
    val fatalTrap = trace.valid & trace.trap & (trace.trapCause === 7.U(4))
    Assert(always(fatalTrap.S |-> (!trace.rdWe).S), "fatal_trap_writes_no_rd")
    Assert(always(fatalTrap.S |-> (!aw.valid & !w.valid).S), "fatal_trap_issues_no_store")
    Assert(always(fatalTrap.S |-> io.status.trap.S), "fatal_trap_reports_trap")
    Assert(always(fatalTrap.S |-> io.status.busy.S), "fatal_trap_stays_busy")
    Assert(always(fatalTrap.S |-> (!io.status.sleep).S), "fatal_trap_does_not_sleep")

    // Sleep excludes every bus request and every busy or trap state. It does
    // not exclude a retirement, because the WFI that enters sleep retires in
    // the same cycle.
    val asleep = io.status.sleep
    Assert(
      always(
        asleep.S |-> (!io.status.busy & !io.status.trap &
          !ar.valid & !aw.valid & !w.valid).S
      ),
      "sleep_quiescence"
    )

    // RV32E register discipline. regAccessIllegal traps any instruction that
    // uses x16-x31, so a retirement that does not trap never names one. This is
    // the core-side invariant behind the register-range assumption the
    // riscv-formal instruction suite makes about the encoding.
    val retire = trace.valid & !trace.trap
    Assert(
      always(retire.S |-> ((trace.rs1Addr < 16.U(5)) & (trace.rs2Addr < 16.U(5))).S),
      "rv32e_retire_regs_in_range"
    )

    // M-mode trap entry. Bounded to BMC depth in the riscv-formal wrapper; the
    // instruction and CSR-persistence suites assume it away entirely.
    val trapEntry = trace.valid & trace.trap
    Assert(always(trapEntry.S |-> (!trace.mstatus.asBits.bit(3)).S), "trap_entry_clears_mie")
    Assert(
      always(trapEntry.S |-> (trace.mstatus.asBits.bit(7) === trace.preTrapMstatus.asBits.bit(3)).S),
      "trap_entry_saves_mie"
    )
    Assert(
      always(trapEntry.S |-> (trace.mstatus.asBits.bits(12, 11) === 3.B(2)).S),
      "trap_entry_sets_mpp"
    )
    Assert(always(trapEntry.S |-> (trace.mepc === trace.pc).S), "trap_entry_saves_pc")
    Assert(always(trapEntry.S |-> (trace.nextPc === trace.mtvec).S), "trap_entry_vectors")

    val mretRetire = retire & (trace.instr === mret)
    Assert(
      always(
        mretRetire.S |-> (trace.postCommitMstatus.asBits.bit(3) === trace.preTrapMstatus.asBits.bit(7)).S
      ),
      "mret_restores_mie"
    )
    Assert(always(mretRetire.S |-> trace.postCommitMstatus.asBits.bit(7).S), "mret_sets_mpie")
    Assert(
      always(mretRetire.S |-> (trace.postCommitMstatus.asBits.bits(12, 11) === 3.B(2)).S),
      "mret_keeps_mpp"
    )
    Assert(always(mretRetire.S |-> (trace.nextPc === trace.mepc).S), "mret_returns_to_mepc")

    // mip is a pure mirror of the three interrupt inputs.
    Assert(always((trace.mip.asBits.bit(3) === io.irq.software).S), "mip_mirrors_software_irq")
    Assert(always((trace.mip.asBits.bit(7) === io.irq.timer).S), "mip_mirrors_timer_irq")
    Assert(always((trace.mip.asBits.bit(11) === io.irq.external).S), "mip_mirrors_external_irq")
    Assert(always(((trace.mip.asBits & mipMaskInv) === zero).S), "mip_reserved_zero")

    // Interrupt entry, the case the instruction suite assumes away with
    // !rvfi_intr.
    val intrEntry = trapEntry & trace.mcause.asBits.bit(xlen - 1)
    val maskExternal = trace.irqPendingMask.asBits.bit(11)
    val maskSoftware = trace.irqPendingMask.asBits.bit(3)
    val maskTimer = trace.irqPendingMask.asBits.bit(7)
    Assert(always(intrEntry.S |-> (trace.mtval === 0.U(xlen)).S), "interrupt_entry_zero_mtval")
    Assert(
      always(intrEntry.S |-> ((trace.irqPendingMask.asBits & mipMaskInv) === zero).S),
      "interrupt_mask_reserved_zero"
    )
    Assert(
      always(intrEntry.S |-> ((trace.irqPendingMask.asBits & mipMask) =/= zero).S),
      "interrupt_mask_nonzero"
    )
    Assert(
      always(intrEntry.S |-> ((trace.irqPendingMask.asBits & ~trace.mie.asBits) === zero).S),
      "interrupt_mask_enabled"
    )
    Assert(
      always((intrEntry & maskExternal).S |-> (trace.mcause === BigInt("8000000b", 16).U(xlen)).S),
      "interrupt_external_priority"
    )
    Assert(
      always(
        (intrEntry & !maskExternal & maskSoftware).S |->
          (trace.mcause === BigInt("80000003", 16).U(xlen)).S
      ),
      "interrupt_software_priority"
    )
    Assert(
      always(
        (intrEntry & !maskExternal & !maskSoftware).S |->
          (maskTimer & (trace.mcause === BigInt("80000007", 16).U(xlen))).S
      ),
      "interrupt_timer_priority"
    )

    // WARL legalization of the writable M-mode CSRs.
    Assert(
      always(trace.valid.S |-> ((trace.mstatus.asBits & mstatusReserved) === zero).S),
      "mstatus_reserved_zero"
    )
    Assert(
      always(
        trace.valid.S |-> ((trace.mstatus.asBits.bits(12, 11) === 0.B(2)) |
          (trace.mstatus.asBits.bits(12, 11) === 3.B(2))).S
      ),
      "mstatus_mpp_legal"
    )

    // WFI wake. The riscv-formal liveness suite assumes WFI away and the
    // wrapper replaces it with an eight-cycle bounded counter at BMC depth.
    // eventually() needs no bound at all.
    val sleepWithIrq = asleep & io.irq.pending
    val wfiCounter = RegInit(0.U(4))
    when(sleepWithIrq) {
      wfiCounter := (wfiCounter + 1.U(4)).asBits.bits(3, 0).asUInt
    }.otherwise {
      wfiCounter := 0.U(4)
    }
    Assert(always((wfiCounter < 8.U(4)).S), "wfi_wake_bounded")
    Assert(always(sleepWithIrq.S |-> eventually((!asleep).S)), "wfi_eventually_wakes")

    // Reachability of every antecedent above.
    Cover(rError.S, "cover_axi_read_error")
    Cover(bError.S, "cover_axi_write_error")
    Cover(fatalTrap.S, "cover_fatal_trap")
    Cover(asleep.S, "cover_sleep")
    Cover(arStalled.S, "cover_axi_ar_stalled")
    Cover(awStalled.S, "cover_axi_aw_stalled")
    Cover(wStalled.S, "cover_axi_w_stalled")
    Cover(readOutstanding.S, "cover_axi_read_outstanding")
    Cover(writePending.S, "cover_axi_write_pending")
    Cover((arFire & rFire).S, "cover_axi_ar_r_same_cycle")
    Cover((awFire & bFire).S, "cover_axi_aw_b_same_cycle")
    Cover((retire & (trace.rs1Addr =/= 0.U(5))).S, "cover_retire_uses_rs1")
    Cover(trapEntry.S, "cover_trap_entry")
    Cover(mretRetire.S, "cover_mret_retire")
    Cover(intrEntry.S, "cover_interrupt_entry")
    Cover((intrEntry & maskExternal).S, "cover_interrupt_external")
    Cover((intrEntry & !maskExternal & maskSoftware).S, "cover_interrupt_software")
    Cover((intrEntry & !maskExternal & !maskSoftware).S, "cover_interrupt_timer")
    Cover(sleepWithIrq.S, "cover_sleep_with_irq")
