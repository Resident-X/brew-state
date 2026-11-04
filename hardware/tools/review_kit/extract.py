"""The extract of a deterministic check's report that a root holds.

A check that reads the design and lists its results gives a report whose lines each name the rule they are about. A unit
declares the rules it judges (`check_rules`); the extract of a root is the report's own lines for the union of the rules of the units of the groups it serves, in the
report's order, so a reviewer cites the check's figure and does not measure the design again. Nothing is
computed here: a line is kept whole or left out, so a figure the report did not carry is not in the extract. The declaration
says which artefact is the report and the pattern that reads the rule out of a line.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import catalogue as cat

#: The name an extract artefact takes beside the report it is cut from; a name in the folder `extract`.
NAME_FOLDER = "extract"


def missing_line(rules: Sequence[str]) -> str:
    """The closing line an extract carries for the declared rules the report holds no line for."""
    return f"The check's report holds no line for the rules: {', '.join(rules)}.\n"


class Extractor:
    """The lines of one report by rule, read with the declaration's pattern, and the extract any set of rules makes."""

    def __init__(self, report: cat.Measured, pattern: "re.Pattern[str]"):
        self.report = report
        self.lines: List[Tuple[Optional[str], str]] = []
        self.block: Dict[str, int] = {}
        for line in report.data.decode("utf-8").splitlines():
            found = pattern.search(line)
            rule = found.group("rule").strip() if found else None
            self.lines.append((rule, line))
            if rule is not None:
                self.block[rule] = self.block.get(rule, 0) + len(line) + 1

    @property
    def name(self) -> str:
        return f"{NAME_FOLDER}/{self.report.name}"

    def missing(self, rules: Iterable[str]) -> List[str]:
        """The rules, sorted, that the report holds no line for."""
        return sorted(rule for rule in set(rules) if rule not in self.block)

    def text(self, rules: Iterable[str]) -> str:
        """The report's lines for the rules, in the report's order, then the closing line for a rule with none."""
        wanted = set(rules)
        body = "".join(line + "\n" for rule, line in self.lines if rule in wanted)
        absent = self.missing(wanted)
        return body + (missing_line(absent) if absent else "")

    def size(self, rules: Iterable[str]) -> int:
        """The characters `text` holds for the rules, without building it."""
        wanted = set(rules)
        absent = self.missing(wanted)
        return sum(self.block.get(rule, 0) for rule in wanted) + (len(missing_line(absent)) if absent else 0)

    def artefact(self, rules: Iterable[str]) -> cat.Measured:
        """The extract as an artefact of a root, measured as any text is: by its length."""
        text = self.text(rules)
        data = text.encode("utf-8")
        return cat.Measured(self.name, "extract", self.report.source, hashlib.sha256(data).hexdigest(), len(text), True, data)
