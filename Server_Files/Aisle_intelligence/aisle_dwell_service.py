"""
Aisle Dwell-Time Service - Laptop
====================================
Tracks how long each detected person spends inside each aisle's
calibrated zone, using one background thread per aisle video.

Run this on your laptop (separate from doorway_service and queue_service):
    pip install ultralytics opencv-python flask
    python aisle_dwell_service.py

Then from any device on the same network:
    http://<laptop-ip>:5003/
"""

import csv
import json
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import cv2
from flask import Flask, jsonify, render_template_string
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
ZONES_FILE = ROOT / "aisle_zones.json"
MODEL_PATH = "yolov8n.pt"
CONFIDENCE = 0.4
IOU = 0.5
TRACKER = "bytetrack.yaml"

CSV_PATH = ROOT / "data" / "aisle_dwell_events.csv"
CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

SERVICE_PORT = 5003

# Load calibrated zones
if not ZONES_FILE.exists():
    raise RuntimeError(
        f"Missing {ZONES_FILE}. Run calibrate_aisle_zones.py first."
    )

with ZONES_FILE.open("r", encoding="utf-8") as f:
    AISLE_ZONES = json.load(f)

if not AISLE_ZONES:
    raise RuntimeError(
        "aisle_zones.json is empty. Run calibrate_aisle_zones.py first "
        "to define at least one aisle's zone polygon."
    )

# =========================================================
# INLINE DASHBOARD HTML TEMPLATE
# =========================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aisle Dwell-Time Dashboard</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --accent-blue: #38bdf8;
            --accent-purple: #a855f7;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --border-color: #334155;
            --highlight: #22c55e;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 24px;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }

        h1 {
            font-size: 1.5rem;
            font-weight: 600;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            background-color: var(--card-bg);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.875rem;
            border: 1px solid var(--border-color);
        }

        .pulse-dot {
            width: 10px;
            height: 10px;
            background-color: var(--highlight);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--highlight);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }

        .grid-layout {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
        }

        @media (max-width: 1024px) {
            .grid-layout {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background-color: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            padding: 20px;
            margin-bottom: 24px;
        }

        .card h3 {
            margin-bottom: 16px;
            color: var(--text-sub);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        /* Metrics grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .metric-box {
            background-color: rgba(255, 255, 255, 0.03);
            padding: 16px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }

        .metric-box label {
            font-size: 0.75rem;
            color: var(--text-sub);
            text-transform: uppercase;
        }

        .metric-box .val {
            font-size: 1.6rem;
            font-weight: 700;
            margin-top: 4px;
            color: var(--accent-blue);
        }

        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }

        th, td {
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
        }

        th {
            color: var(--text-sub);
            font-weight: 500;
        }

        tbody tr:hover {
            background-color: rgba(255, 255, 255, 0.02);
        }

        /* Heatmap image styling */
        .heatmap-container {
            width: 100%;
            border-radius: 8px;
            overflow: hidden;
            background-color: #000;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 250px;
            border: 1px dashed var(--border-color);
        }

        .heatmap-img {
            max-width: 100%;
            height: auto;
            display: block;
        }

        .badge-busiest {
            background-color: var(--accent-purple);
            color: #fff;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }
    </style>
</head>
<body>

    <header>
        <h1>Aisle Dwell-Time Analytics</h1>
        <div class="status-badge">
            <div class="pulse-dot"></div>
            <span>SERVICE ACTIVE</span>
        </div>
    </header>

    <div class="grid-layout">
        <!-- Main Column: Summary Table & Recent Events -->
        <div>
            <div class="card">
                <h3>Aisle Performance Breakdown</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Aisle ID</th>
                            <th>Inside Now</th>
                            <th>Visits</th>
                            <th>Avg Dwell</th>
                            <th>Longest Dwell</th>
                        </tr>
                    </thead>
                    <tbody id="aisle-table-body">
                        <!-- Dynamically filled -->
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h3>Recent Dwell Events (Last 20)</h3>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Aisle</th>
                            <th>Track ID</th>
                            <th>Enter Time</th>
                            <th>Duration</th>
                        </tr>
                    </thead>
                    <tbody id="events-table-body">
                        <!-- Dynamically filled -->
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Right Column: Summary Metrics & Heatmap -->
        <div>
            <div class="card">
                <h3>Live Insights</h3>
                <div class="metrics-grid">
                    <div class="metric-box">
                        <label>Busiest Aisle</label>
                        <div class="val" id="metric-busiest" style="font-size: 1.2rem; color: var(--accent-purple);">--</div>
                    </div>
                    <div class="metric-box">
                        <label>Active Aisles</label>
                        <div class="val" id="metric-active-aisles">0</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h3>Store Spatial Heatmap</h3>
                <div class="heatmap-container">
                    <img id="heatmap-img" class="heatmap-img" src="/heatmap.png" alt="Heatmap preview" 
                         onerror="this.style.display='none'; document.getElementById('heatmap-fallback').style.display='block';">
                    <div id="heatmap-fallback" style="display:none; color: var(--text-sub); text-align: center; padding: 20px;">
                        Floor plan not configured.<br>
                        <small>Run <code>calibrate_floor_plan.py</code> to enable heatmap visualization.</small>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function updateDashboard() {
            try {
                // Fetch summary statistics
                const summaryRes = await fetch('/analytics/summary');
                const summaryData = await summaryRes.json();

                // Fetch recent events
                const eventsRes = await fetch('/analytics/events/recent');
                const eventsData = await eventsRes.json();

                // Update Metrics
                document.getElementById('metric-busiest').innerText = summaryData.busiest_aisle || 'N/A';
                document.getElementById('metric-active-aisles').innerText = Object.keys(summaryData.aisles || {}).length;

                // Update Aisle Table
                const aisleTable = document.getElementById('aisle-table-body');
                aisleTable.innerHTML = '';
                
                for (const [aisleId, stats] of Object.entries(summaryData.aisles || {})) {
                    const isBusiest = aisleId === summaryData.busiest_aisle;
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>
                            <strong>${aisleId}</strong> 
                            ${isBusiest ? '<span class="badge-busiest">BUSIEST</span>' : ''}
                        </td>
                        <td>${stats.people_inside_now}</td>
                        <td>${stats.completed_visits}</td>
                        <td>${stats.average_dwell_seconds}s</td>
                        <td>${stats.longest_dwell_seconds}s</td>
                    `;
                    aisleTable.appendChild(row);
                }

                // Update Recent Events Table
                const eventsTable = document.getElementById('events-table-body');
                eventsTable.innerHTML = '';

                eventsData.forEach(evt => {
                    const row = document.createElement('tr');
                    const timeStr = evt.enter_time ? evt.enter_time.split('T')[1] || evt.enter_time : '';
                    row.innerHTML = `
                        <td>#${evt.event_id}</td>
                        <td>${evt.aisle_id}</td>
                        <td>ID ${evt.track_id}</td>
                        <td>${timeStr}</td>
                        <td><strong>${evt.duration_seconds}s</strong></td>
                    `;
                    eventsTable.appendChild(row);
                });

                // Refresh Heatmap timestamp to bypass cache if image is enabled
                const heatmapImg = document.getElementById('heatmap-img');
                if (heatmapImg.style.display !== 'none') {
                    heatmapImg.src = '/heatmap.png?t=' + new Date().getTime();
                }

            } catch (err) {
                console.error('Error fetching dashboard data:', err);
            }
        }

        // Auto-refresh every 2 seconds
        setInterval(updateDashboard, 2000);
        updateDashboard();
    </script>
</body>
</html>
"""

# =========================================================
# SHARED STATE
# =========================================================

state_lock = threading.Lock()

# Per-aisle live state: who's currently inside, and running totals
aisle_state = {
    aisle_id: {
        "currently_inside": {},   # track_id -> entry_time (epoch seconds)
        "completed_dwells": [],   # list of durations in seconds, this session
        "people_inside_now": 0,
    }
    for aisle_id in AISLE_ZONES
}

if not CSV_PATH.exists():
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            ["event_id", "aisle_id", "track_id", "enter_time", "exit_time", "duration_seconds"]
        )

event_counter_lock = threading.Lock()
event_counter = 1


def log_dwell_event(aisle_id, track_id, enter_time, exit_time):
    global event_counter
    with event_counter_lock:
        current_id = event_counter
        event_counter += 1

    duration = round(exit_time - enter_time, 1)
    row = [
        current_id, aisle_id, track_id,
        datetime.fromtimestamp(enter_time).isoformat(timespec="seconds"),
        datetime.fromtimestamp(exit_time).isoformat(timespec="seconds"),
        duration,
    ]

    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)

    print(f"[DWELL] {aisle_id} | person {track_id} | {duration}s")
    return duration


def point_inside_zone(point, polygon):
    result = cv2.pointPolygonTest(polygon, (float(point[0]), float(point[1])), False)
    return result >= 0


# =========================================================
# PER-AISLE DETECTION WORKER
# =========================================================

def aisle_worker(aisle_id, video_filename, polygon_points):
    import numpy as np
    polygon = np.array(polygon_points, dtype=np.int32)

    video_path = ROOT / video_filename
    model = YOLO(MODEL_PATH)  # each thread loads its own model instance

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR [{aisle_id}]: could not open video {video_path}")
        return

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_delay = 1.0 / source_fps

    print(f"[{aisle_id}] worker started, reading {video_filename}")

    missing_frames_by_track = defaultdict(int)
    MAX_MISSING_FRAMES = 20  # ~ a few seconds worth, tune per your fps

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        time.sleep(frame_delay)

        results = model.track(
            frame, persist=True, tracker=TRACKER,
            conf=CONFIDENCE, iou=IOU, classes=[0], verbose=False,
        )

        seen_ids = set()

        if results and results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes
            track_ids = boxes.id.int().cpu().tolist()
            coordinates = boxes.xyxy.cpu().numpy()

            for track_id, box in zip(track_ids, coordinates):
                x1, y1, x2, y2 = box
                center = (int((x1 + x2) / 2), int((y1 + y2) / 2))
                inside = point_inside_zone(center, polygon)

                with state_lock:
                    entry_dict = aisle_state[aisle_id]["currently_inside"]

                    if inside:
                        seen_ids.add(track_id)
                        missing_frames_by_track[track_id] = 0
                        if track_id not in entry_dict:
                            entry_dict[track_id] = time.time()

        # Handle people who've disappeared or left the zone
        with state_lock:
            entry_dict = aisle_state[aisle_id]["currently_inside"]
            for track_id in list(entry_dict.keys()):
                if track_id in seen_ids:
                    continue

                missing_frames_by_track[track_id] += 1

                if missing_frames_by_track[track_id] >= MAX_MISSING_FRAMES:
                    enter_time = entry_dict.pop(track_id)
                    exit_time = time.time()
                    duration = log_dwell_event(aisle_id, track_id, enter_time, exit_time)
                    aisle_state[aisle_id]["completed_dwells"].append(duration)
                    missing_frames_by_track.pop(track_id, None)

            aisle_state[aisle_id]["people_inside_now"] = len(entry_dict)


# =========================================================
# FLASK API & DASHBOARD ROUTES
# =========================================================

app = Flask(__name__)


@app.route("/")
def dashboard():
    """Renders the inline interactive web dashboard."""
    return render_template_string(DASHBOARD_HTML)


@app.route("/analytics/summary")
def analytics_summary():
    with state_lock:
        result = {}
        for aisle_id, data in aisle_state.items():
            dwells = data["completed_dwells"]
            avg_dwell = round(sum(dwells) / len(dwells), 1) if dwells else 0
            result[aisle_id] = {
                "people_inside_now": data["people_inside_now"],
                "completed_visits": len(dwells),
                "average_dwell_seconds": avg_dwell,
                "longest_dwell_seconds": round(max(dwells), 1) if dwells else 0,
            }

    # Identify which aisle has the highest average dwell time right now
    busiest_aisle = None
    if result:
        aisles_with_data = {k: v for k, v in result.items() if v["completed_visits"] > 0}
        if aisles_with_data:
            busiest_aisle = max(aisles_with_data, key=lambda a: aisles_with_data[a]["average_dwell_seconds"])

    return jsonify({
        "aisles": result,
        "busiest_aisle": busiest_aisle,
    })


@app.route("/analytics/events/recent")
def recent_events():
    events = []
    if CSV_PATH.exists():
        with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
            events = list(csv.DictReader(f))
    events = events[-20:]
    events.reverse()
    return jsonify(events)


@app.route("/heatmap.png")
def heatmap_image():
    """Renders and serves the current heatmap as a PNG image."""
    from flask import send_file
    try:
        import generate_heatmap
        current_analytics = analytics_summary().get_json()
        output_path = generate_heatmap.generate_heatmap(analytics_data=current_analytics)
        return send_file(output_path, mimetype="image/png")
    except Exception:
        return jsonify({
            "error": "floor_plan_not_configured",
            "message": "Run calibrate_floor_plan.py first to set up floor_plan_map.json",
        }), 404


if __name__ == "__main__":
    for aisle_id, config in AISLE_ZONES.items():
        thread = threading.Thread(
            target=aisle_worker,
            args=(aisle_id, config["video"], config["polygon"]),
            daemon=True,
        )
        thread.start()

    print()
    print("==========================================")
    print("  AISLE DWELL-TIME SERVICE")
    print("==========================================")
    print(f" Aisles tracked: {list(AISLE_ZONES.keys())}")
    print(f" Dashboard UI:  http://0.0.0.0:{SERVICE_PORT}/")
    print(f" Analytics:     http://0.0.0.0:{SERVICE_PORT}/analytics/summary")
    print("==========================================")
    print()

    app.run(host="0.0.0.0", port=SERVICE_PORT, debug=False, use_reloader=False)