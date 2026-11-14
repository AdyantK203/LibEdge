# LibEdge

LibEdge is a context-aware library seating system. It turns anonymous seat-state snapshots into live availability, group-seat recommendations, staff floor views, and directions to the recommended table.

Bluetooth is not used. The student and staff interfaces communicate with the backend over HTTP and WebSocket connections.

```text
Camera/video -> YOLO seat analysis -> MongoDB floor-zone snapshots
                                      |
                                LibEdge backend :8000
                                      |
             Student website + staff dashboard + camera manager
```

## Included features

- Student seat search for a group size, with an optional quieter-place preference.
- Live availability, occupancy, noise, adjacent-seat count, and alternative zone recommendations.
- Light/dark themes plus desktop and phone-preview layouts.
- Interactive table tiles for every recommendation and a **Locate seats** route map for all three floors.
- Staff dashboard with per-floor, per-zone tile maps and live WebSocket updates.
- Integrated camera manager for adding a camera/video source, previewing detection, and publishing reviewed seat states.
- MongoDB polling for occupancy snapshots; sample data can be seeded for a full UI test.

## Project layout

```text
backend/                  FastAPI seating API, MongoDB sync, recommendation engine
backend/camera_manager/   Integrated camera manager, YOLO code, local model weights
frontend/                 React/Vite student, staff, map, and camera-manager UI
edge/                     Optional separate edge-node writer for Jetson/LAN deployments
```

The YOLO camera manager and its model weights are inside this repository. You do not need to start the separate `Downloads\YOLO` project.

## One-time Windows setup

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

Install frontend packages once:

```powershell
cd .\frontend
& "C:\Program Files\nodejs\npm.cmd" install
```

## Start LibEdge

Set `MONGODB_URI` securely in the same PowerShell session before starting the backend. Do not put database passwords in code or commit them to Git.

For the normal MongoDB-backed app:

```powershell
cd C:\Users\karad\Downloads\libedge\libedge
$env:MONGODB_DATABASE = "libedge"
$env:MONGODB_COLLECTION = "floor_state"
$env:NODE_KEY = "choose-a-private-local-key"
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

For a no-database UI demo, leave `MONGODB_URI` unset and use the same command. The backend starts with simulated occupancy.

Start the frontend in another terminal:

```powershell
cd C:\Users\karad\Downloads\libedge\libedge\frontend
& "C:\Program Files\nodejs\node.exe" .\node_modules\vite\bin\vite.js --host 127.0.0.1 --port 5173
```

Open:

| Interface | URL |
| --- | --- |
| Student seating | `http://127.0.0.1:5173/` |
| Staff dashboard | `http://127.0.0.1:5173/#admin` |
| Camera manager | `http://127.0.0.1:5173/#cameras` |
| Backend state API | `http://127.0.0.1:8000/api/state` |

The Vite development server forwards `/api`, `/ws`, and `/camera-manager` to the single backend on port 8000. There is no separate camera-manager port.

## MongoDB snapshot contract

The backend reads the latest snapshot for each floor-zone pair from the collection named by `MONGODB_COLLECTION`. A YOLO pipeline or the integrated camera manager writes the same format.

```json
{
  "_id": "floor-2-zone-B",
  "floor": 2,
  "zone": "B",
  "updated_at": "2026-11-03T12:00:00Z",
  "seats": {
    "2-B000": "empty",
    "2-B001": "occupied",
    "2-B002": "object"
  },
  "noise": { "2-B": 33 }
}
```

Seat IDs use `floor-zone-table-row-column`. For example, `2-B000` means floor 2, Zone B, table 0, row 0, column 0. Each table has two rows and four seats per row. Valid layout IDs are defined in `backend/layout.py`.

Useful environment variables:

```text
MONGODB_URI=<Atlas or local MongoDB URI>
MONGODB_DATABASE=libedge
MONGODB_COLLECTION=floor_state
MONGODB_POLL_SECONDS=2
NODE_KEY=<private value used by authenticated edge writers>
CAMERA_MANAGER_ENABLED=1
```

The collection name must be identical for the backend and camera manager. If you use `libedge_yolo_detections` or `libedge_sample_state` instead of `floor_state`, set `MONGODB_COLLECTION` to that same value before starting the backend.

## Seed realistic sample data

With `MONGODB_URI` set and the backend stopped, run:

```powershell
cd C:\Users\karad\Downloads\libedge\libedge
$env:MONGODB_DATABASE = "libedge"
$env:MONGODB_COLLECTION = "libedge_sample_state"
.\.venv\Scripts\python.exe .\backend\seed_sample_data.py
```

Then start the backend with `MONGODB_COLLECTION` still set to `libedge_sample_state`. The script writes six floor-zone snapshots and does not change unrelated documents.

## Camera manager

Open the staff dashboard and choose **Manage cameras**, or visit `/#cameras`. Camera management is served by the same FastAPI backend at `/camera-manager/`.

1. Add a camera name, floor, zone, source (RTSP URL, HTTP URL, or local video path), and interval.
2. Use **Test now** to make a detection preview.
3. Create and review a seat-polygon calibration for that exact camera resolution.
4. Mark the calibration reviewed only after confirming its LibEdge seat IDs.
5. The manager then writes one current snapshot per calibrated floor-zone into the configured MongoDB collection.

Dynamic chair/person detection is preview-only. It intentionally does not publish an unreviewed seating layout to the student app. See [the camera manager guide](backend/camera_manager/README.md) for details.

## Maps and seating directions

Every recommendation contains a selectable table map. Choosing a different suitable zone updates the tile map, availability statistics, and **Locate seats** destination. The directions panel uses built-in floor-plan illustrations for Floors 1–3, consistent lift/stair access, landmarks, and a blue route from the lift to the selected table.

The routes and landmarks are designed for the current demonstration; seats are not reserved by selecting or locating them.

## Deployment notes

- Use HTTPS and proper staff authentication before exposing the staff dashboard or camera manager outside a trusted network.
- Keep MongoDB credentials in environment variables or a secrets manager only.
- For a real camera installation, calibrate each zone separately and monitor stale timestamps / camera-offline states.
- The `edge/` folder remains available for a future NVIDIA Jetson deployment that posts authenticated updates over the LAN.
