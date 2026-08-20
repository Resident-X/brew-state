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

advanced over a step by the exact solution for a constant duty, rather than by assuming the rate held. Per side:

| Coefficient | Enters as | Unit |
|---|---|---|
| `brew.thermal_mass_j_per_k` / `steam.thermal_mass_j_per_k` | `C`, the energy that raises the casting by one kelvin | J/K |
| `brew.heater_power_w` / `steam.heater_power_w` | `P`, the element's power at full duty | W |
| `brew.loss_w_per_k` / `steam.loss_w_per_k` | `k`, the loss per kelvin above ambient | W/K |
| `ambient_temperature_c` | `T_ambient`, shared by both masses and the state both start from | °C |

The two masses are independent. Nothing in these relations couples one to the other — which is a property of this machine, whose blocks are separately heated and not plumbed in series.

**The water on its way to the group.** A first-order relaxation towards the casting it has just passed through:

    τ · dT_outlet/dt = T_brew − T_outlet

| Coefficient | Enters as | Unit |
|---|---|---|
| `brew.outlet_time_constant_s` | `τ`, how far the water the group receives lags the casting | s |

The element does not appear in this relation, and that is the whole of it: the heater reaches the water only through the casting. Nor does the water appear anywhere else: nothing downstream of the casting enters any other relation here, which is what the omissions below say about identifying this coefficient. Set `τ` small enough and the two temperatures become one, which is the model this description used to be — so the coefficient is also the measure of how much of a distinction is being claimed. What it stands for is a residence time and a length of tube rather than a thermal capacity, so it is not derived from the coefficients above and cannot be.

Advanced over a step by the exact solution for a casting that traverses the step linearly, rather than by holding the casting at either end of its traverse. Holding it would be first-order in the step length, and every other relation here is exact for its own step — the pressure relations because what they relax towards really is constant across a step, and the masses because the closed form for a constant duty is available.

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

Nothing else enters. There is no resistance term, so what the water is being pushed through makes no difference to this figure: the same duty reports the same rate through an open path, through a fresh puck and through a blocked one. That is the rate commanded, not the rate a cup received, and the gap between the two is the puck, the pump's flow-versus-pressure characteristic and the mechanical cap — all three of which remain among the omissions at the end of this statement. Nothing in this description consumes this rate either: it is reported so that a loop commanding flow has something to close against and a meter's reading has something to be compared with, and the energy the moving water would carry out of the casting is still absent from the relations above.

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
- **The outlet time constant** is the widest fraction in the description, and it is wide for a different reason from the loss coefficients: those are known to be wrong in a direction, and this one is barely known at all. It stands for a residence time and a run of tube that have not been measured, and measuring them is not cheap — it needs a temperature at the group during an extraction, which is precisely the reading this machine is not instrumented to take. It is also the coefficient that decides how much of a gap there is between the casting and the water, so anything reconstructing the water from a reading of the casting — which is the only reading this machine has — is sensitive to it directly. A narrow fraction here would be a claim nobody is in a position to make.
- **Ambient** is not a property of the machine at all but of the room it stands in, and it moves. The fraction against it covers an ordinary indoor range rather than an error in a measurement, because there is no measurement — a machine commissioned in a cold garage sits at one end of it and one in a warm kitchen at the other.
- **The saturation temperature** is the tightest figure in the description, and the only one whose uncertainty is not really about the machine: water boils where the atmosphere says it does, so the fraction against it stands for the elevation and the weather the machine might be operated at rather than for any doubt about the steam tables.
- **The saturation slope** is read off the same tables and is arithmetically sound, but it is a local slope standing in for a curve. Its error is a property of where it is used rather than of the reading: close to saturation it is nearly exact, and well above — where the steam thermostat permits the mass to go — it understates the truth by a factor. The fraction is sized for the range the model may legitimately be used over. It is not a licence to use the model outside that range, which the omission below rules out entirely.

## What this description leaves out

Each of these is absent on purpose. Some belong to work not yet done, and some are outside what a plant description is for — but none of them is an oversight, and a design decision that depends on one is depending on something this description does not carry.

- **The energy water carries away.** The rate water is drawn is now reported — it is the fifth quantity above — but nothing in these relations spends anything to move it. No water enters a block, is heated and leaves; the masses lose energy only to ambient, and the drawn rate is reported beside the equations rather than appearing in any of them. This remains the largest omission by far: during an extraction or a steam draw, flow dominates the thermal balance, and the model will understate the droop by as much as it did before the rate existed. Reporting a rate is not modelling what it costs, and the presence of the quantity must not be read as the omission being closed. The outlet relation does not soften it either. It carries the casting's temperature to the water with a lag and takes no energy out of the casting to do it, so it is a description of delay and not of flow — and its time constant is fixed rather than moving with the rate now reported, which on a real machine is what would set it.
- **The mass and temperature of anything downstream** — group head, portafilter, the water already in the path. The outlet temperature here is the water as it leaves the casting, which is not the water at the puck: everything between the two is absent.
- **Any way to identify the outlet time constant from what the machine senses.** This is a consequence of the first omission rather than a separate choice, and it is the sharpest limit in this description. The machine's only brew temperature sensor is in the casting, and the outlet relation is downstream of it — the water takes nothing out of the casting in these equations, so nothing the sensor reads depends on that coefficient. A prediction error computed against that sensor is therefore blind to it, and so is anything built on such an error: an outlet constant that is wrong, or one that moves as the water channel fouls, produces no residual at all rather than a small one. What this description carries about that coefficient is an assumed error and nothing else, and no run of the machine as it stands can narrow it. Closing it needs either a flow term in the relations above, which would make the casting's own reading depend on what is drawn through it, or an observation downstream of the casting. Which of those is the answer is not settled here. The drawn rate being reported as a quantity does not begin to close it: the limit is that nothing the brew sensor reads depends on the outlet coefficient, and a rate that enters none of the relations changes nothing about what that sensor reads.
- **Any coupling between the two sides.** No shared water, no shared supply budget, no heat conducted between the blocks through the chassis. The supply budget is real on this machine and is reasoned about elsewhere; it is not in these equations.
- **The pump's flow-versus-pressure characteristic, and the puck.** Both pressure and flow follow the command — one with a time constant, the other immediately — and neither carries a resistance term. The model has no notion of what is downstream of the pump, so it cannot represent the coupling between the two that a real machine has through the coffee: a puck that tightens raises pressure and drops flow, and here the two are independent functions of one level. Nor can it represent the mechanical cap opening, which is where a real machine's delivered flow stops tracking what was asked for. Everything this description reports about water movement is therefore what was commanded, and there is nothing here from which what was delivered could be worked out.

  The two pump coefficients make the size of this concrete, and they have to be read together rather than one at a time. `pump.pressure_bar` is what the pump makes against a closed outlet, which is the zero-flow end of its characteristic; `pump.flow_ml_per_s` is what it delivers into an open path, which is the zero-pressure end. They are the two ends of one curve and no pump is at both ends at once, so a model at full duty reports a pressure and a rate that cannot occur together on this machine. Each is declared one-sided and reaching downwards for that reason, but a pair of one-sided figures is not a curve: nothing here says which pressure goes with which rate, and no argument that a given pressure implies a given flow can be made from this description. Sizing anything against both at once — a supply budget, a delivery time, an energy balance — takes the worst of two cases that exclude each other.
- **The hot-water path and the three-way valve.** The machine serialises espresso and hot water through one block in the plumbing. This description carries one brew path and cannot represent that contention.
- **Everything that makes element power vary.** `heater_power_w` is a fixed coefficient, and two real effects are folded flat into it. The supply is one: an element is a resistance, so power goes as the square of the voltage, and the declared 230–240 V spread alone is about 8% in delivered power — a sagging supply looks like nothing at all here. The element's own temperature is the other: its resistance rises as it heats, so it delivers slightly less power hot than cold. That second one does not average out, because it is in step with the heat-up this model is mostly used to reason about — the model will run slightly fast towards the end of a climb. Its size depends on the element alloy, which is not established; for a nichrome-type element it is on the order of a percent or two over the working range, which is smaller than the supply spread but systematic where the supply spread is not. Both belong in the error budget the description is reasoned against rather than in these equations.
- **Anything inside the casting.** Element-to-casting lag, gradients across the block, and where a sensor is bonded relative to the water channel are all collapsed into one uniform temperature.
- **Sensor behaviour.** No noise, no lag, no offset, no failure. The model answers with the state itself, and what a sensor would have reported is the measurement work's subject.
- **The protective devices.** Thermostats, thermal fuse and relief hardware are absent: the model will happily run a block past a trip point that would have opened on the real machine. Their trip points are declared in the reference-machine declaration.
- **Steam pressure anywhere but just above saturation.** `steam.pressure_bar_per_k` is the saturation line's *local* slope at 100 °C, and the saturation line is not a straight one. Extrapolated to the 200 °C the steam thermostat permits, this relation gives roughly a quarter of the real pressure. The steam side's behaviour near its protection limit is the one thing this description must not be used to reason about, and it is where the machine's largest open pressure question sits — see the pressure note in `../../docs/reference-machine.md`.
- **Steam quality and latent heat.** The steam relation is a pressure–temperature slope only. Nothing here says how much steam is available or what drawing it costs.
- **Any shape to the error, beyond its size.** Each value now states how far out it may be, and nothing states anything else about that error. Nothing says whether a coefficient is as likely to be high as low — three of them are known to be one-sided, and the section above says which — and nothing says which errors move together. The element ratings are the case that matters: both are fed from one supply, so a sagging mains makes both low at once, and treating them as independent would understate the case where both elements are wanted. What a sweep is required to do about that is not settled here — it is stated once, as a criterion on the robustness verification, so that the rule lives where the sweep does rather than in a note beside the numbers.
