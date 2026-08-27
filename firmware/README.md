# Firmware

The control logic, the hardware seam that separates it from the target, and the
plant-model seam that separates the equations of the machine from everything
that uses them.

## Why the hardware seam exists

The control logic has to be exercised before any hardware exists, and the
analysis that catches memory errors and undefined behaviour runs on a host
rather than on a microcontroller. Both need the control logic to build and run
with the target absent. So every peripheral operation the control logic uses is
declared once, in vendor-neutral terms, in `include/hw_interface.h`, and two
implementations satisfy it: a simulated one for the host and an STM32 HAL-backed
one for the target.

Which implementation a build gets follows from which environment is built. It is
not a run-time choice, and no source file under `src/control` differs between the
two builds. That is what keeps an indirect call out of the control path.

## Why the plant-model seam exists

Two machines of the same architecture differ only in their numbers. Two machines
of different architectures differ in their equations, and no set of numbers
bridges that. So the split is drawn there: parameters are data the machine
carries, and structure is code behind a named interface. Adopting a machine of
the same architecture is then measurement work rather than development work, and
supporting a different architecture is implementing `include/plant_model.h`
rather than negotiating with everything that consumes the model.

Which structure a build gets follows from which directory under `src/plant/` it
compiles and puts on the include path — again a build-time fact, decided by
`DEC-MODEL-STRUCTURE-AT-BUILD-TIME` rather than by anything read while the
software runs. A build compiling the plant model must name exactly one; naming
none or naming two stops the build rather than letting a default or the linker
choose. Controlling a machine with another architecture's dynamics has no
obvious symptom until the machine is well outside where it should be, so it is
made unreachable rather than merely unlikely.

The `fixture` structure describes no machine. It exists because the checks that
keep one structure out of another's artefact, and that refuse a two-structure
build, both pass unconditionally with only one structure in the tree — and a
check that cannot fail is not a check.

The `boiler` structure is what makes the paragraph above a demonstration rather
than an intention. It is a different architecture, not the same equations with
different numbers: one heated vessel serves both the brew path and the steam
path, where the reference machine has two masses heated independently. So both
temperature quantities are answered from the one vessel state, steam pressure
follows that same state above saturation, and the machine's second heating
channel goes unanswered — a structure of a given architecture answers the
channels its machine has, and the vocabulary belongs to the machine rather than
to the structure. A structure of the same architecture with different numbers
would have exercised only the parameter path, which the two descriptions under
`params/` already cover and which is the weaker claim.

Adding it edited nothing already in the tree. No existing structure, neither
seam header, the shared parameter loader, none of the check tools, no gate
invocation and no existing test suite changed to admit it; what it cost is its
own directory, its own two descriptions, its own suite, three environment
entries here, two lines and one further argument in the repository's task file,
and this documentation. That list is the claim, and the change-set that
introduced it is where the claim is checked.

Whether the `thermoblock` structure's equations describe any real machine is a
question that needs a real machine, and so is the same question about `boiler` —
with the difference that nobody on this project owns a machine of that
architecture, so `boiler` is unverified as a final state rather than as a gap
somebody here is expected to close. What is established by both is that the
numbers are replaceable, the equations are replaceable, and neither is reachable
except through the seam.

## Where a value in a description came from

The design is reasoned against a description of the machine long before the
machine has been measured, and the values in such a description are not all the
same kind of fact. Some are read off a document, some are estimated because
nothing states them, and later some will be measured on the bench. An estimate
that cannot be told apart from a measurement is the more dangerous of the two,
because it is trusted like the measurement it resembles.

So a description that claims a real machine records, against each value and in
the same file, how that figure was arrived at and what it was arrived at from:

```
brew.heater_power_w = 1000.0 ~ 0.25 @document Coffee thermoblock element, read off the circuit diagram on p.24 of the service manual.
```

An annotation runs to the end of its line, so that is one line however far it
wraps on screen. A continuation line carries no `=` and is refused.

The kinds — `document`, `estimated`, `measured` — are declared once, in
`include/plant_origin.h`, so a further one is a deliberate edit there rather than
a word somebody typed into a description. Keeping the account beside the value
rather than in a table next to it is what stops the two drifting apart: an
estimate that has lost its provenance is trusted like the measurement it
resembles, and nothing about a bare number reveals that its account has gone.

A description that claims no machine at all says so, with `@describes-no-machine`
on a line of its own, and that statement is what exempts it from accounting for
its values — a number chosen because it differs from another has no origin to
record. The exemption follows what a description claims rather than which
structure it belongs to, so a machine-describing structure may still ship
descriptions that claim nothing about one.

The loader refuses a malformed annotation rather than skipping it, and
`check_parameter_origins.py` fails the build on a value with no account behind
it. A convention that depends on remembering is not a discipline: provenance
decays under time pressure, adding one more coefficient, and the failure leaves
no trace at the point of use.

## How wrong a value is assumed to be

The figure after the `~` is the error the design is entitled to assume for the
value before it, as a fraction of that value: `1000.0 ~ 0.25` says the machine's
real figure is assumed to lie within a quarter either side of a thousand. It is
assumed rather than measured, like everything else in a description of a machine
that has not been on a bench, and the marker is declared once in
`include/plant_budget.h`.

The order of the two annotations is fixed — value, then error, then origin —
because an origin's account is free text running to the end of the line and
would otherwise swallow whatever followed it.

It is carried beside the value for the same reason the origin is: a margin held
against an unstated uncertainty cannot be checked by anyone, including its author
later, and cannot be revisited when identification lands better or worse than it
was sized for. `check_assumed_error.py` fails the build on a coefficient with no
figure against it, in every description that claims a machine.

This is the one annotation the running program keeps.
`plant_parameter_budget_load()` reads a description for it and
`plant_parameter_budget_for()` answers for one coefficient by name, both through
the seam, so a consumer reasoning about how wrong the model may be never names a
structure. A coefficient the description carried no figure for reads back as
undeclared rather than as an error of zero: "the description says this is exact"
and "the description says nothing about this" demand opposite responses.

## What a wrong model is not permitted to take away

The model will be wrong, and the useful question is what still holds when it is.
`params/robustness.declaration` names each behaviour the design commits to and
classifies it as one of three words declared in `include/plant_robustness.h`:
`invariant` for what must hold however wrong the model turns out to be —
refusing what cannot be delivered, reaching a safe state, respecting the supply
budget, surrendering accumulated intent at the actuator limit — `bounded` for
what holds across the error the description declares and is not claimed beyond
it, such as stability and the margin protecting a trip point, and `degrading`
for what is permitted to get worse as the model does, such as how tightly a
setpoint is held.

The middle class earns its place: a guarantee that holds whatever the model says
and a guarantee that holds provided the model is within the declared error are
different promises, and a later verification checks the first by making the
model arbitrarily wrong and the second by sweeping the declared range.

It is data rather than a paragraph because a paragraph cannot be diffed when a
behaviour is added and cannot fail a build when one arrives unclassified.
`check_robustness_declaration.py` refuses a behaviour with no class, with two,
with a word the header does not declare, a behaviour named twice, and a class
nothing falls into. Whether a loop actually holds an invariant behaviour across
the declared range of model error is the robustness verification's question;
there is no loop yet.

## How far a structure has been verified

Cheap to add is not the same as supported. Every structure here compiles, links
and passes the seam's tests without any of that establishing that its equations
describe the machine they claim — that is settled on a bench, and nowhere else.
So each structure declares how far it has been taken, in its own header, and
`check_support_status.py` fails the build on a structure that declares nothing,
declares something outside the vocabulary, or claims verification with nothing
cited behind it. The vocabulary is declared once, in `include/plant_support.h`.

| Structure | Support status | Evidence |
| --- | --- | --- |
| `thermoblock` | `PLANT_SUPPORT_UNVERIFIED` | — |
| `fixture` | `PLANT_SUPPORT_UNVERIFIED` | — |
| `flow_fixture` | `PLANT_SUPPORT_UNVERIFIED` | — |
| `boiler` | `PLANT_SUPPORT_UNVERIFIED` | — |
| `outlet_only_fixture` | `PLANT_SUPPORT_UNVERIFIED` | — |

The line is drawn at verification against real hardware and at nothing else. In
particular it is **not** drawn at whose machine a structure describes: the
`thermoblock` structure describes the architecture this project's own machine is
built on, and that is a statement about what its equations are for rather than
evidence that anyone has run them against one. Nobody has. There is no machine
on the bench yet, so every structure in the tree is unverified and says so in the
same words — which is what lets an adopter comparing two of them compare like
with like, rather than reading the author's structure as the tested one.

A structure becomes `PLANT_SUPPORT_HARDWARE_VERIFIED` by being run against
hardware of its architecture and citing what was run, in
`PLANT_STRUCTURE_SUPPORT_EVIDENCE` and in the table above. Support status is the
field most likely to be set optimistically, because setting it costs nothing at
the moment of writing and its consequences land on somebody else's machine much
later. Requiring the citation is what makes the optimistic setting the one that
fails a check rather than the one that ships.

## Layout

| Path | What it holds |
| --- | --- |
| `include/hw_interface.h` | The hardware seam. Free functions, no vendor type, compiles freestanding. |
| `include/plant_model.h` | The plant-model seam. Free functions, no structure named, no equation. |
| `include/machine_actuation.h` | The machine's actuation channels and the scale their levels are on, declared once for both seams. Owned by neither. |
| `include/plant_types.h` | The vocabulary the plant seam is expressed in: quantities, actuation, parameter and step faults. |
| `include/plant_support.h` | The one place the support-status vocabulary is declared. Names no structure. |
| `include/plant_origin.h` | The one place the origin vocabulary is declared — how a value in a description was arrived at, and how a description says it claims no machine. Names no structure. |
| `include/plant_budget.h` | The one place the marker introducing a value's assumed error is declared, and what that figure means. Names no structure. |
| `include/plant_robustness.h` | The one place the three classes a declared behaviour is put in are declared — what a wrong model may take away, what it may take away only beyond the declared error, and what it may not. Names no structure, and names no control law. |
| `src/control/` | The control logic. Reaches hardware only through the seam. Identical in both builds. |
| `src/hw/sim/` | The simulated implementation, and the controls tests use to stand readings up. |
| `src/hw/stm32/` | The STM32 HAL-backed implementation. Naming vendor symbols is its job. |
| `src/plant/common/` | Reads a parameter record from a description. One parser, every structure. Not a structure itself. |
| `src/plant/thermoblock/` | The machine-describing structure: two heated masses, pump-driven brew pressure, steam pressure above saturation. |
| `src/plant/fixture/` | A structure that models nothing, so the exclusivity and two-structure checks have a second subject. Answers no pump channel and keeps no state the estimator reconstructs, on purpose -- see `src/plant/flow_fixture/` for the structure that exists because of that. |
| `src/plant/flow_fixture/` | A third structure that models nothing, alongside `fixture`. Answers a pump channel and one accumulator under both names the estimator reaches it by -- the state it reconstructs and the state its correction writes -- so `control_init` can come up against it and stay corrected once up, and a real admission can be asked of `control_command_delivery_reporting` -- which `fixture`'s own narrowness rules out. |
| `src/plant/boiler/` | A structure of a different architecture: one heated vessel serving both paths, so both temperature quantities follow one heater and the machine's second heating channel goes unanswered. |
| `src/plant/outlet_only_fixture/` | A third structure that models nothing, alongside `fixture` and `flow_fixture`. Answers the state `estimator_init`'s reachability check probes and refuses the different state the estimator's per-step correction writes toward for the identical reconstructed value -- the one pairing shape a structure can be admitted on one name of and silently never corrected against, which `SOL-ADMISSION-PROVES-FULL-PAIRING`'s widened admission check exists to refuse instead. |
| `params/` | Parameter descriptions, and the statement of what each represents. Read at run time. The host builds open the one they are given; the target has no filesystem to open one from, so its build compiles the description it declares into the artefact and the entry point reads those bytes back through the same loader. Each is named for the structure it describes — `<structure>.params`, or `<structure>-<variant>.params` where a structure ships several — which is how the task that runs the host artefacts knows what to run each against. A description no structure claims is reported rather than left unrun. A description that claims a real machine accounts for every value it carries and is accompanied by `<structure>.md`, which says what those quantities are and how they relate. |
| `params/robustness.declaration` | The behaviours the design commits to, each classified as one that must survive an arbitrarily wrong model or one permitted to degrade with it. Carried with the descriptions because it is the other half of the same design input: a declared range of model error says nothing without a statement of which behaviours are not allowed to depend on it. |
| `src/app/native/` | Host entry point: drives the control path and the model, including their error paths, and exits. |
| `src/app/stm32/` | Target entry point: brings the peripherals up, turns the description the artefact carries into a parameter record, then runs the same control path. It also holds the one translation unit that compiles the description the build generates. |
| `test/test_control/` | The control logic exercised against the simulated implementation. |
| `test/test_plant/` | The plant model exercised through the seam, naming no structure symbol. |
| `test/test_plant_narrow/` | The seam driven against a structure answering fewer actuation channels than the machine has — the refusal of a command with nowhere to land, which a structure answering everything cannot exercise. |
| `test/test_plant_boiler/` | The single-boiler structure exercised through the seam, asserting what holds of that architecture whatever its coefficients are. |
| `test/test_estimator_outlet_only_fixture/` | `estimator_init` asked directly for the admission a structure answering only the reconstruction-target state is refused by -- the one case no other suite's structure can drive. |
| `tools/` | The checks that make the seam's properties build failures rather than review notes, and the build steps that render the carried description and keep the model's operations in the artefact. |

The control logic behind the seam is a minimal path that reads a sensor,
consults the clock and drives an output. What this establishes is separability,
not control performance — the control law, the state estimator and the plant
model are separate units of work.

## Building

PlatformIO is the build system. It installs into its own virtual environment
rather than onto `PATH`:

```sh
curl -fsSL -o get-platformio.py \
  https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py
python3 get-platformio.py
```

The host environment needs only a system C compiler. The target environment
downloads the ARM GCC toolchain and the STM32Cube framework on its first build;
after that both build offline.

Everything runs from the repository root through the task runner:

```sh
task fw:verify     # build every environment, run every check, run the tests, run the host builds, run the emulation tier, sweep the arithmetic
task fw:build      # the environments only
task fw:check      # the build-time checks only
task fw:test       # the control-logic and plant-model tests, and the tests covering the checks
task fw:run        # every host executable, against the descriptions its structure ships
task fw:emulate    # the target build's own artefact, executed against models of the peripherals it drives
```

The emulation tier needs an emulator and the vendor's register description,
neither of which is committed. They are fetched, pinned by digest, into
`.tooling` by:

```sh
task fw:emulate:provision
```

`fw:emulate` provisions on its own if they are not there, so the separate task
is for fetching ahead of time — on a machine that will be offline later, or in a
job that wants the download in its own step. What the tier establishes, how the
peripheral models are written, and why a run is only evidence about the artefact
the target build wrote are all in [`emulation/README.md`](emulation/README.md).

One more runs on demand rather than in the gate:

```sh
task fw:mutate                    # break each guarded property, require its check to notice
task fw:mutate -- -k header       # only the mutations whose name matches
task fw:mutate -- --list          # name them without running
```

It edits sources in place and restores them, so it refuses to start when those
files have uncommitted changes, and it verifies the restore before reporting.

Three things make its answers mean something. Each command is run once before
anything is broken, because a command that already fails would make every
mutation under it look caught. A mutation counts as caught only when its command
reports having *found the problem* — these checks exit 1 for that and 2 for
being unable to look, and treating the second as a catch would be this tool
committing the failure it exists to detect. And because editing the build file
makes the build system discard every linked artefact, the artefacts are re-made
during the run and again at the end, so neither the next mutation nor the
ordinary gate is left inspecting something that is no longer there.

It overlaps the tool tests under `tools/tests/` on purpose but does not replace
them: those drive each check against synthetic broken subjects in the gate,
where this drives the real checks against the real sources end to end, which is
what catches a check that is correct in isolation and mis-wired in the build.

It is out of the gate because it answers a question — are these checks real —
that does not change between commits the way the checks' own results do. Run it
when a check is added or reworked.

The second sweeps the plant model's arithmetic instead of the checks. It is the
last step of `fw:verify` as well as being runnable alone, so the full gate asks
not only whether the checks pass but whether the tests would notice the model
being wrong:

```sh
task fw:sweep                     # alter every comparison and operator, require a test to notice
task fw:sweep -- --survivors-only # list what survived without judging it
```

Where `fw:mutate` breaks named properties one at a time, this generates the
class those names are drawn from. Every comparison, arithmetic operator and
increment in the sources every structure shares, and in the equations of every
structure declaring that they describe a machine, is altered in turn and the
suite is run against each alteration. That population is read out of the tree
rather than listed anywhere: a structure joins it by declaring
`PLANT_STRUCTURE_MACHINE_CLAIM` as `PLANT_DESCRIBES_A_MACHINE` in its own header,
and `mull_sweep.py` refuses to run if a list reappears in `mull.yml` to override
it. The two answer different
questions, and the difference is the point: a list of specific defects that are
caught establishes exactly the members of the list, and says nothing about the
defects nobody thought to write down.

It needs LLVM 19 and the matching Mull package, which the ordinary gate does
not, so the environments it compiles — `native_mutation`,
`native_fixture_mutation` and `native_boiler_mutation` — declare
`custom_mutation_sweep` in `platformio.ini`
and are left alone by the gates covering every host build. Those gates say so
when they skip one rather than passing over it silently. Both environments are
swept because a mutant counts as caught when *any* suite kills it: the sources
under `src/plant/common` are compiled into both structures' runners, and the
refusal of a command on an unanswered channel can only be triggered against the
fixture, which answers one channel of three.

The sweep is the one host build compiled without the sanitizers, deliberately.
A mutant that makes the program read out of bounds is stopped by
AddressSanitizer whether or not a test asserts anything, and counting that as
caught would credit the suite with noticing something the analysis noticed. The
question here is what the tests catch, so it is asked with nothing else
watching.

A mutant no test kills is not a defect until somebody has decided it could be
one. Some cannot change what the program does at all — a comparison at a
boundary where both branches give the same value — and writing a test to kill
one would mean asserting something untrue to move a number. So every survivor
is accounted for by hand in `mutation_triage.yaml`, as `equivalent`, as a real
`gap`, or as `analysis` for one whose only effect is a read or write outside
something, which no assertion can see and the sanitized build aborts on. The
sweep fails on a survivor nobody has judged, and reports it as an unreviewed
count rather than as a defect count, because which of the two it is is exactly
what has not been decided. It fails on a gap left standing, and on a judgement
about a mutant it no longer finds — the code that judgement was made about has
changed, so it has to be made again rather than carried forward.

Its first run found six real gaps and they were closed by tests, not recorded:
indented lines, a final line with no newline after it, the two refusals that
quote a line, the declared bounds being admissible values rather than the first
refused ones, and a value token longer than the loader can hold.

`.github/workflows/mutation-sweep.yml` runs it on a hosted runner, started by
hand for the same reason the task is. Nothing in the toolchain discovery names a
Homebrew path, but a verification tool is only portable once it has run
somewhere other than the machine it was written on.

Set `PIO=/path/to/pio` if PlatformIO lives somewhere other than
`~/.platformio/penv/bin/pio`, and `MULL_CLANG`, `MULL_IR_FRONTEND` or
`MULL_RUNNER` if the mutation toolchain is somewhere the sweep does not look.

## What the checks enforce

Each is a standalone script, so the same check runs from the build and from the
task runner. Six of them also run automatically inside every `pio run`.

| Check | What it fails on |
| --- | --- |
| `check_header_neutral.py` | The seam header names a vendor symbol, or does not compile standalone against a freestanding compiler with no vendor include path. Runs inside every build. |
| `check_encapsulation.py` | A file under `src/control` reaches a HAL function, a CMSIS symbol, a peripheral instance, a device header, an include the check cannot resolve, a peripheral address, or assembly. Runs inside every build. |
| `check_sanitizers.py` | A source of this project's own reaches a host artefact without the sanitizers, or without the strict warning settings in an environment that could scope them to this project's sources, or the executable links no sanitizer runtime — failures that otherwise pass silently. Covers every host environment the build declares. |
| `check_direct_calls.py` | A seam call in a linked executable is indirect, or a seam operation the control logic references is reached by no direct call at all. Covers every host artefact the build declares. |
| `check_control_identical.py` | A control translation unit does not preprocess identically in both environments — which is how an environment-defined macro reaching the control logic is caught. |
| `check_plant_header.py` | A seam header names a structure, reaches into a structure's record, carries a function definition, or fails to compile standalone against *every* structure in turn. Run over `plant_model.h`, and over `plant_types.h`, `plant_support.h`, `plant_machine_claim.h`, `plant_origin.h`, `plant_budget.h`, `plant_robustness.h` and `machine_actuation.h` under `--vocabulary-only`, which drops only the requirement to declare an operation. Inspecting one and not the others would let the uninspected one clear itself. Runs inside every build. |
| `check_plant_encapsulation.py` | Anything outside `src/plant/` includes a structure's own header or names a field or function a structure owns. Runs inside every build. |
| `check_structure_selection.py` | A build that compiles the plant model names no structure, or names more than one. Runs inside every build, before anything is compiled. |
| `check_structure_exclusive.py` | A linked artefact is missing the structure it was built for, or carries a symbol belonging to another one — or a structure in the tree is built by no environment at all, and so is checked by nothing. Covers every structure. |
| `check_selection_refused.py` | A deliberately misconfigured environment — naming no structure, naming two, or mapping an actuation channel table short of the vocabulary it maps — builds anyway, leaves an artefact behind, or stops for a reason other than the one it declares. |
| `check_parameters_are_data.py` | One unchanged artefact run against two descriptions differing in a single coefficient produces the same trajectory twice, which is what a compiled-in coefficient does. |
| `check_actuation_declaration.py` | A structure declares no set of actuation channels, declares more than one, declares an empty one, or names a channel the machine's shared vocabulary does not carry. Runs inside every build, over every structure in the tree rather than the one the build selected. |
| `check_parameter_origins.py` | A description that claims a real machine carries a value with no origin, an origin of a kind the vocabulary does not declare, or a kind with no account behind it; a coefficient the structure requires is absent from it; or its statement of what it represents has fallen behind the coefficients and quantities it has to name. Also fails a vocabulary that no longer separates an estimate from a measurement, and a tree in which every description exempts itself, since that inspects nothing. Runs inside every build, over every description in the tree rather than the one the build runs against. |
| `check_assumed_error.py` | A description that claims a real machine carries a value with no assumed error against it, or one that is not a figure a value could be out by — absent after its marker, unreadable, negative or not finite. Also fails a vocabulary whose marker is the one that already introduces an origin, since an account runs to the end of the line and would swallow every figure, and a tree in which every description exempts itself, since that inspects nothing. Runs inside every build, over every description in the tree. |
| `check_robustness_declaration.py` | A behaviour the design commits to carries no class, carries two, or carries a word the vocabulary does not declare; a behaviour is declared twice; a class has nothing in it, which is a declaration that drew no line; or the artefact is absent or empty. Reads the classes out of `plant_robustness.h` rather than restating them. |
| `check_machine_claim.py` | A structure declares nothing about whether its equations describe a machine, declares it more than once, or declares something outside the vocabulary. Also fails a vocabulary that has grown a distinction beyond that one, and a tree in which no structure describes a machine at all, since the mutation sweep would then draw its mutants from an empty population. Runs inside every build, over every structure in the tree rather than the one the build selected. |
| `check_support_status.py` | A structure declares no support status, declares one outside the vocabulary, claims hardware verification without citing it, or is documented with a status its own header does not claim. Also fails a vocabulary that has grown a distinction beyond whether hardware has verified the structure. Runs inside every build, over every structure in the tree rather than the one the build selected. |

The plant model's invariants are additionally exercised across the range each
coefficient declares admissible, rather than at the one nominal value. The
bounds are discovered through the seam by offering a description and seeing
whether it is accepted, so the test cannot drift from what the structure
declares and does not have to name a structure symbol to read them. That test is
what found an initial state which was not an equilibrium of the structure's own
equations — invisible at the nominal ambient, which sits below saturation.

Each check fails rather than passes when it cannot find what it is meant to
inspect. A check that inspects nothing must not report success. The
encapsulation checks apply the same rule to file kinds: they inspect every file
under their subject except a listed set they know a build never compiles, so a
C++ or assembly source dropped into a directory the build filter takes
wholesale cannot walk past them.

The plant checks carry that further, because several of them can only fail if
there is something to fail against. `check_plant_header.py` refuses a tree with
fewer than two structures, since compiling against one cannot distinguish a
neutral header from one written for that structure.
`check_structure_exclusive.py` refuses a tree with fewer than two, and refuses
one where two structures declare the same names — in either case there is
nothing to exclude, and it would pass whatever the artefact contained.
`check_structure_selection.py` treats a source filter it could not resolve as an
error rather than as "this build compiles no plant source".

What a structure owns is read out of the structures themselves rather than
listed in the tools: `structure_symbols.py` derives each structure's fields and
declarations from its own header, so a structure that gains a coefficient does
not need a check to be updated to keep covering it.

## What the gates cover, and how they know

A gate handed the name of what it covers checks what somebody remembered to
name, and a green build looks identical either way. So the gates whose subjects
are a set that grows with the tree discover them instead. `build_environments.py`
reads `platformio.ini` — resolving `extends` and `${section.option}` the way the
build system does — and answers which environments produce a host artefact,
which link this project's own entry point, which run tests, and which structure
each one selects. `run_host_artefacts.py` and `run_host_tests.py` use the same
answers to run what was built, since a sanitizer reports nothing until the code
runs and tests that never ran leave nothing behind to notice. `run_host_tests.py` also requires every
structure in the tree to have an environment running tests against it, and every
suite in the test directory to be one some environment would run: with more than
one test environment, one of them quietly ceasing to run — or a suite no
environment's `test_filter` takes in — is invisible in a count of what passed.
The matching requirement for artefacts is `check_structure_exclusive.py`'s,
which reports a structure no environment builds one for.

Properties a gate must not guess at are declared in `platformio.ini` beside the
environment they describe, with the reason as the value: `custom_must_not_build`
on the configurations required to be refused, which cannot also be required to
build cleanly; `custom_strict_flags_exemption` on the environment that compiles
the test runner's generated support file through the same path as this project's
sources, and so cannot scope the warning settings to ours alone; and
`custom_embedded_description` on a build for a board, naming the description its
artefact carries compiled in. The exemption is honoured only on an environment
that really does compile foreign sources that way, so it cannot become a way of
turning the settings off where they could be kept.

A configuration required to be refused may also declare
`custom_must_not_build_marker`, naming what its own refusal has to print. More
than one check can stop a build, and a marker-blind gate would keep passing
after the check an environment exists to exercise stopped running at all —
`check_selection_refused.py` reads each environment's own marker rather than
one shared string. An environment naming none is read as expecting
`check_structure_selection`, which is what every misconfigured environment
declared before this option existed.

Four gates keep their named subjects, because there the names are the content of
the check rather than a list to forget: the two plant-header checks (one header
is a seam, the other a vocabulary, and the obligations differ),
`check_control_identical.py` (comparing that pair is what it compares),
`check_selection_refused.py` (a forgotten name there fails loudly rather than
quietly), and `check_parameters_are_data.py` (it needs two descriptions
differing in a single coefficient before it can conclude anything).

Every discovering gate fails when it discovers nothing — no structure, no
artefact, no environment — because a gate covering an empty set reports success
in exactly the way a gate nobody ran does.

## What the machine carries

A host build opens the description it is exercised against; the machine has no
filesystem to open one from. So the description travels inside the artefact:
the build renders `params/thermoblock.params` into the build directory as an
array of bytes, one translation unit under `src/app/stm32/` compiles it, and the
entry point hands those bytes to the plant seam's own loader. There is no
second parser, and a description that loader refuses leaves the machine without
a model rather than running on defaults.

Rendering the bytes from the file is not an argument that they are the right
bytes. Three things can put a description into an artefact that nobody verified
— a build naming a different one, a rendering left behind by an incremental
build, and a variant sitting in `params/` beside the intended one — and none of
them has a symptom on the machine, because predictions that stop matching
observation look exactly like a machine that has drifted. So the rendered bytes
are compared against the description the host tier is pinned to through
`REFERENCE_DESCRIPTION_PATH`, before anything is compiled, and the build stops
when they differ.

The artefact is then read after linking, which is a separate question from all
of the above. The linker discards what nothing reaches, and nothing on the
machine drives the model yet — the estimator that will hold an instance of it is
a later unit of work. An artefact the equations were dropped from passes every
check made before it exists: the build succeeds, the description is still
carried, and the maths those equations call into stops being needed, so a
toolchain that could never have resolved it is not asked and appears to have
answered. The operations `include/plant_model.h` declares are therefore named to
the linker as wanted, read out of that header rather than listed anywhere, and
`check_target_carries_model.py` establishes they survived.

## The nominated STM32 family

The target environment names an STM32F4 board so that the control logic can be
preprocessed and compiled against a real cross toolchain before any controller
is chosen. That nomination is not the machine's controller selection, which is
answered later against measured parameters. Changing it touches
`src/hw/stm32/` and `platformio.ini` and nothing else — which is the seam's own
property, and the reason the nomination is cheap.
