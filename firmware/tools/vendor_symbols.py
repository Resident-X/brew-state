"""Detection of vendor symbols in C source.

A vendor symbol is anything that ties a translation unit to the target
microcontroller: a device or HAL header, a HAL or CMSIS identifier, a
peripheral instance name, or a macro the build system injects to say which
device is being built for. The control logic is not allowed to name any of
them -- it reaches hardware through the seam instead -- so this module is the
one place that says what "naming the vendor" means, and both the encapsulation
check and the header check use it.

Detection runs over source with comments and string literals removed, so a
symbol mentioned in a comment is not a violation while the same token in code
is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Header names that only a translation unit tied to the target would include.
VENDOR_INCLUDE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^stm32.*\.h$", re.IGNORECASE),
    re.compile(r"^system_stm32.*\.h$", re.IGNORECASE),
    re.compile(r"^core_c[mr][0-9].*\.h$", re.IGNORECASE),
    re.compile(r"^cmsis.*\.h$", re.IGNORECASE),
    re.compile(r"^arm_.*\.h$", re.IGNORECASE),
    re.compile(r".*_hal(_[a-z0-9_]+)?\.h$", re.IGNORECASE),
    re.compile(r".*_ll_[a-z0-9_]+\.h$", re.IGNORECASE),
)

#: Identifiers that name the vendor's API, its peripherals, or the build's device.
VENDOR_IDENTIFIER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("HAL function or macro", re.compile(r"\b__?HAL_[A-Za-z0-9_]+\b")),
    ("HAL function or macro", re.compile(r"\bHAL_[A-Za-z0-9_]+\b")),
    ("HAL type", re.compile(r"\b[A-Za-z0-9_]+_(HandleTypeDef|InitTypeDef|TypeDef)\b")),
    ("low-layer driver call", re.compile(r"\bLL_[A-Za-z0-9_]+\b")),
    ("CMSIS core intrinsic", re.compile(r"\b__(NOP|WFI|WFE|DSB|DMB|ISB|enable_irq|disable_irq|get_[A-Z]+|set_[A-Z]+)\b")),
    ("CMSIS core symbol", re.compile(r"\b(NVIC|SCB|SysTick|ITM|DWT|CoreDebug)\b")),
    ("peripheral instance", re.compile(r"\b(GPIO[A-K]|TIM[0-9]+|ADC[0-9]+|DAC[0-9]+|USART[0-9]+|UART[0-9]+|SPI[0-9]+|I2C[0-9]+|DMA[0-9]+|CAN[0-9]+|RTC|IWDG|WWDG|RCC|PWR|FLASH|EXTI)\b")),
    ("device family macro", re.compile(r"\bSTM32[A-Za-z0-9_]*\b", re.IGNORECASE)),
    ("inline assembly", re.compile(r"\b(?:__asm__|__asm|asm)\b")),
    (
        "memory-mapped register address",
        re.compile(r"\(\s*(?:const\s+)?volatile[A-Za-z0-9_ \t*]*\*\s*\)\s*0[xX][0-9A-Fa-f]+"),
    ),
    ("build-injected macro", re.compile(r"\b(USE_HAL_DRIVER|USE_FULL_LL_DRIVER|PLATFORMIO|ARDUINO|F_CPU|HSE_VALUE|HSI_VALUE)\b")),
)

_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]')

#: Include paths that reach an implementation of the seam rather than the seam.
#: Only the implementations are allowed to know which hardware is behind it, so
#: a control translation unit reaching one of their headers has gone around the
#: interface even when the header itself names no vendor symbol.
IMPLEMENTATION_PATH_PATTERN = re.compile(r"(^|/)(hw|src)?/?hw/[^/]+/", re.IGNORECASE)
_INCLUDE_DIRECTIVE = re.compile(r"^\s*#\s*include\b")


@dataclass(frozen=True)
class Violation:
    """One vendor symbol found at one place."""

    path: str
    line: int
    symbol: str
    kind: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.kind} '{self.symbol}'"


def strip_comments_and_strings(source: str) -> str:
    """Blank out comments and string/char literals, preserving line structure.

    Replacing rather than deleting keeps every remaining character on its
    original line, so line numbers reported against the result are the line
    numbers of the original file.
    """
    out: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""

        if ch == "/" and nxt == "/":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
            continue

        if ch == "/" and nxt == "*":
            out.append("  ")
            i += 2
            while i < n and not (source[i] == "*" and i + 1 < n and source[i + 1] == "/"):
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
            continue

        if ch in ('"', "'"):
            quote = ch
            out.append(" ")
            i += 1
            while i < n and source[i] != quote:
                if source[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                    continue
                out.append("\n" if source[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append(" ")
                i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def find_violations(path: str, source: str) -> list[Violation]:
    """Report every vendor include and vendor identifier in one source file."""
    cleaned = strip_comments_and_strings(source)
    violations: list[Violation] = []

    # An include directive's filename is a string literal, which stripping has
    # blanked out. So the directive is recognised on the stripped line -- which
    # is what makes a commented-out include invisible, as it should be -- and
    # then read off the original line, which still has the filename.
    original_lines = source.splitlines()

    for lineno, line in enumerate(cleaned.splitlines(), start=1):
        if _INCLUDE_DIRECTIVE.match(line):
            original = original_lines[lineno - 1] if lineno <= len(original_lines) else ""
            match = _INCLUDE.match(original)
            if match is None:
                # The included file is named by a macro, so what is actually
                # included cannot be read here. Fail rather than skip: an
                # unresolvable include is exactly where a device header hides.
                violations.append(
                    Violation(path, lineno, original.strip(), "include the check cannot resolve")
                )
                continue
            included = match.group(1)
            header = included.split("/")[-1]
            if any(pattern.match(header) for pattern in VENDOR_INCLUDE_PATTERNS):
                violations.append(Violation(path, lineno, included, "vendor header include"))
            elif IMPLEMENTATION_PATH_PATTERN.search(included):
                violations.append(
                    Violation(path, lineno, included, "seam implementation header include")
                )
            # An include line's own text is not scanned for identifiers: the
            # header name has already been judged on the rules that fit it.
            continue

        for kind, pattern in VENDOR_IDENTIFIER_PATTERNS:
            for found in pattern.finditer(line):
                violations.append(Violation(path, lineno, found.group(0), kind))

    return _deduplicate(violations)


def _deduplicate(violations: list[Violation]) -> list[Violation]:
    """Collapse repeats of the same symbol at the same place, keeping order.

    One token can match more than one pattern -- a HAL macro also looks like a
    HAL function -- and reporting it twice would suggest two problems.
    """
    seen: set[tuple[str, int, str]] = set()
    unique: list[Violation] = []
    for violation in violations:
        key = (violation.path, violation.line, violation.symbol)
        if key in seen:
            continue
        seen.add(key)
        unique.append(violation)
    return unique
