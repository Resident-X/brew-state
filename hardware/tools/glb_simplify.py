#!/usr/bin/env python3
"""Make a KiCad GLB export small enough to hand to a browser viewer, keeping its colours and final shape.

usage: glb_simplify.py IN.glb OUT.glb [--keep FRACTION] [--keep-translucent] [--preview PREFIX [--zoom-at X,Y,W]]

Needs numpy, trimesh, fast-simplification and pillow, which render_board_3d.py installs on demand into a
virtual environment in the 3D cache folder (it runs this file with that environment's Python). The
result has one mesh per colour (every part's triangles of that colour merged, split only where a piece
would pass 65535 vertices), vertices welded, the solder mask drawn opaque in the board's colour, no
normals and no textures: draw it with flat shading. Positions are 16-bit normalised integers under one scene scale and
offset (KHR_mesh_quantization, which three.js's GLTFLoader reads without a decoder), so the file needs
no Draco or meshopt decoder. `--keep FRACTION` below 1 also decimates each part's mesh to that fraction of
its triangles, which visibly distorts small parts; the default keeps every triangle. `--preview PREFIX`
writes PREFIX-angled.png and PREFIX-top.png (and PREFIX-zoom.png about the board point X,Y with window width
W, in the board's millimetres, y down as in the board file) from the file as written, read back by a reader
of its own, by a plain depth-sorted rasteriser, so the loss of detail can be judged by eye.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from collections import defaultdict


def load_groups(path):
    """Colour key -> list of (points, faces), one entry per mesh of the file, in the file's frame."""
    import numpy as np
    import trimesh

    scene = trimesh.load(path, force="scene")
    groups = defaultdict(list)
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(transform)
        colour = getattr(mesh.visual.material, "baseColorFactor", None)
        key = tuple(int(c) for c in colour) if colour is not None else (128, 128, 128, 255)
        groups[key].append((np.asarray(mesh.vertices, dtype=float), np.asarray(mesh.faces)))
    return groups


def weld(points, faces, digits=6):
    import numpy as np

    rounded = np.round(points, digits)
    _, first, inverse = np.unique(rounded, axis=0, return_index=True, return_inverse=True)
    inverse = np.asarray(inverse).reshape(-1)
    faces = inverse[faces]
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    faces = faces[keep]
    used, remap = np.unique(faces, return_inverse=True)
    return points[first][used], np.asarray(remap).reshape(faces.shape)


def solid_board(groups):
    """Draw the solder mask opaque and the board body in the mask's colour, so a viewer has no translucent
    layer to sort and the board reads as the finished green it is."""
    out = defaultdict(list)
    mask = [k for k in groups if 200 <= k[3] < 255 and k[1] > k[0] and k[1] > k[2]]
    body = (107, 115, 74, 255)
    colour = (mask[0][0], mask[0][1], mask[0][2], 255) if mask else None
    for key, parts in groups.items():
        if key in mask:
            out[colour].extend(parts)
        elif key == body and colour:
            out[colour].extend(parts)
        else:
            out[key].extend(parts)
    return out


def join(parts):
    import numpy as np

    offset = 0
    pts, fcs = [], []
    for p, f in parts:
        pts.append(p)
        fcs.append(f + offset)
        offset += len(p)
    return np.vstack(pts), np.vstack(fcs)


def simplify(groups, keep, floor=0):
    """Weld and decimate every mesh on its own (so one part never collapses into its neighbour), keeping a
    mesh of at most `floor` triangles as it is and any larger one down to floor + keep of the rest, then
    merge each colour's meshes into one."""
    import fast_simplification as fs
    import numpy as np

    out = {}
    for key, parts in groups.items():
        done = []
        for points, faces in parts:
            points, faces = weld(points, faces)
            if len(faces) > floor and keep < 1.0:
                target = floor + keep * (len(faces) - floor)
                p, f = fs.simplify(points.astype(np.float32), faces.astype(np.int32),
                                   target_reduction=1.0 - target / len(faces), agg=2)
                points, faces = np.asarray(p, dtype=float), np.asarray(f)
            if len(faces):
                done.append((points, faces))
        if done:
            out[key] = join(done)
    return out


def chunks_of(points, faces, limit=65000):
    """Split one mesh's faces into pieces of at most `limit` vertices each, so indices fit 16 bits."""
    import numpy as np

    out, start = [], 0
    order = np.argsort(points[faces].mean(axis=1)[:, 0], kind="stable")
    faces = faces[order]
    while start < len(faces):
        end = min(len(faces), start + limit // 3)
        used, remap = np.unique(faces[start:end], return_inverse=True)
        out.append((points[used], np.asarray(remap).reshape(-1, 3)))
        start = end
    return out


def write_glb(groups, path):
    """One mesh per colour (split where a piece would need more than 65535 vertices), positions as
    16-bit normalised integers under one scene scale and offset (KHR_mesh_quantization, which three.js's
    GLTFLoader reads without a decoder), indices 16 bit."""
    import numpy as np

    allp = np.vstack([p for p, _ in groups.values()])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    extent = np.maximum(hi - lo, 1e-9)
    chunks = bytearray()
    views, accessors, meshes, materials, nodes = [], [], [], [], []

    def add(data: bytes, target: int):
        while len(chunks) % 4:
            chunks.append(0)
        views.append({"buffer": 0, "byteOffset": len(chunks), "byteLength": len(data), "target": target})
        chunks.extend(data)
        return len(views) - 1

    for key, (points, faces) in sorted(groups.items()):
        r, g, b, a = (c / 255.0 for c in key)
        material = {"pbrMetallicRoughness": {"baseColorFactor": [r, g, b, a], "metallicFactor": 0.0,
                                             "roughnessFactor": 0.7}, "doubleSided": True}
        if a < 0.99:
            material["alphaMode"] = "BLEND"
        materials.append(material)
        primitives = []
        for pts, fcs in chunks_of(points, faces):
            q = np.rint((pts - lo) / extent * 65535.0).astype("<u2")
            pv = add(np.ascontiguousarray(np.pad(q, ((0, 0), (0, 1)))).tobytes(), 34962)
            views[pv]["byteStride"] = 8
            accessors.append({"bufferView": pv, "componentType": 5123, "normalized": True, "count": len(q),
                              "type": "VEC3", "min": [int(v) for v in q.min(axis=0)],
                              "max": [int(v) for v in q.max(axis=0)]})
            iv = add(np.asarray(fcs, dtype="<u2").reshape(-1).tobytes(), 34963)
            accessors.append({"bufferView": iv, "componentType": 5123, "count": int(fcs.size), "type": "SCALAR"})
            primitives.append({"attributes": {"POSITION": len(accessors) - 2}, "indices": len(accessors) - 1,
                               "material": len(materials) - 1})
        meshes.append({"primitives": primitives})
    nodes = [{"mesh": i, "translation": [float(v) for v in lo], "scale": [float(v) for v in extent]}
             for i in range(len(meshes))]
    doc = {"asset": {"version": "2.0", "generator": "glb_simplify.py"}, "scene": 0,
           "extensionsUsed": ["KHR_mesh_quantization"], "extensionsRequired": ["KHR_mesh_quantization"],
           "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes, "materials": materials,
           "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(chunks)}]}
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    while len(chunks) % 4:
        chunks.append(0)
    total = 12 + 8 + len(js) + 8 + len(chunks)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<4sII", b"glTF", 2, total))
        fh.write(struct.pack("<I4s", len(js), b"JSON") + js)
        fh.write(struct.pack("<I4s", len(chunks), b"BIN\0") + bytes(chunks))


def read_glb(path):
    """Read back what write_glb wrote, with no help from a glTF library: colour -> (points, faces) in the
    file's frame, positions decoded from their normalised 16-bit form and the node's scale and offset."""
    import numpy as np

    data = open(path, "rb").read()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and version == 2 and length == len(data)
    jlen, _ = struct.unpack_from("<I4s", data, 12)
    doc = json.loads(data[20:20 + jlen])
    blen, _ = struct.unpack_from("<I4s", data, 20 + jlen)
    binary = data[28 + jlen:28 + jlen + blen]
    groups = {}
    for node in doc["nodes"]:
        mesh = doc["meshes"][node["mesh"]]
        scale, offset = np.array(node["scale"]), np.array(node["translation"])
        pts, fcs, base = [], [], 0
        for prim in mesh["primitives"]:
            acc = doc["accessors"][prim["attributes"]["POSITION"]]
            view = doc["bufferViews"][acc["bufferView"]]
            raw = np.frombuffer(binary, dtype="<u2", count=view["byteLength"] // 2, offset=view["byteOffset"])
            q = raw.reshape(-1, view["byteStride"] // 2)[: acc["count"], :3]
            pts.append(q / 65535.0 * scale + offset)
            iacc = doc["accessors"][prim["indices"]]
            iview = doc["bufferViews"][iacc["bufferView"]]
            idx = np.frombuffer(binary, dtype="<u2", count=iacc["count"], offset=iview["byteOffset"])
            fcs.append(idx.reshape(-1, 3).astype(np.int64) + base)
            base += acc["count"]
        colour = doc["materials"][mesh["primitives"][0]["material"]]["pbrMetallicRoughness"]["baseColorFactor"]
        groups[tuple(int(round(c * 255)) for c in colour)] = (np.vstack(pts), np.vstack(fcs))
    return groups


def preview(groups, prefix, zoom_at=None, size=(1400, 1000)):
    """Depth-sorted flat-shaded pictures from the groups (board x right, y up, z toward the viewer)."""
    import numpy as np
    from PIL import Image, ImageDraw

    def picture(name, rx, rz, window):
        rot_x = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
        rot_z = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
        m = rot_x @ rot_z
        tris, cols, depth = [], [], []
        for key, (points, faces) in groups.items():
            # glTF metres, y up, z = the board's y (down); the picture's frame is mm, y up the board
            p = (points * 1000.0)[:, [0, 2, 1]] * np.array([1.0, -1.0, 1.0])
            p = p @ m.T
            t = p[faces]
            n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
            ln = np.linalg.norm(n, axis=1)
            ln[ln == 0] = 1
            n = n / ln[:, None]
            light = 0.35 + 0.65 * np.abs(n @ np.array([0.3, 0.4, 0.86]))
            tris.append(t)
            cols.append(np.array(key[:3])[None, :] * light[:, None])
            depth.append(t[:, :, 2].mean(axis=1))
        tris, cols, depth = np.vstack(tris), np.vstack(cols), np.concatenate(depth)
        allp = tris.reshape(-1, 3)
        if window is None:
            lo, hi = allp.min(axis=0), allp.max(axis=0)
            cx, cy, w = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (hi[0] - lo[0]) * 1.05
        else:
            cx, cy, w = window[0], -window[1], window[2]
        scale = size[0] / w
        img = Image.new("RGB", size, (200, 205, 225))
        draw = ImageDraw.Draw(img)
        for i in np.argsort(depth):
            t = tris[i]
            xy = [((x - cx) * scale + size[0] / 2, size[1] / 2 - (y - cy) * scale) for x, y, _ in t]
            draw.polygon(xy, fill=tuple(int(c) for c in cols[i]))
        img.save(f"{prefix}-{name}.png")

    picture("top", 0.0, 0.0, None)
    picture("angled", math.radians(-50), math.radians(25), None)
    if zoom_at:
        picture("zoom", 0.0, 0.0, zoom_at)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--keep", type=float, default=1.0)
    parser.add_argument("--keep-translucent", action="store_true",
                        help="leave the solder mask translucent and the board body in its own colour")
    parser.add_argument("--preview")
    parser.add_argument("--zoom-at", help="X,Y,W in board mm (y down) for the close-up")
    parser.add_argument("--preview-source", action="store_true", help="also draw IN.glb as PREFIX-before-*.png")
    args = parser.parse_args(argv)
    groups = load_groups(args.src)
    if not args.keep_translucent:
        groups = solid_board(groups)
    small = simplify(groups, args.keep)
    write_glb(small, args.dst)
    small = read_glb(args.dst)
    zoom = tuple(float(v) for v in args.zoom_at.split(",")) if args.zoom_at else None
    tri = sum(len(f) for _, f in small.values())
    print(f"{len(small)} meshes, {tri} triangles")
    if args.preview:
        if args.preview_source:
            preview({k: join(v) for k, v in groups.items()}, args.preview + "-before", zoom)
        preview(small, args.preview + "-after", zoom)
    return 0


if __name__ == "__main__":
    sys.exit(main())
