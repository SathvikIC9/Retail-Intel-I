# Smart Retail Intelligence System

A simple project that watches a store using cameras + AI, and shows everything live on a small screen (Arduino App Lab) and a dashboard.

Think of it like this: **the laptop does the "seeing"** (using cameras and AI), and **the Arduino board does the "showing"** (a tiny screen that asks the laptop "what did you see?" and displays it nicely).

---

##  Built With

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=for-the-badge&logo=flask&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Ultralytics YOLOv8](https://img.shields.io/badge/YOLOv8-Object%20Detection-00FFFF?style=for-the-badge&logo=yolo&logoColor=black)
![NumPy](https://img.shields.io/badge/NumPy-Data-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-Data-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-Charts-11557C?style=for-the-badge&logo=plotly&logoColor=white)
![Arduino](https://img.shields.io/badge/Arduino-App%20Lab-00979D?style=for-the-badge&logo=arduino&logoColor=white)
![HTML/CSS/JS](https://img.shields.io/badge/HTML%2FCSS%2FJS-Dashboard-E34F26?style=for-the-badge&logo=html5&logoColor=white)

---

##  How the Arduino and Laptop Talk to Each Other

Imagine the laptop and the Arduino board are two friends standing in the same room (connected to the **same Wi-Fi**). Each friend has their own "address" (an **IP address**) .

- The **laptop** does all the heavy thinking. It watches the camera feeds, runs AI (YOLOv8) to detect people, and figures out things like "how many people are at the door" or "is the queue too long."
- The **laptop shares this info over the Wi-Fi network**  nobody outside the network can see it, so the data stays safe and private.
- The **Arduino board** (running a small Python app called App Lab) simply **asks the laptop** for this info every few seconds using the laptop's IP address, and then shows it on its own little screen/dashboard.

So it's basically:

```
Cameras →  Laptop (AI thinking) →  Same Wi-Fi →  Arduino Board (shows the result)
```

No data ever leaves your Wi-Fi network — everything stays local and safe.

>  Before running anything, open `App_Lab/python/main.py` and change this line to match **your laptop's actual IP address**:
> ```python
> LAPTOP_IP = "192.XX.X.XX"   # <-- change this
> ```

---

##  Project Structure

The project has two homes: files for the **laptop (PC)** and files for the **Arduino App Lab**.

```
 Project Root
│
├── Server_Files/              ←  These run on your LAPTOP (the "brains")
│   │
│   ├──  Doorway_Footfall/      
│   │   ├── laptop_doorway_service.py  ← Counts people walking in/out of the door
│   │   ├── caliberate_from_video.py   ← Sets the boundaries
│   │   ├── configure.json
│   │   ├── yolov8n.pt
│   │   ├── people.mp4
│   │   └── requirements.txt
│   │
│   ├──  Queue_Management/      ← Watches the checkout queue and its length
│   │   ├── queue_dashboard_app.py
│   │   ├── caliberate_queue_lines.py
│   │   ├── caliberate_alert_zones.py
│   │   ├── person_tracker.py
│   │   ├── queue_tracker.py
│   │   ├── state_inferrer.py
│   │   ├── zone_assigner.py
│   │   ├── alert_lines.json
│   │   ├── zones.json
│   │   ├── yolov8n.pt
│   │   ├── q2.mp4
│   │   └── requirements.txt
│   │
│   └──  Aisle_intelligence/    ← Tracks how long people dwell in each aisle
│       ├── aisle_dwell_service.py
│       ├── aisle_zones.json
│       ├── caliberate_aisle.py
│       ├── caliberate_aisle_zones.py
│       ├── floor_map_plan.json
│       ├── generate_heatmap.py
│       ├── Project 8.mp4
│       ├── yolov8n.pt
│       └── requirements.txt
│
└──  App_Lab/                   ←  These go to your ARDUINO board (the "face")
    ├──  python/
    ├── inventory_manager.py
    ├── inventory_synced.csv
    ├── main.py
    ├── requirements.txt
    ├── static/
    │   ├── aisle_analytics.js
    │   ├── alerts.js
    │   ├── analytics.js
    │   ├── app.js
    │   ├── chartjs/
    │   │   ├── chart.umd.min.js
    │   │   └── chartjs-plugin-datalabels.min.js
    │   ├── fontawsome/
    │   │   ├── css/
    │   │   │   └── all.min.css
    │   │   └── webfonts/
    │   │       ├── fa-brands-400.woff2
    │   │       ├── fa-regular-400.woff2
    │   │       ├── fa-solid-900.woff2
    │   │       └── fa-v4compatibility.woff2
    │   └── fonts/
    │       ├── PlusJakartaSans-Bold.ttf
    │       ├── PlusJakartaSans-BoldItalic.ttf
    │       ├── PlusJakartaSans-ExtraBold.ttf
    │       ├── PlusJakartaSans-ExtraBoldItalic.ttf
    │       ├── PlusJakartaSans-ExtraLight.ttf
    │       └── PlusJakartaSans-ExtraLightItalic.ttf
    └──  sketch/                ← The tiny animation shown on the LED matrix
        ├──sketch.yaml
        └── sketch.ino
```

**Simple rule to remember:**
- Everything inside `Server_Files/` → stays and runs on your **laptop/PC**.
- Everything inside `App_Lab/` → gets uploaded/deployed to the **Arduino App Lab**.

---

##  How to Run It

Each folder has its own `requirements.txt` — this is just a shopping list of Python libraries that the program needs. Install it with:

```bash
pip install -r requirements.txt
```

### Step 1 — Run each service in its own terminal (on the laptop)

Open **3 separate terminals**, one for each folder, and run:

| Terminal | Folder | File to Run |
|---|---|---|
| 1. | `Server_Files/Aisle_intelligence` | `python aisle_dwell_service.py` |
| 2. | `Server_Files/Doorway_Footfall` | `python laptop_doorway_service.py` |
| 3. | `Server_Files/Queue_Management` | `python queue_dashboard_app.py` |

Each one keeps running in the background, quietly watching its own camera feed and serving the results over Wi-Fi.

### Step 2 — Deploy the App Lab files to the Arduino

Upload everything inside `App_Lab/` to your Arduino App Lab. It will connect to your laptop (using the IP address you set earlier) and pull in the live data from all 3 services to show on its screen.

---

##  What Each Part Actually Does 

- **Doorway Footfall**  — Counts how many people come in and go out.
- **Queue Management**  — Watches the checkout line and tells you if it's getting too long.
- **Aisle Intelligence**  — Sees which aisles people spend the most time in (like a little heatmap).
- **App Lab (Arduino)**  — The friendly face of the project. Doesn't do any AI itself — just asks the laptop "what's happening?" and shows it.

That's it! Cameras see → laptop thinks → Arduino shows. Simple as that. 
