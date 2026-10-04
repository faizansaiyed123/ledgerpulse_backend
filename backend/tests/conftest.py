import pytest

from backend.app import create_app
from backend.database import db


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}
    CORS_ORIGINS = "http://localhost:5173"
    FRONTEND_URL = "http://localhost:5173"
    PLATFORM_ADMIN_UIDS = {"platform-user"}
    FIREBASE_PROJECT_ID = ""
    FIREBASE_CLIENT_EMAIL = ""
    FIREBASE_PRIVATE_KEY = ""
    SMTP_HOST = ""
    SMTP_PORT = 587
    SMTP_USERNAME = ""
    SMTP_PASSWORD = ""
    SMTP_FROM_EMAIL = ""
    SMTP_FROM_NAME = "LedgerPulse"
    SMTP_USE_TLS = True
    SMTP_USE_SSL = False
    CONTACT_INBOX_EMAIL = ""
    ENV = "test"

    @classmethod
    def validate(cls):
        return None


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def auth_headers(uid="test-user", email=None, name="Test User"):
    return {
        "X-Test-User-Id": uid,
        "X-Test-User-Email": email or f"{uid}@example.test",
        "X-Test-User-Name": name,
    }
