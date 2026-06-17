// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
package com.vowstar.ditdah32

import me.jiuyang.zaozi.*
import me.jiuyang.zaozi.default.{*, given}
import me.jiuyang.zaozi.reftpe.*
import me.jiuyang.zaozi.valuetpe.*
import org.llvm.mlir.scalalib.capi.ir.{Block, Context}

import java.lang.foreign.Arena

class DitDah32Layers(parameter: DitDah32Parameter) extends LayerInterface(parameter):
  def layers = Seq(Layer("DV"))

class Decoupled[T <: Data](gen: T) extends Bundle:
  val ready = Flipped(Bool())
  val valid = Aligned(Bool())
  val bits  = Aligned(gen)

class AxiAw(parameter: DitDah32Parameter) extends Bundle:
  val addr = Aligned(UInt(parameter.xlen))
  val prot = Aligned(UInt(3))

class AxiW(parameter: DitDah32Parameter) extends Bundle:
  val data = Aligned(UInt(parameter.xlen))
  val strb = Aligned(UInt(4))

class AxiB extends Bundle:
  val resp = Aligned(UInt(2))

class AxiAr(parameter: DitDah32Parameter) extends Bundle:
  val addr = Aligned(UInt(parameter.xlen))
  val prot = Aligned(UInt(3))

class AxiR(parameter: DitDah32Parameter) extends Bundle:
  val data = Aligned(UInt(parameter.xlen))
  val resp = Aligned(UInt(2))

class AxiLiteBundle(parameter: DitDah32Parameter) extends Bundle:
  val aw = Aligned(new Decoupled(new AxiAw(parameter)))
  val w  = Aligned(new Decoupled(new AxiW(parameter)))
  val b  = Flipped(new Decoupled(new AxiB))
  val ar = Aligned(new Decoupled(new AxiAr(parameter)))
  val r  = Flipped(new Decoupled(new AxiR(parameter)))

class InterruptBundle extends Bundle:
  val software = Flipped(Bool())
  val timer    = Flipped(Bool())
  val external = Flipped(Bool())
  val pending  = Aligned(Bool())

class StatusBundle extends Bundle:
  val trap  = Aligned(Bool())
  val busy  = Aligned(Bool())
  val sleep = Aligned(Bool())

class DitDah32IO(parameter: DitDah32Parameter) extends HWBundle(parameter):
  val clock = Flipped(Clock())
  val reset = Flipped(Reset())

  val axi    = Aligned(new AxiLiteBundle(parameter))
  val irq    = Aligned(new InterruptBundle)
  val status = Aligned(new StatusBundle)

// Verification trace surface. Lowered into the layer("DV") bind collateral so
// the production main module carries no trace ports or registers; the formal
// wrapper and cocotb harness resolve these via the generated probe XMRs.
class DitDah32Probe(parameter: DitDah32Parameter)
    extends DVBundle[DitDah32Parameter, DitDah32Layers](parameter):
  private def dv = layers("DV")
  val trace_valid           = ProbeRead(Bool(), dv)
  val trace_pc              = ProbeRead(UInt(parameter.xlen), dv)
  val trace_next_pc         = ProbeRead(UInt(parameter.xlen), dv)
  val trace_instr           = ProbeRead(UInt(parameter.xlen), dv)
  val trace_len             = ProbeRead(UInt(3), dv)
  val trace_rd_we           = ProbeRead(Bool(), dv)
  val trace_rd              = ProbeRead(UInt(parameter.registerIndexBits), dv)
  val trace_rd_wdata        = ProbeRead(UInt(parameter.xlen), dv)
  val trace_rs1_addr        = ProbeRead(UInt(5), dv)
  val trace_rs1_rdata       = ProbeRead(UInt(parameter.xlen), dv)
  val trace_rs2_addr        = ProbeRead(UInt(5), dv)
  val trace_rs2_rdata       = ProbeRead(UInt(parameter.xlen), dv)
  val trace_mem_addr        = ProbeRead(UInt(parameter.xlen), dv)
  val trace_mem_rmask       = ProbeRead(UInt(4), dv)
  val trace_mem_wmask       = ProbeRead(UInt(4), dv)
  val trace_mem_rdata       = ProbeRead(UInt(parameter.xlen), dv)
  val trace_mem_wdata       = ProbeRead(UInt(parameter.xlen), dv)
  val trace_mem_fault       = ProbeRead(Bool(), dv)
  val trace_mem_fault_rmask = ProbeRead(UInt(4), dv)
  val trace_mem_fault_wmask = ProbeRead(UInt(4), dv)
  val trace_csr_addr        = ProbeRead(UInt(12), dv)
  val trace_csr_rmask       = ProbeRead(UInt(parameter.xlen), dv)
  val trace_csr_wmask       = ProbeRead(UInt(parameter.xlen), dv)
  val trace_csr_rdata       = ProbeRead(UInt(parameter.xlen), dv)
  val trace_csr_wdata       = ProbeRead(UInt(parameter.xlen), dv)
  val trace_trap            = ProbeRead(Bool(), dv)
  val trace_trap_cause      = ProbeRead(UInt(4), dv)
  val trace_mstatus         = ProbeRead(UInt(parameter.xlen), dv)
  val trace_mstatus_pre_trap = ProbeRead(UInt(parameter.xlen), dv)
  val trace_mip             = ProbeRead(UInt(parameter.xlen), dv)
  val trace_mcause          = ProbeRead(UInt(parameter.xlen), dv)

object CoreState:
  val RESET:    Int = 0
  val RUN:      Int = 1
  val TRAP:     Int = 2
  val STRADDLE: Int = 3
  val LOAD:     Int = 4
  val STORE:    Int = 5
  val SLEEP:    Int = 6
  val IRQ:      Int = 7

object TrapCause:
  val NONE:          Int = 0
  val ILLEGAL:       Int = 1
  val EBREAK:        Int = 2
  val RV32E_REGISTER:Int = 3
  val ECALL:         Int = 4
  val LOAD_MISALIGN: Int = 5
  val STORE_MISALIGN:Int = 6
  val AXI_ERROR:     Int = 7
  val INTERRUPT:     Int = 8

object CsrAddr:
  val MSTATUS:   Int = 0x300
  val MISA:      Int = 0x301
  val MIE:       Int = 0x304
  val MTVEC:     Int = 0x305
  val MSCRATCH:  Int = 0x340
  val MEPC:      Int = 0x341
  val MCAUSE:    Int = 0x342
  val MTVAL:     Int = 0x343
  val MIP:       Int = 0x344
  val MVENDORID: Int = 0xf11
  val MARCHID:   Int = 0xf12
  val MIMPID:    Int = 0xf13
  val MHARTID:   Int = 0xf14

object CsrBits:
  val MSTATUS_MIE:  Int = 3
  val MSTATUS_MPIE: Int = 7
  val MSTATUS_MPP_LOW: Int = 11
  val MSTATUS_MPP_HIGH: Int = 12
  val IRQ_SOFTWARE: Int = 3
  val IRQ_TIMER:    Int = 7
  val IRQ_EXTERNAL: Int = 11

object StandardCause:
  val INSTRUCTION_MISALIGNED: Int = 0
  val ILLEGAL_INSTRUCTION:    Int = 2
  val BREAKPOINT:             Int = 3
  val LOAD_MISALIGNED:        Int = 4
  val STORE_MISALIGNED:       Int = 6
  val ECALL_M:                Int = 11

@generator
object DitDah32Module
    extends Generator[DitDah32Parameter, DitDah32Layers, DitDah32IO, DitDah32Probe]:

  override def moduleName(parameter: DitDah32Parameter): String = "DitDah32"

  private def trapMstatus[R <: Referable[Bits]](current: R)(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): Node[Bits] =
    0.B(19) ##
    3.B(2) ##
    0.B(3) ##
    current.bits(CsrBits.MSTATUS_MIE, CsrBits.MSTATUS_MIE) ##
    0.B(3) ##
    0.B(1) ##
    0.B(3)

  private def mretMstatus[R <: Referable[Bits]](current: R)(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): Node[Bits] =
    0.B(19) ##
    3.B(2) ##
    0.B(3) ##
    1.B(1) ##
    0.B(3) ##
    current.bits(CsrBits.MSTATUS_MPIE, CsrBits.MSTATUS_MPIE) ##
    0.B(3)

  private def writableMstatus[R <: Referable[Bits]](writeData: R)(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): Node[Bits] =
    // WARL legalization for DitDah32 (M-only): MPP is hard-wired to 2'b11
    // because U and S modes are not supported. Any value the software writes
    // to mstatus.MPP reads back as 11, matching the Priv Spec recommendation
    // for cores that implement a single privilege level. All non-MIE/MPIE
    // bits stay reserved-zero.
    0.B(19) ##
    3.B(2) ##
    0.B(3) ##
    writeData.bits(CsrBits.MSTATUS_MPIE, CsrBits.MSTATUS_MPIE) ##
    0.B(3) ##
    writeData.bits(CsrBits.MSTATUS_MIE, CsrBits.MSTATUS_MIE) ##
    0.B(3)

  private def csrReadSignals(
      addr: Referable[Bits],
      mstatus: Referable[Bits],
      mie: Referable[Bits],
      mtvec: Referable[Bits],
      mscratch: Referable[Bits],
      mepc: Referable[Bits],
      mcause: Referable[Bits],
      mtval: Referable[Bits],
      mip: Referable[Bits],
      parameter: DitDah32Parameter
  )(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): (Wire[Bits], Wire[Bool], Wire[Bool]) =
    val data = Wire(Bits(parameter.xlen))
    val valid = Wire(Bool())
    val readOnly = Wire(Bool())

    data := 0.B(parameter.xlen)
    valid := false.B
    readOnly := false.B
    when(addr === CsrAddr.MSTATUS.B(12)) { valid := true.B; data := mstatus }
    when(addr === CsrAddr.MISA.B(12)) { valid := true.B; readOnly := true.B; data := 0x40000014.B(parameter.xlen) }
    when(addr === CsrAddr.MIE.B(12)) { valid := true.B; data := mie }
    when(addr === CsrAddr.MTVEC.B(12)) { valid := true.B; data := mtvec }
    when(addr === CsrAddr.MSCRATCH.B(12)) { valid := true.B; data := mscratch }
    when(addr === CsrAddr.MEPC.B(12)) { valid := true.B; data := mepc }
    when(addr === CsrAddr.MCAUSE.B(12)) { valid := true.B; data := mcause }
    when(addr === CsrAddr.MTVAL.B(12)) { valid := true.B; data := mtval }
    when(addr === CsrAddr.MIP.B(12)) { valid := true.B; readOnly := true.B; data := mip }
    when(addr === CsrAddr.MVENDORID.B(12)) { valid := true.B; readOnly := true.B; data := 0.B(parameter.xlen) }
    when(addr === CsrAddr.MARCHID.B(12)) { valid := true.B; readOnly := true.B; data := 0.B(parameter.xlen) }
    when(addr === CsrAddr.MIMPID.B(12)) { valid := true.B; readOnly := true.B; data := 0.B(parameter.xlen) }
    when(addr === CsrAddr.MHARTID.B(12)) { valid := true.B; readOnly := true.B; data := 0.B(parameter.xlen) }

    (data, valid, readOnly)

  private def readGpr(
      index: Referable[Bits],
      x1: Referable[UInt],
      x2: Referable[UInt],
      x3: Referable[UInt],
      x4: Referable[UInt],
      x5: Referable[UInt],
      x6: Referable[UInt],
      x7: Referable[UInt],
      x8: Referable[UInt],
      x9: Referable[UInt],
      x10: Referable[UInt],
      x11: Referable[UInt],
      x12: Referable[UInt],
      x13: Referable[UInt],
      x14: Referable[UInt],
      x15: Referable[UInt],
      parameter: DitDah32Parameter
  )(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): Wire[UInt] =
    val data = Wire(UInt(parameter.xlen))
    data := 0.U(parameter.xlen)
    when(index === 1.B(5)) { data := x1 }
    when(index === 2.B(5)) { data := x2 }
    when(index === 3.B(5)) { data := x3 }
    when(index === 4.B(5)) { data := x4 }
    when(index === 5.B(5)) { data := x5 }
    when(index === 6.B(5)) { data := x6 }
    when(index === 7.B(5)) { data := x7 }
    when(index === 8.B(5)) { data := x8 }
    when(index === 9.B(5)) { data := x9 }
    when(index === 10.B(5)) { data := x10 }
    when(index === 11.B(5)) { data := x11 }
    when(index === 12.B(5)) { data := x12 }
    when(index === 13.B(5)) { data := x13 }
    when(index === 14.B(5)) { data := x14 }
    when(index === 15.B(5)) { data := x15 }
    data

  private def writeGpr(
      enable: Referable[Bool],
      index: Referable[Bits],
      data: Referable[UInt],
      x1: Reg[UInt],
      x2: Reg[UInt],
      x3: Reg[UInt],
      x4: Reg[UInt],
      x5: Reg[UInt],
      x6: Reg[UInt],
      x7: Reg[UInt],
      x8: Reg[UInt],
      x9: Reg[UInt],
      x10: Reg[UInt],
      x11: Reg[UInt],
      x12: Reg[UInt],
      x13: Reg[UInt],
      x14: Reg[UInt],
      x15: Reg[UInt]
  )(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): Unit =
    when(enable & (index === 1.B(5))) { x1 := data }
    when(enable & (index === 2.B(5))) { x2 := data }
    when(enable & (index === 3.B(5))) { x3 := data }
    when(enable & (index === 4.B(5))) { x4 := data }
    when(enable & (index === 5.B(5))) { x5 := data }
    when(enable & (index === 6.B(5))) { x6 := data }
    when(enable & (index === 7.B(5))) { x7 := data }
    when(enable & (index === 8.B(5))) { x8 := data }
    when(enable & (index === 9.B(5))) { x9 := data }
    when(enable & (index === 10.B(5))) { x10 := data }
    when(enable & (index === 11.B(5))) { x11 := data }
    when(enable & (index === 12.B(5))) { x12 := data }
    when(enable & (index === 13.B(5))) { x13 := data }
    when(enable & (index === 14.B(5))) { x14 := data }
    when(enable & (index === 15.B(5))) { x15 := data }

  def architecture(parameter: DitDah32Parameter) =
    val io = summon[Interface[DitDah32IO]]
    val probe = summon[Interface[DitDah32Probe]]

    // Channel locals keep the architecture method under the JVM 64 KB cap.
    val axiAw = io.axi.aw
    val axiW  = io.axi.w
    val axiB  = io.axi.b
    val axiAr = io.axi.ar
    val axiR  = io.axi.r

    given Ref[Clock] = io.clock
    given Ref[Reset] = io.reset

    val pc       = RegInit(parameter.resetVector.U(parameter.xlen))
    val instrReg = RegInit(0.B(parameter.xlen))
    val fetched  = RegInit(false.B)
    val fetchOutstanding = RegInit(false.B)
    val memOutstanding = RegInit(false.B)
    val storeAwDone = RegInit(false.B)
    val storeWDone  = RegInit(false.B)
    val state    = RegInit(CoreState.RESET.U(3))
    val straddleLowHalfword = RegInit(0.B(16))
    val memPcReg         = RegInit(0.U(parameter.xlen))
    val memInstrReg      = RegInit(0.B(parameter.xlen))
    val memLenReg        = RegInit(0.U(3))
    val memNextPcReg     = RegInit(0.U(parameter.xlen))
    val memAddrReg       = RegInit(0.U(parameter.xlen))
    val memRdReg         = RegInit(0.B(5))
    val memFunct3Reg     = RegInit(0.U(3))
    val memStoreDataReg  = RegInit(0.B(parameter.xlen))
    val memStoreBeReg    = RegInit(0.U(4))
    val irqCauseReg      = RegInit(0.B(parameter.xlen))
    val csrMstatus       = RegInit(0.B(parameter.xlen))
    val csrMie           = RegInit(0.B(parameter.xlen))
    val csrMtvec         = RegInit(0.U(parameter.xlen))
    val csrMscratch      = RegInit(0.B(parameter.xlen))
    val csrMepc          = RegInit(0.U(parameter.xlen))
    val csrMcause        = RegInit(0.B(parameter.xlen))
    val csrMtval         = RegInit(0.U(parameter.xlen))
    val trapEventReg       = RegInit(false.B)
    val x1  = RegInit(0.U(parameter.xlen))
    val x2  = RegInit(0.U(parameter.xlen))
    val x3  = RegInit(0.U(parameter.xlen))
    val x4  = RegInit(0.U(parameter.xlen))
    val x5  = RegInit(0.U(parameter.xlen))
    val x6  = RegInit(0.U(parameter.xlen))
    val x7  = RegInit(0.U(parameter.xlen))
    val x8  = RegInit(0.U(parameter.xlen))
    val x9  = RegInit(0.U(parameter.xlen))
    val x10 = RegInit(0.U(parameter.xlen))
    val x11 = RegInit(0.U(parameter.xlen))
    val x12 = RegInit(0.U(parameter.xlen))
    val x13 = RegInit(0.U(parameter.xlen))
    val x14 = RegInit(0.U(parameter.xlen))
    val x15 = RegInit(0.U(parameter.xlen))

    val stateReset        = Wire(Bool())
    val stateRun          = Wire(Bool())
    val stateTrap         = Wire(Bool())
    val stateStraddle     = Wire(Bool())
    val stateLoad         = Wire(Bool())
    val stateStore        = Wire(Bool())
    val stateSleep        = Wire(Bool())
    val stateIrq          = Wire(Bool())
    val pcHalfwordHigh    = Wire(Bool())
    val pcFetchAddr       = Wire(UInt(parameter.xlen))
    val instrAddr         = Wire(UInt(parameter.xlen))
    val lowerHalfwordBits = Wire(Bits(2))
    val upperHalfwordBits = Wire(Bits(2))
    val instrLowBits      = Wire(Bits(2))
    val instrCompressed   = Wire(Bool())
    val straddled32       = Wire(Bool())
    val pcPlus2           = Wire(UInt(parameter.xlen))
    val pcPlus4           = Wire(UInt(parameter.xlen))
    val sequentialPc      = Wire(UInt(parameter.xlen))
    val execNextPc        = Wire(UInt(parameter.xlen))
    val selectedHalfword  = Wire(Bits(16))
    val selectedInstr     = Wire(Bits(parameter.xlen))
    val straddledInstr    = Wire(Bits(parameter.xlen))
    val decodedInstr      = Wire(Bits(parameter.xlen))
    val cDecodedInstr     = Wire(Bits(parameter.xlen))
    val cNoWriteHint      = Wire(Bool())
    val cInsn             = Wire(Bits(16))
    val cQuadrant         = Wire(Bits(2))
    val cFunct3           = Wire(Bits(3))
    val cRdRs1            = Wire(Bits(5))
    val cRs2              = Wire(Bits(5))
    val cRdPrime          = Wire(Bits(5))
    val cRs1Prime         = Wire(Bits(5))
    val cRs2Prime         = Wire(Bits(5))
    val cShamt            = Wire(Bits(5))
    val cImm6             = Wire(Bits(parameter.xlen))
    val cAddi4spnImm      = Wire(Bits(parameter.xlen))
    val cLwImm            = Wire(Bits(parameter.xlen))
    val cLwspImm          = Wire(Bits(parameter.xlen))
    val cSwspImm          = Wire(Bits(parameter.xlen))
    val cAddi16spImm      = Wire(Bits(parameter.xlen))
    val cBranchImm        = Wire(Bits(parameter.xlen))
    val cJumpImm          = Wire(Bits(parameter.xlen))
    val commitNow         = Wire(Bool())
    val commitInstr       = Wire(Bits(parameter.xlen))
    val commitLen         = Wire(UInt(3))
    val commitCompressed  = Wire(Bool())
    val fetchRequest      = Wire(Bool())
    val fetchArValid      = Wire(Bool())
    val fetchArFire       = Wire(Bool())
    val fetchAcceptsResponse = Wire(Bool())
    val fetchResponseFire = Wire(Bool())
    val fetchResponseOk   = Wire(Bool())
    val fetchResponseError = Wire(Bool())
    val instrReady        = Wire(Bool())
    val instrRdata        = Wire(Bits(parameter.xlen))
    val loadArValid       = Wire(Bool())
    val loadArFire        = Wire(Bool())
    val loadAcceptsResponse = Wire(Bool())
    val loadResponseFire  = Wire(Bool())
    val loadResponseOk    = Wire(Bool())
    val loadResponseError = Wire(Bool())
    val storeAwValid      = Wire(Bool())
    val storeWValid       = Wire(Bool())
    val storeAwFire       = Wire(Bool())
    val storeWFire        = Wire(Bool())
    val storeBothDone     = Wire(Bool())
    val storeResponseFire = Wire(Bool())
    val storeResponseOk   = Wire(Bool())
    val storeResponseError = Wire(Bool())
    val opcode            = Wire(Bits(7))
    val rdIndex           = Wire(Bits(5))
    val rs1Index          = Wire(Bits(5))
    val rs2Index          = Wire(Bits(5))
    val funct3            = Wire(Bits(3))
    val funct7            = Wire(Bits(7))
    val shamt             = Wire(UInt(5))
    val rs1Data           = Wire(UInt(parameter.xlen))
    val rs2Data           = Wire(UInt(parameter.xlen))
    val rs2Shamt          = Wire(UInt(5))
    val imm12             = Wire(UInt(parameter.xlen))
    val immS              = Wire(UInt(parameter.xlen))
    val immB              = Wire(UInt(parameter.xlen))
    val immJ              = Wire(UInt(parameter.xlen))
    val upperImm          = Wire(UInt(parameter.xlen))
    val jalrTarget        = Wire(UInt(parameter.xlen))
    val memAddr           = Wire(UInt(parameter.xlen))
    val memAlignedAddr    = Wire(UInt(parameter.xlen))
    val storeData         = Wire(Bits(parameter.xlen))
    val storeBe           = Wire(UInt(4))
    val loadByte          = Wire(Bits(8))
    val loadHalf          = Wire(Bits(16))
    val loadWdata         = Wire(Bits(parameter.xlen))
    val loadMemMask       = Wire(UInt(4))
    val rs1SignedOrder    = Wire(UInt(parameter.xlen))
    val rs2SignedOrder    = Wire(UInt(parameter.xlen))
    val imm12SignedOrder  = Wire(UInt(parameter.xlen))
    val sraImmWdata       = Wire(UInt(parameter.xlen))
    val sraRegWdata       = Wire(UInt(parameter.xlen))
    val isLui             = Wire(Bool())
    val isAuipc           = Wire(Bool())
    val isJal             = Wire(Bool())
    val isJalr            = Wire(Bool())
    val isBranch          = Wire(Bool())
    val isLoad            = Wire(Bool())
    val isStore           = Wire(Bool())
    val isOpImm           = Wire(Bool())
    val isAluImm          = Wire(Bool())
    val isOpReg           = Wire(Bool())
    val isAluReg          = Wire(Bool())
    val isFence           = Wire(Bool())
    val isEcall           = Wire(Bool())
    val isEbreak          = Wire(Bool())
    val isWfi             = Wire(Bool())
    val isMret            = Wire(Bool())
    val isCsr             = Wire(Bool())
    val isCsrImm          = Wire(Bool())
    val csrAddr           = Wire(Bits(12))
    val csrOperand        = Wire(Bits(parameter.xlen))
    val csrWriteData      = Wire(Bits(parameter.xlen))
    val csrTraceWriteData = Wire(Bits(parameter.xlen))
    val csrWriteEnable    = Wire(Bool())
    val csrUsesRs1        = Wire(Bool())
    val csrIllegal        = Wire(Bool())
    val postCommitMstatus = Wire(Bits(parameter.xlen))
    val postCommitMie     = Wire(Bits(parameter.xlen))
    val irqMip            = Wire(Bits(parameter.xlen))
    val irqEnabledMask    = Wire(Bits(parameter.xlen))
    val irqSoftwareEnabled = Wire(Bool())
    val irqTimerEnabled   = Wire(Bool())
    val irqExternalEnabled = Wire(Bool())
    val irqIndividuallyPending = Wire(Bool())
    val irqTrapPending    = Wire(Bool())
    val irqCause          = Wire(Bits(parameter.xlen))
    val postCommitIrqEnabledMask = Wire(Bits(parameter.xlen))
    val postCommitIrqSoftwareEnabled = Wire(Bool())
    val postCommitIrqTimerEnabled = Wire(Bool())
    val postCommitIrqExternalEnabled = Wire(Bool())
    val postCommitIrqTrapPending = Wire(Bool())
    val postCommitIrqCause = Wire(Bits(parameter.xlen))
    val trapVector        = Wire(UInt(parameter.xlen))
    val standardTrapCause = Wire(Bits(parameter.xlen))
    val standardTrapValue = Wire(UInt(parameter.xlen))
    val isCNop            = Wire(Bool())
    val rdIllegal         = Wire(Bool())
    val rs1Illegal        = Wire(Bool())
    val rs2Illegal        = Wire(Bool())
    val execUsesRd        = Wire(Bool())
    val execUsesRs1       = Wire(Bool())
    val execUsesRs2       = Wire(Bool())
    val execKnown         = Wire(Bool())
    val execTrap          = Wire(Bool())
    val execTrapCause     = Wire(UInt(4))
    val execWdata         = Wire(UInt(parameter.xlen))
    val execWriteRd       = Wire(Bool())
    val branchTaken       = Wire(Bool())
    val loadMisaligned    = Wire(Bool())
    val storeMisaligned   = Wire(Bool())
    val execWaitsForMem   = Wire(Bool())

    stateReset := state === CoreState.RESET.U(3)
    stateRun   := state === CoreState.RUN.U(3)
    stateTrap  := state === CoreState.TRAP.U(3)
    stateStraddle := state === CoreState.STRADDLE.U(3)
    stateLoad  := state === CoreState.LOAD.U(3)
    stateStore := state === CoreState.STORE.U(3)
    stateSleep := state === CoreState.SLEEP.U(3)
    stateIrq   := state === CoreState.IRQ.U(3)
    pcHalfwordHigh := pc.asBits.bit(1)
    pcFetchAddr := (pc.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt

    fetchRequest := stateRun | stateStraddle
    fetchArValid := fetchRequest & !fetchOutstanding
    fetchArFire := fetchArValid & axiAr.ready
    fetchAcceptsResponse := fetchOutstanding | fetchArFire
    fetchResponseFire := fetchAcceptsResponse & axiR.valid
    fetchResponseError := fetchResponseFire & (axiR.bits.resp =/= 0.U(2))
    fetchResponseOk := fetchResponseFire & !fetchResponseError
    instrReady := fetchResponseOk
    instrRdata := axiR.bits.data.asBits

    loadArValid := stateLoad & !memOutstanding
    loadArFire := loadArValid & axiAr.ready
    loadAcceptsResponse := stateLoad & (memOutstanding | loadArFire)
    loadResponseFire := loadAcceptsResponse & axiR.valid
    loadResponseError := loadResponseFire & (axiR.bits.resp =/= 0.U(2))
    loadResponseOk := loadResponseFire & !loadResponseError
    storeAwValid := stateStore & !storeAwDone
    storeWValid := stateStore & !storeWDone
    storeAwFire := storeAwValid & axiAw.ready
    storeWFire := storeWValid & axiW.ready
    storeBothDone := (storeAwDone | storeAwFire) & (storeWDone | storeWFire)
    val storeComplete = stateStore & storeBothDone
    storeResponseFire := storeComplete & axiB.valid
    storeResponseError := storeResponseFire & (axiB.bits.resp =/= 0.U(2))
    storeResponseOk := storeResponseFire & !storeResponseError

    lowerHalfwordBits := instrRdata.bits(1, 0)
    upperHalfwordBits := instrRdata.bits(17, 16)
    instrLowBits      := pcHalfwordHigh.?(upperHalfwordBits, lowerHalfwordBits)
    instrCompressed   := instrLowBits =/= 3.B(2)
    straddled32       := pcHalfwordHigh & !instrCompressed
    selectedHalfword  := pcHalfwordHigh.?(instrRdata.bits(31, 16), instrRdata.bits(15, 0))

    pcPlus2 := (pc + 2.U(parameter.xlen)).asBits.bits(parameter.xlen - 1, 0).asUInt
    pcPlus4 := (pc + 4.U(parameter.xlen)).asBits.bits(parameter.xlen - 1, 0).asUInt
    sequentialPc := commitCompressed.?(pcPlus2, pcPlus4)
    instrAddr := stateStraddle.?(pcPlus2, pcFetchAddr)
    selectedInstr := instrCompressed.?(0.B(16) ## selectedHalfword, instrRdata)
    straddledInstr := instrRdata.bits(15, 0) ## straddleLowHalfword

    commitNow := (stateStraddle & instrReady) | (stateRun & instrReady & !straddled32)
    commitInstr := stateStraddle.?(straddledInstr, selectedInstr)
    commitLen := stateStraddle.?(4.U(3), instrCompressed.?(2.U(3), 4.U(3)))
    commitCompressed := commitLen === 2.U(3)

    cInsn := commitInstr.bits(15, 0)
    cQuadrant := cInsn.bits(1, 0)
    cFunct3 := cInsn.bits(15, 13)
    cRdRs1 := cInsn.bits(11, 7)
    cRs2 := cInsn.bits(6, 2)
    cRdPrime := 1.B(2) ## cInsn.bits(4, 2)
    cRs1Prime := 1.B(2) ## cInsn.bits(9, 7)
    cRs2Prime := 1.B(2) ## cInsn.bits(4, 2)
    cShamt := cInsn.bits(6, 2)
    cImm6 :=
      cInsn.bit(12).?(0x3ffffff.B(26), 0.B(26)) ##
      cInsn.bits(12, 12) ##
      cInsn.bits(6, 2)
    cAddi4spnImm :=
      0.B(22) ##
      cInsn.bits(10, 7) ##
      cInsn.bits(12, 11) ##
      cInsn.bits(5, 5) ##
      cInsn.bits(6, 6) ##
      0.B(2)
    cLwImm :=
      0.B(25) ##
      cInsn.bits(5, 5) ##
      cInsn.bits(12, 10) ##
      cInsn.bits(6, 6) ##
      0.B(2)
    cLwspImm :=
      0.B(24) ##
      cInsn.bits(3, 2) ##
      cInsn.bits(12, 12) ##
      cInsn.bits(6, 4) ##
      0.B(2)
    cSwspImm :=
      0.B(24) ##
      cInsn.bits(8, 7) ##
      cInsn.bits(12, 9) ##
      0.B(2)
    cAddi16spImm :=
      cInsn.bit(12).?(0x3fffff.B(22), 0.B(22)) ##
      cInsn.bits(12, 12) ##
      cInsn.bits(4, 3) ##
      cInsn.bits(5, 5) ##
      cInsn.bits(2, 2) ##
      cInsn.bits(6, 6) ##
      0.B(4)
    cBranchImm :=
      cInsn.bit(12).?(0x7fffff.B(23), 0.B(23)) ##
      cInsn.bits(12, 12) ##
      cInsn.bits(6, 5) ##
      cInsn.bits(2, 2) ##
      cInsn.bits(11, 10) ##
      cInsn.bits(4, 3) ##
      0.B(1)
    cJumpImm :=
      cInsn.bit(12).?(0xfffff.B(20), 0.B(20)) ##
      cInsn.bits(12, 12) ##
      cInsn.bits(8, 8) ##
      cInsn.bits(10, 9) ##
      cInsn.bits(6, 6) ##
      cInsn.bits(7, 7) ##
      cInsn.bits(2, 2) ##
      cInsn.bits(11, 11) ##
      cInsn.bits(5, 3) ##
      0.B(1)

    cDecodedInstr := 0.B(parameter.xlen)
    cNoWriteHint := false.B
    when(cQuadrant === 0.B(2)) {
      when((cFunct3 === 0.B(3)) & (cAddi4spnImm =/= 0.B(parameter.xlen))) {
        cDecodedInstr := (
          cAddi4spnImm.bits(11, 0) ##
          2.B(5) ##
          0.B(3) ##
          cRdPrime ##
          0x13.B(7)
        )
      }
      when(cFunct3 === 2.B(3)) {
        cDecodedInstr := (
          cLwImm.bits(11, 0) ##
          cRs1Prime ##
          2.B(3) ##
          cRdPrime ##
          0x03.B(7)
        )
      }
      when(cFunct3 === 6.B(3)) {
        cDecodedInstr := (
          cLwImm.bits(11, 5) ##
          cRs2Prime ##
          cRs1Prime ##
          2.B(3) ##
          cLwImm.bits(4, 0) ##
          0x23.B(7)
        )
      }
    }
    when(cQuadrant === 1.B(2)) {
      when(cFunct3 === 0.B(3)) {
        cDecodedInstr := (
          cImm6.bits(11, 0) ##
          cRdRs1 ##
          0.B(3) ##
          cRdRs1 ##
          0x13.B(7)
        )
      }
      when(cFunct3 === 1.B(3)) {
        cDecodedInstr := (
          cJumpImm.bits(20, 20) ##
          cJumpImm.bits(10, 1) ##
          cJumpImm.bits(11, 11) ##
          cJumpImm.bits(19, 12) ##
          1.B(5) ##
          0x6f.B(7)
        )
      }
      when(cFunct3 === 2.B(3)) {
        cDecodedInstr := (
          cImm6.bits(11, 0) ##
          0.B(5) ##
          0.B(3) ##
          cRdRs1 ##
          0x13.B(7)
        )
      }
      when(cFunct3 === 3.B(3)) {
        when((cRdRs1 === 0.B(5)) & (cImm6 =/= 0.B(parameter.xlen))) {
          cDecodedInstr := (
            cImm6.bits(19, 0) ##
            cRdRs1 ##
            0x37.B(7)
          )
        }
        when((cRdRs1 === 2.B(5)) & (cAddi16spImm =/= 0.B(parameter.xlen))) {
          cDecodedInstr := (
            cAddi16spImm.bits(11, 0) ##
            2.B(5) ##
            0.B(3) ##
            2.B(5) ##
            0x13.B(7)
          )
        }
        when((cRdRs1 =/= 0.B(5)) & (cRdRs1 =/= 2.B(5)) & ((cImm6 =/= 0.B(parameter.xlen)) | cRdRs1.bit(4))) {
          cDecodedInstr := (
            cImm6.bits(19, 0) ##
            cRdRs1 ##
            0x37.B(7)
          )
        }
      }
      when(cFunct3 === 4.B(3)) {
        when(cInsn.bits(11, 10) === 0.B(2)) {
          when(!cInsn.bit(12)) {
            cDecodedInstr := (
              0.B(7) ##
              cShamt ##
              cRs1Prime ##
              5.B(3) ##
              cRs1Prime ##
              0x13.B(7)
            )
          }
        }
        when(cInsn.bits(11, 10) === 1.B(2)) {
          when(!cInsn.bit(12)) {
            cDecodedInstr := (
              0x20.B(7) ##
              cShamt ##
              cRs1Prime ##
              5.B(3) ##
              cRs1Prime ##
              0x13.B(7)
            )
          }
        }
        when(cInsn.bits(11, 10) === 2.B(2)) {
          cDecodedInstr := (
            cImm6.bits(11, 0) ##
            cRs1Prime ##
            7.B(3) ##
            cRs1Prime ##
            0x13.B(7)
          )
        }
        when(cInsn.bits(11, 10) === 3.B(2)) {
          when(!cInsn.bit(12)) {
            when(cInsn.bits(6, 5) === 0.B(2)) {
              cDecodedInstr := (
                0x20.B(7) ##
                cRs2Prime ##
                cRs1Prime ##
                0.B(3) ##
                cRs1Prime ##
                0x33.B(7)
              )
            }
            when(cInsn.bits(6, 5) === 1.B(2)) {
              cDecodedInstr := (
                0.B(7) ##
                cRs2Prime ##
                cRs1Prime ##
                4.B(3) ##
                cRs1Prime ##
                0x33.B(7)
              )
            }
            when(cInsn.bits(6, 5) === 2.B(2)) {
              cDecodedInstr := (
                0.B(7) ##
                cRs2Prime ##
                cRs1Prime ##
                6.B(3) ##
                cRs1Prime ##
                0x33.B(7)
              )
            }
            when(cInsn.bits(6, 5) === 3.B(2)) {
              cDecodedInstr := (
                0.B(7) ##
                cRs2Prime ##
                cRs1Prime ##
                7.B(3) ##
                cRs1Prime ##
                0x33.B(7)
              )
            }
          }
        }
      }
      when(cFunct3 === 5.B(3)) {
        cDecodedInstr := (
          cJumpImm.bits(20, 20) ##
          cJumpImm.bits(10, 1) ##
          cJumpImm.bits(11, 11) ##
          cJumpImm.bits(19, 12) ##
          0.B(5) ##
          0x6f.B(7)
        )
      }
      when((cFunct3 === 6.B(3)) | (cFunct3 === 7.B(3))) {
        cDecodedInstr := (
          cBranchImm.bits(12, 12) ##
          cBranchImm.bits(10, 5) ##
          0.B(5) ##
          cRs1Prime ##
          (cFunct3 === 6.B(3)).?(0.B(3), 1.B(3)) ##
          cBranchImm.bits(4, 1) ##
          cBranchImm.bits(11, 11) ##
          0x63.B(7)
        )
      }
    }
    when(cQuadrant === 2.B(2)) {
      when(cFunct3 === 0.B(3)) {
        when(!cInsn.bit(12)) {
          cDecodedInstr := (
            0.B(7) ##
            cShamt ##
            cRdRs1 ##
            1.B(3) ##
            cRdRs1 ##
            0x13.B(7)
          )
        }
      }
      when((cFunct3 === 2.B(3)) & (cRdRs1 =/= 0.B(5))) {
        cDecodedInstr := (
          cLwspImm.bits(11, 0) ##
          2.B(5) ##
          2.B(3) ##
          cRdRs1 ##
          0x03.B(7)
        )
      }
      when(cFunct3 === 4.B(3)) {
        when(!cInsn.bit(12) & (cRs2 === 0.B(5)) & (cRdRs1 =/= 0.B(5))) {
          cDecodedInstr := (
            0.B(12) ##
            cRdRs1 ##
            0.B(3) ##
            0.B(5) ##
            0x67.B(7)
          )
        }
        when(!cInsn.bit(12) & (cRs2 =/= 0.B(5))) {
          cDecodedInstr := (
            0.B(7) ##
            cRs2 ##
            0.B(5) ##
            0.B(3) ##
            cRdRs1 ##
            0x33.B(7)
          )
        }
        when(cInsn.bit(12) & (cRs2 === 0.B(5)) & (cRdRs1 === 0.B(5))) {
          cDecodedInstr := 0x00100073.B(parameter.xlen)
        }
        when(cInsn.bit(12) & (cRs2 === 0.B(5)) & (cRdRs1 =/= 0.B(5))) {
          cDecodedInstr := (
            0.B(12) ##
            cRdRs1 ##
            0.B(3) ##
            1.B(5) ##
            0x67.B(7)
          )
        }
        when(cInsn.bit(12) & (cRs2 =/= 0.B(5))) {
          cDecodedInstr := (
            0.B(7) ##
            cRs2 ##
            cRdRs1 ##
            0.B(3) ##
            cRdRs1 ##
            0x33.B(7)
          )
        }
      }
      when(cFunct3 === 6.B(3)) {
        cDecodedInstr := (
          cSwspImm.bits(11, 5) ##
          cRs2 ##
          2.B(5) ##
          2.B(3) ##
          cSwspImm.bits(4, 0) ##
          0x23.B(7)
        )
      }
    }
    decodedInstr := commitCompressed.?(cDecodedInstr, commitInstr)

    opcode   := decodedInstr.bits(6, 0)
    rdIndex  := decodedInstr.bits(11, 7)
    funct3   := decodedInstr.bits(14, 12)
    rs1Index := decodedInstr.bits(19, 15)
    rs2Index := decodedInstr.bits(24, 20)
    shamt    := decodedInstr.bits(24, 20).asUInt
    funct7   := decodedInstr.bits(31, 25)

    rs1Data := readGpr(rs1Index, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15, parameter)
    rs2Data := readGpr(rs2Index, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15, parameter)

    csrAddr := decodedInstr.bits(31, 20)
    isCsr := (opcode === 0x73.B(7)) & (funct3 =/= 0.B(3))
    isCsrImm := isCsr & funct3.bit(2)
    csrOperand := isCsrImm.?(0.B(27) ## rs1Index, rs1Data.asBits)
    // CSR write attempt per Priv Spec v1.12 §9.4: CSRRW/CSRRWI always write;
    // CSRRS/CSRRC/CSRRSI/CSRRCI do NOT write iff rs1/uimm field (insn[19:15])
    // is 0. Using rs1Index (architectural), not runtime data, keeps the
    // illegal-instruction trap on read-only CSRs spec-conformant.
    csrWriteEnable := isCsr & (
      (funct3 === 1.B(3)) |
      (funct3 === 5.B(3)) |
      ((funct3 =/= 0.B(3)) & (funct3 =/= 4.B(3)) & (rs1Index =/= 0.B(5)))
    )
    csrUsesRs1 := isCsr & !isCsrImm & (
      (funct3 === 1.B(3)) |
      (((funct3 === 2.B(3)) | (funct3 === 3.B(3))) & (rs1Index =/= 0.B(5)))
    )

    irqMip := (
      io.irq.software.?(8.U(parameter.xlen), 0.U(parameter.xlen)) +
      io.irq.timer.?(0x80.U(parameter.xlen), 0.U(parameter.xlen)) +
      io.irq.external.?(0x800.U(parameter.xlen), 0.U(parameter.xlen))
    ).asBits.bits(parameter.xlen - 1, 0)
    irqEnabledMask := (csrMie & irqMip).bits(parameter.xlen - 1, 0)
    irqSoftwareEnabled := irqEnabledMask.bit(CsrBits.IRQ_SOFTWARE)
    irqTimerEnabled := irqEnabledMask.bit(CsrBits.IRQ_TIMER)
    irqExternalEnabled := irqEnabledMask.bit(CsrBits.IRQ_EXTERNAL)
    irqIndividuallyPending := irqEnabledMask =/= 0.B(parameter.xlen)
    irqTrapPending := irqIndividuallyPending & csrMstatus.bit(CsrBits.MSTATUS_MIE)
    irqCause := BigInt("80000007", 16).B(parameter.xlen)
    when(irqSoftwareEnabled) {
      irqCause := BigInt("80000003", 16).B(parameter.xlen)
    }
    when(irqExternalEnabled) {
      irqCause := BigInt("8000000b", 16).B(parameter.xlen)
    }
    trapVector := (csrMtvec.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt

    val (csrReadData, csrValid, csrReadOnly) =
      csrReadSignals(csrAddr, csrMstatus, csrMie, csrMtvec.asBits, csrMscratch, csrMepc.asBits, csrMcause, csrMtval.asBits, irqMip, parameter)

    csrWriteData := csrReadData
    when((funct3 === 1.B(3)) | (funct3 === 5.B(3))) {
      csrWriteData := csrOperand
    }
    when((funct3 === 2.B(3)) | (funct3 === 6.B(3))) {
      csrWriteData := (csrReadData | csrOperand).bits(parameter.xlen - 1, 0)
    }
    when((funct3 === 3.B(3)) | (funct3 === 7.B(3))) {
      csrWriteData := (csrReadData & (csrOperand ^ BigInt("ffffffff", 16).B(parameter.xlen))).bits(parameter.xlen - 1, 0)
    }
    // RVFI csr_<name>_wdata reports the user-intended next value before
    // any WARL legalization, matching the RVFI convention
    // used by rvfi_csrw_check. Hardware-level WARL legalization is applied
    // separately on postCommit* and the CSR register input below.
    csrTraceWriteData := csrWriteData

    postCommitMstatus := csrMstatus
    when(csrWriteEnable & (csrAddr === CsrAddr.MSTATUS.B(12)) & !execTrap) {
      postCommitMstatus := writableMstatus(csrWriteData)
    }
    when(isMret & !execTrap) {
      postCommitMstatus := mretMstatus(csrMstatus)
    }
    postCommitMie := csrMie
    when(csrWriteEnable & (csrAddr === CsrAddr.MIE.B(12)) & !execTrap) {
      postCommitMie := (csrWriteData & 0x888.B(parameter.xlen)).bits(parameter.xlen - 1, 0)
    }
    postCommitIrqEnabledMask := (postCommitMie & irqMip).bits(parameter.xlen - 1, 0)
    postCommitIrqSoftwareEnabled := postCommitIrqEnabledMask.bit(CsrBits.IRQ_SOFTWARE)
    postCommitIrqTimerEnabled := postCommitIrqEnabledMask.bit(CsrBits.IRQ_TIMER)
    postCommitIrqExternalEnabled := postCommitIrqEnabledMask.bit(CsrBits.IRQ_EXTERNAL)
    postCommitIrqTrapPending := (postCommitIrqEnabledMask =/= 0.B(parameter.xlen)) & postCommitMstatus.bit(CsrBits.MSTATUS_MIE)
    postCommitIrqCause := BigInt("80000007", 16).B(parameter.xlen)
    when(postCommitIrqSoftwareEnabled) {
      postCommitIrqCause := BigInt("80000003", 16).B(parameter.xlen)
    }
    when(postCommitIrqExternalEnabled) {
      postCommitIrqCause := BigInt("8000000b", 16).B(parameter.xlen)
    }
    csrIllegal := isCsr & (!csrValid | (funct3 === 4.B(3)) | (csrWriteEnable & csrReadOnly))

    imm12 := (decodedInstr.bit(31).?(0xfffff.B(20), 0.B(20)) ## decodedInstr.bits(31, 20)).asUInt
    immS := (
      decodedInstr.bit(31).?(0xfffff.B(20), 0.B(20)) ##
      decodedInstr.bits(31, 25) ##
      decodedInstr.bits(11, 7)
    ).asUInt
    immB := (
      decodedInstr.bit(31).?(0x7ffff.B(19), 0.B(19)) ##
      decodedInstr.bits(31, 31) ##
      decodedInstr.bits(7, 7) ##
      decodedInstr.bits(30, 25) ##
      decodedInstr.bits(11, 8) ##
      0.B(1)
    ).asUInt
    immJ := (
      decodedInstr.bit(31).?(0x7ff.B(11), 0.B(11)) ##
      decodedInstr.bits(31, 31) ##
      decodedInstr.bits(19, 12) ##
      decodedInstr.bits(20, 20) ##
      decodedInstr.bits(30, 21) ##
      0.B(1)
    ).asUInt
    upperImm := (decodedInstr.bits(31, 12) ## 0.B(12)).asUInt
    jalrTarget := ((rs1Data + imm12).asBits.bits(parameter.xlen - 1, 1) ## 0.B(1)).asUInt
    memAddr := (isStore).?((rs1Data + immS).asBits.bits(parameter.xlen - 1, 0).asUInt, (rs1Data + imm12).asBits.bits(parameter.xlen - 1, 0).asUInt)
    memAlignedAddr := (memAddr.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt
    storeData := rs2Data.asBits
    storeBe := 0.U(4)
    when(isStore) {
      when(funct3 === 0.B(3)) {
        when(memAddr.asBits.bits(1, 0) === 0.B(2)) {
          storeData := 0.B(24) ## rs2Data.asBits.bits(7, 0)
          storeBe := 1.U(4)
        }
        when(memAddr.asBits.bits(1, 0) === 1.B(2)) {
          storeData := 0.B(16) ## rs2Data.asBits.bits(7, 0) ## 0.B(8)
          storeBe := 2.U(4)
        }
        when(memAddr.asBits.bits(1, 0) === 2.B(2)) {
          storeData := 0.B(8) ## rs2Data.asBits.bits(7, 0) ## 0.B(16)
          storeBe := 4.U(4)
        }
        when(memAddr.asBits.bits(1, 0) === 3.B(2)) {
          storeData := rs2Data.asBits.bits(7, 0) ## 0.B(24)
          storeBe := 8.U(4)
        }
      }
      when(funct3 === 1.B(3)) {
        when(!memAddr.asBits.bit(1)) {
          storeData := 0.B(16) ## rs2Data.asBits.bits(15, 0)
          storeBe := 3.U(4)
        }
        when(memAddr.asBits.bit(1)) {
          storeData := rs2Data.asBits.bits(15, 0) ## 0.B(16)
          storeBe := 0xc.U(4)
        }
      }
      when(funct3 === 2.B(3)) {
        storeData := rs2Data.asBits
        storeBe := 0xf.U(4)
      }
    }
    loadByte := axiR.bits.data.asBits.bits(7, 0)
    when(memAddrReg.asBits.bits(1, 0) === 1.B(2)) {
      loadByte := axiR.bits.data.asBits.bits(15, 8)
    }
    when(memAddrReg.asBits.bits(1, 0) === 2.B(2)) {
      loadByte := axiR.bits.data.asBits.bits(23, 16)
    }
    when(memAddrReg.asBits.bits(1, 0) === 3.B(2)) {
      loadByte := axiR.bits.data.asBits.bits(31, 24)
    }
    loadHalf := memAddrReg.asBits.bit(1).?(axiR.bits.data.asBits.bits(31, 16), axiR.bits.data.asBits.bits(15, 0))
    loadWdata := axiR.bits.data.asBits
    when(memFunct3Reg === 0.U(3)) {
      loadWdata := loadByte.bit(7).?(0xffffff.B(24), 0.B(24)) ## loadByte
    }
    when(memFunct3Reg === 1.U(3)) {
      loadWdata := loadHalf.bit(15).?(0xffff.B(16), 0.B(16)) ## loadHalf
    }
    when(memFunct3Reg === 4.U(3)) {
      loadWdata := 0.B(24) ## loadByte
    }
    when(memFunct3Reg === 5.U(3)) {
      loadWdata := 0.B(16) ## loadHalf
    }
    loadMemMask := 0.U(4)
    when((memFunct3Reg === 0.U(3)) | (memFunct3Reg === 4.U(3))) {
      when(memAddrReg.asBits.bits(1, 0) === 0.B(2)) { loadMemMask := 1.U(4) }
      when(memAddrReg.asBits.bits(1, 0) === 1.B(2)) { loadMemMask := 2.U(4) }
      when(memAddrReg.asBits.bits(1, 0) === 2.B(2)) { loadMemMask := 4.U(4) }
      when(memAddrReg.asBits.bits(1, 0) === 3.B(2)) { loadMemMask := 8.U(4) }
    }
    when((memFunct3Reg === 1.U(3)) | (memFunct3Reg === 5.U(3))) {
      loadMemMask := memAddrReg.asBits.bit(1).?(0xc.U(4), 3.U(4))
    }
    when(memFunct3Reg === 2.U(3)) {
      loadMemMask := 0xf.U(4)
    }
    rs2Shamt := rs2Data.asBits.bits(4, 0).asUInt
    rs1SignedOrder := ((~(rs1Data.asBits.bits(parameter.xlen - 1, parameter.xlen - 1))) ## rs1Data.asBits.bits(parameter.xlen - 2, 0)).asUInt
    rs2SignedOrder := ((~(rs2Data.asBits.bits(parameter.xlen - 1, parameter.xlen - 1))) ## rs2Data.asBits.bits(parameter.xlen - 2, 0)).asUInt
    imm12SignedOrder := ((~(imm12.asBits.bits(parameter.xlen - 1, parameter.xlen - 1))) ## imm12.asBits.bits(parameter.xlen - 2, 0)).asUInt
    sraImmWdata := ((rs1Data.asBits.bits(parameter.xlen - 1, parameter.xlen - 1) ## rs1Data.asBits).asSInt >> shamt).asBits.bits(parameter.xlen - 1, 0).asUInt
    sraRegWdata := ((rs1Data.asBits.bits(parameter.xlen - 1, parameter.xlen - 1) ## rs1Data.asBits).asSInt >> rs2Shamt).asBits.bits(parameter.xlen - 1, 0).asUInt

    isLui    := opcode === 0x37.B(7)
    isAuipc  := opcode === 0x17.B(7)
    isJal    := opcode === 0x6f.B(7)
    isJalr   := (opcode === 0x67.B(7)) & (funct3 === 0.B(3))
    isBranch := (opcode === 0x63.B(7)) & (
      (funct3 === 0.B(3)) |
      (funct3 === 1.B(3)) |
      (funct3 === 4.B(3)) |
      (funct3 === 5.B(3)) |
      (funct3 === 6.B(3)) |
      (funct3 === 7.B(3))
    )
    isLoad := (opcode === 0x03.B(7)) & (
      (funct3 === 0.B(3)) |
      (funct3 === 1.B(3)) |
      (funct3 === 2.B(3)) |
      (funct3 === 4.B(3)) |
      (funct3 === 5.B(3))
    )
    isStore := (opcode === 0x23.B(7)) & (
      (funct3 === 0.B(3)) |
      (funct3 === 1.B(3)) |
      (funct3 === 2.B(3))
    )
    isOpImm  := opcode === 0x13.B(7)
    isAluImm := isOpImm & (
      (funct3 === 0.B(3)) |
      (funct3 === 2.B(3)) |
      (funct3 === 3.B(3)) |
      (funct3 === 4.B(3)) |
      (funct3 === 6.B(3)) |
      (funct3 === 7.B(3)) |
      ((funct3 === 1.B(3)) & (funct7 === 0.B(7))) |
      ((funct3 === 5.B(3)) & ((funct7 === 0.B(7)) | (funct7 === 0x20.B(7))))
    )
    isOpReg  := opcode === 0x33.B(7)
    isAluReg := isOpReg & (
      ((funct7 === 0.B(7)) & (
        (funct3 === 0.B(3)) |
        (funct3 === 1.B(3)) |
        (funct3 === 2.B(3)) |
        (funct3 === 3.B(3)) |
        (funct3 === 4.B(3)) |
        (funct3 === 5.B(3)) |
        (funct3 === 6.B(3)) |
        (funct3 === 7.B(3))
      )) |
      ((funct7 === 0x20.B(7)) & ((funct3 === 0.B(3)) | (funct3 === 5.B(3))))
    )
    isFence  := (opcode === 0x0f.B(7)) & (funct3 === 0.B(3))
    isEcall  := decodedInstr === 0x00000073.B(parameter.xlen)
    isEbreak := decodedInstr === 0x00100073.B(parameter.xlen)
    isWfi    := decodedInstr === 0x10500073.B(parameter.xlen)
    isMret   := decodedInstr === 0x30200073.B(parameter.xlen)
    isCNop   := commitCompressed & (commitInstr === 1.B(parameter.xlen))

    rdIllegal  := rdIndex.bit(4)
    rs1Illegal := rs1Index.bit(4)
    rs2Illegal := rs2Index.bit(4)
    loadMisaligned := isLoad & (
      (((funct3 === 1.B(3)) | (funct3 === 5.B(3))) & memAddr.asBits.bit(0)) |
      ((funct3 === 2.B(3)) & (memAddr.asBits.bits(1, 0) =/= 0.B(2)))
    )
    storeMisaligned := isStore & (
      ((funct3 === 1.B(3)) & memAddr.asBits.bit(0)) |
      ((funct3 === 2.B(3)) & (memAddr.asBits.bits(1, 0) =/= 0.B(2)))
    )
    execUsesRd  := isLui | isAuipc | isJal | isJalr | isLoad | isAluImm | isAluReg | isCsr
    execUsesRs1 := isJalr | isBranch | isLoad | isStore | isAluImm | isAluReg | csrUsesRs1
    execUsesRs2 := isBranch | isStore | isAluReg
    execKnown   := isLui | isAuipc | isJal | isJalr | isBranch | isLoad | isStore | isAluImm | isAluReg | isFence | isEcall | isEbreak | isWfi | isMret | isCsr | isCNop

    val regAccessIllegal = (execUsesRd & rdIllegal) | (execUsesRs1 & rs1Illegal) | (execUsesRs2 & rs2Illegal)
    execTrap := (!execKnown) | csrIllegal | regAccessIllegal | loadMisaligned | storeMisaligned | isEcall | isEbreak
    execTrapCause := TrapCause.NONE.U(4)
    when(!execKnown | csrIllegal) {
      execTrapCause := TrapCause.ILLEGAL.U(4)
    }
    when(regAccessIllegal) {
      execTrapCause := TrapCause.RV32E_REGISTER.U(4)
    }
    when(loadMisaligned) {
      execTrapCause := TrapCause.LOAD_MISALIGN.U(4)
    }
    when(storeMisaligned) {
      execTrapCause := TrapCause.STORE_MISALIGN.U(4)
    }
    when(isEcall) {
      execTrapCause := TrapCause.ECALL.U(4)
    }
    when(isEbreak) {
      execTrapCause := TrapCause.EBREAK.U(4)
    }

    standardTrapCause := StandardCause.ILLEGAL_INSTRUCTION.B(parameter.xlen)
    when(loadMisaligned) {
      standardTrapCause := StandardCause.LOAD_MISALIGNED.B(parameter.xlen)
    }
    when(storeMisaligned) {
      standardTrapCause := StandardCause.STORE_MISALIGNED.B(parameter.xlen)
    }
    when(isEcall) {
      standardTrapCause := StandardCause.ECALL_M.B(parameter.xlen)
    }
    when(isEbreak) {
      standardTrapCause := StandardCause.BREAKPOINT.B(parameter.xlen)
    }
    standardTrapValue := 0.U(parameter.xlen)
    when(!execKnown | csrIllegal) {
      standardTrapValue := commitInstr.asUInt
    }
    when(loadMisaligned | storeMisaligned) {
      standardTrapValue := memAddr
    }

    execWdata := 0.U(parameter.xlen)
    when(isLui) {
      execWdata := upperImm
    }
    when(isAuipc) {
      execWdata := (pc + upperImm).asBits.bits(parameter.xlen - 1, 0).asUInt
    }
    when(isJal | isJalr) {
      execWdata := sequentialPc
    }
    when(isAluImm) {
      when(funct3 === 0.B(3)) {
        execWdata := (rs1Data + imm12).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 2.B(3)) {
        execWdata := (rs1SignedOrder < imm12SignedOrder).?(1.U(parameter.xlen), 0.U(parameter.xlen))
      }
      when(funct3 === 3.B(3)) {
        execWdata := (rs1Data < imm12).?(1.U(parameter.xlen), 0.U(parameter.xlen))
      }
      when(funct3 === 4.B(3)) {
        execWdata := (rs1Data.asBits ^ imm12.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 6.B(3)) {
        execWdata := (rs1Data.asBits | imm12.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 7.B(3)) {
        execWdata := (rs1Data.asBits & imm12.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 1.B(3)) {
        execWdata := (rs1Data << shamt).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 5.B(3)) & (funct7 === 0.B(7))) {
        execWdata := (rs1Data >> shamt).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 5.B(3)) & (funct7 === 0x20.B(7))) {
        execWdata := sraImmWdata
      }
    }
    when(isAluReg) {
      when((funct3 === 0.B(3)) & (funct7 === 0.B(7))) {
        execWdata := (rs1Data + rs2Data).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 0.B(3)) & (funct7 === 0x20.B(7))) {
        execWdata := (rs1Data - rs2Data).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 1.B(3)) {
        execWdata := (rs1Data << rs2Shamt).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 2.B(3)) {
        execWdata := (rs1SignedOrder < rs2SignedOrder).?(1.U(parameter.xlen), 0.U(parameter.xlen))
      }
      when(funct3 === 3.B(3)) {
        execWdata := (rs1Data < rs2Data).?(1.U(parameter.xlen), 0.U(parameter.xlen))
      }
      when(funct3 === 4.B(3)) {
        execWdata := (rs1Data.asBits ^ rs2Data.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 5.B(3)) & (funct7 === 0.B(7))) {
        execWdata := (rs1Data >> rs2Shamt).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 5.B(3)) & (funct7 === 0x20.B(7))) {
        execWdata := sraRegWdata
      }
      when(funct3 === 6.B(3)) {
        execWdata := (rs1Data.asBits | rs2Data.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 7.B(3)) {
        execWdata := (rs1Data.asBits & rs2Data.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
    }
    when(isCsr) {
      execWdata := csrReadData.asUInt
    }
    execWriteRd := execUsesRd & !execTrap & (rdIndex =/= 0.B(5)) & !cNoWriteHint
    execWaitsForMem := (isLoad | isStore) & !execTrap

    // Commit-cycle outcomes: a committing instruction either enters the
    // memory phase (load/store) or retires immediately (everything else).
    val commitEntersMem = commitNow & execWaitsForMem
    val commitNonMem    = commitNow & !execWaitsForMem

    branchTaken := false.B
    when(isBranch) {
      when(funct3 === 0.B(3)) {
        branchTaken := rs1Data === rs2Data
      }
      when(funct3 === 1.B(3)) {
        branchTaken := rs1Data =/= rs2Data
      }
      when(funct3 === 4.B(3)) {
        branchTaken := rs1SignedOrder < rs2SignedOrder
      }
      when(funct3 === 5.B(3)) {
        branchTaken := !(rs1SignedOrder < rs2SignedOrder)
      }
      when(funct3 === 6.B(3)) {
        branchTaken := rs1Data < rs2Data
      }
      when(funct3 === 7.B(3)) {
        branchTaken := !(rs1Data < rs2Data)
      }
    }

    execNextPc := sequentialPc
    when(isBranch & branchTaken) {
      execNextPc := (pc + immB).asBits.bits(parameter.xlen - 1, 0).asUInt
    }
    when(isJal) {
      execNextPc := (pc + immJ).asBits.bits(parameter.xlen - 1, 0).asUInt
    }
    when(isJalr) {
      execNextPc := jalrTarget
    }
    when(isMret) {
      execNextPc := csrMepc
    }

    axiAw.valid := storeAwValid
    axiAw.bits.addr  := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt
    axiAw.bits.prot  := 2.U(3)
    axiW.valid  := storeWValid
    axiW.bits.data   := memStoreDataReg.asUInt
    axiW.bits.strb   := memStoreBeReg
    axiB.ready  := storeComplete
    axiAr.valid := loadArValid | fetchArValid
    axiAr.bits.addr  := stateLoad.?((memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt, instrAddr)
    axiAr.bits.prot  := stateLoad.?(2.U(3), 6.U(3))
    axiR.ready  := loadAcceptsResponse | fetchAcceptsResponse

    io.irq.pending := irqIndividuallyPending
    io.status.trap      := stateTrap | trapEventReg
    io.status.busy := stateRun | stateStraddle | stateLoad | stateStore | stateIrq
    io.status.sleep := stateSleep

    when(stateReset) {
      state := CoreState.RUN.U(3)
      fetchOutstanding := false.B
      memOutstanding := false.B
      storeAwDone := false.B
      storeWDone := false.B
    }.otherwise {
      trapEventReg := false.B

      when(fetchArFire) {
        fetchOutstanding := true.B
      }
      when(fetchResponseFire) {
        fetchOutstanding := false.B
      }
      when(loadArFire) {
        memOutstanding := true.B
      }
      when(loadResponseFire) {
        memOutstanding := false.B
      }
      when(storeAwFire) {
        storeAwDone := true.B
      }
      when(storeWFire) {
        storeWDone := true.B
      }

      when(stateIrq) {
        state := CoreState.RUN.U(3)
        pc := trapVector
        trapEventReg := true.B
      }

      when(stateSleep) {
        when(irqIndividuallyPending) {
          state := CoreState.RUN.U(3)
          when(irqTrapPending) {
            state := CoreState.IRQ.U(3)
            irqCauseReg := irqCause
            csrMepc := pc
            csrMcause := irqCause
            csrMtval := 0.U(parameter.xlen)
            csrMstatus := trapMstatus(csrMstatus)
          }
        }
      }

      when(fetchResponseError) {
        // Recoverable instruction access fault per doc/memory_fault_contract.md.
        state := CoreState.IRQ.U(3)
        csrMcause := 1.B(parameter.xlen)
        csrMtval := pc
        csrMepc := pc
        csrMstatus := trapMstatus(csrMstatus)
        trapEventReg := true.B
      }

      when(loadResponseError) {
        // Recoverable load access fault per doc/memory_fault_contract.md.
        state := CoreState.IRQ.U(3)
        csrMcause := 5.B(parameter.xlen)
        csrMtval := memAddrReg
        csrMepc := memPcReg
        csrMstatus := trapMstatus(csrMstatus)
        trapEventReg := true.B
      }

      when(storeResponseError) {
        // Recoverable store access fault per doc/memory_fault_contract.md.
        storeAwDone := false.B
        storeWDone := false.B
        state := CoreState.IRQ.U(3)
        csrMcause := 7.B(parameter.xlen)
        csrMtval := memAddrReg
        csrMepc := memPcReg
        csrMstatus := trapMstatus(csrMstatus)
        trapEventReg := true.B
      }

      when(loadResponseOk) {
        instrReg := memInstrReg
        fetched  := true.B
        pc       := memNextPcReg
        state    := CoreState.RUN.U(3)

        writeGpr(memRdReg =/= 0.B(5), memRdReg, loadWdata.asUInt, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15)

        when(irqTrapPending) {
          state := CoreState.IRQ.U(3)
          irqCauseReg := irqCause
          csrMepc := memNextPcReg
          csrMcause := irqCause
          csrMtval := 0.U(parameter.xlen)
          csrMstatus := trapMstatus(csrMstatus)
        }
      }

      when(storeResponseOk) {
        storeAwDone := false.B
        storeWDone := false.B
        instrReg := memInstrReg
        fetched  := true.B
        pc       := memNextPcReg
        state    := CoreState.RUN.U(3)

        when(irqTrapPending) {
          state := CoreState.IRQ.U(3)
          irqCauseReg := irqCause
          csrMepc := memNextPcReg
          csrMcause := irqCause
          csrMtval := 0.U(parameter.xlen)
          csrMstatus := trapMstatus(csrMstatus)
        }
      }

      when(stateStraddle) {
        when(instrReady) {
          instrReg := straddledInstr
          fetched  := true.B
          when(!execWaitsForMem) {
            pc       := execNextPc
            state    := CoreState.RUN.U(3)
          }
        }
      }.otherwise {
        when(stateRun & instrReady) {
          when(straddled32) {
            straddleLowHalfword := instrRdata.bits(31, 16)
            state := CoreState.STRADDLE.U(3)
          }.otherwise {
            instrReg := instrRdata
            fetched  := true.B
            when(!execWaitsForMem) {
              pc       := execNextPc
            }
          }
        }
      }

      when(commitEntersMem) {
        memPcReg        := pc
        memInstrReg     := commitInstr
        memLenReg       := commitLen
        memNextPcReg    := sequentialPc
        memAddrReg      := memAddr
        memRdReg        := rdIndex
        memFunct3Reg    := funct3.asUInt
        memStoreDataReg := storeData
        memStoreBeReg   := storeBe
        memOutstanding  := false.B
        storeAwDone     := false.B
        storeWDone      := false.B
        when(isLoad) {
          state := CoreState.LOAD.U(3)
        }
        when(isStore) {
          state := CoreState.STORE.U(3)
        }
      }

      when(commitNonMem) {
        trapEventReg := execTrap

        writeGpr(execWriteRd, rdIndex, execWdata, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15)

        when(csrWriteEnable & !execTrap) {
          when(csrAddr === CsrAddr.MSTATUS.B(12)) {
            csrMstatus := writableMstatus(csrWriteData)
          }
          when(csrAddr === CsrAddr.MIE.B(12)) {
            csrMie := (csrWriteData & 0x888.B(parameter.xlen)).bits(parameter.xlen - 1, 0)
          }
          when(csrAddr === CsrAddr.MTVEC.B(12)) {
            csrMtvec := (csrWriteData.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt
          }
          when(csrAddr === CsrAddr.MSCRATCH.B(12)) {
            csrMscratch := csrWriteData
          }
          when(csrAddr === CsrAddr.MEPC.B(12)) {
            csrMepc := (csrWriteData.bits(parameter.xlen - 1, 1) ## 0.B(1)).asUInt
          }
          when(csrAddr === CsrAddr.MCAUSE.B(12)) {
            csrMcause := csrWriteData
          }
          when(csrAddr === CsrAddr.MTVAL.B(12)) {
            csrMtval := csrWriteData.asUInt
          }
        }

        when(isMret & !execTrap) {
          pc := csrMepc
          csrMstatus := mretMstatus(csrMstatus)
        }

        when(execTrap) {
          pc := trapVector
          state := CoreState.RUN.U(3)
          csrMepc := pc
          csrMcause := standardTrapCause
          csrMtval := standardTrapValue
          csrMstatus := trapMstatus(csrMstatus)
        }.otherwise {
          when(isWfi) {
            state := CoreState.SLEEP.U(3)
          }
          when(postCommitIrqTrapPending) {
            state := CoreState.IRQ.U(3)
            irqCauseReg := postCommitIrqCause
            csrMepc := isMret.?(csrMepc, execNextPc)
            csrMcause := postCommitIrqCause
            csrMtval := 0.U(parameter.xlen)
            csrMstatus := trapMstatus(postCommitMstatus)
          }
        }
      }
    }

    // Architectural trace shadow. Mirrors the core retire/trap timing as a
    // pure observer; lowered into the layer("DV") bind collateral so the
    // production main module is trace-free. Probes are read by the formal
    // wrapper and cocotb harness via the generated XMR macros.
    layer("DV"):
      val traceValidReg      = RegInit(false.B)
      val tracePcReg         = RegInit(0.U(parameter.xlen))
      val traceNextPcReg     = RegInit(0.U(parameter.xlen))
      val traceInstrReg      = RegInit(0.U(parameter.xlen))
      val traceLenReg        = RegInit(0.U(3))
      val traceRdWeReg       = RegInit(false.B)
      val traceRdReg         = RegInit(0.U(parameter.registerIndexBits))
      val traceRdWdataReg    = RegInit(0.U(parameter.xlen))
      val traceRs1AddrReg    = RegInit(0.U(5))
      val traceRs1RdataReg   = RegInit(0.U(parameter.xlen))
      val traceRs2AddrReg    = RegInit(0.U(5))
      val traceRs2RdataReg   = RegInit(0.U(parameter.xlen))
      val traceMemAddrReg    = RegInit(0.U(parameter.xlen))
      val traceMemRmaskReg   = RegInit(0.U(4))
      val traceMemWmaskReg   = RegInit(0.U(4))
      val traceMemRdataReg   = RegInit(0.U(parameter.xlen))
      val traceMemWdataReg   = RegInit(0.U(parameter.xlen))
      val traceMemFaultReg      = RegInit(false.B)
      val traceMemFaultRmaskReg = RegInit(0.U(4))
      val traceMemFaultWmaskReg = RegInit(0.U(4))
      val traceCsrAddrReg    = RegInit(0.U(12))
      val traceCsrRmaskReg   = RegInit(0.U(parameter.xlen))
      val traceCsrWmaskReg   = RegInit(0.U(parameter.xlen))
      val traceCsrRdataReg   = RegInit(0.U(parameter.xlen))
      val traceCsrWdataReg   = RegInit(0.U(parameter.xlen))
      val traceTrapReg       = RegInit(false.B)
      val traceTrapCauseReg  = RegInit(0.U(4))
      val tracePreTrapMstatusReg = RegInit(0.U(parameter.xlen))
      val memTraceRs1AddrReg  = RegInit(0.U(5))
      val memTraceRs1RdataReg = RegInit(0.U(parameter.xlen))
      val memTraceRs2AddrReg  = RegInit(0.U(5))
      val memTraceRs2RdataReg = RegInit(0.U(parameter.xlen))

      // trace_mstatus_pre_trap exposes RegNext(csrMstatus). For 1-cycle-delay
      // exception trap paths (fetch/load/store fault and execTrap) this aligns
      // with the trace_trap retire cycle and lets the wrapper prove MPIE=MIE.
      // Interrupt entry paths use a 2-cycle delay and a CSR-write-aware input,
      // so the wrapper restricts the MPIE swap assertion to !rvfi_intr retires.
      tracePreTrapMstatusReg := csrMstatus.asUInt

      when(!stateReset) {
        traceValidReg := false.B
        traceRdWeReg := false.B
        traceRdReg := 0.U(parameter.registerIndexBits)
        traceRdWdataReg := 0.U(parameter.xlen)
        traceRs1AddrReg := 0.U(5)
        traceRs1RdataReg := 0.U(parameter.xlen)
        traceRs2AddrReg := 0.U(5)
        traceRs2RdataReg := 0.U(parameter.xlen)
        traceMemAddrReg := 0.U(parameter.xlen)
        traceMemRmaskReg := 0.U(4)
        traceMemWmaskReg := 0.U(4)
        traceMemRdataReg := 0.U(parameter.xlen)
        traceMemWdataReg := 0.U(parameter.xlen)
        traceMemFaultReg := false.B
        traceMemFaultRmaskReg := 0.U(4)
        traceMemFaultWmaskReg := 0.U(4)
        traceCsrAddrReg := 0.U(12)
        traceCsrRmaskReg := 0.U(parameter.xlen)
        traceCsrWmaskReg := 0.U(parameter.xlen)
        traceCsrRdataReg := 0.U(parameter.xlen)
        traceCsrWdataReg := 0.U(parameter.xlen)
        traceTrapReg := false.B
        traceTrapCauseReg := 0.U(4)

        when(stateIrq) {
          traceValidReg := true.B
          tracePcReg := csrMepc
          traceNextPcReg := trapVector
          traceInstrReg := 0.U(parameter.xlen)
          traceLenReg := 0.U(3)
          traceRdWeReg := false.B
          traceRdReg := 0.U(parameter.registerIndexBits)
          traceRdWdataReg := 0.U(parameter.xlen)
          traceRs1AddrReg := 0.U(5)
          traceRs1RdataReg := 0.U(parameter.xlen)
          traceRs2AddrReg := 0.U(5)
          traceRs2RdataReg := 0.U(parameter.xlen)
          traceTrapReg := true.B
          traceTrapCauseReg := TrapCause.INTERRUPT.U(4)
        }

        when(fetchResponseError) {
          traceValidReg := true.B
          tracePcReg := pc
          traceNextPcReg := pc
          traceInstrReg := 0.U(parameter.xlen)
          traceLenReg := 4.U(3)
          traceRdWeReg := false.B
          traceRdReg := 0.U(parameter.registerIndexBits)
          traceRdWdataReg := 0.U(parameter.xlen)
          traceRs1AddrReg := 0.U(5)
          traceRs1RdataReg := 0.U(parameter.xlen)
          traceRs2AddrReg := 0.U(5)
          traceRs2RdataReg := 0.U(parameter.xlen)
          traceMemAddrReg := (pc.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt
          traceMemFaultReg := true.B
          traceMemFaultRmaskReg := 0.U(4)
          traceMemFaultWmaskReg := 0.U(4)
          traceCsrAddrReg := CsrAddr.MCAUSE.U(12)
          traceCsrRmaskReg := BigInt("ffffffff", 16).U(parameter.xlen)
          traceCsrWmaskReg := BigInt("ffffffff", 16).U(parameter.xlen)
          traceCsrRdataReg := csrMcause.asUInt
          traceCsrWdataReg := 1.U(parameter.xlen)
          traceTrapReg := true.B
          traceTrapCauseReg := TrapCause.AXI_ERROR.U(4)
        }

        when(loadResponseError) {
          traceValidReg := true.B
          tracePcReg := memPcReg
          traceNextPcReg := memPcReg
          traceInstrReg := memInstrReg.asUInt
          traceLenReg := memLenReg
          traceRdWeReg := false.B
          traceRdReg := 0.U(parameter.registerIndexBits)
          traceRdWdataReg := 0.U(parameter.xlen)
          traceRs1AddrReg := 0.U(5)
          traceRs1RdataReg := 0.U(parameter.xlen)
          traceRs2AddrReg := 0.U(5)
          traceRs2RdataReg := 0.U(parameter.xlen)
          traceMemAddrReg := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt
          traceMemFaultReg := true.B
          traceMemFaultRmaskReg := loadMemMask
          traceMemFaultWmaskReg := 0.U(4)
          traceCsrAddrReg := CsrAddr.MCAUSE.U(12)
          traceCsrRmaskReg := BigInt("ffffffff", 16).U(parameter.xlen)
          traceCsrWmaskReg := BigInt("ffffffff", 16).U(parameter.xlen)
          traceCsrRdataReg := csrMcause.asUInt
          traceCsrWdataReg := 5.U(parameter.xlen)
          traceTrapReg := true.B
          traceTrapCauseReg := TrapCause.AXI_ERROR.U(4)
        }

        when(storeResponseError) {
          traceValidReg := true.B
          tracePcReg := memPcReg
          traceNextPcReg := memPcReg
          traceInstrReg := memInstrReg.asUInt
          traceLenReg := memLenReg
          traceRdWeReg := false.B
          traceRdReg := 0.U(parameter.registerIndexBits)
          traceRdWdataReg := 0.U(parameter.xlen)
          traceRs1AddrReg := 0.U(5)
          traceRs1RdataReg := 0.U(parameter.xlen)
          traceRs2AddrReg := 0.U(5)
          traceRs2RdataReg := 0.U(parameter.xlen)
          traceMemAddrReg := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt
          traceMemFaultReg := true.B
          traceMemFaultRmaskReg := 0.U(4)
          traceMemFaultWmaskReg := memStoreBeReg
          traceCsrAddrReg := CsrAddr.MCAUSE.U(12)
          traceCsrRmaskReg := BigInt("ffffffff", 16).U(parameter.xlen)
          traceCsrWmaskReg := BigInt("ffffffff", 16).U(parameter.xlen)
          traceCsrRdataReg := csrMcause.asUInt
          traceCsrWdataReg := 7.U(parameter.xlen)
          traceTrapReg := true.B
          traceTrapCauseReg := TrapCause.AXI_ERROR.U(4)
        }

        when(loadResponseOk) {
          traceValidReg := true.B
          tracePcReg := memPcReg
          traceNextPcReg := memNextPcReg
          traceInstrReg := memInstrReg.asUInt
          traceLenReg := memLenReg
          traceRdWeReg := memRdReg =/= 0.B(5)
          traceRdReg := memRdReg.bits(3, 0).asUInt
          traceRdWdataReg := (memRdReg =/= 0.B(5)).?(loadWdata.asUInt, 0.U(parameter.xlen))
          traceRs1AddrReg := memTraceRs1AddrReg
          traceRs1RdataReg := memTraceRs1RdataReg
          traceRs2AddrReg := memTraceRs2AddrReg
          traceRs2RdataReg := memTraceRs2RdataReg
          traceMemAddrReg := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt
          traceMemRmaskReg := loadMemMask
          traceMemWmaskReg := 0.U(4)
          traceMemRdataReg := axiR.bits.data
          traceMemWdataReg := 0.U(parameter.xlen)
          traceTrapReg := false.B
          traceTrapCauseReg := 0.U(4)
        }

        when(storeResponseOk) {
          traceValidReg := true.B
          tracePcReg := memPcReg
          traceNextPcReg := memNextPcReg
          traceInstrReg := memInstrReg.asUInt
          traceLenReg := memLenReg
          traceRdWeReg := false.B
          traceRdReg := 0.U(parameter.registerIndexBits)
          traceRdWdataReg := 0.U(parameter.xlen)
          traceRs1AddrReg := memTraceRs1AddrReg
          traceRs1RdataReg := memTraceRs1RdataReg
          traceRs2AddrReg := memTraceRs2AddrReg
          traceRs2RdataReg := memTraceRs2RdataReg
          traceMemAddrReg := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.B(2)).asUInt
          traceMemRmaskReg := 0.U(4)
          traceMemWmaskReg := memStoreBeReg
          traceMemRdataReg := 0.U(parameter.xlen)
          traceMemWdataReg := memStoreDataReg.asUInt
          traceTrapReg := false.B
          traceTrapCauseReg := 0.U(4)
        }

        when(stateStraddle) {
          when(instrReady) {
            when(!execWaitsForMem) {
              traceValidReg := true.B
              tracePcReg := pc
              traceNextPcReg := execNextPc
              traceInstrReg := straddledInstr.asUInt
              traceLenReg := 4.U(3)
            }
          }
        }.otherwise {
          when(stateRun & instrReady) {
            when(!straddled32) {
              when(!execWaitsForMem) {
                traceValidReg := true.B
                tracePcReg := pc
                traceNextPcReg := execNextPc
                traceInstrReg := selectedInstr.asUInt
                traceLenReg := instrCompressed.?(2.U(3), 4.U(3))
              }
            }
          }
        }

        when(commitEntersMem) {
          memTraceRs1AddrReg := execUsesRs1.?(rs1Index.asUInt, 0.U(5))
          memTraceRs1RdataReg := execUsesRs1.?(rs1Data, 0.U(parameter.xlen))
          memTraceRs2AddrReg := execUsesRs2.?(rs2Index.asUInt, 0.U(5))
          memTraceRs2RdataReg := execUsesRs2.?(rs2Data, 0.U(parameter.xlen))
        }

        when(commitNonMem) {
          traceTrapReg := execTrap
          traceTrapCauseReg := execTrapCause
          traceRdWeReg := execWriteRd
          traceRdReg := rdIndex.bits(3, 0).asUInt
          traceRdWdataReg := execWriteRd.?(execWdata, 0.U(parameter.xlen))
          traceRs1AddrReg := (execUsesRs1 & !execTrap).?(rs1Index.asUInt, 0.U(5))
          traceRs1RdataReg := (execUsesRs1 & !execTrap).?(rs1Data, 0.U(parameter.xlen))
          traceRs2AddrReg := (execUsesRs2 & !execTrap).?(rs2Index.asUInt, 0.U(5))
          traceRs2RdataReg := (execUsesRs2 & !execTrap).?(rs2Data, 0.U(parameter.xlen))
          traceNextPcReg := execTrap.?(trapVector, execNextPc)
          when(isCsr & !execTrap) {
            traceCsrAddrReg := csrAddr.asUInt
            traceCsrRmaskReg := BigInt("ffffffff", 16).U(parameter.xlen)
            traceCsrRdataReg := csrReadData.asUInt
            when(csrWriteEnable) {
              traceCsrWmaskReg := BigInt("ffffffff", 16).U(parameter.xlen)
              traceCsrWdataReg := csrTraceWriteData.asUInt
            }
          }
        }
      }

      probe.trace_valid           <== traceValidReg
      probe.trace_pc              <== tracePcReg
      probe.trace_next_pc         <== traceNextPcReg
      probe.trace_instr           <== traceInstrReg
      probe.trace_len             <== traceLenReg
      probe.trace_rd_we           <== traceRdWeReg
      probe.trace_rd              <== traceRdReg
      probe.trace_rd_wdata        <== traceRdWdataReg
      probe.trace_rs1_addr        <== traceRs1AddrReg
      probe.trace_rs1_rdata       <== traceRs1RdataReg
      probe.trace_rs2_addr        <== traceRs2AddrReg
      probe.trace_rs2_rdata       <== traceRs2RdataReg
      probe.trace_mem_addr        <== traceMemAddrReg
      probe.trace_mem_rmask       <== traceMemRmaskReg
      probe.trace_mem_wmask       <== traceMemWmaskReg
      probe.trace_mem_rdata       <== traceMemRdataReg
      probe.trace_mem_wdata       <== traceMemWdataReg
      probe.trace_mem_fault       <== traceMemFaultReg
      probe.trace_mem_fault_rmask <== traceMemFaultRmaskReg
      probe.trace_mem_fault_wmask <== traceMemFaultWmaskReg
      probe.trace_csr_addr        <== traceCsrAddrReg
      probe.trace_csr_rmask       <== traceCsrRmaskReg
      probe.trace_csr_wmask       <== traceCsrWmaskReg
      probe.trace_csr_rdata       <== traceCsrRdataReg
      probe.trace_csr_wdata       <== traceCsrWdataReg
      probe.trace_trap            <== traceTrapReg
      probe.trace_trap_cause      <== traceTrapCauseReg
      probe.trace_mstatus_pre_trap <== tracePreTrapMstatusReg

      val traceMstatusWire = Wire(UInt(parameter.xlen))
      val traceMipWire      = Wire(UInt(parameter.xlen))
      val traceMcauseWire   = Wire(UInt(parameter.xlen))
      traceMstatusWire := csrMstatus.asUInt
      traceMipWire := irqMip.asUInt
      traceMcauseWire := csrMcause.asUInt
      probe.trace_mstatus <== traceMstatusWire
      probe.trace_mip     <== traceMipWire
      probe.trace_mcause  <== traceMcauseWire
