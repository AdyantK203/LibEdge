"""LibEdge context engine.
Step 1: spatial grouping  - flood-fill empty seats into contiguous blocks (same table, side by side or face to face).
Step 2: ranking           - zones that can host the group are scored on fit, free space, quietness and walk distance.
A floor with the most empty seats can still lose: only contiguous blocks count."""
from collections import deque
from layout import BY_ZONE, ZONES, label

W = {"fit": .35, "space": .25, "quiet": .25, "near": .15}
_clamp = lambda v: max(0.0, min(1.0, v))

def free_groups(seats, state):
    free = {(s.table, s.r, s.c): s for s in seats if state.get(s.id) == "empty"}
    seen, groups = set(), []
    for k in sorted(free):
        if k in seen: continue
        q, comp = deque([k]), []
        seen.add(k)
        while q:
            t, r, c = q.popleft(); comp.append(free[(t, r, c)])
            for nb in ((t, r, c + 1), (t, r, c - 1), (t, r + 1, c), (t, r - 1, c)):
                if nb in free and nb not in seen: seen.add(nb); q.append(nb)
        groups.append(comp)
    return groups

def zone_stats(state, noise):
    out = []
    for (f, z), seats in BY_ZONE.items():
        g = free_groups(seats, state)
        empty = sum(len(x) for x in g)
        out.append(dict(floor=f, zone=z, label=label(z), total=len(seats), empty=empty,
                        occ=round(100 * (1 - empty / len(seats))), groups=g,
                        max_group=max((len(x) for x in g), default=0),
                        noise=noise[(f, z)], walk=ZONES[(f, z)]["walk"]))
    return out

def level(db): return "low" if db < 36 else "moderate" if db < 46 else "high"

def score(z, n):
    # tight fit preferred: keeps the big blocks free for bigger groups
    fit = 1 / (1 + .15 * (z["max_group"] - n))
    return (W["fit"] * fit + W["space"] * (1 - z["occ"] / 100)
            + W["quiet"] * _clamp((55 - z["noise"]) / 25) + W["near"] * _clamp(1 - z["walk"] / 120))

def recommend(state, noise, n):
    zs = zone_stats(state, noise)
    floors = [dict(floor=f, empty=sum(z["empty"] for z in zs if z["floor"] == f),
                   max_group=max(z["max_group"] for z in zs if z["floor"] == f))
              for f in sorted({z["floor"] for z in zs})]
    ok = [z for z in zs if z["max_group"] >= n]
    if not ok:
        return dict(ok=False, group=n, floors=floors, best=max(z["max_group"] for z in zs))
    best = max(ok, key=lambda z: score(z, n))
    block = min((g for g in best["groups"] if len(g) >= n), key=len)
    return dict(ok=True, group=n, floor=best["floor"], zone=best["zone"], label=best["label"],
                seats=[s.id for s in block[:n]], max_group=best["max_group"], occ=best["occ"],
                noise=best["noise"], noise_level=level(best["noise"]), walk=best["walk"], floors=floors)

def compact(rec, state):
    """Small JSON that fits one BLE characteristic. map: e=empty o=taken b=bag *=your seats."""
    fl = [[f["floor"], f["empty"], f["max_group"]] for f in rec["floors"]]
    if not rec["ok"]:
        return {"ok": 0, "g": rec["group"], "fl": fl, "best": rec["best"]}
    seats = BY_ZONE[(rec["floor"], rec["zone"])]
    idx, pick = {(s.table, s.r, s.c): s for s in seats}, set(rec["seats"])
    ch = {"empty": "e", "occupied": "o", "object": "b"}
    rows = "|".join("".join("*" if idx[(t, r, c)].id in pick else ch.get(state.get(idx[(t, r, c)].id), "o")
                    for r in range(2) for c in range(4)) for t in sorted({s.table for s in seats}))
    return {"ok": 1, "g": rec["group"], "f": rec["floor"], "z": rec["label"], "n": rec["max_group"],
            "q": rec["noise_level"], "t": rec["walk"], "o": rec["occ"], "map": rows, "fl": fl}

def summary(state, noise):
    zs = zone_stats(state, noise)
    taken = sum(v != "empty" for v in state.values())
    quiet, big = min(zs, key=lambda z: z["noise"]), max(zs, key=lambda z: z["max_group"])
    floors = []
    for f in sorted({z["floor"] for z in zs}):
        fz = [z for z in zs if z["floor"] == f]
        floors.append(dict(floor=f, occ=round(100 * (1 - sum(z["empty"] for z in fz) / sum(z["total"] for z in fz))),
                           empty=sum(z["empty"] for z in fz),
                           zones=[{k: z[k] for k in ("label", "empty", "occ", "max_group", "noise")} for z in fz]))
    return dict(total=len(state), occupancy=round(100 * taken / len(state)), available=len(state) - taken,
                quietest=f'{quiet["floor"]}F-{quiet["label"]}', largest=f'{big["floor"]}F-{big["label"]}',
                largest_size=big["max_group"], floors=floors)
