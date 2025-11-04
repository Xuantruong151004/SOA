import os
import requests
from flask import request, jsonify
from functools import wraps

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:5000")
AUTH_VERIFY_PATH = os.getenv("AUTH_VERIFY_PATH", "/auth")

def jwt_required_external(f):
    """
    Middleware xác thực token bằng cách gọi sang Auth Service (TH2).
    Token phải ở header Authorization: Bearer <token>.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"msg": "Missing or invalid Authorization header"}), 401
        token = auth_header.replace("Bearer ", "").strip()
        try:
            resp = requests.get(
                f"{AUTH_SERVICE_URL}{AUTH_VERIFY_PATH}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
        except requests.RequestException:
            return jsonify({"msg": "Auth service unavailable"}), 503

        if resp.status_code != 200:
            return jsonify({"msg": "Unauthorized"}), 401

        # Có thể lấy identity/claims nếu cần
        request.user = resp.json().get("user")
        return f(*args, **kwargs)
    return wrapper
