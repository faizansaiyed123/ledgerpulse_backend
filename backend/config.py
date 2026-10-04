import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ENV = os.getenv("FLASK_ENV", os.getenv("ENV", "development"))
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-only-change-me"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres@localhost:5432/ledgerpulse_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
    }
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    CONTACT_INBOX_EMAIL = os.getenv("CONTACT_INBOX_EMAIL", "")

    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
    FIREBASE_CLIENT_EMAIL = os.getenv("FIREBASE_CLIENT_EMAIL", "")
    FIREBASE_PRIVATE_KEY = os.getenv("FIREBASE_PRIVATE_KEY", "")

    PLATFORM_ADMIN_UIDS = {
        value.strip()
        for value in os.getenv("PLATFORM_ADMIN_UIDS", "").split(",")
        if value.strip()
    }

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "LedgerPulse")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    @classmethod
    def validate(cls):
        if cls.ENV == "production":
            if cls.SECRET_KEY == "dev-only-change-me":
                raise RuntimeError("SECRET_KEY must be configured in production")
            if not cls.SQLALCHEMY_DATABASE_URI:
                raise RuntimeError("DATABASE_URL must be configured in production")
            if cls.SMTP_USE_TLS and cls.SMTP_USE_SSL:
                raise RuntimeError("SMTP_USE_TLS and SMTP_USE_SSL cannot both be enabled")
