# Coffee — a model-based controller for a dual-thermoblock espresso machine

Replacing the factory control board in a Sunbeam EM7000 with a controller that actually models the machine: state estimation, a forward horizon, flow and pressure profiling, and a hardware safety chain with no firmware anywhere in it.

This repository is **public domain**. Take any of it.

## What is here right now

A **requirement graph** and nothing else. No firmware, no board, no schematics of our own. That is deliberate — the requirements are being finished before the code starts, and this repo is partly an argument that doing it in that order is faster rather than slower.

So if you came looking for something to flash, it does not exist yet.

## Where to start reading

**If you want to know what this machine is meant to do**, read the personas and journeys first. They are written to be read by a person, not parsed by a tool:

- `specs/personas/` — three stakeholders. The **operator** who makes coffee, the **builder** who designs and commissions it, and the **adopter** who found this published and owns a different machine.
- `specs/journeys/` — what actually happens: pulling a shot, steaming a jug, serving a group, commissioning the plant, correcting drift, keeping the machine in condition.

**If you want to know what constrains it**, read `specs/obligations/`. These are the cross-cutting commitments — electrical and thermal safety, real-time discipline, control-design discipline, verification discipline, open-source maintainability, physical configuration control. The safety obligation is the only one whose authority is external to this project, and it outranks everything else in the graph.

**If you want the detail**, `specs/requirements/` holds the functional and constraint requirements, `specs/definitions/` the vocabulary, and `specs/decisions/` the choices that have been made and why — including the options that were rejected.

**If you are rebuilding this on your own machine**, read [`docs/reference-machine.md`](docs/reference-machine.md) first. Everything specific to *our* machine — supply voltage, mains frequency, element ratings, protection trip points — lives in that one file. The requirement graph is written without those values so that replacing that file is the whole job.

## Two different promises

Be clear about which of these you are:

- **Same architecture** (a dual-thermoblock machine): the graph should apply to you, and adapting it should mean supplying your own parameters rather than changing requirements.
- **Different architecture** (single boiler, heat exchanger): the requirements will not all fit — an HX group's temperature depends on time since the last shot, which has no representation in a thermoblock's state at any parameter values. What transfers is the **method**, the tooling and the safety architecture. That is a smaller promise, and it is the honest one.

## Reading the graph

Nodes are `.req.yaml` files — plain YAML with prose in them. You need nothing but a text editor.

**How they connect.** A requirement `derives-from` one or more *criteria* of the node above it, so the chain runs persona → journey → requirement, with each node carrying numbered criteria (`REQ-BREW-TEMP-001.C1`) attached by `criterion-of`. Obligations sit across the top: they are not part of that chain but constrain everything under them, and the safety obligation outranks the lot. Requirements also derive from each other's criteria where one genuinely builds on another. Decisions attach by `addresses`.

**Priorities.** Every requirement carries one:

| | |
|---|---|
| `must` | the system is wrong without it |
| `should` | real value, deliberately ranked below the musts |
| `could` | worth having, and shipping without it is not a defect |

Priority is about whether the system is wrong, not about when something gets built.

**The engine is not included.** The graph is managed by [Staircase](#staircase), whose CLI can navigate it (`show`, `trace`, `query`, `validate`). That tool is not part of this repository and is not currently something you can obtain, so everything here is written to be read without it. If you have it, `show <ID>` and `trace <ID>` are the two worth knowing.

## Staircase

This project is built with Staircase, whose thesis is that disciplined, requirement-driven, complete-the-first-time engineering produces better software, faster, that stays maintainable. This repo is partly a test of that claim in public, on a real physical thing that can burn someone.

One discipline is worth knowing about while reading: **requirements state properties, not mechanisms.** You will not find part numbers, sensor technologies, interface choices or tuning constants in `specs/`. Those are decisions and they live separately. That is also what makes the graph portable to a machine on a different continent running on a different voltage — a requirement that names a mechanism does not travel.

## Status

Requirement graph in progress. Not yet complete, not yet built, not yet verified against anything.
