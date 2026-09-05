import cv2
import json
import numpy as np

IMAGE_PATH = "image.jpg"
OUTPUT_FILE = "zones.json"

image = cv2.imread(IMAGE_PATH)

if image is None:
    print(f"ERROR: Could not load {IMAGE_PATH}")
    raise SystemExit

zones = {}
points = []

current_zone_name = "counter_1_cashier"

ZONE_COLORS = {
    "cashier": (0, 0, 255),      # red
    "service": (0, 255, 255),    # yellow
    "queue": (0, 255, 0),        # green
}


def get_zone_color(zone_name):
    if "cashier" in zone_name:
        return ZONE_COLORS["cashier"]

    if "service" in zone_name:
        return ZONE_COLORS["service"]

    if "queue" in zone_name:
        return ZONE_COLORS["queue"]

    return (255, 255, 255)


def redraw():
    display = image.copy()

    # Draw all saved zones
    for zone_name, zone_points in zones.items():
        if len(zone_points) < 3:
            continue

        color = get_zone_color(zone_name)

        polygon = np.array(zone_points, dtype=np.int32)

        cv2.polylines(
            display,
            [polygon],
            isClosed=True,
            color=color,
            thickness=2
        )

        # Put zone name near first vertex
        x, y = zone_points[0]

        cv2.putText(
            display,
            zone_name,
            (x, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA
        )

    # Draw current polygon being edited
    color = get_zone_color(current_zone_name)

    for point in points:
        cv2.circle(
            display,
            tuple(point),
            5,
            color,
            -1
        )

    if len(points) > 1:
        for i in range(len(points) - 1):
            cv2.line(
                display,
                tuple(points[i]),
                tuple(points[i + 1]),
                color,
                2
            )

    cv2.putText(
        display,
        f"Drawing: {current_zone_name}",
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    return display


def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:

        points.append([x, y])

        print(f"Point added: ({x}, {y})")


cv2.namedWindow(
    "Zone Calibration",
    cv2.WINDOW_NORMAL
)

cv2.setMouseCallback(
    "Zone Calibration",
    mouse_callback
)

print("""
ZONE CALIBRATION TOOL
---------------------

Left Click : Add polygon point

ENTER      : Finish/save current zone
N          : Enter next zone name
C          : Clear current polygon
U          : Undo last point
D          : Delete current saved zone
S          : Save zones.json
Q          : Quit

Recommended naming:

counter_1_cashier
counter_1_service
counter_1_queue
...
""")

while True:

    display = redraw()

    cv2.imshow(
        "Zone Calibration",
        display
    )

    key = cv2.waitKey(30) & 0xFF

    # New zone
    if key == ord("n"):

        zone_name = input(
            "Enter zone name: "
        ).strip()

        if zone_name:
            current_zone_name = zone_name
            points.clear()

            print(
                f"Now drawing: {current_zone_name}"
            )

    # Finish polygon
    elif key == 13:

        if len(points) >= 3:

            zones[current_zone_name] = points.copy()

            print(
                f"Saved {current_zone_name} "
                f"with {len(points)} points"
            )

            points.clear()

        else:
            print(
                "Need at least 3 points!"
            )

    # Clear current points
    elif key == ord("c"):

        points.clear()

        print(
            "Current polygon cleared."
        )

    # Undo last point
    elif key == ord("u"):

        if points:
            removed = points.pop()

            print(
                f"Removed point: {removed}"
            )

    # Delete saved zone
    elif key == ord("d"):

        if current_zone_name in zones:

            del zones[current_zone_name]

            print(
                f"Deleted saved zone: "
                f"{current_zone_name}"
            )

        points.clear()

    # Save JSON
    elif key == ord("s"):

        with open(
            OUTPUT_FILE,
            "w"
        ) as f:

            json.dump(
                zones,
                f,
                indent=4
            )

        print(
            f"Saved {len(zones)} zones "
            f"to {OUTPUT_FILE}"
        )

    # Quit
    elif key == ord("q"):
        break


cv2.destroyAllWindows()