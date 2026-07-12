// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT

module DitDah32JtagDtmFormal;
    reg tck = 1'b0;
    always #1 tck = !tck;

    reg reset = 1'b1;
    always @(posedge tck) begin
        reset <= 1'b0;
    end

    (* anyseq *) reg        tms;
    (* anyseq *) reg        tdi;
    (* anyseq *) reg        trstN;
    (* anyseq *) reg        responseToggle;
    (* anyseq *) reg [6:0]  responseAddr;
    (* anyseq *) reg [31:0] responseData;
    (* anyseq *) reg [1:0]  responseOp;

    wire        tdo;
    wire        requestToggle;
    wire [6:0]  requestAddr;
    wire [31:0] requestData;
    wire [1:0]  requestOp;
    wire [3:0]  probeState;
    wire [4:0]  probeIr;
    wire [4:0]  probeIrShift;
    wire [40:0] probeDrShift;
    wire        probeOutstanding;
    wire [1:0]  probeStickyStatus;

    ditdah32_jtag_dtm_top dut (
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
        .responseOp(responseOp),
        .probeState(probeState),
        .probeIr(probeIr),
        .probeIrShift(probeIrShift),
        .probeDrShift(probeDrShift),
        .probeOutstanding(probeOutstanding),
        .probeStickyStatus(probeStickyStatus)
    );

    function automatic [3:0] tap_next;
        input [3:0] state;
        input       next_tms;
        begin
            case (state)
                4'h0: tap_next = next_tms ? 4'h0 : 4'h1;
                4'h1: tap_next = next_tms ? 4'h2 : 4'h1;
                4'h2: tap_next = next_tms ? 4'h9 : 4'h3;
                4'h3: tap_next = next_tms ? 4'h5 : 4'h4;
                4'h4: tap_next = next_tms ? 4'h5 : 4'h4;
                4'h5: tap_next = next_tms ? 4'h8 : 4'h6;
                4'h6: tap_next = next_tms ? 4'h7 : 4'h6;
                4'h7: tap_next = next_tms ? 4'h8 : 4'h4;
                4'h8: tap_next = next_tms ? 4'h2 : 4'h1;
                4'h9: tap_next = next_tms ? 4'h0 : 4'hA;
                4'hA: tap_next = next_tms ? 4'hC : 4'hB;
                4'hB: tap_next = next_tms ? 4'hC : 4'hB;
                4'hC: tap_next = next_tms ? 4'hF : 4'hD;
                4'hD: tap_next = next_tms ? 4'hE : 4'hD;
                4'hE: tap_next = next_tms ? 4'hF : 4'hB;
                default: tap_next = next_tms ? 4'h2 : 4'h1;
            endcase
        end
    endfunction

    reg       f_past_valid = 1'b0;
    reg [2:0] tms_high_count = 3'd0;

    always @(posedge tck) begin
        f_past_valid <= 1'b1;
        if (reset || !trstN || !tms) begin
            tms_high_count <= 3'd0;
        end else if (tms_high_count < 3'd5) begin
            tms_high_count <= tms_high_count + 3'd1;
        end

        if (f_past_valid && !$past(reset)) begin
            if (responseToggle == $past(responseToggle)) begin
                assume(responseAddr == $past(responseAddr));
                assume(responseData == $past(responseData));
                assume(responseOp == $past(responseOp));
            end

            if ($past(trstN)) begin
                assert(probeState == tap_next($past(probeState), $past(tms)));
            end else begin
                assert(probeState == 4'h0);
                assert(probeIr == 5'h01);
                assert(!probeOutstanding);
                assert(probeStickyStatus == 2'h0);
            end

            if ($past(trstN && probeState == 4'h0)) begin
                assert(probeIr == 5'h01);
                assert(!probeOutstanding);
                assert(requestOp == 2'h0);
                assert(probeStickyStatus == 2'h0);
            end
            if ($past(trstN && probeState == 4'hA)) begin
                assert(probeIrShift == 5'h01);
            end
            if ($past(trstN && probeState == 4'h3 && probeIr == 5'h01)) begin
                assert(probeDrShift == 41'h1);
            end
            if ($past(trstN && probeState == 4'h3 && probeIr == 5'h10)) begin
                assert((probeDrShift[31:0] & 32'hFFFF_F3FF) == 32'h0000_7071);
                assert(probeDrShift[11:10] == $past(probeStickyStatus));
                assert(probeDrShift[40:32] == 9'h0);
            end

            if (requestToggle == $past(requestToggle)) begin
                if ($past(trstN && probeState != 4'h0)) begin
                    assert(requestAddr == $past(requestAddr));
                    assert(requestData == $past(requestData));
                    assert(requestOp == $past(requestOp));
                end
            end else begin
                assert($past(trstN));
                assert($past(probeState) == 4'h8);
                assert($past(probeIr) == 5'h11);
                assert($past(probeStickyStatus) == 2'h0);
                assert(!$past(probeOutstanding));
                assert($past(probeDrShift[1:0]) == 2'h1 ||
                       $past(probeDrShift[1:0]) == 2'h2);
            end
        end

        if (!reset) begin
            assert(probeStickyStatus == 2'h0 ||
                   probeStickyStatus == 2'h2 ||
                   probeStickyStatus == 2'h3);
            if (probeOutstanding) begin
                assert(requestOp == 2'h1 || requestOp == 2'h2);
            end
            if (tms_high_count == 3'd5) begin
                assert(probeState == 4'h0);
            end
            if (probeState == 4'hB) begin
                assert(tdo == probeIrShift[0]);
            end
            if (probeState == 4'h4) begin
                assert(tdo == probeDrShift[0]);
            end
        end
    end
endmodule

module DitDah32DebugModuleFormal;
    reg clock = 1'b0;
    always #1 clock = !clock;

    reg reset = 1'b1;
    always @(posedge clock) begin
        reset <= 1'b0;
    end

    (* anyseq *) reg        requestToggle;
    (* anyseq *) reg [6:0]  requestAddr;
    (* anyseq *) reg [31:0] requestData;
    (* anyseq *) reg [1:0]  requestOp;
    (* anyseq *) reg        hartHalted;
    (* anyseq *) reg        hartRunning;
    (* anyseq *) reg        hartResumeAck;
    (* anyseq *) reg        hartResetAck;
    (* anyseq *) reg        abstractDone;
    (* anyseq *) reg [2:0]  abstractError;
    (* anyseq *) reg [31:0] abstractRdata;

    wire        responseToggle;
    wire [6:0]  responseAddr;
    wire [31:0] responseData;
    wire [1:0]  responseOp;
    wire        haltReq;
    wire        resumeReq;
    wire        resetReq;
    wire        haltOnResetReq;
    wire        abstractValid;
    wire [1:0]  abstractCmdType;
    wire        abstractWrite;
    wire [15:0] abstractRegno;
    wire [2:0]  abstractSize;
    wire [31:0] abstractData;
    wire [31:0] abstractAddress;
    wire        probeRequestToggleSync;
    wire        probeRequestToggleSeen;
    wire        probeDmactive;
    wire        probeAbstractBusy;
    wire [2:0]  probeCommandError;

    ditdah32_debug_module_top dut (
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
        .abstractRdata(abstractRdata),
        .probeRequestToggleSync(probeRequestToggleSync),
        .probeRequestToggleSeen(probeRequestToggleSeen),
        .probeDmactive(probeDmactive),
        .probeAbstractBusy(probeAbstractBusy),
        .probeCommandError(probeCommandError)
    );

    reg f_past_valid = 1'b0;
    reg request_in_flight = 1'b0;

    always @(posedge clock) begin
        f_past_valid <= 1'b1;

        if (reset) begin
            request_in_flight <= 1'b0;
        end else begin
            if (f_past_valid && requestToggle != $past(requestToggle)) begin
                assume(!request_in_flight);
                assume(requestOp == 2'h1 || requestOp == 2'h2);
                request_in_flight <= 1'b1;
            end
            if (f_past_valid && responseToggle != $past(responseToggle)) begin
                request_in_flight <= 1'b0;
            end
        end

        assume(!(hartHalted && hartRunning));
        assume(!abstractDone || probeAbstractBusy);

        if (f_past_valid && !$past(reset)) begin
            if (requestToggle == $past(requestToggle)) begin
                assume(requestAddr == $past(requestAddr));
                assume(requestData == $past(requestData));
                assume(requestOp == $past(requestOp));
            end

            assert((responseToggle != $past(responseToggle)) ==
                   ($past(probeRequestToggleSync) != $past(probeRequestToggleSeen)));
            if (responseToggle != $past(responseToggle)) begin
                assert(responseAddr == $past(requestAddr));
            end
            if ($past(probeAbstractBusy && abstractDone)) begin
                assert(!probeAbstractBusy);
            end
            assert(!(abstractValid && $past(abstractValid)));
            assert(!(resumeReq && $past(resumeReq)));
        end

        if (!reset) begin
            assert(responseOp == 2'h0);
            assert(probeCommandError != 3'h6);
            if (!probeDmactive) begin
                assert(!haltReq);
                assert(!resumeReq);
                assert(!resetReq);
                assert(!haltOnResetReq);
                assert(!abstractValid);
                assert(!probeAbstractBusy);
                assert(probeCommandError == 3'h0);
            end
            if (abstractValid) begin
                assert(probeDmactive);
                assert(hartHalted);
                assert(probeAbstractBusy);
                assert(abstractCmdType == 2'h0 || abstractCmdType == 2'h2);
                assert(abstractSize <= 3'h2);
            end
            if (resumeReq) begin
                assert(probeDmactive);
                assert(hartHalted);
            end
            if (haltReq || resetReq || haltOnResetReq) begin
                assert(probeDmactive);
            end
        end
    end
endmodule
