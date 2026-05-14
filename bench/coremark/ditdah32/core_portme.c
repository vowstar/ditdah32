// SPDX-License-Identifier: MIT
#include <stdarg.h>

#include "coremark.h"
#include "bench_result.h"

static CORE_TICKS elapsed_ticks;
ee_u32 default_num_contexts = 1;

void portable_init(core_portable *p, int *argc, char *argv[])
{
    (void)p;
    (void)argc;
    (void)argv;
    ditdah32_bench_result.magic = 0u;
    ditdah32_bench_result.value2 = 0u;
    ditdah32_bench_result.value3 = 0u;
}

void portable_fini(core_portable *p)
{
    (void)p;
    bench_report(
        DITDAH32_BENCH_COREMARK,
        (ditdah32_bench_result.value2 == 1u && ditdah32_bench_result.value3 == 0u) ? 0u : 1u,
        DITDAH32_COREMARK_ITERATIONS,
        elapsed_ticks,
        ditdah32_bench_result.value2,
        ditdah32_bench_result.value3);
}

ee_s32 portme_sys1(void)
{
    return DITDAH32_COREMARK_SEED1;
}

ee_s32 portme_sys2(void)
{
    return DITDAH32_COREMARK_SEED2;
}

ee_s32 portme_sys3(void)
{
    return DITDAH32_COREMARK_SEED3;
}

ee_s32 portme_sys4(void)
{
    return DITDAH32_COREMARK_ITERATIONS;
}

ee_s32 portme_sys5(void)
{
    return 0;
}

void start_time(void)
{
    elapsed_ticks = 0;
    bench_timing_start();
}

void stop_time(void)
{
    bench_timing_stop();
    elapsed_ticks = 10;
}

CORE_TICKS get_time(void)
{
    return elapsed_ticks;
}

secs_ret time_in_secs(CORE_TICKS ticks)
{
    return ticks;
}

void *portable_malloc(ee_size_t size)
{
    return bench_malloc(size);
}

void portable_free(void *p)
{
    (void)p;
}

int coremark_printf(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    va_end(args);
    return bench_printf(fmt);
}
