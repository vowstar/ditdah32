// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
#include "bench_result.h"
#include "../upstream/dhry.h"

int dhrystone_upstream_main(void);

extern Rec_Pointer Ptr_Glob;
extern Rec_Pointer Next_Ptr_Glob;
extern int Int_Glob;
extern Boolean Bool_Glob;
extern char Ch_1_Glob;
extern char Ch_2_Glob;
extern int Arr_1_Glob[50];
extern int Arr_2_Glob[50][50];

int ditdah32_main(void)
{
    unsigned int fail = 0;

    dhrystone_upstream_main();

    if (Int_Glob != 5) {
        fail |= 1u << 0;
    }
    if (Bool_Glob != 1) {
        fail |= 1u << 1;
    }
    if (Ch_1_Glob != 'A' || Ch_2_Glob != 'B') {
        fail |= 1u << 2;
    }
    if (Arr_1_Glob[8] != 7) {
        fail |= 1u << 3;
    }
    if (Arr_2_Glob[8][7] != DITDAH32_DHRYSTONE_RUNS + 10) {
        fail |= 1u << 4;
    }
    if (Ptr_Glob == 0 || Ptr_Glob->Discr != Ident_1
        || Ptr_Glob->variant.var_1.Enum_Comp != Ident_3
        || Ptr_Glob->variant.var_1.Int_Comp != 17) {
        fail |= 1u << 5;
    }
    if (Next_Ptr_Glob == 0 || Next_Ptr_Glob->Discr != Ident_1
        || Next_Ptr_Glob->variant.var_1.Enum_Comp != Ident_2
        || Next_Ptr_Glob->variant.var_1.Int_Comp != 18) {
        fail |= 1u << 6;
    }

    bench_report(
        DITDAH32_BENCH_DHRYSTONE,
        fail == 0 ? 0u : 1u,
        DITDAH32_DHRYSTONE_RUNS,
        (unsigned int)Arr_2_Glob[8][7],
        fail,
        0u);

    return fail == 0 ? 0 : 1;
}
