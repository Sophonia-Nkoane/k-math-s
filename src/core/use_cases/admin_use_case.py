from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import bcrypt

from core.ports.repositories import AuditRepoPort, UserRepoPort
from core.use_cases.pagination import sort_and_paginate


class AdminUseCase:
    def __init__(self, user_repo: UserRepoPort, audit_repo: Optional[AuditRepoPort] = None) -> None:
        self.user_repo = user_repo
        self.audit_repo = audit_repo

    @staticmethod
    def _is_admin(role: Optional[str]) -> bool:
        return str(role or "").lower() == "admin"

    def list_users(self, exclude_username: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.user_repo.list_users(exclude_username=exclude_username)

    def list_users_paged(
        self,
        exclude_username: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "username",
        sort_dir: str = "asc",
    ) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
        rows = self.list_users(exclude_username=exclude_username)
        return sort_and_paginate(rows, sort_by=sort_by, sort_dir=sort_dir, page=page, page_size=page_size)

    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        actor_user_id: Optional[int] = None,
        actor_role: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        if not self._is_admin(actor_role):
            return False, "Admin role required"
        if not username or not password:
            return False, "username and password are required"
        role_normalized = str(role or "user").lower()
        if role_normalized not in {"admin", "user"}:
            return False, "role must be admin or user"
        if self.user_repo.get_user_by_username(username):
            return False, "Username already exists"

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        self.user_repo.create_user(username=username, password_hash=password_hash, role=role_normalized)

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=actor_user_id,
                action_type="CREATE_USER",
                object_type="User",
                object_id=username,
                details=f"Created user with role={role_normalized}",
            )
        return True, None

    def update_user_password(
        self,
        username: str,
        new_password: str,
        actor_user_id: Optional[int] = None,
        actor_role: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        if not self._is_admin(actor_role):
            return False, "Admin role required"
        if not username or not new_password:
            return False, "username and new_password are required"
        if not self.user_repo.get_user_by_username(username):
            return False, "User not found"

        password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        ok = self.user_repo.update_user_password(username=username, password_hash=password_hash)
        if not ok:
            return False, "Failed to update user password"

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=actor_user_id,
                action_type="UPDATE_USER_PASSWORD",
                object_type="User",
                object_id=username,
                details="Updated user password",
            )
        return True, None

    def update_user(
        self,
        username: str,
        role: Optional[str] = None,
        new_password: Optional[str] = None,
        actor_user_id: Optional[int] = None,
        actor_role: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        if not self._is_admin(actor_role):
            return False, "Admin role required"
        if not username:
            return False, "username is required"

        target = self.user_repo.get_user_by_username(username)
        if not target:
            return False, "User not found"

        details: List[str] = []
        normalized_role = None
        if role is not None:
            normalized_role = str(role or "").lower()
            if normalized_role not in {"admin", "user"}:
                return False, "role must be admin or user"
            current_role = str(target.get("role") or "user").lower()
            if current_role == "admin" and normalized_role != "admin" and self.user_repo.count_admin_users() <= 1:
                return False, "Cannot demote the last admin account"
            if normalized_role != current_role:
                ok = self.user_repo.update_user_role(username=username, role=normalized_role)
                if not ok:
                    return False, "Failed to update user role"
                details.append(f"Updated role to {normalized_role}")

        if new_password:
            password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            ok = self.user_repo.update_user_password(username=username, password_hash=password_hash)
            if not ok:
                return False, "Failed to update user password"
            details.append("Updated user password")

        if not details:
            return False, "No changes supplied"

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=actor_user_id,
                action_type="UPDATE_USER",
                object_type="User",
                object_id=username,
                details="; ".join(details),
            )
        return True, None

    def delete_user(
        self,
        username: str,
        actor_username: Optional[str],
        actor_user_id: Optional[int] = None,
        actor_role: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        if not self._is_admin(actor_role):
            return False, "Admin role required"
        if not username:
            return False, "username is required"
        if actor_username and username == actor_username:
            return False, "You cannot delete your own account"

        target = self.user_repo.get_user_by_username(username)
        if not target:
            return False, "User not found"

        # Prevent deleting the last admin account.
        if self._is_admin(target.get("role")) and self.user_repo.count_admin_users() <= 1:
            return False, "Cannot delete the last admin account"

        ok = self.user_repo.delete_user(username=username)
        if not ok:
            return False, "Failed to delete user"

        if self.audit_repo:
            self.audit_repo.log_action(
                user_id=actor_user_id,
                action_type="DELETE_USER",
                object_type="User",
                object_id=username,
                details="Deleted user",
            )
        return True, None
