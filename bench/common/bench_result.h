// SPDX-License-Identifier: MIT
#ifndef DITDAH32_BENCH_RESULT_H
#define DITDAH32_BENCH_RESULT_H

enum {
    DITDAH32_BENCH_MAGIC = 0xdd32beefu,
    DITDAH32_BENCH_COREMARK = 1u,
    DITDAH32_BENCH_DHRYSTONE = 2u,
    DITDAH32_BENCH_TIMING_START = 0x53544152u,
    DITDAH32_BENCH_TIMING_STOP = 0x53544f50u,
};

struct ditdah32_bench_result {
    volatile unsigned int magic;
    volatile unsigned int benchmark_id;
    volatile unsigned int status;
    volatile unsigned int value0;
    volatile unsigned int value1;
    volatile unsigned int value2;
    volatile unsigned int value3;
};

extern volatile struct ditdah32_bench_result ditdah32_bench_result;
extern volatile unsigned int ditdah32_bench_timing_state;

void bench_report(
    unsigned int benchmark_id,
    unsigned int status,
    unsigned int value0,
    unsigned int value1,
    unsigned int value2,
    unsigned int value3);

void *bench_malloc(unsigned int size);
int bench_printf(const char *fmt, ...);
int bench_scanf(const char *fmt, ...);
long bench_time(long *value);
void bench_timing_start(void);
void bench_timing_stop(void);

#endif
