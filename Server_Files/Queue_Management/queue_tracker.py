class QueueTracker:

    def __init__(self, max_missing_frames=30):
        self.people = {}
        self.completed_waits = []

        # Number of consecutive frames a track may be missing
        # before it is considered inactive.
        self.max_missing_frames = max_missing_frames

    def update(self, assignments, frame_number):

        # Keep track of which IDs were detected in this frame
        seen_ids = set()

        for person in assignments:

            track_id = person["track_id"]
            counter_id = person["counter_id"]
            zone_type = person["zone_type"]
            zone_name = person["zone_name"]

            seen_ids.add(track_id)

            # --------------------------------------------------
            # NEW PERSON
            # --------------------------------------------------

            if track_id not in self.people:

                state = self._infer_state(zone_type)

                self.people[track_id] = {
                    "track_id": track_id,

                    "counter_id": counter_id,

                    "current_zone": zone_name,
                    "current_zone_type": zone_type,

                    "previous_zone": None,
                    "previous_zone_type": None,

                    "state": state,

                    "queue_entry_frame": (
                        frame_number
                        if zone_type == "QUEUE"
                        else None
                    ),

                    "service_entry_frame": (
                        frame_number
                        if zone_type == "SERVICE"
                        else None
                    ),

                    "wait_frames": 0,

                    "completed_wait": None,

                    "last_seen_frame": frame_number,

                    # Lifecycle flag
                    "active": True,
                }

                continue

            # --------------------------------------------------
            # EXISTING PERSON
            # --------------------------------------------------

            data = self.people[track_id]

            previous_zone_type = data["current_zone_type"]

            data["previous_zone"] = data["current_zone"]
            data["previous_zone_type"] = previous_zone_type

            data["current_zone"] = zone_name
            data["current_zone_type"] = zone_type
            data["counter_id"] = counter_id

            # Track was seen again
            data["last_seen_frame"] = frame_number
            data["active"] = True

            # --------------------------------------------------
            # QUEUE → SERVICE
            # --------------------------------------------------

            if (
                previous_zone_type == "QUEUE"
                and zone_type == "SERVICE"
            ):

                if data["queue_entry_frame"] is not None:

                    wait_frames = (
                        frame_number
                        - data["queue_entry_frame"]
                    )

                    data["wait_frames"] = wait_frames
                    data["completed_wait"] = wait_frames

                    self.completed_waits.append(
                        wait_frames
                    )

                data["service_entry_frame"] = frame_number
                data["state"] = "SERVING"

            # --------------------------------------------------
            # QUEUING
            # --------------------------------------------------

            elif zone_type == "QUEUE":

                # Person has just entered a queue
                if previous_zone_type != "QUEUE":

                    data["queue_entry_frame"] = frame_number
                    data["completed_wait"] = None

                data["state"] = "QUEUING"

                if data["queue_entry_frame"] is not None:

                    data["wait_frames"] = (
                        frame_number
                        - data["queue_entry_frame"]
                    )

            # --------------------------------------------------
            # SERVING
            # --------------------------------------------------

            elif zone_type == "SERVICE":

                # If they entered service without coming from
                # a queue, initialize service time here.
                if previous_zone_type != "SERVICE":

                    data["service_entry_frame"] = frame_number

                data["state"] = "SERVING"

            # --------------------------------------------------
            # CASHIER
            # --------------------------------------------------

            elif zone_type == "CASHIER":

                data["state"] = "CASHIER"

            # --------------------------------------------------
            # OUTSIDE / UNASSIGNED
            # --------------------------------------------------

            else:

                data["state"] = "OUTSIDE"

        # ------------------------------------------------------
        # HANDLE MISSING TRACKS
        # ------------------------------------------------------

        self._expire_missing_tracks(
            seen_ids,
            frame_number
        )

    # ==========================================================
    # STATE INFERENCE
    # ==========================================================

    def _infer_state(self, zone_type):

        if zone_type == "QUEUE":
            return "QUEUING"

        elif zone_type == "SERVICE":
            return "SERVING"

        elif zone_type == "CASHIER":
            return "CASHIER"

        else:
            return "OUTSIDE"

    # ==========================================================
    # TRACK LIFECYCLE
    # ==========================================================

    def _expire_missing_tracks(
        self,
        seen_ids,
        frame_number
    ):

        for track_id, data in self.people.items():

            # Already inactive
            if not data["active"]:
                continue

            # Track was detected this frame
            if track_id in seen_ids:
                continue

            missing_frames = (
                frame_number
                - data["last_seen_frame"]
            )

            # --------------------------------------------------
            # TEMPORARILY LOST
            # --------------------------------------------------

            if missing_frames <= self.max_missing_frames:

                # Keep the person's state.
                #
                # IMPORTANT:
                # We do NOT change them to OUTSIDE here.
                #
                # ByteTrack can temporarily lose a person due
                # to occlusion or detection failure.
                pass

            # --------------------------------------------------
            # TRACK EXPIRED
            # --------------------------------------------------

            else:

                data["active"] = False

                # We intentionally DO NOT add a completed wait
                # here.
                #
                # A person disappearing from the camera does not
                # prove that their queue journey was completed.

    # ==========================================================
    # ACTIVE PEOPLE
    # ==========================================================
    def get_people(self):
        return self.people


    def get_active_people(self):

        return {
            track_id: data
            for track_id, data in self.people.items()
            if data["active"]
        }

    # ==========================================================
    # COMPLETED WAIT ANALYTICS
    # ==========================================================

    def get_average_wait(self):

        if not self.completed_waits:
            return 0.0

        return (
            sum(self.completed_waits)
            / len(self.completed_waits)
        )

    def get_longest_wait(self):

        if not self.completed_waits:
            return 0

        return max(self.completed_waits)