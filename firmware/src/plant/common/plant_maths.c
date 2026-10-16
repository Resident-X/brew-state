/*
 * The elementary functions behind the plant model's equations.
 *
 * plant_maths.h says why they are here and what they promise. This file is how.
 * Every one is a range reduction to a short interval followed by a polynomial
 * whose coefficients are the Taylor series' own, taken far enough that the
 * truncation is below what a float can hold. Nothing is tuned to a table of
 * values: a reader can check each coefficient against the series it names.
 *
 * Every product and sum is written as a separate statement or a parenthesised
 * expression that no build may fuse. The builds that compile this file say so
 * (-ffp-contract=off); the arithmetic is only the same on every host because
 * they do.
 */
#include "plant_maths.h"

#include <float.h>
#include <stdint.h>
#include <string.h>

/* The inverse factorials the series are written with. */
#define INVERSE_FACTORIAL_3 (1.0f / 6.0f)
#define INVERSE_FACTORIAL_4 (1.0f / 24.0f)
#define INVERSE_FACTORIAL_5 (1.0f / 120.0f)
#define INVERSE_FACTORIAL_6 (1.0f / 720.0f)
#define INVERSE_FACTORIAL_7 (1.0f / 5040.0f)
#define INVERSE_FACTORIAL_8 (1.0f / 40320.0f)
#define INVERSE_FACTORIAL_9 (1.0f / 362880.0f)
#define INVERSE_FACTORIAL_10 (1.0f / 3628800.0f)

/* Conservative edges, inside the true cuts (about -87.34, 88.72); k stays in [-126, 127]. */
#define EXP_LOWEST_ARGUMENT (-87.0f)
#define EXP_HIGHEST_ARGUMENT 88.0f

/* The reduction of an exponential's argument to a multiple of ln 2 and a rest. */
#define LOG2_E 0x1.715476p+0f
#define LN2_HIGH 0x1.63p-1f
#define LN2_LOW (-0x1.bd0106p-13f)

/* The exponential less one is a series directly on this interval. */
#define EXPM1_SERIES_REACH 0.5f

/* The sine's reduction to a multiple of a quarter turn... */
#define SIN_HIGHEST_ARGUMENT 6000.0f
#define TWO_OVER_PI 0x1.45f306p-1f
/*
 * ...against a half pi held in three parts. The first two carry twelve bits
 * each, so that their product with a multiple below 4096 is exact, and the
 * third carries what is left to the precision of a float.
 */
#define HALF_PI_FIRST 0x1.92p+0f
#define HALF_PI_SECOND 0x1.fb4p-12f
#define HALF_PI_THIRD 0x1.4442d2p-24f

/*
 * e^r - 1 for |r| <= 0.5, as r + r^2/2 + r^3/6 + ... through r^8/8!. The first
 * term is kept apart from the rest so that a small r gives a result that is r
 * to the last digit and not r plus a rounding of something that was nearly one.
 */
static float expm1_series(float r)
{
    const float square = r * r;
    const float tail = r * (INVERSE_FACTORIAL_3 +
                            r * (INVERSE_FACTORIAL_4 +
                                 r * (INVERSE_FACTORIAL_5 +
                                      r * (INVERSE_FACTORIAL_6 +
                                           r * (INVERSE_FACTORIAL_7 + r * INVERSE_FACTORIAL_8)))));
    return r + square * (0.5f + tail);
}

float plant_expf(float x)
{
    if (x != x) {
        return x;
    }
    if (x < EXP_LOWEST_ARGUMENT) {
        return 0.0f;
    }
    if (x > EXP_HIGHEST_ARGUMENT) {
        return FLT_MAX;
    }

    /*
     * x = k ln 2 + r with |r| no more than half of ln 2, so that e^x is e^r
     * times two to the k. The multiple is the nearest whole number, found by
     * adding half in the direction of x and truncating, and ln 2 is held in two
     * parts for the same reason half pi is below.
     */
    const int k = (int)(x * LOG2_E + (x < 0.0f ? -0.5f : 0.5f));
    const float multiple = (float)k;
    const float r = (x - multiple * LN2_HIGH) - multiple * LN2_LOW;

    /*
     * Two to the k, built as the float whose exponent field is k and whose
     * fraction is zero. The lowest argument above keeps k at or above -126, the
     * smallest exponent a normal float has, and the highest keeps it at or below
     * 127, the largest.
     */
    const uint32_t exponent_field = (uint32_t)(k + 127) << 23;
    float scale;
    memcpy(&scale, &exponent_field, sizeof(scale));

    return (1.0f + expm1_series(r)) * scale;
}

float plant_expm1f(float x)
{
    if (x != x) {
        return x;
    }
    if (x >= -EXPM1_SERIES_REACH && x <= EXPM1_SERIES_REACH) {
        return expm1_series(x);
    }
    /*
     * Away from zero the exponential is at least a third away from one, so one
     * bit at most is lost to the subtraction, which the stated bound allows.
     */
    return plant_expf(x) - 1.0f;
}

/* sin r for |r| <= a quarter turn, as r - r^3/3! + r^5/5! - ... through r^9/9!. */
static float sine_series(float r)
{
    const float square = r * r;
    return r + r * square *
                   (-INVERSE_FACTORIAL_3 +
                    square * (INVERSE_FACTORIAL_5 +
                              square * (-INVERSE_FACTORIAL_7 + square * INVERSE_FACTORIAL_9)));
}

/* cos r for the same interval, as 1 - r^2/2! + r^4/4! - ... through r^10/10!. */
static float cosine_series(float r)
{
    const float square = r * r;
    return 1.0f +
           square * (-0.5f +
                     square * (INVERSE_FACTORIAL_4 +
                               square * (-INVERSE_FACTORIAL_6 +
                                         square * (INVERSE_FACTORIAL_8 -
                                                   square * INVERSE_FACTORIAL_10))));
}

float plant_sinf(float x)
{
    if (x != x) {
        return x;
    }

    const float magnitude = x < 0.0f ? -x : x;
    if (magnitude > SIN_HIGHEST_ARGUMENT) {
        return 0.0f;
    }

    /*
     * |x| = k (pi / 2) + r with |r| no more than a quarter turn. The sine is
     * then plus or minus the sine or the cosine of r according to which quarter
     * turn k lands in, and the sign of x is put back at the end.
     */
    const int quarters = (int)(magnitude * TWO_OVER_PI + 0.5f);
    const float multiple = (float)quarters;
    const float r = ((magnitude - multiple * HALF_PI_FIRST) - multiple * HALF_PI_SECOND) -
                    multiple * HALF_PI_THIRD;

    float value;
    switch (quarters & 3) {
    case 0:
        value = sine_series(r);
        break;
    case 1:
        value = cosine_series(r);
        break;
    case 2:
        value = -sine_series(r);
        break;
    default:
        value = -cosine_series(r);
        break;
    }
    return x < 0.0f ? -value : value;
}
