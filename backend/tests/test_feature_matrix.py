from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

from .conftest import auth_headers


def bootstrap(client, uid="test-user", email=None, name="Test User"):
    headers = auth_headers(uid, email or f"{uid}@example.test", name)
    response = client.post("/api/auth/bootstrap", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    return headers, body["organizations"][0]["id"]


def test_full_business_api_lifecycle(client):
    headers, org_id = bootstrap(client)
    assert client.get("/api/health").status_code == 200

    created_org = client.post(
        "/api/organizations",
        headers=headers,
        json={"name": "Secondary Workspace", "currency": "INR"},
    )
    assert created_org.status_code == 201
    secondary_id = created_org.get_json()["id"]
    updated = client.put(
        f"/api/organizations/{secondary_id}",
        headers=headers,
        json={"name": "Secondary Workspace Updated", "paymentTermsDays": 45, "country": "India"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["name"] == "Secondary Workspace Updated"

    customer = client.post(
        "/api/customers",
        headers=headers,
        json={
            "orgId": org_id,
            "name": "Lifecycle Customer",
            "email": "customer@example.test",
            "company": "Lifecycle Ltd",
            "currency": "USD",
            "paymentTermsDays": 30,
        },
    )
    assert customer.status_code == 201
    customer_id = customer.get_json()["id"]

    vendor = client.post(
        "/api/vendors",
        headers=headers,
        json={
            "orgId": org_id,
            "name": "Lifecycle Vendor",
            "category": "software",
            "email": "vendor@example.test",
        },
    )
    assert vendor.status_code == 201
    vendor_id = vendor.get_json()["id"]

    invoice = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "orgId": org_id,
            "customerId": customer_id,
            "invoiceNumber": "INV-LIFECYCLE-001",
            "issueDate": date.today().isoformat(),
            "dueDate": (date.today() + timedelta(days=30)).isoformat(),
            "currency": "USD",
            "discountPercent": 10,
            "taxPercent": 5,
            "items": [
                {
                    "description": "Implementation",
                    "quantity": 2,
                    "unitPrice": 500,
                    "taxRatePercent": 5,
                }
            ],
            "status": "draft",
        },
    )
    assert invoice.status_code == 201
    inv = invoice.get_json()
    invoice_id = inv["id"]
    assert inv["subtotal"] == 1000.0
    assert inv["discountAmount"] == 100.0
    assert inv["taxAmount"] == 45.0
    assert inv["totalAmount"] == 945.0

    updated_invoice = client.put(
        f"/api/invoices/{invoice_id}",
        headers=headers,
        json={"status": "sent", "notes": "Updated from lifecycle test"},
    )
    assert updated_invoice.status_code == 200
    duplicated = client.post(f"/api/invoices/{invoice_id}/duplicate", headers=headers)
    assert duplicated.status_code == 201

    payment = client.post(
        "/api/payments",
        headers=headers,
        json={
            "invoiceId": invoice_id,
            "amount": 245,
            "paymentMethod": "bank_transfer",
            "paymentDate": date.today().isoformat(),
            "reference": "E2E-245",
        },
    )
    assert payment.status_code == 201
    assert payment.get_json()["amount"] == 245.0

    batch = client.post(
        "/api/payments/batch",
        headers=headers,
        json={
            "entries": [
                {
                    "invoiceId": invoice_id,
                    "amount": 100,
                    "paymentMethod": "credit_card",
                    "paymentDate": date.today().isoformat(),
                }
            ]
        },
    )
    assert batch.status_code == 201
    assert batch.get_json()["count"] == 1

    expense = client.post(
        "/api/expenses",
        headers=headers,
        json={
            "orgId": org_id,
            "vendorId": vendor_id,
            "category": "software",
            "description": "Lifecycle expense",
            "amount": 125.50,
            "taxAmount": 5.50,
            "currency": "USD",
            "paymentMethod": "credit_card",
            "isReimbursable": False,
            "status": "pending",
        },
    )
    assert expense.status_code == 201
    expense_id = expense.get_json()["id"]

    expense_update = client.put(
        f"/api/expenses/{expense_id}",
        headers=headers,
        json={"description": "Lifecycle expense updated", "status": "approved"},
    )
    assert expense_update.status_code == 200
    status_update = client.post(
        f"/api/expenses/{expense_id}/status",
        headers=headers,
        json={"status": "approved"},
    )
    assert status_update.status_code == 200

    recurring = client.post(
        "/api/recurring",
        headers=headers,
        json={
            "orgId": org_id,
            "templateInvoiceNumber": "REC-LIFECYCLE",
            "customerId": customer_id,
            "frequency": "monthly",
            "nextRunDate": date.today().isoformat(),
            "currency": "USD",
            "subtotal": 250,
            "discountAmount": 0,
            "taxAmount": 12.5,
            "totalAmount": 262.5,
            "items": [
                {
                    "description": "Recurring support",
                    "quantity": 1,
                    "unitPrice": 250,
                    "taxRatePercent": 5,
                }
            ],
        },
    )
    assert recurring.status_code == 201
    recurring_id = recurring.get_json()["id"]
    recurring_update = client.put(
        f"/api/recurring/{recurring_id}",
        headers=headers,
        json={"status": "paused"},
    )
    assert recurring_update.status_code == 200

    activity = client.post(
        "/api/activities",
        headers=headers,
        json={
            "orgId": org_id,
            "action": "Lifecycle test activity",
            "entityType": "organization",
            "entityId": org_id,
            "details": "Created by API lifecycle test",
        },
    )
    assert activity.status_code == 201

    summary = client.get(f"/api/organizations/{org_id}/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.get_json()["invoiceCount"] >= 2
    assert summary.get_json()["customerCount"] == 1
    assert summary.get_json()["paymentCount"] == 2

    assert client.get(f"/api/customers/{customer_id}", headers=headers).status_code == 200
    assert client.get(f"/api/vendors/{vendor_id}", headers=headers).status_code == 200
    assert client.get(f"/api/invoices/{invoice_id}", headers=headers).status_code == 200
    assert client.get(f"/api/payments?org_id={org_id}", headers=headers).status_code == 200
    assert client.get(f"/api/expenses/{expense_id}", headers=headers).status_code == 200
    assert client.get(f"/api/recurring?org_id={org_id}", headers=headers).status_code == 200
    assert client.get(f"/api/activities?org_id={org_id}&limit=200", headers=headers).status_code == 200

    assert client.delete(f"/api/customers/{customer_id}", headers=headers).status_code == 409
    assert client.delete(f"/api/vendors/{vendor_id}", headers=headers).status_code == 409

    assert client.delete(f"/api/recurring/{recurring_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/expenses/{expense_id}", headers=headers).status_code == 200

    invalid = client.post(
        "/api/recurring",
        headers=headers,
        json={
            "orgId": org_id,
            "customerId": customer_id,
            "frequency": "monthly",
            "nextRunDate": date.today().isoformat(),
            "currency": "USD",
            "subtotal": 100,
            "discountAmount": 0,
            "taxAmount": 10,
            "totalAmount": 999,
            "items": [{"description": "Bad total", "quantity": 1, "unitPrice": 100}],
        },
    )
    assert invalid.status_code == 400


def test_roles_invitations_tenant_security_and_platform_diagnostics(client):
    owner_headers, org_id = bootstrap(client, "owner", "owner@example.test", "Owner")

    invite = client.post(
        f"/api/organizations/{org_id}/members/invitations",
        headers=owner_headers,
        json={"email": "staff@example.test", "role": "staff", "name": "Staff"},
    )
    assert invite.status_code == 201
    token = parse_qs(urlparse(invite.get_json()["invitationUrl"]).query)["invite"][0]
    member_id = invite.get_json()["member"]["id"]

    wrong = client.post(
        f"/api/organizations/{org_id}/invitations/accept",
        headers=auth_headers("wrong", "wrong@example.test", "Wrong"),
        json={"token": token},
    )
    assert wrong.status_code == 403

    accepted = client.post(
        f"/api/organizations/{org_id}/invitations/accept",
        headers=auth_headers("staff", "staff@example.test", "Staff"),
        json={"token": token},
    )
    assert accepted.status_code == 200

    role = client.put(
        f"/api/organizations/{org_id}/members/{member_id}",
        headers=owner_headers,
        json={"role": "accountant"},
    )
    assert role.status_code == 200
    assert role.get_json()["role"] == "accountant"

    removed = client.delete(
        f"/api/organizations/{org_id}/members/{member_id}",
        headers=owner_headers,
    )
    assert removed.status_code == 200

    other_headers, other_org = bootstrap(client, "other", "other@example.test", "Other")
    assert client.get(f"/api/organizations/{other_org}", headers=owner_headers).status_code == 403
    assert client.get("/api/admin/overview", headers=auth_headers("regular")).status_code == 403
    assert client.get("/api/health/details", headers=auth_headers("regular")).status_code == 403
    assert client.get("/api/admin/overview", headers=owner_headers).status_code == 200
    assert client.get("/api/health/details", headers=owner_headers).status_code == 200

    assert client.post(
        f"/api/organizations/{org_id}/sample-data",
        headers=owner_headers,
    ).status_code == 201
    assert client.get(f"/api/organizations/{org_id}/summary", headers=owner_headers).status_code == 200

    unauthorized = client.get("/api/auth/me")
    assert unauthorized.status_code == 401
    assert other_headers["X-Test-User-Id"] == "other"
