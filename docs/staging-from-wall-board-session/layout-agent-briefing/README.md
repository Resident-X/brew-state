# Briefing a layout agent (staged)

What this is: the project owner's standing rulings to the agent that lays out a board, written generically, with a note of which parts `docs/board-design-method.md` already carries and which are new. The proposed home is a subsection `### Briefing a layout agent` in the method's section "Placement, routing and review as practised on a dense mains board" (or beside it).

What it needs: nothing. It is text.

Proposed permanent home: `docs/board-design-method.md`, heading `### Briefing a layout agent`, new content only; then this subfolder is deleted.

Coverage against the method as it stands (section "Placement, routing and review as practised on a dense mains board", steps 1, 4 and 5):

| Ruling | In the method? |
| --- | --- |
| Owner of the board decides method, order, part moves, exceptions and stopping, and logs each | Covered in step 1 (the design owner and its sign-off list). New: the statement that the agent does not wait for the relaying session on these |
| Priority ranks: safety, neatness, performance rules that matter on this board, cost | Covered in step 1 |
| About 90 percent of an excellent engineer's result, 100 percent defined, residuals listed | Covered in step 1 |
| Neatness leads and the picture decides | Covered in step 5 |
| Stop after three send-backs on one area | Covered in step 4. New: report revised estimates honestly, with a checkpoint where stopping near 90 percent is possible |
| Relaxations listed for the owner's sign-off | Covered in step 1 (rule, nets, reason). New: the keep-strictly list is board-specific and belongs in the brief |
| The agent owns the board: may rework low-voltage copper and placement freely, never locks, never commits, mains copper only on the owner's instruction | Partly covered (locking rules in step 4). New: the ownership statement, placement changes committed before any unlocked copper is added, and the agent suggesting mains-side changes as written proposals |
| Mechanics: polling, reporting by message, delegation, at most four heavy processes | New |
| Plain language for a mechatronics engineer who is not an electrical engineer | New |

## Text for the subsection

### Briefing a layout agent

Give the agent that lays out a board the following, in the brief, as the owner's standing rulings. Adapt the bracketed parts to the board.

1. **The agent owns the method.** It decides method, order, helper pattern, part moves, exceptions, when to accept, when to change approach and when to stop, and logs each decision with its reason. It does not wait for the session that relays its work on these. That session verifies independently and imports.
2. **The goal and the ranking.** State the build the board is for (for example a one-shot ordered build that an experienced engineer reviewing it publicly would not call bad), that it is a hobby-grade open-source board, and the ranking: safety first, then neatness and workmanship, then the performance rules that matter on this board, then cost.
3. **The bar.** About 90 percent of what an excellent engineer could do with unlimited time on this placement. The agent defines what 100 percent would look like and lists the residual imperfections it accepts. Keep strict what a reviewer notices first: hooks, loops round placement mistakes, via thickets, long diagonals across other nets, wandering.
4. **Neatness leads, and the picture decides.** Legal but wandering copper is never accepted or locked. Numbers are proxies; the agent's judgement of the picture of each layer is the acceptance call, and the owner's side audits with pictures and a blind review.
5. **A stop-loss.** After three send-backs on one area without accepted progress, change the approach and do not send back a fourth time. The agent reports revised estimates honestly, with a checkpoint where stopping near 90 percent is possible.
6. **Relaxations are listed.** A rule that exists for behaviour the board does not have gives way to neatness. Each such relaxation is listed with its net, its rule and why this board does not need it, for the owner's sign-off. State in the brief which rules stay strict on this board (for the first board: mains clearance and creepage, the crystal's limits, sense and reference integrity, the data pair's basics and its protection, digital decoupling closeness, the stated bus as written, test-point reachability).
7. **Ownership and its limits.** The agent owns the board it works on. On the low-voltage side it may re-lay any copper, move or re-place parts including whole groups, change layer use, rework an area from scratch or change the helper pattern. It lists every part move and relaxation with reasons for the owner's sign-off. Placement changes are committed before any unlocked copper is added, so they are made early. On the mains side it may suggest changes as written proposals, when they improve the mains side or leave it unchanged and give a significant benefit to the low-voltage side; it never changes mains copper or clearances itself, unless the owner instructs it to for a named board. Never: locking, committing, connector pin order, anything outside its working folder.
8. **Mechanics.** The agent's prompt cache is short, so it polls helpers in steps shorter than the cache life and does not treat a lapse as a restart. It does not re-read files it knows. When reporting it sends a message (it does not end its turn) stating its context size and whether its state is captured, then waits for instructions. It keeps a hand-over file current. It keeps its own context lean by delegating reading, rendering and counting to cheaper helpers, and tells every helper to use the system clock, never to kill processes by name, and to run at most four heavy processes at once under a lowered priority.
9. **Plain language.** Reports are written for a mechatronics engineer who is not an electrical engineer: pictures with every judgement, and the part moves, relaxations and assumptions listed for the owner.
