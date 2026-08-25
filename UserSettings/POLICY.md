# UserSettings policy — identity & offline

**Status:** Production policy (2026-07-19)  
**Conflict default:** **Server wins** on version mismatch  
**Phone after confirm:** Session stays logged in; next login uses new number

---

## Field sensitivity

| Field | Offline edit | Queue | OTP | Writer API |
|-------|--------------|-------|-----|------------|
| `first_name`, `second_name` | Yes | `PROFILE_NAME_UPDATE` | No | `PATCH /api/settings/profile/name/` |
| `phone_number` | **No** | **Forbidden** | **Yes** | request + confirm under `/api/settings/profile/phone/` |
| `email` | Future | Future | Optional | Future settings path |

---

## Single writer

| Surface | Allowed |
|---------|---------|
| `UserSettings` | Name + phone (OTP) |
| `GET /api/sync/profile/` | Rehydrate only |
| `PATCH /api/sync/profile/` | **Not** name/phone/email (`use_settings_api`) |

---

## Versioning

- Shared `ResourceVersion(resource_type=profile, resource_id=user_id)`.
- Name/phone success → `bump_version("profile", user_id)`.
- Client stores `profile_version`; name updates send `base_version`.
- Stale `base_version` → **409** `version_conflict` → client replaces local from server.

---

## Offline name merge

1. Local pending name + `base_version` = V.  
2. Rehydrate with server version == V → keep pending; still push.  
3. Rehydrate with server version > V → **drop pending**, apply server (server wins).  
4. Push success → clear pending; set version from response.  
5. Coalesce queue: keep **latest** `PROFILE_NAME_UPDATE` only.

---

## Phone state machine

```text
idle → request (OTP to NEW phone) → pending_challenge → confirm OTP → committed
                              ↘ expire / too many attempts → idle
```

Never set Room “account phone” until confirm **200**.

---

## Idempotency

- Every write carries `mutation_id` (UUID).
- Redis remembers success payloads 24h for safe retries.
