import os
import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from flask import Flask, render_template_string, send_file, jsonify, request
from ultralytics import YOLO

from zone_assigner import load_zones, assign_person
from state_inferrer import infer_counter_states
from person_tracker import PersonTracker
from queue_tracker import QueueTracker


app = Flask(__name__)

ROOT_DIR = Path(__file__).resolve().parent


# ============================================================
# CONFIG
# ============================================================

MODEL_PATH = "yolov8n.pt"
ZONES_PATH = "zones.json"

VIDEO_PATH = "queue.mp4"
VIDEO_LOOP = True

FRAME_PATHS = [
    "frame1.jpg",
    "frame2.jpg",
    "frame3.jpg",
]

CONFIDENCE = 0.25
OUTPUT_DIR = "dashboard_output"
SERVICE_PORT = 5002  # separate from doorway service (5001) and board (5000)
ALERT_LINES_PATH = "alert_lines.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)

alert_lines = {}
if os.path.exists(ALERT_LINES_PATH):
    with open(ALERT_LINES_PATH, "r", encoding="utf-8") as f:
        alert_lines = json.load(f)


# ============================================================
# LOAD SYSTEM
# ============================================================

model = YOLO(MODEL_PATH)
zones = load_zones(ZONES_PATH)
person_tracker = PersonTracker(history_size=5)
queue_tracker = QueueTracker()

current_frame_index = 0
data_lock = threading.Lock()

latest_data = {
    "frame_number": 0,
    "counters": {},
    "people": [],
    "total_waiting": 0
}

alerts_lock = threading.Lock()
active_alerts = {}   # counter_id -> alert dict


# ============================================================
# INLINED HTML TEMPLATE
# ============================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Queue Management Dashboard</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-red: #ef4444;
            --accent-green: #22c55e;
            --border-color: #334155;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-primary);
            padding: 24px;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }

        .grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
        }

        @media (max-width: 1024px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .video-container {
            position: relative;
            width: 100%;
            border-radius: 8px;
            overflow: hidden;
            background: #000;
        }

        .video-feed {
            width: 100%;
            height: auto;
            display: block;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.03);
            padding: 16px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }

        .stat-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--accent-blue);
            margin-top: 4px;
        }

        .counter-badge {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 8px;
            margin-bottom: 8px;
            border-left: 4px solid var(--border-color);
        }

        .status-badge {
            font-size: 0.75rem;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            text-transform: uppercase;
        }

        .status-active { background: #166534; color: #4ade80; }
        .status-idle { background: #854d0e; color: #fde047; }

        .alert-item {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid var(--accent-red);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            color: #fca5a5;
        }

        .btn-alert {
            background: var(--accent-red);
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            margin-top: 8px;
            width: 100%;
        }

        .btn-alert:hover {
            opacity: 0.9;
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>Queue Operations Dashboard</h1>
        <div id="frame-info" style="color: var(--text-secondary);">Processing Frame: #0</div>
    </div>

    <div class="grid">
        <!-- Main Column: Video Stream -->
        <div>
            <div class="card">
                <div class="card-title">Live Camera Analytics Feed</div>
                <div class="video-container">
                    <img id="stream" src="/frame" class="video-feed" alt="Live Feed">
                </div>
            </div>
        </div>

        <!-- Sidebar Column: Key Metrics & Alerts -->
        <div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div>Waiting</div>
                    <div id="stat-waiting" class="stat-value">0</div>
                </div>
                <div class="stat-card">
                    <div>Avg Wait (f)</div>
                    <div id="stat-avg-wait" class="stat-value">0</div>
                </div>
                <div class="stat-card">
                    <div>Max Wait (f)</div>
                    <div id="stat-max-wait" class="stat-value">0</div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Active Alerts</div>
                <div id="alerts-container">
                    <div style="color: var(--text-secondary); font-size: 0.9rem;">No active alerts</div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">Counter Status</div>
                <div id="counters-container">
                    <!-- Dynamic Counters -->
                </div>
            </div>
        </div>
    </div>

    <script>
        // Update live visual image feed
        function refreshFrame() {
            const img = document.getElementById('stream');
            img.src = '/frame?t=' + new Date().getTime();
        }

        // Fetch live queue analytics and counters status
        async function fetchAnalytics() {
            try {
                const response = await fetch('/api/analytics/summary');
                const data = await response.json();
                
                document.getElementById('frame-info').innerText = `Processing Frame: #${data.frame_number}`;
                document.getElementById('stat-waiting').innerText = data.total_waiting;
                document.getElementById('stat-avg-wait').innerText = data.average_wait_frames;
                document.getElementById('stat-max-wait').innerText = data.longest_wait_frames;

                const countersDiv = document.getElementById('counters-container');
                countersDiv.innerHTML = '';
                data.counters.forEach(c => {
                    const statusClass = c.state === 'BUSY' || c.state === 'ACTIVE' ? 'status-active' : 'status-idle';
                    countersDiv.innerHTML += `
                        <div class="counter-badge" style="border-left-color: ${c.queue_count > 3 ? '#ef4444' : '#38bdf8'}">
                            <div>
                                <strong>Counter ${c.counter_id}</strong>
                                <div style="font-size: 0.8rem; color: var(--text-secondary);">Queue: ${c.queue_count} people</div>
                            </div>
                            <div>
                                <span class="status-badge ${statusClass}">${c.state || 'IDLE'}</span>
                                <button class="btn-alert" onclick="triggerManagerAlert(${c.counter_id})">Alert Manager</button>
                            </div>
                        </div>
                    `;
                });
            } catch (e) {
                console.error("Error loading analytics:", e);
            }
        }

        // Fetch live line-crossing alerts
        async function fetchAlerts() {
            try {
                const response = await fetch('/api/alerts');
                const data = await response.json();
                const alertsDiv = document.getElementById('alerts-container');
                
                if (data.alerts.length === 0) {
                    alertsDiv.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.9rem;">No active overflow alerts</div>';
                } else {
                    alertsDiv.innerHTML = '';
                    data.alerts.forEach(a => {
                        alertsDiv.innerHTML += `
                            <div class="alert-item">
                                <strong>⚠️ Overflow Warning</strong>
                                <div style="font-size: 0.85rem; margin-top: 4px;">${a.message}</div>
                            </div>
                        `;
                    });
                }
            } catch (e) {
                console.error("Error fetching alerts:", e);
            }
        }

        async function triggerManagerAlert(counterId) {
            await fetch('/api/alert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ counter_id: counterId })
            });
            alert(`Manager dispatched to Counter ${counterId}`);
        }

        // Polling interval
        setInterval(refreshFrame, 200);
        setInterval(fetchAnalytics, 500);
        setInterval(fetchAlerts, 500);
    </script>
</body>
</html>
"""


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
# ALERT LINE LOGIC
# ============================================================

def which_side_of_line(point, line_p1, line_p2):
    x, y = point
    x1, y1 = line_p1
    x2, y2 = line_p2
    return (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)


def check_alert_line_crossings(smoothed_assignments):
    counters_with_people_past_line = set()

    for assignment in smoothed_assignments:
        zone_type = assignment.get("zone_type")
        counter_id = assignment.get("counter_id")

        if zone_type != "QUEUE" or counter_id is None:
            continue

        counter_key = f"counter_{counter_id}"
        line_config = alert_lines.get(counter_key)
        if not line_config:
            continue

        bbox = assignment["bbox"]
        center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

        line_p1, line_p2 = line_config["line"]
        counter_side_point = line_config["counter_side_point"]

        counter_side_sign = which_side_of_line(counter_side_point, line_p1, line_p2)
        person_side_sign = which_side_of_line(center, line_p1, line_p2)

        is_past_line = (counter_side_sign > 0) != (person_side_sign > 0)

        if is_past_line:
            counters_with_people_past_line.add(counter_key)

    with alerts_lock:
        for counter_key in alert_lines:
            if counter_key in counters_with_people_past_line:
                if counter_key not in active_alerts:
                    active_alerts[counter_key] = {
                        "counter_id": counter_key,
                        "type": "queue_overflow",
                        "message": f"{counter_key.replace('_', ' ').title()} queue has passed the overflow line",
                        "triggered_at": time.time(),
                    }
            else:
                active_alerts.pop(counter_key, None)


# ============================================================
# PROCESS ONE FRAME
# ============================================================

def process_frame(frame_source, frame_number):
    global latest_data

    if isinstance(frame_source, (str, Path)):
        image = cv2.imread(str(frame_source))
        if image is None:
            raise RuntimeError(f"Could not load {frame_source}")
    else:
        image = frame_source

    # YOLO + BYTE TRACK
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

    if result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()

        if result.boxes.id is not None:
            track_ids = result.boxes.id.cpu().numpy().astype(int)
        else:
            track_ids = [-1] * len(boxes)

        for bbox, confidence, track_id in zip(boxes, confidences, track_ids):
            x1, y1, x2, y2 = bbox
            bbox = [int(x1), int(y1), int(x2), int(y2)]

            assignment = assign_person(bbox, zones)
            assignment["track_id"] = int(track_id)
            assignment["bbox"] = bbox
            assignment["confidence"] = float(confidence)

            assignments.append(assignment)

    # TEMPORAL SMOOTHING
    smoothed_assignments = person_tracker.update(assignments)
    check_alert_line_crossings(smoothed_assignments)

    # QUEUE TRACKER
    queue_tracker.update(smoothed_assignments, frame_number)

    # COUNTER STATES
    counters = infer_counter_states(zones, smoothed_assignments)

    # VISUALIZE
    display = image.copy()

    # Draw zones
    for zone in zones:
        polygon = np.array(zone.points, dtype=np.int32)
        cv2.polylines(display, [polygon], True, zone_color(zone.zone_type), 2)

    # Draw people
    for person in smoothed_assignments:
        x1, y1, x2, y2 = person["bbox"]
        track_id = person["track_id"]
        counter_id = person["counter_id"]
        zone_type = person["zone_type"]
        contact_x, contact_y = person["contact_point"]
        color = zone_color(zone_type)

        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
        cv2.circle(display, (int(contact_x), int(contact_y)), 5, color, -1)

        label = f"ID {track_id} UNASSIGNED" if counter_id is None else f"ID {track_id} C{counter_id} {zone_type}"

        cv2.putText(
            display,
            label,
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            2,
            cv2.LINE_AA
        )

    # SAVE RESULT IMAGE
    output_path = os.path.join(OUTPUT_DIR, "current_frame.jpg")
    cv2.imwrite(output_path, display)

    # PREPARE JSON DATA
    people_data = []
    for person in smoothed_assignments:
        people_data.append({
            "track_id": person["track_id"],
            "counter_id": person["counter_id"],
            "zone_type": person["zone_type"],
            "role": person["role"],
            "confidence": round(person["confidence"], 2),
            "contact_point": [float(person["contact_point"][0]), float(person["contact_point"][1])],
            "bbox": [int(person["bbox"][0]), int(person["bbox"][1]), int(person["bbox"][2]), int(person["bbox"][3])]
        })

    total_waiting = sum(counter["queue_count"] for counter in counters.values())

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
    return render_template_string(HTML_TEMPLATE)


@app.route("/frame")
def frame():
    return send_file(
        os.path.join(OUTPUT_DIR, "current_frame.jpg"),
        mimetype="image/jpeg"
    )


@app.route("/api/status")
def api_status():
    return jsonify(latest_data)


@app.route("/api/next", methods=["POST"])
def next_frame():
    global current_frame_index

    with data_lock:
        current_frame_index += 1
        if current_frame_index >= len(FRAME_PATHS):
            current_frame_index = 0

        frame_number = current_frame_index + 1
        process_frame(FRAME_PATHS[current_frame_index], frame_number)

    return jsonify({"success": True, "frame_number": frame_number})


@app.route("/api/previous", methods=["POST"])
def previous_frame():
    global current_frame_index

    with data_lock:
        current_frame_index -= 1
        if current_frame_index < 0:
            current_frame_index = len(FRAME_PATHS) - 1

        frame_number = current_frame_index + 1
        process_frame(FRAME_PATHS[current_frame_index], frame_number)

    return jsonify({"success": True, "frame_number": frame_number})


@app.route("/api/alert", methods=["POST"])
def alert_manager():
    data = request.json or {}
    counter_id = data.get("counter_id")

    print("\n" + "=" * 60)
    print("MANAGER ALERT")
    print("=" * 60)
    print(f"Request to open/check counter: {counter_id}")
    print("=" * 60 + "\n")

    return jsonify({"success": True, "message": f"Manager alerted for Counter {counter_id}"})


@app.route("/api/alerts")
def get_alerts():
    with alerts_lock:
        alerts_list = list(active_alerts.values())
    alerts_list.sort(key=lambda a: a["triggered_at"], reverse=True)
    return jsonify({"alerts": alerts_list, "count": len(alerts_list)})


@app.route("/api/analytics/summary")
def analytics_summary():
    with data_lock:
        counters = latest_data.get("counters", {})
        total_waiting = latest_data.get("total_waiting", 0)
        frame_number = latest_data.get("frame_number", 0)

    average_wait_frames = queue_tracker.get_average_wait()
    longest_wait_frames = queue_tracker.get_longest_wait()
    active_people = queue_tracker.get_active_people()

    counter_summary = []
    for counter_id, info in counters.items():
        counter_summary.append({
            "counter_id": counter_id,
            "state": info.get("state"),
            "queue_count": info.get("queue_count", 0),
        })

    return jsonify({
        "frame_number": frame_number,
        "total_waiting": total_waiting,
        "active_people_count": len(active_people),
        "average_wait_frames": round(average_wait_frames, 1),
        "longest_wait_frames": longest_wait_frames,
        "counters": counter_summary,
    })


# ============================================================
# VIDEO / FRAME SOURCE
# ============================================================

def video_capture_loop():
    global current_frame_index

    video_file = ROOT_DIR / VIDEO_PATH

    if not video_file.exists():
        print(f"WARNING: {video_file} not found. Falling back to sample-image auto-advance mode.")
        image_auto_advance_loop()
        return

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        print(f"ERROR: Could not open video file {video_file}. Falling back to sample images.")
        image_auto_advance_loop()
        return

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_delay = 1.0 / source_fps
    frame_number = 0

    print(f"Reading video: {video_file}")

    while True:
        ret, frame = cap.read()

        if not ret:
            if VIDEO_LOOP:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            print("End of video reached and VIDEO_LOOP=False. Stopping video loop.")
            break

        frame_number += 1
        time.sleep(frame_delay)

        with data_lock:
            process_frame(frame, frame_number)


def image_auto_advance_loop():
    global current_frame_index
    interval_seconds = 4

    while True:
        time.sleep(interval_seconds)
        with data_lock:
            current_frame_index = (current_frame_index + 1) % len(FRAME_PATHS)
            frame_number = current_frame_index + 1
            process_frame(FRAME_PATHS[current_frame_index], frame_number)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    video_file_exists = (ROOT_DIR / VIDEO_PATH).exists()

    with data_lock:
        if not video_file_exists:
            process_frame(FRAME_PATHS[0], 1)

    capture_thread = threading.Thread(target=video_capture_loop, daemon=True)
    capture_thread.start()

    print("\n==========================================")
    print("  QUEUE MANAGEMENT - LAPTOP SERVICE")
    print("==========================================")
    print(f" Dashboard UI: http://0.0.0.0:{SERVICE_PORT}/")
    print(f" Analytics:    http://0.0.0.0:{SERVICE_PORT}/api/analytics/summary")
    if video_file_exists:
        print(f" Reading video: {VIDEO_PATH}")
    else:
        print(f" No video found at '{VIDEO_PATH}' - using sample images (frame1/2/3.jpg)")
    print("==========================================\n")

    app.run(
        host="0.0.0.0",
        port=SERVICE_PORT,
        debug=False,
        use_reloader=False
    )