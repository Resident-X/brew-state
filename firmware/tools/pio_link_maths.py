"""Link the maths library the plant model's equations need.

On a Mac the maths functions are part of the standard library and asking for
them separately is a no-op. On the GNU systems this is meant to build on just as
readily they live in a library of their own, and leaving it unnamed fails at the
link with the model's own equations undefined -- `expm1f` from the thermal
relaxation, `exp` and `nextafterf` from the tests that check it.

So it is named rather than inherited from whichever host the build happened to
run on. A dependency that is satisfied by accident on the machine the author
uses is one nobody discovers until somebody else builds, and by then it looks
like their problem rather than the build file's.

The build for the board is here for the same reason one step removed. Its
platform happens to name the maths library already, so this changes nothing
there today -- and that is exactly the kind of thing that changes underneath a
project. A dependency the plant model's equations have either belongs to the
build that compiles them or belongs to whoever packaged the platform, and only
one of those is ours to keep true.

This is a separate script from the sanitizer one on purpose. Every host build
needs the maths library; the build compiled for the mutation sweep needs it too
and deliberately does not run the sanitizer script, so folding the two together
would tie a universal need to an analysis one build leaves out.
"""

Import("env")  # noqa: F821 -- injected by SCons

# Appended to the libraries rather than to the link flags, so it is ordered
# after the objects that refer to it however the link line is assembled.
env.Append(LIBS=["m"])  # noqa: F821
