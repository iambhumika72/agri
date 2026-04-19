from __future__ import annotations

"""
api/auth.py
============
JWT-based authentication helpers for AgriSense API.
Guards endpoints with Bearer token verification.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = logging.getLogger(__name__)

# Optional JWT support — graceful fallback if python-jose not installed
try:
    from jose import JWTError, jwt
    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False
    log.warning("python-jose not installed. JWT auth is disabled — all requests will pass through.")

SECRET_KEY = os.environ.get("AGRISENSE_SECRET_KEY", "changeme-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.environ.get("TOKEN_EXPIRE_MINUTES", "60"))

security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT access token."""
    if not _JWT_AVAILABLE:
        return "jwt-disabled"
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    """
    FastAPI dependency: verifies Bearer token and returns decoded payload.
    If JWT is disabled (library missing or secret not set), passes all requests.
    """
    if not _JWT_AVAILABLE or SECRET_KEY == "changeme-in-production":
        log.debug("JWT auth bypassed (disabled in development mode).")
        return {"sub": "dev-user", "role": "admin"}

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
