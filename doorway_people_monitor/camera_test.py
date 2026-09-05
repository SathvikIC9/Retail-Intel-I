import cv2

print("Testing cameras...\n")

for camera_id in range(6):
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print(f"Camera {camera_id}: NOT AVAILABLE")
        cap.release()
        continue

    ret, frame = cap.read()

    if ret:
        print(f"Camera {camera_id}: WORKING - {frame.shape}")

        cv2.imshow(f"Camera {camera_id}", frame)
        print(f"  Press any key to close Camera {camera_id}...")
        cv2.waitKey(1000)
        cv2.destroyAllWindows()
    else:
        print(f"Camera {camera_id}: OPENED but could not read frame")

    cap.release()

print("\nDone.")