"""Static description of the library: zones, tables, seats. Seats sit 2 rows x 4 per table."""
from dataclasses import dataclass
from collections import defaultdict

# noise = baseline dB, walk = seconds from the entrance kiosk
ZONES = {
    (1, "A"): dict(tables=3, noise=49, walk=15), (1, "B"): dict(tables=2, noise=45, walk=25),
    (2, "A"): dict(tables=3, noise=44, walk=45), (2, "B"): dict(tables=3, noise=33, walk=40),
    (3, "East"): dict(tables=2, noise=30, walk=75), (3, "West"): dict(tables=3, noise=38, walk=70),
}

@dataclass(frozen=True)
class Seat:
    id: str; floor: int; zone: str; table: int; r: int; c: int

SEATS = [Seat(f"{f}-{z[0]}{t}{r}{c}", f, z, t, r, c)
         for (f, z), cfg in ZONES.items()
         for t in range(cfg["tables"]) for r in range(2) for c in range(4)]
BY_ID = {s.id: s for s in SEATS}
BY_ZONE = defaultdict(list)
for s in SEATS:
    BY_ZONE[(s.floor, s.zone)].append(s)

def label(zone): return f"Zone {zone}" if len(zone) == 1 else zone
