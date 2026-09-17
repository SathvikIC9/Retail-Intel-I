"""
Doorway People Monitor - Headless Laptop Service (video-file mode with Web UI)
====================================================================
Runs YOLO detection in a background thread, drawing bounding boxes and polygon
overlays to a global buffer. Serves a live MJPEG stream and dashboard at http://<laptop-ip>:5001/.

Run on your laptop:
    pip install ultralytics opencv-python flask pyyaml
    python laptop_doorway_service.py
"""

import csv
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import yaml
from flask import Flask, Response, jsonify, render_template_string
from ultralytics import YOLO

# =========================================================
# PATHS / CONFIG
# =========================================================

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.yaml"

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f) or {}

VIDEO_CFG = CONFIG["video"]
MODEL_CFG = CONFIG["model"]
TRACK_CFG = CONFIG["tracking"]
PORTAL = CONFIG["portal"]

CSV_PATH = ROOT / CONFIG["database"]["csv_path"]
CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

SERVICE_PORT = 5001

# =========================================================
# SHARED STATE & VIDEO BUFFER
# =========================================================

latest_status = {
    "running": False,
    "total_in": 0,
    "total_out": 0,
    "people_inside": 0,
    "last_event": None,
    "last_updated": None,
    "fps": 0.0,
}
status_lock = threading.Lock()

latest_frame = None
frame_lock = threading.Lock()


def update_status(**kwargs):
    with status_lock:
        latest_status.update(kwargs)
        latest_status["last_updated"] = datetime.now().isoformat(timespec="seconds")


# =========================================================
# DOORWAY POLYGON
# =========================================================

polygon_points = np.array(PORTAL["polygon"], dtype=np.int32)

if len(polygon_points) < 3:
    raise RuntimeError("Portal polygon must contain at least 3 points.")


def point_inside_portal(point):
    result = cv2.pointPolygonTest(polygon_points, (float(point[0]), float(point[1])), False)
    return result >= 0


# =========================================================
# CSV LOGGING
# =========================================================

EXPECTED_CSV_HEADER = ["event_id", "track_id", "timestamp", "direction", "confidence"]


def ensure_csv_has_correct_header():
    """Creates the CSV with a proper header if it doesn't exist yet.
    If the file DOES exist but its first line isn't the expected header
    (e.g. an older version of this script wrote data directly without a
    header), this prepends the correct header so csv.DictReader stops
    misinterpreting the first data row as column names."""

    if not CSV_PATH.exists():
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(EXPECTED_CSV_HEADER)
        return

    with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
        first_line = f.readline().strip()

    if first_line != ",".join(EXPECTED_CSV_HEADER):
        print(f"WARNING: {CSV_PATH} is missing its header row. Fixing it now.")
        with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
            existing_content = f.read()
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            f.write(",".join(EXPECTED_CSV_HEADER) + "\n")
            f.write(existing_content)


ensure_csv_has_correct_header()


def get_next_event_id():
    try:
        with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        ids = [int(row["event_id"]) for row in rows if row.get("event_id", "").isdigit()]
        return max(ids) + 1 if ids else 1
    except Exception:
        return 1


event_counter = get_next_event_id()
event_counter_lock = threading.Lock()


def log_event(track_id, direction, confidence):
    global event_counter
    with event_counter_lock:
        current_id = event_counter
        event_counter += 1

    timestamp = datetime.now().isoformat(timespec="seconds")
    row = [current_id, track_id, timestamp, direction, round(float(confidence), 3)]

    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)

    print(f"[EVENT] P{track_id} -> {direction}")
    return {"track_id": track_id, "direction": direction, "timestamp": timestamp}


# =========================================================
# DETECTION WORKER
# =========================================================

def detection_worker():
    global latest_frame
    history = defaultdict(lambda: deque(maxlen=TRACK_CFG.get("history_length", 30)))
    state = {}
    total_in = 0
    total_out = 0

    print("Loading YOLO model:", MODEL_CFG["path"])
    model = YOLO(MODEL_CFG["path"])

    video_path = ROOT / VIDEO_CFG["path"]
    loop_video = VIDEO_CFG.get("loop", True)

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        print(f"ERROR: Could not open video file {video_path}")
        update_status(running=False)
        return

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_delay = 1.0 / source_fps

    update_status(running=True)
    previous_time = time.time()

    print(f"Doorway detection worker started. Reading video: {video_path}")

    while True:
        ret, frame = cap.read()
        if not ret:
            if loop_video:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            print("End of video reached and loop=false. Stopping worker.")
            update_status(running=False)
            break

        if VIDEO_CFG.get("width") and VIDEO_CFG.get("height"):
            frame = cv2.resize(frame, (VIDEO_CFG["width"], VIDEO_CFG["height"]))

        time.sleep(frame_delay)

        results = model.track(
            frame,
            persist=True,
            tracker=TRACK_CFG["tracker"],
            conf=MODEL_CFG["confidence"],
            iou=MODEL_CFG["iou"],
            classes=[0],
            verbose=False,
        )

        # Create overlay canvas
        annotated_frame = frame.copy()
        cv2.polylines(annotated_frame, [polygon_points], isClosed=True, color=(255, 191, 0), thickness=2)

        visible_ids = set()
        last_event = None

        if results and results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes
            track_ids = boxes.id.int().cpu().tolist()
            coordinates = boxes.xyxy.cpu().numpy()
            confidences = boxes.conf.cpu().numpy()

            for track_id, box, confidence in zip(track_ids, coordinates, confidences):
                x1, y1, x2, y2 = map(int, box)
                center = (int((x1 + x2) / 2), int((y1 + y2) / 2))
                visible_ids.add(track_id)
                history[track_id].append(center)

                inside_portal = point_inside_portal(center)

                if track_id not in state:
                    state[track_id] = {
                        "door_seen": inside_portal,
                        "visible_frames": 1,
                        "door_frames": 1 if inside_portal else 0,
                        "left_door_frames": 0,
                        "missing_frames": 0,
                        "confidence": float(confidence),
                        "event": None,
                        "event_done": False,
                    }

                person = state[track_id]
                person["missing_frames"] = 0
                person["visible_frames"] += 1
                person["confidence"] = float(confidence)

                if inside_portal:
                    person["door_seen"] = True
                    person["door_frames"] += 1
                    person["left_door_frames"] = 0
                elif person["door_seen"]:
                    person["left_door_frames"] += 1

                # IN detection logic
                if (
                    not person["event_done"]
                    and person["door_seen"]
                    and person["left_door_frames"] >= 5
                    and person["visible_frames"] >= 8
                ):
                    last_event = log_event(track_id, "IN", confidence)
                    total_in += 1
                    person["event"] = "IN"
                    person["event_done"] = True

                # Draw Visualizations on Frame
                color = (0, 255, 0) if person["event_done"] else (0, 165, 255)
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                cv2.circle(annotated_frame, center, 4, (0, 0, 255), -1)
                cv2.putText(
                    annotated_frame,
                    f"ID: {track_id}",
                    (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                )

        # Disappearing people -> OUT detection
        max_missing = TRACK_CFG.get("max_missing_frames", 15)
        for track_id in list(state.keys()):
            if track_id in visible_ids:
                continue

            person = state[track_id]
            person["missing_frames"] += 1
            missing = person["missing_frames"]

            if not person["event_done"] and person["door_seen"] and missing >= max_missing:
                last_event = log_event(track_id, "OUT", person["confidence"])
                total_out += 1
                person["event"] = "OUT"
                person["event_done"] = True

            if missing > max_missing * 4:
                del state[track_id]
                history.pop(track_id, None)

        current_time = time.time()
        fps = 1.0 / max(current_time - previous_time, 0.0001)
        previous_time = current_time

        # Update latest frame buffer for streaming
        with frame_lock:
            latest_frame = annotated_frame.copy()

        update_status(
            running=True,
            total_in=total_in,
            total_out=total_out,
            people_inside=max(0, total_in - total_out),
            last_event=last_event or latest_status.get("last_event"),
            fps=round(fps, 1),
        )

    cap.release()


# =========================================================
# FLASK WEB SERVER & API
# =========================================================

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Doorway Monitor Feed</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-color: #f8fafc;
            --accent-color: #38bdf8;
            --green: #22c55e;
            --red: #ef4444;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 24px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            margin-bottom: 24px;
        }
        h1 {
            margin: 0 0 8px 0;
            font-size: 1.8rem;
        }
        .grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
        }
        @media (max-width: 900px) {
            .grid { grid-template-columns: 1fr; }
        }
        .card {
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .video-container {
            width: 100%;
            overflow: hidden;
            border-radius: 8px;
            background-color: #000;
        }
        .video-container img {
            width: 100%;
            height: auto;
            display: block;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }
        .stat-card {
            background-color: #334155;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-card .label {
            font-size: 0.8rem;
            color: #94a3b8;
            text-transform: uppercase;
        }
        .stat-card .value {
            font-size: 1.5rem;
            font-weight: bold;
            margin-top: 4px;
        }
        .val-in { color: var(--green); }
        .val-out { color: var(--red); }
        .val-inside { color: var(--accent-color); }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            font-size: 0.9rem;
        }
        th, td {
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid #334155;
        }
        th { color: #94a3b8; }
        .badge {
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.75rem;
        }
        .badge-in { background-color: rgba(34, 197, 94, 0.2); color: var(--green); }
        .badge-out { background-color: rgba(239, 68, 68, 0.2); color: var(--red); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Doorway Monitor Dashboard</h1>
            <div id="status-indicator">Connecting...</div>
        </header>

        <div class="grid">
            <div class="card">
                <div class="video-container">
                    <img src="/video_feed" alt="Live Doorway Stream">
                </div>
            </div>

            <div class="card">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="label">Inside</div>
                        <div class="value val-inside" id="people-inside">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Total In</div>
                        <div class="value val-in" id="total-in">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Total Out</div>
                        <div class="value val-out" id="total-out">0</div>
                    </div>
                </div>

                <h3>Recent Activity</h3>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Direction</th>
                            <th>Time</th>
                        </tr>
                    </thead>
                    <tbody id="events-table">
                        <tr><td colspan="3">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const res = await fetch('/status');
                const data = await res.json();
                
                document.getElementById('people-inside').innerText = data.people_inside;
                document.getElementById('total-in').innerText = data.total_in;
                document.getElementById('total-out').innerText = data.total_out;
                document.getElementById('status-indicator').innerText = 
                    `Status: ${data.running ? 'Running' : 'Stopped'} | FPS: ${data.fps}`;
            } catch (e) {
                console.error("Error fetching status:", e);
            }
        }

        async function fetchEvents() {
            try {
                const res = await fetch('/events/recent');
                const data = await res.json();
                const tbody = document.getElementById('events-table');
                
                if (data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="3">No events logged yet.</td></tr>';
                    return;
                }

                tbody.innerHTML = data.slice(0, 10).map(e => `
                    <tr>
                        <td>#${e.track_id}</td>
                        <td><span class="badge ${e.direction === 'IN' ? 'badge-in' : 'badge-out'}">${e.direction}</span></td>
                        <td>${e.timestamp.split('T')[1] || e.timestamp}</td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error("Error fetching events:", e);
            }
        }

        setInterval(fetchStatus, 1000);
        setInterval(fetchEvents, 2000);
        fetchStatus();
        fetchEvents();
    </script>
</body>
</html>
"""


def generate_frames():
    """MJPEG frame generator function."""
    while True:
        with frame_lock:
            if latest_frame is None:
                time.sleep(0.04)
                continue

            ret, buffer = cv2.imencode(".jpg", latest_frame)
            if not ret:
                continue

            frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )
        time.sleep(0.04)  # Limit stream transmission to ~25 FPS


@app.route("/")
def index():
    """Serves the Web UI dashboard."""
    return render_template_string(HTML_TEMPLATE)


@app.route("/video_feed")
def video_feed():
    """Serves the MJPEG stream endpoint."""
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/status")
def status():
    with status_lock:
        return jsonify(dict(latest_status))


@app.route("/events/recent")
def recent_events():
    events = []
    if CSV_PATH.exists():
        with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
            events = list(csv.DictReader(f))
    events = events[-20:]
    events.reverse()
    return jsonify(events)


@app.route("/analytics/summary")
def analytics_summary():
    """Pre-aggregated analytics for the board's Store Analytics tab
    (headline cards + hourly traffic chart). This was missing from this
    file, which is why the hourly chart was rendering blank."""
    events = []
    if CSV_PATH.exists():
        with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
            events = list(csv.DictReader(f))

    hourly_in = defaultdict(int)
    hourly_out = defaultdict(int)
    total_in = 0
    total_out = 0
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_in = 0
    today_out = 0

    for row in events:
        direction = row.get("direction")
        timestamp = row.get("timestamp", "")
        if not timestamp:
            continue

        try:
            dt = datetime.fromisoformat(timestamp)
        except ValueError:
            continue

        hour_label = dt.strftime("%H:00")
        is_today = timestamp.startswith(today_str)

        if direction == "IN":
            total_in += 1
            hourly_in[hour_label] += 1
            if is_today:
                today_in += 1
        elif direction == "OUT":
            total_out += 1
            hourly_out[hour_label] += 1
            if is_today:
                today_out += 1

    all_hours = sorted(set(hourly_in.keys()) | set(hourly_out.keys()))
    hourly_breakdown = [
        {"hour": hour, "in": hourly_in.get(hour, 0), "out": hourly_out.get(hour, 0)}
        for hour in all_hours
    ]

    peak_hour = None
    if hourly_in:
        peak_hour = max(hourly_in, key=hourly_in.get)

    people_inside_now = max(0, total_in - total_out)

    return jsonify({
        "total_visits_all_time": total_in,
        "total_exits_all_time": total_out,
        "people_inside_now": people_inside_now,
        "today_visits": today_in,
        "today_exits": today_out,
        "peak_hour": peak_hour,
        "hourly_breakdown": hourly_breakdown,
    })


if __name__ == "__main__":
    worker_thread = threading.Thread(target=detection_worker, daemon=True)
    worker_thread.start()

    print()
    print("==========================================")
    print("  DOORWAY MONITOR - LAPTOP SERVICE")
    print("==========================================")
    print(f" Dashboard UI: http://0.0.0.0:{SERVICE_PORT}/")
    print(f" Video Stream: http://0.0.0.0:{SERVICE_PORT}/video_feed")
    print(f" Status API:   http://0.0.0.0:{SERVICE_PORT}/status")
    print("==========================================")
    print()

    app.run(host="0.0.0.0", port=SERVICE_PORT, debug=False, use_reloader=False)