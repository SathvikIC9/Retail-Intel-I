import cv2
import numpy as np
from ultralytics import YOLO

from zone_assigner import load_zones, assign_person
from state_inferrer import infer_counter_states
from person_tracker import PersonTracker
from queue_tracker import QueueTracker


# ==================================================
# CONFIG
# ==================================================

MODEL_PATH = "yolov8n.pt"

FRAME_PATHS = [
    "frame1.jpg",
    "frame2.jpg",
    "frame3.jpg",
]

CONFIDENCE = 0.25


# ==================================================
# LOAD MODEL + ZONES + PERSON TRACKER
# ==================================================

model = YOLO(MODEL_PATH)

zones = load_zones("zones.json")

print(f"Loaded {len(zones)} zones")

# IMPORTANT:
# Create this ONCE, outside the frame loop.
# This allows the tracker to maintain history.
tracker = PersonTracker(
    history_size=5
    
)
queue_tracker = QueueTracker()


# ==================================================
# ZONE COLORS
# ==================================================

def zone_color(zone_type):

    if zone_type == "CASHIER":
        return (0, 0, 255)

    if zone_type == "SERVICE":
        return (0, 255, 255)

    if zone_type == "QUEUE":
        return (0, 255, 0)

    return (255, 255, 255)


# ==================================================
# PROCESS FRAMES SEQUENTIALLY
# ==================================================

for frame_number, frame_path in enumerate(
    FRAME_PATHS,
    start=1
):

    print()
    print("=" * 70)
    print(f"FRAME {frame_number}: {frame_path}")
    print("=" * 70)


    # ------------------------------------------------
    # Load image
    # ------------------------------------------------

    image = cv2.imread(frame_path)

    if image is None:

        print(
            f"ERROR: Could not load {frame_path}"
        )

        continue


    # ------------------------------------------------
    # YOLOv8n + ByteTrack
    # ------------------------------------------------
    #
    # persist=True keeps the tracker state alive
    # between frames.
    #
    # classes=[0] means PERSON only.
    #

    results = model.track(
        image,
        conf=CONFIDENCE,
        classes=[0],
        tracker="bytetrack.yaml",
        persist=True,
        verbose=False
    )

    result = results[0]


    # ------------------------------------------------
    # Check for detections
    # ------------------------------------------------

    if (
        result.boxes is None
        or len(result.boxes) == 0
    ):

        print("No people detected.")

        cv2.imshow(
            "Multi Frame Tracking",
            image
        )

        key = cv2.waitKey(1000) & 0xFF

        if key == ord("q"):
            break

        continue


    # ------------------------------------------------
    # Bounding boxes
    # ------------------------------------------------

    boxes = (
        result.boxes.xyxy
        .cpu()
        .numpy()
    )


    # ------------------------------------------------
    # Detection confidence
    # ------------------------------------------------

    confidences = (
        result.boxes.conf
        .cpu()
        .numpy()
    )


    # ------------------------------------------------
    # Tracking IDs
    # ------------------------------------------------

    if result.boxes.id is not None:

        track_ids = (
            result.boxes.id
            .cpu()
            .numpy()
            .astype(int)
        )

    else:

        track_ids = [
            -1
        ] * len(boxes)


    # =================================================
    # ASSIGN DETECTIONS TO ZONES
    # =================================================

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


        # ---------------------------------------------
        # Existing geometry pipeline
        # ---------------------------------------------

        assignment = assign_person(
            bbox,
            zones
        )


        # ---------------------------------------------
        # Add tracking information
        # ---------------------------------------------

        assignment["track_id"] = int(
            track_id
        )

        assignment["bbox"] = bbox

        assignment["confidence"] = float(
            confidence
        )


        assignments.append(
            assignment
        )


    # =================================================
    # TEMPORAL SMOOTHING
    # =================================================

    smoothed_assignments = tracker.update(
        assignments
    )

    # -----------------------------------------------
    # Queue/person state tracking
    # -----------------------------------------------

    queue_tracker.update(
        smoothed_assignments,
        frame_number
    )


    # =================================================
    # COUNTER STATE INFERENCE
    # =================================================

    counters = infer_counter_states(
        zones,
        smoothed_assignments
    )


    # =================================================
    # PRINT PERSON RESULTS
    # =================================================

    print()

    print(
        "TRACKED PEOPLE:"
    )

    for person in smoothed_assignments:

        track_id = person["track_id"]

        counter_id = person["counter_id"]

        zone_type = person["zone_type"]

        role = person["role"]

        confidence = person["confidence"]


        # ---------------------------------------------
        # Handle unassigned people safely
        # ---------------------------------------------

        if counter_id is None:

            counter_text = "UNASSIGNED"

        else:

            counter_text = f"C{counter_id}"


        if zone_type is None:

            zone_text = "NONE"

        else:

            zone_text = zone_type


        if role is None:

            role_text = "NONE"

        else:

            role_text = role


        print(
            f"ID {track_id:>3} | "
            f"{counter_text:<10} | "
            f"{zone_text:<7} | "
            f"{role_text:<10} | "
            f"conf={confidence:.2f}"
        )


    # =================================================
    # PRINT COUNTER STATES
    # =================================================

    print()

    print(
        "COUNTERS:"
    )


    for counter_id, counter in counters.items():

        print(
            f"  C{counter_id}: "
            f"{counter['state']:<6} | "
            f"Queue={counter['queue_count']}"
        )

    print()
    print("PERSON STATES:")

    for track_id, person in queue_tracker.get_people().items():

        print(
            f"  ID {track_id}: "
            f"{person['state']:<8} | "
            f"C{person['counter_id']} | "
            f"Zone={person['current_zone']} | "
            f"Wait={person['wait_frames']} frames"
        )


    print()

    average_wait = queue_tracker.get_average_wait()

    print(
        f"Completed average wait: "
        f"{average_wait:.1f} frames"
    )


    # =================================================
    # VISUALIZATION
    # =================================================

    display = image.copy()


    # ------------------------------------------------
    # Draw calibrated zones
    # ------------------------------------------------

    for zone in zones:

        polygon = np.array(
            zone.points,
            dtype=np.int32
        )

        cv2.polylines(
            display,
            [polygon],
            True,
            zone_color(
                zone.zone_type
            ),
            2
        )


    # ------------------------------------------------
    # Draw tracked people
    # ------------------------------------------------

    for person in smoothed_assignments:

        x1, y1, x2, y2 = person["bbox"]

        track_id = person["track_id"]

        zone_type = person["zone_type"]

        counter_id = person["counter_id"]

        contact_x, contact_y = person[
            "contact_point"
        ]


        # ---------------------------------------------
        # Color
        # ---------------------------------------------

        color = zone_color(
            zone_type
        )


        # ---------------------------------------------
        # Bounding box
        # ---------------------------------------------

        cv2.rectangle(
            display,
            (x1, y1),
            (x2, y2),
            color,
            2
        )


        # ---------------------------------------------
        # Contact point
        # ---------------------------------------------

        cv2.circle(
            display,
            (
                int(contact_x),
                int(contact_y)
            ),
            6,
            color,
            -1
        )


        # ---------------------------------------------
        # Label
        # ---------------------------------------------

        if counter_id is None:

            label = (
                f"ID {track_id} "
                f"UNASSIGNED"
            )

        else:

            label = (
                f"ID {track_id} "
                f"C{counter_id} "
                f"{zone_type}"
            )


        cv2.putText(
            display,
            label,
            (
                x1,
                max(
                    20,
                    y1 - 8
                )
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA
        )


    # =================================================
    # COUNTER SUMMARY ON IMAGE
    # =================================================

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
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )


        y += 30


    # =================================================
    # FRAME NUMBER
    # =================================================

    cv2.putText(
        display,
        f"FRAME {frame_number}",
        (15, y + 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )


    # =================================================
    # DISPLAY
    # =================================================

    cv2.namedWindow(
        "Multi Frame Tracking",
        cv2.WINDOW_NORMAL
    )

    cv2.imshow(
        "Multi Frame Tracking",
        display
    )


    # ------------------------------------------------
    # Wait 1 second
    # ------------------------------------------------

    key = cv2.waitKey(1000) & 0xFF


    if key == ord("q"):
        break


# ==================================================
# CLEANUP
# ==================================================

cv2.destroyAllWindows()