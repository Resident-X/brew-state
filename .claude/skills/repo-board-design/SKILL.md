---
name: repo-board-design
description: Entry point for designing or reviewing a controller board in KiCad with the agent. Use for any board design, layout, routing or pre-order work. It loads Konnect's KiCad skills and hands every instruction to docs/board-design-method.md.
---

# Board design

The single source of every instruction is [`docs/board-design-method.md`](../../../docs/board-design-method.md). Read it before doing anything else, and follow it in the order it gives. This skill adds nothing to it.

- Load Konnect's bundled skills as they ship, without editing them: `konnect`, `kicad-schematic`, `kicad-pcb`, `kicad-library`, `kicad-review` and `kicad-manufacture`.
- Do all board work in the main session. Tools Konnect loads mid-session are not visible to subagents.
- Where a bundled Konnect skill conflicts with the method, the method governs.
