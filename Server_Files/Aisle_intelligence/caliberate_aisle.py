"""
Floor Plan Region Calibration Tool
=====================================
Click a region (rectangle or polygon) for each aisle on your store's
floor plan image, tagged with the SAME aisle_id used in aisle_zones.json
(e.g. "aisle_1", "aisle_2"). This links each camera's dwell-time data
to a specific spot on the floor plan, so the heatmap knows where to
draw each aisle's color.

Saves to floor_plan_map.json:
    {
      "floor_plan_image": "store_floor_plan.png",
      "regions": {
        "aisle_1": [[x, y], [x, y], [x, y], [x, y]],
        "aisle_2": [[x, y], [x, y], [x, y], [x, y]]
      }
    }

Usage:
    python calibrate_floor_plan.py

Controls:
    LEFT CLICK   = add a point for the CURRENT aisle's region
    RIGHT CLICK  = remove last point
    ENTER        = confirm this aisle's region, save, prompts for next aisle_id
    ESC          = quit
"""

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
MAP_FILE = ROOT / "floor_plan_map.json"

FLOOR_PLAN_IMAGE = "map.png"  # <-- change to your actual filename

points = []
current_aisle_id = None

if MAP_FILE.exists():
    with MAP_FILE.open("r", encoding="utf-8") as f:
        saved_map = json.load(f)
    regions = saved_map.get("regions", {})
else:
    regions = {}

image_path = ROOT / FLOOR_PLAN_IMAGE
base_image = cv2.imread(str(image_path))

if base_image is None:
    print(f"ERROR: Could not load {image_path}")
    print("Set FLOOR_PLAN_IMAGE at the top of this script to your actual filename.")
    raise SystemExit(1)


def mouse_callback(event, x, y, flags, param):
    global points
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        print(f"  Point {len(points)}: ({x}, {y})")
    elif event == cv2.EVENT_RBUTTONDOWN:
        if points:
            removed = points.pop()
            print(f"  Removed point: {removed}")


def prompt_next_aisle():
    global current_aisle_id, points
    aisle_id = input(
        "\nEnter aisle_id for this region (must match aisle_zones.json, "
        "e.g. aisle_1) or press Enter alone to finish: "
    ).strip()

    if not aisle_id:
        return False

    current_aisle_id = aisle_id
    points = []
    print(f"Now click the region for: {current_aisle_id}")
    return True


window_name = "Floor Plan Calibration"
cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, mouse_callback)

print()
print("=================================================")
print("   FLOOR PLAN REGION CALIBRATION")
print("=================================================")
print(f"Floor plan image: {image_path}")
print(f"Already-mapped aisles: {list(regions.keys())}")
print()

if not prompt_next_aisle():
    print("Nothing to calibrate. Exiting.")
    raise SystemExit(0)

while True:
    display = base_image.copy()

    # Draw already-saved regions (dimmed, labeled)
    for aisle_id, region_points in regions.items():
        polygon = np.array(region_points, dtype=np.int32)
        cv2.polylines(display, [polygon], True, (150, 150, 150), 1)
        label_point = tuple(region_points[0])
        cv2.putText(display, aisle_id, label_point,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)

    # Draw the region currently being clicked
    for i, point in enumerate(points):
        cv2.circle(display, point, 6, (0, 140, 255), -1)
        cv2.putText(display, str(i + 1), (point[0] + 8, point[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 140, 255), 2)

    if len(points) >= 2:
        for i in range(len(points) - 1):
            cv2.line(display, points[i], points[i + 1], (0, 140, 255), 2)

    if len(points) >= 3:
        overlay = display.copy()
        cv2.fillPoly(overlay, [np.array(points)], (0, 140, 255))
        display = cv2.addWeighted(overlay, 0.25, display, 0.75, 0)

    cv2.rectangle(display, (5, 5), (500, 70), (0, 0, 0), -1)
    cv2.putText(display, f"Mapping: {current_aisle_id}", (18, 27),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    cv2.putText(display, "Click corners of this aisle's shape | ENTER: confirm | ESC: quit",
                (18, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    cv2.imshow(window_name, display)
    key = cv2.waitKey(1) & 0xFF

    if key == 13:  # ENTER
        if len(points) < 3:
            print("ERROR: Select at least 3 points (corners) before confirming.")
            continue

        regions[current_aisle_id] = [list(p) for p in points]

        with MAP_FILE.open("w", encoding="utf-8") as f:
            json.dump({
                "floor_plan_image": FLOOR_PLAN_IMAGE,
                "regions": regions,
            }, f, indent=2)

        print(f"Saved region for {current_aisle_id} -> {MAP_FILE}")

        if not prompt_next_aisle():
            print("Calibration complete.")
            break

    elif key == 27:  # ESC
        print("Calibration ended.")
        break

cv2.destroyAllWindows()