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
 * turns and far more than a step of the plant's pair of masses contains. Beyond
 * the domain the result is zero, the sine's mean, rather than a number whose
 * leading digits the argument reduction could no longer vouch for. NaN returns
 * NaN. The sine of either zero is plus zero.
 */
float plant_sinf(float x);

#endif
