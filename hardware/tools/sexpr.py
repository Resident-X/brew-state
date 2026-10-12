"""Reading and writing KiCad's S-expression files.

KiCad's layout, schematic and custom-rules files are all one nested list
grammar: parenthesised lists of bare atoms and double-quoted strings. A rules
file may also carry `#` comments to the end of a line. This reads that grammar
into nested Python lists and writes it back, keeping a quoted string quoted and
its escapes as written, so a file that is read and written back unchanged means
to KiCad what it meant before.
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Union


class SexprError(ValueError):
    """The text is not a well-formed S-expression."""


class Quoted(str):
    """A double-quoted string, held as written between its quotes (escapes kept)."""


Node = Union[str, "List[Node]"]


def parse(text: str, comments: bool = False, spans: Optional[List[Tuple[int, int, int]]] = None) -> List[Node]:
    """Every top-level form in `text`, in order.

    `comments` allows `#` comments outside strings, which KiCad accepts in a
    custom rules file and nowhere else. A `spans` list given here receives, for
    each top-level form in turn, its (start, end) offsets in `text` and the line
    it starts on, so a form can be quoted or pointed at exactly as written.
    """
    stack: List[List[Node]] = [[]]
    i, n = 0, len(text)
    line = 1
    start, start_line = 0, 1
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif c in " \t\r":
            i += 1
        elif c == "#" and comments:
            while i < n and text[i] != "\n":
                i += 1
        elif c == "(":
            if len(stack) == 1:
                start, start_line = i, line
            stack.append([])
            i += 1
        elif c == ")":
            if len(stack) == 1:
                raise SexprError(f"unbalanced ')' at line {line}")
            done = stack.pop()
            stack[-1].append(done)
            i += 1
            if len(stack) == 1 and spans is not None:
                spans.append((start, i, start_line))
        elif c == '"':
            first, j = line, i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\":
                    j += 1
                elif text[j] == "\n":
                    line += 1
                j += 1
            if j >= n:
                raise SexprError(f"unterminated string starting at line {first}")
            stack[-1].append(Quoted(text[i + 1:j]))
            if len(stack) == 1 and spans is not None:
                spans.append((i, j + 1, first))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            stack[-1].append(text[i:j])
            if len(stack) == 1 and spans is not None:
                spans.append((i, j, line))
            i = j
    if len(stack) != 1:
        raise SexprError(f"{len(stack) - 1} unclosed '(' at end of text")
    return stack[0]


def parse_one(text: str) -> List[Node]:
    """The single top-level list a KiCad layout or schematic file is."""
    forms = parse(text)
    if len(forms) != 1 or not isinstance(forms[0], list):
        raise SexprError("expected exactly one top-level list")
    return forms[0]


def dump(node: Node, depth: int = 0) -> str:
    """Write a node back as text KiCad reads."""
    if isinstance(node, Quoted):
        return f'"{node}"'
    if isinstance(node, str):
        return node
    if not any(isinstance(child, list) for child in node):
        return "(" + " ".join(dump(child) for child in node) + ")"
    pad = "\t" * (depth + 1)
    text = "("
    for index, item in enumerate(node):
        if isinstance(item, list):
            text += "\n" + pad + dump(item, depth + 1)
        else:
            text += ("" if index == 0 else " ") + dump(item)
    return text + "\n" + "\t" * depth + ")"


def head(node: Node) -> str:
    """The keyword a list starts with, or '' for an atom or empty list."""
    if isinstance(node, list) and node and isinstance(node[0], str) and not isinstance(node[0], Quoted):
        return node[0]
    return ""


def children(node: Node, keyword: str) -> List[List[Node]]:
    """The direct child lists of `node` that start with `keyword`."""
    if not isinstance(node, list):
        return []
    return [child for child in node if head(child) == keyword]


def child(node: Node, keyword: str):
    """The first direct child list starting with `keyword`, or None."""
    found = children(node, keyword)
    return found[0] if found else None
