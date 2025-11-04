import os
from decimal import Decimal, InvalidOperation
from flask import Flask, request, jsonify
from flask import send_from_directory
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

from models import db, Order, OrderItem
from auth import jwt_required_external
from product_service import check_product_availability, get_product_service_url, get_auth_token
import requests

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS", "False") == "True"

db.init_app(app)

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

# ==================== ORDER ENDPOINTS ====================

# 1) GET /orders: Lấy danh sách tất cả các đơn hàng
@app.get("/orders")
@jwt_required_external
def list_orders():
    orders = Order.query.order_by(Order.id.desc()).all()
    return jsonify([order.to_dict() for order in orders]), 200

# 2) GET /orders/:id: Lấy thông tin chi tiết một đơn hàng
@app.get("/orders/<int:order_id>")
@jwt_required_external
def get_order(order_id: int):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"msg": "Order not found"}), 404
    return jsonify(order.to_dict()), 200

# 3) POST /orders: Tạo đơn hàng mới (kiểm tra tồn kho)
@app.post("/orders")
@jwt_required_external
def create_order():
    data = request.get_json() or {}
    
    customer_name = data.get("customer_name")
    customer_email = data.get("customer_email")
    items = data.get("items", [])  # Danh sách các mặt hàng
    
    # Validate
    if not customer_name:
        return jsonify({"msg": "customer_name is required"}), 400
    if not customer_email:
        return jsonify({"msg": "customer_email is required"}), 400
    if not items or not isinstance(items, list) or len(items) == 0:
        return jsonify({"msg": "items is required and must be a non-empty list"}), 400
    
    # Kiểm tra tồn kho và tính toán tổng tiền
    total_amount = Decimal('0.00')
    order_items_data = []
    
    for item in items:
        product_id = item.get("product_id")
        quantity = item.get("quantity")
        
        if not product_id:
            return jsonify({"msg": "product_id is required in items"}), 400
        if not quantity or quantity <= 0:
            return jsonify({"msg": "quantity must be a positive integer"}), 400
        
        # Kiểm tra tồn kho từ Product Service
        is_available, product_data, error = check_product_availability(product_id, quantity)
        
        if not is_available:
            return jsonify({"msg": error or "Product not available"}), 400
        
        # Lấy thông tin sản phẩm
        unit_price = Decimal(str(product_data.get("price", 0)))
        product_name = product_data.get("name", "")
        total_price = unit_price * quantity
        
        order_items_data.append({
            "product_id": product_id,
            "product_name": product_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": total_price
        })
        
        total_amount += total_price
    
    # Tạo đơn hàng
    order = Order(
        customer_name=customer_name,
        customer_email=customer_email,
        total_amount=total_amount,
        status="pending"
    )
    db.session.add(order)
    db.session.flush()  # Lấy ID của order
    
    # Tạo các order items
    for item_data in order_items_data:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data["product_id"],
            product_name=item_data["product_name"],
            quantity=item_data["quantity"],
            unit_price=item_data["unit_price"],
            total_price=item_data["total_price"]
        )
        db.session.add(order_item)
    
    db.session.commit()
    return jsonify(order.to_dict()), 201

# 4) PUT /orders/:id: Cập nhật trạng thái đơn hàng
@app.put("/orders/<int:order_id>")
@jwt_required_external
def update_order(order_id: int):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"msg": "Order not found"}), 404
    
    data = request.get_json() or {}
    status = data.get("status")
    
    # Validate status
    valid_statuses = ["pending", "completed", "cancelled"]
    if status and status not in valid_statuses:
        return jsonify({"msg": f"status must be one of: {', '.join(valid_statuses)}"}), 400
    
    # Cập nhật trạng thái
    if status:
        order.status = status
    
    # Cập nhật các trường khác nếu có
    if "customer_name" in data:
        order.customer_name = data["customer_name"]
    if "customer_email" in data:
        order.customer_email = data["customer_email"]
    
    db.session.commit()
    return jsonify(order.to_dict()), 200

# 5) DELETE /orders/:id: Xóa một đơn hàng
@app.delete("/orders/<int:order_id>")
@jwt_required_external
def delete_order(order_id: int):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"msg": "Order not found"}), 404
    db.session.delete(order)
    db.session.commit()
    return "", 204

# ==================== ORDER ITEMS ENDPOINTS ====================

# 1) GET /order_items: Lấy danh sách tất cả mặt hàng trong đơn hàng
@app.get("/order_items")
@jwt_required_external
def list_order_items():
    order_id = request.args.get("order_id", type=int)
    
    if order_id:
        # Lấy items theo order_id
        items = OrderItem.query.filter_by(order_id=order_id).all()
    else:
        # Lấy tất cả items
        items = OrderItem.query.order_by(OrderItem.id.desc()).all()
    
    return jsonify([item.to_dict() for item in items]), 200

# 2) GET /order_items/:id: Lấy thông tin chi tiết một mặt hàng
@app.get("/order_items/<int:item_id>")
@jwt_required_external
def get_order_item(item_id: int):
    item = OrderItem.query.get(item_id)
    if not item:
        return jsonify({"msg": "Order item not found"}), 404
    return jsonify(item.to_dict()), 200

# 3) POST /order_items: Tạo mặt hàng mới
@app.post("/order_items")
@jwt_required_external
def create_order_item():
    data = request.get_json() or {}
    
    order_id = data.get("order_id")
    product_id = data.get("product_id")
    quantity = data.get("quantity")
    
    # Validate
    if not order_id:
        return jsonify({"msg": "order_id is required"}), 400
    if not product_id:
        return jsonify({"msg": "product_id is required"}), 400
    if not quantity or quantity <= 0:
        return jsonify({"msg": "quantity must be a positive integer"}), 400
    
    # Kiểm tra order tồn tại
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"msg": "Order not found"}), 404
    
    # Kiểm tra tồn kho từ Product Service
    is_available, product_data, error = check_product_availability(product_id, quantity)
    
    if not is_available:
        return jsonify({"msg": error or "Product not available"}), 400
    
    # Lấy thông tin sản phẩm
    unit_price = Decimal(str(product_data.get("price", 0)))
    product_name = product_data.get("name", "")
    total_price = unit_price * quantity
    
    # Tạo order item
    order_item = OrderItem(
        order_id=order_id,
        product_id=product_id,
        product_name=product_name,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price
    )
    db.session.add(order_item)
    
    # Cập nhật tổng tiền của đơn hàng
    order.total_amount += total_price
    
    db.session.commit()
    return jsonify(order_item.to_dict()), 201

# 4) PUT /order_items/:id: Cập nhật mặt hàng
@app.put("/order_items/<int:item_id>")
@jwt_required_external
def update_order_item(item_id: int):
    item = OrderItem.query.get(item_id)
    if not item:
        return jsonify({"msg": "Order item not found"}), 404
    
    data = request.get_json() or {}
    
    # Lấy order để cập nhật tổng tiền
    order = Order.query.get(item.order_id)
    if not order:
        return jsonify({"msg": "Order not found"}), 404
    
    # Trừ tổng tiền cũ
    old_total = item.total_price
    order.total_amount -= old_total
    
    # Cập nhật quantity nếu có
    quantity = data.get("quantity", item.quantity)
    if quantity != item.quantity:
        if quantity <= 0:
            return jsonify({"msg": "quantity must be a positive integer"}), 400
        
        # Kiểm tra tồn kho
        is_available, product_data, error = check_product_availability(item.product_id, quantity)
        
        if not is_available:
            # Hoàn lại tổng tiền
            order.total_amount += old_total
            db.session.commit()
            return jsonify({"msg": error or "Product not available"}), 400
        
        item.quantity = quantity
        item.unit_price = Decimal(str(product_data.get("price", item.unit_price)))
        item.total_price = item.unit_price * quantity
    
    # Cộng tổng tiền mới
    order.total_amount += item.total_price
    
    db.session.commit()
    return jsonify(item.to_dict()), 200

# 5) DELETE /order_items/:id: Xóa một mặt hàng trong đơn hàng
@app.delete("/order_items/<int:item_id>")
@jwt_required_external
def delete_order_item(item_id: int):
    item = OrderItem.query.get(item_id)
    if not item:
        return jsonify({"msg": "Order item not found"}), 404
    
    # Cập nhật tổng tiền của đơn hàng
    order = Order.query.get(item.order_id)
    if order:
        order.total_amount -= item.total_price
    
    db.session.delete(item)
    db.session.commit()
    return "", 204

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.getenv("PORT", "5002"))
    app.run(host="0.0.0.0", port=port, debug=True)
