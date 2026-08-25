# Terms of Service — Support app

**Status:** Production-oriented vertical slice (2026-07-19)  
**Locales:** `en` (English), `sw` (Kiswahili)  
**Extensibility:** `document_type` supports `TERMS` today; `PRIVACY` ready in model enums

---

## Architecture

```text
views (HTTP) → LegalService (rules) → LegalDocument / LegalAcceptance
content/*.txt → seed_terms command → DB
```

| Layer | Responsibility |
|-------|----------------|
| `models.py` | Storage shape; open to new types/locales/formats |
| `services/legal_service.py` | Current doc, status, accept, validation |
| `serializers.py` | Wire contracts |
| `views.py` / `urls.py` | HTTP only |
| `admin.py` | Ops publish/edit |
| `management/commands/seed_terms.py` | Bootstrap v1.0.0 EN+SW |

**Acceptance rule:** keyed by `(user, document_type, version)`. Locale is *what they read*, not a separate acceptance identity. Publishing a new **version** forces re-accept (`must_accept: true`).

---

## HTTP API

Base: `/api/support/`

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `terms/?locale=en\|sw` | Public | Current published TERMS |
| GET | `terms/status/` | JWT | `must_accept`, versions |
| POST | `terms/accept/` | JWT | Accept current version |
| GET | `legal/current/?document_type=&locale=` | Public | Generic (TERMS/PRIVACY later) |
| GET | `health/` | Public | Mount check |

### GET terms response (shape)

```json
{
  "success": true,
  "message": "Current terms retrieved.",
  "data": {
    "document_type": "TERMS",
    "version": "1.0.0",
    "locale": "sw",
    "title": "...",
    "body": "...",
    "body_format": "plain",
    "effective_at": "...",
    "updated_at": "..."
  }
}
```

If `sw` is missing, service falls back to `en`.

### POST accept body

```json
{
  "version": "1.0.0",
  "locale": "sw",
  "platform": "android",
  "app_version": "1.0"
}
```

---

## Ops

```bash
python manage.py migrate Support
python manage.py seed_terms
python manage.py seed_terms --force   # rewrite bodies
```

Admin: **Legal documents** / **Legal acceptances**.

**Verified 2026-07-19:** migration applied; seed created `en` + `sw` v1.0.0 published.

---

## Android contract

- Public load: plain or authenticated client OK  
- Status + accept: authenticated hub (`authRetrofitClient.getClient`)  
- Gate splash/login when `must_accept == true`  
- UI: Compose Terms screen with EN/SW toggle  

See client `docs/TERMS_OF_SERVICE.md` and `SESSION_CHANGELOG_2026-07-19.md`.
