from functools import wraps

from flask import current_app, g, jsonify, request

from backend.database import db
from backend.models import Organization, OrganizationMember

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth, credentials
except ImportError:  # pragma: no cover - dependency installed in normal runtime
    firebase_admin = None
    firebase_auth = None
    credentials = None


def _init_firebase():
    if firebase_admin is None:
        raise RuntimeError("firebase-admin is not installed")
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    project_id = current_app.config.get("FIREBASE_PROJECT_ID")
    client_email = current_app.config.get("FIREBASE_CLIENT_EMAIL")
    private_key = current_app.config.get("FIREBASE_PRIVATE_KEY")

    if client_email and private_key:
        private_key = private_key.replace("\\n", "\n")
        cred = credentials.Certificate(
            {
                "project_id": project_id,
                "client_email": client_email,
                "private_key": private_key,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
        return firebase_admin.initialize_app(cred, {"projectId": project_id} if project_id else None)

    return firebase_admin.initialize_app(options={"projectId": project_id} if project_id else None)


def verify_token():
    if current_app.config.get("TESTING"):
        test_uid = request.headers.get("X-Test-User-Id")
        if test_uid:
            return {
                "uid": test_uid,
                "email": request.headers.get("X-Test-User-Email", f"{test_uid}@example.test"),
                "name": request.headers.get("X-Test-User-Name", "Test User"),
            }

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise PermissionError("Authentication required")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise PermissionError("Authentication required")

    try:
        _init_firebase()
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
        return {
            "uid": decoded["uid"],
            "email": decoded.get("email", ""),
            "name": decoded.get("name", "") or decoded.get("email", "").split("@")[0],
        }
    except Exception as exc:
        raise PermissionError("Invalid or expired authentication token") from exc


def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            g.current_user = verify_token()
        except PermissionError as exc:
            return jsonify({"error": "Unauthorized", "message": str(exc)}), 401
        except Exception as exc:
            current_app.logger.exception("Authentication configuration failure")
            return jsonify({"error": "Authentication service unavailable", "message": "Authentication is not configured correctly"}), 503
        return func(*args, **kwargs)

    return wrapper


def current_user():
    return getattr(g, "current_user", None)


def platform_admin_required(func):
    @wraps(func)
    @require_auth
    def wrapper(*args, **kwargs):
        uid = current_user()["uid"]
        if uid not in current_app.config.get("PLATFORM_ADMIN_UIDS", set()):
            return jsonify({"error": "Forbidden", "message": "Platform administrator access required"}), 403
        return func(*args, **kwargs)

    return wrapper


def get_membership(org_id: str, *, for_update: bool = False):
    uid = current_user()["uid"]
    query = OrganizationMember.query.filter_by(org_id=org_id, user_id=uid, status="active")
    if for_update:
        query = query.with_for_update()
    return query.first()


def require_org_membership(org_id: str, *, roles=None, for_update: bool = False):
    org = Organization.query.get(org_id)
    if not org:
        return None, (jsonify({"error": "Organization not found"}), 404)
    member = get_membership(org_id, for_update=for_update)
    if not member:
        return None, (jsonify({"error": "Forbidden", "message": "You are not a member of this organization"}), 403)
    if roles and member.role not in set(roles):
        return None, (jsonify({"error": "Forbidden", "message": "Insufficient permissions"}), 403)
    return (org, member), None
