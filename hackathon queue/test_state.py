from zone_assigner import (
    load_zones,
    assign_person
)

from state_inferrer import (
    infer_counter_states
)


# ------------------------------------------------
# Load calibrated zones
# ------------------------------------------------

zones = load_zones("zones.json")

print(f"Loaded {len(zones)} zones")


# ------------------------------------------------
# Get a point safely inside a zone
# ------------------------------------------------

def get_zone_center(zone):

    x = sum(
        point[0]
        for point in zone.points
    ) / len(zone.points)

    y = sum(
        point[1]
        for point in zone.points
    ) / len(zone.points)

    return int(x), int(y)


# ------------------------------------------------
# Create a fake bounding box
#
# The important thing is that the bottom-center
# of the box lands at the selected point.
# ------------------------------------------------

def make_bbox(x, y):

    width = 40
    height = 100

    x1 = int(x - width / 2)
    x2 = int(x + width / 2)

    y1 = int(y - height)
    y2 = int(y)

    return [x1, y1, x2, y2]


# ------------------------------------------------
# Find zones by name
# ------------------------------------------------

zone_by_name = {
    zone.name: zone
    for zone in zones
}


# ------------------------------------------------
# Create simulated people
# ------------------------------------------------

test_people = []


def add_person(zone_name):

    zone = zone_by_name[zone_name]

    x, y = get_zone_center(zone)

    bbox = make_bbox(x, y)

    test_people.append(bbox)

    print(
        f"Added person to "
        f"{zone_name} at ({x}, {y})"
    )


# ------------------------------------------------
# Counter 1
# ------------------------------------------------

add_person("counter_1_cashier")
add_person("counter_1_service")
add_person("counter_1_queue")
add_person("counter_1_queue")


# ------------------------------------------------
# Counter 2
# ------------------------------------------------

add_person("counter_2_cashier")
add_person("counter_2_service")
add_person("counter_2_queue")


# ------------------------------------------------
# Counter 3
# ------------------------------------------------

add_person("counter_3_cashier")


# ------------------------------------------------
# Counter 4
# ------------------------------------------------

# No people


# ------------------------------------------------
# Run zone assignment
# ------------------------------------------------

assignments = []

for bbox in test_people:

    result = assign_person(
        bbox,
        zones
    )

    assignments.append(result)


# ------------------------------------------------
# Print person assignments
# ------------------------------------------------

print()
print("=" * 60)
print("PERSON ASSIGNMENTS")
print("=" * 60)

for i, result in enumerate(
    assignments,
    start=1
):

    print(
        f"Person {i}: "
        f"{result['zone_name']} | "
        f"{result['role']}"
    )


# ------------------------------------------------
# Infer counter states
# ------------------------------------------------

counters = infer_counter_states(
    zones,
    assignments
)


# ------------------------------------------------
# Print counter states
# ------------------------------------------------

print()
print("=" * 60)
print("COUNTER STATES")
print("=" * 60)

for counter_id, counter in counters.items():

    print()

    print(
        f"Counter {counter_id}"
    )

    print(
        f"  Cashier present     : "
        f"{counter['cashier_present']}"
    )

    print(
        f"  Customer in service : "
        f"{counter['customer_in_service']}"
    )

    print(
        f"  Queue count         : "
        f"{counter['queue_count']}"
    )

    print(
        f"  State               : "
        f"{counter['state']}"
    )