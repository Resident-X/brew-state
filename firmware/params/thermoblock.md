# What the thermoblock description represents

This is the statement that goes with `thermoblock.params`. It is read with the values rather than instead of them: the file holds a list of numbers, and a list of numbers cannot be checked against a machine and cannot be extended without guessing what its author meant.

It says what each quantity stands for, what unit it is carried in, which relations link them, and — at the end, and just as deliberately — what the description leaves out. A quantity omitted here is one the design cannot reason about, and a reader has no other way to tell an omission from an oversight.

Whether these relations match the machine's measured behaviour is not settled here and cannot be until the machine is on the bench. What is settled here is that the description says what it claims.

## The machine this describes

The reference machine declared in `../../docs/reference-machine.md`: two independently heated thermoblocks, one serving espresso and hot water, the other serving steam only. A thermoblock is a casting with an element embedded in it and a water channel passing through it. It heats water as the water flows past and holds no reservoir, which is why the description carries a thermal mass and no stored volume.

## The states the structure integrates

Each is a field the model advances from one step to the next. All five are single precision, as everything crossing the seam is.

| State | Physical thing | Unit |
|---|---|---|
| `brew_temperature_c` | Bulk temperature of the coffee thermoblock's casting, taken as uniform | °C |
| `brew_outlet_temperature_c` | Temperature of the water on its way from that casting to the group | °C |
| `steam_temperature_c` | Bulk temperature of the steam thermochamber's casting, taken as uniform | °C |
| `brew_pressure_bar` | Pressure in the brew path between the pump and the group | bar, gauge |
| `steam_pressure_bar` | Pressure in the steam path | bar, gauge |

The coffee side carries two temperatures because on this architecture they are two things. The element acts on the casting, and the water the group receives has passed through that casting and left it; a machine that heats water as it flows past puts real dynamics between the metal and the stream, and a description carrying one temperature for both would be asserting there are none. The casting is the one the machine senses — its brew sensor is in the casting, which is where a sensor can physically go — and the water at the group is the one an extraction is judged by, which is why the two have to be separate before anything can reconstruct the second from the first. The steam side carries one because nothing is drawn through it in the same way — what a steam draw does to that mass is among the omissions at the end of this statement.

`steam_pressure_bar` is held alongside the others but is not integrated independently: every step recomputes it from `steam_temperature_c` through the saturation relation below. It is a state in the record and a function in the equations, and treating it as though it had its own dynamics would be wrong.

## The quantities the seam exposes

These are what a consumer can read back through `plant_model_quantity`. Most are answered from exactly one state, in the same unit; the exception is noted under the table and is the reason the wording is not stronger.

| Quantity | Answered from | Unit |
|---|---|---|
| `PLANT_QUANTITY_BREW_TEMPERATURE_C` | `brew_temperature_c` | °C |
| `PLANT_QUANTITY_STEAM_TEMPERATURE_C` | `steam_temperature_c` | °C |
| `PLANT_QUANTITY_BREW_PRESSURE_BAR` | `brew_pressure_bar` | bar, gauge |
| `PLANT_QUANTITY_STEAM_PRESSURE_BAR` | `steam_pressure_bar` | bar, gauge |
| `PLANT_QUANTITY_BREW_FLOW_ML_PER_S` | no state — the commanded pump level | mL/s |

Four of the five are read from a state. `PLANT_QUANTITY_BREW_FLOW_ML_PER_S` is not, and it is the one entry in this table that is a function of what was commanded rather than of what the structure integrated: the relation below turns the pump's commanded level into a rate, and nothing accumulates. Volume per unit time rather than mass per unit time, because a flow meter reads volume and the coefficient behind it is written in those terms — anything downstream needing a mass rate converts, and a visible conversion is worth more than a quantity nobody can hold an instrument against.

The correspondence runs the other way too, and unevenly. There are five states and five quantities and they are not the same five. `brew_outlet_temperature_c` is a state with no quantity against it, which is the point of carrying it: it is the temperature the design most wants and the one the machine does not report, so it is what work reconstructing an unmeasured state has to reconstruct. The drawn rate is the converse — a quantity with no state against it — and that is equally deliberate, because nothing about it needs integrating and giving it a state would invite something to correct it against a reading. Reading a state is a separate operation from reading a quantity — `plant_model_state`, over the vocabulary below — because the quantities are the machine's and the states are this structure's, and a structure of another architecture answers a different set.

| State reachable through `plant_model_state` | Answered from |
|---|---|
| `PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C` | `brew_temperature_c` |
| `PLANT_STATE_BREW_OUTLET_TEMPERATURE_C` | `brew_outlet_temperature_c` |
| `PLANT_STATE_STEAM_TEMPERATURE_C` | `steam_temperature_c` |
| `PLANT_STATE_BREW_PRESSURE_BAR` | `brew_pressure_bar` |
| `PLANT_STATE_STEAM_PRESSURE_BAR` | `steam_pressure_bar` |

This structure keeps every state the vocabulary names, which is a property of this architecture and not of structures in general.

## What drives it

Three actuation channels, each commanded in parts per thousand of full scale and used as a duty fraction. The model takes duty as proportional drive within a step; how a duty becomes a switching pattern on a real load belongs to the actuation work, not here.

| Channel | Acts on |
|---|---|
| `ACTUATION_CHANNEL_BREW_HEATER` | The coffee block's element |
| `ACTUATION_CHANNEL_STEAM_HEATER` | The steam block's element |
| `ACTUATION_CHANNEL_PUMP` | The brew path's pump |

## The relations, and which coefficient enters which

**Each heated mass.** A lumped thermal mass with an element in it, losing to ambient in proportion to how far above ambient it sits:

    C · dT/dt = P · duty − k · (T − T_ambient)

That is the whole of the steam side. The coffee side carries one term more, below, because water is drawn through it. Both are advanced over a step by the exact solution for a constant duty, rather than by assuming the rate held. Per side:

| Coefficient | Enters as | Unit |
|---|---|---|
| `brew.thermal_mass_j_per_k` / `steam.thermal_mass_j_per_k` | `C`, the energy that raises the casting by one kelvin | J/K |
| `brew.heater_power_w` / `steam.heater_power_w` | `P`, the element's power at full duty | W |
| `brew.loss_w_per_k` / `steam.loss_w_per_k` | `k`, the loss per kelvin above ambient | W/K |
| `ambient_temperature_c` | `T_ambient`, shared by both masses and the state both start from | °C |

The two masses are independent. Nothing in these relations couples one to the other — which is a property of this machine, whose blocks are separately heated and not plumbed in series.

**What the coffee block gives up to the water.** Water is drawn through the coffee block and not through the steam one, so the coffee side carries a second loss:

    C · dT_brew/dt = P · duty − k · (T_brew − T_ambient) − flow · c_v · (T_outlet − T_feed)

| Coefficient | Enters as | Unit |
|---|---|---|
| `water.heat_capacity_j_per_ml_k` | `c_v`, what a millilitre of water costs to raise by one kelvin | J/(mL·K) |
| `water.feed_temperature_c` | `T_feed`, the temperature the water arrives at | °C |

Three things about that term are decisions rather than arithmetic, and each is a decision this description can be argued with about.

The rate is a volume per unit time, because that is what the relation above it produces and what a meter would read, so the coefficient that turns it into a power has to be per unit volume. Water's specific heat is per unit mass and there is no density anywhere in this description to convert with; carrying one here would be carrying a coefficient nobody would ever vary, so the density is folded into `c_v` and the conversion is one visible number rather than two.

The temperature the water arrives at is its own coefficient and not `ambient_temperature_c`. On this machine the two are the same number, because the tank stands in the same room the machine does — but they are not the same quantity, and the moment the machine is plumbed, or is somewhere with a winter main, the feed runs far below the room while the loss to ambient goes on being reckoned against the room. Reusing ambient would have made a description that is correct here and silently wrong everywhere else, which is the failure this project is least entitled to ship.

And the difference is taken at the water leaving rather than at the casting. Energy leaves this machine in the water that leaves it, at the temperature that water is actually at, so the casting's own temperature would be the wrong end of the gradient the outlet state exists to represent. It also has a consequence worth stating outright: it is what makes the casting — the one thing this machine senses — depend on the outlet state. See the omissions below, where what that does and does not buy is set out.

**The water on its way to the group.** A first-order relaxation towards the casting it has just passed through, over a residence time that shortens as more water is pushed past:

    τ(flow) · dT_outlet/dt = T_brew − T_outlet
    1 / τ(flow) = flow / V_held + 1 / τ_conduction

| Coefficient | Enters as | Unit |
|---|---|---|
| `brew.outlet_held_volume_ml` | `V_held`, the water held between the casting and the group | mL |
| `brew.outlet_conduction_time_constant_s` | `τ_conduction`, how fast that water reaches the casting when none of it is being displaced | s |

The element does not appear in this relation, and that is deliberate: the heater reaches the water only through the casting. What has changed is that the lag is no longer a constant of the machine. Two things bring the held water to the casting's temperature and they act at once, so they add as rates: displacement, which turns the held volume over once every time the draw has moved that volume through it, and conduction, which works on whatever is sitting there whether or not anything is moving.

Writing them as reciprocals is what makes the relation defined at a closed pump rather than merely defended there. Written as a residence time alone, `τ = V_held / flow`, a closed pump divides by nothing and the description would need a rule for that case — and a rule is a discontinuity wherever it takes effect. Added as rates, a closed pump contributes exactly zero to the first term and what is left is the conduction rate, which is a coefficient with a strictly positive range. There is no branch and nothing to guard.

The two coefficients replace a single fixed outlet time constant, which was this description's figure for the residence time at the flow a shot is drawn at. The drawn rate now supplies that directly, so keeping it would have been carrying the same quantity twice — see the accounting section below, where the reasoning behind that superseded figure is re-worked rather than carried over.

**How the casting and the water are advanced together.** The two relations above now each contain the other's state, so neither has a closed form of its own left to be exact against. What the pair does have is linearity, and coefficients that hold still across a step of constant actuation — so it is advanced by the exact solution of the coupled pair over that step, not by an approximation with a bounded error, and not by shortening the interval until an approximation stops mattering. The interval remains the one the seam is handed.

The step is the same shape every other relation here uses: the state after it is where it started, plus a weight times the rate it was leaving at, plus a second weight times the rate that rate was itself changing at. Two weights instead of one is the whole of what coupling costs. As the step vanishes the two go to the step and half its square, which is what anyone would write down; over a long step they carry the pair all the way to where it settles.

Two shapes are possible and both are the same closed form. Ordinarily the pair is two separate decays. But when a fast draw pulls hard on a light casting, the pair oscillates instead — the casting gives up heat according to where the water is, and the water is always behind, so the casting can overshoot and come back. That is not a defect of the integration but a property of these relations at those coefficients, and the step is exact across it. Whether a real block does that is a question for a real block; what can be said here is that the description does not hide it.

The error this leaves is arithmetic rather than assumption, so it sits differently from the figures accounted for below: for a step of constant actuation there is no truncation term at all, and what remains is the rounding of single precision. That is worth stating precisely because the section below is about how wrong the values are, and it would otherwise be reasonable to wonder how much the integration adds. What it adds is not quite the flat rounding every other relation here carries, and the difference is worth being exact about rather than glossed. The two weights are assembled by subtracting two quantities of similar size — the pair's two modes, separated — and how much of each other they cancel depends on how many time constants of the faster mode the step spans. So the rounding grows with that span rather than staying put: at the extremes of the admissible coefficient ranges, over a step long enough to swallow the fast mode entirely, it reaches something a reader would notice. At the coefficients this description actually declares, and at the roughly hundred-millisecond interval the seam is driven with, the fast mode is barely a fraction of one step and the result agrees with an extended-precision reference into its seventh decimal digit — which is the rounding of the single-precision state itself and nothing more. The claim is therefore bounded rather than unconditional: no truncation term ever, and rounding that is negligible over the intervals and coefficients this description is written for.

**Brew pressure.** A first-order relaxation towards what the pump is commanding:

    τ · dp/dt = pump.pressure_bar · duty − p

| Coefficient | Enters as | Unit |
|---|---|---|
| `pump.pressure_bar` | The pressure the brew path settles to at full pump duty — the asymptote of the relation above, not the pump's closed-outlet rating, though it is the rating this description estimates it from | bar |
| `brew.pressure_time_constant_s` | `τ`, how fast the path reaches it | s |

**The rate water is drawn.** Algebraic, from what the pump is commanded, and proportional to it:

    flow = pump.flow_ml_per_s · duty

| Coefficient | Enters as | Unit |
|---|---|---|
| `pump.flow_ml_per_s` | The rate the brew path draws at full pump duty | mL/s |

Nothing else enters. There is no resistance term, so what the water is being pushed through makes no difference to this figure: the same duty reports the same rate through an open path, through a fresh puck and through a blocked one. That is the rate commanded, not the rate a cup received, and the gap between the two is the puck, the pump's flow-versus-pressure characteristic and the mechanical cap — all three of which remain among the omissions at the end of this statement.

This rate is now consumed as well as reported, and in two places: it sets how much energy leaves the coffee block, and it sets how fast the water on its way to the group approaches the casting. Both are the relations above and both read this one figure rather than deriving a second rate of their own, so a description whose commanded rate is wrong is wrong about the thermal balance in exactly the way it is wrong about the rate — which is worth knowing, because that figure carries one of the widest fractions here and is one-sided into the bargain.

**Steam pressure.** Algebraic, from the steam block's temperature, and zero until that mass reaches saturation:

    p_steam = max(0, steam.pressure_bar_per_k · (T_steam − steam.saturation_temperature_c))

| Coefficient | Enters as | Unit |
|---|---|---|
| `steam.saturation_temperature_c` | The temperature below which the steam path carries no gauge pressure | °C |
| `steam.pressure_bar_per_k` | The local slope of saturation pressure with temperature above it | bar/K |

Temperatures are advanced before pressures within a step, so steam pressure reflects where its mass has just arrived rather than where it was.

## How wrong each value is assumed to be

Every value in `thermoblock.params` carries, beside it, the error the design is entitled to assume for that value. The figures are in that file and are not repeated here — one statement of them exists rather than two that can disagree. What is here is why each is the size it is, which is a judgement and belongs where judgements can be argued with.

Each is a fraction of the value it stands against, either side of it, so a coefficient written as 300 with a fifth against it says the design assumes the machine's real figure lies between 240 and 360. A fraction rather than a quantity in the coefficient's own unit, because a reader of a margin calculation should not have to know whether the number beside it is in joules per kelvin or in bar per kelvin to know how much trust it carries.

Every one of them is assumed. Nobody has measured how far out any of these is, and none of these fractions is evidence; they are what a reader who knows how each figure was arrived at would call generous rather than optimistic. Replacing an assumption with a measurement belongs to the characterisation work, and it will move these as well as the values.

The reasoning, by the kind of fact each figure is:

- **The two element ratings** are read off the manufacturer's circuit diagram and are among the tighter figures here, though not tight. Two real effects that these equations fold flat into a constant have to fit inside them: the declared 230–240 V supply spread is about 8% in delivered power on its own, and an element's resistance rises as it heats, which is another percent or two and is systematic in step with the climb this model is mostly used to reason about. The coffee side carries considerably more than the steam side, and the difference is the dispute recorded against it — the machine's owner recalls that element as 1200 W against the manual's 1000 W, and the fraction is wide enough to contain the owner's figure. A margin sized against the manual alone would be sized against a figure that may simply belong to another variant.
- **The two casting masses** are worked out from geometry, an assumed alloy and a casting nobody has weighed, and the steam side's is additionally a judgement that it is heavier than the other on the strength of an exploded view. A few tens of percent is what estimating a mass from a drawing is worth. These are also the coefficients most likely to be displaced first, because putting a casting on a scale is the cheapest measurement on the list.
- **The loss coefficients** are the loosest figures in the description, deliberately. They come from exposed area under still-air convection with no allowance at all for conduction into the chassis, and that path exists and is not small. The estimate is therefore known to be low rather than merely uncertain, and the fraction against each is wide enough to admit a value well above it.
- **The pump's pressure** is a nameplate rating used for something it is not: what the pump makes against a closed outlet, standing in for what the brew path settles to at full duty. That substitution is a judgement rather than a reading, and the true figure is lower rather than symmetrically uncertain — the fraction is sized to reach it.
- **The pump's flow at full duty** is the only coefficient here with no figure of its own behind it. What is recorded for the fitted pump is an electrical rating and a pressure rating, both for the type rather than from any measurement of this part, and neither of them is a delivery rate; no source for one has been found. The figure is therefore what a vibratory pump of that class does. Its fraction is wide for a reason the others are not: what it has to contain is not the error in one figure but the difference between two operating cases these equations cannot tell apart, since the same duty reports the same rate into an open path as through a puck at working pressure. The true figure for an extraction sits well below the value, so like the pump's pressure this one is one-sided rather than symmetric.
- **The brew path's time constant** comes from comparable machines rather than from this one, whose compliance and fill volume are not established. It is also the coefficient the extraction transient is most sensitive to, so it carries about half the value: a coefficient that is both poorly known and influential is where a narrow assumed error does the most damage.
- **The held volume between the casting and the group** replaces half of what a single fixed outlet time constant used to carry, and it is the better-behaved half. It is a geometry, so it is estimated the way the casting masses are estimated — from a drawing, an assumed bore and a path length nobody has measured — and it carries a fraction of the same order for the same reason, a little wider because a bore is squared on its way to a volume. What makes it worth having as a coefficient in its own right is that it is measurable without instrumenting the group at all: the volume between the casting and the group can be displaced and weighed on a bench. Of the two coefficients that replaced the old one, this is the one that will move first.
- **The no-draw conduction constant** carries the other half, and it is now the widest fraction in the description. That title moved rather than being inherited: the old outlet constant was widest because it stood for a residence time nobody had measured, and the drawn-rate relation now computes that residence time from the held volume, which leaves this coefficient standing for something else entirely and worse known. It is a conduction path with no draw across it, and it is not one path but two averaged by hand — water in the casting's own channel sits a millimetre from hot metal and equilibrates in about a second, while water already out of the block and in the run of tube reaches the casting through nothing at all and on its own never would. One constant for both is a judgement about which part of the held volume dominates, and the fraction is sized wide enough to admit either answer rather than to express a measurement error. It is also the coefficient that decides what the model says about a machine sitting idle between shots, which is most of the time a machine spends.
- **The feed water temperature** is not a property of the machine either, and its fraction is sized for the same kind of reason ambient's is — except that where ambient covers a room, this covers a plumbing arrangement. On the reference machine the feed is a tank standing in the room and the figure is the room's. On a plumbed machine, or on this one in a colder place, it is a mains temperature well below that. The fraction reaches down to about ten degrees, which is a temperate winter main; a machine fed anything colder than that is outside what this figure covers, and saying so here is better than leaving somebody to discover it inside a margin they derived from it. A description that only fitted the tank in the warm kitchen would be one this project could not honestly publish.
- **The volumetric heat capacity of water** is the tightest figure here after the saturation temperature, and like that one its uncertainty is not about this machine at all. It is read off the same tables and multiplied by a density from them. What its fraction covers is the choice of a single number for a property that moves: the product falls by about three percent between a cold feed and a boiling outlet, and this description carries one figure for the whole of that span. The fraction is sized to contain the span rather than to express a doubt about the tables, which is a different claim from every other figure here and is why it is stated separately.
- **Ambient** is not a property of the machine at all but of the room it stands in, and it moves. The fraction against it covers an ordinary indoor range rather than an error in a measurement, because there is no measurement — a machine commissioned in a cold garage sits at one end of it and one in a warm kitchen at the other.
- **The saturation temperature** is the tightest figure in the description, and the only one whose uncertainty is not really about the machine: water boils where the atmosphere says it does, so the fraction against it stands for the elevation and the weather the machine might be operated at rather than for any doubt about the steam tables.
- **The saturation slope** is read off the same tables and is arithmetically sound, but it is a local slope standing in for a curve. Its error is a property of where it is used rather than of the reading: close to saturation it is nearly exact, and well above — where the steam thermostat permits the mass to go — it understates the truth by a factor. The fraction is sized for the range the model may legitimately be used over. It is not a licence to use the model outside that range, which the omission below rules out entirely.

## What this description leaves out

Each of these is absent on purpose. Some belong to work not yet done, and some are outside what a plant description is for — but none of them is an oversight, and a design decision that depends on one is depending on something this description does not carry.

- **How completely the drawn water equilibrates.** The outlet relation relaxes the water fully towards the casting given enough time, and it does that at any draw whatever: raise the flow and the relaxation gets faster, but what it is heading for is still the casting's own temperature. That is a claim no real block could meet. Water pushed through fast enough leaves before it has taken all the heat on offer, and the faster it is pushed the further short it stops — so a real machine's delivered temperature falls with flow for a reason these relations have no term for. The consequence runs both ways and both are optimistic: the model overstates what the group receives at a high draw, and it overstates the droop too, because water that left cooler than the casting also took less out of it. Nothing here bounds the size of that. It is stated because a reader who has just seen a flow term arrive is entitled to think this was what arrived, and it is not — modelling how completely the water equilibrates would need a second coefficient and a relation this description does not carry.
- **What it costs the casting to warm the water it is holding.** `brew.outlet_held_volume_ml` names a real quantity of water — four millilitres at the declared value, which is about 16.6 J/K, a twentieth of the casting's own thermal mass — and the outlet relation moves that water's temperature freely. The casting's balance is never charged for the move. The only water term in that balance is the drawn one, which accounts for the stream leaving at the outlet temperature and for nothing else; the held volume's own thermal store sits outside it entirely, so a block bringing its held water up from cold appears to do so at no cost to itself. The case where this is largest is the one with no draw at all: with the pump closed the outlet still relaxes towards the casting at the conduction constant, so on this description an idle machine warms its held water from ambient to working temperature and loses nothing doing it. At the declared coefficients that is on the order of tens of watts averaged across the relaxation, against a 1000 W element and a 1.2 W/K loss — not a rounding. It is absent for the same reason the equilibration above is: charging it properly means carrying the held volume as a thermal mass in its own right, coupled to the casting in both directions, rather than as a lag on a temperature. What follows is that the model warms and recovers a little faster than a real block would, everywhere there is a gap between the two temperatures, and most visibly on a machine that has been standing.
- **The temperature dependence of what a millilitre of water costs.** `water.heat_capacity_j_per_ml_k` is one figure, and the property it stands for is not constant: it falls by about three percent between a cold feed and a boiling outlet, mostly through the density. The relations use the single figure at every temperature. This is small beside the other omissions here and is recorded rather than folded into that coefficient's assumed error, because an error fraction says how wrong a number may be and this says the number moves — which a margin calculation treats differently.
- **The mass and temperature of anything downstream** — group head, portafilter, the water already in the path. The outlet temperature here is the water as it leaves the casting, which is not the water at the puck: everything between the two is absent.
- **Any identification of the outlet coefficients from what the machine senses.** This description used to record something stronger here: that nothing the machine senses depends on the outlet coefficient at all. That is no longer true, and the change is worth being exact about. The energy the drawn water removes is taken at the water's temperature, so with a draw open the casting — which is where the brew sensor is, and the only reading this machine has — moves differently depending on where the water leaving it sits, and therefore differently for a different held volume or conduction constant. A prediction error computed against that sensor is no longer blind to them: it carries information about them, and an outlet coefficient that is wrong, or one that moves as the channel fouls, now produces a residual rather than nothing at all.

  Reachable is all that says. Nobody has estimated these coefficients from any data, of this machine or any other, and nothing here claims a figure identified rather than assumed. How much information that residual carries, whether it is enough to separate the two outlet coefficients from each other or from the loss coefficient, and what a draw would have to look like for it to be worth anything, are all open — and settling them needs a bench, because the residual only exists while water is actually being drawn and nothing about that has been run. What this description carries about these two coefficients is still an assumed error and nothing else. What has changed is that narrowing it is now a question of doing the work rather than of instrumenting the machine differently.
- **Any coupling between the two sides.** No shared water, no shared supply budget, no heat conducted between the blocks through the chassis. The supply budget is real on this machine and is reasoned about elsewhere; it is not in these equations.
- **The pump's flow-versus-pressure characteristic, and the puck.** Both pressure and flow follow the command — one with a time constant, the other immediately — and neither carries a resistance term. The model has no notion of what is downstream of the pump, so it cannot represent the coupling between the two that a real machine has through the coffee: a puck that tightens raises pressure and drops flow, and here the two are independent functions of one level. Nor can it represent the mechanical cap opening, which is where a real machine's delivered flow stops tracking what was asked for. Everything this description reports about water movement is therefore what was commanded, and there is nothing here from which what was delivered could be worked out.

  The two pump coefficients make the size of this concrete, and they have to be read together rather than one at a time. `pump.pressure_bar` is what the pump makes against a closed outlet, which is the zero-flow end of its characteristic; `pump.flow_ml_per_s` is what it delivers into an open path, which is the zero-pressure end. They are the two ends of one curve and no pump is at both ends at once, so a model at full duty reports a pressure and a rate that cannot occur together on this machine. Each is declared one-sided and reaching downwards for that reason, but a pair of one-sided figures is not a curve: nothing here says which pressure goes with which rate, and no argument that a given pressure implies a given flow can be made from this description. Sizing anything against both at once — a supply budget, a delivery time, an energy balance — takes the worst of two cases that exclude each other.
- **The hot-water path and the three-way valve.** The machine serialises espresso and hot water through one block in the plumbing. This description carries one brew path and cannot represent that contention.
- **Everything that makes element power vary.** `heater_power_w` is a fixed coefficient, and two real effects are folded flat into it. The supply is one: an element is a resistance, so power goes as the square of the voltage, and the declared 230–240 V spread alone is about 8% in delivered power — a sagging supply looks like nothing at all here. The element's own temperature is the other: its resistance rises as it heats, so it delivers slightly less power hot than cold. That second one does not average out, because it is in step with the heat-up this model is mostly used to reason about — the model will run slightly fast towards the end of a climb. Its size depends on the element alloy, which is not established; for a nichrome-type element it is on the order of a percent or two over the working range, which is smaller than the supply spread but systematic where the supply spread is not. Both belong in the error budget the description is reasoned against rather than in these equations.
- **Anything inside the casting.** Element-to-casting lag, gradients across the block, and where a sensor is bonded relative to the water channel are all collapsed into one uniform temperature.
- **Sensor behaviour.** No noise, no lag, no offset, no failure. The model answers with the state itself, and what a sensor would have reported is the measurement work's subject.
- **The protective devices.** Thermostats, thermal fuse and relief hardware are absent: the model will happily run a block past a trip point that would have opened on the real machine. Their trip points are declared in the reference-machine declaration.
- **Steam pressure anywhere but just above saturation.** `steam.pressure_bar_per_k` is the saturation line's *local* slope at 100 °C, and the saturation line is not a straight one. Extrapolated to the 200 °C the steam thermostat permits, this relation gives roughly a quarter of the real pressure. The steam side's behaviour near its protection limit is the one thing this description must not be used to reason about, and it is where the machine's largest open pressure question sits — see the pressure note in `../../docs/reference-machine.md`.
- **Steam quality and latent heat.** The steam relation is a pressure–temperature slope only. Nothing here says how much steam is available or what drawing it costs. The coffee side's flow term does not reach across: it is written from the brew path's drawn rate and takes energy out of the coffee block, and the steam mass loses energy to ambient and to nothing else. A steam draw is still free in these relations, and it is the larger of the two draws in energy terms because what it costs is mostly latent heat, which this description has no coefficient for at all.
- **Any shape to the error, beyond its size.** Each value now states how far out it may be, and nothing states anything else about that error. Nothing says whether a coefficient is as likely to be high as low — three of them are known to be one-sided, and the section above says which — and nothing says which errors move together. The element ratings are the case that matters: both are fed from one supply, so a sagging mains makes both low at once, and treating them as independent would understate the case where both elements are wanted. What a sweep is required to do about that is not settled here — it is stated once, as a criterion on the robustness verification, so that the rule lives where the sweep does rather than in a note beside the numbers.
