// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
package com.vowstar.ditdah32

import me.jiuyang.zaozi.*
import me.jiuyang.zaozi.default.{*, given}
import me.jiuyang.zaozi.reftpe.*
import me.jiuyang.zaozi.valuetpe.*
import org.llvm.mlir.scalalib.capi.ir.{Block, Context}

import java.lang.foreign.Arena

trait DitDah32Gpr:
  protected def readGpr(
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

  protected def writeGpr(
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
