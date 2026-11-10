"""
Cintamani Security & Token Verification Dependency.
Protects /api/v1/* endpoints by enforcing Bearer token authentication.
"""

from __future__ import annotations
import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import get_config

security_scheme = HTTPBearer(auto_error=False)


def verify_api_token(
    credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),
) -> str:
    """
    Validates Bearer token in the Authorization header.
    Returns the token if valid, otherwise raises 401 Unauthorized.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Expected format: Bearer <api_token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected_token = get_config().get("api_token")
    provided_token = credentials.credentials.strip()

    if not expected_token or not secrets.compare_digest(
        provided_token.encode("utf-8"), expected_token.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_token


def validate_token_string(token_str: str) -> bool:
    """Helper function to check token validity directly without FastAPI request."""
    expected_token = get_config().get("api_token")
    return bool(
        expected_token
        and secrets.compare_digest(
            token_str.strip().encode("utf-8"), expected_token.encode("utf-8")
        )
    )
