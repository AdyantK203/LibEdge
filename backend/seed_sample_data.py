"""Write deterministic LibEdge occupancy snapshots to a MongoDB test collection."""
import os
from datetime import datetime, timezone

from pymongo import MongoClient

from layout import BY_ZONE, ZONES


def sample_status(seat):
    """Repeatable mix of available, occupied, and obstructed seats for the demo."""
    value = (seat.table * 7 + seat.r * 3 + seat.c * 5 + seat.floor) % 10
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
        updated_at = datetime.now(timezone.utc)
        for (floor, zone), config in ZONES.items():
            seats = {
                seat.id: sample_status(seat)
                for seat in BY_ZONE[(floor, zone)]
            }
            document = {
                "_id": f"sample-floor-{floor}-zone-{zone}",
                "floor": floor,
                "zone": zone,
                "updated_at": updated_at,
                "seats": seats,
                "noise": {f"{floor}-{zone}": config["noise"]},
                "sample_data": True,
            }
            collection.replace_one({"_id": document["_id"]}, document, upsert=True)
        print(
            f"Wrote {len(ZONES)} sample floor-zone snapshots to "
            f"{db_name}.{collection_name}; no other documents were changed."
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
