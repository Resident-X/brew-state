#!/usr/bin/env python3
"""The register map the peripheral models are written against, from two sides.

A peripheral model is only a model of the part if the offsets it answers are the
part's offsets. Nothing in a run establishes that: a model that put the compare
registers four bytes further along would answer every access the firmware made
in a place the firmware never wrote, and the run would report four channels that
never moved -- or, worse, would keep working while the models and the part
quietly meant different things.

So both sides are read here. The addresses the models use are lifted out of the
model sources themselves, by reading them rather than by copying the numbers into
a second list that could drift. The part's addresses come from the vendor's
register description. Comparing the two is what makes the description
load-bearing rather than decorative.

The windows the models keep for the harness are checked from the same
description and in the opposite direction: they must correspond to no register
the part declares, or a model would be shadowing hardware.
"""

import ast
import os
import xml.etree.ElementTree as ElementTree

HERE = os.path.dirname(os.path.abspath(__file__))
PERIPHERALS = os.path.abspath(os.path.join(HERE, "..", "peripherals"))


_BINARY = {
    ast.LShift: lambda a, b: a << b,
    ast.RShift: lambda a, b: a >> b,
    ast.BitOr: lambda a, b: a | b,
    ast.BitAnd: lambda a, b: a & b,
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
}


def _evaluate(node, known):
    """A model constant's value, from arithmetic over literals and earlier ones.

    Deliberately narrow: the point is to read the numbers the models were
    written with, not to run them. Anything outside this grammar is skipped
    rather than guessed at.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in known:
            raise ValueError(node.id)
        return known[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        return _BINARY[type(node.op)](
            _evaluate(node.left, known), _evaluate(node.right, known))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate(node.operand, known)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
        return ~_evaluate(node.operand, known)
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_evaluate(item, known) for item in node.elts]
    raise ValueError(ast.dump(node))


def model_constants(model_name):
    """Module-level integer constants of a peripheral model, without running it."""
    return source_constants(os.path.join(PERIPHERALS, "%s.py" % model_name))


def source_constants(path):
    """Module-level integer constants of a source file, without running it.

    The models and the script that exercises the artefact are written for the
    emulator's interpreter and reference its objects at module level, so they
    cannot be imported. Reading their syntax gets the numbers without executing
    anything.
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    constants = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            constants[target.id] = _evaluate(node.value, constants)
        except ValueError:
            continue
    return constants


def _text(element, tag, default=None):
    found = element.find(tag)
    return default if found is None else found.text.strip()


def _number(text):
    text = text.strip().lower().replace("_", "")
    if text.startswith("0x"):
        return int(text, 16)
    if text.startswith("#"):
        return int(text[1:], 2)
    return int(text, 0)


def peripheral_map(svd_path, peripheral_name):
    """{register name: offset} and {register name: {field: bit position}}."""
    root = ElementTree.parse(svd_path).getroot()
    peripherals = {}
    for element in root.iter("peripheral"):
        name = _text(element, "name")
        if name is not None:
            peripherals[name] = element

    element = peripherals.get(peripheral_name)
    if element is None:
        raise KeyError("%s declares no peripheral %s" % (svd_path, peripheral_name))

    derived = element.get("derivedFrom")
    registers = {}
    fields = {}
    if derived:
        registers, fields = peripheral_map(svd_path, derived)[1:3]

    base = _number(_text(element, "baseAddress"))
    for register in element.iter("register"):
        register_name = _text(register, "name")
        registers[register_name] = _number(_text(register, "addressOffset"))
        bits = {}
        for field in register.iter("field"):
            bits[_text(field, "name")] = _number(_text(field, "bitOffset"))
        fields[register_name] = bits
    return base, registers, fields


def declared_offsets(svd_path, peripheral_name):
    """Every byte offset the part declares a register at, as a set."""
    _, registers, _ = peripheral_map(svd_path, peripheral_name)
    occupied = set()
    for offset in registers.values():
        for byte in range(4):
            occupied.add(offset + byte)
    return occupied
