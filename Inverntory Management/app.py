import os
import pandas as pd
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import inventory_manager

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Resolve relative path dynamically based on script directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, 'inventory_synced.csv')

# Helper to load and calculate live status
def get_processed_inventory():
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
    else:
        # Fallback to inventory_manager's CSV
        inv = inventory_manager.load_inventory()
        df = pd.DataFrame(list(inv.values()))

    products = df.to_dict(orient='records')
    for p in products:
        shelf = int(p.get('shelf_units', 0))
        cap = int(p.get('shelf_capacity', 10)) if p.get('shelf_capacity') else 10
        p['shelf_units'] = shelf
        p['shelf_capacity'] = cap
        
        if shelf <= 0:
            p['status'] = 'Out of Stock'
            p['status_class'] = 'status-out'
        elif shelf <= (cap * 0.25):
            p['status'] = 'Low Stock'
            p['status_class'] = 'status-low'
        else:
            p['status'] = 'In Stock'
            p['status_class'] = 'status-ok'

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

if __name__ == '__main__':
    print("Starting RetailInteli Engine on http://0.0.0.0:5000 ...")
    app.run(host="0.0.0.0", port=5000, debug=False)