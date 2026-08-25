"""
Profile name updates — single writer for first_name / second_name.

Conflict policy (production default):
  - Client may send base_version (last known ResourceVersion for profile).
  - If base_version is stale (server version advanced), raise ConflictError.
  - Server wins: client must re-GET profile and optionally re-submit as a new mutation.

Idempotency:
  - mutation_id (UUID) is remembered in Redis for 24h; replays return the same success payload.

Offline clients:
  - Same endpoint is used when the queue drains; no separate offline API.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import redis
from django.db import transaction

from datasync.utils import bump_version, get_or_create_version
from Loginandauthentication.models import CustomUser

from .exceptions import ConflictError, SettingsError, ValidationError

# Shared Redis (same host pattern as OTP). Decode responses for JSON convenience.
_redis = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

MUTATION_TTL_SECONDS = 60 * 60 * 24  # 24 hours
NAME_MAX_LEN = 50
# Letters, spaces, hyphen, apostrophe — keep tight for production identity fields.
NAME_PATTERN = re.compile(r"^[\w\s\-'.]+$", re.UNICODE)


class ProfileService:
    """Authoritative name mutation path for /api/settings/profile/name/."""

    @staticmethod
    def get_profile_snapshot(user: CustomUser) -> dict[str, Any]:
        """Build API-facing profile projection + version for clients and Room."""
        version = get_or_create_version("profile", user.pk)
        return {
            "user_id": user.pk,
            "first_name": user.first_name,
            "second_name": user.second_name,
            "phone_number": user.phone_number,
            "email": user.email,
            "is_driver": user.is_driver,
            "profile_version": version.version,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }

    @classmethod
    def update_name(
        cls,
        user: CustomUser,
        *,
        first_name: str,
        second_name: str,
        mutation_id: str,
        base_version: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Apply name change under version + idempotency rules.

        Returns snapshot dict including profile_version after bump.
        """
        mutation_id = (mutation_id or "").strip()
        if not mutation_id:
            raise ValidationError("mutation_id is required", code="mutation_id_required")

        # --- Idempotent replay (same mutation_id) ---
        cache_key = f"profile_mutation:{mutation_id}"
        cached = _redis.get(cache_key)
        if cached:
            return json.loads(cached)

        first = cls._clean_name(first_name, "first_name")
        second = cls._clean_name(second_name, "second_name")

        with transaction.atomic():
            # Lock user row so concurrent name edits serialize.
            locked = CustomUser.objects.select_for_update().get(pk=user.pk)
            current_version = get_or_create_version("profile", locked.pk).version

            # Optimistic concurrency: offline client must not clobber a newer server state.
            if base_version is not None and int(base_version) != int(current_version):
                raise ConflictError(
                    "Profile was updated on the server. Re-fetch profile (server wins).",
                    code="version_conflict",
                )

            locked.first_name = first
            locked.second_name = second
            locked.save(update_fields=["first_name", "second_name", "updated_at"])

            # Single version stream shared with datasync rehydrate.
            bumped = bump_version("profile", locked.pk)
            snapshot = {
                "user_id": locked.pk,
                "first_name": locked.first_name,
                "second_name": locked.second_name,
                "phone_number": locked.phone_number,
                "email": locked.email,
                "is_driver": locked.is_driver,
                "profile_version": bumped.version,
                "mutation_id": mutation_id,
                "updated_at": locked.updated_at.isoformat() if locked.updated_at else None,
            }

        _redis.set(cache_key, json.dumps(snapshot), ex=MUTATION_TTL_SECONDS)
        return snapshot

    @staticmethod
    def _clean_name(value: str, field: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValidationError(f"{field} is required", code="name_required")
        if len(text) > NAME_MAX_LEN:
            raise ValidationError(
                f"{field} must be at most {NAME_MAX_LEN} characters",
                code="name_too_long",
            )
        if not NAME_PATTERN.match(text):
            raise ValidationError(
                f"{field} contains invalid characters",
                code="name_invalid_chars",
            )
        return text
