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

// Temporal properties over the AXI channels and the trace shadow. Stated inside
// layer("DV") so they reach DitDah32_DV.sv as SVA and the production module
// stays assertion-free. The shadow registers stand in for $past, which the
// zaozi LTL surface does not bind.
object DitDah32Sva:

  def apply(
      parameter: DitDah32Parameter,
      io: Interface[DitDah32IO],
      traceValidReg: Reg[Bool],
      traceTrapReg: Reg[Bool],
      traceTrapCauseReg: Reg[UInt],
      traceRdWeReg: Reg[Bool]
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

    val ar = io.axi.ar
    val aw = io.axi.aw
    val w  = io.axi.w
    val r  = io.axi.r
    val b  = io.axi.b

    val arAddrPast = RegInit(0.U(parameter.xlen))
    val arProtPast = RegInit(0.U(3))
    val awAddrPast = RegInit(0.U(parameter.xlen))
    val awProtPast = RegInit(0.U(3))
    val wDataPast  = RegInit(0.U(parameter.xlen))
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

    val busFault = traceValidReg & traceTrapReg & (traceTrapCauseReg === 7.U(4)) & !traceRdWeReg
    val rError = r.valid & r.ready & (r.bits.resp =/= 0.U(2))
    val bError = b.valid & b.ready & (b.bits.resp =/= 0.U(2))
    Assert(rError.S |=> busFault.S, "axi_read_error_traps")
    Assert(bError.S |=> busFault.S, "axi_write_error_traps")

    // Anchored on the fatal-trap retire cycle. The same conjuncts on a sticky
    // latch are false, because the core resumes and fetches the handler.
    val fatalTrap = traceValidReg & traceTrapReg & (traceTrapCauseReg === 7.U(4))
    Assert(always(fatalTrap.S |-> (!traceRdWeReg).S), "fatal_trap_writes_no_rd")
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

    // Reachability of every antecedent above.
    Cover(rError.S, "cover_axi_read_error")
    Cover(bError.S, "cover_axi_write_error")
    Cover(fatalTrap.S, "cover_fatal_trap")
    Cover(asleep.S, "cover_sleep")
    Cover(arStalled.S, "cover_axi_ar_stalled")
    Cover(awStalled.S, "cover_axi_aw_stalled")
    Cover(wStalled.S, "cover_axi_w_stalled")
