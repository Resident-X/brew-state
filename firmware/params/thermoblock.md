# What the thermoblock description represents

This is the statement that goes with `thermoblock.params`. It is read with the values rather than instead of them: the file holds a list of numbers, and a list of numbers cannot be checked against a machine and cannot be extended without guessing what its author meant.

It says what each quantity stands for, what unit it is carried in, which relations link them, and — at the end, and just as deliberately — what the description leaves out. A quantity omitted here is one the design cannot reason about, and a reader has no other way to tell an omission from an oversight.

Whether these relations match the machine's measured behaviour is not settled here and cannot be until the machine is on the bench. What is settled here is that the description says what it claims.

## The machine this describes

The reference machine declared in `../../docs/reference-machine.md`: two independently heated thermoblocks, one serving espresso and hot water, the other serving steam only. A thermoblock is a casting with an element embedded in it and a water channel passing through it. It heats water as the water flows past and holds no reservoir, which is why the description carries a thermal mass and no stored volume.

## The states the structure integrates

Each is a field the model advances from one step to the next. All four are single precision, as everything crossing the seam is.

| State | Physical thing | Unit |
|---|---|---|
| `brew_temperature_c` | Bulk temperature of the coffee thermoblock's casting, taken as uniform | °C |
| `steam_temperature_c` | Bulk temperature of the steam thermochamber's casting, taken as uniform | °C |
| `brew_pressure_bar` | Pressure in the brew path between the pump and the group | bar, gauge |
| `steam_pressure_bar` | Pressure in the steam path | bar, gauge |

`steam_pressure_bar` is held alongside the others but is not integrated independently: every step recomputes it from `steam_temperature_c` through the saturation relation below. It is a state in the record and a function in the equations, and treating it as though it had its own dynamics would be wrong.

## The quantities the seam exposes

These are what a consumer can read back through `plant_model_quantity`. Each is answered from exactly one state, in the same unit.

| Quantity | Answered from |
|---|---|
| `PLANT_QUANTITY_BREW_TEMPERATURE_C` | `brew_temperature_c` |
| `PLANT_QUANTITY_STEAM_TEMPERATURE_C` | `steam_temperature_c` |
| `PLANT_QUANTITY_BREW_PRESSURE_BAR` | `brew_pressure_bar` |
| `PLANT_QUANTITY_STEAM_PRESSURE_BAR` | `steam_pressure_bar` |

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

advanced over a step by the exact solution for a constant duty, rather than by assuming the rate held. Per side:

| Coefficient | Enters as | Unit |
|---|---|---|
| `brew.thermal_mass_j_per_k` / `steam.thermal_mass_j_per_k` | `C`, the energy that raises the casting by one kelvin | J/K |
| `brew.heater_power_w` / `steam.heater_power_w` | `P`, the element's power at full duty | W |
| `brew.loss_w_per_k` / `steam.loss_w_per_k` | `k`, the loss per kelvin above ambient | W/K |
| `ambient_temperature_c` | `T_ambient`, shared by both masses and the state both start from | °C |

The two masses are independent. Nothing in these relations couples one to the other — which is a property of this machine, whose blocks are separately heated and not plumbed in series.

**Brew pressure.** A first-order relaxation towards what the pump is commanding:

    τ · dp/dt = pump.pressure_bar · duty − p

| Coefficient | Enters as | Unit |
|---|---|---|
| `pump.pressure_bar` | The pressure the brew path settles to at full pump duty — the asymptote of the relation above, not the pump's closed-outlet rating, though it is the rating this description estimates it from | bar |
| `brew.pressure_time_constant_s` | `τ`, how fast the path reaches it | s |

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
- **The brew path's time constant** comes from comparable machines rather than from this one, whose compliance and fill volume are not established. It is also the coefficient the extraction transient is most sensitive to, so it carries about half the value: a coefficient that is both poorly known and influential is where a narrow assumed error does the most damage.
- **Ambient** is not a property of the machine at all but of the room it stands in, and it moves. The fraction against it covers an ordinary indoor range rather than an error in a measurement, because there is no measurement — a machine commissioned in a cold garage sits at one end of it and one in a warm kitchen at the other.
- **The saturation temperature** is the tightest figure in the description, and the only one whose uncertainty is not really about the machine: water boils where the atmosphere says it does, so the fraction against it stands for the elevation and the weather the machine might be operated at rather than for any doubt about the steam tables.
- **The saturation slope** is read off the same tables and is arithmetically sound, but it is a local slope standing in for a curve. Its error is a property of where it is used rather than of the reading: close to saturation it is nearly exact, and well above — where the steam thermostat permits the mass to go — it understates the truth by a factor. The fraction is sized for the range the model may legitimately be used over. It is not a licence to use the model outside that range, which the omission below rules out entirely.

## What this description leaves out

Each of these is absent on purpose. Some belong to work not yet done, and some are outside what a plant description is for — but none of them is an oversight, and a design decision that depends on one is depending on something this description does not carry.

- **Water flow, and the energy it carries away.** Nothing here models water entering a block, being heated, and leaving. The masses lose energy only to ambient. This is the largest omission by far: during an extraction or a steam draw, flow dominates the thermal balance, and the model will understate the droop.
- **The mass and temperature of anything downstream** — group head, portafilter, the water already in the path. Brew temperature here is the casting's, not the water's at the puck.
- **Any coupling between the two sides.** No shared water, no shared supply budget, no heat conducted between the blocks through the chassis. The supply budget is real on this machine and is reasoned about elsewhere; it is not in these equations.
- **The pump's flow-versus-pressure characteristic, and the puck.** Pressure follows the command with a time constant and no resistance term; the model has no notion of what is downstream of the pump or of how much water moves.
- **The hot-water path and the three-way valve.** The machine serialises espresso and hot water through one block in the plumbing. This description carries one brew path and cannot represent that contention.
- **Everything that makes element power vary.** `heater_power_w` is a fixed coefficient, and two real effects are folded flat into it. The supply is one: an element is a resistance, so power goes as the square of the voltage, and the declared 230–240 V spread alone is about 8% in delivered power — a sagging supply looks like nothing at all here. The element's own temperature is the other: its resistance rises as it heats, so it delivers slightly less power hot than cold. That second one does not average out, because it is in step with the heat-up this model is mostly used to reason about — the model will run slightly fast towards the end of a climb. Its size depends on the element alloy, which is not established; for a nichrome-type element it is on the order of a percent or two over the working range, which is smaller than the supply spread but systematic where the supply spread is not. Both belong in the error budget the description is reasoned against rather than in these equations.
- **Anything inside the casting.** Element-to-casting lag, gradients across the block, and where a sensor is bonded relative to the water channel are all collapsed into one uniform temperature.
- **Sensor behaviour.** No noise, no lag, no offset, no failure. The model answers with the state itself, and what a sensor would have reported is the measurement work's subject.
- **The protective devices.** Thermostats, thermal fuse and relief hardware are absent: the model will happily run a block past a trip point that would have opened on the real machine. Their trip points are declared in the reference-machine declaration.
- **Steam pressure anywhere but just above saturation.** `steam.pressure_bar_per_k` is the saturation line's *local* slope at 100 °C, and the saturation line is not a straight one. Extrapolated to the 200 °C the steam thermostat permits, this relation gives roughly a quarter of the real pressure. The steam side's behaviour near its protection limit is the one thing this description must not be used to reason about, and it is where the machine's largest open pressure question sits — see the pressure note in `../../docs/reference-machine.md`.
- **Steam quality and latent heat.** The steam relation is a pressure–temperature slope only. Nothing here says how much steam is available or what drawing it costs.
- **Any shape to the error, beyond its size.** Each value now states how far out it may be, and nothing states anything else about that error. Nothing says whether a coefficient is as likely to be high as low — two of them are known to be one-sided, and the section above says which — and nothing says which errors move together. The element ratings are the case that matters: both are fed from one supply, so a sagging mains makes both low at once, and treating them as independent would understate the case where both elements are wanted. What a sweep is required to do about that is not settled here — it is stated once, as a criterion on the robustness verification, so that the rule lives where the sweep does rather than in a note beside the numbers.
