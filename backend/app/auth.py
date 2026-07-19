from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import InvalidTokenError
from pydantic import BaseModel

from app.api_errors import AuthenticationConfigurationError
from app.services.workflow_repository import workspace_is_owned_by

DATAQUAY_INTERNAL_AUTH_SECRET_ENV = "DATAQUAY_INTERNAL_AUTH_SECRET"
TOKEN_ISSUER = "dataquay-next"
TOKEN_AUDIENCE = "dataquay-fastapi"
TOKEN_ALGORITHM = "HS256"
MAX_TOKEN_LIFETIME_SECONDS = 120

bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    user_id: int


def require_authenticated_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser:
    secret = _get_internal_auth_secret()
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        claims = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=[TOKEN_ALGORITHM],
            audience=TOKEN_AUDIENCE,
            issuer=TOKEN_ISSUER,
            leeway=5,
            options={"require": ["sub", "iat", "exp", "iss", "aud"]},
        )
        subject = claims["sub"]
        issued_at = int(claims["iat"])
        expires_at = int(claims["exp"])
        if (
            not isinstance(subject, str)
            or not subject.isdecimal()
            or int(subject) <= 0
            or expires_at <= issued_at
            or expires_at - issued_at > MAX_TOKEN_LIFETIME_SECONDS
        ):
            raise InvalidTokenError("Invalid DataQuay identity claims.")
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise _unauthorized() from None

    return AuthenticatedUser(user_id=int(subject))


CurrentUser = Annotated[AuthenticatedUser, Depends(require_authenticated_user)]


def require_workspace_owner(
    dataset_id: str,
    user: CurrentUser,
) -> AuthenticatedUser:
    if not workspace_is_owned_by(dataset_id, user.user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset workspace was not found.",
        )
    return user


WorkspaceOwner = Annotated[AuthenticatedUser, Depends(require_workspace_owner)]


def _get_internal_auth_secret() -> str:
    import os

    secret = os.getenv(DATAQUAY_INTERNAL_AUTH_SECRET_ENV, "").strip()
    if len(secret.encode("utf-8")) < 32:
        raise AuthenticationConfigurationError(
            "DATAQUAY_INTERNAL_AUTH_SECRET must be configured with at least 32 bytes."
        )
    return secret


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid authenticated identity is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
