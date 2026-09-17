import sys
import subprocess

def install_if_missing(package_name, pip_name=None):
    if pip_name is None:
        pip_name = package_name
    try:
        __import__(package_name)
    except ImportError:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            pip_name, "--break-system-packages"
        ])

install_if_missing("flask")
install_if_missing("numpy")
install_if_missing("flask-cors")
install_if_missing("cv2", "opencv-python-headless")
install_if_missing("requests")
import os
import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import inventory_manager

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# =========================================================
# ANALYTICS: laptop doorway service integration
# =========================================================
# The laptop runs YOLO detection (too heavy for this board's storage) and
# exposes results over HTTP. This board just polls that API and forwards
# the data to the dashboard - no ML, no CSV parsing needed here.
LAPTOP_IP = "192.168.1.36"     # <-- CHANGE THIS to your laptop's actual IP
LAPTOP_PORT = 5001              # doorway detection service
LAPTOP_BASE_URL = f"http://{LAPTOP_IP}:{LAPTOP_PORT}"

QUEUE_LAPTOP_PORT = 5002        # queue detection service (same laptop, different port)
QUEUE_BASE_URL = f"http://{LAPTOP_IP}:{QUEUE_LAPTOP_PORT}"

AISLE_LAPTOP_PORT = 5003        # aisle dwell-time + heatmap service (same laptop, different port)
AISLE_BASE_URL = f"http://{LAPTOP_IP}:{AISLE_LAPTOP_PORT}"

REQUEST_TIMEOUT_SECONDS = 3

# Helper to load and calculate live status.
# Reads through inventory_manager so this is the SAME file (and same
# status/threshold logic) that Reset/Deduct/Reset-Category write to.
def get_processed_inventory():
    inventory = inventory_manager.load_inventory()
    statuses = inventory_manager.check_stock_levels(inventory)

    products = []
    for pid, p in inventory.items():
        p = dict(p)
        shelf = int(p.get('shelf_units', 0))
        cap = int(p.get('shelf_capacity', 10)) if p.get('shelf_capacity') else 10
        p['shelf_units'] = shelf
        p['shelf_capacity'] = cap

        status = statuses.get(pid, inventory_manager.STATUS_STOCK_OK)
        if status == inventory_manager.STATUS_OUT_OF_STOCK:
            p['status'] = 'Out of Stock'
            p['status_class'] = 'status-out'
        elif status == inventory_manager.STATUS_RESTOCK_REQUIRED:
            p['status'] = 'Low Stock'
            p['status_class'] = 'status-low'
        else:
            p['status'] = 'In Stock'
            p['status_class'] = 'status-ok'

        products.append(p)

    products.sort(key=lambda p: p.get('product_id', ''))
    return products

def get_processed_categories(products):
    categories = {}
    for p in products:
        cat = p.get('category', 'General')
        units = p.get('shelf_units', 0)
        cap = p.get('shelf_capacity', 10)
        unit_label = p.get('unit', 'Units')

        if cat not in categories:
            categories[cat] = {
                'category': cat,
                'total_shelf_units': 0,
                'capacity_per_item': 0,
                'out_of_stock_count': 0,
                'needs_attention': False,
                'unit': unit_label
            }

        categories[cat]['total_shelf_units'] += units
        categories[cat]['capacity_per_item'] += cap

        if units <= (cap * 0.25):
            categories[cat]['needs_attention'] = True
        if units == 0:
            categories[cat]['out_of_stock_count'] += 1

    return list(categories.values())

# ==========================================
# MAIN DASHBOARD / INVENTORY ROUTE
# ==========================================

@app.route('/')
def home():
    """Renders the HTML and injects data fetched directly from the CSV."""
    products = get_processed_inventory()
    categories = get_processed_categories(products)
    
    # Calculate metric card summaries
    low_stock_count = sum(1 for p in products if p['status'] in ['Low Stock', 'Out of Stock'])
    
    return render_template(
        'index.html',
        products=products,
        categories=categories,
        low_stock_count=low_stock_count
    )

# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.route('/api/products', methods=['GET'])
def get_products():
    return jsonify(get_processed_inventory()), 200

@app.route('/api/category/summary', methods=['GET'])
def get_category_summary():
    products = get_processed_inventory()
    return jsonify(get_processed_categories(products)), 200

@app.route('/api/products/deduct', methods=['POST'])
def deduct_stock():
    data = request.get_json() or {}
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))

    try:
        inventory_manager.deduct_stock(product_id, quantity)
        return jsonify({"message": "Stock deducted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/category/reset', methods=['POST'])
def reset_category_stock():
    data = request.get_json() or {}
    category = data.get('category')
    try:
        inventory_manager.reset_category_stock(category)
        return jsonify({"message": f"Reset stock for category {category}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/products/<product_id>/reset', methods=['POST'])
def reset_single_product(product_id):
    try:
        inventory_manager.reset_product_stock(product_id)
        return jsonify({"message": f"Product {product_id} stock restored"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================================================
# ANALYTICS ROUTES (proxy to the laptop's doorway service)
# =========================================================
# These never talk to a camera or run YOLO themselves - they just fetch
# already-computed JSON from the laptop and pass it through. If the
# laptop is offline or unreachable, we return a safe fallback instead
# of letting the dashboard hang or crash.

@app.route('/api/analytics/summary', methods=['GET'])
def analytics_summary():
    try:
        response = requests.get(
            f"{LAPTOP_BASE_URL}/analytics/summary",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return jsonify(response.json()), 200
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "laptop_unreachable",
            "message": str(e),
            "total_visits_all_time": 0,
            "total_exits_all_time": 0,
            "people_inside_now": 0,
            "today_visits": 0,
            "today_exits": 0,
            "peak_hour": None,
            "hourly_breakdown": [],
        }), 200


@app.route('/api/analytics/status', methods=['GET'])
def analytics_status():
    """Lightweight live status (used for the Dashboard tab's Visitors card)."""
    try:
        response = requests.get(
            f"{LAPTOP_BASE_URL}/status",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return jsonify(response.json()), 200
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "laptop_unreachable",
            "message": str(e),
            "running": False,
            "total_in": 0,
            "total_out": 0,
            "people_inside": 0,
            "last_event": None,
            "fps": 0,
        }), 200


@app.route('/api/analytics/events/recent', methods=['GET'])
def analytics_recent_events():
    try:
        response = requests.get(
            f"{LAPTOP_BASE_URL}/events/recent",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return jsonify(response.json()), 200
    except requests.exceptions.RequestException as e:
        return jsonify([]), 200


# =========================================================
# QUEUE MANAGEMENT ROUTES (proxy to the laptop's queue service, port 5002)
# =========================================================

@app.route('/api/queue/summary', methods=['GET'])
def queue_summary():
    try:
        response = requests.get(
            f"{QUEUE_BASE_URL}/api/analytics/summary",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return jsonify(response.json()), 200
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "laptop_unreachable",
            "message": str(e),
            "total_waiting": 0,
            "active_people_count": 0,
            "average_wait_frames": 0,
            "longest_wait_frames": 0,
            "counters": [],
        }), 200


@app.route('/api/queue/status', methods=['GET'])
def queue_status():
    """Full live status including per-person data, used for detailed views."""
    try:
        response = requests.get(
            f"{QUEUE_BASE_URL}/api/status",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return jsonify(response.json()), 200
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "laptop_unreachable",
            "frame_number": 0,
            "counters": {},
            "people": [],
            "total_waiting": 0,
        }), 200


# =========================================================
# AISLE DWELL-TIME + HEATMAP ROUTES (proxy to laptop, port 5003)
# =========================================================

@app.route('/api/aisle/summary', methods=['GET'])
def aisle_summary():
    try:
        response = requests.get(
            f"{AISLE_BASE_URL}/analytics/summary",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return jsonify(response.json()), 200
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "laptop_unreachable",
            "message": str(e),
            "aisles": {},
            "busiest_aisle": None,
        }), 200


@app.route('/api/aisle/heatmap.png', methods=['GET'])
def aisle_heatmap_image():
    """Streams the live-rendered heatmap PNG straight from the laptop.
    The board never generates the image itself - just forwards bytes."""
    try:
        response = requests.get(
            f"{AISLE_BASE_URL}/heatmap.png",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.content, 200, {'Content-Type': 'image/png'}
    except requests.exceptions.RequestException:
        # Return a 404 so the frontend's <img onerror=...> can show a fallback
        return '', 404


# =========================================================
# ALERTS (single source of truth - shared by Dashboard + Alerts page)
# =========================================================

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Proxies the queue service's alert store. Both the Dashboard's
    notification widget and the dedicated Alerts page call THIS route,
    so they always see the exact same data - no possibility of drift."""
    try:
        response = requests.get(
            f"{QUEUE_BASE_URL}/api/alerts",
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return jsonify(response.json()), 200
    except requests.exceptions.RequestException:
        return jsonify({"alerts": [], "count": 0}), 200


if __name__ == '__main__':
    print("Starting RetailInteli Engine on http://0.0.0.0:5000 ...")
    app.run(host="0.0.0.0", port=5000, debug=False)