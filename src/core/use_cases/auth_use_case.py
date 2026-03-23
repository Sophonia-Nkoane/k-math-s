from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import bcrypt

from core.ports.repositories import AuditRepoPort, UserRepoPort
from core.services.token_service import TokenService


class AuthUseCase:
    def __init__(
        self,
        user_repo: UserRepoPort,
        token_service: TokenService,
        audit_repo: Optional[AuditRepoPort] = None,
    ) -> None:
        self.user_repo = user_repo
        self.token_service = token_service
        self.audit_repo = audit_repo

    def login(self, username: str, password: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        user = self.user_repo.get_user_by_username(username)
        if not user:
            return None, "Invalid username or password"

        stored_password = str(user.get("password") or "")
        try:
            is_valid = bcrypt.checkpw(password.encode("utf-8"), stored_password.encode("utf-8"))
        except ValueError:
            # Legacy plain text fallback
            is_valid = stored_password == password

        if not is_valid:
            return None, "Invalid username or password"

        user_id = int(user.get("user_id")) if user.get("user_id") is not None else None
        role = str(user.get("role") or "user")
        access_token = self.token_service.issue_access_token(
            subject=username,
            role=role,
            user_id=user_id,
            minutes=60,
        )
        refresh_token = self.token_service.issue_refresh_token(
            subject=username,
            role=role,
            user_id=user_id,
            days=7,
        )

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=user_id,
                action_type="LOGIN",
                object_type="User",
                object_id=username,
                details="User authenticated through shared AuthUseCase",
            )

        return {
            "user_id": user_id,
            "username": username,
            "role": role,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,
        }, None

    def refresh(self, refresh_token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            claims = self.token_service.decode_token(refresh_token)
        except Exception:
            return None, "Invalid refresh token"

        if claims.get("typ") != "refresh":
            return None, "Invalid refresh token type"

        username = str(claims.get("sub") or "")
        role = str(claims.get("role") or "user")
        user_id = claims.get("user_id")

        token = self.token_service.issue_access_token(
            subject=username,
            role=role,
            user_id=user_id,
            minutes=60,
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 3600,
        }, None

    def verify_access_token(self, token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            claims = self.token_service.decode_token(token)
        except Exception:
            return None, "Invalid token"

        if claims.get("typ") != "access":
            return None, "Invalid token type"

        return claims, None

    def verify_user_password(self, user_id: int, password: str) -> bool:
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return False
        stored_password = str(user.get("password") or "")
        try:
            return bool(bcrypt.checkpw(password.encode("utf-8"), stored_password.encode("utf-8")))
        except ValueError:
            return stored_password == password
