"""
app.py — Flask API wrapper for inventory_manager.py
"""

from flask import Flask, jsonify, request, send_from_directory
import backup.inventory_manager as im

app = Flask(__name__)

# Valid categories matching the store aisle floor plan
STORE_CATEGORIES = [
    "Snacks",
    "Beverages",
    "Baby Care",
    "Sanitary",
    "Pulses & Flour",
    "Vegetables",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _status_for(product, inventory):
    statuses = im.check_stock_levels(inventory)
    return statuses.get(product["product_id"], "UNKNOWN")


def _enrich(product, inventory):
    """Attach computed status to a product dict."""
    return {**product, "status": _status_for(product, inventory)}


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@app.route("/api/categories", methods=["GET"])
def list_categories():
    """Return list of store aisle categories matching floor plan layout."""
    return jsonify(STORE_CATEGORIES)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@app.route("/api/products", methods=["GET"])
def list_products():
    inventory = im.load_inventory()
    category_filter = request.args.get("category")

    products = [_enrich(p, inventory) for p in im.get_all_products(inventory)]

    if category_filter:
        products = [p for p in products if p.get("category") == category_filter]

    return jsonify(products)


@app.route("/api/products/<product_id>", methods=["GET"])
def get_product(product_id):
    inventory = im.load_inventory()
    product = im.get_product(product_id, inventory)
    if product is None:
        return jsonify({"error": f"Product '{product_id}' not found."}), 404
    return jsonify(_enrich(product, inventory))


@app.route("/api/products", methods=["POST"])
def add_product():
    data = request.get_json(force=True)
    required = [
        "product_id",
        "product_name",
        "category",
        "price",
        "total_stock",
        "restock_threshold",
    ]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    try:
        inventory = im.add_product(
            product_id=data["product_id"],
            product_name=data["product_name"],
            category=data["category"],
            price=data["price"],
            total_stock=data["total_stock"],
            restock_threshold=data["restock_threshold"],
        )
    except im.ValidationError as e:
        return jsonify({"error": str(e)}), 422

    product = im.get_product(data["product_id"], inventory)
    return jsonify(_enrich(product, inventory)), 201


@app.route("/api/products/<product_id>", methods=["PUT"])
def update_product(product_id):
    data = request.get_json(force=True)
    # product_id rename is blocked upstream; strip it silently for safety
    data.pop("product_id", None)

    try:
        inventory = im.update_product(product_id, data)
    except im.ValidationError as e:
        return jsonify({"error": str(e)}), 422

    product = im.get_product(product_id, inventory)
    return jsonify(_enrich(product, inventory))


# ---------------------------------------------------------------------------
# Shelf simulation
# ---------------------------------------------------------------------------

@app.route("/api/shelf/simulate", methods=["POST"])
def simulate_shelf():
    """
    Run the shelf simulator on current inventory and persist the result.
    Optionally accepts a JSON body {"test_data": {"P001": 12, "P002": 4}}
    to inject exact shelf counts.
    """
    body = request.get_json(silent=True) or {}
    test_data = body.get("test_data")

    inventory = im.load_inventory()
    shelf_data = im.fetch_shelf_data(inventory=inventory, test_data=test_data)
    im.update_shelf_quantities(inventory, shelf_data)
    im.save_inventory(inventory)

    products = [_enrich(p, inventory) for p in im.get_all_products(inventory)]
    return jsonify({
        "shelf_reading": shelf_data,
        "products": products,
    })


# ---------------------------------------------------------------------------
# Restock
# ---------------------------------------------------------------------------

@app.route("/api/restock", methods=["GET"])
def restock_status():
    inventory = im.load_inventory()
    category_filter = request.args.get("category")
    alerts = im.generate_restock_status(inventory, category=category_filter)
    return jsonify(alerts)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)