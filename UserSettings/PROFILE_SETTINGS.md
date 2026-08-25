# Profile settings API

Base: `/api/settings/`  
Auth: JWT Bearer (except health)

---

## Endpoints

### GET `profile/`

Snapshot for Settings + Room.

```json
{
  "success": true,
  "data": {
    "user_id": 1,
    "first_name": "Ian",
    "second_name": "Nbo",
    "phone_number": "+2547...",
    "email": "...",
    "is_driver": false,
    "profile_version": 3,
    "updated_at": "..."
  }
}
```

### PATCH `profile/name/`

```json
{
  "first_name": "Ian",
  "second_name": "Nbo",
  "mutation_id": "uuid",
  "base_version": 3
}
```

| Code | Meaning |
|------|---------|
| 200 | Updated (or idempotent replay) |
| 400 | Validation |
| 409 | `version_conflict` — re-GET profile |

### POST `profile/phone/request/`

```json
{ "new_phone_number": "+2547...", "mutation_id": "uuid" }
```

```json
{
  "data": {
    "challenge_id": "uuid",
    "expires_in": 600,
    "masked_destination": "+25****21",
    "mutation_id": "uuid"
  }
}
```

### POST `profile/phone/confirm/`

```json
{
  "challenge_id": "uuid",
  "otp": "123456",
  "mutation_id": "uuid"
}
```

Commits `phone_number` + bumps `profile_version`.

---

## Errors envelope

```json
{ "success": false, "error": "phone_taken", "message": "..." }
```

Codes: `version_conflict`, `phone_taken`, `otp_invalid`, `challenge_expired`, `use_settings_api` (datasync), …

---

## Android

See `Imanicommunityapp/docs/PROFILE_SETTINGS_SYNC.md`.
