"""
Legal documents and user acceptances.

Designed for evolution:
  - document_type allows TERMS today, PRIVACY (or others) tomorrow without new tables
  - body_format allows plain → markdown → html without API renames
  - acceptance is keyed by (user, document_type, version) so locale is presentation only
"""

from django.conf import settings
from django.db import models


class DocumentType(models.TextChoices):
    TERMS = "TERMS", "Terms of Service"
    PRIVACY = "PRIVACY", "Privacy Policy"


class Locale(models.TextChoices):
    EN = "en", "English"
    SW = "sw", "Kiswahili"


class BodyFormat(models.TextChoices):
    PLAIN = "plain", "Plain text"
    MARKDOWN = "markdown", "Markdown"
    HTML = "html", "HTML"


class LegalDocument(models.Model):
    """
    One localized edition of a legal document version.

    Example: version 1.0.0 exists as two rows (en + sw). Accepting either
    counts as accepting that version for the document_type.
    """

    document_type = models.CharField(
        max_length=32,
        choices=DocumentType.choices,
        db_index=True,
    )
    version = models.CharField(max_length=32, db_index=True)
    locale = models.CharField(
        max_length=8,
        choices=Locale.choices,
        default=Locale.EN,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    body_format = models.CharField(
        max_length=16,
        choices=BodyFormat.choices,
        default=BodyFormat.PLAIN,
    )
    effective_at = models.DateTimeField()
    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document_type", "version", "locale"],
                name="uniq_legal_doc_type_version_locale",
            ),
        ]
        indexes = [
            models.Index(fields=["document_type", "is_published", "locale"]),
        ]

    def __str__(self):
        return f"{self.document_type} v{self.version} [{self.locale}]"


class LegalAcceptance(models.Model):
    """
    Immutable acceptance record. Re-accepting the same version is idempotent
    at the service layer (no duplicate rows for same user/type/version).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="legal_acceptances",
    )
    document_type = models.CharField(
        max_length=32,
        choices=DocumentType.choices,
        db_index=True,
    )
    version = models.CharField(max_length=32, db_index=True)
    locale = models.CharField(
        max_length=8,
        choices=Locale.choices,
        help_text="Locale the user was viewing when they accepted.",
    )
    accepted_at = models.DateTimeField(auto_now_add=True)
    platform = models.CharField(max_length=32, blank=True, default="")
    app_version = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        ordering = ["-accepted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "document_type", "version"],
                name="uniq_legal_accept_user_type_version",
            ),
        ]

    def __str__(self):
        return f"user={self.user_id} {self.document_type} v{self.version}"
