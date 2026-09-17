"""
Queue Alert Line Calibration Tool
=====================================
Lets you draw ONE overflow alert line per counter, on a frame from your
queue video. If a person in that counter's queue is detected standing
BEYOND this line (farther from the counter than the line), an alert
gets raised.

Saves to alert_lines.json:
    {
      "counter_1": {
        "line": [[x1, y1], [x2, y2]],
        "counter_side_point": [x, y]
      }
    }

"counter_side_point" is a point you click on the COUNTER side of the
line (e.g. near the cashier), used to figure out which side of the
line counts as "too far back" vs "still fine".

Usage:
    python calibrate_alert_lines.py

Controls:
    1-9            = set counter number
    LEFT CLICK      = first click = line point 1, second click = line
                       point 2, third click = the counter-side reference point
    RIGHT CLICK     = undo last click
    ENTER           = confirm this counter's line, move to next counter
    A / D           = step to previous / next frame
    SPACE           = jump forward 30 frames
    ESC             = quit
"""

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
VIDEO_PATH = ROOT / "q2.mp4"     # <-- change to your actual queue video filename
LINES_FILE = ROOT / "alert_lines.json"

clicks = []
current_counter = 1
current_frame_index = 0

if LINES_FILE.exists():
    with LINES_FILE.open("r", encoding="utf-8") as f:
        saved_lines = json.load(f)
else:
    saved_lines = {}

cap = cv2.VideoCapture(str(VIDEO_PATH))
if not cap.isOpened():
    print(f"ERROR: Could not open video file {VIDEO_PATH}")
    raise SystemExit(1)

total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))


def read_frame(index):
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ret, frame = cap.read()
    return frame if ret else None


def mouse_callback(event, x, y, flags, param):
    global clicks
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(clicks) < 3:
            clicks.append((x, y))
            labels = ["Line point 1", "Line point 2", "Counter-side reference point"]
            print(f"  {labels[len(clicks) - 1]}: ({x}, {y})")
    elif event == cv2.EVENT_RBUTTONDOWN:
        if clicks:
            removed = clicks.pop()
            print(f"  Removed: {removed}")


window_name = "Queue Alert Line Calibration"
cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, mouse_callback)

print()
print("=================================================")
print("   QUEUE ALERT LINE CALIBRATION")
print("=================================================")
print(f"Video: {VIDEO_PATH} ({total_frames} frames)")
print(f"Existing alert lines: {list(saved_lines.keys())}")
print()
print("1-9            = set counter number")
print("Click 1        = first line point")
print("Click 2        = second line point")
print("Click 3        = a reference point on the COUNTER side of the line")
print("ENTER          = confirm this counter's line")
print("A/D            = prev/next frame | SPACE: +30 frames | ESC: quit")
print()

frame = read_frame(current_frame_index)
if frame is None:
    print("ERROR: Could not read a frame.")
    raise SystemExit(1)

while True:
    display = frame.copy()

    for i, point in enumerate(clicks):
        color = (0, 200, 255) if i < 2 else (0, 255, 0)
        cv2.circle(display, point, 7, color, -1)

    if len(clicks) >= 2:
        cv2.line(display, clicks[0], clicks[1], (0, 200, 255), 3)

    if len(clicks) == 3:
        cv2.putText(display, "COUNTER SIDE", (clicks[2][0] + 10, clicks[2][1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.rectangle(display, (10, 10), (620, 130), (0, 0, 0), -1)
    cv2.putText(display, f"Alert line for: counter_{current_counter}", (25, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
    cv2.putText(display, "1-9: counter | Click line pt1, pt2, then counter-side point", (25, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(display, "ENTER: confirm | A/D: frame | ESC: quit", (25, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(display, f"Frame {current_frame_index}/{total_frames}", (25, 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    cv2.imshow(window_name, display)
    key = cv2.waitKey(1) & 0xFF

    if key in [ord(str(n)) for n in range(1, 10)]:
        current_counter = int(chr(key))
        print(f"Counter set to: {current_counter}")

    elif key == ord("a"):
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

    elif key == 13:  # ENTER
        if len(clicks) != 3:
            print("ERROR: Need exactly 3 clicks (line point 1, line point 2, counter-side point).")
            continue

        counter_key = f"counter_{current_counter}"
        saved_lines[counter_key] = {
            "line": [list(clicks[0]), list(clicks[1])],
            "counter_side_point": list(clicks[2]),
        }

        with LINES_FILE.open("w", encoding="utf-8") as f:
            json.dump(saved_lines, f, indent=2)

        print(f"Saved alert line for {counter_key} -> {LINES_FILE}")
        clicks = []

    elif key == 27:  # ESC
        print("Calibration ended.")
        break

cap.release()
cv2.destroyAllWindows()