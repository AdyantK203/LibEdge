from camera_manager.src.posture import posture_evidence
import os

import time
import json
import asyncio
import threading
import cv2
import numpy as np
import torch
import pymongo
from camera_manager.src.libedge_contract import validate_config, snapshot
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from ultralytics import YOLO

import warnings
warnings.filterwarnings("ignore")

torch.backends.cudnn.benchmark = True

# ================= Setup & Models =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Keep camera code, models and generated previews inside LibEdge by default.
# Environment overrides remain available for a production deployment.
DATA_DIR = os.environ.get("CAMERA_DATA_DIR", BASE_DIR)
MODEL_DIR = os.environ.get("CAMERA_MODEL_DIR", os.path.join(BASE_DIR, "models"))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# MongoDB Setup - Unified database "libedge" for both cameras and floor states to match LibEdgeFrontend
MONGO_URI = os.environ.get("MONGODB_URI", os.environ.get("MONGO_URI", os.environ.get("MONGO_URL", "mongodb://localhost:27017/")))
mongo_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = mongo_client[os.environ.get("MONGODB_DATABASE", "libedge")]
cameras_collection = db["cameras"]
floor_state_collection = db[os.environ.get("MONGODB_COLLECTION", "floor_state")]

DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"

POSE_PATH = os.environ.get("CAMERA_POSE_MODEL", os.path.join(MODEL_DIR, "yolo11m-pose.pt"))
DETECT_PATH = os.environ.get("CAMERA_DETECT_MODEL", os.path.join(MODEL_DIR, "yolo11m.pt"))
if not os.path.exists(POSE_PATH):
    POSE_PATH = os.path.join(BASE_DIR, "yolo11n-pose.pt")
if not os.path.exists(DETECT_PATH):
    DETECT_PATH = os.path.join(BASE_DIR, "yolo11n.pt")

print(f"[*] Starting LibEdge Vision Models on {DEVICE}...")
pose_model = YOLO(POSE_PATH)
detect_model = YOLO(DETECT_PATH)

if DEVICE != "cpu":
    pose_model.to(DEVICE).to(torch.float16)
    detect_model.to(DEVICE).to(torch.float16)

templates = Jinja2Templates(directory=TEMPLATES_DIR)
CAMERAS = []


def load_internal_store():
    global CAMERAS
    try:
        CAMERAS = list(cameras_collection.find({}, {"_id": False}))
        for cam in CAMERAS:
            cam.setdefault("total_seats", 0)
            cam.setdefault("occupied", 0)
            cam.setdefault("vacant", 0)
            cam.setdefault("seats", [])
    except Exception:
        CAMERAS = []
        
CAMERA_CONFIG_KEYS = {
    "id", "name", "floor", "zone", "zone_code", "source",
    "interval_sec", "person_conf", "chair_conf", "seat_config",
    "status", "last_tested", "output_video"
}


def persist_store():
    # Only camera stream/hardware config goes into cameras collection
    for cam in CAMERAS:
        cam_config = {k: cam[k] for k in CAMERA_CONFIG_KEYS if k in cam}
        cameras_collection.update_one(
            {"id": cam["id"]},
            {
                "$set": cam_config,
                "$unset": {
                    "total_seats": "",
                    "occupied": "",
                    "vacant": "",
                    "seats": ""
                }
            },
            upsert=True
        )
    # All room/floor seat analysis, counts, and states are published into floor_state
    publish_floor_states()


def infer_zone_code(cam):
    """Extract layout zone code from camera config (e.g. 'A', 'B', 'East', 'West').

    Checks the explicit zone_code field first; falls back to parsing the
    free-text zone name so existing cameras keep working.
    """
    zc = cam.get("zone_code")
    if zc:
        return zc
    zone = cam.get("zone", "")
    for code in ("East", "West"):
        if code.lower() in zone.lower():
            return code
    parts = zone.split()
    if parts and len(parts[-1]) <= 4:
        return parts[-1]
    return ""


def publish_floor_states():
    """Publish only successful calibrated measurements, one document per zone."""
    owners = {}
    for camera in CAMERAS:
        doc = camera.get("libedge_snapshot")
        if doc:
            owners[doc['_id']] = owners.get(doc['_id'], 0) + 1
    for cam in CAMERAS:
        doc = cam.get("libedge_snapshot")
        if not doc:
            continue
        if owners[doc["_id"]] != 1:
            print(f"[!] Multiple cameras claim {doc['_id']}; use one calibrated camera per zone")
            continue
        try:
            floor_state_collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        except Exception as exc:
            print(f"[!] Snapshot write failed for {cam['id']}: {type(exc).__name__}")


TRACKERS = {}

def analyze_camera_frame(frame, cam, person_conf, chair_conf):
    """Use fixed polygons when configured; dynamic detection is preview-only."""
    config_path = cam.get("seat_config")
    if not config_path:
        cam.pop("libedge_snapshot", None)
        return analyze_frame_dynamically(frame, person_conf, chair_conf)
    path = config_path if os.path.isabs(config_path) else os.path.join(DATA_DIR, config_path)
    with open(path, encoding="utf-8") as handle:
        cfg = json.load(handle)
    polygons = validate_config(cfg, require_review=True)
    if cfg.get("image_size") != [frame.shape[1], frame.shape[0]]:
        raise ValueError("Camera resolution does not match its seat calibration")
    floor_num = int(''.join(filter(str.isdigit, str(cam['floor']))))
    if cfg['floor'] != floor_num or cfg['zone'] != infer_zone_code(cam):
        raise ValueError("Camera floor/zone does not match its calibration")
    key = (cam['id'], cam['source'], json.dumps(cfg, sort_keys=True))
    if key not in TRACKERS:
        from camera_manager.check.occupancy_evaluator import SeatOccupancyTracker
        TRACKERS[key] = SeatOccupancyTracker(polygons, model_path=DETECT_PATH)
    states = TRACKERS[key].process_frame(frame, conf=person_conf)
    cam['libedge_snapshot'] = snapshot(cfg['floor'], cfg['zone'], states)
    seats = []
    for sid, status in states.items():
        points = polygons[sid]
        seats.append({'seat_id': sid, 'row': int(sid[-2]) + 1, 'seat': int(sid[-1]) + 1,
                      'status': {'empty': 'Vacant', 'occupied': 'Occupied', 'object': 'Object'}[status],
                      'box': [min(p[0] for p in points), min(p[1] for p in points),
                              max(p[0] for p in points), max(p[1] for p in points)]})
    return len(seats), sum(v == 'occupied' for v in states.values()), sum(v == 'empty' for v in states.values()), seats


# ================= Dynamic Geometry & Association =================
def is_sitting_posture(keypoints, confidences):
    # Hidden knees do not establish posture. Retain only positive pose evidence.
    points = [[float(x), float(y), float(conf)] for (x, y), conf in zip(keypoints, confidences)]
    return posture_evidence(points) == "seated"


def box_contains_point(box, point):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def compute_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter = max(0, xB - xA) * max(0, yB - yA)
    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    union = areaA + areaB - inter
    return (inter / union) if union > 0 else 0


def analyze_frame_dynamically(frame, person_conf=0.25, chair_conf=0.17):
    h, w = frame.shape[:2]
    imgsz = min(max(w, h), 960)

    pose_res = pose_model.predict(frame, imgsz=imgsz, conf=person_conf, device=DEVICE, verbose=False)[0]
    seated_people = []
    if pose_res.keypoints is not None:
        boxes = pose_res.boxes.xyxy.cpu().numpy().astype(int)
        kpts = pose_res.keypoints.xy.cpu().numpy()
        confs = pose_res.keypoints.conf.cpu().numpy()

        for i in range(len(boxes)):
            if is_sitting_posture(kpts[i], confs[i]):
                if confs[i][11] > 0.3 or confs[i][12] > 0.3:
                    hx = float((kpts[i][11][0] + kpts[i][12][0]) / 2.0)
                    hy = float((kpts[i][11][1] + kpts[i][12][1]) / 2.0)
                else:
                    hx = float((boxes[i][0] + boxes[i][2]) / 2.0)
                    hy = float(boxes[i][1] + (boxes[i][3] - boxes[i][1]) * 0.75)
                seated_people.append({"box": boxes[i], "hip": (hx, hy)})

    detect_res = detect_model.predict(frame, imgsz=imgsz, classes=[56], conf=chair_conf, device=DEVICE, verbose=False)[0]
    raw_chairs = []
    for box in detect_res.boxes:
        b = box.xyxy[0].cpu().numpy().astype(int)
        cls_id = int(box.cls[0].cpu().numpy())
        conf = float(box.conf[0].cpu().numpy())
        bw = b[2] - b[0]
        bh = b[3] - b[1]
        if cls_id == 56 and conf >= chair_conf and (bw / float(bh)) <= 1.6:
            raw_chairs.append(b)

    raw_chairs = sorted(raw_chairs, key=lambda c: c[1])
    rows = []
    current_row = []
    row_threshold = 45

    for c in raw_chairs:
        if not current_row:
            current_row.append(c)
        else:
            avg_y = sum(item[1] for item in current_row) / len(current_row)
            if abs(c[1] - avg_y) <= row_threshold:
                current_row.append(c)
            else:
                rows.append(current_row)
                current_row = [c]
    if current_row:
        rows.append(current_row)

    structured_seats = []
    occupied_count = 0
    vacant_count = 0

    for r_idx, row in enumerate(rows):
        row_sorted = sorted(row, key=lambda c: c[0])
        for s_idx, cbox in enumerate(row_sorted):
            seat_id = f"R{r_idx+1}S{s_idx+1}"
            is_occupied = any(
                box_contains_point(cbox, p["hip"]) or compute_iou(cbox, p["box"]) > 0.15
                for p in seated_people
            )
            if is_occupied:
                occupied_count += 1
                status = "Occupied"
            else:
                vacant_count += 1
                status = "Vacant"

            structured_seats.append({
                "seat_id": seat_id,
                "row": r_idx + 1,
                "seat": s_idx + 1,
                "box": cbox.tolist(),
                "status": status
            })

    total_seats = occupied_count + vacant_count
    return total_seats, occupied_count, vacant_count, structured_seats


def render_display(frame, structured_seats):
    overlay = frame.copy()
    occ_count = sum(1 for s in structured_seats if s["status"] == "Occupied")
    vac_count = sum(1 for s in structured_seats if s["status"] == "Vacant")

    for s in structured_seats:
        b = s["box"]
        is_occ = s["status"] == "Occupied"
        color = (70, 70, 235) if is_occ else (30, 195, 240) if s["status"] == "Object" else (46, 204, 113)
        
        if not is_occ:
            cv2.rectangle(overlay, (b[0], b[1]), (b[2], b[3]), color, -1)
        cv2.rectangle(frame, (b[0], b[1]), (b[2], b[3]), color, 2)
        cv2.putText(frame, f"{s['seat_id']}", (b[0], max(18, b[1] - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

    banner = f"Vacant: {vac_count}  |  Occupied: {occ_count}"
    cv2.rectangle(frame, (8, 6), (280, 36), (20, 20, 20), -1)
    cv2.putText(frame, banner, (14, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)

    return cv2.addWeighted(overlay, 0.20, frame, 0.80, 0)


INFERENCE_LOCK = threading.Lock()

def run_camera_test(cam, duration_sec=0):
    # Scheduler and test-now requests share the same models and trackers.
    with INFERENCE_LOCK:
        cam.pop("libedge_snapshot", None)
        try:
            _run_camera_test(cam, duration_sec)
        except Exception as exc:
            cam.pop("libedge_snapshot", None)
            cam["status"] = f"Analysis failed ({type(exc).__name__})"
            print(f"[!] Camera {cam['id']}: {exc}")

def _run_camera_test(cam, duration_sec=0):
    source = cam["source"]
    person_conf = float(cam.get("person_conf", 0.25))
    chair_conf = float(cam.get("chair_conf", 0.17))
    is_live = source.startswith("rtsp://") or source.startswith("http://")
    if not is_live:
        source = os.path.join(DATA_DIR, source) if not os.path.isabs(source) else source

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        cam["status"] = "Offline (Source unreachable)"
        cam["last_tested"] = datetime.now().strftime("%H:%M:%S")
        return

    if duration_sec > 0:
        out_path = os.path.join(OUTPUTS_DIR, f"{cam['id']}_test.webm")
        native_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        native_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = 25.0

        fourcc = cv2.VideoWriter_fourcc(*"VP80")
        out = cv2.VideoWriter(out_path, fourcc, fps, (native_w, native_h))

        start_time = time.time()
        totals, occs, vacs, last_seats = [], [], [], []
        frame_idx = 0
        FRAME_STRIDE = 2
        cached_seats = []
        cached_tot, cached_occ, cached_vac = 0, 0, 0
        
        while time.time() - start_time < duration_sec:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    break
            
            frame_idx += 1
            if frame_idx % FRAME_STRIDE == 0 or frame_idx == 1:
                cached_tot, cached_occ, cached_vac, cached_seats = analyze_camera_frame(frame, cam, person_conf, chair_conf)

            totals.append(cached_tot)
            occs.append(cached_occ)
            vacs.append(cached_vac)
            last_seats = cached_seats
            
            rendered = render_display(frame, cached_seats)
            out.write(rendered)

        cap.release()
        out.release()

        if not totals:
            cam["status"] = "No Video Signal"
            cam["last_tested"] = datetime.now().strftime("%H:%M:%S")
            return

        cam["total_seats"] = int(round(sum(totals) / len(totals)))
        cam["occupied"] = int(round(sum(occs) / len(occs)))
        cam["vacant"] = int(round(sum(vacs) / len(vacs)))
        cam["seats"] = last_seats
        cam["output_video"] = f"/outputs/{cam['id']}_test.webm"
        cam["status"] = "Processed test clip"
    else:
        ret, frame = False, None
        if is_live:
            for _ in range(5):
                ret, frame = cap.read()
                if not ret:
                    break
        else:
            ret, frame = cap.read()

        cap.release()

        if not ret or frame is None:
            cam["status"] = "No Video Signal"
            cam["last_tested"] = datetime.now().strftime("%H:%M:%S")
            return

        total, occ, vac, seats = analyze_camera_frame(frame, cam, person_conf, chair_conf)
        cam["total_seats"] = total
        cam["occupied"] = occ
        cam["vacant"] = vac
        cam["seats"] = seats
        cam["status"] = "Active"

    cam["last_tested"] = datetime.now().strftime("%H:%M:%S")


# ================= Background Polling Task =================
async def background_scheduler():
    last_exec = {}
    while True:
        now = time.time()
        updated = False
        for cam in CAMERAS:
            cid = cam["id"]
            interval = int(cam.get("interval_sec", 30))
            if now - last_exec.get(cid, 0) >= interval:
                last_exec[cid] = now
                await asyncio.to_thread(run_camera_test, cam, 0)
                updated = True
        if updated:
            await asyncio.to_thread(persist_store)
            await manager.broadcast(current_state())
        await asyncio.sleep(1)


class ConnectionManager:
    def __init__(self):
        self.active_connections = list()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()


def current_state():
    total_occ = sum(c.get("occupied", 0) for c in CAMERAS)
    total_tot = sum(c.get("total_seats", 0) for c in CAMERAS)
    total_avail = sum(c.get("vacant", 0) for c in CAMERAS)
    overall_occ_pct = round((total_occ / total_tot * 100) if total_tot > 0 else 0)

    floors_map = {}
    for c in CAMERAS:
        f = c.get("floor", "Floor 1")
        if f not in floors_map:
            floors_map[f] = {"zones": [], "occ_sum": 0, "tot_sum": 0}
        
        vac = c.get("vacant", 0)
        occ = c.get("occupied", 0)
        tot = c.get("total_seats", 0)
        occ_pct = round((occ / tot * 100) if tot > 0 else 0)
        
        floors_map[f]["zones"].append({
            "label": c.get("zone", c.get("name")),
            "empty": vac,
            "max_group": min(vac, 4),
            "noise": 35.0
        })
        floors_map[f]["occ_sum"] += occ
        floors_map[f]["tot_sum"] += tot

    floors_list = []
    for f_name, data in floors_map.items():
        f_num = ''.join(filter(str.isdigit, f_name)) or "1"
        f_tot = data["tot_sum"]
        f_occ = data["occ_sum"]
        f_pct = round((f_occ / f_tot * 100) if f_tot > 0 else 0)
        floors_list.append({
            "floor": int(f_num),
            "occ": f_pct,
            "zones": data["zones"]
        })

    nodes = [
        {
            "floor": 1,
            "mode": "edge",
            "age_seconds": 2
        }
    ]

    return {
        "occupancy": overall_occ_pct,
        "available": total_avail,
        "quietest": CAMERAS[0]["zone"] if CAMERAS else "Quiet Zone A",
        "largest": "Floor 1",
        "largest_size": max([c.get("vacant", 0) for c in CAMERAS], default=4),
        "floors": floors_list,
        "nodes": nodes
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(load_internal_store)
    task = asyncio.create_task(background_scheduler())
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.to_thread(mongo_client.close)

app = FastAPI(title="LibEdge Camera & Zone Manager", lifespan=lifespan)

from fastapi.staticfiles import StaticFiles
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")


# ================= REST Endpoints =================
class CameraModel(BaseModel):
    id: str
    name: str
    floor: str
    zone: str
    source: str
    interval_sec: int
    person_conf: float = 0.25
    chair_conf: float = 0.17
    zone_code: str = ""
    seat_config: str = ""


@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/cameras")
async def get_all_cameras():
    return JSONResponse(CAMERAS)


@app.get("/api/state")
async def get_state():
    return current_state()


@app.get("/api/recommend")
async def recommend(group: int = 2):
    cam = CAMERAS[0] if CAMERAS else None
    vac = cam.get("vacant", 4) if cam else 4
    ok = vac >= group
    
    seats = cam.get("seats", []) if cam else []
    map_str = "eeee|eeee"
    if seats:
        rows = {}
        for s in seats:
            rows.setdefault(s["row"], []).append("o" if s["status"] == "Occupied" else "e")
        map_str = "|".join("".join(row[:4]) for row in rows.values()) or "eeee|eeee"

    return {
        "ok": ok,
        "g": group,
        "f": 1,
        "z": cam.get("zone", "Quiet Zone A") if cam else "Quiet Zone A",
        "n": vac,
        "q": "low",
        "t": 45,
        "o": cam.get("occupied", 0) if cam else 50,
        "map": map_str,
        "fl": [[1, vac, vac]],
        "best": vac
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json(current_state())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/cameras")
async def save_camera(data: CameraModel):
    global CAMERAS
    for i, c in enumerate(CAMERAS):
        if c["id"] == data.id:
            CAMERAS[i]["name"] = data.name
            CAMERAS[i]["floor"] = data.floor
            CAMERAS[i]["zone"] = data.zone
            CAMERAS[i]["source"] = data.source
            CAMERAS[i]["interval_sec"] = data.interval_sec
            CAMERAS[i]["person_conf"] = data.person_conf
            CAMERAS[i]["chair_conf"] = data.chair_conf
            CAMERAS[i]["zone_code"] = data.zone_code
            CAMERAS[i]["seat_config"] = data.seat_config
            CAMERAS[i].pop("libedge_snapshot", None)
            await asyncio.to_thread(persist_store)
            await manager.broadcast(current_state())
            return {"status": "updated"}

    new_entry = {
        "id": data.id,
        "name": data.name,
        "floor": data.floor,
        "zone": data.zone,
        "source": data.source,
        "interval_sec": data.interval_sec,
        "person_conf": data.person_conf,
        "chair_conf": data.chair_conf,
        "zone_code": data.zone_code,
        "seat_config": data.seat_config,
        "total_seats": 0,
        "occupied": 0,
        "vacant": 0,
        "seats": [],
        "output_video": "",
        "last_tested": "Pending",
        "status": "Initialized"
    }
    CAMERAS.append(new_entry)
    await asyncio.to_thread(persist_store)
    await manager.broadcast(current_state())
    return {"status": "created"}


@app.delete("/api/cameras/{cam_id}")
async def delete_camera(cam_id: str):
    global CAMERAS
    CAMERAS = [c for c in CAMERAS if c["id"] != cam_id]
    await asyncio.to_thread(cameras_collection.delete_one, {"id": cam_id})
    await asyncio.to_thread(persist_store)
    await manager.broadcast(current_state())
    return {"status": "deleted"}


@app.post("/api/cameras/{cam_id}/test-now")
async def test_camera_now(cam_id: str):
    for c in CAMERAS:
        if c["id"] == cam_id:
            await asyncio.to_thread(run_camera_test, c, 5.0)
            await asyncio.to_thread(persist_store)
            await manager.broadcast(current_state())
            return {
                "status": c["status"],
                "total_seats": c["total_seats"], 
                "occupied": c["occupied"], 
                "vacant": c["vacant"],
                "seats": c["seats"],
                "output_video": c.get("output_video", "")
            }
    return JSONResponse(status_code=404, content={"status": "not found"})
