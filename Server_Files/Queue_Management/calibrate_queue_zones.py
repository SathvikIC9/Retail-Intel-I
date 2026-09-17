"""
Queue Zone Calibration Tool - Video File Mode (Reframed & Auto-Scaled)
=======================================================================
Lets you click zone polygons (cashier / service / queue) for one or more
counters on a frame pulled from a video file, and saves them into
zones.json in the exact format zone_assigner.py expects:

    {
      "counter_1_cashier": [[x, y], ...],
      "counter_1_service": [[x, y], ...],
      "counter_1_queue":   [[x, y], ...],
      "counter_2_cashier": [[x, y], ...],
      ...
    }

Usage:
    python calibrate_queue_zones.py

Workflow:
    1. Step through the video (A/D or SPACE) to find a good frame.
    2. Pick a counter number (1, 2, 3...) and a zone type (cashier/
       service/queue) using number keys and letter keys shown on screen.
    3. Click the polygon points for that zone.
    4. Press ENTER to save the CURRENT zone and move to the next one.
    5. Repeat for every zone/counter you need.
    6. Press W at any time to write everything collected so far to
       zones.json. Press ESC to quit.
"""

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
VIDEO_PATH = ROOT / "q2.mp4"     # <-- change this to your actual video filename
ZONES_FILE = ROOT / "zones.json"

# Set this to True to wipe ALL existing zones and start completely fresh
# every time you run this script. Set back to False once you're happy
# with your zones, so re-running the tool doesn't erase your work.
RESET_ON_START = True

# Maximum display window constraints to prevent screen overflow
MAX_DISPLAY_WIDTH = 1280
MAX_DISPLAY_HEIGHT = 720

ZONE_TYPES = ["cashier", "service", "queue"]
ZONE_TYPE_KEYS = {ord("c"): "cashier", ord("s"): "service", ord("q"): "queue"}

ZONE_COLORS = {
    "cashier": (0, 0, 255),      # red
    "service": (0, 200, 0),      # green
    "queue": (255, 180, 0),      # orange/blue mix
}

points = []
current_counter = 1
current_zone_type = "cashier"
current_frame_index = 0

# Scaling global state
scale = 1.0
disp_w = 0
disp_h = 0

# Load any existing zones so re-running this tool doesn't wipe prior work,
# UNLESS RESET_ON_START is True, in which case we start with a clean slate
# and immediately overwrite zones.json on disk too.
if RESET_ON_START:
    saved_zones = {}
    with ZONES_FILE.open("w", encoding="utf-8") as f:
        json.dump(saved_zones, f, indent=4)
    print(f"RESET_ON_START=True: cleared {ZONES_FILE} - starting fresh.")
elif ZONES_FILE.exists():
    with ZONES_FILE.open("r", encoding="utf-8") as f:
        saved_zones = json.load(f)
else:
    saved_zones = {}

cap = cv2.VideoCapture(str(VIDEO_PATH))
if not cap.isOpened():
    print(f"ERROR: Could not open video file {VIDEO_PATH}")
    print("Set VIDEO_PATH at the top of this script to your actual video filename.")
    raise SystemExit(1)

total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# Calculate scale factor to keep output contained in screen frame
scale_w = MAX_DISPLAY_WIDTH / orig_w
scale_h = MAX_DISPLAY_HEIGHT / orig_h
scale = min(1.0, scale_w, scale_h)

disp_w = int(orig_w * scale)
disp_h = int(orig_h * scale)


def read_frame(index):
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ret, frame = cap.read()
    return frame if ret else None


def mouse_callback(event, x, y, flags, param):
    global points, scale
    if event == cv2.EVENT_LBUTTONDOWN:
        # Scale mouse click coordinates back up to original video resolution
        orig_x = int(round(x / scale))
        orig_y = int(round(y / scale))
        points.append((orig_x, orig_y))
        print(f"  Point {len(points)}: ({orig_x}, {orig_y})")
    elif event == cv2.EVENT_RBUTTONDOWN:
        if points:
            removed = points.pop()
            print(f"  Removed point: {removed}")


window_name = "Queue Zone Calibration (video mode)"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.setMouseCallback(window_name, mouse_callback)

print()
print("=================================================")
print("   QUEUE ZONE CALIBRATION TOOL (video file)")
print("=================================================")
print(f"Video: {VIDEO_PATH} ({total_frames} frames, resolution: {orig_w}x{orig_h})")
print(f"Existing zones loaded: {list(saved_zones.keys())}")
print()
print("A / D          = step to previous / next frame")
print("SPACE          = jump forward 30 frames")
print("1-9            = set counter number")
print("C / S / Q      = set zone type (cashier / service / queue)")
print("LEFT CLICK     = add polygon point")
print("RIGHT CLICK    = remove last point")
print("ENTER          = confirm current zone, move to next")
print("W              = write zones.json now")
print("R              = RESET - clear ALL zones and start over")
print("ESC            = quit without saving further changes")
print()

frame = read_frame(current_frame_index)
if frame is None:
    print("ERROR: Could not read a frame from the video.")
    raise SystemExit(1)

while True:
    display = frame.copy()

    # Draw the zone currently being clicked
    active_color = ZONE_COLORS.get(current_zone_type, (255, 255, 255))
    for i, point in enumerate(points):
        cv2.circle(display, point, 6, active_color, -1)
        cv2.putText(display, str(i + 1), (point[0] + 8, point[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, active_color, 2)

    if len(points) >= 2:
        for i in range(len(points) - 1):
            cv2.line(display, points[i], points[i + 1], active_color, 2)

    if len(points) >= 3:
        overlay = display.copy()
        cv2.fillPoly(overlay, [np.array(points)], active_color)
        display = cv2.addWeighted(overlay, 0.20, display, 0.80, 0)

    zone_key_name = f"counter_{current_counter}_{current_zone_type}"

    cv2.rectangle(display, (10, 10), (620, 150), (0, 0, 0), -1)
    cv2.putText(display, "QUEUE ZONE CALIBRATION (video mode)", (25, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(display, f"Now drawing: {zone_key_name}", (25, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, active_color, 2)
    cv2.putText(display, "1-9: counter | C/S/Q: cashier/service/queue", (25, 82),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(display, "Click: add point | Right-click: undo | ENTER: confirm zone", (25, 104),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(display, "A/D: prev/next frame | W: write zones.json | R: reset all | ESC: quit", (25, 126),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(display, f"Frame {current_frame_index}/{total_frames}", (25, 148),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Resize image display buffer to scaled dimensions before rendering
    resized_display = cv2.resize(display, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
    cv2.resizeWindow(window_name, disp_w, disp_h)
    cv2.imshow(window_name, resized_display)
    
    key = cv2.waitKey(1) & 0xFF

    if key == 255:
        continue

    if key == ord("a"):
        current_frame_index = max(0, current_frame_index - 1)
        new_frame = read_frame(current_frame_index)
        if new_frame is not None:
            frame = new_frame

    elif key == ord("d"):
        current_frame_index = min(total_frames - 1, current_frame_index + 1)
        new_frame = read_frame(current_frame_index)
        if new_frame is not None:
            frame = new_frame

    elif key == ord(" "):
        current_frame_index = min(total_frames - 1, current_frame_index + 30)
        new_frame = read_frame(current_frame_index)
        if new_frame is not None:
            frame = new_frame

    elif key in [ord(str(n)) for n in range(1, 10)]:
        current_counter = int(chr(key))
        print(f"Counter set to: {current_counter}")

    elif key in ZONE_TYPE_KEYS:
        current_zone_type = ZONE_TYPE_KEYS[key]
        print(f"Zone type set to: {current_zone_type}")

    elif key == 13:  # ENTER - confirm current zone
        if len(points) < 3:
            print("ERROR: Select at least 3 points before confirming a zone.")
            continue

        saved_zones[zone_key_name] = [list(p) for p in points]
        print(f"Zone saved (in memory): {zone_key_name} ({len(points)} points)")
        print("Press W to write zones.json to disk, or continue drawing more zones.")
        points = []

    elif key == ord("r"):
        saved_zones.clear()
        points.clear()
        with ZONES_FILE.open("w", encoding="utf-8") as f:
            json.dump(saved_zones, f, indent=4)
        print()
        print("ALL ZONES CLEARED. zones.json is now empty. Start drawing fresh.")
        print()

    elif key == ord("w"):
        with ZONES_FILE.open("w", encoding="utf-8") as f:
            json.dump(saved_zones, f, indent=4)
        print()
        print("=================================================")
        print(f"zones.json WRITTEN with {len(saved_zones)} zones:")
        for name in saved_zones:
            print(f"  - {name}")
        print("=================================================")
        print()

    elif key == 27:  # ESC
        print("Calibration session ended (any unsaved zone confirmations were kept in memory only if you pressed W).")
        break

cap.release()
cv2.destroyAllWindows()