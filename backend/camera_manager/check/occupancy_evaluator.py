"""Real-time Seat Occupancy Evaluator using Calibrated Anchors.

Evaluates video frames against pre-calibrated seat polygons or boxes.
Detects:
  - 'empty': Vacant seat
  - 'occupied': Person sitting / working at desk slot
  - 'object': Backpack, laptop, handbag, or books (seat hogging)

Uses sliding-window majority voting across frames to prevent flicker.
"""

import collections
import os
import cv2
import numpy as np
from ultralytics import YOLO

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

PERSON_CLASS = 0
ITEM_CLASSES = {24: "backpack", 26: "handbag", 63: "laptop", 73: "book"}


def find_model_path(name="yolo11n.pt"):
    candidates = [
        os.path.join(PROJECT_ROOT, name),
        os.path.join(PROJECT_ROOT, "src", name),
        os.path.join(SCRIPT_DIR, name),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return name


class SeatOccupancyTracker:
    def __init__(self, seat_polygons, window_size=7, model_path=None):
        """Args:

        seat_polygons: dict of {seat_id: [[x, y], [x, y], ...]}
        window_size: number of historical frames for majority voting
        """
        self.polygons = {
            sid: np.array(pts, dtype=np.int32)
            for sid, pts in seat_polygons.items()
        }
        self.window_size = window_size
        self.history = {sid: collections.deque(maxlen=window_size) for sid in self.polygons}
        self.model = YOLO(model_path or find_model_path("yolo11n.pt"))
        self.target_classes = [PERSON_CLASS] + list(ITEM_CLASSES.keys())

    def process_frame(self, frame, conf=0.22):
        """Classifies each seat polygon in the current frame and applies temporal

        smoothing.
        """
        h, w = frame.shape[:2]
        imgsz = min(max(w, h), 1280)
        res = self.model.predict(
            frame,
            imgsz=imgsz,
            classes=self.target_classes,
            conf=conf,
            verbose=False,
        )[0]

        # Instantaneous classifications for this frame
        frame_state = {sid: "empty" for sid in self.polygons}

        boxes = res.boxes.xyxy.cpu().numpy().astype(int)
        classes = res.boxes.cls.cpu().numpy().astype(int)

        for box, cls_id in zip(boxes, classes):
            # Check bottom-center of the bounding box (seat contact point)
            pt = (
                int((box[0] + box[2]) / 2),
                int(box[1] + 0.65 * (box[3] - box[1])),
            )

            for sid, poly in self.polygons.items():
                if cv2.pointPolygonTest(poly, pt, False) >= 0:
                    if cls_id == PERSON_CLASS:
                        frame_state[sid] = "occupied"
                    elif cls_id in ITEM_CLASSES and frame_state[sid] == "empty":
                        frame_state[sid] = "object"

        # Update historical deque and calculate majority vote
        smoothed_state = {}
        for sid in self.polygons:
            self.history[sid].append(frame_state[sid])
            vote = collections.Counter(self.history[sid]).most_common(1)[0][0]
            smoothed_state[sid] = vote

        return smoothed_state

    def render_overlay(self, frame, states):
        """Draws seats color-coded by state:

        Green = Empty, Blue/Red = Occupied, Yellow = Object/Hogged.
        """
        overlay = frame.copy()
        result = frame.copy()

        COLOR_MAP = {
            "empty": (46, 204, 113),      # Green
            "occupied": (70, 70, 235),   # Blue / Red
            "object": (30, 195, 240),     # Yellow
        }

        vacant_cnt = 0
        occupied_cnt = 0
        object_cnt = 0

        for sid, poly in self.polygons.items():
            st = states.get(sid, "unknown")
            color = COLOR_MAP.get(st, (180, 180, 180))

            if st == "empty":
                vacant_cnt += 1
            elif st == "occupied":
                occupied_cnt += 1
            else:
                object_cnt += 1

            # Polygon fill
            cv2.fillPoly(overlay, [poly], color)
            cv2.polylines(result, [poly], isClosed=True, color=color, thickness=2)

            # Label
            x_min = int(np.min(poly[:, 0]))
            y_min = int(np.min(poly[:, 1]))
            label = f"{sid} ({st[:3].upper()})"
            cv2.putText(
                result,
                label,
                (x_min, max(18, y_min - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                result,
                label,
                (x_min, max(18, y_min - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (20, 20, 20),
                1,
                cv2.LINE_AA,
            )

        blended = cv2.addWeighted(overlay, 0.25, result, 0.75, 0)

        # Status header
        banner = (
            f"Vacant: {vacant_cnt}  |  "
            f"Occupied: {occupied_cnt}  |  "
            f"Object/Hogged: {object_cnt}"
        )
        cv2.rectangle(blended, (10, 8), (440, 36), (20, 20, 20), -1)
        cv2.putText(
            blended,
            banner,
            (18, 27),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        return blended
