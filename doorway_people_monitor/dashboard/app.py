from flask import Flask, jsonify, render_template
from pathlib import Path
import csv
from datetime import datetime

# =========================================================
# PATHS
# =========================================================

ROOT = Path(__file__).resolve().parents[1]

CSV_PATH = ROOT / "data" / "people_events.csv"


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


# =========================================================
# READ CSV
# =========================================================

def read_events():

    events = []

    if not CSV_PATH.exists():
        return events

    try:

        with CSV_PATH.open(
            "r",
            newline="",
            encoding="utf-8"
        ) as f:

            reader = csv.DictReader(f)

            for row in reader:

                if not row:
                    continue

                events.append(row)

    except Exception as e:

        print("CSV ERROR:", e)

    return events


# =========================================================
# CALCULATE STATISTICS
# =========================================================

def calculate_stats(events):

    total_in = 0
    total_out = 0

    for event in events:

        direction = event.get(
            "direction",
            ""
        ).upper()

        if direction == "IN":
            total_in += 1

        elif direction == "OUT":
            total_out += 1

    people_inside = max(
        0,
        total_in - total_out
    )

    return {
        "people_inside": people_inside,
        "total_in": total_in,
        "total_out": total_out,
        "total_events": len(events)
    }


# =========================================================
# DASHBOARD PAGE
# =========================================================

@app.route("/")
def dashboard():

    return render_template(
        "index.html"
    )


# =========================================================
# API: CURRENT DATA
# =========================================================

@app.route("/api/data")
def api_data():

    events = read_events()

    stats = calculate_stats(
        events
    )

    # -----------------------------------------------------
    # Recent events
    # -----------------------------------------------------

    recent_events = events[-20:]

    recent_events.reverse()


    # -----------------------------------------------------
    # Hourly statistics
    # -----------------------------------------------------

    hourly = {}

    for event in events:

        timestamp = event.get(
            "timestamp",
            ""
        )

        direction = event.get(
            "direction",
            ""
        ).upper()

        try:

            dt = datetime.fromisoformat(
                timestamp
            )

            hour = dt.strftime(
                "%H:00"
            )

        except Exception:

            continue


        if hour not in hourly:

            hourly[hour] = {
                "in": 0,
                "out": 0
            }


        if direction == "IN":

            hourly[hour]["in"] += 1

        elif direction == "OUT":

            hourly[hour]["out"] += 1


    return jsonify({

        "stats": stats,

        "recent_events": recent_events,

        "hourly": hourly

    })


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    print()
    print("==========================================")
    print("      DOORWAY MONITOR DASHBOARD")
    print("==========================================")
    print()
    print("CSV:", CSV_PATH)
    print()
    print("Open:")
    print("http://127.0.0.1:5000")
    print()
    print("Press CTRL+C to stop.")
    print()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )