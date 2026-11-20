"""Repack a glb_simplify.py GLB (one quantised mesh per colour, KHR_mesh_quantization) into a compact
deflated file the page decodes itself, losslessly: the same 16-bit positions, triangles and colours.

usage: pack.py IN.glb OUT.wasm

Per mesh: triangles reordered along a Morton curve of their centroids (winding kept), vertices renumbered by
first use; positions delta-coded (16-bit wrap, zigzag) and indices coded as distance below the next new
vertex; both split into byte planes. The whole file is zlib-deflated (the browser's DecompressionStream
'deflate' reads it). Layout before deflate: b'BSM1', u32 json length, json, then per mesh
6*nv bytes of position planes (lo x,y,z then hi x,y,z) and 2*ni bytes of index planes (lo, hi).
"""
import json, struct, sys, zlib
import numpy as np

src, dst = sys.argv[1:3]
d = open(src, "rb").read()
L = struct.unpack("<I", d[12:16])[0]
j = json.loads(d[20:20 + L])
buf = d[20 + L + 8:]


def acc(i):
    a = j["accessors"][i]; v = j["bufferViews"][a["bufferView"]]
    off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    n = {"SCALAR": 1, "VEC3": 3}[a["type"]]
    assert a["componentType"] == 5123, a
    stride = v.get("byteStride") or 2 * n
    raw = np.frombuffer(buf, np.uint8, (a["count"] - 1) * stride + 2 * n, off)
    raw = np.lib.stride_tricks.as_strided(raw, (a["count"], 2 * n), (stride, 1))
    return raw.copy().view("<u2").reshape(-1, n)


def morton(c):
    c = c.astype(np.uint64)

    def part(x):
        x = x & np.uint64(0x1fffff)
        for s, m in ((32, 0x1f00000000ffff), (16, 0x1f0000ff0000ff), (8, 0x100f00f00f00f00f),
                     (4, 0x10c30c30c30c30c3), (2, 0x1249249249249249)):
            x = (x | (x << np.uint64(s))) & np.uint64(m)
        return x
    return part(c[:, 0]) | (part(c[:, 1]) << np.uint64(1)) | (part(c[:, 2]) << np.uint64(2))


nodes = [n for n in j["nodes"] if "mesh" in n]
scale, offset = nodes[0]["scale"], nodes[0]["translation"]
assert all(n["scale"] == scale and n["translation"] == offset and "rotation" not in n for n in nodes)
meta = {"s": scale, "t": offset, "m": []}
body = bytearray()
check = []
for n in nodes:
    for p in j["meshes"][n["mesh"]]["primitives"]:
        mat = j["materials"][p["material"]]
        colour = mat["pbrMetallicRoughness"]["baseColorFactor"]
        P = acc(p["attributes"]["POSITION"]).astype(np.int64)
        T = acc(p["indices"]).reshape(-1, 3).astype(np.int64)
        check.append((P[T].copy(), colour))
        T = T[np.argsort(morton(P[T].mean(axis=1).astype(np.int64)), kind="stable")]
        I = T.reshape(-1)
        uniq, firstpos = np.unique(I, return_index=True)
        order = uniq[np.argsort(firstpos)]
        remap = np.empty(len(P), np.int64); remap[order] = np.arange(len(order))
        P2, I2 = P[order], remap[I]
        hw = np.maximum.accumulate(np.concatenate([[0], I2[:-1] + 1]))
        code = hw - I2
        assert code.min() >= 0 and code.max() < 65536
        dP = np.diff(P2, axis=0, prepend=np.zeros((1, 3), np.int64))
        d16 = ((dP + 32768) & 0xFFFF) - 32768
        zz = ((d16 << 1) ^ (d16 >> 15)) & 0xFFFF
        pb = zz.astype("<u2").view(np.uint8).reshape(-1, 3, 2)
        for k in (0, 1):
            for c in range(3):
                body += pb[:, c, k].tobytes()
        cb = code.astype("<u2").view(np.uint8).reshape(-1, 2)
        body += cb[:, 0].tobytes() + cb[:, 1].tobytes()
        meta["m"].append({"c": [round(x, 4) for x in colour], "v": int(len(P2)), "i": int(len(I2))})

js = json.dumps(meta, separators=(",", ":")).encode()
raw = b"BSM1" + struct.pack("<I", len(js)) + js + bytes(body)
out = zlib.compress(raw, 9)
open(dst, "wb").write(out)

# round trip: decode exactly as the page does and compare every triangle's vertices
u = zlib.decompress(out); jl = struct.unpack("<I", u[4:8])[0]; mm = json.loads(u[8:8 + jl]); o = 8 + jl
for k, m in enumerate(mm["m"]):
    nv, ni = m["v"], m["i"]
    a = np.frombuffer(u, np.uint8, 6 * nv, o).reshape(6, nv).astype(np.int64); o += 6 * nv
    z = a[:3] | (a[3:] << 8)
    dd = (z >> 1) ^ -(z & 1)
    pos = (np.cumsum(dd, axis=1) & 0xFFFF).T
    b = np.frombuffer(u, np.uint8, 2 * ni, o).reshape(2, ni).astype(np.int64); o += 2 * ni
    code = b[0] | (b[1] << 8)
    idx = np.empty(ni, np.int64); hw = 0
    for q in range(ni):
        v = hw - code[q]; idx[q] = v
        if v == hw: hw += 1
    tri = pos[idx.reshape(-1, 3)]
    ref, colour = check[k]
    key = lambda t: np.lexsort(t.reshape(len(t), -1).T[::-1])
    assert tri.shape == ref.shape and np.array_equal(tri[key(tri)], ref[key(ref)]), k
print(src, len(d), "->", dst, len(out), "bytes;", len(mm["m"]), "meshes,",
      sum(m["i"] for m in mm["m"]) // 3, "triangles; round trip exact")
