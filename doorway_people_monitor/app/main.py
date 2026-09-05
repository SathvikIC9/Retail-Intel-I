import csv
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO


# =========================================================
# PATHS / CONFIG
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f) or {}

CAMERA = CONFIG["camera"]
MODEL_CFG = CONFIG["model"]
TRACK_CFG = CONFIG["tracking"]
PORTAL = CONFIG["portal"]

CSV_PATH = ROOT / CONFIG["database"]["csv_path"]
CSV_PATH.parent.mkdir(parents=True, exist_ok=True)


# =========================================================
# CAMERA
# =========================================================

camera_source = CAMERA["source"]

cap = cv2.VideoCapture(
    camera_source,
    cv2.CAP_DSHOW
)

cap.set(
    cv2.CAP_PROP_FRAME_WIDTH,
    CAMERA["width"]
)

cap.set(
    cv2.CAP_PROP_FRAME_HEIGHT,
    CAMERA["height"]
)

cap.set(
    cv2.CAP_PROP_FPS,
    CAMERA["fps"]
)

if not cap.isOpened():
    raise RuntimeError(
        f"Could not open camera {camera_source}"
    )


# =========================================================
# YOLO
# =========================================================

model_path = ROOT / MODEL_CFG["path"]

model = YOLO(str(model_path))


# =========================================================
# DOORWAY POLYGON
# =========================================================

polygon_points = np.array(
    PORTAL["polygon"],
    dtype=np.int32
)

if len(polygon_points) < 3:
    raise RuntimeError(
        "Portal polygon must contain at least 3 points."
    )


def point_inside_portal(point):
    result = cv2.pointPolygonTest(
        polygon_points,
        (float(point[0]), float(point[1])),
        False
    )

    return result >= 0


def portal_center():

    moments = cv2.moments(polygon_points)

    if moments["m00"] == 0:

        x = np.mean(
            polygon_points[:, 0]
        )

        y = np.mean(
            polygon_points[:, 1]
        )

    else:

        x = (
            moments["m10"]
            /
            moments["m00"]
        )

        y = (
            moments["m01"]
            /
            moments["m00"]
        )

    return int(x), int(y)


# =========================================================
# CSV
# =========================================================

if not CSV_PATH.exists():

    with CSV_PATH.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            [
                "event_id",
                "track_id",
                "timestamp",
                "direction",
                "confidence"
            ]
        )


def get_next_event_id():

    try:

        with CSV_PATH.open(
            "r",
            newline="",
            encoding="utf-8"
        ) as f:

            rows = list(
                csv.DictReader(f)
            )

        if not rows:
            return 1

        ids = []

        for row in rows:

            try:
                ids.append(
                    int(row["event_id"])
                )
            except:
                pass

        if ids:
            return max(ids) + 1

    except Exception:
        pass

    return 1


event_counter = get_next_event_id()


def log_event(
    track_id,
    direction,
    confidence
):

    global event_counter

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    row = [
        event_counter,
        track_id,
        timestamp,
        direction,
        round(float(confidence), 3)
    ]

    with CSV_PATH.open(
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)
        writer.writerow(row)

    print(
        f"[EVENT] P{track_id} -> {direction}"
    )

    event_counter += 1


# =========================================================
# TRACK HISTORY
# =========================================================

history = defaultdict(
    lambda: deque(
        maxlen=TRACK_CFG.get(
            "history_length",
            30
        )
    )
)


# =========================================================
# PERSON STATE
# =========================================================

state = {}


# =========================================================
# COUNTERS
# =========================================================

total_in = 0
total_out = 0


# =========================================================
# DRAW PORTAL
# =========================================================

def draw_portal(frame):

    overlay = frame.copy()

    cv2.fillPoly(
        overlay,
        [polygon_points],
        (255, 180, 0)
    )

    frame[:] = cv2.addWeighted(
        overlay,
        0.18,
        frame,
        0.82,
        0
    )

    cv2.polylines(
        frame,
        [polygon_points],
        True,
        (255, 180, 0),
        3
    )

    cx, cy = portal_center()

    cv2.circle(
        frame,
        (cx, cy),
        6,
        (255, 180, 0),
        -1
    )

    cv2.putText(
        frame,
        "DOOR",
        (cx - 25, cy - 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 180, 0),
        2
    )


# =========================================================
# DRAW PERSON
# =========================================================

def draw_person(
    frame,
    track_id,
    box,
    center,
    inside_portal,
    person_state
):

    x1, y1, x2, y2 = box

    if person_state["event"] == "IN":

        label = f"P{track_id} IN"

    elif person_state["event"] == "OUT":

        label = f"P{track_id} OUT"

    elif inside_portal:

        label = f"P{track_id} DOOR"

    else:

        label = f"P{track_id}"

    # Bounding box

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        2
    )

    # ID label

    cv2.putText(
        frame,
        label,
        (
            x1,
            max(y1 - 10, 20)
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 255, 0),
        2
    )

    # Center

    cv2.circle(
        frame,
        center,
        5,
        (0, 0, 255),
        -1
    )

    # Trajectory

    points = history[track_id]

    for i in range(
        1,
        len(points)
    ):

        cv2.line(
            frame,
            points[i - 1],
            points[i],
            (0, 255, 255),
            2
        )


# =========================================================
# START
# =========================================================

print()
print("==========================================")
print("       DOORWAY PEOPLE MONITOR")
print("==========================================")
print()
print("Camera:", camera_source)
print("Model:", MODEL_CFG["path"])
print("Portal points:", len(polygon_points))
print()
print("Detection logic:")
print("  IN  = person enters through doorway")
print("  OUT = person disappears through doorway")
print()
print("Press Q to quit.")
print()


previous_time = time.time()


# =========================================================
# MAIN LOOP
# =========================================================

while True:

    # -----------------------------------------------------
    # CAMERA
    # -----------------------------------------------------

    ret, frame = cap.read()

    if not ret:

        print(
            "WARNING: Camera frame could not be read."
        )

        break


    # -----------------------------------------------------
    # YOLO + BYTE TRACK
    # -----------------------------------------------------

    results = model.track(
        frame,
        persist=True,
        tracker=TRACK_CFG["tracker"],
        conf=MODEL_CFG["confidence"],
        iou=MODEL_CFG["iou"],
        classes=[0],
        verbose=False
    )


    visible_ids = set()


    # =====================================================
    # PROCESS DETECTIONS
    # =====================================================

    if (
        results
        and results[0].boxes is not None
        and results[0].boxes.id is not None
    ):

        boxes = results[0].boxes

        track_ids = (
            boxes.id
            .int()
            .cpu()
            .tolist()
        )

        coordinates = (
            boxes.xyxy
            .cpu()
            .numpy()
        )

        confidences = (
            boxes.conf
            .cpu()
            .numpy()
        )


        for (
            track_id,
            box,
            confidence
        ) in zip(
            track_ids,
            coordinates,
            confidences
        ):

            x1, y1, x2, y2 = map(
                int,
                box
            )


            # -------------------------------------------------
            # PERSON CENTER
            # -------------------------------------------------

            center = (
                int((x1 + x2) / 2),
                int((y1 + y2) / 2)
            )


            visible_ids.add(track_id)

            history[track_id].append(center)


            # -------------------------------------------------
            # DOORWAY STATUS
            # -------------------------------------------------

            inside_portal = point_inside_portal(
                center
            )


            # -------------------------------------------------
            # CREATE STATE
            # -------------------------------------------------

            if track_id not in state:

                state[track_id] = {

                    # Person has touched doorway
                    "door_seen": inside_portal,

                    # Number of visible frames
                    "visible_frames": 1,

                    # Number of doorway frames
                    "door_frames": (
                        1
                        if inside_portal
                        else 0
                    ),

                    # Frames outside doorway after
                    # touching it
                    "left_door_frames": 0,

                    # Missing frames
                    "missing_frames": 0,

                    # Confidence
                    "confidence": float(
                        confidence
                    ),

                    # Event
                    "event": None,

                    # Prevent duplicate events
                    "event_done": False
                }


            person = state[track_id]


            # -------------------------------------------------
            # UPDATE STATE
            # -------------------------------------------------

            person["missing_frames"] = 0

            person["visible_frames"] += 1

            person["confidence"] = float(
                confidence
            )


            if inside_portal:

                person["door_seen"] = True

                person["door_frames"] += 1

                person["left_door_frames"] = 0

            else:

                if person["door_seen"]:

                    person["left_door_frames"] += 1


            # =================================================
            # IN DETECTION
            #
            # Person touches doorway and then moves
            # into the camera-visible area.
            # =================================================

            if (
                not person["event_done"]
                and person["door_seen"]
                and person["left_door_frames"] >= 5
                and person["visible_frames"] >= 8
            ):

                log_event(
                    track_id,
                    "IN",
                    confidence
                )

                total_in += 1

                person["event"] = "IN"

                person["event_done"] = True


            # -------------------------------------------------
            # DRAW PERSON
            # -------------------------------------------------

            draw_person(
                frame,
                track_id,
                (
                    x1,
                    y1,
                    x2,
                    y2
                ),
                center,
                inside_portal,
                person
            )


    # =====================================================
    # DISAPPEARING PEOPLE
    # =====================================================

    max_missing = TRACK_CFG.get(
        "max_missing_frames",
        15
    )


    for track_id in list(
        state.keys()
    ):

        if track_id in visible_ids:
            continue


        person = state[track_id]

        person["missing_frames"] += 1

        missing = person[
            "missing_frames"
        ]


        # =================================================
        # OUT
        #
        # Person was associated with doorway and then
        # disappeared from the camera.
        # =================================================

        if (
            not person["event_done"]
            and person["door_seen"]
            and missing >= max_missing
        ):

            log_event(
                track_id,
                "OUT",
                person["confidence"]
            )

            total_out += 1

            person["event"] = "OUT"

            person["event_done"] = True


        # -------------------------------------------------
        # CLEAN OLD TRACKS
        # -------------------------------------------------

        if missing > max_missing * 4:

            del state[track_id]

            if track_id in history:

                del history[track_id]


    # =====================================================
    # DRAW DOOR
    # =====================================================

    draw_portal(frame)


    # =====================================================
    # FPS
    # =====================================================

    current_time = time.time()

    fps = 1.0 / max(
        current_time - previous_time,
        0.0001
    )

    previous_time = current_time


    # =====================================================
    # INFO PANEL
    # =====================================================

    cv2.rectangle(
        frame,
        (10, 10),
        (285, 95),
        (0, 0, 0),
        -1
    )


    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (20, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2
    )


    cv2.putText(
        frame,
        f"IN: {total_in}",
        (20, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 255, 255),
        2
    )


    cv2.putText(
        frame,
        f"OUT: {total_out}",
        (140, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 150, 255),
        2
    )


    # =====================================================
    # SHOW
    # =====================================================

    cv2.imshow(
        "Doorway People Monitor",
        frame
    )


    key = cv2.waitKey(1) & 0xFF


    if key == ord("q"):
        break


# =========================================================
# CLEANUP
# =========================================================

cap.release()

cv2.destroyAllWindows()

print()
print("==========================================")
print("PROGRAM STOPPED")
print("==========================================")
print()
print(f"Total IN:  {total_in}")
print(f"Total OUT: {total_out}")
print()