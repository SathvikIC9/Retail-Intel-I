"""
Store Heatmap Generator
==========================
Reads floor_plan_map.json (which region on the floor plan = which aisle)
and the aisle dwell-time service's live /analytics/summary data, then
draws a color-coded heatmap overlay: aisles with longer average dwell
time appear "hotter" (red), quick-pass aisles appear "cooler" (blue).

This module is imported by main.py-side code (or run standalone to test).
It does NOT run its own Flask server - it's a helper that the aisle
service or the board can call to get a rendered heatmap image.

Standalone test usage:
    python generate_heatmap.py
    (writes heatmap_output.png you can open and inspect)
"""

import json
from pathlib import Path

import cv2
import numpy as np
import requests

ROOT = Path(__file__).resolve().parent
MAP_FILE = ROOT / "floor_plan_map.json"

AISLE_SERVICE_URL = "http://localhost:5003/analytics/summary"


def load_floor_plan_map():
    with MAP_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def dwell_time_to_color(dwell_seconds, min_dwell, max_dwell):
    """Maps a dwell time to a color on a blue (cool/quick) -> red (hot/slow) scale."""
    if max_dwell <= min_dwell:
        ratio = 0.5
    else:
        ratio = (dwell_seconds - min_dwell) / (max_dwell - min_dwell)
        ratio = max(0.0, min(1.0, ratio))

    # BGR format (OpenCV). Blue at ratio=0, Yellow in middle, Red at ratio=1.
    if ratio < 0.5:
        local_ratio = ratio / 0.5
        b = int(255 * (1 - local_ratio))
        g = int(255 * local_ratio)
        r = 0
    else:
        local_ratio = (ratio - 0.5) / 0.5
        b = 0
        g = int(255 * (1 - local_ratio))
        r = int(255 * local_ratio)

    return (b, g, r)


def fetch_aisle_analytics():
    try:
        response = requests.get(AISLE_SERVICE_URL, timeout=3)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"WARNING: could not reach aisle service ({e}). Using zero data.")
        return {"aisles": {}, "busiest_aisle": None}


def generate_heatmap(output_path="heatmap_output.png", analytics_data=None):
    floor_plan_data = load_floor_plan_map()
    floor_plan_image_path = ROOT / floor_plan_data["floor_plan_image"]
    regions = floor_plan_data["regions"]

    base_image = cv2.imread(str(floor_plan_image_path))
    if base_image is None:
        raise RuntimeError(f"Could not load floor plan image: {floor_plan_image_path}")

    analytics = analytics_data if analytics_data is not None else fetch_aisle_analytics()
    aisle_data = analytics.get("aisles", {})

    dwell_values = [
        data["average_dwell_seconds"]
        for data in aisle_data.values()
        if data.get("completed_visits", 0) > 0
    ]
    min_dwell = min(dwell_values) if dwell_values else 0
    max_dwell = max(dwell_values) if dwell_values else 1

    overlay = base_image.copy()

    for aisle_id, region_points in regions.items():
        polygon = np.array(region_points, dtype=np.int32)
        data = aisle_data.get(aisle_id, {})
        avg_dwell = data.get("average_dwell_seconds", 0)
        visits = data.get("completed_visits", 0)

        if visits > 0:
            color = dwell_time_to_color(avg_dwell, min_dwell, max_dwell)
        else:
            color = (200, 200, 200)  # gray = no data yet

        cv2.fillPoly(overlay, [polygon], color)

    result = cv2.addWeighted(overlay, 0.55, base_image, 0.45, 0)

    for aisle_id, region_points in regions.items():
        data = aisle_data.get(aisle_id, {})
        avg_dwell = data.get("average_dwell_seconds", 0)
        visits = data.get("completed_visits", 0)
        inside_now = data.get("people_inside_now", 0)

        centroid_x = int(sum(p[0] for p in region_points) / len(region_points))
        centroid_y = int(sum(p[1] for p in region_points) / len(region_points))

        label = f"{aisle_id}: {avg_dwell}s avg" if visits > 0 else f"{aisle_id}: no data"
        if inside_now > 0:
            label += f" ({inside_now} now)"

        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(
            result,
            (centroid_x - text_w // 2 - 5, centroid_y - text_h - 5),
            (centroid_x + text_w // 2 + 5, centroid_y + 5),
            (255, 255, 255), -1,
        )
        cv2.putText(
            result, label, (centroid_x - text_w // 2, centroid_y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2,
        )

    cv2.imwrite(str(ROOT / output_path), result)
    return str(ROOT / output_path)


if __name__ == "__main__":
    output_file = generate_heatmap()
    print(f"Heatmap written to: {output_file}")