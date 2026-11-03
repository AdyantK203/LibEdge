"""Edge node (runs on each Jetson). Frames are read, analysed in memory and dropped.
Only {seat_id: state} leaves this process.

seats json:  {"floor": 2, "seats": {"2-B000": [[x,y],[x,y],[x,y],[x,y]], ...}}   (pixel polygons)
usage:  python seat_monitor.py --source rtsp://cam2/stream --seats seats_f2.json --weights weights/yolov8n.pt"""
import argparse, json, time
from collections import Counter, deque
import cv2, numpy as np, requests
from ultralytics import YOLO

PERSON, THINGS = 0, {24, 26, 63, 73}       # person; backpack, handbag, laptop, book

def classify(res, polys):
    out = {k: "empty" for k in polys}
    for box, cls in zip(res.boxes.xyxy.cpu().numpy(), res.boxes.cls.cpu().numpy().astype(int)):
        x1, y1, x2, y2 = box
        pt = (float((x1 + x2) / 2), float(y1 + .6 * (y2 - y1)))      # lower-centre suits overhead views
        for k, poly in polys.items():
            if cv2.pointPolygonTest(poly, pt, False) >= 0:
                if cls == PERSON: out[k] = "occupied"
                elif cls in THINGS and out[k] == "empty": out[k] = "object"
    return out

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--source", required=True); a.add_argument("--seats", required=True)
    a.add_argument("--weights", default="weights/yolov8n.pt"); a.add_argument("--backend", default="http://localhost:8000")
    a.add_argument("--key", default="dev-node-key"); a.add_argument("--interval", type=float, default=2.0)
    a.add_argument("--window", type=int, default=9)
    a = a.parse_args()
    if a.interval <= 0 or a.window <= 0:
        raise SystemExit("--interval and --window must be greater than zero")
    with open(a.seats, encoding="utf-8") as f:
        cfg = json.load(f)
    floor = cfg.get("floor")
    if floor not in (1, 2, 3):
        raise SystemExit("seat config floor must match a configured backend floor (1, 2, or 3)")
    if not isinstance(cfg.get("seats"), dict) or not cfg["seats"]:
        raise SystemExit("seat config must contain a non-empty 'seats' object")
    for seat_id, points in cfg["seats"].items():
        if not seat_id.startswith(f"{floor}-"):
            raise SystemExit(f"seat {seat_id!r} does not belong to configured floor {floor}")
        if not isinstance(points, list) or len(points) < 3 or any(not isinstance(p, list) or len(p) != 2 for p in points):
            raise SystemExit(f"seat {seat_id!r} must have at least three [x, y] polygon points")
    polys = {k: np.array(v, np.int32) for k, v in cfg["seats"].items()}
    hist = {k: deque(maxlen=a.window) for k in polys}               # majority vote: one bad frame can't flip a seat
    model, cap, last = YOLO(a.weights), cv2.VideoCapture(a.source), 0.0
    live = a.source.isdigit() or a.source.startswith("rtsp")
    while True:
        ok, frame = cap.read()
        if not ok:
            if live: time.sleep(1); cap.open(a.source)
            else: cap.set(cv2.CAP_PROP_POS_FRAMES, 0)                # loop a recorded demo clip
            continue
        for k, s in classify(model(frame, verbose=False, classes=[PERSON, *THINGS])[0], polys).items():
            hist[k].append(s)
        if time.time() - last >= a.interval:
            seats = {k: Counter(h).most_common(1)[0][0] for k, h in hist.items() if h}
            try: requests.post(f"{a.backend}/api/edge/update", json={"floor": cfg["floor"], "seats": seats},
                               headers={"X-Node-Key": a.key}, timeout=3)
            except requests.RequestException as e: print("backend unreachable:", e)
            last = time.time()

if __name__ == "__main__": main()
