# Doorway People Monitor

Laptop-first, Arduino UNO Q-ready people entry/exit prototype.

## Current pipeline

Camera -> OpenCV -> YOLOv8 Nano -> ByteTrack -> Door Portal State Machine -> CSV

This first version deliberately does NOT use a simple counting line.

## 1. Create/activate your virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you already have the virtual environment from the previous `test_frames` project, you can use that environment instead.

## 2. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Run

```powershell
python app/main.py
```

On the first run, Ultralytics downloads `yolov8n.pt`.

## 4. Camera source

`config.yaml` contains:

```yaml
camera:
  source: 0
```

If your camera is another device, change `source` to `1`, `2`, etc.

## 5. Door portal calibration

The current portal coordinates are only an initial estimate for the supplied camera view:

```yaml
portal:
  x1: 330
  y1: 70
  x2: 535
  y2: 365
```

We will calibrate these after seeing the live window.

## Important behavior

OUT:
- person is already tracked
- approaches the door portal
- enters the portal region
- disappears
- remains absent for the confirmation timeout

IN:
- a new person appears at the portal
- tracker establishes the person
- person moves away from the portal into the room
- event is confirmed

Sideways movement away from the doorway should not count as OUT.

## Next modules

1. Persistent person identity / re-identification
2. SQLite database
3. Dashboard API
4. Live dashboard
5. Heatmap
6. 3D analytics
7. UNO Q deployment
