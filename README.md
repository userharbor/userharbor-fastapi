# userharbor-fastapi

FastAPI integration for
[UserHarbor](https://github.com/userharbor/userharbor).

## Installation

```bash
pip install userharbor-fastapi
```

## Basic usage

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

The built-in router exposes:

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

Authentication uses bearer session tokens:

```http
Authorization: Bearer <session-token>
```
