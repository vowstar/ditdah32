// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT

module ditdah32_jtag_dtm_top (
    input         tck,
    input         reset,
    input         tms,
    input         tdi,
    input         trstN,
    output        tdo,
    output        requestToggle,
    output [6:0]  requestAddr,
    output [31:0] requestData,
    output [1:0]  requestOp,
    input         responseToggle,
    input  [6:0]  responseAddr,
    input  [31:0] responseData,
    input  [1:0]  responseOp,
    output [3:0]  probeState,
    output [4:0]  probeIr,
    output [4:0]  probeIrShift,
    output [40:0] probeDrShift,
    output        probeOutstanding,
    output [1:0]  probeStickyStatus
);
    DitDah32JtagDtm dut (
        .tck(tck),
        .reset(reset),
        .tms(tms),
        .tdi(tdi),
        .trstN(trstN),
        .tdo(tdo),
        .requestToggle(requestToggle),
        .requestAddr(requestAddr),
        .requestData(requestData),
        .requestOp(requestOp),
        .responseToggle(responseToggle),
        .responseAddr(responseAddr),
        .responseData(responseData),
        .responseOp(responseOp)
    );

    assign probeState = dut.state;
    assign probeIr = dut.ir;
    assign probeIrShift = dut.irShift;
    assign probeDrShift = dut.drShift;
    assign probeOutstanding = dut.outstanding;
    assign probeStickyStatus = dut.stickyStatus;
endmodule

module ditdah32_debug_module_top (
    input         clock,
    input         reset,
    input         requestToggle,
    input  [6:0]  requestAddr,
    input  [31:0] requestData,
    input  [1:0]  requestOp,
    output        responseToggle,
    output [6:0]  responseAddr,
    output [31:0] responseData,
    output [1:0]  responseOp,
    output        haltReq,
    output        resumeReq,
    output        resetReq,
    output        haltOnResetReq,
    input         hartHalted,
    input         hartRunning,
    input         hartResumeAck,
    input         hartResetAck,
    output        abstractValid,
    output [1:0]  abstractCmdType,
    output        abstractWrite,
    output [15:0] abstractRegno,
    output [2:0]  abstractSize,
    output [31:0] abstractData,
    output [31:0] abstractAddress,
    input         abstractDone,
    input  [2:0]  abstractError,
    input  [31:0] abstractRdata,
    output        probeRequestToggleSync,
    output        probeRequestToggleSeen,
    output        probeDmactive,
    output        probeAbstractBusy,
    output [2:0]  probeCommandError
);
    DitDah32DebugModule dut (
        .clock(clock),
        .reset(reset),
        .requestToggle(requestToggle),
        .requestAddr(requestAddr),
        .requestData(requestData),
        .requestOp(requestOp),
        .responseToggle(responseToggle),
        .responseAddr(responseAddr),
        .responseData(responseData),
        .responseOp(responseOp),
        .haltReq(haltReq),
        .resumeReq(resumeReq),
        .resetReq(resetReq),
        .haltOnResetReq(haltOnResetReq),
        .hartHalted(hartHalted),
        .hartRunning(hartRunning),
        .hartResumeAck(hartResumeAck),
        .hartResetAck(hartResetAck),
        .abstractValid(abstractValid),
        .abstractCmdType(abstractCmdType),
        .abstractWrite(abstractWrite),
        .abstractRegno(abstractRegno),
        .abstractSize(abstractSize),
        .abstractData(abstractData),
        .abstractAddress(abstractAddress),
        .abstractDone(abstractDone),
        .abstractError(abstractError),
        .abstractRdata(abstractRdata)
    );

    assign probeRequestToggleSync = dut.requestToggleSync;
    assign probeRequestToggleSeen = dut.requestToggleSeen;
    assign probeDmactive = dut.dmactive;
    assign probeAbstractBusy = dut.abstractBusy;
    assign probeCommandError = dut.commandError;
endmodule
