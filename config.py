import datetime
import os

class Config:
    # Database cho Order Service
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI", 
        "mysql+pymysql://root:02052004@localhost:3306/orderdb"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Auth Service (TH2) configuration
    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:5000")
    AUTH_VERIFY_PATH = os.getenv("AUTH_VERIFY_PATH", "/auth")
    
    # Product Service (TH3) configuration
    PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:5001")
    
    # JWT config (nếu cần)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key-change-this")
    JWT_ACCESS_TOKEN_EXPIRES = datetime.timedelta(hours=1)
