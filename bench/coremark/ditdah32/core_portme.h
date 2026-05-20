// SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com>
// SPDX-License-Identifier: MIT
#ifndef CORE_PORTME_H
#define CORE_PORTME_H

#include "bench_result.h"

#define HAS_FLOAT 0
#define HAS_TIME_H 0
#define USE_CLOCK 0
#define HAS_STDIO 0
#define HAS_PRINTF 0
#define MAIN_HAS_NOARGC 1
#define MAIN_HAS_NORETURN 0
#define SEED_METHOD SEED_FUNC
#define MEM_METHOD MEM_STATIC
#define MULTITHREAD 1
#define CORE_DEBUG 0

#define COMPILER_VERSION "riscv32-none-elf-gcc"
#define COMPILER_FLAGS "-march=rv32ec -mabi=ilp32e -Os -ffreestanding -nostdlib"
#define MEM_LOCATION "DitDah32 static RAM"

#define ee_printf coremark_printf

typedef signed short ee_s16;
typedef unsigned short ee_u16;
typedef signed int ee_s32;
typedef unsigned int ee_u32;
typedef unsigned char ee_u8;
typedef int ee_f32;
typedef unsigned int ee_size_t;
typedef unsigned int ee_ptr_int;
typedef unsigned int CORE_TICKS;

#define CORETIMETYPE ee_u32
#define NULL ((void *)0)
#define align_mem(x) (void *)(4 + (((ee_ptr_int)(x)-1) & ~3))

typedef struct core_portable_s {
    unsigned int dummy;
} core_portable;

extern ee_u32 default_num_contexts;

void portable_init(core_portable *p, int *argc, char *argv[]);
void portable_fini(core_portable *p);
int coremark_printf(const char *fmt, ...);
ee_s32 portme_sys1(void);
ee_s32 portme_sys2(void);
ee_s32 portme_sys3(void);
ee_s32 portme_sys4(void);
ee_s32 portme_sys5(void);

#endif
