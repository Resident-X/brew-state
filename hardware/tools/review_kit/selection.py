"""The selection of a group's views from an already-rendered folder's view index.

The views command writes, beside its images, an index (`index.json`) that lists every image with the view it is of, its
net, its classes, the layers it shows and the board region it covers. A unit declares the views it needs as artefact names;
this module resolves a description of them, by view kind, net, net class, layer and board region, to those names, by
reading the index alone. It renders nothing and starts no program: the views a group holds are chosen from the set already
rendered, which is not rendered again to change what a group holds.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

INDEX = "views/index.json"
FOLDER = "views"

Region = Tuple[float, float, float, float]
Names = Union[str, Iterable[str]]


class IndexUnreadable(Exception):
    """The folder's view index cannot be read; the text names the file and what to do."""


class EmptySelection(ValueError):
    """The description matches no image of the index, so a unit would declare no view it asked for."""


def read_index(review: str, relative: str = INDEX) -> Dict[str, Any]:
    """The view index of a review folder as the views command wrote it."""
    path = os.path.join(review, relative)
    try:
        with open(path, encoding="utf-8") as handle:
            index = json.load(handle)
    except (OSError, ValueError) as error:
        raise IndexUnreadable(f"the view index {path} cannot be read as JSON ({error}); write the review folder with the folder "
                              "command, which copies the views and their index") from error
    if not isinstance(index, dict) or not isinstance(index.get("images"), list):
        raise IndexUnreadable(f"the view index {path} has no list of images; write the review folder with the folder command")
    return index


def as_set(values: Optional[Names]) -> Optional[set]:
    if values is None:
        return None
    return {values} if isinstance(values, str) else set(values)


def class_names(image: Dict[str, Any]) -> set:
    """The net classes an image is of: the names a net's view lists, or the names of the classes a class map draws."""
    return {entry["name"] if isinstance(entry, dict) else entry for entry in image.get("classes", [])}


def meets(box: Dict[str, Any], region: Region) -> bool:
    return (box["x0"] <= region[2] and box["x1"] >= region[0] and box["y0"] <= region[3] and box["y1"] >= region[1])


def select(index: Dict[str, Any], *, view: Optional[Names] = None, nets: Optional[Names] = None, classes: Optional[Names] = None,
           layers: Optional[Names] = None, region: Optional[Region] = None, fields: Optional[Dict[str, Names]] = None,
           folder: str = FOLDER, allow_empty: bool = False) -> List[str]:
    """The artefact names (`<folder>/<file>`, sorted) of the images of `index` that match every description given.

    `view` is a view kind or kinds (`layer`, `assembly`, `net`, `class map`, `crop`, `3d`), `nets` a net name or names,
    `classes` a net class or classes, `layers` a layer or layers the image shows, and `region` the board rectangle
    (x0, y0, x1, y1) in millimetres an image's region must meet, and `fields` any other field of an image the index lists
    (`side`, `circuit`, `direction`) by the value or values it must have. A description left out does not narrow the selection. A
    description that matches no image is refused naming it, unless `allow_empty`."""
    kinds, wanted_nets, wanted_classes, wanted_layers = as_set(view), as_set(nets), as_set(classes), as_set(layers)
    found = set()
    for image in index["images"]:
        if kinds is not None and image.get("view") not in kinds:
            continue
        if wanted_nets is not None and image.get("net") not in wanted_nets:
            continue
        if wanted_classes is not None and not wanted_classes & class_names(image):
            continue
        if wanted_layers is not None and not wanted_layers & {entry["name"] for entry in image.get("layers", [])}:
            continue
        if region is not None and ("region_mm" not in image or not meets(image["region_mm"], region)):
            continue
        if fields is not None and any(image.get(key) not in as_set(wanted) for key, wanted in fields.items()):
            continue
        found.add(f"{folder}/{image['file']}")
    if not found and not allow_empty:
        given = {key: sorted(value) if isinstance(value, set) else value for key, value in
                 (("view", kinds), ("nets", wanted_nets), ("classes", wanted_classes), ("layers", wanted_layers), ("region", region),
                  ("fields", fields))
                 if value is not None}
        raise EmptySelection(f"no image of the view index matches {given}; name a view, net, class, layer or region the index lists")
    return sorted(found)
