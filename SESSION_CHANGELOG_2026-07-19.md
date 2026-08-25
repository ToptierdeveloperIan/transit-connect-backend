# Session changelog — 2026-07-19 (backend)

Companion log for Android:  
`Imanicommunityapp/SESSION_CHANGELOG_2026-07-19.md`

---

## Support & UserSettings apps

### Goal

Scaffold two production domains and mount them on the root project **only** (no full feature implementation yet).

| App | `INSTALLED_APPS` name | URL prefix | Health |
|-----|----------------------|------------|--------|
| Support | `Support` | `/api/support/` | `GET health/` |
| UserSettings | `UserSettings` | `/api/settings/` | `GET health/` |

### Why two apps

| App | Owns |
|-----|------|
| **UserSettings** | Profile mutations and account preferences (name, phone, email, logout/session later) |
| **Support** | Help, legal content, tickets/contact later |

Client already splits Settings UI into **Profile** vs **Support & Legal** (`supportProfile/SettingsFragment`).

### Files created / updated

| Path | Role |
|------|------|
| `Support/` | Django app (`startapp`) + `urls.py` + health view |
| `UserSettings/` | Same |
| `ridehaiingbackend/settings.py` | Registered both apps |
| `ridehaiingbackend/urls.py` | Included both URL confs |
| `Support/README.md` | Purpose + planned endpoints |
| `UserSettings/README.md` | Purpose + planned endpoints |

### Health responses

```json
{ "success": true, "app": "Support", "message": "Support app is live." }
{ "success": true, "app": "UserSettings", "message": "UserSettings app is live." }
```

`permission_classes = [AllowAny]` on health only (global DRF default is `IsAuthenticated`).

### Explicit non-goals this session

- No models/migrations beyond empty app skeleton  
- No move of `changeFname` / `changePhone` from `Loginandauthentication` yet  
- No Android client wiring to these mounts yet  

---

## Related Android work (same session)

Production Retrofit consolidation under `authRetrofitClient` + `ImaniApp` cold start.  
See client `NETWORK.md` and client session changelog.

---

## Terms of Service E2E (completed)

| Item | Detail |
|------|--------|
| Models | `LegalDocument`, `LegalAcceptance` |
| Migration | `Support/migrations/0001_legal_documents.py` |
| Service | `Support/services/legal_service.py` |
| API | `GET terms/`, `GET terms/status/`, `POST terms/accept/`, `GET legal/current/` |
| Locales | `en`, `sw` (Kiswahili) |
| Seed | `python manage.py seed_terms` → v1.0.0 both languages |
| Docs | `Support/TERMS_OF_SERVICE.md`, updated `Support/README.md` |

Android Compose client + gate documented in  
`Imanicommunityapp/docs/TERMS_OF_SERVICE.md`.

## UserSettings profile APIs — implemented

| Path | Role |
|------|------|
| `GET profile/` | Snapshot + `profile_version` |
| `PATCH profile/name/` | Names + offline queue replay |
| `POST profile/phone/request/` | OTP to new number |
| `POST profile/phone/confirm/` | Commit phone |

Also: datasync profile PATCH blocks identity fields.  
Docs: `UserSettings/POLICY.md`, `PROFILE_SETTINGS.md`.

## Wallet app — implemented (foundation)

| Item | Detail |
|------|--------|
| App | `Wallet` at `/api/wallet/` |
| Models | `WalletAccount`, `WalletIntent`, `LedgerEntry` (append-only) |
| Deposit | MPESA/AIRTEL intents; credit only via `apply_provider_success` |
| Spend | Amount from `fare_bridge.payment_amount_for_quote` → `discounted_fare` |
| Reversal | Compensating ledger entries (no mutation of history) |
| Docs | `Wallet/POLICY.md`, `WALLET.md`, `README.md` |

**Not yet:** full STK callback auto-wire into deposit success (call service from paymentSystem next); Airtel engine; Android wallet UI.

## Next backend work (recommended)

### Support (follow-ons)

```text
GET  /api/support/privacy/     (mirror Terms pattern)
GET  /api/support/help/
POST /api/support/tickets/     (later)
```
