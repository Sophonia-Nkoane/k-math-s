from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt


class TokenService:
    def __init__(self, secret: Optional[str] = None, algorithm: str = "HS256") -> None:
        self.secret = secret or os.getenv("KMATHS_JWT_SECRET", "change-me-in-production")
        self.algorithm = algorithm

    def issue_access_token(
        self,
        subject: str,
        role: str,
        user_id: Optional[int],
        minutes: int = 60,
        extra_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "sub": subject,
            "role": role,
            "user_id": user_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=minutes)).timestamp()),
            "typ": "access",
        }
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def issue_refresh_token(
        self,
        subject: str,
        role: str,
        user_id: Optional[int],
        days: int = 7,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "role": role,
            "user_id": user_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=days)).timestamp()),
            "typ": "refresh",
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Dict[str, Any]:
        return jwt.decode(token, self.secret, algorithms=[self.algorithm])
