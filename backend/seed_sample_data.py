"""Write deterministic LibEdge occupancy snapshots to a MongoDB test collection."""
import os
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient

from layout import BY_ZONE, ZONES

SNAPSHOTS_PER_ZONE = 10
SNAPSHOT_INTERVAL_SECONDS = 30


def sample_status(seat, snapshot_index):
    """Repeatable seat mix that shifts over time to resemble changing occupancy."""
    value = (seat.table * 7 + seat.r * 3 + seat.c * 5 + seat.floor + snapshot_index * 3) % 10
    if value in (0, 1):
        return "occupied"
    if value == 2:
        return "object"
    return "empty"


def main():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise SystemExit("Set MONGODB_URI in this PowerShell session before running this script.")

    db_name = os.getenv("MONGODB_DATABASE", "libedge")
    collection_name = os.getenv("MONGODB_COLLECTION", "libedge_sample_state")
    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    try:
        client.admin.command("ping")
        collection = client[db_name][collection_name]
        now = datetime.now(timezone.utc)
        for (floor, zone), config in ZONES.items():
            for snapshot_index in range(SNAPSHOTS_PER_ZONE):
                seats = {
                    seat.id: sample_status(seat, snapshot_index)
                    for seat in BY_ZONE[(floor, zone)]
                }
                # Reuse the original ID for the newest snapshot, so repeat runs
                # refresh the current zone document instead of accumulating it.
                if snapshot_index == SNAPSHOTS_PER_ZONE - 1:
                    document_id = f"sample-floor-{floor}-zone-{zone}"
                else:
                    document_id = f"sample-floor-{floor}-zone-{zone}-history-{snapshot_index:02d}"
                document = {
                    "_id": document_id,
                    "floor": floor,
                    "zone": zone,
                    "updated_at": now - timedelta(
                        seconds=(SNAPSHOTS_PER_ZONE - 1 - snapshot_index) * SNAPSHOT_INTERVAL_SECONDS
                    ),
                    "seats": seats,
                    "noise": {f"{floor}-{zone}": config["noise"]},
                    "sample_data": True,
                    "sample_snapshot": snapshot_index + 1,
                }
                collection.replace_one({"_id": document_id}, document, upsert=True)
        print(
            f"Wrote {len(ZONES) * SNAPSHOTS_PER_ZONE} sample snapshots "
            f"({SNAPSHOTS_PER_ZONE} per zone, spanning "
            f"{(SNAPSHOTS_PER_ZONE - 1) * SNAPSHOT_INTERVAL_SECONDS} seconds) to "
            f"{db_name}.{collection_name}; no other documents were changed."
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
