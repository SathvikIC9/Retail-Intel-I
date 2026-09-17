"""
Aisle Dwell-Time Zone Calibration Tool (Reframed & Auto-Scaled)
================================================================
Lets you click ONE zone polygon per aisle video, saved into
aisle_zones.json in the format:

    {
      "aisle_1": {
        "video": "aisle1.mp4",
        "polygon": [[x, y], ...]
      },
      "aisle_2": {
        "video": "aisle2.mp4",
        "polygon": [[x, y], ...]
      }
    }

Usage:
    python calibrate_aisle_zones.py

Controls:
    N             = start calibrating the NEXT aisle
    A / D         = step to previous / next frame
    SPACE         = jump forward 30 frames
    LEFT CLICK    = add polygon point
    RIGHT CLICK   = remove last point
    ENTER         = confirm this aisle's zone, save, move to next aisle
    ESC           = quit
"""

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
ZONES_FILE = ROOT / "aisle_zones.json"

# Maximum dimensions for display window to prevent screen overflow
MAX_DISPLAY_WIDTH = 1280
MAX_DISPLAY_HEIGHT = 720

if ZONES_FILE.exists():
    with ZONES_FILE.open("r", encoding="utf-8") as f:
        aisle_zones = json.load(f)
else:
    aisle_zones = {}

points = []
current_frame_index = 0
cap = None
total_frames = 0
current_aisle_id = None
current_video_name = None

# Scaling variables
scale = 1.0
disp_w = 0
disp_h = 0


def mouse_callback(event, x, y, flags, param):
    global points, scale
    if event == cv2.EVENT_LBUTTONDOWN:
        # Convert scaled mouse click coordinates back to original video resolution
        orig_x = int(round(x / scale))
        orig_y = int(round(y / scale))
        points.append((orig_x, orig_y))
        print(f"  Point {len(points)}: ({orig_x}, {orig_y})")
    elif event == cv2.EVENT_RBUTTONDOWN:
        if points:
            removed = points.pop()
            print(f"  Removed point: {removed}")


def read_frame(index):
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ret, frame = cap.read()
    return frame if ret else None


def update_scale_and_dimensions(orig_w, orig_h):
    """Calculates display scale factor so video fits on screen."""
    global scale, disp_w, disp_h
    scale_w = MAX_DISPLAY_WIDTH / orig_w
    scale_h = MAX_DISPLAY_HEIGHT / orig_h
    scale = min(1.0, scale_w, scale_h)  # Only downscale if larger than max limits

    disp_w = int(orig_w * scale)
    disp_h = int(orig_h * scale)


def start_new_aisle():
    global cap, total_frames, current_frame_index, current_aisle_id, current_video_name, points

    aisle_id = input("\nEnter aisle ID (e.g. aisle_1): ").strip()
    video_name = input(f"Enter video filename for {aisle_id} (e.g. aisle1.mp4): ").strip()

    video_path = ROOT / video_name
    new_cap = cv2.VideoCapture(str(video_path))

    if not new_cap.isOpened():
        print(f"ERROR: Could not open {video_path}. Check the filename and try again.")
        return False

    cap = new_cap
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    current_frame_index = 0
    current_aisle_id = aisle_id
    current_video_name = video_name
    points = []

    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    update_scale_and_dimensions(orig_w, orig_h)

    print(f"Now calibrating: {aisle_id} using {video_name} ({total_frames} frames, resolution: {orig_w}x{orig_h})")
    return True


window_name = "Aisle Dwell Zone Calibration"
# WINDOW_NORMAL allows standard resizing without forcing full frame display
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.setMouseCallback(window_name, mouse_callback)

print()
print("=================================================")
print("   AISLE DWELL-TIME ZONE CALIBRATION")
print("=================================================")
print(f"Existing aisles already calibrated: {list(aisle_zones.keys())}")
print()
print("Press N to start calibrating the next aisle.")
print()

if not start_new_aisle():
    raise SystemExit(1)

frame = read_frame(current_frame_index)

while frame is None:
    print("Could not read a frame. Try again.")
    if not start_new_aisle():
        raise SystemExit(1)
    frame = read_frame(current_frame_index)

while True:
    display = frame.copy()

    # Draw points on original frame resolution
    for i, point in enumerate(points):
        cv2.circle(display, point, 7, (0, 140, 255), -1)
        cv2.putText(display, str(i + 1), (point[0] + 10, point[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 140, 255), 2)

    if len(points) >= 2:
        for i in range(len(points) - 1):
            cv2.line(display, points[i], points[i + 1], (0, 140, 255), 2)

    if len(points) >= 3:
        overlay = display.copy()
        cv2.fillPoly(overlay, [np.array(points)], (0, 140, 255))
        display = cv2.addWeighted(overlay, 0.2, display, 0.8, 0)

    # Context Header UI
    cv2.rectangle(display, (10, 10), (620, 120), (0, 0, 0), -1)
    cv2.putText(display, f"Calibrating: {current_aisle_id} ({current_video_name})", (25, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(display, "Left click: add | Right click: undo | ENTER: save+next aisle", (25, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(display, "A/D: prev/next frame | SPACE: +30 frames | N: new aisle | ESC: quit", (25, 82),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(display, f"Frame {current_frame_index}/{total_frames}", (25, 106),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Resize frame to fit within workspace limits
    resized_display = cv2.resize(display, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
    cv2.resizeWindow(window_name, disp_w, disp_h)
    cv2.imshow(window_name, resized_display)

    key = cv2.waitKey(1) & 0xFF

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

    elif key == ord("n"):
        if start_new_aisle():
            new_frame = read_frame(current_frame_index)
            if new_frame is not None:
                frame = new_frame

    elif key == 13:  # ENTER
        if len(points) < 3:
            print("ERROR: Select at least 3 points before confirming.")
            continue

        aisle_zones[current_aisle_id] = {
            "video": current_video_name,
            "polygon": [list(p) for p in points],
        }

        with ZONES_FILE.open("w", encoding="utf-8") as f:
            json.dump(aisle_zones, f, indent=2)

        print()
        print(f"Saved {current_aisle_id} -> {ZONES_FILE}")
        print(f"All aisles so far: {list(aisle_zones.keys())}")
        print("Press N to calibrate another aisle, or ESC to finish.")
        print()

    elif key == 27:  # ESC
        print("Calibration finished.")
        break

cap.release()
cv2.destroyAllWindows()