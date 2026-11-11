from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Query, Request
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .config import JWT_ALG, JWT_SECRET, JWT_TTL_MIN
from .db import get_db
from .models import User

hasher = PasswordHash.recommended()


def hash_password(p: str) -> str:
    return hasher.hash(p)


def verify_password(p: str, h: str) -> bool:
    return hasher.verify(p, h)


def make_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_TTL_MIN)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, JWT_SECRET, algorithm=JWT_ALG)


def _user_from_token(token: str, db: Session) -> User:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user = db.get(User, int(data["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        user = None
    if user is None:
        raise HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    return user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPException(401, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    return _user_from_token(token, db)


def user_from_query_token(token: str = Query(...), db: Session = Depends(get_db)) -> User:
    """EventSource cannot send headers, so the SSE stream accepts the token as a query parameter."""
    return _user_from_token(token, db)


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    return user
