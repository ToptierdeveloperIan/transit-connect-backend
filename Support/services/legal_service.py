"""
Legal document domain logic.

Views stay thin; all rules live here so we can refactor storage/format later
without rewriting API contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone

from Support.models import DocumentType, LegalAcceptance, LegalDocument, Locale


class LegalError(Exception):
    """Base domain error for legal operations."""

    code = "legal_error"
    status = 400

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class DocumentNotFoundError(LegalError):
    code = "document_not_found"
    status = 404


class VersionMismatchError(LegalError):
    code = "version_mismatch"
    status = 400


class InvalidLocaleError(LegalError):
    code = "invalid_locale"
    status = 400


@dataclass(frozen=True)
class AcceptanceStatus:
    document_type: str
    current_version: Optional[str]
    accepted_version: Optional[str]
    must_accept: bool
    accepted_at: Optional[str]


class LegalService:
    DEFAULT_LOCALE = Locale.EN
    FALLBACK_LOCALE = Locale.EN

    @staticmethod
    def normalize_locale(locale: Optional[str]) -> str:
        if not locale:
            return LegalService.DEFAULT_LOCALE
        value = locale.strip().lower()
        # Accept BCP-47 style prefixes: sw-KE → sw
        if "-" in value:
            value = value.split("-", 1)[0]
        valid = {c.value for c in Locale}
        if value not in valid:
            raise InvalidLocaleError(
                f"Unsupported locale '{locale}'. Supported: {sorted(valid)}"
            )
        return value

    @staticmethod
    def normalize_document_type(document_type: Optional[str]) -> str:
        if not document_type:
            return DocumentType.TERMS
        value = document_type.strip().upper()
        valid = {c.value for c in DocumentType}
        if value not in valid:
            raise LegalError(
                f"Unsupported document_type '{document_type}'. Supported: {sorted(valid)}",
                code="invalid_document_type",
            )
        return value

    @classmethod
    def get_current_document(
        cls,
        document_type: Optional[str] = None,
        locale: Optional[str] = None,
        *,
        allow_fallback: bool = True,
    ) -> LegalDocument:
        doc_type = cls.normalize_document_type(document_type)
        loc = cls.normalize_locale(locale)

        qs = LegalDocument.objects.filter(
            document_type=doc_type,
            is_published=True,
            locale=loc,
            effective_at__lte=timezone.now(),
        ).order_by("-effective_at", "-id")

        doc = qs.first()
        if doc is None and allow_fallback and loc != cls.FALLBACK_LOCALE:
            doc = LegalDocument.objects.filter(
                document_type=doc_type,
                is_published=True,
                locale=cls.FALLBACK_LOCALE,
                effective_at__lte=timezone.now(),
            ).order_by("-effective_at", "-id").first()

        if doc is None:
            raise DocumentNotFoundError(
                f"No published {doc_type} document for locale '{loc}'."
            )
        return doc

    @classmethod
    def get_status(cls, user, document_type: Optional[str] = None) -> AcceptanceStatus:
        doc_type = cls.normalize_document_type(document_type)
        try:
            current = cls.get_current_document(doc_type, cls.DEFAULT_LOCALE)
            current_version = current.version
        except DocumentNotFoundError:
            return AcceptanceStatus(
                document_type=doc_type,
                current_version=None,
                accepted_version=None,
                must_accept=False,
                accepted_at=None,
            )

        acceptance = (
            LegalAcceptance.objects.filter(
                user=user,
                document_type=doc_type,
                version=current_version,
            )
            .order_by("-accepted_at")
            .first()
        )

        if acceptance is not None:
            return AcceptanceStatus(
                document_type=doc_type,
                current_version=current_version,
                accepted_version=acceptance.version,
                must_accept=False,
                accepted_at=acceptance.accepted_at.isoformat(),
            )

        latest_any = (
            LegalAcceptance.objects.filter(user=user, document_type=doc_type)
            .order_by("-accepted_at")
            .first()
        )
        return AcceptanceStatus(
            document_type=doc_type,
            current_version=current_version,
            accepted_version=latest_any.version if latest_any else None,
            must_accept=True,
            accepted_at=latest_any.accepted_at.isoformat() if latest_any else None,
        )

    @classmethod
    @transaction.atomic
    def accept(
        cls,
        user,
        *,
        version: str,
        locale: Optional[str] = None,
        document_type: Optional[str] = None,
        platform: str = "",
        app_version: str = "",
    ) -> LegalAcceptance:
        doc_type = cls.normalize_document_type(document_type)
        loc = cls.normalize_locale(locale)
        version = (version or "").strip()
        if not version:
            raise LegalError("version is required", code="version_required")

        # Ensure this version exists as a published document (any locale of that version)
        published = LegalDocument.objects.filter(
            document_type=doc_type,
            version=version,
            is_published=True,
        ).exists()
        if not published:
            raise VersionMismatchError(
                f"Version '{version}' is not a published {doc_type} document."
            )

        current = cls.get_current_document(doc_type, loc)
        if current.version != version:
            raise VersionMismatchError(
                f"Only the current version can be accepted. "
                f"Current is '{current.version}', got '{version}'."
            )

        existing = LegalAcceptance.objects.filter(
            user=user,
            document_type=doc_type,
            version=version,
        ).first()
        if existing is not None:
            return existing

        return LegalAcceptance.objects.create(
            user=user,
            document_type=doc_type,
            version=version,
            locale=loc,
            platform=(platform or "")[:32],
            app_version=(app_version or "")[:32],
        )
