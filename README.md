<picture>
  <img src="https://github.com/userharbor/userharbor/raw/master/docs/assets/logo-full.png" alt="userharbor">
</picture>

[![GitHub License](https://img.shields.io/github/license/userharbor/userharbor-fastapi)](https://github.com/userharbor/userharbor-fastapi?tab=MIT-1-ov-file)
[![Tests](https://img.shields.io/github/actions/workflow/status/userharbor/userharbor-fastapi/publish.yml?label=tests)](https://github.com/userharbor/userharbor-fastapi/blob/master/.github/workflows/tests.yml)
[![Codecov](https://img.shields.io/codecov/c/github/userharbor/userharbor-fastapi)](https://codecov.io/gh/userharbor/userharbor-fastapi)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/userharbor-fastapi)](https://pypi.org/project/userharbor-fastapi)
[![PyPI - Version](https://img.shields.io/pypi/v/userharbor-fastapi)](https://pypi.org/project/userharbor-fastapi)
[![Code style: black](https://img.shields.io/badge/code%20style-black-black)](https://github.com/psf/black)
[![Linting: Ruff](https://img.shields.io/badge/linting-Ruff-black?logo=ruff&logoColor=black)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Pytest](https://img.shields.io/badge/testing-Pytest-red?logo=pytest&logoColor=red)](https://docs.pytest.org/)
[![Zensical](https://img.shields.io/badge/docs-Zensical-yellow?logo=MaterialForMkDocs&logoColor=yellow)](https://userharbor.github.io/userharbor/)

> **Project status:** UserHarbor FastAPI is currently in an early stage of development.
> The API may change frequently. The library is not ready for production use yet.

`userharbor-fastapi` provides a FastAPI integration for
[`userharbor`](https://github.com/userharbor/userharbor).

It provides:

* account management routes
* bearer session token authentication
* current-user dependencies
* optional-user dependencies
* role and permission dependencies
* UserHarbor exception to HTTP error mapping
* configurable user serialization

The package only handles FastAPI routing and dependency wiring. It does not
store users, send emails, hash passwords, generate tokens, or implement
application-specific authentication policy.

---

## Installation

```bash
pip install userharbor-fastapi
```

This package depends on `userharbor` and FastAPI.

---

## Example usage

```python
from fastapi import Depends, FastAPI
from userharbor import UserHarbor
from userharbor_fastapi import UserHarborFastAPI


harbor = UserHarbor(
    secret_key="your-secret-key",
    store=store,
    email_sender=email_sender,
)

auth = UserHarborFastAPI(harbor)

app = FastAPI()
app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.get("/me")
def me(user=Depends(auth.current_user)):
    return user


@app.get("/admin")
def admin(user=Depends(auth.require_role("admin"))):
    return user


@app.get("/billing")
def billing(user=Depends(auth.require_permission("billing.read"))):
    return user
```

For real applications, configure `UserHarbor` with a concrete `UserStore` and
`EmailSender`, such as the official SQLAlchemy and SMTP integrations.

---

## Built-in routes

The adapter exposes account routes through `auth.router`:

```text
POST   /register
POST   /verify-email
POST   /resend-verification
POST   /login
POST   /logout
POST   /logout-all
GET    /me
POST   /password-reset/request
POST   /password-reset/confirm
POST   /password/change
DELETE /account
```

Mount the router under the prefix used by your application:

```python
app.include_router(auth.router, prefix="/auth", tags=["auth"])
```

---

## Authentication

`POST /login` returns a bearer-compatible token response:

```json
{
  "access_token": "session-token",
  "token_type": "bearer"
}
```

Send the session token on protected requests:

```http
Authorization: Bearer <session-token>
```

---

## Dependencies

Use `auth.current_user` for routes that require a valid session:

```python
@app.get("/account")
def account(user=Depends(auth.current_user)):
    return user
```

Use `auth.optional_user` when authentication should be optional:

```python
@app.get("/homepage")
def homepage(user=Depends(auth.optional_user)):
    return {"authenticated": user is not None}
```

Use role and permission dependencies for authorization:

```python
@app.get("/admin")
def admin(user=Depends(auth.require_role("admin"))):
    return user


@app.get("/invoices")
def invoices(user=Depends(auth.require_permission("billing.invoices.read"))):
    return user
```

---

## User serialization

By default, `/me` returns:

```json
{
  "username": "jane",
  "email": "jane@example.com",
  "verified": true
}
```

Pass `user_serializer` when your application wants to expose a different public
user shape:

```python
auth = UserHarborFastAPI(
    harbor,
    user_serializer=lambda user: {
        "username": user.username,
        "email": user.email,
        "verified": user.verified,
        "display_name": user.display_name,
    },
)
```

---

## Error responses

UserHarbor exceptions are converted into structured HTTP errors:

```json
{
  "detail": {
    "detail": "Invalid username or password",
    "code": "invalid_credentials"
  }
}
```

Authentication failures return `401`, authorization failures return `403`,
unknown roles and permissions return `404`, validation errors return `400`, and
username conflicts return `409`.

---

## License

UserHarbor FastAPI is released under the MIT License.
