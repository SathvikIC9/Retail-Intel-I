import cv2
import json
import numpy as np

from zone_assigner import load_zones, point_in_zone


IMAGE_PATH = "image.jpg"
ZONES_FILE = "zones.json"


# --------------------------------------------------
# Load image
# --------------------------------------------------

image = cv2.imread(IMAGE_PATH)

if image is None:
    print(f"ERROR: Could not load {IMAGE_PATH}")
    raise SystemExit


# --------------------------------------------------
# Load zones
# --------------------------------------------------

zones = load_zones(ZONES_FILE)

print(f"Loaded {len(zones)} zones")


# --------------------------------------------------
# Helper: zone colors
# --------------------------------------------------

def get_color(zone_type):

    if zone_type == "CASHIER":
        return (0, 0, 255)       # Red

    if zone_type == "SERVICE":
        return (0, 255, 255)     # Yellow

    if zone_type == "QUEUE":
        return (0, 255, 0)       # Green

    return (255, 255, 255)


# --------------------------------------------------
# Draw calibrated zones
# --------------------------------------------------

def draw_zones():

    display = image.copy()

    for zone in zones:

        polygon = np.array(
            zone.points,
            dtype=np.int32
        )

        color = get_color(
            zone.zone_type
        )

        cv2.polylines(
            display,
            [polygon],
            True,
            color,
            2
        )

        # Calculate polygon center
        cx = int(
            sum(p[0] for p in zone.points)
            / len(zone.points)
        )

        cy = int(
            sum(p[1] for p in zone.points)
            / len(zone.points)
        )

        cv2.putText(
            display,
            zone.name,
            (cx, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            2,
            cv2.LINE_AA
        )

    return display


# --------------------------------------------------
# Find which zones contain a point
# --------------------------------------------------

def find_zones(x, y):

    memberships = []

    point = (x, y)

    for zone in zones:

        if point_in_zone(point, zone):

            memberships.append(zone)

    return memberships


# --------------------------------------------------
# Mouse callback
# --------------------------------------------------

def mouse_callback(event, x, y, flags, param):

    global display

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    print()
    print("=" * 60)

    print(
        f"Clicked point: ({x}, {y})"
    )

    memberships = find_zones(x, y)

    # ----------------------------------------------
    # No zone
    # ----------------------------------------------

    if not memberships:

        print("ZONE: UNASSIGNED")
        print("ROLE: UNASSIGNED")

        cv2.circle(
            display,
            (x, y),
            7,
            (255, 255, 255),
            -1
        )

        cv2.putText(
            display,
            "UNASSIGNED",
            (x + 10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        cv2.imshow(
            "Click Zone Test",
            display
        )

        return

    # ----------------------------------------------
    # Show all memberships
    # ----------------------------------------------

    print("Memberships:")

    for zone in memberships:

        print(
            f"  - {zone.name}"
        )

    # ----------------------------------------------
    # Resolve assignment
    # ----------------------------------------------

    priority = {
        "CASHIER": 1,
        "SERVICE": 2,
        "QUEUE": 3
    }

    selected = min(
        memberships,
        key=lambda z: priority[z.zone_type]
    )

    # ----------------------------------------------
    # Determine role
    # ----------------------------------------------

    if selected.zone_type == "CASHIER":
        role = "CASHIER"
    else:
        role = "CUSTOMER"

    print()
    print(
        f"ASSIGNMENT: {selected.name}"
    )

    print(
        f"COUNTER: {selected.counter_id}"
    )

    print(
        f"ZONE TYPE: {selected.zone_type}"
    )

    print(
        f"ROLE: {role}"
    )

    if len(memberships) > 1:

        print(
            "AMBIGUITY: True"
        )

    else:

        print(
            "AMBIGUITY: False"
        )

    print("=" * 60)

    # ----------------------------------------------
    # Draw clicked point
    # ----------------------------------------------

    display = draw_zones()

    cv2.circle(
        display,
        (x, y),
        8,
        (255, 0, 255),
        -1
    )

    # ----------------------------------------------
    # Draw assignment text
    # ----------------------------------------------

    text = (
        f"{selected.name} | {role}"
    )

    cv2.putText(
        display,
        text,
        (x + 10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 0, 255),
        2,
        cv2.LINE_AA
    )

    cv2.imshow(
        "Click Zone Test",
        display
    )


# --------------------------------------------------
# Main
# --------------------------------------------------

display = draw_zones()

cv2.namedWindow(
    "Click Zone Test",
    cv2.WINDOW_NORMAL
)

cv2.setMouseCallback(
    "Click Zone Test",
    mouse_callback
)

print("""
CLICK ZONE TEST
---------------

Click anywhere on the image.

The program will tell you:

- Which zone contains the point
- Which counter it belongs to
- Whether it is CASHIER / CUSTOMER
- Whether multiple zones contain it

COLORS:

RED    = CASHIER
YELLOW = SERVICE
GREEN  = QUEUE
PURPLE = CLICKED POINT

Press Q to quit.
""")

cv2.imshow(
    "Click Zone Test",
    display
)

while True:

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

cv2.destroyAllWindows()