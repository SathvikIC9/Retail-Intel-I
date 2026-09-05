"""
inventory_manager.py

Core inventory logic for the Arduino UNO Q retail inventory system.

Design goals (see project spec):
  - ONE csv file is the single source of truth (product + inventory + billing fields).
  - Shelf quantities come from fetch_shelf_data() — SIMULATED for this prototype,
    but written so it can be swapped for a real camera/AI detection call later
    without touching anything else in this file.
  - No Bluetooth / networking code here at all. Restock info is just returned
    as plain Python data structures; the dashboard (or anything else) decides
    what to do with it.

Only the Python standard library is used: csv, os, json (not actually needed
here, kept out), datetime, random (only to drive the shelf simulator), tempfile.
"""

import csv
import os
import random
import tempfile
from datetime import datetime

# ---------------------------------------------------------------------------
# 1. CONFIGURATION — all paths live here, nowhere else in the program.
# ---------------------------------------------------------------------------

# On the real UNO Q, point this at wherever you want the data to live, e.g.
# "/home/arduino/inventory_data". Overridable via env var for easy testing.
DATA_DIR = os.environ.get("UNOQ_DATA_DIR", os.path.join(os.path.dirname(__file__), "inventory_data"))
CSV_FILE = os.path.join(DATA_DIR, "inventory_large.csv")

# The single set of columns that define the CSV schema. If the supermarket's
# real export uses different column names, this is the only place to change.
CSV_COLUMNS = [
    "product_id",
    "product_name",
    "category",
    "price",
    "total_stock",
    "shelf_units",
    "restock_threshold",
    "units_sold",
    "last_billing_update",
    "last_shelf_update",
]

# Fields that must be numeric (and, for these particular fields, non-negative).
NUMERIC_FIELDS = ["price", "total_stock", "shelf_units", "restock_threshold", "units_sold"]

STATUS_STOCK_OK = "STOCK_OK"
STATUS_RESTOCK_REQUIRED = "RESTOCK_REQUIRED"
STATUS_OUT_OF_STOCK = "OUT_OF_STOCK"


def _now() -> str:
    """Timestamp string used for last_billing_update / last_shelf_update."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# 2. LOAD / SAVE — the only two functions that touch the file directly.
# ---------------------------------------------------------------------------

def load_inventory():
    """
    Read the master CSV and return the inventory as a dict keyed by product_id:

        {
            "P001": {"product_id": "P001", "product_name": "Milk", ... },
            "P002": {...},
            ...
        }

    Numeric fields are converted to int/float. Returns an empty dict if the
    file does not exist yet (first run).
    """
    _ensure_data_dir()
    inventory = {}

    if not os.path.exists(CSV_FILE):
        return inventory

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product = dict(row)
            for field in NUMERIC_FIELDS:
                # price can be a float, the rest are whole units
                if field == "price":
                    product[field] = float(product.get(field, 0) or 0)
                else:
                    product[field] = int(float(product.get(field, 0) or 0))
            inventory[product["product_id"]] = product

    return inventory


def save_inventory(inventory) -> None:
    """
    Write the current inventory back to CSV_FILE.

    Uses a write-to-temp-file-then-replace pattern so a power interruption
    on the UNO Q can't leave the master CSV half-written / corrupted.
    """
    _ensure_data_dir()

    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix="inventory_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for product_id in sorted(inventory.keys()):
                row = {col: inventory[product_id].get(col, "") for col in CSV_COLUMNS}
                writer.writerow(row)
        # Atomic on POSIX (and on the UNO Q's Linux side): either the old file
        # is fully there or the new one is — never a half-written file.
        os.replace(tmp_path, CSV_FILE)
    except Exception:
        # Clean up the temp file if something went wrong before the replace.
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# ---------------------------------------------------------------------------
# 3. SHELF DATA — SIMULATED in this prototype.
#
#    This is the ONLY function that needs to change when the real
#    shelf-camera / AI product-detection system is ready. Everything
#    downstream of it (update_shelf_quantities, check_stock_levels,
#    generate_restock_status) is agnostic to where the numbers come from.
# ---------------------------------------------------------------------------

def fetch_shelf_data(inventory=None, test_data=None):
    """
    Return the latest shelf quantity for each product:

        {"P001": 12, "P002": 4, "P003": 3}

    SIMULATED behaviour for this prototype:
      - If `test_data` is given, it's returned as-is (lets you feed exact
        scenarios in tests / demos, e.g. the example in the spec).
      - Otherwise, if `inventory` is given, we simulate a camera reading by
        taking each product's current shelf_units and jittering it by a
        small random amount (as if items were bought/moved since the last
        read). This just keeps the demo realistic.
      - If neither is given, we load the inventory ourselves.

    INTEGRATION POINT: replace the body of this function with a call to the
    real shelf-camera / AI detection service. Keep the same signature
    (accepts nothing required, returns {product_id: int_units}) and nothing
    else in this file needs to change.
    """
    if test_data is not None:
        return dict(test_data)

    if inventory is None:
        inventory = load_inventory()

    simulated = {}
    for product_id, product in inventory.items():
        current = product.get("shelf_units", 0)
        # Simulate small natural fluctuation: sold a couple, or unchanged.
        drift = random.choice([-2, -1, -1, 0, 0, 0, 1])
        simulated[product_id] = max(0, current + drift)

    return simulated


# ---------------------------------------------------------------------------
# 4. INVENTORY UPDATE FLOW
# ---------------------------------------------------------------------------

def update_shelf_quantities(inventory, shelf_data):
    """
    Apply the output of fetch_shelf_data() onto the in-memory inventory,
    updating shelf_units and last_shelf_update. Does NOT save to disk —
    call save_inventory() afterwards if you want the change persisted.
    Returns the same inventory dict for convenience.
    """
    timestamp = _now()
    for product_id, shelf_units in shelf_data.items():
        if product_id in inventory:
            inventory[product_id]["shelf_units"] = max(0, int(shelf_units))
            inventory[product_id]["last_shelf_update"] = timestamp
    return inventory


def check_stock_levels(inventory):
    """
    Check every product against its threshold.

    Returns a dict: {product_id: status_string}, using:
        STOCK_OK, RESTOCK_REQUIRED, OUT_OF_STOCK
    """
    statuses = {}
    for product_id, product in inventory.items():
        shelf_units = product.get("shelf_units", 0)
        threshold = product.get("restock_threshold", 0)

        if shelf_units <= 0:
            status = STATUS_OUT_OF_STOCK
        elif shelf_units <= threshold:
            status = STATUS_RESTOCK_REQUIRED
        else:
            status = STATUS_STOCK_OK

        statuses[product_id] = status
    return statuses


def generate_restock_status(inventory=None):
    """
    Return a list of products that need attention (RESTOCK_REQUIRED or
    OUT_OF_STOCK), e.g.:

        [
            {
                "product_id": "P002",
                "product_name": "Bread",
                "shelf_units": 4,
                "threshold": 5,
                "status": "RESTOCK_REQUIRED"
            }
        ]

    This is plain application data — no Bluetooth, no networking. A
    dashboard or a future comms layer can do whatever it wants with it.
    """
    if inventory is None:
        inventory = load_inventory()

    statuses = check_stock_levels(inventory)
    results = []
    for product_id, status in statuses.items():
        if status in (STATUS_RESTOCK_REQUIRED, STATUS_OUT_OF_STOCK):
            product = inventory[product_id]
            results.append({
                "product_id": product_id,
                "product_name": product.get("product_name", ""),
                "shelf_units": product.get("shelf_units", 0),
                "threshold": product.get("restock_threshold", 0),
                "status": status,
            })
    return results


# ---------------------------------------------------------------------------
# 5. LOOKUPS
# ---------------------------------------------------------------------------

def get_product(product_id, inventory=None):
    """Return the dict for one product, or None if it doesn't exist."""
    if inventory is None:
        inventory = load_inventory()
    return inventory.get(product_id)


def get_all_products(inventory=None):
    """Return all products as a list of dicts, sorted by product_id."""
    if inventory is None:
        inventory = load_inventory()
    return [inventory[pid] for pid in sorted(inventory.keys())]


# ---------------------------------------------------------------------------
# 6. VALIDATION — used by update_product() before anything touches the CSV.
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when manager-dashboard input fails validation."""
    pass


def _validate_product_id(product_id, inventory, expect_existing):
    if not product_id or not str(product_id).strip():
        raise ValidationError("product_id cannot be empty.")
    exists = product_id in inventory
    if expect_existing and not exists:
        raise ValidationError(f"Product '{product_id}' does not exist.")
    if not expect_existing and exists:
        raise ValidationError(f"Product '{product_id}' already exists (duplicate ID).")


def _validate_numeric_fields(fields: dict):
    for field, value in fields.items():
        if field not in NUMERIC_FIELDS:
            continue
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"Field '{field}' must be numeric (got {value!r}).")
        if num < 0:
            raise ValidationError(f"Field '{field}' cannot be negative (got {value!r}).")


# ---------------------------------------------------------------------------
# 7. MANAGER DASHBOARD ENTRY POINT — edits go through here, and only here.
# ---------------------------------------------------------------------------

def update_product(product_id, updates: dict, inventory=None, persist=True):
    """
    Apply manager-dashboard edits to one product.

    `updates` is a dict of any subset of the editable fields, e.g.:
        {"product_name": "Whole Milk", "price": 55, "restock_threshold": 6}

    Validates input, prevents negative numeric values, and (since product_id
    is the dict key) duplicate IDs can't be created through this path.
    Raises ValidationError on bad input — nothing is written in that case.

    If persist=True (default), writes the updated CSV via save_inventory().
    Returns the updated inventory dict.
    """
    if inventory is None:
        inventory = load_inventory()

    _validate_product_id(product_id, inventory, expect_existing=True)
    _validate_numeric_fields(updates)

    product = inventory[product_id]
    for field, value in updates.items():
        if field == "product_id":
            # Renaming IDs is a separate, riskier operation — not allowed here.
            continue
        if field in NUMERIC_FIELDS:
            product[field] = float(value) if field == "price" else int(float(value))
        elif field in CSV_COLUMNS:
            product[field] = value

    product["last_billing_update"] = _now()

    if persist:
        save_inventory(inventory)

    return inventory


def add_product(product_id, product_name, category, price, total_stock,
                 restock_threshold, inventory=None, persist=True):
    """
    Add a brand-new product row. Validates the ID is non-empty and unique,
    and that all numeric fields are valid non-negative numbers.
    """
    if inventory is None:
        inventory = load_inventory()

    _validate_product_id(product_id, inventory, expect_existing=False)
    fields = {
        "price": price,
        "total_stock": total_stock,
        "restock_threshold": restock_threshold,
    }
    _validate_numeric_fields(fields)

    timestamp = _now()
    inventory[product_id] = {
        "product_id": product_id,
        "product_name": product_name,
        "category": category,
        "price": float(price),
        "total_stock": int(float(total_stock)),
        "shelf_units": 0,  # unknown until fetch_shelf_data() runs
        "restock_threshold": int(float(restock_threshold)),
        "units_sold": 0,
        "last_billing_update": timestamp,
        "last_shelf_update": timestamp,
    }

    if persist:
        save_inventory(inventory)

    return inventory


# ---------------------------------------------------------------------------
# 8. DEMO / SELF-TEST — run this file directly to see the full flow once.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    inv = load_inventory()
    print(f"Loaded {len(inv)} products from {CSV_FILE}\n")

    # Use the exact example from the spec so the output is checkable.
    demo_shelf_data = fetch_shelf_data(test_data={"P001": 12, "P002": 4, "P003": 8})
    update_shelf_quantities(inv, demo_shelf_data)
    save_inventory(inv)

    print("After fetch_shelf_data() + update_shelf_quantities():\n")
    print(f"{'Product':<12}{'Shelf':<8}{'Threshold':<12}{'Status'}")
    for product in get_all_products(inv):
        status = check_stock_levels(inv)[product["product_id"]]
        print(f"{product['product_name']:<12}{product['shelf_units']:<8}{product['restock_threshold']:<12}{status}")

    print("\nRestock status list (what a dashboard/comms layer would consume):")
    for item in generate_restock_status(inv):
        print(" ", item)
