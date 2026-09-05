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
# Load image
# --------------------------------------------------

image = cv2.imread(IMAGE_PATH)

if image is None:
    print(f"ERROR: Could not load {IMAGE_PATH}")
    raise SystemExit


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
# Run detection
# --------------------------------------------------

results = model(
    IMAGE_PATH,
    conf=0.25,
    classes=[0],
    verbose=False
)

result = results[0]


# --------------------------------------------------
# Extract person detections
# --------------------------------------------------

detections = []

for box in result.boxes:

    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

    confidence = float(
        box.conf[0]
    )

    bbox = [
        int(x1),
        int(y1),
        int(x2),
        int(y2)
    ]

    detections.append({
        "bbox": bbox,
        "confidence": confidence
    })


print(
    f"Detected {len(detections)} people"
)


# --------------------------------------------------
# Assign people to zones
# --------------------------------------------------

assignments = []

for detection in detections:

    bbox = detection["bbox"]

    assignment = assign_person(
        bbox,
        zones
    )

    assignment["bbox"] = bbox
    assignment["confidence"] = detection["confidence"]

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
# Print person assignments
# --------------------------------------------------

print()
print("=" * 70)
print("PERSON ASSIGNMENTS")
print("=" * 70)

for i, person in enumerate(
    assignments,
    start=1
):

    print()

    print(
        f"Person {i}"
    )

    print(
        f"  BBox       : "
        f"{person['bbox']}"
    )

    print(
        f"  Confidence : "
        f"{person['confidence']:.2f}"
    )

    print(
        f"  Contact    : "
        f"{person['contact_point']}"
    )

    print(
        f"  Counter    : "
        f"{person['counter_id']}"
    )

    print(
        f"  Zone       : "
        f"{person['zone_type']}"
    )

    print(
        f"  Role       : "
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
# Draw calibrated zones
# --------------------------------------------------

for zone in zones:

    polygon = np.array(
        zone.points,
        dtype=np.int32
    )

    color = zone_color(
        zone.zone_type
    )

    cv2.polylines(
        display,
        [polygon],
        True,
        color,
        2
    )


# --------------------------------------------------
# Draw detected people
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

    # Label
    if person["counter_id"] is None:

        label = "UNASSIGNED"

    else:

        label = (
            f"C{person['counter_id']} "
            f"{person['zone_type']} "
            f"{person['confidence']:.2f}"
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
# Draw counter state summary
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
    "Queue Detection",
    cv2.WINDOW_NORMAL
)

cv2.imshow(
    "Queue Detection",
    display
)

print()
print("Press Q to quit.")

while True:

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break


cv2.destroyAllWindows()