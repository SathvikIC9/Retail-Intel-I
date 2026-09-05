from zone_assigner import load_zones, assign_person


# Load calibrated zones
zones = load_zones("zones.json")

print(f"Loaded {len(zones)} zones")


# -------------------------------------------------
# Test bounding boxes
# -------------------------------------------------
#
# IMPORTANT:
# These are just example boxes.
# We will replace them with boxes positioned
# specifically for your image afterward.
#

test_people = [
    [350, 200, 390, 350],
    [400, 300, 440, 430],
    [450, 400, 490, 550],
    [700, 300, 740, 450],
    [100, 100, 130, 200],
]


for i, bbox in enumerate(test_people, start=1):

    result = assign_person(
        bbox,
        zones
    )

    print()
    print("=" * 60)
    print(f"PERSON {i}")
    print("=" * 60)

    print(f"Bounding box : {bbox}")

    print(
        f"Contact point: "
        f"{result['contact_point']}"
    )

    print(
        f"Memberships  : "
        f"{result['memberships']}"
    )

    print(
        f"Zone         : "
        f"{result['zone_name']}"
    )

    print(
        f"Counter      : "
        f"{result['counter_id']}"
    )

    print(
        f"Zone type    : "
        f"{result['zone_type']}"
    )

    print(
        f"Role         : "
        f"{result['role']}"
    )

    print(
        f"Ambiguity    : "
        f"{result['ambiguity']}"
    )