
import cv2
import yaml
from pathlib import Path

# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

CAMERA_INDEX = 1

CONFIG_FILE = Path("config.yaml")

# Points selected by the user
points = []

# ---------------------------------------------------------
# MOUSE CALLBACK
# ---------------------------------------------------------

def mouse_callback(event, x, y, flags, param):
    global points

    if event == cv2.EVENT_LBUTTONDOWN:

        # Add point
        if len(points) < 8:
            points.append((x, y))
            print(f"Point {len(points)}: ({x}, {y})")

    elif event == cv2.EVENT_RBUTTONDOWN:

        # Remove last point
        if points:
            removed = points.pop()
            print(f"Removed point: {removed}")


# ---------------------------------------------------------
# CAMERA
# ---------------------------------------------------------

cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

if not cap.isOpened():
    print(f"ERROR: Could not open camera {CAMERA_INDEX}")
    print("Try changing CAMERA_INDEX at the top of this file.")
    exit()

# Try to match the resolution used by the main application
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

window_name = "Door Calibration"

cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, mouse_callback)

print()
print("========================================")
print("        DOOR CALIBRATION TOOL")
print("========================================")
print()
print("LEFT CLICK  = add point")
print("RIGHT CLICK = remove last point")
print()
print("Click the corners/outline of the ACTUAL")
print("doorway that leads to the area the camera")
print("cannot see.")
print()
print("Recommended order:")
print()
print("1 -> top-left")
print("2 -> top-right")
print("3 -> bottom-right")
print("4 -> bottom-left")
print()
print("Press ENTER when finished.")
print("Press R to reset.")
print("Press Q to quit.")
print()

# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------

while True:

    ret, frame = cap.read()

    if not ret:
        print("ERROR: Could not read camera frame.")
        break

    display = frame.copy()

    # -----------------------------------------------------
    # DRAW SELECTED POINTS
    # -----------------------------------------------------

    for i, point in enumerate(points):

        cv2.circle(
            display,
            point,
            7,
            (0, 0, 255),
            -1
        )

        cv2.putText(
            display,
            str(i + 1),
            (point[0] + 10, point[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

    # -----------------------------------------------------
    # DRAW POLYGON
    # -----------------------------------------------------

    if len(points) >= 2:

        for i in range(len(points) - 1):

            cv2.line(
                display,
                points[i],
                points[i + 1],
                (255, 180, 0),
                2
            )

    if len(points) >= 3:

        # Draw filled transparent polygon
        overlay = display.copy()

        cv2.fillPoly(
            overlay,
            [__import__("numpy").array(points)],
            (255, 180, 0)
        )

        display = cv2.addWeighted(
            overlay,
            0.20,
            display,
            0.80,
            0
        )

        # Redraw polygon outline
        for i in range(len(points)):

            cv2.line(
                display,
                points[i],
                points[(i + 1) % len(points)],
                (255, 180, 0),
                3
            )

    # -----------------------------------------------------
    # INSTRUCTIONS
    # -----------------------------------------------------

    cv2.rectangle(
        display,
        (10, 10),
        (500, 105),
        (0, 0, 0),
        -1
    )

    cv2.putText(
        display,
        "DOOR CALIBRATION",
        (25, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    cv2.putText(
        display,
        "Left click: add | Right click: undo",
        (25, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1
    )

    cv2.putText(
        display,
        "ENTER: save | R: reset | Q: quit",
        (25, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1
    )

    cv2.imshow(window_name, display)

    key = cv2.waitKey(1) & 0xFF

    # -----------------------------------------------------
    # RESET
    # -----------------------------------------------------

    if key == ord("r"):

        points.clear()

        print("Points reset.")

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    elif key == 13:  # ENTER

        if len(points) < 3:

            print()
            print("ERROR: Select at least 3 points.")
            print()

            continue

        # Load existing config
        if CONFIG_FILE.exists():

            with open(CONFIG_FILE, "r") as f:
                config = yaml.safe_load(f) or {}

        else:

            config = {}

        # Create portal section
        config["portal"] = {
            "polygon": [list(point) for point in points]
        }

        # Save
        with open(CONFIG_FILE, "w") as f:

            yaml.safe_dump(
                config,
                f,
                sort_keys=False
            )

        print()
        print("========================================")
        print("DOOR PORTAL SAVED")
        print("========================================")

        for i, point in enumerate(points):

            print(
                f"Point {i + 1}: "
                f"x={point[0]}, y={point[1]}"
            )

        print()
        print(f"Saved to: {CONFIG_FILE}")
        print()

        break

    # -----------------------------------------------------
    # QUIT
    # -----------------------------------------------------

    elif key == ord("q"):

        print("Calibration cancelled.")
        break


cap.release()
cv2.destroyAllWindows()