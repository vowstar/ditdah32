// SPDX-License-Identifier: MIT
#include <stdarg.h>

#include "bench_result.h"

#ifndef DITDAH32_DHRYSTONE_RUNS
#define DITDAH32_DHRYSTONE_RUNS 1
#endif

extern unsigned int __heap_start;
extern unsigned int __heap_end;

volatile struct ditdah32_bench_result ditdah32_bench_result
    __attribute__((section(".bench_result")));
volatile unsigned int ditdah32_bench_timing_state
    __attribute__((section(".bench_timing")));

static unsigned char *heap_next;
static unsigned int bench_time_call_count;

static int starts_with(const char *text, const char *prefix)
{
    while (*prefix) {
        if (*text++ != *prefix++) {
            return 0;
        }
    }
    return 1;
}

void bench_report(
    unsigned int benchmark_id,
    unsigned int status,
    unsigned int value0,
    unsigned int value1,
    unsigned int value2,
    unsigned int value3)
{
    ditdah32_bench_result.magic = DITDAH32_BENCH_MAGIC;
    ditdah32_bench_result.benchmark_id = benchmark_id;
    ditdah32_bench_result.status = status;
    ditdah32_bench_result.value0 = value0;
    ditdah32_bench_result.value1 = value1;
    ditdah32_bench_result.value2 = value2;
    ditdah32_bench_result.value3 = value3;
}

void bench_timing_start(void)
{
    ditdah32_bench_timing_state = DITDAH32_BENCH_TIMING_START;
}

void bench_timing_stop(void)
{
    ditdah32_bench_timing_state = DITDAH32_BENCH_TIMING_STOP;
}

void *bench_malloc(unsigned int size)
{
    unsigned int aligned_size = (size + 3u) & ~3u;
    unsigned char *result;

    if (heap_next == 0) {
        heap_next = (unsigned char *)&__heap_start;
    }

    result = heap_next;
    if (result + aligned_size > (unsigned char *)&__heap_end) {
        return 0;
    }

    heap_next = result + aligned_size;
    return result;
}

int bench_printf(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    va_end(args);

    if (starts_with(fmt, "ERROR!") || starts_with(fmt, "Errors detected")
        || starts_with(fmt, "Cannot validate operation")) {
        ditdah32_bench_result.value3 = 1u;
    }
    if (starts_with(fmt, "Correct operation validated")) {
        ditdah32_bench_result.value2 = 1u;
    }

    return 0;
}

int bench_scanf(const char *fmt, ...)
{
    va_list args;
    int *value;

    (void)fmt;
    va_start(args, fmt);
    value = va_arg(args, int *);
    va_end(args);
    if (value) {
        *value = DITDAH32_DHRYSTONE_RUNS;
    }
    return 1;
}

long bench_time(long *value)
{
    if (bench_time_call_count == 0u) {
        bench_timing_start();
    } else {
        bench_timing_stop();
    }
    bench_time_call_count++;

    if (value) {
        *value = 0;
    }
    return 0;
}

void *memcpy(void *dst, const void *src, unsigned int size)
{
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    while (size--) {
        *d++ = *s++;
    }
    return dst;
}

void *memmove(void *dst, const void *src, unsigned int size)
{
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;

    if (d < s) {
        while (size--) {
            *d++ = *s++;
        }
    } else {
        d += size;
        s += size;
        while (size--) {
            *--d = *--s;
        }
    }

    return dst;
}

void *memset(void *dst, int value, unsigned int size)
{
    unsigned char *d = (unsigned char *)dst;
    while (size--) {
        *d++ = (unsigned char)value;
    }
    return dst;
}

char *strcpy(char *dst, const char *src)
{
    char *result = dst;
    while ((*dst++ = *src++) != 0) {
    }
    return result;
}

int strcmp(const char *left, const char *right)
{
    while (*left && *left == *right) {
        left++;
        right++;
    }
    return (unsigned char)*left - (unsigned char)*right;
}

unsigned int strlen(const char *text)
{
    const char *start = text;
    while (*text) {
        text++;
    }
    return (unsigned int)(text - start);
}

int puts(const char *text)
{
    (void)text;
    return 0;
}

void exit(int status)
{
    bench_report(0u, (unsigned int)status, 0u, 0u, 0u, 0u);
    __asm__ volatile("ebreak");
    while (1) {
    }
}
