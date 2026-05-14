/* SPDX-License-Identifier: MIT */

.section .text.start
.globl _start
_start:
    .option push
    .option norelax
    la sp, __stack_top
    .option pop

    la a0, __bss_start
    la a1, __bss_end
1:
    bgeu a0, a1, 2f
    sw zero, 0(a0)
    addi a0, a0, 4
    j 1b

2:
    call ditdah32_main
    la a1, ditdah32_bench_result
    lw a2, 0(a1)
    li a3, 0xdd32beef
    beq a2, a3, 3f
    sw a3, 0(a1)
    sw zero, 4(a1)
    sw a0, 8(a1)
3:
    ebreak
4:
    j 4b
