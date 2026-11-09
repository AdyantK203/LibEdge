"""Poll MongoDB floor snapshots into the shared recommendation state."""
import asyncio
import logging
import math
import time
from datetime import datetime, timezone

from layout import BY_ID, ZONES

log = logging.getLogger("libedge.mongo")
VALID_STATES = {"empty", "occupied", "object"}
FLOORS = sorted({seat.floor for seat in BY_ID.values()})


def _timestamp(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            return None
    return None


def apply_documents(collection, state, noise, node_last_seen, node_mode):
    """Apply latest-per-zone documents; a document without zone covers its floor."""
    applied_floors = set()
    floor_times = {}
    zone_times = {}
    # Apply older snapshots first so newer documents overwrite their seat states.
    for doc in collection.find({"floor": {"$in": FLOORS}}).sort("updated_at", 1):
        floor = doc.get("floor")
        zone = doc.get("zone")
        if (floor not in FLOORS or
                (zone is not None and not isinstance(zone, str)) or
                (zone is not None and (floor, zone) not in ZONES) or
                not isinstance(doc.get("seats"), dict)):
            log.warning("ignoring malformed floor snapshot")
            continue

        applied = 0
        for seat_id, status in doc["seats"].items():
            seat = BY_ID.get(seat_id)
            if (seat and seat.floor == floor and
                    (zone is None or seat.zone == zone) and status in VALID_STATES):
                state[seat_id] = status
                applied += 1
        if not applied:
            log.warning("floor %s snapshot contains no valid seat states", floor)
            continue

        noise_doc = doc.get("noise")
        for key, db in (noise_doc.items() if isinstance(noise_doc, dict) else ()):
            if not isinstance(key, str):
                continue
            try:
                floor_text, zone_name = key.split("-", 1)
                noise_zone = (int(floor_text), zone_name)
                level = float(db)
            except (ValueError, TypeError):
                continue
            if noise_zone in ZONES and math.isfinite(level) and 0 <= level <= 150:
                noise[noise_zone] = level

        updated_at = _timestamp(doc.get("updated_at")) or time.time()
        if zone is None:
            floor_times[floor] = updated_at
        else:
            zone_times[(floor, zone)] = updated_at
        node_mode[floor] = "mongo"
        applied_floors.add(floor)

    for floor in FLOORS:
        if floor in floor_times:
            node_last_seen[floor] = floor_times[floor]
            continue
        floor_zones = [key for key in ZONES if key[0] == floor]
        if floor_zones and all(key in zone_times for key in floor_zones):
            node_last_seen[floor] = min(zone_times[key] for key in floor_zones)
        else:
            node_last_seen.pop(floor, None)
    return applied_floors


async def run(collection, state, noise, node_last_seen, node_mode, interval=2.0):
    """Keep the in-memory state fresh without blocking FastAPI's event loop."""
    while True:
        try:
            await asyncio.to_thread(
                apply_documents, collection, state, noise, node_last_seen, node_mode
            )
        except Exception:
            log.exception("MongoDB occupancy sync failed; retaining last known state")
        await asyncio.sleep(interval)
