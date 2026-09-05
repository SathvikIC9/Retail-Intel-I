import os
import cv2
import numpy as np

from flask import Flask, render_template, send_file, jsonify, request
from ultralytics import YOLO

from zone_assigner import load_zones, assign_person
from state_inferrer import infer_counter_states
from person_tracker import PersonTracker
from queue_tracker import QueueTracker


app = Flask(__name__)


# ============================================================
# CONFIG
# ============================================================

MODEL_PATH = "yolov8n.pt"
ZONES_PATH = "zones.json"

FRAME_PATHS = [
    "frame1.jpg",
    "frame2.jpg",
    "frame3.jpg",
]

CONFIDENCE = 0.25

OUTPUT_DIR = "dashboard_output"

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


# ============================================================
# LOAD SYSTEM
# ============================================================

model = YOLO(MODEL_PATH)

zones = load_zones(
    ZONES_PATH
)

person_tracker = PersonTracker(
    history_size=5
)

queue_tracker = QueueTracker()

current_frame_index = 0

latest_data = {
    "frame_number": 0,
    "counters": {},
    "people": [],
    "total_waiting": 0
}


# ============================================================
# COLORS
# ============================================================

def zone_color(zone_type):

    if zone_type == "CASHIER":
        return (0, 0, 255)

    if zone_type == "SERVICE":
        return (0, 255, 255)

    if zone_type == "QUEUE":
        return (0, 255, 0)

    return (255, 255, 255)


# ============================================================
# PROCESS ONE FRAME
# ============================================================

def process_frame(frame_path, frame_number):

    global latest_data

    image = cv2.imread(
        frame_path
    )

    if image is None:
        raise RuntimeError(
            f"Could not load {frame_path}"
        )


    # --------------------------------------------------------
    # YOLO + BYTE TRACK
    # --------------------------------------------------------

    results = model.track(
        image,
        conf=CONFIDENCE,
        classes=[0],
        tracker="bytetrack.yaml",
        persist=True,
        verbose=False
    )

    result = results[0]


    assignments = []


    if (
        result.boxes is not None
        and len(result.boxes) > 0
    ):

        boxes = (
            result.boxes.xyxy
            .cpu()
            .numpy()
        )

        confidences = (
            result.boxes.conf
            .cpu()
            .numpy()
        )

        if result.boxes.id is not None:

            track_ids = (
                result.boxes.id
                .cpu()
                .numpy()
                .astype(int)
            )

        else:

            track_ids = [
                -1
            ] * len(boxes)


        for bbox, confidence, track_id in zip(
            boxes,
            confidences,
            track_ids
        ):

            x1, y1, x2, y2 = bbox

            bbox = [
                int(x1),
                int(y1),
                int(x2),
                int(y2)
            ]

            assignment = assign_person(
                bbox,
                zones
            )

            assignment["track_id"] = int(
                track_id
            )

            assignment["bbox"] = bbox

            assignment["confidence"] = float(
                confidence
            )

            assignments.append(
                assignment
            )


    # --------------------------------------------------------
    # TEMPORAL SMOOTHING
    # --------------------------------------------------------

    smoothed_assignments = (
        person_tracker.update(
            assignments
        )
    )


    # --------------------------------------------------------
    # QUEUE TRACKER
    # --------------------------------------------------------

    queue_tracker.update(
        smoothed_assignments,
        frame_number
    )


    # --------------------------------------------------------
    # COUNTER STATES
    # --------------------------------------------------------

    counters = infer_counter_states(
        zones,
        smoothed_assignments
    )


    # --------------------------------------------------------
    # VISUALIZE
    # --------------------------------------------------------

    display = image.copy()


    # Draw zones
    for zone in zones:

        polygon = np.array(
            zone.points,
            dtype=np.int32
        )

        cv2.polylines(
            display,
            [polygon],
            True,
            zone_color(
                zone.zone_type
            ),
            2
        )


    # Draw people
    for person in smoothed_assignments:

        x1, y1, x2, y2 = person[
            "bbox"
        ]

        track_id = person[
            "track_id"
        ]

        counter_id = person[
            "counter_id"
        ]

        zone_type = person[
            "zone_type"
        ]

        contact_x, contact_y = person[
            "contact_point"
        ]

        color = zone_color(
            zone_type
        )

        cv2.rectangle(
            display,
            (x1, y1),
            (x2, y2),
            color,
            2
        )

        cv2.circle(
            display,
            (
                int(contact_x),
                int(contact_y)
            ),
            5,
            color,
            -1
        )

        if counter_id is None:

            label = (
                f"ID {track_id} "
                f"UNASSIGNED"
            )

        else:

            label = (
                f"ID {track_id} "
                f"C{counter_id} "
                f"{zone_type}"
            )

        cv2.putText(
            display,
            label,
            (
                x1,
                max(
                    20,
                    y1 - 8
                )
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            2,
            cv2.LINE_AA
        )


    # --------------------------------------------------------
    # SAVE RESULT IMAGE
    # --------------------------------------------------------

    output_path = os.path.join(
        OUTPUT_DIR,
        "current_frame.jpg"
    )

    cv2.imwrite(
        output_path,
        display
    )


    # --------------------------------------------------------
    # PREPARE JSON DATA
    # --------------------------------------------------------

    people_data = []

    for person in smoothed_assignments:

        people_data.append({
            "track_id": person["track_id"],
            "counter_id": person["counter_id"],
            "zone_type": person["zone_type"],
            "role": person["role"],
            "confidence": round(
                person["confidence"],
                2
            ),

            # Position of the person's feet/contact point
            "contact_point": [
                float(person["contact_point"][0]),
                float(person["contact_point"][1])
            ],

            # Bounding box is useful later for richer visualization
            "bbox": [
                int(person["bbox"][0]),
                int(person["bbox"][1]),
                int(person["bbox"][2]),
                int(person["bbox"][3])
            ]
        })


    total_waiting = sum(
        counter["queue_count"]
        for counter in counters.values()
    )


    latest_data = {
        "frame_number": frame_number,

        "image_width": int(image.shape[1]),
        "image_height": int(image.shape[0]),

        "counters": counters,
        "people": people_data,
        "total_waiting": total_waiting
    }


    return output_path


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def dashboard():

    return render_template(
        "dashboard.html"
    )


@app.route("/frame")
def frame():

    return send_file(
        os.path.join(
            OUTPUT_DIR,
            "current_frame.jpg"
        ),
        mimetype="image/jpeg"
    )


@app.route("/api/status")
def api_status():

    return jsonify(
        latest_data
    )


@app.route("/api/next", methods=["POST"])
def next_frame():

    global current_frame_index

    current_frame_index += 1

    if current_frame_index >= len(
        FRAME_PATHS
    ):

        current_frame_index = 0


    frame_number = (
        current_frame_index + 1
    )

    process_frame(
        FRAME_PATHS[
            current_frame_index
        ],
        frame_number
    )

    return jsonify({
        "success": True,
        "frame_number": frame_number
    })


@app.route("/api/previous", methods=["POST"])
def previous_frame():

    global current_frame_index

    current_frame_index -= 1

    if current_frame_index < 0:

        current_frame_index = (
            len(FRAME_PATHS) - 1
        )


    frame_number = (
        current_frame_index + 1
    )

    process_frame(
        FRAME_PATHS[
            current_frame_index
        ],
        frame_number
    )

    return jsonify({
        "success": True,
        "frame_number": frame_number
    })


@app.route("/api/alert", methods=["POST"])
def alert_manager():

    data = request.json or {}

    counter_id = data.get(
        "counter_id"
    )

    print()
    print("=" * 60)
    print("MANAGER ALERT")
    print("=" * 60)

    print(
        f"Request to open/check "
        f"counter: {counter_id}"
    )

    print("=" * 60)

    return jsonify({
        "success": True,
        "message": (
            f"Manager alerted for "
            f"Counter {counter_id}"
        )
    })


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    # Process first frame before opening dashboard
    process_frame(
        FRAME_PATHS[0],
        1
    )

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )