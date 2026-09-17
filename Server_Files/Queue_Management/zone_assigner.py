import json
import math


class Zone:
    def __init__(self, name, points):
        self.name = name
        self.points = points

        parts = name.split("_")

        self.counter_id = int(parts[1])
        self.zone_type = parts[2].upper()

        # Precompute bounding box
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        self.min_x = min(xs)
        self.max_x = max(xs)
        self.min_y = min(ys)
        self.max_y = max(ys)


def load_zones(filename="zones.json"):
    with open(filename, "r") as f:
        raw_zones = json.load(f)

    zones = []

    for name, points in raw_zones.items():
        zones.append(
            Zone(name, points)
        )

    return zones


def get_contact_point(bbox):
    """
    bbox = [x1, y1, x2, y2]

    Returns bottom-center of bounding box.
    """

    x1, y1, x2, y2 = bbox

    x = (x1 + x2) / 2
    y = y2

    return x, y


def point_in_polygon(point, polygon):
    """
    Ray-casting point-in-polygon test.
    """

    x, y = point

    inside = False

    n = len(polygon)

    j = n - 1

    for i in range(n):

        xi, yi = polygon[i]
        xj, yj = polygon[j]

        intersects = (
            (yi > y) != (yj > y)
            and
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )

        if intersects:
            inside = not inside

        j = i

    return inside


def point_in_zone(point, zone):
    """
    First perform fast AABB rejection.
    Then perform polygon test.
    """

    x, y = point

    # Fast rejection
    if x < zone.min_x:
        return False

    if x > zone.max_x:
        return False

    if y < zone.min_y:
        return False

    if y > zone.max_y:
        return False

    # Actual polygon test
    return point_in_polygon(
        point,
        zone.points
    )


def find_memberships(contact_point, zones):
    """
    Find every zone containing the contact point.
    """

    memberships = []

    for zone in zones:

        if point_in_zone(
            contact_point,
            zone
        ):

            memberships.append({
                "counter_id": zone.counter_id,
                "zone_type": zone.zone_type,
                "zone_name": zone.name
            })

    return memberships


def resolve_assignment(
    contact_point,
    memberships,
    zones
):
    """
    Resolve which zone/counter owns the person.
    """

    # Person is not inside any zone
    if not memberships:

        return {
            "counter_id": None,
            "zone_type": None,
            "role": "UNASSIGNED",
            "ambiguity": True,
            "zone_name": None
        }

    # Zone priority
    #
    # Lower number = higher priority
    priority = {
        "CASHIER": 1,
        "SERVICE": 2,
        "QUEUE": 3
    }

    best_priority = min(
        priority[m["zone_type"]]
        for m in memberships
    )

    candidates = [
        m
        for m in memberships
        if priority[m["zone_type"]] == best_priority
    ]

    # Only one candidate
    if len(candidates) == 1:

        selected = candidates[0]

    else:

        # Multiple candidates of the same type.
        # Choose nearest zone.

        x, y = contact_point

        def distance(membership):

            zone = next(
                z
                for z in zones
                if z.name == membership["zone_name"]
            )

            # Zone centroid
            cx = sum(
                p[0]
                for p in zone.points
            ) / len(zone.points)

            cy = sum(
                p[1]
                for p in zone.points
            ) / len(zone.points)

            return math.sqrt(
                (x - cx) ** 2 +
                (y - cy) ** 2
            )

        selected = min(
            candidates,
            key=distance
        )

    # Determine role
    if selected["zone_type"] == "CASHIER":
        role = "CASHIER"
    else:
        role = "CUSTOMER"

    return {
        "counter_id": selected["counter_id"],
        "zone_type": selected["zone_type"],
        "role": role,
        "ambiguity": len(memberships) > 1,
        "zone_name": selected["zone_name"]
    }


def assign_person(bbox, zones):
    """
    Complete assignment pipeline:

    bbox
      ↓
    contact point
      ↓
    AABB rejection
      ↓
    point-in-polygon
      ↓
    memberships
      ↓
    ambiguity resolution
      ↓
    final assignment
    """

    contact_point = get_contact_point(bbox)

    memberships = find_memberships(
        contact_point,
        zones
    )

    assignment = resolve_assignment(
        contact_point,
        memberships,
        zones
    )

    assignment["contact_point"] = contact_point
    assignment["memberships"] = memberships

    return assignment