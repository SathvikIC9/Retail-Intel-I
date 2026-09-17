"""
inventory_manager.py — Core inventory logic with fixed shelf capacities and category resets.
"""

import csv
import os
import random
import tempfile
from datetime import datetime

DATA_DIR = os.environ.get("UNOQ_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
CSV_FILE = os.environ.get("UNOQ_CSV_FILE", os.path.join(DATA_DIR, "inventory_synced.csv"))

CSV_COLUMNS = [
    "product_id",
    "product_name",
    "category",
    "price",
    "total_stock",
    "shelf_units",
    "shelf_capacity",
    "units_sold",
    "last_billing_update",
    "last_shelf_update",
]

NUMERIC_FIELDS = ["price", "total_stock", "shelf_units", "shelf_capacity", "units_sold"]

CATEGORY_CAPACITIES = {
    "Snacks": 10,
    "Beverages": 10,
    "Baby Care": 5,
    "Sanitary": 5,
    "Pulses & Flour": 20,
    "Vegetables": 15,
}

STATUS_STOCK_OK = "STOCK_OK"
STATUS_RESTOCK_REQUIRED = "RESTOCK_REQUIRED"
STATUS_OUT_OF_STOCK = "OUT_OF_STOCK"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def load_inventory():
    _ensure_data_dir()
    inventory = {}

    if not os.path.exists(CSV_FILE):
        return inventory

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product = dict(row)
            for field in NUMERIC_FIELDS:
                if field == "price":
                    product[field] = float(product.get(field, 0) or 0)
                else:
                    product[field] = int(float(product.get(field, 0) or 0))
            
            # Ensure shelf capacity defaults to category configuration
            cat = product.get("category", "")
            if cat in CATEGORY_CAPACITIES and product["shelf_capacity"] <= 0:
                product["shelf_capacity"] = CATEGORY_CAPACITIES[cat]

            inventory[product["product_id"]] = product

    return inventory


def save_inventory(inventory) -> None:
    _ensure_data_dir()

    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix="inventory_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for product_id in sorted(inventory.keys()):
                row = {col: inventory[product_id].get(col, "") for col in CSV_COLUMNS}
                writer.writerow(row)
        os.replace(tmp_path, CSV_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def deduct_stock(product_id, quantity, inventory=None, persist=True):
    """Deduct stock when items are purchased via the POS/Deduct page."""
    if inventory is None:
        inventory = load_inventory()

    if product_id not in inventory:
        raise ValueError(f"Product ID '{product_id}' not found.")

    qty = int(quantity)
    if qty <= 0:
        raise ValueError("Deduction quantity must be greater than zero.")

    product = inventory[product_id]
    current_shelf = product.get("shelf_units", 0)

    if qty > current_shelf:
        raise ValueError(f"Cannot deduct {qty} units. Only {current_shelf} available on shelf.")

    product["shelf_units"] -= qty
    product["units_sold"] += qty
    product["last_billing_update"] = _now()

    if persist:
        save_inventory(inventory)

    return inventory


def reset_category_stock(category_name, inventory=None, persist=True):
    """Refill shelf units back to maximum capacity for a category."""
    if inventory is None:
        inventory = load_inventory()

    timestamp = _now()
    count = 0
    for pid, product in inventory.items():
        if product.get("category") == category_name:
            cap = product.get("shelf_capacity") or CATEGORY_CAPACITIES.get(category_name, 10)
            product["shelf_units"] = cap
            product["last_shelf_update"] = timestamp
            count += 1

    if persist:
        save_inventory(inventory)

    return count


def reset_product_stock(product_id, inventory=None, persist=True):
    """Refill shelf units back to maximum capacity for a single product."""
    if inventory is None:
        inventory = load_inventory()

    if product_id not in inventory:
        raise ValueError(f"Product '{product_id}' does not exist.")

    product = inventory[product_id]
    cat = product.get("category")
    cap = product.get("shelf_capacity") or CATEGORY_CAPACITIES.get(cat, 10)

    product["shelf_units"] = cap
    product["last_shelf_update"] = _now()

    if persist:
        save_inventory(inventory)

    return inventory


def check_stock_levels(inventory):
    """Check shelf units against fixed threshold (20% of shelf capacity)."""
    statuses = {}
    for product_id, product in inventory.items():
        shelf_units = product.get("shelf_units", 0)
        cap = product.get("shelf_capacity", 10)
        
        # Restock trigger occurs when stock drops below 25% capacity
        threshold = max(1, int(cap * 0.25))

        if shelf_units <= 0:
            status = STATUS_OUT_OF_STOCK
        elif shelf_units <= threshold:
            status = STATUS_RESTOCK_REQUIRED
        else:
            status = STATUS_STOCK_OK

        statuses[product_id] = status
    return statuses


def generate_category_summary(inventory=None):
    """Generate aggregate capacity and stock status grouped by category."""
    if inventory is None:
        inventory = load_inventory()

    statuses = check_stock_levels(inventory)
    categories = {}

    for cat_name, max_cap in CATEGORY_CAPACITIES.items():
        categories[cat_name] = {
            "category": cat_name,
            "unit": "Kgs" if cat_name in ["Pulses & Flour", "Vegetables"] else "Units",
            "capacity_per_item": max_cap,
            "total_items": 0,
            "total_shelf_units": 0,
            "out_of_stock_count": 0,
            "restock_required_count": 0,
            "needs_attention": False
        }

    for pid, product in inventory.items():
        cat = product.get("category")
        if cat in categories:
            categories[cat]["total_items"] += 1
            categories[cat]["total_shelf_units"] += product.get("shelf_units", 0)
            
            st = statuses[pid]
            if st == STATUS_OUT_OF_STOCK:
                categories[cat]["out_of_stock_count"] += 1
                categories[cat]["needs_attention"] = True
            elif st == STATUS_RESTOCK_REQUIRED:
                categories[cat]["restock_required_count"] += 1
                categories[cat]["needs_attention"] = True

    return list(categories.values())


def fetch_shelf_data(inventory=None, test_data=None):
    if test_data is not None:
        return dict(test_data)

    if inventory is None:
        inventory = load_inventory()

    simulated = {}
    for product_id, product in inventory.items():
        current = product.get("shelf_units", 0)
        drift = random.choice([-2, -1, -1, 0, 0, 0, 1])
        simulated[product_id] = max(0, current + drift)

    return simulated


def update_shelf_quantities(inventory, shelf_data):
    timestamp = _now()
    for product_id, shelf_units in shelf_data.items():
        if product_id in inventory:
            inventory[product_id]["shelf_units"] = max(0, int(shelf_units))
            inventory[product_id]["last_shelf_update"] = timestamp
    return inventory


def generate_restock_status(inventory=None, category=None):
    if inventory is None:
        inventory = load_inventory()

    statuses = check_stock_levels(inventory)
    results = []
    for product_id, status in statuses.items():
        product = inventory[product_id]
        if category and product.get("category") != category:
            continue

        if status in (STATUS_RESTOCK_REQUIRED, STATUS_OUT_OF_STOCK):
            cap = product.get("shelf_capacity", 10)
            results.append({
                "product_id": product_id,
                "product_name": product.get("product_name", ""),
                "category": product.get("category", ""),
                "shelf_units": product.get("shelf_units", 0),
                "shelf_capacity": cap,
                "status": status,
            })
    return results


def get_product(product_id, inventory=None):
    if inventory is None:
        inventory = load_inventory()
    return inventory.get(product_id)


def get_all_products(inventory=None):
    if inventory is None:
        inventory = load_inventory()
    return [inventory[pid] for pid in sorted(inventory.keys())]