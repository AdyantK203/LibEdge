"""Shared LibEdge seat validation and MongoDB snapshot contract (no ML imports)."""
import math
from datetime import datetime, timezone

# Must match LibEdge/backend/layout.py. Two rows, four columns per table.
TABLES = {(1, "A"): 3, (1, "B"): 2, (2, "A"): 3,
          (2, "B"): 3, (3, "East"): 2, (3, "West"): 3}
STATES = {"empty", "occupied", "object", "unknown"}

def valid_ids(floor, zone):
    if (floor, zone) not in TABLES:
        raise ValueError(f"Unknown LibEdge floor/zone: {floor}/{zone}")
    return {f"{floor}-{zone[0]}{t}{r}{c}" for t in range(TABLES[(floor, zone)])
            for r in range(2) for c in range(4)}

def validate_config(config, require_review=False):
    floor, zone = config["floor"], config["zone"]
    allowed = valid_ids(floor, zone)
    seats = config.get("seats")
    if not isinstance(seats, dict) or not seats:
        raise ValueError("seats must be a non-empty dictionary of seat IDs to polygons")
    for sid, poly in seats.items():
        if sid not in allowed:
            raise ValueError(f"Seat {sid} does not exist in the LibEdge layout")
        if not isinstance(poly, list) or len(poly) < 3:
            raise ValueError(f"Seat {sid} needs at least three polygon points")
        if any(not isinstance(p, list) or len(p) != 2 or
               any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in p)
               for p in poly):
            raise ValueError(f"Invalid coordinates for {sid}")
    if require_review and config.get("calibration_reviewed") is not True:
        raise ValueError("Review the draft seat IDs and polygons before publishing; set calibration_reviewed to true afterwards")
    return seats

def snapshot(floor, zone, states, updated_at=None):
    allowed = valid_ids(floor, zone)
    if not states or any(sid not in allowed or status not in STATES for sid, status in states.items()):
        raise ValueError("Snapshot contains invalid LibEdge seat IDs or statuses")
    return {"_id": f"floor-{floor}-zone-{zone}", "floor": floor, "zone": zone,
            "updated_at": updated_at or datetime.now(timezone.utc).isoformat(), "seats": dict(states)}
