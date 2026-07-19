"""JWT auth with refresh token rotation + RBAC."""
import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from models import User, UserPublic, UserRole

JWT_SECRET = os.environ.get("JWT_SECRET", "cropvision-dev")
JWT_ALGO = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_MIN = int(os.environ.get("ACCESS_TOKEN_MINUTES", "60"))
REFRESH_DAYS = int(os.environ.get("REFRESH_TOKEN_DAYS", "30"))

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _make_token(sub: str, role: str, ttl: timedelta, kind: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "kind": kind,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def make_access(user_id: str, role: str) -> str:
    return _make_token(user_id, role, timedelta(minutes=ACCESS_MIN), "access")


def make_refresh(user_id: str, role: str) -> str:
    return _make_token(user_id, role, timedelta(days=REFRESH_DAYS), "refresh")


def decode_token(token: str, expected_kind: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("kind") != expected_kind:
        raise HTTPException(status_code=401, detail="Wrong token kind")
    return payload


async def current_user(token: Optional[str] = Depends(oauth2)) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token, "access")
    from server import get_db
    doc = await get_db().users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**doc)


def require_role(*roles: str):
    async def _dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _dep


def to_public(u: User) -> UserPublic:
    return UserPublic(id=u.id, email=u.email, name=u.name, role=u.role,
                      language=u.language, phone=u.phone,
                      cooperative_id=u.cooperative_id)
