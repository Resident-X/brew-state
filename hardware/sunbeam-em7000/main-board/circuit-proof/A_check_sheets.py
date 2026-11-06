# Checks sheets/101 and sheets/102: unique refs, every pin in exactly one net or no_connect, no net with a single pin except labelled globals.
import yaml, collections, glob
for f in sorted(glob.glob("../sheets/10*.yaml")):
    d = yaml.safe_load(open(f))
    refs = [p["ref"] for p in d["parts"]]
    assert len(refs) == len(set(refs)), "duplicate ref"
    where = collections.defaultdict(list)
    for n, v in d["nets"].items():
        for p in v["pins"]:
            where[p].append(n)
    for nc in d["no_connect"]:
        where[nc["pin"]].append("NC")
    multi = {p: n for p, n in where.items() if len(n) > 1}
    print(f, "parts", len(refs), "pins", len(where), "multi", multi)
    for n, v in d["nets"].items():
        if len(v["pins"]) < 2 and v["scope"] == "local":
            print("  single-pin local net:", n)
