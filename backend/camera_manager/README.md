# LibEdge camera manager

The camera manager is part of the LibEdge backend. It is not a separate server and does not need the old `Downloads\YOLO` project.

| Service | Address |
| --- | --- |
| Staff entry point | `http://127.0.0.1:5173/#cameras` |
| Direct manager route | `http://127.0.0.1:8000/camera-manager/` |
| Camera API | `http://127.0.0.1:8000/camera-manager/api/cameras` |

The manager uses the same FastAPI process, MongoDB connection, and `MONGODB_COLLECTION` as the seating recommendation backend. It stores camera configuration in the `cameras` collection and writes approved occupancy snapshots into the configured floor-state collection.

## Local files

```text
backend/camera_manager/app.py       Manager API, scheduler, and inference flow
backend/camera_manager/models/      Local YOLO person-pose and detection weights
backend/camera_manager/src/         LibEdge validation contract and posture helper
backend/camera_manager/templates/   Camera management interface
```

`yolo11m.pt` and `yolo11m-pose.pt` are included locally. By default, no path outside the LibEdge repository is required.

## Start the integrated backend

Install the camera and API dependencies once, from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

In the terminal that has your securely set `MONGODB_URI`:

```powershell
cd C:\Users\karad\Downloads\libedge\libedge
$env:MONGODB_DATABASE = "libedge"
$env:MONGODB_COLLECTION = "floor_state"
$env:NODE_KEY = "choose-a-private-local-key"
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start the Vite frontend in another terminal, then open `/#cameras` from the staff dashboard. The frontend proxies the camera-manager route to port 8000.

Set `CAMERA_MANAGER_ENABLED=0` only if you intentionally want to start the seating backend without loading YOLO and camera-manager routes.

## Add a camera

1. Go to **Staff dashboard → Manage cameras**.
2. Add a camera name, its floor and zone, source, and polling interval.
3. The source may be an RTSP URL, HTTP stream, or a local video file path.
4. Select **Test now** to run an on-demand preview and verify that the source can be opened.
5. Attach a reviewed calibration file before treating its output as live seating data.

The scheduler analyzes each configured source at its configured interval. Inference runs off the API request loop, so testing or camera polling does not block regular student recommendations.

## Calibration and publishing rules

Automatic person/chair detection is useful for a preview, but it does not know the permanent identity of a physical seat. A camera can publish to LibEdge only when it has a reviewed seat-polygon calibration that:

- has the exact source image resolution;
- names valid LibEdge seat IDs, such as `2-B000`;
- has `calibration_reviewed: true`;
- matches the configured floor and zone;
- is the only active camera publishing that floor-zone snapshot.

When those conditions are met, the manager writes documents such as:

```json
{
  "_id": "floor-2-zone-B",
  "floor": 2,
  "zone": "B",
  "updated_at": "2026-11-03T12:00:00Z",
  "seats": { "2-B000": "empty", "2-B001": "occupied" }
}
```

The main LibEdge backend polls that same collection and broadcasts changes to the student and staff interfaces. A camera without calibration remains preview-only and cannot overwrite seating availability.

## Operational notes

- Keep camera manager and staff routes on localhost or behind authentication until staff access control is implemented.
- Use a single writer for each floor-zone. The manager rejects duplicate zone ownership rather than silently choosing one camera.
- If a camera stream fails to open, its status becomes offline; the previous snapshot is not replaced by an invented one.
- Override model locations only when needed: `CAMERA_MODEL_DIR`, `CAMERA_POSE_MODEL`, and `CAMERA_DETECT_MODEL`.
- Do not put MongoDB credentials in source code, camera configuration files, or Git commits.
