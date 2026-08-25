"""
Phone change state machine (online only).

  request → Redis challenge + OTP to NEW number
  confirm → verify OTP → swap CustomUser.phone_number → bump profile version

Phone is the login identity. It must NEVER be changed offline or without OTP.
Local clients may show a draft pending number only after request; final phone
is applied only after confirm success.

Redis keys:
  phone_change:user:{user_id}  → challenge payload (TTL)
  phone_change:mutation:{mutation_id} → idempotent confirm result
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

import redis
from django.db import transaction

from datasync.utils import bump_version, get_or_create_version
from Loginandauthentication.finalOTP import OTP
from Loginandauthentication.models import CustomUser
from Loginandauthentication.whatsappOTP import normalize_phone_number

from .exceptions import ChallengeError, PhoneTakenError, ValidationError

_redis = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

CHALLENGE_TTL_SECONDS = 600  # 10 minutes
MUTATION_TTL_SECONDS = 60 * 60 * 24
MAX_OTP_ATTEMPTS = 5


class PhoneChangeService:
    """Authoritative phone mutation path for /api/settings/profile/phone/*."""

    @classmethod
    def request_change(
        cls,
        user: CustomUser,
        *,
        new_phone_number: str,
        mutation_id: str,
    ) -> dict[str, Any]:
        """
        Start phone change: validate uniqueness, store challenge, SMS OTP to new number.
        Does not modify CustomUser yet.
        """
        mutation_id = (mutation_id or "").strip()
        if not mutation_id:
            raise ValidationError("mutation_id is required", code="mutation_id_required")

        try:
            new_phone = normalize_phone_number((new_phone_number or "").strip())
        except Exception as exc:
            raise ValidationError(f"Invalid phone number: {exc}", code="phone_invalid") from exc

        current = normalize_phone_number(user.phone_number)
        if new_phone == current:
            raise ValidationError(
                "New phone number must be different from the current number.",
                code="phone_unchanged",
            )

        # Uniqueness: another account already owns this number.
        if CustomUser.objects.filter(phone_number=new_phone).exclude(pk=user.pk).exists():
            raise PhoneTakenError(
                "This phone number is already registered to another account.",
            )

        # Supersede any prior in-flight challenge for this user.
        challenge_id = str(uuid.uuid4())
        otp = OTP.GenerateOTP()
        payload = {
            "challenge_id": challenge_id,
            "user_id": user.pk,
            "new_phone": new_phone,
            "otp": otp,
            "mutation_id": mutation_id,
            "attempts": 0,
        }
        _redis.set(
            cls._user_challenge_key(user.pk),
            json.dumps(payload),
            ex=CHALLENGE_TTL_SECONDS,
        )

        # OTP only to the NEW number — user must control that handset.
        OTP.send_otp("sms", new_phone, otp)

        return {
            "challenge_id": challenge_id,
            "expires_in": CHALLENGE_TTL_SECONDS,
            "masked_destination": cls._mask_phone(new_phone),
            "mutation_id": mutation_id,
            # Debug-friendly in non-prod only would strip otp; we do not return otp.
        }

    @classmethod
    def confirm_change(
        cls,
        user: CustomUser,
        *,
        challenge_id: str,
        otp: str,
        mutation_id: str,
    ) -> dict[str, Any]:
        """
        Verify OTP and commit phone change. Idempotent on mutation_id after success.
        """
        mutation_id = (mutation_id or "").strip()
        challenge_id = (challenge_id or "").strip()
        otp = (otp or "").strip()
        if not mutation_id or not challenge_id or not otp:
            raise ValidationError(
                "challenge_id, otp, and mutation_id are required",
                code="confirm_fields_required",
            )

        # Idempotent confirm (network retry after success).
        mut_key = f"phone_change:mutation:{mutation_id}"
        cached = _redis.get(mut_key)
        if cached:
            return json.loads(cached)

        raw = _redis.get(cls._user_challenge_key(user.pk))
        if not raw:
            raise ChallengeError(
                "Phone change challenge expired or not found. Request a new code.",
                code="challenge_expired",
            )

        data = json.loads(raw)
        if data.get("challenge_id") != challenge_id:
            raise ChallengeError(
                "Challenge does not match. Request a new code.",
                code="challenge_mismatch",
            )
        if int(data.get("user_id")) != int(user.pk):
            raise ChallengeError("Challenge does not belong to this user.", code="challenge_user")
        if data.get("mutation_id") != mutation_id:
            raise ChallengeError(
                "mutation_id does not match the pending challenge.",
                code="mutation_mismatch",
            )

        attempts = int(data.get("attempts") or 0) + 1
        data["attempts"] = attempts
        if attempts > MAX_OTP_ATTEMPTS:
            _redis.delete(cls._user_challenge_key(user.pk))
            raise ChallengeError(
                "Too many incorrect OTP attempts. Request a new code.",
                code="otp_attempts_exceeded",
                status=429,
            )

        if str(data.get("otp")) != str(otp):
            # Persist attempt counter with remaining TTL.
            ttl = _redis.ttl(cls._user_challenge_key(user.pk))
            _redis.set(
                cls._user_challenge_key(user.pk),
                json.dumps(data),
                ex=ttl if ttl and ttl > 0 else CHALLENGE_TTL_SECONDS,
            )
            raise ChallengeError("Invalid OTP.", code="otp_invalid")

        new_phone = data["new_phone"]

        with transaction.atomic():
            locked = CustomUser.objects.select_for_update().get(pk=user.pk)
            # Re-check uniqueness under lock.
            if (
                CustomUser.objects.filter(phone_number=new_phone)
                .exclude(pk=locked.pk)
                .exists()
            ):
                raise PhoneTakenError(
                    "This phone number was taken before confirmation completed.",
                )

            locked.phone_number = new_phone
            locked.save(update_fields=["phone_number", "updated_at"])
            bumped = bump_version("profile", locked.pk)

            snapshot = {
                "user_id": locked.pk,
                "phone_number": locked.phone_number,
                "first_name": locked.first_name,
                "second_name": locked.second_name,
                "email": locked.email,
                "is_driver": locked.is_driver,
                "profile_version": bumped.version,
                "mutation_id": mutation_id,
                "updated_at": locked.updated_at.isoformat() if locked.updated_at else None,
            }

        _redis.delete(cls._user_challenge_key(user.pk))
        _redis.set(mut_key, json.dumps(snapshot), ex=MUTATION_TTL_SECONDS)
        return snapshot

    @staticmethod
    def _user_challenge_key(user_id: int) -> str:
        return f"phone_change:user:{user_id}"

    @staticmethod
    def _mask_phone(phone: str) -> str:
        if len(phone) < 4:
            return "****"
        return phone[:3] + "****" + phone[-2:]
