# Camera manager

The camera manager is mounted on the LibEdge backend at `/camera-manager/` on port 8000. Its code and required model weights are kept under `backend/camera_manager`, so it does not require the separate YOLO folder after setup. It does not have staff authentication; keep the backend on localhost until authentication is added.

In PowerShell, set `MONGODB_URI` securely in the same terminal and then run:

```powershell
cd C:\Users\karad\Downloads\libedge\libedge
$env:MONGODB_DATABASE = 'libedge'
$env:MONGODB_COLLECTION = 'libedge_yolo_detections'
$env:NODE_KEY = '<your-private-node-key>'
& '.\.venv\Scripts\python.exe' -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The collection must match the one the LibEdge backend reads. Set `CAMERA_MODEL_DIR`, `CAMERA_POSE_MODEL`, or `CAMERA_DETECT_MODEL` only if you deliberately store models elsewhere. The manager uses reviewed calibration JSONs for publishing seat states; without them, detection is a preview only.

Restart both the backend and Vite frontend after updating. The `#cameras` page uses the Vite proxy or an equivalent production reverse proxy to reach `/camera-manager/` on port 8000. Set `CAMERA_MANAGER_ENABLED=0` to start the seating backend without the camera manager.
