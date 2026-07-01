import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from userharbor import UserHarbor

from fakes import InMemoryUserStore, SpyEmailSender
from userharbor_fastapi import UserHarborFastAPI

VALID_USERNAME = "janek123"
VALID_EMAIL = "janek@example.com"
VALID_PASSWORD = "Strongpass1!"
NEW_PASSWORD = "NewStrongpass1!"
SECRET_KEY = "test-secret-key"


@pytest.fixture
def store() -> InMemoryUserStore:
    return InMemoryUserStore()


@pytest.fixture
def email_sender() -> SpyEmailSender:
    return SpyEmailSender()


@pytest.fixture
def harbor(
    store: InMemoryUserStore,
    email_sender: SpyEmailSender,
) -> UserHarbor:
    return UserHarbor(SECRET_KEY, store, email_sender)


@pytest.fixture
def auth(harbor: UserHarbor) -> UserHarborFastAPI:
    return UserHarborFastAPI(harbor)


@pytest.fixture
def app(auth: UserHarborFastAPI) -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router, prefix="/auth")

    @app.get("/protected")
    def protected(user=Depends(auth.current_user)):
        return user

    @app.get("/optional-user")
    def optional_user(user=Depends(auth.optional_user)):
        return user

    @app.get("/admin")
    def admin(user=Depends(auth.require_role("admin"))):
        return user

    @app.get("/invalid-role")
    def invalid_role(user=Depends(auth.require_role("Admin"))):
        return user

    @app.get("/invalid-permission")
    def invalid_permission(user=Depends(auth.require_permission("billing"))):
        return user

    @app.get("/billing")
    def billing(user=Depends(auth.require_permission("billing.read"))):
        return user

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)
