import json
from pathlib import Path

import cv2
import numpy as np


class IdentityManager:

    def __init__(
        self,
        storage_path,
        match_threshold=0.78,
        appearance_history=5
    ):
        self.storage_path = Path(storage_path)
        self.match_threshold = match_threshold
        self.appearance_history = appearance_history

        self.identities = {}

        self.load()

    # ---------------------------------------------------------
    # LOAD / SAVE
    # ---------------------------------------------------------

    def load(self):

        if not self.storage_path.exists():
            self.identities = {}
            return

        try:

            with open(
                self.storage_path,
                "r",
                encoding="utf-8"
            ) as f:

                self.identities = json.load(f)

        except Exception:

            self.identities = {}

    def save(self):

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            self.storage_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.identities,
                f,
                indent=2
            )

    # ---------------------------------------------------------
    # CREATE NEW PERSON ID
    # ---------------------------------------------------------

    def create_person(self, descriptor):

        numbers = []

        for person_id in self.identities:

            if person_id.startswith("P"):

                try:
                    numbers.append(
                        int(person_id[1:])
                    )
                except ValueError:
                    pass

        next_number = (
            max(numbers)
            if numbers
            else 0
        ) + 1

        person_id = f"P{next_number:03d}"

        self.identities[person_id] = {

            "appearances": [],

            "entries": 0,

            "exits": 0

        }

        if descriptor is not None:

            self.identities[person_id][
                "appearances"
            ].append(
                descriptor.tolist()
            )

        self.save()

        return person_id

    # ---------------------------------------------------------
    # ADD APPEARANCE
    # ---------------------------------------------------------

    def update_appearance(
        self,
        person_id,
        descriptor
    ):

        if descriptor is None:
            return

        if person_id not in self.identities:
            return

        appearances = self.identities[
            person_id
        ].setdefault(
            "appearances",
            []
        )

        appearances.append(
            descriptor.tolist()
        )

        appearances = appearances[
            -self.appearance_history:
        ]

        self.identities[
            person_id
        ]["appearances"] = appearances

        self.save()

    # ---------------------------------------------------------
    # APPEARANCE MATCH
    # ---------------------------------------------------------

    def match(self, descriptor):

        if descriptor is None:
            return None, 0.0

        best_person = None
        best_score = -1.0

        for person_id, data in self.identities.items():

            appearances = data.get(
                "appearances",
                []
            )

            for appearance in appearances:

                old_descriptor = np.asarray(
                    appearance,
                    dtype=np.float32
                )

                score = self.similarity(
                    descriptor,
                    old_descriptor
                )

                if score > best_score:

                    best_score = score
                    best_person = person_id

        if (
            best_person is not None
            and best_score >= self.match_threshold
        ):

            return (
                best_person,
                best_score
            )

        return None, best_score

    # ---------------------------------------------------------
    # SIMILARITY
    # ---------------------------------------------------------

    @staticmethod
    def similarity(a, b):

        if a is None or b is None:
            return 0.0

        if len(a) != len(b):
            return 0.0

        # Histogram portion
        hist_a = a[:-1].astype(
            np.float32
        )

        hist_b = b[:-1].astype(
            np.float32
        )

        score = cv2.compareHist(
            hist_a,
            hist_b,
            cv2.HISTCMP_CORREL
        )

        return float(score)

    # ---------------------------------------------------------
    # EVENT COUNTERS
    # ---------------------------------------------------------

    def register_event(
        self,
        person_id,
        direction
    ):

        if person_id not in self.identities:
            return

        if direction == "IN":

            self.identities[
                person_id
            ]["entries"] += 1

        elif direction == "OUT":

            self.identities[
                person_id
            ]["exits"] += 1

        self.save()