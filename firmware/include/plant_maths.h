/*
 * The elementary functions the plant model's equations are built from.
 *
 * The model needs three: the exponential, the exponential less one, and the
 * sine. They are written here rather than taken from the host's maths library
 * because that library is not one thing. Apple's, glibc's and the board
 * toolchain's each round the last bit of these functions differently, and a
 * model whose results differ in the last bit between hosts cannot have a
 * trajectory recorded on one host and compared on another -- which is the whole
 * of what a recorded trajectory is for.
 *
 * These are built from the operations IEEE 754 fixes the result of -- addition,
 * subtraction, multiplication, division and the conversion between float and
 * integer -- and from nothing else, so that on a build which does not fuse a
 * multiply with an add they return the same bits on every host and on the
 * target. Fusing is turned off in every build that compiles them. Square root
 * and absolute value are also exact everywhere and stay what they are.
 *
 * Accuracy, against the same function evaluated in double precision, over the
 * stated domain. The bounds hold at every argument the tests sample, a dense
 * scan of each domain, and the series' truncation is below them by construction:
 *
 *   plant_expf     relative error no greater than 1.2e-7 (about one ulp)
 *   plant_expm1f   relative error no greater than 1.2e-7 on [-0.5, 0.5], where
 *                  it matters that a small result keeps its leading digits, and
 *                  no greater than 2.0e-7 elsewhere, where the result is the
 *                  exponential less one and one cancelled bit is lost
 *   plant_sinf     absolute error no greater than 1.2e-7 on |x| <= 6000
 *
 * The bounds are checked by a test sampling the domain, which is the only reason
 * to believe them; they are not proved for every float.
 */
#ifndef PLANT_MATHS_H
#define PLANT_MATHS_H

/*
 * e raised to x. Domain: -87 <= x <= 88, which is every argument the plant
 * passes; it only ever passes the exponent of a decay. The two edges are
 * conservative, chosen so the power of two the result is scaled by stays a
 * normal float; they are not where the range ends. The true result is a normal
 * float down to about -87.34 and finite up to about 88.72. Outside the edges the
 * result saturates: below -87 it is zero, though the true value there, at most
 * 1.6e-38, is still representable down to -87.34, and above 88 it is the largest
 * finite float. That step, from about 1.65e38 at 88 to the largest float just
 * above it, is a deliberate saturation and not an approximation of the true
 * value. Infinity saturates the same way and NaN returns NaN.
 */
float plant_expf(float x);

/*
 * e raised to x, less one, with the leading digits of the answer kept however
 * small it is. Domain and saturation as plant_expf above, so for x above 88 the
 * result is the largest finite float less one, which is that float, and for x
 * below -87 it is minus one. The result for minus infinity is minus one.
 */
float plant_expm1f(float x);

/*
 * The sine of x in radians. Domain: |x| <= 6000, which is nearly a thousand
 * turns. Beyond the domain the result is zero, the sine's mean, rather than a
 * number whose leading digits the argument reduction could no longer vouch for.
 * NaN returns NaN. The sine of either zero is plus zero.
 *
 * The plant's only argument is the turn of its coupled pair over a step, and a
 * turn reaches a result only multiplied by plant_expf of minus the pair's decay
 * over the same step, which is exactly zero once that decay exceeds 87. The turn
 * is at most 2 * sqrt(c * V / M) times the decay, where c is the heat capacity
 * of water per millilitre, V the volume held between the casting and the group
 * and M the casting's thermal mass: the rate the water pulls on the casting over
 * the rate it approaches it is at most c * V / M, and the decay is at least half
 * the approach rate times the step. At the worst corner of the declared errors
 * of the shipped description, c * V / M = (4.15 * 1.03) * (4.0 * 1.6) /
 * (320 * 0.6) = 0.142, so the turn is at most 0.75 times the decay and no more
 * than 66 radians wherever the decay is 87 or less, against a domain of 6000.
 * A step long enough to carry the turn past the domain has a decay far past 87,
 * where the sine is zero and so is the factor it multiplies. The sine's
 * divisor, the turn itself, is a square root of a positive number there.
 */
float plant_sinf(float x);

#endif
