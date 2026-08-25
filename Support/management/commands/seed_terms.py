"""
Seed published Terms of Service v1.0.0 in English and Kiswahili.

  python manage.py seed_terms
  python manage.py seed_terms --force   # rewrite bodies if version exists
"""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from Support.models import BodyFormat, DocumentType, LegalDocument, Locale

VERSION = "1.0.0"
EFFECTIVE = parse_datetime("2026-07-19T00:00:00+00:00") or timezone.now()
CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


class Command(BaseCommand):
    help = "Seed TERMS documents (en + sw) for version 1.0.0"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update title/body if the version+locale already exists",
        )

    def handle(self, *args, **options):
        force = options["force"]
        specs = [
            (Locale.EN, "Imani Community — Terms of Service", "terms_en_v1.txt"),
            (Locale.SW, "Imani Community — Masharti ya Huduma", "terms_sw_v1.txt"),
        ]
        for locale, title, filename in specs:
            body = (CONTENT_DIR / filename).read_text(encoding="utf-8")
            obj, created = LegalDocument.objects.get_or_create(
                document_type=DocumentType.TERMS,
                version=VERSION,
                locale=locale,
                defaults={
                    "title": title,
                    "body": body,
                    "body_format": BodyFormat.PLAIN,
                    "effective_at": EFFECTIVE,
                    "is_published": True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created TERMS {VERSION} [{locale}]"))
            elif force:
                obj.title = title
                obj.body = body
                obj.body_format = BodyFormat.PLAIN
                obj.effective_at = EFFECTIVE
                obj.is_published = True
                obj.save()
                self.stdout.write(self.style.WARNING(f"Updated TERMS {VERSION} [{locale}]"))
            else:
                self.stdout.write(f"Exists TERMS {VERSION} [{locale}] (use --force to rewrite)")
