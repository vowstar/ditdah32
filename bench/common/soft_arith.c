// SPDX-License-Identifier: MIT

static unsigned int udivmod32(unsigned int dividend, unsigned int divisor, unsigned int *remainder)
{
    unsigned int quotient = 0;
    unsigned int partial = 0;
    int bit;

    if (divisor == 0) {
        if (remainder) {
            *remainder = dividend;
        }
        return 0xffffffffu;
    }

    for (bit = 31; bit >= 0; bit--) {
        partial = (partial << 1) | ((dividend >> bit) & 1u);
        if (partial >= divisor) {
            partial -= divisor;
            quotient |= 1u << bit;
        }
    }

    if (remainder) {
        *remainder = partial;
    }
    return quotient;
}

unsigned int __mulsi3(unsigned int left, unsigned int right)
{
    unsigned int result = 0;

    while (right) {
        if (right & 1u) {
            result += left;
        }
        left <<= 1;
        right >>= 1;
    }

    return result;
}

unsigned int __udivsi3(unsigned int dividend, unsigned int divisor)
{
    return udivmod32(dividend, divisor, 0);
}

unsigned int __umodsi3(unsigned int dividend, unsigned int divisor)
{
    unsigned int remainder;
    (void)udivmod32(dividend, divisor, &remainder);
    return remainder;
}

int __divsi3(int dividend, int divisor)
{
    unsigned int negative = 0;
    unsigned int udividend;
    unsigned int udivisor;
    unsigned int quotient;

    if (dividend < 0) {
        negative ^= 1u;
        udividend = (unsigned int)(-dividend);
    } else {
        udividend = (unsigned int)dividend;
    }

    if (divisor < 0) {
        negative ^= 1u;
        udivisor = (unsigned int)(-divisor);
    } else {
        udivisor = (unsigned int)divisor;
    }

    quotient = udivmod32(udividend, udivisor, 0);
    return negative ? -(int)quotient : (int)quotient;
}

int __modsi3(int dividend, int divisor)
{
    unsigned int negative = 0;
    unsigned int udividend;
    unsigned int udivisor;
    unsigned int remainder;

    if (dividend < 0) {
        negative = 1u;
        udividend = (unsigned int)(-dividend);
    } else {
        udividend = (unsigned int)dividend;
    }

    if (divisor < 0) {
        udivisor = (unsigned int)(-divisor);
    } else {
        udivisor = (unsigned int)divisor;
    }

    (void)udivmod32(udividend, udivisor, &remainder);
    return negative ? -(int)remainder : (int)remainder;
}

double __floatsidf(int value)
{
    (void)value;
    return 0.0;
}

double __muldf3(double left, double right)
{
    (void)left;
    (void)right;
    return 0.0;
}

double __divdf3(double left, double right)
{
    (void)left;
    (void)right;
    return 0.0;
}

int __fixdfsi(double value)
{
    (void)value;
    return 0;
}
