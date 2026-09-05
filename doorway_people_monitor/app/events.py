import csv
from datetime import datetime
from pathlib import Path


class EventLogger:

    def __init__(self, csv_path):

        self.csv_path = Path(csv_path)

        self.csv_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.event_counter = 0

        self.initialize()

    def initialize(self):

        if not self.csv_path.exists():

            with open(
                self.csv_path,
                "w",
                newline="",
                encoding="utf-8"
            ) as f:

                writer = csv.writer(f)

                writer.writerow([
                    "event_id",
                    "person_id",
                    "track_id",
                    "timestamp",
                    "direction",
                    "confidence"
                ])

    def log(
        self,
        person_id,
        track_id,
        direction,
        confidence
    ):

        self.event_counter += 1

        timestamp = datetime.now().isoformat(
            timespec="seconds"
        )

        row = [
            self.event_counter,
            person_id,
            track_id,
            timestamp,
            direction,
            round(float(confidence), 3)
        ]

        with open(
            self.csv_path,
            "a",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.writer(f)
            writer.writerow(row)

        print(
            f"[EVENT] "
            f"{person_id} "
            f"(track {track_id}) "
            f"-> {direction}"
        )