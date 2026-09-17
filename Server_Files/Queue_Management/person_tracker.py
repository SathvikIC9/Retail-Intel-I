from collections import defaultdict, deque


class PersonTracker:

    def __init__(self, history_size=5):

        self.history_size = history_size

        # track_id -> recent zone assignments
        self.zone_history = defaultdict(
            lambda: deque(
                maxlen=self.history_size
            )
        )

        # track_id -> latest assignment
        self.people = {}


    def update(self, assignments):

        stable_assignments = []

        for person in assignments:

            track_id = person["track_id"]

            zone_name = person.get(
                "zone_name"
            )

            zone_type = person.get(
                "zone_type"
            )

            counter_id = person.get(
                "counter_id"
            )


            # ------------------------------------------
            # Store this frame's zone
            # ------------------------------------------

            self.zone_history[
                track_id
            ].append(
                (
                    zone_name,
                    zone_type,
                    counter_id
                )
            )


            # ------------------------------------------
            # Find the most common recent zone
            # ------------------------------------------

            history = list(
                self.zone_history[
                    track_id
                ]
            )


            valid_history = [
                item
                for item in history
                if item[0] is not None
            ]


            if valid_history:

                counts = defaultdict(int)

                for item in valid_history:
                    counts[item] += 1

                stable_zone = max(
                    counts,
                    key=counts.get
                )

                stable_zone_name = stable_zone[0]
                stable_zone_type = stable_zone[1]
                stable_counter_id = stable_zone[2]

            else:

                stable_zone_name = None
                stable_zone_type = None
                stable_counter_id = None


            # ------------------------------------------
            # Add smoothed information
            # ------------------------------------------

            smoothed = person.copy()

            smoothed["zone_name"] = (
                stable_zone_name
            )

            smoothed["zone_type"] = (
                stable_zone_type
            )

            smoothed["counter_id"] = (
                stable_counter_id
            )

            smoothed["smoothed"] = True


            # ------------------------------------------
            # Save latest state
            # ------------------------------------------

            self.people[
                track_id
            ] = smoothed


            stable_assignments.append(
                smoothed
            )


        return stable_assignments