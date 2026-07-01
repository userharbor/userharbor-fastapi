from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)
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

ErrorPayload = dict[str, str]


ERROR_CODES: dict[type[UserHarborError], str] = {
    InvalidCredentialsError: "invalid_credentials",
    InvalidEmailError: "invalid_email",
    InvalidPasswordResetTokenError: "invalid_password_reset_token",
    InvalidPermissionError: "invalid_permission",
    InvalidRoleError: "invalid_role",
    InvalidSessionTokenError: "invalid_session_token",
    InvalidUsernameError: "invalid_username",
    InvalidVerificationTokenError: "invalid_verification_token",
    PermissionDeniedError: "permission_denied",
    UnknownPermissionError: "unknown_permission",
    UnknownRoleError: "unknown_role",
    UnverifiedUserError: "unverified_user",
    WeakPasswordError: "weak_password",
}


def get_status_code(error: UserHarborError) -> int:
    if isinstance(error, (InvalidCredentialsError, InvalidSessionTokenError)):
        return HTTP_401_UNAUTHORIZED
    if isinstance(error, (PermissionDeniedError, UnverifiedUserError)):
        return HTTP_403_FORBIDDEN
    if isinstance(error, (UnknownPermissionError, UnknownRoleError)):
        return HTTP_404_NOT_FOUND
    if isinstance(error, InvalidUsernameError) and "already exists" in str(error):
        return HTTP_409_CONFLICT
    return HTTP_400_BAD_REQUEST


def get_error_code(error: UserHarborError) -> str:
    for error_type, code in ERROR_CODES.items():
        if isinstance(error, error_type):
            return code
    return "userharbor_error"


def error_payload(error: UserHarborError) -> ErrorPayload:
    return {
        "detail": str(error) or error.__class__.__name__,
        "code": get_error_code(error),
    }


def userharbor_exception_handler(
    _request: Request, error: UserHarborError
) -> JSONResponse:
    return JSONResponse(
        status_code=get_status_code(error),
        content=error_payload(error),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        UserHarborError,
        userharbor_exception_handler,  # type: ignore[arg-type]
    )

