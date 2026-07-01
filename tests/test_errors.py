from fastapi import FastAPI
from fastapi.testclient import TestClient
from userharbor.exceptions import (
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidPasswordResetTokenError,
    InvalidPermissionError,
    InvalidRoleError,
    InvalidSessionTokenError,
    InvalidUsernameError,
    InvalidVerificationTokenError,
    PermissionDeniedError,
    UnknownPermissionError,
    UnknownRoleError,
    UnverifiedUserError,
    UserHarborError,
    WeakPasswordError,
)

from conftest import VALID_EMAIL, VALID_PASSWORD, VALID_USERNAME
from userharbor_fastapi.errors import (
    error_payload,
    get_error_code,
    get_status_code,
    register_exception_handlers,
)


def test_endpoint_error_mapping(client, email_sender) -> None:
    response = client.post(
        "/auth/register",
        json={"username": "ab", "email": VALID_EMAIL, "password": VALID_PASSWORD},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_username"

    response = client.post(
        "/auth/register",
        json={
            "username": VALID_USERNAME,
            "email": "not-an-email",
            "password": VALID_PASSWORD,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_email"

    response = client.post(
        "/auth/register",
        json={"username": VALID_USERNAME, "email": VALID_EMAIL, "password": "weak"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "weak_password"

    response = client.post(
        "/auth/register",
        json={
            "username": VALID_USERNAME,
            "email": VALID_EMAIL,
            "password": VALID_PASSWORD,
        },
    )
    assert response.status_code == 201

    response = client.post(
        "/auth/register",
        json={
            "username": VALID_USERNAME,
            "email": "other@example.com",
            "password": VALID_PASSWORD,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_username"

    response = client.post("/auth/verify-email", json={"token": "wrong"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_verification_token"

    response = client.post(
        "/auth/login",
        json={"username": VALID_USERNAME, "password": VALID_PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "unverified_user"

    token = email_sender.sent_verifications[-1].verification_token
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200

    response = client.post(
        "/auth/login",
        json={"username": VALID_USERNAME, "password": "Wrongpass1!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_credentials"

    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": "wrong", "new_password": VALID_PASSWORD},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_password_reset_token"

    response = client.get("/auth/me")
    assert response.status_code == 401

    response = client.get("/auth/me", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_session_token"


def test_rbac_error_mapping(client, email_sender) -> None:
    client.post(
        "/auth/register",
        json={
            "username": VALID_USERNAME,
            "email": VALID_EMAIL,
            "password": VALID_PASSWORD,
        },
    )
    token = email_sender.sent_verifications[-1].verification_token
    client.post("/auth/verify-email", json={"token": token})
    login_response = client.post(
        "/auth/login",
        json={"username": VALID_USERNAME, "password": VALID_PASSWORD},
    )
    session_token = login_response.json()["access_token"]

    response = client.get("/admin", headers={"Authorization": f"Bearer {session_token}"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "unknown_role"

    response = client.get(
        "/billing",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "unknown_permission"

    response = client.get(
        "/invalid-role",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_role"

    response = client.get(
        "/invalid-permission",
        headers={"Authorization": f"Bearer {session_token}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_permission"


def test_register_exception_handlers() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/")
    def route():
        raise InvalidEmailError("Invalid email")

    response = TestClient(app).get("/")

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid email", "code": "invalid_email"}


def test_error_helpers() -> None:
    errors = [
        (InvalidCredentialsError("bad"), 401, "invalid_credentials"),
        (InvalidSessionTokenError("bad"), 401, "invalid_session_token"),
        (PermissionDeniedError("denied"), 403, "permission_denied"),
        (UnverifiedUserError("unverified"), 403, "unverified_user"),
        (UnknownPermissionError("unknown"), 404, "unknown_permission"),
        (UnknownRoleError("unknown"), 404, "unknown_role"),
        (InvalidUsernameError("Username already exists"), 409, "invalid_username"),
        (InvalidPasswordResetTokenError("bad"), 400, "invalid_password_reset_token"),
        (InvalidPermissionError("bad"), 400, "invalid_permission"),
        (InvalidRoleError("bad"), 400, "invalid_role"),
        (InvalidVerificationTokenError("bad"), 400, "invalid_verification_token"),
        (WeakPasswordError("weak"), 400, "weak_password"),
        (UserHarborError("generic"), 400, "userharbor_error"),
    ]

    for error, status_code, code in errors:
        assert get_status_code(error) == status_code
        assert get_error_code(error) == code
        assert error_payload(error) == {"detail": str(error), "code": code}

    assert error_payload(UserHarborError()) == {
        "detail": "UserHarborError",
        "code": "userharbor_error",
    }
