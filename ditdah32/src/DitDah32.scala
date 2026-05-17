// SPDX-License-Identifier: MIT
package com.vowstar.ditdah32

import me.jiuyang.zaozi.*
import me.jiuyang.zaozi.default.{*, given}
import me.jiuyang.zaozi.reftpe.*
import me.jiuyang.zaozi.valuetpe.*
import org.llvm.mlir.scalalib.capi.ir.{Block, Context}

import java.lang.foreign.Arena

class DitDah32Layers(parameter: DitDah32Parameter) extends LayerInterface(parameter):
  def layers = Seq.empty

class DitDah32IO(parameter: DitDah32Parameter) extends HWBundle(parameter):
  val clock = Flipped(Clock())
  val reset = Flipped(Reset())

  val axi_awvalid = Aligned(Bool())
  val axi_awaddr  = Aligned(UInt(parameter.xlen))
  val axi_awprot  = Aligned(UInt(3))
  val axi_awready = Flipped(Bool())
  val axi_wvalid  = Aligned(Bool())
  val axi_wdata   = Aligned(UInt(parameter.xlen))
  val axi_wstrb   = Aligned(UInt(4))
  val axi_wready  = Flipped(Bool())
  val axi_bvalid  = Flipped(Bool())
  val axi_bready  = Aligned(Bool())
  val axi_bresp   = Flipped(UInt(2))
  val axi_arvalid = Aligned(Bool())
  val axi_araddr  = Aligned(UInt(parameter.xlen))
  val axi_arprot  = Aligned(UInt(3))
  val axi_arready = Flipped(Bool())
  val axi_rvalid  = Flipped(Bool())
  val axi_rready  = Aligned(Bool())
  val axi_rdata   = Flipped(UInt(parameter.xlen))
  val axi_rresp   = Flipped(UInt(2))

  val irq_software = Flipped(Bool())
  val irq_timer    = Flipped(Bool())
  val irq_external = Flipped(Bool())
  val irq_pending  = Aligned(Bool())

  val trap      = Aligned(Bool())
  val core_busy = Aligned(Bool())
  val core_sleep = Aligned(Bool())

  val trace_valid      = Option.when(parameter.enableTrace)(Aligned(Bool()))
  val trace_pc         = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_next_pc    = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_instr      = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_len        = Option.when(parameter.enableTrace)(Aligned(UInt(3)))
  val trace_rd_we      = Option.when(parameter.enableTrace)(Aligned(Bool()))
  val trace_rd         = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.registerIndexBits)))
  val trace_rd_wdata   = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_rs1_addr   = Option.when(parameter.enableTrace)(Aligned(UInt(5)))
  val trace_rs1_rdata  = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_rs2_addr   = Option.when(parameter.enableTrace)(Aligned(UInt(5)))
  val trace_rs2_rdata  = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_mem_addr   = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_mem_rmask  = Option.when(parameter.enableTrace)(Aligned(UInt(4)))
  val trace_mem_wmask  = Option.when(parameter.enableTrace)(Aligned(UInt(4)))
  val trace_mem_rdata  = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_mem_wdata  = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_mem_fault       = Option.when(parameter.enableTrace)(Aligned(Bool()))
  val trace_mem_fault_rmask = Option.when(parameter.enableTrace)(Aligned(UInt(4)))
  val trace_mem_fault_wmask = Option.when(parameter.enableTrace)(Aligned(UInt(4)))
  val trace_csr_addr   = Option.when(parameter.enableTrace)(Aligned(UInt(12)))
  val trace_csr_rmask  = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_csr_wmask  = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_csr_rdata  = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_csr_wdata  = Option.when(parameter.enableTrace)(Aligned(UInt(parameter.xlen)))
  val trace_trap       = Option.when(parameter.enableTrace)(Aligned(Bool()))
  val trace_trap_cause = Option.when(parameter.enableTrace)(Aligned(UInt(4)))

class DitDah32Probe(parameter: DitDah32Parameter)
    extends DVBundle[DitDah32Parameter, DitDah32Layers](parameter)

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

  private def trapMstatus[R <: Referable[UInt]](current: R)(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): Node[UInt] =
    (
      0.U(19).asBits ##
      3.U(2).asBits ##
      0.U(3).asBits ##
      current.asBits.bits(CsrBits.MSTATUS_MIE, CsrBits.MSTATUS_MIE) ##
      0.U(3).asBits ##
      0.U(1).asBits ##
      0.U(3).asBits
    ).asUInt

  private def mretMstatus[R <: Referable[UInt]](current: R)(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): Node[UInt] =
    (
      0.U(19).asBits ##
      3.U(2).asBits ##
      0.U(3).asBits ##
      1.U(1).asBits ##
      0.U(3).asBits ##
      current.asBits.bits(CsrBits.MSTATUS_MPIE, CsrBits.MSTATUS_MPIE) ##
      0.U(3).asBits
    ).asUInt

  private def writableMstatus[R <: Referable[UInt]](writeData: R)(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): Node[UInt] =
    (
      0.U(19).asBits ##
      writeData.asBits.bits(CsrBits.MSTATUS_MPP_HIGH, CsrBits.MSTATUS_MPP_LOW) ##
      0.U(3).asBits ##
      writeData.asBits.bits(CsrBits.MSTATUS_MPIE, CsrBits.MSTATUS_MPIE) ##
      0.U(3).asBits ##
      writeData.asBits.bits(CsrBits.MSTATUS_MIE, CsrBits.MSTATUS_MIE) ##
      0.U(3).asBits
    ).asUInt

  private def csrReadSignals(
      addr: Referable[UInt],
      mstatus: Referable[UInt],
      mie: Referable[UInt],
      mtvec: Referable[UInt],
      mscratch: Referable[UInt],
      mepc: Referable[UInt],
      mcause: Referable[UInt],
      mtval: Referable[UInt],
      mip: Referable[UInt],
      parameter: DitDah32Parameter
  )(
      using Arena,
      Context,
      Block,
      sourcecode.File,
      sourcecode.Line,
      sourcecode.Name.Machine,
      InstanceContext
  ): (Wire[UInt], Wire[Bool], Wire[Bool]) =
    val data = Wire(UInt(parameter.xlen))
    val valid = Wire(Bool())
    val readOnly = Wire(Bool())

    data := 0.U(parameter.xlen)
    valid := false.B
    readOnly := false.B
    when(addr === CsrAddr.MSTATUS.U(12)) { valid := true.B; data := mstatus }
    when(addr === CsrAddr.MISA.U(12)) { valid := true.B; readOnly := true.B; data := 0x40000014.U(parameter.xlen) }
    when(addr === CsrAddr.MIE.U(12)) { valid := true.B; data := mie }
    when(addr === CsrAddr.MTVEC.U(12)) { valid := true.B; data := mtvec }
    when(addr === CsrAddr.MSCRATCH.U(12)) { valid := true.B; data := mscratch }
    when(addr === CsrAddr.MEPC.U(12)) { valid := true.B; data := mepc }
    when(addr === CsrAddr.MCAUSE.U(12)) { valid := true.B; data := mcause }
    when(addr === CsrAddr.MTVAL.U(12)) { valid := true.B; data := mtval }
    when(addr === CsrAddr.MIP.U(12)) { valid := true.B; readOnly := true.B; data := mip }
    when(addr === CsrAddr.MVENDORID.U(12)) { valid := true.B; readOnly := true.B; data := 0.U(parameter.xlen) }
    when(addr === CsrAddr.MARCHID.U(12)) { valid := true.B; readOnly := true.B; data := 0.U(parameter.xlen) }
    when(addr === CsrAddr.MIMPID.U(12)) { valid := true.B; readOnly := true.B; data := 0.U(parameter.xlen) }
    when(addr === CsrAddr.MHARTID.U(12)) { valid := true.B; readOnly := true.B; data := 0.U(parameter.xlen) }

    (data, valid, readOnly)

  private def readGpr(
      index: Referable[UInt],
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
    when(index === 1.U(5)) { data := x1 }
    when(index === 2.U(5)) { data := x2 }
    when(index === 3.U(5)) { data := x3 }
    when(index === 4.U(5)) { data := x4 }
    when(index === 5.U(5)) { data := x5 }
    when(index === 6.U(5)) { data := x6 }
    when(index === 7.U(5)) { data := x7 }
    when(index === 8.U(5)) { data := x8 }
    when(index === 9.U(5)) { data := x9 }
    when(index === 10.U(5)) { data := x10 }
    when(index === 11.U(5)) { data := x11 }
    when(index === 12.U(5)) { data := x12 }
    when(index === 13.U(5)) { data := x13 }
    when(index === 14.U(5)) { data := x14 }
    when(index === 15.U(5)) { data := x15 }
    data

  private def writeGpr(
      enable: Referable[Bool],
      index: Referable[UInt],
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
    when(enable & (index === 1.U(5))) { x1 := data }
    when(enable & (index === 2.U(5))) { x2 := data }
    when(enable & (index === 3.U(5))) { x3 := data }
    when(enable & (index === 4.U(5))) { x4 := data }
    when(enable & (index === 5.U(5))) { x5 := data }
    when(enable & (index === 6.U(5))) { x6 := data }
    when(enable & (index === 7.U(5))) { x7 := data }
    when(enable & (index === 8.U(5))) { x8 := data }
    when(enable & (index === 9.U(5))) { x9 := data }
    when(enable & (index === 10.U(5))) { x10 := data }
    when(enable & (index === 11.U(5))) { x11 := data }
    when(enable & (index === 12.U(5))) { x12 := data }
    when(enable & (index === 13.U(5))) { x13 := data }
    when(enable & (index === 14.U(5))) { x14 := data }
    when(enable & (index === 15.U(5))) { x15 := data }

  def architecture(parameter: DitDah32Parameter) =
    val io = summon[Interface[DitDah32IO]]

    given Ref[Clock] = io.clock
    given Ref[Reset] = io.reset

    val pc       = RegInit(parameter.resetVector.U(parameter.xlen))
    val instrReg = RegInit(0.U(parameter.xlen))
    val fetched  = RegInit(false.B)
    val fetchOutstanding = RegInit(false.B)
    val memOutstanding = RegInit(false.B)
    val storeAwDone = RegInit(false.B)
    val storeWDone  = RegInit(false.B)
    val state    = RegInit(CoreState.RESET.U(3))
    val straddleLowHalfword = RegInit(0.U(16))
    val memPcReg         = RegInit(0.U(parameter.xlen))
    val memInstrReg      = RegInit(0.U(parameter.xlen))
    val memLenReg        = RegInit(0.U(3))
    val memNextPcReg     = RegInit(0.U(parameter.xlen))
    val memAddrReg       = RegInit(0.U(parameter.xlen))
    val memRdReg         = RegInit(0.U(5))
    val memFunct3Reg     = RegInit(0.U(3))
    val memStoreDataReg  = RegInit(0.U(parameter.xlen))
    val memStoreBeReg    = RegInit(0.U(4))
    val memTraceRs1AddrReg  = Option.when(parameter.enableTrace)(RegInit(0.U(5)))
    val memTraceRs1RdataReg = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val memTraceRs2AddrReg  = Option.when(parameter.enableTrace)(RegInit(0.U(5)))
    val memTraceRs2RdataReg = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val irqCauseReg      = RegInit(0.U(parameter.xlen))
    val csrMstatus       = RegInit(0.U(parameter.xlen))
    val csrMie           = RegInit(0.U(parameter.xlen))
    val csrMtvec         = RegInit(0.U(parameter.xlen))
    val csrMscratch      = RegInit(0.U(parameter.xlen))
    val csrMepc          = RegInit(0.U(parameter.xlen))
    val csrMcause        = RegInit(0.U(parameter.xlen))
    val csrMtval         = RegInit(0.U(parameter.xlen))
    val trapEventReg       = RegInit(false.B)
    val traceValidReg      = Option.when(parameter.enableTrace)(RegInit(false.B))
    val tracePcReg         = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceNextPcReg     = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceInstrReg      = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceLenReg        = Option.when(parameter.enableTrace)(RegInit(0.U(3)))
    val traceRdWeReg       = Option.when(parameter.enableTrace)(RegInit(false.B))
    val traceRdReg         = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.registerIndexBits)))
    val traceRdWdataReg    = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceRs1AddrReg    = Option.when(parameter.enableTrace)(RegInit(0.U(5)))
    val traceRs1RdataReg   = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceRs2AddrReg    = Option.when(parameter.enableTrace)(RegInit(0.U(5)))
    val traceRs2RdataReg   = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceMemAddrReg    = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceMemRmaskReg   = Option.when(parameter.enableTrace)(RegInit(0.U(4)))
    val traceMemWmaskReg   = Option.when(parameter.enableTrace)(RegInit(0.U(4)))
    val traceMemRdataReg   = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceMemWdataReg   = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceMemFaultReg      = Option.when(parameter.enableTrace)(RegInit(false.B))
    val traceMemFaultRmaskReg = Option.when(parameter.enableTrace)(RegInit(0.U(4)))
    val traceMemFaultWmaskReg = Option.when(parameter.enableTrace)(RegInit(0.U(4)))
    val traceCsrAddrReg    = Option.when(parameter.enableTrace)(RegInit(0.U(12)))
    val traceCsrRmaskReg   = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceCsrWmaskReg   = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceCsrRdataReg   = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceCsrWdataReg   = Option.when(parameter.enableTrace)(RegInit(0.U(parameter.xlen)))
    val traceTrapReg       = Option.when(parameter.enableTrace)(RegInit(false.B))
    val traceTrapCauseReg  = Option.when(parameter.enableTrace)(RegInit(0.U(4)))
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
    val lowerHalfwordBits = Wire(UInt(2))
    val upperHalfwordBits = Wire(UInt(2))
    val instrLowBits      = Wire(UInt(2))
    val instrCompressed   = Wire(Bool())
    val straddled32       = Wire(Bool())
    val pcPlus2           = Wire(UInt(parameter.xlen))
    val pcPlus4           = Wire(UInt(parameter.xlen))
    val sequentialPc      = Wire(UInt(parameter.xlen))
    val execNextPc        = Wire(UInt(parameter.xlen))
    val selectedHalfword  = Wire(UInt(16))
    val selectedInstr     = Wire(UInt(parameter.xlen))
    val straddledInstr    = Wire(UInt(parameter.xlen))
    val decodedInstr      = Wire(UInt(parameter.xlen))
    val cDecodedInstr     = Wire(UInt(parameter.xlen))
    val cNoWriteHint      = Wire(Bool())
    val cInsn             = Wire(UInt(16))
    val cQuadrant         = Wire(UInt(2))
    val cFunct3           = Wire(UInt(3))
    val cRdRs1            = Wire(UInt(5))
    val cRs2              = Wire(UInt(5))
    val cRdPrime          = Wire(UInt(5))
    val cRs1Prime         = Wire(UInt(5))
    val cRs2Prime         = Wire(UInt(5))
    val cShamt            = Wire(UInt(5))
    val cImm6             = Wire(UInt(parameter.xlen))
    val cAddi4spnImm      = Wire(UInt(parameter.xlen))
    val cLwImm            = Wire(UInt(parameter.xlen))
    val cLwspImm          = Wire(UInt(parameter.xlen))
    val cSwspImm          = Wire(UInt(parameter.xlen))
    val cAddi16spImm      = Wire(UInt(parameter.xlen))
    val cBranchImm        = Wire(UInt(parameter.xlen))
    val cJumpImm          = Wire(UInt(parameter.xlen))
    val commitNow         = Wire(Bool())
    val commitInstr       = Wire(UInt(parameter.xlen))
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
    val instrRdata        = Wire(UInt(parameter.xlen))
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
    val opcode            = Wire(UInt(7))
    val rdIndex           = Wire(UInt(5))
    val rs1Index          = Wire(UInt(5))
    val rs2Index          = Wire(UInt(5))
    val funct3            = Wire(UInt(3))
    val funct7            = Wire(UInt(7))
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
    val storeData         = Wire(UInt(parameter.xlen))
    val storeBe           = Wire(UInt(4))
    val loadByte          = Wire(UInt(8))
    val loadHalf          = Wire(UInt(16))
    val loadWdata         = Wire(UInt(parameter.xlen))
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
    val csrAddr           = Wire(UInt(12))
    val csrOperand        = Wire(UInt(parameter.xlen))
    val csrWriteData      = Wire(UInt(parameter.xlen))
    val csrTraceWriteData = Wire(UInt(parameter.xlen))
    val csrWriteEnable    = Wire(Bool())
    val csrUsesRs1        = Wire(Bool())
    val csrIllegal        = Wire(Bool())
    val postCommitMstatus = Wire(UInt(parameter.xlen))
    val postCommitMie     = Wire(UInt(parameter.xlen))
    val irqMip            = Wire(UInt(parameter.xlen))
    val irqEnabledMask    = Wire(UInt(parameter.xlen))
    val irqSoftwareEnabled = Wire(Bool())
    val irqTimerEnabled   = Wire(Bool())
    val irqExternalEnabled = Wire(Bool())
    val irqIndividuallyPending = Wire(Bool())
    val irqTrapPending    = Wire(Bool())
    val irqCause          = Wire(UInt(parameter.xlen))
    val postCommitIrqEnabledMask = Wire(UInt(parameter.xlen))
    val postCommitIrqSoftwareEnabled = Wire(Bool())
    val postCommitIrqTimerEnabled = Wire(Bool())
    val postCommitIrqExternalEnabled = Wire(Bool())
    val postCommitIrqTrapPending = Wire(Bool())
    val postCommitIrqCause = Wire(UInt(parameter.xlen))
    val trapVector        = Wire(UInt(parameter.xlen))
    val standardTrapCause = Wire(UInt(parameter.xlen))
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
    pcFetchAddr := (pc.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt

    fetchRequest := stateRun | stateStraddle
    fetchArValid := fetchRequest & !fetchOutstanding
    fetchArFire := fetchArValid & io.axi_arready
    fetchAcceptsResponse := fetchOutstanding | fetchArFire
    fetchResponseFire := fetchAcceptsResponse & io.axi_rvalid
    fetchResponseError := fetchResponseFire & (io.axi_rresp =/= 0.U(2))
    fetchResponseOk := fetchResponseFire & !fetchResponseError
    instrReady := fetchResponseOk
    instrRdata := io.axi_rdata

    loadArValid := stateLoad & !memOutstanding
    loadArFire := loadArValid & io.axi_arready
    loadAcceptsResponse := stateLoad & (memOutstanding | loadArFire)
    loadResponseFire := loadAcceptsResponse & io.axi_rvalid
    loadResponseError := loadResponseFire & (io.axi_rresp =/= 0.U(2))
    loadResponseOk := loadResponseFire & !loadResponseError
    storeAwValid := stateStore & !storeAwDone
    storeWValid := stateStore & !storeWDone
    storeAwFire := storeAwValid & io.axi_awready
    storeWFire := storeWValid & io.axi_wready
    storeBothDone := (storeAwDone | storeAwFire) & (storeWDone | storeWFire)
    storeResponseFire := stateStore & storeBothDone & io.axi_bvalid
    storeResponseError := storeResponseFire & (io.axi_bresp =/= 0.U(2))
    storeResponseOk := storeResponseFire & !storeResponseError

    lowerHalfwordBits := instrRdata.asBits.bits(1, 0).asUInt
    upperHalfwordBits := instrRdata.asBits.bits(17, 16).asUInt
    instrLowBits      := pcHalfwordHigh.?(upperHalfwordBits, lowerHalfwordBits)
    instrCompressed   := instrLowBits =/= 3.U(2)
    straddled32       := pcHalfwordHigh & !instrCompressed
    selectedHalfword  := pcHalfwordHigh.?(instrRdata.asBits.bits(31, 16).asUInt, instrRdata.asBits.bits(15, 0).asUInt)

    pcPlus2 := (pc + 2.U(parameter.xlen)).asBits.bits(parameter.xlen - 1, 0).asUInt
    pcPlus4 := (pc + 4.U(parameter.xlen)).asBits.bits(parameter.xlen - 1, 0).asUInt
    sequentialPc := commitCompressed.?(pcPlus2, pcPlus4)
    instrAddr := stateStraddle.?(pcPlus2, pcFetchAddr)
    selectedInstr := instrCompressed.?((0.U(16).asBits ## selectedHalfword.asBits).asUInt, instrRdata)
    straddledInstr := (instrRdata.asBits.bits(15, 0) ## straddleLowHalfword.asBits).asUInt

    commitNow := (stateStraddle & instrReady) | (stateRun & instrReady & !straddled32)
    commitInstr := stateStraddle.?(straddledInstr, selectedInstr)
    commitLen := stateStraddle.?(4.U(3), instrCompressed.?(2.U(3), 4.U(3)))
    commitCompressed := commitLen === 2.U(3)

    cInsn := commitInstr.asBits.bits(15, 0).asUInt
    cQuadrant := cInsn.asBits.bits(1, 0).asUInt
    cFunct3 := cInsn.asBits.bits(15, 13).asUInt
    cRdRs1 := cInsn.asBits.bits(11, 7).asUInt
    cRs2 := cInsn.asBits.bits(6, 2).asUInt
    cRdPrime := (1.U(2).asBits ## cInsn.asBits.bits(4, 2)).asUInt
    cRs1Prime := (1.U(2).asBits ## cInsn.asBits.bits(9, 7)).asUInt
    cRs2Prime := (1.U(2).asBits ## cInsn.asBits.bits(4, 2)).asUInt
    cShamt := cInsn.asBits.bits(6, 2).asUInt
    cImm6 := (
      cInsn.asBits.bit(12).?(0x3ffffff.U(26), 0.U(26)).asBits ##
      cInsn.asBits.bits(12, 12) ##
      cInsn.asBits.bits(6, 2)
    ).asUInt
    cAddi4spnImm := (
      0.U(22).asBits ##
      cInsn.asBits.bits(10, 7) ##
      cInsn.asBits.bits(12, 11) ##
      cInsn.asBits.bits(5, 5) ##
      cInsn.asBits.bits(6, 6) ##
      0.U(2).asBits
    ).asUInt
    cLwImm := (
      0.U(25).asBits ##
      cInsn.asBits.bits(5, 5) ##
      cInsn.asBits.bits(12, 10) ##
      cInsn.asBits.bits(6, 6) ##
      0.U(2).asBits
    ).asUInt
    cLwspImm := (
      0.U(24).asBits ##
      cInsn.asBits.bits(3, 2) ##
      cInsn.asBits.bits(12, 12) ##
      cInsn.asBits.bits(6, 4) ##
      0.U(2).asBits
    ).asUInt
    cSwspImm := (
      0.U(24).asBits ##
      cInsn.asBits.bits(8, 7) ##
      cInsn.asBits.bits(12, 9) ##
      0.U(2).asBits
    ).asUInt
    cAddi16spImm := (
      cInsn.asBits.bit(12).?(0x3fffff.U(22), 0.U(22)).asBits ##
      cInsn.asBits.bits(12, 12) ##
      cInsn.asBits.bits(4, 3) ##
      cInsn.asBits.bits(5, 5) ##
      cInsn.asBits.bits(2, 2) ##
      cInsn.asBits.bits(6, 6) ##
      0.U(4).asBits
    ).asUInt
    cBranchImm := (
      cInsn.asBits.bit(12).?(0x7fffff.U(23), 0.U(23)).asBits ##
      cInsn.asBits.bits(12, 12) ##
      cInsn.asBits.bits(6, 5) ##
      cInsn.asBits.bits(2, 2) ##
      cInsn.asBits.bits(11, 10) ##
      cInsn.asBits.bits(4, 3) ##
      0.U(1).asBits
    ).asUInt
    cJumpImm := (
      cInsn.asBits.bit(12).?(0xfffff.U(20), 0.U(20)).asBits ##
      cInsn.asBits.bits(12, 12) ##
      cInsn.asBits.bits(8, 8) ##
      cInsn.asBits.bits(10, 9) ##
      cInsn.asBits.bits(6, 6) ##
      cInsn.asBits.bits(7, 7) ##
      cInsn.asBits.bits(2, 2) ##
      cInsn.asBits.bits(11, 11) ##
      cInsn.asBits.bits(5, 3) ##
      0.U(1).asBits
    ).asUInt

    cDecodedInstr := 0.U(parameter.xlen)
    cNoWriteHint := false.B
    when(cQuadrant === 0.U(2)) {
      when((cFunct3 === 0.U(3)) & (cAddi4spnImm =/= 0.U(parameter.xlen))) {
        cDecodedInstr := (
          cAddi4spnImm.asBits.bits(11, 0) ##
          2.U(5).asBits ##
          0.U(3).asBits ##
          cRdPrime.asBits ##
          0x13.U(7).asBits
        ).asUInt
      }
      when(cFunct3 === 2.U(3)) {
        cDecodedInstr := (
          cLwImm.asBits.bits(11, 0) ##
          cRs1Prime.asBits ##
          2.U(3).asBits ##
          cRdPrime.asBits ##
          0x03.U(7).asBits
        ).asUInt
      }
      when(cFunct3 === 6.U(3)) {
        cDecodedInstr := (
          cLwImm.asBits.bits(11, 5) ##
          cRs2Prime.asBits ##
          cRs1Prime.asBits ##
          2.U(3).asBits ##
          cLwImm.asBits.bits(4, 0) ##
          0x23.U(7).asBits
        ).asUInt
      }
    }
    when(cQuadrant === 1.U(2)) {
      when(cFunct3 === 0.U(3)) {
        cDecodedInstr := (
          cImm6.asBits.bits(11, 0) ##
          cRdRs1.asBits ##
          0.U(3).asBits ##
          cRdRs1.asBits ##
          0x13.U(7).asBits
        ).asUInt
        when(cImm6 === 0.U(parameter.xlen)) {
          cNoWriteHint := true.B
        }
      }
      when(cFunct3 === 1.U(3)) {
        cDecodedInstr := (
          cJumpImm.asBits.bits(20, 20) ##
          cJumpImm.asBits.bits(10, 1) ##
          cJumpImm.asBits.bits(11, 11) ##
          cJumpImm.asBits.bits(19, 12) ##
          1.U(5).asBits ##
          0x6f.U(7).asBits
        ).asUInt
      }
      when(cFunct3 === 2.U(3)) {
        cDecodedInstr := (
          cImm6.asBits.bits(11, 0) ##
          0.U(5).asBits ##
          0.U(3).asBits ##
          cRdRs1.asBits ##
          0x13.U(7).asBits
        ).asUInt
      }
      when(cFunct3 === 3.U(3)) {
        when((cRdRs1 === 0.U(5)) & (cImm6 =/= 0.U(parameter.xlen))) {
          cDecodedInstr := (
            cImm6.asBits.bits(19, 0) ##
            cRdRs1.asBits ##
            0x37.U(7).asBits
          ).asUInt
        }
        when((cRdRs1 === 2.U(5)) & (cAddi16spImm =/= 0.U(parameter.xlen))) {
          cDecodedInstr := (
            cAddi16spImm.asBits.bits(11, 0) ##
            2.U(5).asBits ##
            0.U(3).asBits ##
            2.U(5).asBits ##
            0x13.U(7).asBits
          ).asUInt
        }
        when((cRdRs1 =/= 0.U(5)) & (cRdRs1 =/= 2.U(5)) & ((cImm6 =/= 0.U(parameter.xlen)) | cRdRs1.asBits.bit(4))) {
          cDecodedInstr := (
            cImm6.asBits.bits(19, 0) ##
            cRdRs1.asBits ##
            0x37.U(7).asBits
          ).asUInt
        }
      }
      when(cFunct3 === 4.U(3)) {
        when(cInsn.asBits.bits(11, 10).asUInt === 0.U(2)) {
          when(!cInsn.asBits.bit(12)) {
            cDecodedInstr := (
              0.U(7).asBits ##
              cShamt.asBits ##
              cRs1Prime.asBits ##
              5.U(3).asBits ##
              cRs1Prime.asBits ##
              0x13.U(7).asBits
            ).asUInt
            when(cShamt === 0.U(5)) {
              cNoWriteHint := true.B
            }
          }
        }
        when(cInsn.asBits.bits(11, 10).asUInt === 1.U(2)) {
          when(!cInsn.asBits.bit(12)) {
            cDecodedInstr := (
              0x20.U(7).asBits ##
              cShamt.asBits ##
              cRs1Prime.asBits ##
              5.U(3).asBits ##
              cRs1Prime.asBits ##
              0x13.U(7).asBits
            ).asUInt
            when(cShamt === 0.U(5)) {
              cNoWriteHint := true.B
            }
          }
        }
        when(cInsn.asBits.bits(11, 10).asUInt === 2.U(2)) {
          cDecodedInstr := (
            cImm6.asBits.bits(11, 0) ##
            cRs1Prime.asBits ##
            7.U(3).asBits ##
            cRs1Prime.asBits ##
            0x13.U(7).asBits
          ).asUInt
        }
        when(cInsn.asBits.bits(11, 10).asUInt === 3.U(2)) {
          when(!cInsn.asBits.bit(12)) {
            when(cInsn.asBits.bits(6, 5).asUInt === 0.U(2)) {
              cDecodedInstr := (
                0x20.U(7).asBits ##
                cRs2Prime.asBits ##
                cRs1Prime.asBits ##
                0.U(3).asBits ##
                cRs1Prime.asBits ##
                0x33.U(7).asBits
              ).asUInt
            }
            when(cInsn.asBits.bits(6, 5).asUInt === 1.U(2)) {
              cDecodedInstr := (
                0.U(7).asBits ##
                cRs2Prime.asBits ##
                cRs1Prime.asBits ##
                4.U(3).asBits ##
                cRs1Prime.asBits ##
                0x33.U(7).asBits
              ).asUInt
            }
            when(cInsn.asBits.bits(6, 5).asUInt === 2.U(2)) {
              cDecodedInstr := (
                0.U(7).asBits ##
                cRs2Prime.asBits ##
                cRs1Prime.asBits ##
                6.U(3).asBits ##
                cRs1Prime.asBits ##
                0x33.U(7).asBits
              ).asUInt
            }
            when(cInsn.asBits.bits(6, 5).asUInt === 3.U(2)) {
              cDecodedInstr := (
                0.U(7).asBits ##
                cRs2Prime.asBits ##
                cRs1Prime.asBits ##
                7.U(3).asBits ##
                cRs1Prime.asBits ##
                0x33.U(7).asBits
              ).asUInt
            }
          }
        }
      }
      when(cFunct3 === 5.U(3)) {
        cDecodedInstr := (
          cJumpImm.asBits.bits(20, 20) ##
          cJumpImm.asBits.bits(10, 1) ##
          cJumpImm.asBits.bits(11, 11) ##
          cJumpImm.asBits.bits(19, 12) ##
          0.U(5).asBits ##
          0x6f.U(7).asBits
        ).asUInt
      }
      when((cFunct3 === 6.U(3)) | (cFunct3 === 7.U(3))) {
        cDecodedInstr := (
          cBranchImm.asBits.bits(12, 12) ##
          cBranchImm.asBits.bits(10, 5) ##
          0.U(5).asBits ##
          cRs1Prime.asBits ##
          (cFunct3 === 6.U(3)).?(0.U(3), 1.U(3)).asBits ##
          cBranchImm.asBits.bits(4, 1) ##
          cBranchImm.asBits.bits(11, 11) ##
          0x63.U(7).asBits
        ).asUInt
      }
    }
    when(cQuadrant === 2.U(2)) {
      when(cFunct3 === 0.U(3)) {
        when(!cInsn.asBits.bit(12)) {
          cDecodedInstr := (
            0.U(7).asBits ##
            cShamt.asBits ##
            cRdRs1.asBits ##
            1.U(3).asBits ##
            cRdRs1.asBits ##
            0x13.U(7).asBits
          ).asUInt
          when(cShamt === 0.U(5)) {
            cNoWriteHint := true.B
          }
        }
      }
      when((cFunct3 === 2.U(3)) & (cRdRs1 =/= 0.U(5))) {
        cDecodedInstr := (
          cLwspImm.asBits.bits(11, 0) ##
          2.U(5).asBits ##
          2.U(3).asBits ##
          cRdRs1.asBits ##
          0x03.U(7).asBits
        ).asUInt
      }
      when(cFunct3 === 4.U(3)) {
        when(!cInsn.asBits.bit(12) & (cRs2 === 0.U(5)) & (cRdRs1 =/= 0.U(5))) {
          cDecodedInstr := (
            0.U(12).asBits ##
            cRdRs1.asBits ##
            0.U(3).asBits ##
            0.U(5).asBits ##
            0x67.U(7).asBits
          ).asUInt
        }
        when(!cInsn.asBits.bit(12) & (cRs2 =/= 0.U(5))) {
          cDecodedInstr := (
            0.U(7).asBits ##
            cRs2.asBits ##
            0.U(5).asBits ##
            0.U(3).asBits ##
            cRdRs1.asBits ##
            0x33.U(7).asBits
          ).asUInt
        }
        when(cInsn.asBits.bit(12) & (cRs2 === 0.U(5)) & (cRdRs1 === 0.U(5))) {
          cDecodedInstr := 0x00100073.U(parameter.xlen)
        }
        when(cInsn.asBits.bit(12) & (cRs2 === 0.U(5)) & (cRdRs1 =/= 0.U(5))) {
          cDecodedInstr := (
            0.U(12).asBits ##
            cRdRs1.asBits ##
            0.U(3).asBits ##
            1.U(5).asBits ##
            0x67.U(7).asBits
          ).asUInt
        }
        when(cInsn.asBits.bit(12) & (cRs2 =/= 0.U(5))) {
          cDecodedInstr := (
            0.U(7).asBits ##
            cRs2.asBits ##
            cRdRs1.asBits ##
            0.U(3).asBits ##
            cRdRs1.asBits ##
            0x33.U(7).asBits
          ).asUInt
        }
      }
      when(cFunct3 === 6.U(3)) {
        cDecodedInstr := (
          cSwspImm.asBits.bits(11, 5) ##
          cRs2.asBits ##
          2.U(5).asBits ##
          2.U(3).asBits ##
          cSwspImm.asBits.bits(4, 0) ##
          0x23.U(7).asBits
        ).asUInt
      }
    }
    decodedInstr := commitCompressed.?(cDecodedInstr, commitInstr)

    opcode   := decodedInstr.asBits.bits(6, 0).asUInt
    rdIndex  := decodedInstr.asBits.bits(11, 7).asUInt
    funct3   := decodedInstr.asBits.bits(14, 12).asUInt
    rs1Index := decodedInstr.asBits.bits(19, 15).asUInt
    rs2Index := decodedInstr.asBits.bits(24, 20).asUInt
    shamt    := decodedInstr.asBits.bits(24, 20).asUInt
    funct7   := decodedInstr.asBits.bits(31, 25).asUInt

    rs1Data := readGpr(rs1Index, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15, parameter)
    rs2Data := readGpr(rs2Index, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15, parameter)

    csrAddr := decodedInstr.asBits.bits(31, 20).asUInt
    isCsr := (opcode === 0x73.U(7)) & (funct3 =/= 0.U(3))
    isCsrImm := isCsr & funct3.asBits.bit(2)
    csrOperand := isCsrImm.?((0.U(27).asBits ## rs1Index.asBits).asUInt, rs1Data)
    csrWriteEnable := isCsr & (
      (funct3 === 1.U(3)) |
      (funct3 === 5.U(3)) |
      (((funct3 === 2.U(3)) | (funct3 === 3.U(3)) | (funct3 === 6.U(3)) | (funct3 === 7.U(3))) & (csrOperand =/= 0.U(parameter.xlen)))
    )
    csrUsesRs1 := isCsr & !isCsrImm & (
      (funct3 === 1.U(3)) |
      (((funct3 === 2.U(3)) | (funct3 === 3.U(3))) & (rs1Index =/= 0.U(5)))
    )

    irqMip := (
      io.irq_software.?(8.U(parameter.xlen), 0.U(parameter.xlen)) +
      io.irq_timer.?(0x80.U(parameter.xlen), 0.U(parameter.xlen)) +
      io.irq_external.?(0x800.U(parameter.xlen), 0.U(parameter.xlen))
    ).asBits.bits(parameter.xlen - 1, 0).asUInt
    irqEnabledMask := (csrMie.asBits & irqMip.asBits).bits(parameter.xlen - 1, 0).asUInt
    irqSoftwareEnabled := irqEnabledMask.asBits.bit(CsrBits.IRQ_SOFTWARE)
    irqTimerEnabled := irqEnabledMask.asBits.bit(CsrBits.IRQ_TIMER)
    irqExternalEnabled := irqEnabledMask.asBits.bit(CsrBits.IRQ_EXTERNAL)
    irqIndividuallyPending := irqEnabledMask =/= 0.U(parameter.xlen)
    irqTrapPending := irqIndividuallyPending & csrMstatus.asBits.bit(CsrBits.MSTATUS_MIE)
    irqCause := BigInt("80000007", 16).U(parameter.xlen)
    when(irqSoftwareEnabled) {
      irqCause := BigInt("80000003", 16).U(parameter.xlen)
    }
    when(irqExternalEnabled) {
      irqCause := BigInt("8000000b", 16).U(parameter.xlen)
    }
    trapVector := (csrMtvec.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt

    val (csrReadData, csrValid, csrReadOnly) =
      csrReadSignals(csrAddr, csrMstatus, csrMie, csrMtvec, csrMscratch, csrMepc, csrMcause, csrMtval, irqMip, parameter)

    csrWriteData := csrReadData
    when((funct3 === 1.U(3)) | (funct3 === 5.U(3))) {
      csrWriteData := csrOperand
    }
    when((funct3 === 2.U(3)) | (funct3 === 6.U(3))) {
      csrWriteData := (csrReadData.asBits | csrOperand.asBits).bits(parameter.xlen - 1, 0).asUInt
    }
    when((funct3 === 3.U(3)) | (funct3 === 7.U(3))) {
      csrWriteData := (csrReadData.asBits & (csrOperand.asBits ^ BigInt("ffffffff", 16).U(parameter.xlen).asBits)).bits(parameter.xlen - 1, 0).asUInt
    }
    // RVFI csr_<name>_wdata reports the user-intended next value before
    // any WARL legalization, matching the RVFI convention
    // used by rvfi_csrw_check. Hardware-level WARL legalization is applied
    // separately on postCommit* and the CSR register input below.
    csrTraceWriteData := csrWriteData

    postCommitMstatus := csrMstatus
    when(isCsr & csrWriteEnable & (csrAddr === CsrAddr.MSTATUS.U(12)) & !execTrap) {
      postCommitMstatus := writableMstatus(csrWriteData)
    }
    when(isMret & !execTrap) {
      postCommitMstatus := mretMstatus(csrMstatus)
    }
    postCommitMie := csrMie
    when(isCsr & csrWriteEnable & (csrAddr === CsrAddr.MIE.U(12)) & !execTrap) {
      postCommitMie := (csrWriteData.asBits & 0x888.U(parameter.xlen).asBits).bits(parameter.xlen - 1, 0).asUInt
    }
    postCommitIrqEnabledMask := (postCommitMie.asBits & irqMip.asBits).bits(parameter.xlen - 1, 0).asUInt
    postCommitIrqSoftwareEnabled := postCommitIrqEnabledMask.asBits.bit(CsrBits.IRQ_SOFTWARE)
    postCommitIrqTimerEnabled := postCommitIrqEnabledMask.asBits.bit(CsrBits.IRQ_TIMER)
    postCommitIrqExternalEnabled := postCommitIrqEnabledMask.asBits.bit(CsrBits.IRQ_EXTERNAL)
    postCommitIrqTrapPending := (postCommitIrqEnabledMask =/= 0.U(parameter.xlen)) & postCommitMstatus.asBits.bit(CsrBits.MSTATUS_MIE)
    postCommitIrqCause := BigInt("80000007", 16).U(parameter.xlen)
    when(postCommitIrqSoftwareEnabled) {
      postCommitIrqCause := BigInt("80000003", 16).U(parameter.xlen)
    }
    when(postCommitIrqExternalEnabled) {
      postCommitIrqCause := BigInt("8000000b", 16).U(parameter.xlen)
    }
    csrIllegal := isCsr & (!csrValid | (funct3 === 4.U(3)) | (csrWriteEnable & csrReadOnly))

    imm12 := (decodedInstr.asBits.bit(31).?(0xfffff.U(20), 0.U(20)).asBits ## decodedInstr.asBits.bits(31, 20)).asUInt
    immS := (
      decodedInstr.asBits.bit(31).?(0xfffff.U(20), 0.U(20)).asBits ##
      decodedInstr.asBits.bits(31, 25) ##
      decodedInstr.asBits.bits(11, 7)
    ).asUInt
    immB := (
      decodedInstr.asBits.bit(31).?(0x7ffff.U(19), 0.U(19)).asBits ##
      decodedInstr.asBits.bits(31, 31) ##
      decodedInstr.asBits.bits(7, 7) ##
      decodedInstr.asBits.bits(30, 25) ##
      decodedInstr.asBits.bits(11, 8) ##
      0.U(1).asBits
    ).asUInt
    immJ := (
      decodedInstr.asBits.bit(31).?(0x7ff.U(11), 0.U(11)).asBits ##
      decodedInstr.asBits.bits(31, 31) ##
      decodedInstr.asBits.bits(19, 12) ##
      decodedInstr.asBits.bits(20, 20) ##
      decodedInstr.asBits.bits(30, 21) ##
      0.U(1).asBits
    ).asUInt
    upperImm := (decodedInstr.asBits.bits(31, 12) ## 0.U(12).asBits).asUInt
    jalrTarget := ((rs1Data + imm12).asBits.bits(parameter.xlen - 1, 1) ## 0.U(1).asBits).asUInt
    memAddr := (isStore).?((rs1Data + immS).asBits.bits(parameter.xlen - 1, 0).asUInt, (rs1Data + imm12).asBits.bits(parameter.xlen - 1, 0).asUInt)
    memAlignedAddr := (memAddr.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt
    storeData := rs2Data
    storeBe := 0.U(4)
    when(isStore) {
      when(funct3 === 0.U(3)) {
        when(memAddr.asBits.bits(1, 0).asUInt === 0.U(2)) {
          storeData := (0.U(24).asBits ## rs2Data.asBits.bits(7, 0)).asUInt
          storeBe := 1.U(4)
        }
        when(memAddr.asBits.bits(1, 0).asUInt === 1.U(2)) {
          storeData := (0.U(16).asBits ## rs2Data.asBits.bits(7, 0) ## 0.U(8).asBits).asUInt
          storeBe := 2.U(4)
        }
        when(memAddr.asBits.bits(1, 0).asUInt === 2.U(2)) {
          storeData := (0.U(8).asBits ## rs2Data.asBits.bits(7, 0) ## 0.U(16).asBits).asUInt
          storeBe := 4.U(4)
        }
        when(memAddr.asBits.bits(1, 0).asUInt === 3.U(2)) {
          storeData := (rs2Data.asBits.bits(7, 0) ## 0.U(24).asBits).asUInt
          storeBe := 8.U(4)
        }
      }
      when(funct3 === 1.U(3)) {
        when(!memAddr.asBits.bit(1)) {
          storeData := (0.U(16).asBits ## rs2Data.asBits.bits(15, 0)).asUInt
          storeBe := 3.U(4)
        }
        when(memAddr.asBits.bit(1)) {
          storeData := (rs2Data.asBits.bits(15, 0) ## 0.U(16).asBits).asUInt
          storeBe := 0xc.U(4)
        }
      }
      when(funct3 === 2.U(3)) {
        storeData := rs2Data
        storeBe := 0xf.U(4)
      }
    }
    loadByte := io.axi_rdata.asBits.bits(7, 0).asUInt
    when(memAddrReg.asBits.bits(1, 0).asUInt === 1.U(2)) {
      loadByte := io.axi_rdata.asBits.bits(15, 8).asUInt
    }
    when(memAddrReg.asBits.bits(1, 0).asUInt === 2.U(2)) {
      loadByte := io.axi_rdata.asBits.bits(23, 16).asUInt
    }
    when(memAddrReg.asBits.bits(1, 0).asUInt === 3.U(2)) {
      loadByte := io.axi_rdata.asBits.bits(31, 24).asUInt
    }
    loadHalf := memAddrReg.asBits.bit(1).?(io.axi_rdata.asBits.bits(31, 16).asUInt, io.axi_rdata.asBits.bits(15, 0).asUInt)
    loadWdata := io.axi_rdata
    when(memFunct3Reg === 0.U(3)) {
      loadWdata := (loadByte.asBits.bit(7).?(0xffffff.U(24), 0.U(24)).asBits ## loadByte.asBits).asUInt
    }
    when(memFunct3Reg === 1.U(3)) {
      loadWdata := (loadHalf.asBits.bit(15).?(0xffff.U(16), 0.U(16)).asBits ## loadHalf.asBits).asUInt
    }
    when(memFunct3Reg === 4.U(3)) {
      loadWdata := (0.U(24).asBits ## loadByte.asBits).asUInt
    }
    when(memFunct3Reg === 5.U(3)) {
      loadWdata := (0.U(16).asBits ## loadHalf.asBits).asUInt
    }
    loadMemMask := 0.U(4)
    when((memFunct3Reg === 0.U(3)) | (memFunct3Reg === 4.U(3))) {
      when(memAddrReg.asBits.bits(1, 0).asUInt === 0.U(2)) { loadMemMask := 1.U(4) }
      when(memAddrReg.asBits.bits(1, 0).asUInt === 1.U(2)) { loadMemMask := 2.U(4) }
      when(memAddrReg.asBits.bits(1, 0).asUInt === 2.U(2)) { loadMemMask := 4.U(4) }
      when(memAddrReg.asBits.bits(1, 0).asUInt === 3.U(2)) { loadMemMask := 8.U(4) }
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

    isLui    := opcode === 0x37.U(7)
    isAuipc  := opcode === 0x17.U(7)
    isJal    := opcode === 0x6f.U(7)
    isJalr   := (opcode === 0x67.U(7)) & (funct3 === 0.U(3))
    isBranch := (opcode === 0x63.U(7)) & (
      (funct3 === 0.U(3)) |
      (funct3 === 1.U(3)) |
      (funct3 === 4.U(3)) |
      (funct3 === 5.U(3)) |
      (funct3 === 6.U(3)) |
      (funct3 === 7.U(3))
    )
    isLoad := (opcode === 0x03.U(7)) & (
      (funct3 === 0.U(3)) |
      (funct3 === 1.U(3)) |
      (funct3 === 2.U(3)) |
      (funct3 === 4.U(3)) |
      (funct3 === 5.U(3))
    )
    isStore := (opcode === 0x23.U(7)) & (
      (funct3 === 0.U(3)) |
      (funct3 === 1.U(3)) |
      (funct3 === 2.U(3))
    )
    isOpImm  := opcode === 0x13.U(7)
    isAluImm := isOpImm & (
      (funct3 === 0.U(3)) |
      (funct3 === 2.U(3)) |
      (funct3 === 3.U(3)) |
      (funct3 === 4.U(3)) |
      (funct3 === 6.U(3)) |
      (funct3 === 7.U(3)) |
      ((funct3 === 1.U(3)) & (funct7 === 0.U(7))) |
      ((funct3 === 5.U(3)) & ((funct7 === 0.U(7)) | (funct7 === 0x20.U(7))))
    )
    isOpReg  := opcode === 0x33.U(7)
    isAluReg := isOpReg & (
      ((funct7 === 0.U(7)) & (
        (funct3 === 0.U(3)) |
        (funct3 === 1.U(3)) |
        (funct3 === 2.U(3)) |
        (funct3 === 3.U(3)) |
        (funct3 === 4.U(3)) |
        (funct3 === 5.U(3)) |
        (funct3 === 6.U(3)) |
        (funct3 === 7.U(3))
      )) |
      ((funct7 === 0x20.U(7)) & ((funct3 === 0.U(3)) | (funct3 === 5.U(3))))
    )
    isFence  := (opcode === 0x0f.U(7)) & (funct3 === 0.U(3))
    isEcall  := decodedInstr === 0x00000073.U(parameter.xlen)
    isEbreak := decodedInstr === 0x00100073.U(parameter.xlen)
    isWfi    := decodedInstr === 0x10500073.U(parameter.xlen)
    isMret   := decodedInstr === 0x30200073.U(parameter.xlen)
    isCNop   := commitCompressed & (commitInstr === 1.U(parameter.xlen))

    rdIllegal  := rdIndex.asBits.bit(4)
    rs1Illegal := rs1Index.asBits.bit(4)
    rs2Illegal := rs2Index.asBits.bit(4)
    loadMisaligned := isLoad & (
      (((funct3 === 1.U(3)) | (funct3 === 5.U(3))) & memAddr.asBits.bit(0)) |
      ((funct3 === 2.U(3)) & (memAddr.asBits.bits(1, 0).asUInt =/= 0.U(2)))
    )
    storeMisaligned := isStore & (
      ((funct3 === 1.U(3)) & memAddr.asBits.bit(0)) |
      ((funct3 === 2.U(3)) & (memAddr.asBits.bits(1, 0).asUInt =/= 0.U(2)))
    )
    execUsesRd  := isLui | isAuipc | isJal | isJalr | isLoad | isAluImm | isAluReg | isCsr
    execUsesRs1 := isJalr | isBranch | isLoad | isStore | isAluImm | isAluReg | csrUsesRs1
    execUsesRs2 := isBranch | isStore | isAluReg
    execKnown   := isLui | isAuipc | isJal | isJalr | isBranch | isLoad | isStore | isAluImm | isAluReg | isFence | isEcall | isEbreak | isWfi | isMret | isCsr | isCNop

    execTrap := (!execKnown) | csrIllegal | (execUsesRd & rdIllegal) | (execUsesRs1 & rs1Illegal) | (execUsesRs2 & rs2Illegal) | loadMisaligned | storeMisaligned | isEcall | isEbreak
    execTrapCause := TrapCause.NONE.U(4)
    when(!execKnown | csrIllegal) {
      execTrapCause := TrapCause.ILLEGAL.U(4)
    }
    when((execUsesRd & rdIllegal) | (execUsesRs1 & rs1Illegal) | (execUsesRs2 & rs2Illegal)) {
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

    standardTrapCause := StandardCause.ILLEGAL_INSTRUCTION.U(parameter.xlen)
    when(loadMisaligned) {
      standardTrapCause := StandardCause.LOAD_MISALIGNED.U(parameter.xlen)
    }
    when(storeMisaligned) {
      standardTrapCause := StandardCause.STORE_MISALIGNED.U(parameter.xlen)
    }
    when(isEcall) {
      standardTrapCause := StandardCause.ECALL_M.U(parameter.xlen)
    }
    when(isEbreak) {
      standardTrapCause := StandardCause.BREAKPOINT.U(parameter.xlen)
    }
    standardTrapValue := 0.U(parameter.xlen)
    when(!execKnown | csrIllegal) {
      standardTrapValue := commitInstr
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
      when(funct3 === 0.U(3)) {
        execWdata := (rs1Data + imm12).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 2.U(3)) {
        execWdata := (rs1SignedOrder < imm12SignedOrder).?(1.U(parameter.xlen), 0.U(parameter.xlen))
      }
      when(funct3 === 3.U(3)) {
        execWdata := (rs1Data < imm12).?(1.U(parameter.xlen), 0.U(parameter.xlen))
      }
      when(funct3 === 4.U(3)) {
        execWdata := (rs1Data.asBits ^ imm12.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 6.U(3)) {
        execWdata := (rs1Data.asBits | imm12.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 7.U(3)) {
        execWdata := (rs1Data.asBits & imm12.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 1.U(3)) {
        execWdata := (rs1Data << shamt).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 5.U(3)) & (funct7 === 0.U(7))) {
        execWdata := (rs1Data >> shamt).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 5.U(3)) & (funct7 === 0x20.U(7))) {
        execWdata := sraImmWdata
      }
    }
    when(isAluReg) {
      when((funct3 === 0.U(3)) & (funct7 === 0.U(7))) {
        execWdata := (rs1Data + rs2Data).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 0.U(3)) & (funct7 === 0x20.U(7))) {
        execWdata := (rs1Data - rs2Data).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 1.U(3)) {
        execWdata := (rs1Data << rs2Shamt).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 2.U(3)) {
        execWdata := (rs1SignedOrder < rs2SignedOrder).?(1.U(parameter.xlen), 0.U(parameter.xlen))
      }
      when(funct3 === 3.U(3)) {
        execWdata := (rs1Data < rs2Data).?(1.U(parameter.xlen), 0.U(parameter.xlen))
      }
      when(funct3 === 4.U(3)) {
        execWdata := (rs1Data.asBits ^ rs2Data.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 5.U(3)) & (funct7 === 0.U(7))) {
        execWdata := (rs1Data >> rs2Shamt).asBits.bits(parameter.xlen - 1, 0).asUInt
      }
      when((funct3 === 5.U(3)) & (funct7 === 0x20.U(7))) {
        execWdata := sraRegWdata
      }
      when(funct3 === 6.U(3)) {
        execWdata := (rs1Data.asBits | rs2Data.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
      when(funct3 === 7.U(3)) {
        execWdata := (rs1Data.asBits & rs2Data.asBits).bits(parameter.xlen - 1, 0).asUInt
      }
    }
    when(isCsr) {
      execWdata := csrReadData
    }
    execWriteRd := execUsesRd & !execTrap & (rdIndex =/= 0.U(5)) & !cNoWriteHint
    execWaitsForMem := (isLoad | isStore) & !execTrap

    branchTaken := false.B
    when(isBranch) {
      when(funct3 === 0.U(3)) {
        branchTaken := rs1Data === rs2Data
      }
      when(funct3 === 1.U(3)) {
        branchTaken := rs1Data =/= rs2Data
      }
      when(funct3 === 4.U(3)) {
        branchTaken := rs1SignedOrder < rs2SignedOrder
      }
      when(funct3 === 5.U(3)) {
        branchTaken := !(rs1SignedOrder < rs2SignedOrder)
      }
      when(funct3 === 6.U(3)) {
        branchTaken := rs1Data < rs2Data
      }
      when(funct3 === 7.U(3)) {
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

    io.axi_awvalid := storeAwValid
    io.axi_awaddr  := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt
    io.axi_awprot  := 2.U(3)
    io.axi_wvalid  := storeWValid
    io.axi_wdata   := memStoreDataReg
    io.axi_wstrb   := memStoreBeReg
    io.axi_bready  := stateStore & storeBothDone
    io.axi_arvalid := loadArValid | fetchArValid
    io.axi_araddr  := stateLoad.?((memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt, instrAddr)
    io.axi_arprot  := stateLoad.?(2.U(3), 6.U(3))
    io.axi_rready  := loadAcceptsResponse | fetchAcceptsResponse

    io.irq_pending := irqIndividuallyPending
    io.trap      := stateTrap | trapEventReg
    io.core_busy := stateRun | stateStraddle | stateLoad | stateStore | stateIrq
    io.core_sleep := stateSleep

    traceValidReg.foreach(reg => io.trace_valid.foreach(_ := reg))
    tracePcReg.foreach(reg => io.trace_pc.foreach(_ := reg))
    traceNextPcReg.foreach(reg => io.trace_next_pc.foreach(_ := reg))
    traceInstrReg.foreach(reg => io.trace_instr.foreach(_ := reg))
    traceLenReg.foreach(reg => io.trace_len.foreach(_ := reg))
    traceRdWeReg.foreach(reg => io.trace_rd_we.foreach(_ := reg))
    traceRdReg.foreach(reg => io.trace_rd.foreach(_ := reg))
    traceRdWdataReg.foreach(reg => io.trace_rd_wdata.foreach(_ := reg))
    traceRs1AddrReg.foreach(reg => io.trace_rs1_addr.foreach(_ := reg))
    traceRs1RdataReg.foreach(reg => io.trace_rs1_rdata.foreach(_ := reg))
    traceRs2AddrReg.foreach(reg => io.trace_rs2_addr.foreach(_ := reg))
    traceRs2RdataReg.foreach(reg => io.trace_rs2_rdata.foreach(_ := reg))
    traceMemAddrReg.foreach(reg => io.trace_mem_addr.foreach(_ := reg))
    traceMemRmaskReg.foreach(reg => io.trace_mem_rmask.foreach(_ := reg))
    traceMemWmaskReg.foreach(reg => io.trace_mem_wmask.foreach(_ := reg))
    traceMemRdataReg.foreach(reg => io.trace_mem_rdata.foreach(_ := reg))
    traceMemWdataReg.foreach(reg => io.trace_mem_wdata.foreach(_ := reg))
    traceMemFaultReg.foreach(reg => io.trace_mem_fault.foreach(_ := reg))
    traceMemFaultRmaskReg.foreach(reg => io.trace_mem_fault_rmask.foreach(_ := reg))
    traceMemFaultWmaskReg.foreach(reg => io.trace_mem_fault_wmask.foreach(_ := reg))
    traceCsrAddrReg.foreach(reg => io.trace_csr_addr.foreach(_ := reg))
    traceCsrRmaskReg.foreach(reg => io.trace_csr_rmask.foreach(_ := reg))
    traceCsrWmaskReg.foreach(reg => io.trace_csr_wmask.foreach(_ := reg))
    traceCsrRdataReg.foreach(reg => io.trace_csr_rdata.foreach(_ := reg))
    traceCsrWdataReg.foreach(reg => io.trace_csr_wdata.foreach(_ := reg))
    traceTrapReg.foreach(reg => io.trace_trap.foreach(_ := reg))
    traceTrapCauseReg.foreach(reg => io.trace_trap_cause.foreach(_ := reg))

    when(stateReset) {
      state := CoreState.RUN.U(3)
      fetchOutstanding := false.B
      memOutstanding := false.B
      storeAwDone := false.B
      storeWDone := false.B
    }.otherwise {
      trapEventReg := false.B
      traceValidReg.foreach(_ := false.B)
      traceRdWeReg.foreach(_ := false.B)
      traceRdReg.foreach(_ := 0.U(parameter.registerIndexBits))
      traceRdWdataReg.foreach(_ := 0.U(parameter.xlen))
      traceRs1AddrReg.foreach(_ := 0.U(5))
      traceRs1RdataReg.foreach(_ := 0.U(parameter.xlen))
      traceRs2AddrReg.foreach(_ := 0.U(5))
      traceRs2RdataReg.foreach(_ := 0.U(parameter.xlen))
      traceMemAddrReg.foreach(_ := 0.U(parameter.xlen))
      traceMemRmaskReg.foreach(_ := 0.U(4))
      traceMemWmaskReg.foreach(_ := 0.U(4))
      traceMemRdataReg.foreach(_ := 0.U(parameter.xlen))
      traceMemWdataReg.foreach(_ := 0.U(parameter.xlen))
      traceMemFaultReg.foreach(_ := false.B)
      traceMemFaultRmaskReg.foreach(_ := 0.U(4))
      traceMemFaultWmaskReg.foreach(_ := 0.U(4))
      traceCsrAddrReg.foreach(_ := 0.U(12))
      traceCsrRmaskReg.foreach(_ := 0.U(parameter.xlen))
      traceCsrWmaskReg.foreach(_ := 0.U(parameter.xlen))
      traceCsrRdataReg.foreach(_ := 0.U(parameter.xlen))
      traceCsrWdataReg.foreach(_ := 0.U(parameter.xlen))
      traceTrapReg.foreach(_ := false.B)
      traceTrapCauseReg.foreach(_ := 0.U(4))

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
        traceValidReg.foreach(_ := true.B)
        tracePcReg.foreach(_ := csrMepc)
        traceNextPcReg.foreach(_ := trapVector)
        traceInstrReg.foreach(_ := 0.U(parameter.xlen))
        traceLenReg.foreach(_ := 0.U(3))
        traceRdWeReg.foreach(_ := false.B)
        traceRdReg.foreach(_ := 0.U(parameter.registerIndexBits))
        traceRdWdataReg.foreach(_ := 0.U(parameter.xlen))
        traceRs1AddrReg.foreach(_ := 0.U(5))
        traceRs1RdataReg.foreach(_ := 0.U(parameter.xlen))
        traceRs2AddrReg.foreach(_ := 0.U(5))
        traceRs2RdataReg.foreach(_ := 0.U(parameter.xlen))
        trapEventReg := true.B
        traceTrapReg.foreach(_ := true.B)
        traceTrapCauseReg.foreach(_ := TrapCause.INTERRUPT.U(4))
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
        csrMcause := 1.U(parameter.xlen)
        csrMtval := pc
        csrMepc := pc
        csrMstatus := trapMstatus(csrMstatus)
        traceValidReg.foreach(_ := true.B)
        tracePcReg.foreach(_ := pc)
        traceNextPcReg.foreach(_ := pc)
        traceInstrReg.foreach(_ := 0.U(parameter.xlen))
        traceLenReg.foreach(_ := 4.U(3))
        traceRdWeReg.foreach(_ := false.B)
        traceRdReg.foreach(_ := 0.U(parameter.registerIndexBits))
        traceRdWdataReg.foreach(_ := 0.U(parameter.xlen))
        traceRs1AddrReg.foreach(_ := 0.U(5))
        traceRs1RdataReg.foreach(_ := 0.U(parameter.xlen))
        traceRs2AddrReg.foreach(_ := 0.U(5))
        traceRs2RdataReg.foreach(_ := 0.U(parameter.xlen))
        traceMemAddrReg.foreach(_ := (pc.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt)
        traceMemFaultReg.foreach(_ := true.B)
        traceMemFaultRmaskReg.foreach(_ := 0.U(4))
        traceMemFaultWmaskReg.foreach(_ := 0.U(4))
        traceCsrAddrReg.foreach(_ := CsrAddr.MCAUSE.U(12))
        traceCsrRmaskReg.foreach(_ := BigInt("ffffffff", 16).U(parameter.xlen))
        traceCsrWmaskReg.foreach(_ := BigInt("ffffffff", 16).U(parameter.xlen))
        traceCsrRdataReg.foreach(_ := csrMcause)
        traceCsrWdataReg.foreach(_ := 1.U(parameter.xlen))
        trapEventReg := true.B
        traceTrapReg.foreach(_ := true.B)
        traceTrapCauseReg.foreach(_ := TrapCause.AXI_ERROR.U(4))
      }

      when(loadResponseError) {
        // Recoverable load access fault per doc/memory_fault_contract.md.
        state := CoreState.IRQ.U(3)
        csrMcause := 5.U(parameter.xlen)
        csrMtval := memAddrReg
        csrMepc := memPcReg
        csrMstatus := trapMstatus(csrMstatus)
        traceValidReg.foreach(_ := true.B)
        tracePcReg.foreach(_ := memPcReg)
        traceNextPcReg.foreach(_ := memPcReg)
        traceInstrReg.foreach(_ := memInstrReg)
        traceLenReg.foreach(_ := memLenReg)
        traceRdWeReg.foreach(_ := false.B)
        traceRdReg.foreach(_ := 0.U(parameter.registerIndexBits))
        traceRdWdataReg.foreach(_ := 0.U(parameter.xlen))
        traceRs1AddrReg.foreach(_ := 0.U(5))
        traceRs1RdataReg.foreach(_ := 0.U(parameter.xlen))
        traceRs2AddrReg.foreach(_ := 0.U(5))
        traceRs2RdataReg.foreach(_ := 0.U(parameter.xlen))
        traceMemAddrReg.foreach(_ := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt)
        traceMemFaultReg.foreach(_ := true.B)
        traceMemFaultRmaskReg.foreach(_ := loadMemMask)
        traceMemFaultWmaskReg.foreach(_ := 0.U(4))
        traceCsrAddrReg.foreach(_ := CsrAddr.MCAUSE.U(12))
        traceCsrRmaskReg.foreach(_ := BigInt("ffffffff", 16).U(parameter.xlen))
        traceCsrWmaskReg.foreach(_ := BigInt("ffffffff", 16).U(parameter.xlen))
        traceCsrRdataReg.foreach(_ := csrMcause)
        traceCsrWdataReg.foreach(_ := 5.U(parameter.xlen))
        trapEventReg := true.B
        traceTrapReg.foreach(_ := true.B)
        traceTrapCauseReg.foreach(_ := TrapCause.AXI_ERROR.U(4))
      }

      when(storeResponseError) {
        // Recoverable store access fault per doc/memory_fault_contract.md.
        storeAwDone := false.B
        storeWDone := false.B
        state := CoreState.IRQ.U(3)
        csrMcause := 7.U(parameter.xlen)
        csrMtval := memAddrReg
        csrMepc := memPcReg
        csrMstatus := trapMstatus(csrMstatus)
        traceValidReg.foreach(_ := true.B)
        tracePcReg.foreach(_ := memPcReg)
        traceNextPcReg.foreach(_ := memPcReg)
        traceInstrReg.foreach(_ := memInstrReg)
        traceLenReg.foreach(_ := memLenReg)
        traceRdWeReg.foreach(_ := false.B)
        traceRdReg.foreach(_ := 0.U(parameter.registerIndexBits))
        traceRdWdataReg.foreach(_ := 0.U(parameter.xlen))
        traceRs1AddrReg.foreach(_ := 0.U(5))
        traceRs1RdataReg.foreach(_ := 0.U(parameter.xlen))
        traceRs2AddrReg.foreach(_ := 0.U(5))
        traceRs2RdataReg.foreach(_ := 0.U(parameter.xlen))
        traceMemAddrReg.foreach(_ := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt)
        traceMemFaultReg.foreach(_ := true.B)
        traceMemFaultRmaskReg.foreach(_ := 0.U(4))
        traceMemFaultWmaskReg.foreach(_ := memStoreBeReg)
        traceCsrAddrReg.foreach(_ := CsrAddr.MCAUSE.U(12))
        traceCsrRmaskReg.foreach(_ := BigInt("ffffffff", 16).U(parameter.xlen))
        traceCsrWmaskReg.foreach(_ := BigInt("ffffffff", 16).U(parameter.xlen))
        traceCsrRdataReg.foreach(_ := csrMcause)
        traceCsrWdataReg.foreach(_ := 7.U(parameter.xlen))
        trapEventReg := true.B
        traceTrapReg.foreach(_ := true.B)
        traceTrapCauseReg.foreach(_ := TrapCause.AXI_ERROR.U(4))
      }

      when(loadResponseOk) {
        instrReg := memInstrReg
        fetched  := true.B
        pc       := memNextPcReg
        state    := CoreState.RUN.U(3)
        traceValidReg.foreach(_ := true.B)
        tracePcReg.foreach(_ := memPcReg)
        traceNextPcReg.foreach(_ := memNextPcReg)
        traceInstrReg.foreach(_ := memInstrReg)
        traceLenReg.foreach(_ := memLenReg)
        traceRdWeReg.foreach(_ := memRdReg =/= 0.U(5))
        traceRdReg.foreach(_ := memRdReg.asBits.bits(3, 0).asUInt)
        traceRdWdataReg.foreach(_ := (memRdReg =/= 0.U(5)).?(loadWdata, 0.U(parameter.xlen)))
        memTraceRs1AddrReg.foreach(mem => traceRs1AddrReg.foreach(_ := mem))
        memTraceRs1RdataReg.foreach(mem => traceRs1RdataReg.foreach(_ := mem))
        memTraceRs2AddrReg.foreach(mem => traceRs2AddrReg.foreach(_ := mem))
        memTraceRs2RdataReg.foreach(mem => traceRs2RdataReg.foreach(_ := mem))
        traceMemAddrReg.foreach(_ := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt)
        traceMemRmaskReg.foreach(_ := loadMemMask)
        traceMemWmaskReg.foreach(_ := 0.U(4))
        traceMemRdataReg.foreach(_ := io.axi_rdata)
        traceMemWdataReg.foreach(_ := 0.U(parameter.xlen))
        traceTrapReg.foreach(_ := false.B)
        traceTrapCauseReg.foreach(_ := 0.U(4))

        writeGpr(memRdReg =/= 0.U(5), memRdReg, loadWdata, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15)

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
        traceValidReg.foreach(_ := true.B)
        tracePcReg.foreach(_ := memPcReg)
        traceNextPcReg.foreach(_ := memNextPcReg)
        traceInstrReg.foreach(_ := memInstrReg)
        traceLenReg.foreach(_ := memLenReg)
        traceRdWeReg.foreach(_ := false.B)
        traceRdReg.foreach(_ := 0.U(parameter.registerIndexBits))
        traceRdWdataReg.foreach(_ := 0.U(parameter.xlen))
        memTraceRs1AddrReg.foreach(mem => traceRs1AddrReg.foreach(_ := mem))
        memTraceRs1RdataReg.foreach(mem => traceRs1RdataReg.foreach(_ := mem))
        memTraceRs2AddrReg.foreach(mem => traceRs2AddrReg.foreach(_ := mem))
        memTraceRs2RdataReg.foreach(mem => traceRs2RdataReg.foreach(_ := mem))
        traceMemAddrReg.foreach(_ := (memAddrReg.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt)
        traceMemRmaskReg.foreach(_ := 0.U(4))
        traceMemWmaskReg.foreach(_ := memStoreBeReg)
        traceMemRdataReg.foreach(_ := 0.U(parameter.xlen))
        traceMemWdataReg.foreach(_ := memStoreDataReg)
        traceTrapReg.foreach(_ := false.B)
        traceTrapCauseReg.foreach(_ := 0.U(4))

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
            traceValidReg.foreach(_ := true.B)
            tracePcReg.foreach(_ := pc)
            traceNextPcReg.foreach(_ := execNextPc)
            traceInstrReg.foreach(_ := straddledInstr)
            traceLenReg.foreach(_ := 4.U(3))
          }
        }
      }.otherwise {
        when(stateRun & instrReady) {
          when(straddled32) {
            straddleLowHalfword := instrRdata.asBits.bits(31, 16).asUInt
            state := CoreState.STRADDLE.U(3)
          }.otherwise {
            instrReg := instrRdata
            fetched  := true.B
            when(!execWaitsForMem) {
              pc       := execNextPc
              traceValidReg.foreach(_ := true.B)
              tracePcReg.foreach(_ := pc)
              traceNextPcReg.foreach(_ := execNextPc)
              traceInstrReg.foreach(_ := selectedInstr)
              traceLenReg.foreach(_ := instrCompressed.?(2.U(3), 4.U(3)))
            }
          }
        }
      }

      when(commitNow & execWaitsForMem) {
        memPcReg        := pc
        memInstrReg     := commitInstr
        memLenReg       := commitLen
        memNextPcReg    := sequentialPc
        memAddrReg      := memAddr
        memRdReg        := rdIndex
        memFunct3Reg    := funct3
        memStoreDataReg := storeData
        memStoreBeReg   := storeBe
        memTraceRs1AddrReg.foreach(_ := execUsesRs1.?(rs1Index, 0.U(5)))
        memTraceRs1RdataReg.foreach(_ := execUsesRs1.?(rs1Data, 0.U(parameter.xlen)))
        memTraceRs2AddrReg.foreach(_ := execUsesRs2.?(rs2Index, 0.U(5)))
        memTraceRs2RdataReg.foreach(_ := execUsesRs2.?(rs2Data, 0.U(parameter.xlen)))
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

      when(commitNow & !execWaitsForMem) {
        trapEventReg := execTrap
        traceTrapReg.foreach(_ := execTrap)
        traceTrapCauseReg.foreach(_ := execTrapCause)
        traceRdWeReg.foreach(_ := execWriteRd)
        traceRdReg.foreach(_ := rdIndex.asBits.bits(3, 0).asUInt)
        traceRdWdataReg.foreach(_ := execWriteRd.?(execWdata, 0.U(parameter.xlen)))
        traceRs1AddrReg.foreach(_ := (execUsesRs1 & !execTrap).?(rs1Index, 0.U(5)))
        traceRs1RdataReg.foreach(_ := (execUsesRs1 & !execTrap).?(rs1Data, 0.U(parameter.xlen)))
        traceRs2AddrReg.foreach(_ := (execUsesRs2 & !execTrap).?(rs2Index, 0.U(5)))
        traceRs2RdataReg.foreach(_ := (execUsesRs2 & !execTrap).?(rs2Data, 0.U(parameter.xlen)))
        traceNextPcReg.foreach(_ := execTrap.?(trapVector, execNextPc))
        when(isCsr & !execTrap) {
          traceCsrAddrReg.foreach(_ := csrAddr)
          traceCsrRmaskReg.foreach(_ := BigInt("ffffffff", 16).U(parameter.xlen))
          traceCsrRdataReg.foreach(_ := csrReadData)
          when(csrWriteEnable) {
            traceCsrWmaskReg.foreach(_ := BigInt("ffffffff", 16).U(parameter.xlen))
            traceCsrWdataReg.foreach(_ := csrTraceWriteData)
          }
        }

        writeGpr(execWriteRd, rdIndex, execWdata, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10, x11, x12, x13, x14, x15)

        when(isCsr & csrWriteEnable & !execTrap) {
          when(csrAddr === CsrAddr.MSTATUS.U(12)) {
            csrMstatus := writableMstatus(csrWriteData)
          }
          when(csrAddr === CsrAddr.MIE.U(12)) {
            csrMie := (csrWriteData.asBits & 0x888.U(parameter.xlen).asBits).bits(parameter.xlen - 1, 0).asUInt
          }
          when(csrAddr === CsrAddr.MTVEC.U(12)) {
            csrMtvec := (csrWriteData.asBits.bits(parameter.xlen - 1, 2) ## 0.U(2).asBits).asUInt
          }
          when(csrAddr === CsrAddr.MSCRATCH.U(12)) {
            csrMscratch := csrWriteData
          }
          when(csrAddr === CsrAddr.MEPC.U(12)) {
            csrMepc := (csrWriteData.asBits.bits(parameter.xlen - 1, 1) ## 0.U(1).asBits).asUInt
          }
          when(csrAddr === CsrAddr.MCAUSE.U(12)) {
            csrMcause := csrWriteData
          }
          when(csrAddr === CsrAddr.MTVAL.U(12)) {
            csrMtval := csrWriteData
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
