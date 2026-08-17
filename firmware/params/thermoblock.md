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

## What this description leaves out

Each of these is absent on purpose. Some belong to work not yet done, and some are outside what a plant description is for — but none of them is an oversight, and a design decision that depends on one is depending on something this description does not carry.

- **Water flow, and the energy it carries away.** Nothing here models water entering a block, being heated, and leaving. The masses lose energy only to ambient. This is the largest omission by far: during an extraction or a steam draw, flow dominates the thermal balance, and the model will understate the droop.
- **The mass and temperature of anything downstream** — group head, portafilter, the water already in the path. Brew temperature here is the casting's, not the water's at the puck.
- **Any coupling between the two sides.** No shared water, no shared supply budget, no heat conducted between the blocks through the chassis. The supply budget is real on this machine and is reasoned about elsewhere; it is not in these equations.
- **The pump's flow-versus-pressure characteristic, and the puck.** Pressure follows the command with a time constant and no resistance term; the model has no notion of what is downstream of the pump or of how much water moves.
- **The hot-water path and the three-way valve.** The machine serialises espresso and hot water through one block in the plumbing. This description carries one brew path and cannot represent that contention.
- **Mains voltage and frequency.** Element power is a coefficient, not a function of supply, so a sagging supply looks like nothing at all here.
- **Anything inside the casting.** Element-to-casting lag, gradients across the block, and where a sensor is bonded relative to the water channel are all collapsed into one uniform temperature.
- **Sensor behaviour.** No noise, no lag, no offset, no failure. The model answers with the state itself, and what a sensor would have reported is the measurement work's subject.
- **The protective devices.** Thermostats, thermal fuse and relief hardware are absent: the model will happily run a block past a trip point that would have opened on the real machine. Their trip points are declared in the reference-machine declaration.
- **Steam pressure anywhere but just above saturation.** `steam.pressure_bar_per_k` is the saturation line's *local* slope at 100 °C, and the saturation line is not a straight one. Extrapolated to the 200 °C the steam thermostat permits, this relation gives roughly a quarter of the real pressure. The steam side's behaviour near its protection limit is the one thing this description must not be used to reason about, and it is where the machine's largest open pressure question sits — see the pressure note in `../../docs/reference-machine.md`.
- **Steam quality and latent heat.** The steam relation is a pressure–temperature slope only. Nothing here says how much steam is available or what drawing it costs.
- **How wrong all of this is.** The error the design is entitled to assume against this description is required elsewhere and deliberately not stated here, so that one statement of it exists rather than two that can disagree.
