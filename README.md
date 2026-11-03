# LibEdge — context-aware library seating

LibEdge keeps camera frames on the floor's edge computer. It sends anonymous seat states to a backend over the library network. The student phone connects to the library gateway over Bluetooth Low Energy (BLE); it does not call the backend over Wi-Fi or mobile data.

```
Camera ─► Jetson (edge/seat_monitor.py; frames stay local)
              │ anonymous seat states over library LAN
              ▼
        FastAPI backend ── context engine ── admin dashboard (#admin)
              │
              └─ BLE gateway (GATT) ◄── Bluetooth LE ──► student phone
```

## Demo without hardware

Run the backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

In another terminal, run the student app:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/?demo` for the student flow or `http://localhost:5173/#admin` for the live dashboard. The demo simulates occupancy; it does not start Bluetooth or read cameras.

## Real Bluetooth student connection

Run the BLE gateway on a Linux device with BlueZ and a Bluetooth adapter. The phone must be close enough to connect to the advertised `LibEdge` GATT service. The web app must be served from a secure HTTPS origin for Web Bluetooth; `localhost` is allowed for development. Hosting the page may use the library network, but recommendation requests and responses between phone and library use BLE.

```bash
cd backend
pip install -r requirements.txt
BLE=1 SIMULATE=0 NODE_KEY='replace-with-a-private-key' uvicorn main:app --host 0.0.0.0
```

Use Chrome on Android. iOS Safari does not support Web Bluetooth; use a compatible browser such as Bluefy or build a native app. `frontend/src/ble.js` contains the GATT UUIDs used by both sides. The desktop demo link is only for local development.

## Edge camera node

Install the edge dependencies on each Jetson, then provide a seat polygon file for that camera view. Every seat ID must exist in `backend/layout.py`; coordinates are pixels in the camera frame.

```bash
cd edge
pip install -r requirements.txt
python seat_monitor.py --source rtsp://CAM/stream --seats seats_f2.json \
  --backend http://BACKEND-LAN-IP:8000 --key 'replace-with-a-private-key'
```

`--source` can also be a prerecorded video file, which loops for demos. The edge node posts occupancy updates over the library LAN using `X-Node-Key`; set its `--key` to the backend's `NODE_KEY`. The admin dashboard reports whether each floor node is reporting or stale. Only configured seat states and optional zone noise values are accepted.

## Read occupancy snapshots from MongoDB

The backend can poll a MongoDB collection and use the latest document for each floor-zone pair. Store one up-to-date document per zone in the `floor_state` collection, with seat IDs matching `backend/layout.py`:

```json
{
  "_id": "floor-2-zone-B",
  "floor": 2,
  "zone": "B",
  "updated_at": "2026-11-03T12:00:00Z",
  "seats": {"2-B000": "empty", "2-B001": "occupied", "2-B002": "object"},
  "noise": {"2-B": 33}
}
```

Update that floor-zone document (upsert by its unique `_id`) whenever the YOLO pipeline produces a new snapshot. A snapshot without `zone` can represent a whole floor. Configure the backend using environment variables; do not put credentials in source files:

Seat IDs must use the existing `floor-zone-table-row-column` digits after the zone initial. For example, `2-B000` is floor 2, zone B, table 0, row 0, column 0; `2-B003` is the fourth seat on that table's first row, and `2-B010` is the first seat on its second row. Number tables from left to right, and number columns from left to right within each row. The current layout defines 4 seats per row and 2 rows per table.

```text
MONGODB_URI=<Atlas or local MongoDB URI>
MONGODB_DATABASE=libedge
MONGODB_COLLECTION=floor_state
MONGODB_POLL_SECONDS=2
NODE_KEY=<private edge-update key>
```

When `MONGODB_URI` is set, MongoDB is used instead of simulated occupancy. The backend keeps a short-lived in-memory copy for the existing recommendation engine, WebSocket dashboard, and BLE responses. The phone still communicates with the library over BLE.

On Windows PowerShell, set those variables in the same terminal that starts the backend, then run:

```powershell
$baseUri = Read-Host "Paste Atlas URI, leaving <db_password> unchanged"
$securePassword = Read-Host "Enter database-user password" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    $env:MONGODB_URI = $baseUri.Replace("<db_password>", [uri]::EscapeDataString($password))
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    Remove-Variable password, securePassword, baseUri, ptr -ErrorAction SilentlyContinue
}
$env:MONGODB_DATABASE = "libedge"
$env:MONGODB_COLLECTION = "floor_state"
$env:NODE_KEY = "<a private edge-update key>"
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The YOLO writer must update each floor's snapshot document with a fresh `updated_at` and a `seats` object. If its current MongoDB document shape differs from the example above, map it into this snapshot format before syncing.

## Current scope

Implemented: simulated floors, seat adjacency and ranking, student recommendations, optional BLE transport, edge camera inference and reporting, and a WebSocket admin dashboard. Zone noise currently uses configured baseline values. Noise sensors, forecasting, seat holds, HVAC control, multi-library sync, and student preference filters are not implemented.
