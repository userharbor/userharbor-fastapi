from collections.abc import Callable
from typing import Any, Generic

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.status import HTTP_201_CREATED, HTTP_401_UNAUTHORIZED
from userharbor import UserHarbor
from userharbor.exceptions import UserHarborError
from userharbor.interfaces import UserT

from .errors import error_payload, get_status_code, register_exception_handlers
from .schemas import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    ResendVerificationRequest,
    TokenResponse,
    VerifyEmailRequest,
)

UserSerializer = Callable[[UserT], Any]
bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


def default_user_serializer(user: UserT) -> dict[str, object]:
    return {
        "username": user.username,
        "email": user.email,
        "verified": user.verified,
    }


def bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return credentials.credentials


class UserHarborFastAPI(Generic[UserT]):
    def __init__(
        self,
        harbor: UserHarbor[UserT],
        *,
        user_serializer: UserSerializer[UserT] | None = None,
    ) -> None:
        self.harbor = harbor
        self.user_serializer = user_serializer or default_user_serializer
        self.router = APIRouter()
        self._register_routes()

    register_exception_handlers = staticmethod(register_exception_handlers)
    session_token = staticmethod(bearer_token)

    def current_user(self, token: str = Depends(bearer_token)) -> UserT:
        try:
            return self.harbor.get_current_user(token)
        except UserHarborError as error:
            raise _as_http_exception(error) from error

    def optional_user(
        self,
        credentials: HTTPAuthorizationCredentials | None = Depends(
            optional_bearer_scheme
        ),
    ) -> UserT | None:
        if credentials is None:
            return None
        try:
            return self.harbor.get_current_user(credentials.credentials)
        except UserHarborError:
            return None

    def require_role(self, role: str) -> Callable[[str], UserT]:
        def dependency(token: str = Depends(bearer_token)) -> UserT:
            try:
                return self.harbor.require_role(token, role)
            except UserHarborError as error:
                raise _as_http_exception(error) from error

        return dependency

    def require_permission(self, permission: str) -> Callable[[str], UserT]:
        def dependency(token: str = Depends(bearer_token)) -> UserT:
            try:
                return self.harbor.require_permission(token, permission)
            except UserHarborError as error:
                raise _as_http_exception(error) from error

        return dependency

    def _register_routes(self) -> None:
        def me_route(user: UserT = Depends(self.current_user)) -> Any:
            return self.me(user)

        self.router.add_api_route(
            "/register",
            self.register,
            methods=["POST"],
            response_model=MessageResponse,
            status_code=HTTP_201_CREATED,
        )
        self.router.add_api_route(
            "/verify-email",
            self.verify_email,
            methods=["POST"],
            response_model=MessageResponse,
        )
        self.router.add_api_route(
            "/resend-verification",
            self.resend_verification,
            methods=["POST"],
            response_model=MessageResponse,
        )
        self.router.add_api_route(
            "/login",
            self.login,
            methods=["POST"],
            response_model=TokenResponse,
        )
        self.router.add_api_route(
            "/logout",
            self.logout,
            methods=["POST"],
            response_model=MessageResponse,
        )
        self.router.add_api_route(
            "/logout-all",
            self.logout_all,
            methods=["POST"],
            response_model=MessageResponse,
        )
        self.router.add_api_route("/me", me_route, methods=["GET"])
        self.router.add_api_route(
            "/password-reset/request",
            self.request_password_reset,
            methods=["POST"],
            response_model=MessageResponse,
        )
        self.router.add_api_route(
            "/password-reset/confirm",
            self.confirm_password_reset,
            methods=["POST"],
            response_model=MessageResponse,
        )
        self.router.add_api_route(
            "/password/change",
            self.change_password,
            methods=["POST"],
            response_model=MessageResponse,
        )
        self.router.add_api_route(
            "/account",
            self.delete_account,
            methods=["DELETE"],
            response_model=MessageResponse,
        )

    def register(self, request: RegisterRequest) -> MessageResponse:
        try:
            self.harbor.register(request.username, request.email, request.password)
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return MessageResponse(detail="User registered")

    def verify_email(self, request: VerifyEmailRequest) -> MessageResponse:
        try:
            self.harbor.verify_email(request.token)
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return MessageResponse(detail="Email verified")

    def resend_verification(
        self, request: ResendVerificationRequest
    ) -> MessageResponse:
        try:
            self.harbor.resend_verification(request.email)
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return MessageResponse(detail="Verification email sent")

    def login(self, request: LoginRequest) -> TokenResponse:
        try:
            session_token = self.harbor.login(request.username, request.password)
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return TokenResponse(access_token=session_token)

    def logout(self, token: str = Depends(bearer_token)) -> MessageResponse:
        try:
            self.harbor.logout(token)
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return MessageResponse(detail="Logged out")

    def logout_all(self, token: str = Depends(bearer_token)) -> MessageResponse:
        try:
            self.harbor.logout_all(token)
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return MessageResponse(detail="Logged out from all sessions")

    def me(self, user: UserT) -> Any:
        return self.user_serializer(user)

    def request_password_reset(
        self, request: PasswordResetRequest
    ) -> MessageResponse:
        try:
            self.harbor.send_password_reset(request.email)
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return MessageResponse(detail="Password reset email sent")

    def confirm_password_reset(
        self, request: PasswordResetConfirmRequest
    ) -> MessageResponse:
        try:
            self.harbor.reset_password(request.new_password, request.token)
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return MessageResponse(detail="Password reset")

    def change_password(
        self,
        request: ChangePasswordRequest,
        token: str = Depends(bearer_token),
    ) -> MessageResponse:
        try:
            self.harbor.change_password(
                request.old_password, request.new_password, token
            )
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return MessageResponse(detail="Password changed")

    def delete_account(
        self,
        request: DeleteAccountRequest,
        token: str = Depends(bearer_token),
    ) -> MessageResponse:
        try:
            self.harbor.delete_account(request.password, token)
        except UserHarborError as error:
            raise _as_http_exception(error) from error
        return MessageResponse(detail="Account deleted")


def _as_http_exception(error: UserHarborError) -> HTTPException:
    return HTTPException(
        status_code=get_status_code(error),
        detail=error_payload(error),
    )
