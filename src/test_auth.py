import copy
import json

import pytest
from fastapi.testclient import TestClient

import app as app_module
import auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "USER_STORE_PATH", tmp_path / "auth_users.json")
    monkeypatch.setattr(auth, "AUDIT_LOG_PATH", tmp_path / "auth_audit.jsonl")
    auth.create_user("lead@slalom.com", "lead-password-123", "practice_lead", ["Technology"])
    auth.create_user("consultant@slalom.com", "consultant-password-123", "consultant")
    monkeypatch.setattr(app_module, "capabilities", copy.deepcopy(app_module.capabilities))
    with TestClient(app_module.app) as test_client:
        yield test_client


def sign_in(client, email, password):
    response = client.post("/auth/login", json={"email": email, "password": password})
    if response.status_code == 200:
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response


def test_anonymous_users_cannot_view_or_mutate_capabilities(client):
    assert client.get("/capabilities").status_code == 401
    response = client.post(
        "/capabilities/Cloud%20Architecture/register",
        params={"email": "attacker@slalom.com"},
    )
    assert response.status_code == 401
    assert client.post(
        "/auth/register",
        json={"email": "new@slalom.com", "password": "new-password-123"},
    ).status_code == 404


def test_authenticated_mutations_require_csrf_token(client):
    sign_in(client, "consultant@slalom.com", "consultant-password-123")
    client.headers.pop("X-CSRF-Token")
    response = client.post("/capabilities/Cloud%20Architecture/register")
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or missing CSRF token"


def test_consultant_registration_requires_lead_approval(client):
    assert sign_in(client, "consultant@slalom.com", "consultant-password-123").status_code == 200
    response = client.post("/capabilities/Cloud%20Architecture/register")
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    capability = client.get("/capabilities").json()["Cloud Architecture"]
    assert "consultant@slalom.com" in capability["pending_consultants"]
    assert "consultant@slalom.com" not in capability["consultants"]


def test_consultant_cannot_remove_another_consultant(client):
    sign_in(client, "consultant@slalom.com", "consultant-password-123")
    response = client.delete(
        "/capabilities/Cloud%20Architecture/unregister",
        params={"email": "alice.smith@slalom.com"},
    )
    assert response.status_code == 403


def test_consultant_cannot_remove_approved_registration(client):
    sign_in(client, "consultant@slalom.com", "consultant-password-123")
    app_module.capabilities["Cloud Architecture"]["consultants"].append("consultant@slalom.com")
    response = client.delete("/capabilities/Cloud%20Architecture/unregister")
    assert response.status_code == 403


def test_practice_lead_can_approve_requests_in_authorized_area(client):
    sign_in(client, "consultant@slalom.com", "consultant-password-123")
    client.post("/capabilities/Cloud%20Architecture/register")
    client.post("/auth/logout")
    assert sign_in(client, "lead@slalom.com", "lead-password-123").status_code == 200
    response = client.post(
        "/capabilities/Cloud%20Architecture/approve",
        params={"email": "consultant@slalom.com"},
    )
    assert response.status_code == 200
    capability = client.get("/capabilities").json()["Cloud Architecture"]
    assert "consultant@slalom.com" in capability["consultants"]
    assert "consultant@slalom.com" not in capability["pending_consultants"]


def test_practice_lead_cannot_manage_another_practice_area(client):
    sign_in(client, "lead@slalom.com", "lead-password-123")
    response = client.delete(
        "/capabilities/Digital%20Strategy/unregister",
        params={"email": "liam.anderson@slalom.com"},
    )
    assert response.status_code == 403


def test_login_rejects_invalid_credentials(client):
    response = sign_in(client, "lead@slalom.com", "wrong-password-123")
    assert response.status_code == 401


def test_lead_can_update_requirements_and_change_is_audited(client):
    sign_in(client, "lead@slalom.com", "lead-password-123")
    response = client.patch(
        "/capabilities/Cloud%20Architecture/requirements",
        json={"capacity": 48},
    )
    assert response.status_code == 200
    assert response.json()["capacity"] == 48
    audit_entries = [
        json.loads(line)
        for line in auth.AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    ]
    assert audit_entries[-1]["action"] == "capability_requirements_updated"
    assert "lead-password-123" not in auth.AUDIT_LOG_PATH.read_text(encoding="utf-8")


def test_reports_are_lead_only_and_scoped_to_assigned_practice_areas(client):
    sign_in(client, "consultant@slalom.com", "consultant-password-123")
    assert client.get("/reports/capabilities").status_code == 403
    client.post("/auth/logout")
    sign_in(client, "lead@slalom.com", "lead-password-123")
    report = client.get("/reports/capabilities")
    assert report.status_code == 200
    assert report.json()["capabilities"] == 6
    assert set(report.json()["by_practice_area"]) == {"Technology"}


def test_consultant_training_request_requires_and_records_lead_review(client):
    sign_in(client, "consultant@slalom.com", "consultant-password-123")
    request_response = client.post(
        "/capabilities/Cloud%20Architecture/training-requests",
        json={"goal": "Build stronger cloud architecture workshop skills"},
    )
    assert request_response.status_code == 201
    assert request_response.json()["status"] == "pending"
    request_data = client.get("/capabilities").json()["Cloud Architecture"]["training_requests"]
    assert request_data[0]["email"] == "consultant@slalom.com"
    assert client.post(
        "/capabilities/Cloud%20Architecture/training-requests/review",
        params={"email": "consultant@slalom.com", "decision": "approved"},
    ).status_code == 403

    client.post("/auth/logout")
    sign_in(client, "lead@slalom.com", "lead-password-123")
    review_response = client.post(
        "/capabilities/Cloud%20Architecture/training-requests/review",
        params={"email": "consultant@slalom.com", "decision": "approved"},
    )
    assert review_response.status_code == 200
    assert app_module.capabilities["Cloud Architecture"]["training_requests"][0]["status"] == "approved"


def test_login_uses_signed_httponly_session_and_returns_no_hash(client):
    response = sign_in(client, "lead@slalom.com", "lead-password-123")
    assert response.status_code == 200
    assert "password_hash" not in response.json()
    assert response.cookies.get("slalom_session")
    assert "httponly" in response.headers["set-cookie"].lower()


def test_account_store_hashes_password_and_rejects_unknown_practice_area(client):
    users = auth.load_users()
    stored_password = users["lead@slalom.com"]["password_hash"]
    assert stored_password != "lead-password-123"
    assert auth.verify_password("lead-password-123", stored_password)
    with pytest.raises(ValueError, match="Use Technology"):
        auth.create_user(
            "other-lead@slalom.com",
            "another-password-123",
            "practice_lead",
            ["Tech"],
        )