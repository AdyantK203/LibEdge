# LibEdge — context-aware library seating

LibEdge shows library seat availability in a browser. Students search for adjacent seats over HTTP; the staff dashboard receives seat updates over WebSocket. Both use the same backend. Bluetooth is no longer required.

```text
YOLO / camera node -> MongoDB snapshots or authenticated edge updates
                              |
                        FastAPI backend
                              |
               Student website + staff dashboard
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

Open `http://localhost:5173/` for the student flow or `http://localhost:5173/#admin` for the live dashboard. Without a MongoDB URI, the backend simulates occupancy. It does not read cameras.

## Connect from a phone

For local development, put the phone and computer on the same Wi-Fi network. Run `npm run dev` in `frontend` (the script binds Vite to the network), then open the Network URL printed by Vite on the phone, for example `http://192.168.1.20:5173/`. Keep the backend running on `127.0.0.1:8000`; Vite forwards `/api` and `/ws` requests to it. Allow the frontend port on your private network if Windows Firewall prompts. `localhost` on a phone refers to the phone, not the computer.

For access over mobile data or outside the library, deploy the built frontend and backend behind an HTTPS host that proxies `/api` and `/ws`. The development server is for local use. Admin authentication is still required before a public deployment; the Staff view link is navigation, not an access control.

## Windows quick start

From the project root, in the terminal containing your MongoDB environment variables:

```powershell
$env:MONGODB_DATABASE = "libedge"
$env:MONGODB_COLLECTION = "libedge_sample_state"
# Use the same private key as the edge writer if you use direct edge updates.
$env:NODE_KEY = [guid]::NewGuid().ToString("N")
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In a second terminal, from the project root:

```powershell
cd frontend
& "C:\Program Files\nodejs\npm.cmd" run dev
```

Restart the backend after Python changes. The frontend normally reloads automatically. To refresh sample snapshots, stop the backend in its terminal, run `..\.venv\Scripts\python.exe .\seed_sample_data.py`, and start the backend again. Seeding writes 60 historical snapshots across six zones; it does not generate a continuous live feed.

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

When `MONGODB_URI` is set, MongoDB is used instead of simulated occupancy. The backend keeps a short-lived in-memory copy for the existing recommendation engine and WebSocket dashboard. Phones request recommendations from the web API.

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

Implemented: simulated floors, MongoDB snapshot polling, seat adjacency and ranking, quiet preference, student web recommendations, light/dark themes, per-seat staff maps, and a WebSocket dashboard. The edge script can run inference and post seat states; the trained model and camera polygons must be supplied and validated for the real library.

Remaining: admin authentication before public hosting, real camera/model validation, actual noise sensors, and live video integration. Zone noise and walking times currently use configured values; landmark descriptions are examples. Seat maps show table layouts, not architectural floor plans. Seats are not reserved. Historical MongoDB snapshots become stale unless the writer refreshes them.
