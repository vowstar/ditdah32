/* SPDX-FileCopyrightText: 2026 Huang Rui <vowstar@gmail.com> */
/* SPDX-License-Identifier: MIT */

ENTRY(_start)

MEMORY
{
    ram (rwx) : ORIGIN = 0x00000000, LENGTH = 256K
}

SECTIONS
{
    . = ORIGIN(ram);

    .text : ALIGN(4)
    {
        KEEP(*(.text.start))
        *(.text*)
        *(.rodata*)
    } > ram

    .data : ALIGN(4)
    {
        *(.sdata*)
        *(.data*)
    } > ram

    .bss (NOLOAD) : ALIGN(4)
    {
        __bss_start = .;
        *(.sbss*)
        *(.bss*)
        *(COMMON)
        __bss_end = .;
    } > ram

    .bench_result (NOLOAD) : ALIGN(4)
    {
        __bench_result_start = .;
        KEEP(*(.bench_result))
        __bench_result_end = .;
    } > ram

    .bench_timing (NOLOAD) : ALIGN(4)
    {
        __bench_timing_start = .;
        KEEP(*(.bench_timing))
        __bench_timing_end = .;
    } > ram

    .heap (NOLOAD) : ALIGN(4)
    {
        __heap_start = .;
        . += 0x4000;
        __heap_end = .;
    } > ram

    .stack (NOLOAD) : ALIGN(16)
    {
        . += 0x4000;
        __stack_top = .;
    } > ram

    __image_end = .;
}
