/*
 * The vocabulary a parameter description records how wrong a value may be in.
 *
 * A description carries values, and every one of them is wrong by some amount
 * nobody has measured. That is not a defect in the description: the machine has
 * not been on the bench, and a figure taken from a diagram or estimated from
 * geometry is the best that can be had until it has. What is a defect is the
 * amount going unstated, because a design established against a description
 * then holds its margins against an uncertainty that exists only in the head of
 * whoever chose them -- and cannot be checked by anyone, including its author a
 * year later, or revisited when identification lands better or worse than the
 * figure it was sized for.
 *
 * So the assumed error travels with the value, in the description, beside the
 * origin of the same value. Both are facts about one number, and a number that
 * can be copied, edited or moved without them is a number that arrives
 * somewhere else with its provenance and its uncertainty stripped off. One
 * grammar carries both for that reason: a second artefact holding the errors
 * would be a second file to keep in step by hand, and the two would eventually
 * disagree about which value a figure belonged to.
 *
 * The error is a fraction of the value it stands against, not a quantity in
 * that value's own unit. A dimensionless fraction is what lets one figure be
 * read without knowing whether the coefficient beside it is a thermal mass in
 * joules per kelvin or a slope in bar per kelvin, and it is the form a margin
 * calculation wants: a coefficient that may be a fifth out is a fifth out
 * whether it is expressed in watts or in kilowatts. `0.25` against a value
 * therefore says the design assumes the machine's real figure lies within a
 * quarter of the one written down, either side of it.
 *
 * It is assumed rather than measured, and the distinction is the whole of what
 * this can claim. Nobody has established these figures on a machine; they are
 * judgements about how well each kind of coefficient is known, and the work
 * that measures them is characterisation, not this. What the description owes
 * is that the judgement is written down where the value is, so that the
 * assumption can be argued with and, later, displaced.
 *
 * Nothing here names a plant structure. Every structure's descriptions are read
 * through the same loader, so a structure name reaching this file would reach
 * every one of them.
 */
#ifndef PLANT_BUDGET_H
#define PLANT_BUDGET_H

/*
 * What introduces the assumed error of the value it follows.
 *
 * A character of its own rather than a second use of the origin marker,
 * because the two annotations say different things about the value and a
 * reader -- or a check -- that cannot tell them apart cannot establish that
 * either is present. One marker with a keyword behind it was the alternative;
 * it would have made the shorter and more frequently written of the two
 * annotations the more verbose one, and made a description's most common line
 * longer for no gain in what it says.
 *
 * The order is fixed: the value, then the error it may be out by, then the
 * origin the figure came from. The account of an origin is free text and runs
 * to the end of the line, so it has to be last or it would swallow whatever
 * followed it; and the error reads naturally against the value it qualifies
 * rather than after a sentence of prose about a service manual.
 */
#define PLANT_BUDGET_MARKER '~'

#endif /* PLANT_BUDGET_H */
