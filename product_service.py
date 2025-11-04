"""
Helper module để giao tiếp với Product Service (TH3)
"""
import os
import requests
from flask import request

def get_product_service_url():
    """Lấy URL của Product Service từ config hoặc environment variable"""
    return os.getenv("PRODUCT_SERVICE_URL", "http://localhost:5001")

def get_auth_token():
    """Lấy JWT token từ request header"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "").strip()
    return None

def get_product(product_id):
    """
    Lấy thông tin sản phẩm từ Product Service
    
    Args:
        product_id: ID của sản phẩm
        
    Returns:
        dict: Thông tin sản phẩm nếu thành công, None nếu không tìm thấy
        tuple: (None, error_message) nếu có lỗi
    """
    try:
        token = get_auth_token()
        if not token:
            return None, "Missing authentication token"
            
        url = f"{get_product_service_url()}/products/{product_id}"
        headers = {"Authorization": f"Bearer {token}"}
        
        resp = requests.get(url, headers=headers, timeout=5)
        
        if resp.status_code == 200:
            return resp.json(), None
        elif resp.status_code == 404:
            return None, f"Product {product_id} not found"
        else:
            return None, f"Product service error: {resp.status_code}"
    except requests.RequestException as e:
        return None, f"Failed to connect to product service: {str(e)}"

def check_product_availability(product_id, quantity):
    """
    Kiểm tra tồn kho sản phẩm
    
    Args:
        product_id: ID của sản phẩm
        quantity: Số lượng cần kiểm tra
        
    Returns:
        tuple: (is_available, product_data, error_message)
        - is_available: True nếu đủ tồn kho, False nếu không
        - product_data: Thông tin sản phẩm nếu tìm thấy
        - error_message: Thông báo lỗi nếu có
    """
    product_data, error = get_product(product_id)
    
    if error:
        return False, None, error
    
    if product_data:
        available_quantity = product_data.get("quantity", 0)
        if available_quantity >= quantity:
            return True, product_data, None
        else:
            return False, product_data, f"Insufficient stock. Available: {available_quantity}, Requested: {quantity}"
    
    return False, None, "Product not found"

