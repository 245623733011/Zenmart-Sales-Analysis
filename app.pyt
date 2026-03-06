# app.py
import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_session import Session
from datetime import datetime
import uuid
import json
import requests

# ---------- CONFIG ----------
CSV_PRODUCTS = "zenmart_sales_cleaned.xlsx"
DB_FILE = "zenmart.db"
SECRET_KEY = "change-this-in-production"
POWER_BI_PUSH_URL = ""

# Simple admin credentials
ADMIN_USERNAME = "Chandana"
ADMIN_PASSWORD = "Chandana"

# ---------- FLASK APP ----------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# ---------- LOAD PRODUCTS ----------
if not os.path.exists(CSV_PRODUCTS):
    raise FileNotFoundError(f"Products Excel not found at {CSV_PRODUCTS}. Update CSV_PRODUCTS in app.py")

products_df = pd.read_excel(CSV_PRODUCTS)

# Detect columns
def detect_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        low = c.lower()
        for cand in candidates:
            if cand.lower() in low:
                return c
    return None

name_col = detect_col(products_df, ["Product", "Product Name", "Name", "product", "product_name"])
price_col = detect_col(products_df, ["UnitPrice", "Unit Price", "Price", "price"])
category_col = detect_col(products_df, ["ProductCategory", "Category", "Product Category", "productcategory"])

if not name_col:
    products_df["product_name"] = "Item " + products_df.index.astype(str)
    name_col = "product_name"
if not price_col:
    products_df["UnitPrice"] = products_df.get("UnitPrice", 50.0)
    price_col = "UnitPrice"
if not category_col:
    products_df["Category"] = products_df.get("Category", "General")
    category_col = "Category"

_products = products_df[[name_col, price_col, category_col]].drop_duplicates().reset_index(drop=True)
_products.columns = ["name", "price", "category"]
_products["product_id"] = _products.index.astype(str)

# Extra items
extra_items = {
    "Snacks": ["Chips", "Biscuits", "Nuts", "Popcorn", "Pretzels", "Chocolate", "Cookies", "Trail Mix"],
    "Beverages": ["Coke", "Pepsi", "Sprite", "Coffee", "Tea", "Fanta", "Mountain Dew", "Lemonade", "Green Tea", "Energy Drink", "Orange Juice", "Apple Juice"],
    "Fruits": ["Apple", "Banana", "Grapes"],
    "Grocery": ["Rice", "Sugar", "Salt", "Wheat", "Flour", "Cooking Oil", "Spices", "Lentils", "Oats", "Cornflakes", "Tea Powder", "Coffee Powder", "Honey", "Vinegar", "Soy Sauce"],
    "Vegetables": ["Tomato", "Potato", "Onion"],
    "Dairy": ["Milk", "Curd", "Butter", "Cheese", "Paneer", "Yogurt"],
    "Bakery": ["Bread", "Cake", "Buns", "Muffins", "Donuts", "Croissants", "Bagels", "Pastries"],
    "Electronics": ["Hair Dryer", "Heater", "Phone", "Laptop", "Tablet", "Smartwatch", "Camera", "Headphones", "Speaker", "Router"],
    "Household": ["Broom", "Mop", "Bucket", "Detergent", "Dish Soap", "Laundry Powder", "Cleaning Cloth", "Toilet Cleaner", "Room Freshener"],
    "Cosmetics": ["Lipstick", "Foundation", "Compact Powder", "Eyeliner", "Mascara", "Blush", "Nail Polish", "Perfume", "Moisturizer", "Face Wash", "Shampoo", "Conditioner"]
}

def unique_list(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result

expanded_rows = []
for _, row in _products.iterrows():
    expanded_rows.append({
        "name": row["name"],
        "price": row["price"],
        "category": row["category"]
    })
    cat = row["category"]
    if cat in extra_items:
        for item in unique_list(extra_items[cat]):
            expanded_rows.append({
                "name": item,
                "price": row["price"],
                "category": cat
            })

_products = pd.DataFrame(expanded_rows).drop_duplicates(subset=["name", "category"]).reset_index(drop=True)
_products["product_id"] = _products.index.astype(str)

# FIX: Ensure JSON serializable
_products["price"] = _products["price"].fillna(0).astype(float)
_products = _products.fillna("").reset_index(drop=True)
PRODUCTS = _products[["product_id", "name", "price", "category"]].to_dict(orient="records")

# ---------- DATABASE ----------
def get_db_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id TEXT PRIMARY KEY,
        invoice_id TEXT,
        product_id TEXT,
        product_name TEXT,
        category TEXT,
        unit_price REAL,
        quantity INTEGER,
        revenue REAL,
        sale_time TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------- HELPERS ----------
def push_to_powerbi(payload: dict):
    if not POWER_BI_PUSH_URL:
        return False, "Power BI push not configured"
    try:
        headers = {"Content-Type":"application/json"}
        r = requests.post(POWER_BI_PUSH_URL, data=json.dumps(payload), headers=headers, timeout=8)
        r.raise_for_status()
        return True, r.text
    except Exception as e:
        return False, str(e)

# ---------- ROUTES ----------
@app.route("/")
def index():
    if "cart" not in session:
        session["cart"] = {}
    return render_template("index.html", products=PRODUCTS)

@app.route("/cart")
def view_cart():
    cart = session.get("cart", {})
    items = []
    for pid, qty in cart.items():
        prod = next((p for p in PRODUCTS if p["product_id"] == pid), None)
        if prod:
            items.append({"product_id": pid, "name": prod["name"], "price": prod["price"],
                          "quantity": qty, "total": prod["price"]*qty})
    return jsonify({"items": items})

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    data = request.get_json()
    pid = data.get("product_id")
    qty = int(data.get("quantity", 1))
    cart = session.get("cart", {})
    cart[pid] = cart.get(pid, 0) + qty
    session["cart"] = cart
    return jsonify({"status":"ok", "cart":cart})

@app.route("/remove_from_cart", methods=["POST"])
def remove_from_cart():
    data = request.get_json()
    pid = data.get("product_id")
    cart = session.get("cart", {})
    if pid in cart:
        cart.pop(pid)
    session["cart"] = cart
    return jsonify({"status":"ok", "cart":cart})

@app.route("/checkout", methods=["POST"])
def checkout():
    cart = session.get("cart", {})
    if not cart:
        return jsonify({"status":"empty", "message":"Cart is empty"}), 400
    invoice = f"INV-{uuid.uuid4().hex[:8]}"
    sale_time = datetime.utcnow().isoformat()
    conn = get_db_conn()
    cur = conn.cursor()
    pushed = []
    for pid, qty in cart.items():
        prod = next((p for p in PRODUCTS if p["product_id"] == pid), None)
        if not prod:
            continue
        unit_price = float(prod["price"])
        revenue = unit_price * qty
        row_id = uuid.uuid4().hex
        cur.execute("""
        INSERT INTO sales (id, invoice_id, product_id, product_name, category, unit_price, quantity, revenue, sale_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (row_id, invoice, pid, prod["name"], prod["category"], unit_price, qty, revenue, sale_time))
        payload = {
            "Invoice": invoice,
            "Product": prod["name"],
            "Category": prod["category"],
            "Quantity": qty,
            "Revenue": revenue,
            "Time": sale_time
        }
        ok, resp = push_to_powerbi(payload)
        pushed.append((ok, resp))
    conn.commit()
    conn.close()
    session["cart"] = {}
    return jsonify({"status":"ok", "invoice": invoice, "pushed": pushed})

@app.route("/sales_data")
def sales_data():
    conn = get_db_conn()
    df = pd.read_sql_query("SELECT * FROM sales", conn)
    conn.close()
    return df.to_json(orient="records")

# ----------------- ADMIN AUTH & DASHBOARD -----------------
@app.route("/admin_login", methods=["POST"])
def admin_login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["is_admin"] = True
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Invalid Admin Login"}), 401

@app.route("/admin_logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if not session.get("is_admin"):
        return "<h3>Unauthorized Access</h3>", 401
    return render_template("dashboard.html")

@app.route("/dashboard_data")
def dashboard_data():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_conn()
    df = pd.read_sql_query("SELECT * FROM sales", conn)
    conn.close()

    if df.empty:
        return jsonify({
            "total_revenue": 0,
            "total_orders": 0,
            "total_qty": 0,
            "category_sales": {},
            "daily_sales": {}
        })

    try:
        df["sale_time"] = pd.to_datetime(df["sale_time"])
    except Exception:
        pass

    total_revenue = float(df["revenue"].sum()) if "revenue" in df.columns else 0
    total_orders = int(df["invoice_id"].nunique()) if "invoice_id" in df.columns else 0
    total_qty = int(df["quantity"].sum()) if "quantity" in df.columns else 0

    category_sales = {}
    if "category" in df.columns and "revenue" in df.columns:
        category_sales = df.groupby("category")["revenue"].sum().to_dict()

    daily_sales = {}
    if "sale_time" in df.columns:
        df["date_only"] = df["sale_time"].dt.date
        daily_sales = df.groupby("date_only")["revenue"].sum().astype(float).to_dict()
        daily_sales = {str(k): v for k, v in daily_sales.items()}

    return jsonify({
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "total_qty": total_qty,
        "category_sales": category_sales,
        "daily_sales": daily_sales
    })

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True, port=8050)
