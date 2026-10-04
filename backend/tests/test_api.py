from datetime import date
from urllib.parse import parse_qs, urlparse

from backend.models import Organization, OrganizationMember

from .conftest import auth_headers


def test_protected_routes_require_auth(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_bootstrap_creates_workspace_for_first_user(client):
    response = client.post("/api/auth/bootstrap", headers=auth_headers())
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["organizations"]) == 1
    assert body["memberships"][0]["role"] == "owner"


def test_tenant_boundary_blocks_other_users(client):
    first = client.post("/api/auth/bootstrap", headers=auth_headers("user-a", "a@example.test", "A")).get_json()
    second = client.post("/api/auth/bootstrap", headers=auth_headers("user-b", "b@example.test", "B")).get_json()
    org_b = second["organizations"][0]["id"]

    response = client.get(f"/api/customers?org_id={org_b}", headers=auth_headers("user-a", "a@example.test", "A"))
    assert response.status_code == 403
    assert first["organizations"][0]["id"] != org_b


def test_invoice_math_and_payment_overage_are_enforced(client):
    headers = auth_headers()
    session = client.post("/api/auth/bootstrap", headers=headers).get_json()
    org_id = session["organizations"][0]["id"]
    customer = client.post(
        "/api/customers",
        headers=headers,
        json={"orgId": org_id, "name": "Acme", "currency": "USD", "paymentTermsDays": 30},
    )
    assert customer.status_code == 201
    customer_id = customer.get_json()["id"]

    invoice = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "orgId": org_id,
            "customerId": customer_id,
            "issueDate": date.today().isoformat(),
            "dueDate": date.today().isoformat(),
            "currency": "USD",
            "discountPercent": 10,
            "taxPercent": 5,
            "items": [{"description": "Service", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert invoice.status_code == 201
    body = invoice.get_json()
    assert body["subtotal"] == 100.0
    assert body["discountAmount"] == 10.0
    assert body["taxAmount"] == 4.5
    assert body["totalAmount"] == 94.5

    over = client.post(
        "/api/payments",
        headers=headers,
        json={
            "invoiceId": body["id"],
            "amount": 100,
            "paymentMethod": "bank_transfer",
            "paymentDate": date.today().isoformat(),
        },
    )
    assert over.status_code == 409


def test_invitation_requires_invited_email_and_is_single_use(client):
    owner_headers = auth_headers("owner", "owner@example.test", "Owner")
    owner_session = client.post("/api/auth/bootstrap", headers=owner_headers).get_json()
    org_id = owner_session["organizations"][0]["id"]
    invite = client.post(
        f"/api/organizations/{org_id}/members/invitations",
        headers=owner_headers,
        json={"email": "invitee@example.test", "role": "accountant", "name": "Invitee"},
    )
    assert invite.status_code == 201
    url = invite.get_json()["invitationUrl"]
    token = parse_qs(urlparse(url).query)["invite"][0]

    wrong = client.post(
        f"/api/organizations/{org_id}/invitations/accept",
        headers=auth_headers("wrong", "wrong@example.test", "Wrong"),
        json={"token": token},
    )
    assert wrong.status_code == 403

    accepted = client.post(
        f"/api/organizations/{org_id}/invitations/accept",
        headers=auth_headers("invitee", "invitee@example.test", "Invitee"),
        json={"token": token},
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["status"] == "active"

    replay = client.post(
        f"/api/organizations/{org_id}/invitations/accept",
        headers=auth_headers("invitee", "invitee@example.test", "Invitee"),
        json={"token": token},
    )
    assert replay.status_code == 404


def test_platform_admin_endpoint_is_restricted(client):
    denied = client.get("/api/admin/overview", headers=auth_headers("regular"))
    assert denied.status_code == 403

    allowed = client.get("/api/admin/overview", headers=auth_headers("platform-user"))
    assert allowed.status_code == 200
