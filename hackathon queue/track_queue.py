import cv2
import numpy as np

from ultralytics import YOLO

from zone_assigner import (
    load_zones,
    assign_person
)

from state_inferrer import (
    infer_counter_states
)


IMAGE_PATH = "image.jpg"
MODEL_PATH = "yolov8n.pt"


# --------------------------------------------------
# Load zones
# --------------------------------------------------

zones = load_zones("zones.json")

print(f"Loaded {len(zones)} zones")


# --------------------------------------------------
# Load YOLOv8 Nano
# --------------------------------------------------

model = YOLO(MODEL_PATH)


# --------------------------------------------------
# Open image
# --------------------------------------------------

image = cv2.imread(IMAGE_PATH)

if image is None:
    print(f"ERROR: Could not load {IMAGE_PATH}")
    raise SystemExit


# --------------------------------------------------
# Run tracking
# --------------------------------------------------
#
# persist=True is important for video.
# For this single-image test, IDs may not be
# meaningful across separate executions.
#
# ByteTrack is selected with tracker="bytetrack.yaml"
#

results = model.track(
    source=IMAGE_PATH,
    conf=0.25,
    classes=[0],
    tracker="bytetrack.yaml",
    persist=True,
    verbose=False
)


result = results[0]


# --------------------------------------------------
# Check whether tracking IDs exist
# --------------------------------------------------

if result.boxes.id is None:

    print("No tracking IDs found.")

    raise SystemExit


track_ids = (
    result.boxes.id
    .cpu()
    .numpy()
    .astype(int)
)


boxes = (
    result.boxes.xyxy
    .cpu()
    .numpy()
)


confidences = (
    result.boxes.conf
    .cpu()
    .numpy()
)


# --------------------------------------------------
# Build assignments
# --------------------------------------------------

assignments = []


for bbox, confidence, track_id in zip(
    boxes,
    confidences,
    track_ids
):

    x1, y1, x2, y2 = bbox

    bbox = [
        int(x1),
        int(y1),
        int(x2),
        int(y2)
    ]

    assignment = assign_person(
        bbox,
        zones
    )

    assignment["track_id"] = int(track_id)
    assignment["bbox"] = bbox
    assignment["confidence"] = float(confidence)

    assignments.append(
        assignment
    )


# --------------------------------------------------
# Infer counter states
# --------------------------------------------------

counters = infer_counter_states(
    zones,
    assignments
)


# --------------------------------------------------
# Print tracking results
# --------------------------------------------------

print()
print("=" * 70)
print("TRACKED PEOPLE")
print("=" * 70)

for person in assignments:

    print()

    print(
        f"Track ID : "
        f"{person['track_id']}"
    )

    print(
        f"Confidence: "
        f"{person['confidence']:.2f}"
    )

    print(
        f"BBox     : "
        f"{person['bbox']}"
    )

    print(
        f"Contact  : "
        f"{person['contact_point']}"
    )

    print(
        f"Counter  : "
        f"{person['counter_id']}"
    )

    print(
        f"Zone     : "
        f"{person['zone_type']}"
    )

    print(
        f"Role     : "
        f"{person['role']}"
    )


# --------------------------------------------------
# Print counter states
# --------------------------------------------------

print()
print("=" * 70)
print("COUNTER STATES")
print("=" * 70)

for counter_id, counter in counters.items():

    print()

    print(
        f"Counter {counter_id}"
    )

    print(
        f"  Cashier present     : "
        f"{counter['cashier_present']}"
    )

    print(
        f"  Customer in service : "
        f"{counter['customer_in_service']}"
    )

    print(
        f"  Queue count         : "
        f"{counter['queue_count']}"
    )

    print(
        f"  State               : "
        f"{counter['state']}"
    )


# --------------------------------------------------
# Visualization
# --------------------------------------------------

display = image.copy()


def zone_color(zone_type):

    if zone_type == "CASHIER":
        return (0, 0, 255)

    if zone_type == "SERVICE":
        return (0, 255, 255)

    if zone_type == "QUEUE":
        return (0, 255, 0)

    return (255, 255, 255)


# --------------------------------------------------
# Draw zones
# --------------------------------------------------

for zone in zones:

    polygon = np.array(
        zone.points,
        dtype=np.int32
    )

    cv2.polylines(
        display,
        [polygon],
        True,
        zone_color(zone.zone_type),
        2
    )


# --------------------------------------------------
# Draw tracked people
# --------------------------------------------------

for person in assignments:

    x1, y1, x2, y2 = person["bbox"]

    contact_x, contact_y = person[
        "contact_point"
    ]

    contact_x = int(contact_x)
    contact_y = int(contact_y)

    zone_type = person["zone_type"]

    color = zone_color(zone_type)

    # Bounding box
    cv2.rectangle(
        display,
        (x1, y1),
        (x2, y2),
        color,
        2
    )

    # Contact point
    cv2.circle(
        display,
        (contact_x, contact_y),
        6,
        color,
        -1
    )

    # Track ID + assignment
    if person["counter_id"] is None:

        label = (
            f"ID {person['track_id']} "
            f"UNASSIGNED"
        )

    else:

        label = (
            f"ID {person['track_id']} "
            f"C{person['counter_id']} "
            f"{person['zone_type']}"
        )

    cv2.putText(
        display,
        label,
        (x1, max(20, y1 - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        2,
        cv2.LINE_AA
    )


# --------------------------------------------------
# Draw counter summary
# --------------------------------------------------

y = 30

for counter_id, counter in counters.items():

    text = (
        f"C{counter_id}: "
        f"{counter['state']} "
        f"| Queue={counter['queue_count']}"
    )

    cv2.putText(
        display,
        text,
        (20, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    y += 30


# --------------------------------------------------
# Display
# --------------------------------------------------

cv2.namedWindow(
    "Queue Tracking",
    cv2.WINDOW_NORMAL
)

cv2.imshow(
    "Queue Tracking",
    display
)

print()
print("Press Q to quit.")

while True:

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break


cv2.destroyAllWindows()