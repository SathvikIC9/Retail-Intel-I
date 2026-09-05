import cv2
import json
import numpy as np

IMAGE_PATH = "image.jpg"
ZONES_FILE = "zones.json"

image = cv2.imread(IMAGE_PATH)

if image is None:
    print(f"ERROR: Could not load {IMAGE_PATH}")
    raise SystemExit

with open(ZONES_FILE, "r") as f:
    zones = json.load(f)


def get_color(zone_name):
    if "cashier" in zone_name:
        return (0, 0, 255)       # red

    if "service" in zone_name:
        return (0, 255, 255)     # yellow

    if "queue" in zone_name:
        return (0, 255, 0)       # green

    return (255, 255, 255)


display = image.copy()

for zone_name, points in zones.items():

    if len(points) < 3:
        print(f"WARNING: {zone_name} has fewer than 3 points")
        continue

    polygon = np.array(points, dtype=np.int32)

    color = get_color(zone_name)

    # Draw polygon
    cv2.polylines(
        display,
        [polygon],
        isClosed=True,
        color=color,
        thickness=2
    )

    # Calculate center for label
    M = cv2.moments(polygon)

    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
    else:
        cx, cy = points[0]

    # Label
    cv2.putText(
        display,
        zone_name,
        (cx, cy),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        color,
        2,
        cv2.LINE_AA
    )


print(f"Loaded {len(zones)} zones")

print("""
ZONE VERIFICATION

RED    = CASHIER
YELLOW = SERVICE
GREEN  = QUEUE

Press Q to quit.
""")

cv2.namedWindow(
    "Zone Verification",
    cv2.WINDOW_NORMAL
)

cv2.imshow(
    "Zone Verification",
    display
)

while True:
    key = cv2.waitKey(0) & 0xFF

    if key == ord("q"):
        break

cv2.destroyAllWindows()