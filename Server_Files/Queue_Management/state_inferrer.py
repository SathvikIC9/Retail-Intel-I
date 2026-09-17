def infer_counter_states(zones, assignments):
    """
    Calculate state for every counter.

    assignments is a list of results returned by
    zone_assigner.assign_person().
    """

    # Find all counters from calibrated zones
    counter_ids = sorted(
        set(zone.counter_id for zone in zones)
    )

    counters = {}

    # -----------------------------------------
    # Initialize counters
    # -----------------------------------------

    for counter_id in counter_ids:

        counters[counter_id] = {
            "counter_id": counter_id,
            "cashier_present": False,
            "customer_in_service": False,
            "queue_count": 0,
            "state": "CLOSED"
        }

    # -----------------------------------------
    # Process people
    # -----------------------------------------

    for person in assignments:

        counter_id = person["counter_id"]
        zone_type = person["zone_type"]
        role = person["role"]

        # Ignore people outside all zones
        if counter_id is None:
            continue

        # Ignore invalid counter
        if counter_id not in counters:
            continue

        # -------------------------------------
        # CASHIER
        # -------------------------------------

        if (
            zone_type == "CASHIER"
            and role == "CASHIER"
        ):
            counters[counter_id]["cashier_present"] = True

        # -------------------------------------
        # CUSTOMER BEING SERVED
        # -------------------------------------

        elif (
            zone_type == "SERVICE"
            and role == "CUSTOMER"
        ):
            counters[counter_id][
                "customer_in_service"
            ] = True

        # -------------------------------------
        # CUSTOMER WAITING
        # -------------------------------------

        elif (
            zone_type == "QUEUE"
            and role == "CUSTOMER"
        ):
            counters[counter_id]["queue_count"] += 1

    # -----------------------------------------
    # Determine counter state
    # -----------------------------------------

    for counter in counters.values():

        if not counter["cashier_present"]:

            counter["state"] = "CLOSED"

        elif (
            not counter["customer_in_service"]
            and
            counter["queue_count"] == 0
        ):

            counter["state"] = "IDLE"

        else:

            counter["state"] = "BUSY"

    return counters