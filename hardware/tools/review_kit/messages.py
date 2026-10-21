"""The messages a review sends: the shared context every session continues from, a unit's prompt, and a repair turn.

The shared context is one stream-json user message: text blocks and base64 image
blocks, one artefact after another in a fixed order (by name), with no unit's
prompt in it and no request to use a tool. The same declaration and review
folder give the same bytes and so the same prefix hash, which is what lets a
rerun hit the cache. A unit's prompt is its template with the named slots filled
by the unit's items and declared values.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from string import Formatter
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import catalogue as cat
from . import decl
from . import session as sess

#: What a shared-context node answers, so that its stream is told from one that did anything else.
ACK = "ACK"
INTRO = ("This message holds the material that the sessions continuing from here share. Read it as the evidence for the "
         "tasks they are each given. Do not judge anything and do not use a tool now.")
ENDING = f"Hold this for the sessions that continue from here; answer only {ACK}."


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def header(artefact: cat.Measured) -> str:
    """The line that names an artefact in the message; an image's is the form the stream reduction recognises."""
    return f"=== image: {artefact.name} ===" if artefact.kind == "image" else f"=== {artefact.name} ==="


@dataclass(frozen=True)
class SharedContext:
    """The shared-context message with its hash and size.

    `tokens` is the measured size: the artefacts' measured sizes and the framing text, by the catalogue's own measures.
    `blocks` pairs each artefact with the hash of its content, in the order the message holds them.
    """

    message: str
    prefix_sha: str
    tokens: int
    framing_tokens: int
    blocks: Tuple[Tuple[str, str], ...]

    def as_dict(self) -> Dict[str, Any]:
        return {"prefix_sha": self.prefix_sha, "tokens": self.tokens, "framing_tokens": self.framing_tokens,
                "artefacts": [{"name": name, "sha256": digest} for name, digest in self.blocks]}


def shared_context(catalogue: cat.Catalogue) -> SharedContext:
    """The one message every session of the review continues from."""
    blocks: List[Dict[str, Any]] = [sess.text_block(INTRO)]
    framing = len(INTRO) + len(ENDING)
    for artefact in catalogue.artefacts:
        head = header(artefact)
        if artefact.kind == "image":
            blocks.append(sess.text_block(head))
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": artefact.media_type,
                                                       "data": base64.b64encode(artefact.data).decode("ascii")}})
            framing += len(head)
        else:
            blocks.append(sess.text_block(head + "\n" + artefact.data.decode("utf-8")))
            framing += len(head) + 1
    blocks.append(sess.text_block(ENDING))
    message = sess.user_message(blocks)
    return SharedContext(message, sha256(message), catalogue.tokens + framing, framing,
                         tuple((artefact.name, artefact.sha256) for artefact in catalogue.artefacts))


def slots_in(template: str) -> List[str]:
    return [name for _, name, _, _ in Formatter().parse(template) if name is not None]


def unit_prompt(declaration: decl.Declaration, unit_id: str, items: Optional[Sequence[str]] = None) -> str:
    """The unit's prompt: its template with the slots filled by the unit's items, the result tables in plain terms and the
    declared values. `items` overrides the order of the items (a replica's variant), never which ones."""
    unit = declaration.units[unit_id]
    order = list(items) if items is not None else list(unit.items)
    if sorted(order) != sorted(unit.items):
        raise ValueError(f"unit {unit_id}'s prompt was given items other than the unit's own")
    filled = dict(unit.values)
    filled.update({"unit": unit_id, "items": "\n".join(f"- {item}" for item in order),
                   "schema": decl.describe(declaration.shape)})
    template = declaration.templates[unit.template]
    return template.format(**{name: filled[name] for name in slots_in(template)})


def group_prompt(declaration: decl.Declaration, units: Sequence[str], orders: Optional[Dict[str, Sequence[str]]] = None,
                 framing: str = "") -> str:
    """The prompt of a group of units: each unit's prompt, one after another, under a line naming it. A group of one unit
    is that unit's prompt as it stands. `framing` is a replica's added opening."""
    orders = orders or {}
    parts = [unit_prompt(declaration, unit, orders.get(unit)) for unit in units]
    body = parts[0] if len(parts) == 1 else "\n\n".join(f"## Unit {unit}\n{part}" for unit, part in zip(units, parts))
    return (framing.rstrip() + "\n\n" + body) if framing else body


def prompt_message(prompt: str) -> str:
    return sess.user_message([sess.text_block(prompt)])


def repair_prompt(problems: Sequence[str]) -> str:
    """The turn that asks a session to correct its own answer."""
    listed = "\n".join(f"- {problem}" for problem in problems)
    return ("Your answer has these problems:\n" + listed + "\n\nReturn the whole corrected answer, every table in full, and "
            "change nothing the problems do not require.")


def make_spec(declaration: decl.Declaration, tools: Sequence[str], cwd: str, model: Optional[str] = None,
              system: Optional[str] = None, append_system: Optional[str] = None) -> sess.SessionSpec:
    """The one specification every session of the review starts from, its result schema derived from the declared tables."""
    return sess.SessionSpec(tuple(tools), cwd, model, system, append_system, declaration.json_schema())


def measured_size(message: str) -> int:
    """The size of a message re-measured from its own blocks: a text by its length, an image by the patch formula on its
    decoded header. For a message of texts without recorded counts, it equals `SharedContext.tokens`."""
    total = 0
    for block in json.loads(message)["message"]["content"]:
        if block["type"] == "text":
            total += len(block["text"])
        elif block["type"] == "image":
            header_found = cat.image_size(base64.b64decode(block["source"]["data"]))
            total += cat.image_tokens(header_found[1], header_found[2]) if header_found else 0
    return total
