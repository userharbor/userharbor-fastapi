import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from userharbor.exceptions import UserHarborError

from conftest import NEW_PASSWORD, VALID_EMAIL, VALID_PASSWORD, VALID_USERNAME
from userharbor_fastapi import UserHarborFastAPI, bearer_token, default_user_serializer
from userharbor_fastapi.schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    PasswordResetRequest,
    ResendVerificationRequest,
)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_and_verify(client: TestClient, email_sender) -> None:
    response = client.post(
        "/auth/register",
        json={
            "username": VALID_USERNAME,
            "email": VALID_EMAIL,
            "password": VALID_PASSWORD,
        },
    )
    assert response.status_code == 201
    token = email_sender.sent_verifications[-1].verification_token
    response = client.post("/auth/verify-email", json={"token": token})
    assert response.status_code == 200


def login(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        json={"username": VALID_USERNAME, "password": VALID_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    return response.json()["access_token"]


def test_account_flow(client, store, email_sender) -> None:
    register_and_verify(client, email_sender)
    assert store.users[VALID_USERNAME].verified
    assert email_sender.sent_email_verified[-1].email == VALID_EMAIL

    token = login(client)

    response = client.get("/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json() == {
        "username": VALID_USERNAME,
        "email": VALID_EMAIL,
        "verified": True,
    }

    response = client.get("/protected", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["username"] == VALID_USERNAME

    response = client.post(
        "/auth/resend-verification",
        json={"email": VALID_EMAIL},
    )
    assert response.status_code == 200
    assert response.json() == {"detail": "Verification email sent"}
    assert len(email_sender.sent_verifications) == 1

    response = client.post(
        "/auth/password-reset/request",
        json={"email": VALID_EMAIL},
    )
    assert response.status_code == 200
    assert response.json() == {"detail": "Password reset email sent"}

    reset_token = email_sender.sent_password_resets[-1].reset_token
    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json() == {"detail": "Password reset"}
    assert email_sender.sent_password_changed[-1].email == VALID_EMAIL

    response = client.post("/auth/logout", headers=auth_header(token))
    assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json={"username": VALID_USERNAME, "password": NEW_PASSWORD},
    )
    token = response.json()["access_token"]

    response = client.post(
        "/auth/password/change",
        headers=auth_header(token),
        json={"old_password": NEW_PASSWORD, "new_password": VALID_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json() == {"detail": "Password changed"}

    response = client.post(
        "/auth/login",
        json={"username": VALID_USERNAME, "password": VALID_PASSWORD},
    )
    first_token = response.json()["access_token"]
    second_token = login(client)
    response = client.post("/auth/logout-all", headers=auth_header(first_token))
    assert response.status_code == 200
    assert response.json() == {"detail": "Logged out from all sessions"}
    assert client.get("/auth/me", headers=auth_header(second_token)).status_code == 401

    final_token = login(client)
    response = client.request(
        "DELETE",
        "/auth/account",
        headers=auth_header(final_token),
        json={"password": VALID_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json() == {"detail": "Account deleted"}
    assert VALID_USERNAME not in store.users
    assert email_sender.sent_account_deleted[-1].email == VALID_EMAIL


def test_logout_removes_only_current_session(client, email_sender) -> None:
    register_and_verify(client, email_sender)
    first_token = login(client)
    second_token = login(client)

    response = client.post("/auth/logout", headers=auth_header(first_token))

    assert response.status_code == 200
    assert response.json() == {"detail": "Logged out"}
    assert client.get("/auth/me", headers=auth_header(first_token)).status_code == 401
    assert client.get("/auth/me", headers=auth_header(second_token)).status_code == 200


def test_rbac_dependencies(client, harbor, email_sender) -> None:
    register_and_verify(client, email_sender)
    token = login(client)
    harbor.roles.create("admin")
    harbor.permissions.create("billing.read")

    assert client.get("/admin", headers=auth_header(token)).status_code == 403
    assert client.get("/billing", headers=auth_header(token)).status_code == 403

    harbor.roles.create("billing")
    harbor.roles.grant_permission("billing", "billing.read")
    harbor.grant_role(VALID_USERNAME, "admin")
    harbor.grant_role(VALID_USERNAME, "billing")

    assert client.get("/admin", headers=auth_header(token)).status_code == 200
    assert client.get("/billing", headers=auth_header(token)).status_code == 200


def test_optional_user_dependency(client, email_sender) -> None:
    assert client.get("/optional-user").json() is None
    assert client.get("/optional-user", headers=auth_header("wrong")).json() is None

    register_and_verify(client, email_sender)
    token = login(client)

    response = client.get("/optional-user", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["username"] == VALID_USERNAME


def test_custom_user_serializer(harbor, email_sender) -> None:
    auth = UserHarborFastAPI(
        harbor,
        user_serializer=lambda user: {"name": user.username, "ok": user.verified},
    )
    app = FastAPI()
    app.include_router(auth.router, prefix="/auth")
    client = TestClient(app)

    register_and_verify(client, email_sender)
    token = login(client)

    assert client.get("/auth/me", headers=auth_header(token)).json() == {
        "name": VALID_USERNAME,
        "ok": True,
    }


def test_default_user_serializer() -> None:
    class User:
        username = "jane"
        email = "jane@example.com"
        verified = True

    assert default_user_serializer(User()) == {
        "username": "jane",
        "email": "jane@example.com",
        "verified": True,
    }


def test_adapter_error_branches(auth, monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise UserHarborError("broken")

    with pytest.raises(HTTPException) as missing_token:
        bearer_token(None)
    assert missing_token.value.status_code == 401

    monkeypatch.setattr(auth.harbor, "resend_verification", fail)
    with pytest.raises(HTTPException):
        auth.resend_verification(ResendVerificationRequest(email=VALID_EMAIL))

    monkeypatch.setattr(auth.harbor, "logout_all", fail)
    with pytest.raises(HTTPException):
        auth.logout_all("token")

    monkeypatch.setattr(auth.harbor, "send_password_reset", fail)
    with pytest.raises(HTTPException):
        auth.request_password_reset(PasswordResetRequest(email=VALID_EMAIL))

    monkeypatch.setattr(auth.harbor, "change_password", fail)
    with pytest.raises(HTTPException):
        auth.change_password(
            ChangePasswordRequest(
                old_password=VALID_PASSWORD,
                new_password=NEW_PASSWORD,
            ),
            "token",
        )

    monkeypatch.setattr(auth.harbor, "delete_account", fail)
    with pytest.raises(HTTPException):
        auth.delete_account(DeleteAccountRequest(password=VALID_PASSWORD), "token")
