# Staging folder: the wall board session's reusable tools

This folder is temporary. It exists so that tools and notes made while laying out the heater wall board are held in the repository, not on a laptop, until each is placed in its proper home. A graph maintenance item per subfolder resolves it: the item moves the content to its home, proves it, and deletes the subfolder. When the last subfolder is gone, this folder and this file are deleted too.

Nothing here is part of the design record, the tooling or the verification. Nothing here is run by any test or gate: the folder sits under `docs/` and none of the round gate's tiers read it.

| Subfolder | What it holds | Proposed permanent home | Maintenance item |
| --- | --- | --- | --- |
| `wall-board-layout-scripts/` | The text-edit and silk scripts that produced the wall board's routing passes and silk changes, and the change logs of each pass | `hardware/sunbeam-em7000/heater-wall-board/` (board-specific edit scripts) and `hardware/tools/` (the generic ones), reconciled with the scripted-layout-tools leaf | SOL-WALL-BOARD-LAYOUT-SCRIPTS-ARE-TRACKED-AT-THEIR-HOME-AND-THE-STAGING-FOLDER-IS-GONE |
| `brew-state-artifact/` | The generators of the Brew State web page, the verified 3D placement corrections, the main board hero render settings | `hardware/tools/` plus the machine-record folder, regenerable from tracked board files | SOL-BREW-STATE-ARTIFACT-IS-REGENERABLE-FROM-TRACKED-FILES-AND-THE-STAGING-FOLDER-IS-GONE |
| `layout-agent-briefing/` | The owner's standing rulings to a layout agent, written generically, and which parts the method already carries | `docs/board-design-method.md`, as `### Briefing a layout agent` | SOL-METHOD-CARRIES-A-BRIEFING-A-LAYOUT-AGENT-SUBSECTION-AND-THE-STAGING-FOLDER-IS-GONE |
| `review-dispatch-note.md` | How a pending workflow interrupt is run headless | The memory-only decision is recorded in this file's own section below | none (see below) |

## What was scrubbed

- Every absolute local path (the owner's home folder, the session scratchpad, a worktree, a render helper) was replaced with a placeholder (`<repo>`), an argument, or an environment variable. Two files had any: `brew-state-artifact/layer_views_c.py` (now reads `BOARD_TOOLS`, `KICAD_CLI` and `WORK_DIR` from the environment, and calls `resvg` from the search path) and `wall-board-layout-scripts/verify_one.py` (now defaults `--root` to the current folder and `--kicad-cli` to `KICAD_CLI` or `kicad-cli`). The `KPY` constant in three edit scripts names KiCad's own bundled interpreter at its standard macOS install location; it is an install default and is documented in the scripts' README.
- No logic was otherwise changed. Every Python file still parses (`python3 -m py_compile`); none was run.
- A search of every file for token, secret, api key, password, bearer, Authorization and e-mail patterns found one hit, the word "tokens" in a docstring meaning text tokens in a KiCad file. The Brew State page was searched the same way, byte-wise: no hit; its only external addresses are the page's script CDN and font host.

## Not staged

- `add_maker.py`: no file of that name exists on the machine. The maker-line insertion is in `wall-board-layout-scripts/add_legend.py` (the logo, maker line and coat keep-out marks).
- `r4/CHANGES.txt`: absent.
- `silk_copper.py` appears once: the final-pass and round-7 copies were byte-identical.

## The review-dispatch recipe

Kept as `review-dispatch-note.md` (a recipe, not the script). The repository records no workflow-run recipes outside the engine's own skills, so no graph node was authored for it; whoever resolves this folder decides whether the note belongs in the operator skills or is dropped.
