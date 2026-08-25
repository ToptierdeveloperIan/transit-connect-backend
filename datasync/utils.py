import hashlib
from datetime import timezone as datetime_timezone

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import ResourceVersion


def normalize_resource_id(resource_id=None):
    if resource_id is None:
        return ""
    return str(resource_id)


def generate_etag(content):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return f'"{hashlib.md5(content).hexdigest()}"'


def get_or_create_version(resource_type, resource_id=None):
    resource_id = normalize_resource_id(resource_id)
    version, _ = ResourceVersion.objects.get_or_create(
        resource_type=resource_type,
        resource_id=resource_id,
        defaults={"version": 0},
    )
    return version


def bump_version(resource_type, resource_id=None):
    resource_id = normalize_resource_id(resource_id)
    with transaction.atomic():
        version, _ = ResourceVersion.objects.select_for_update().get_or_create(
            resource_type=resource_type,
            resource_id=resource_id,
            defaults={"version": 0},
        )
        ResourceVersion.objects.filter(pk=version.pk).update(version=F("version") + 1)
        version.refresh_from_db()
        return version


def parse_since_param(value):
    if not value:
        return None

    parsed = parse_datetime(value)
    if parsed is None:
        raise ValueError("Invalid since parameter. Use ISO 8601 datetime format.")

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone=datetime_timezone.utc)
    return parsed
