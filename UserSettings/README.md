# UserSettings

**Mount:** `/api/settings/`  
**Role:** Single writer for profile **name** and **phone (OTP)**.

## Docs

| File | Purpose |
|------|---------|
| [POLICY.md](./POLICY.md) | Offline / conflict / sensitivity |
| [PROFILE_SETTINGS.md](./PROFILE_SETTINGS.md) | HTTP contracts |

## Layout

```text
views.py                 HTTP
services/profile_service.py
services/phone_change_service.py
serializers.py
```

## Quick test

```bash
# JWT required for profile routes
GET  /api/settings/profile/
PATCH /api/settings/profile/name/
POST /api/settings/profile/phone/request/
POST /api/settings/profile/phone/confirm/
```

Requires Redis for OTP challenges + mutation idempotency (same as login OTP).
