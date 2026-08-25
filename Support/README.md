# Support app

**Mounted at:** `/api/support/`  
**Registered:** `Support` in `INSTALLED_APPS`

## Live features

### Health
- `GET /api/support/health/`

### Terms of Service (production slice)
See **[TERMS_OF_SERVICE.md](./TERMS_OF_SERVICE.md)** for full design.

| Method | Path | Auth |
|--------|------|------|
| GET | `terms/?locale=en\|sw` | Public |
| GET | `terms/status/` | JWT |
| POST | `terms/accept/` | JWT |
| GET | `legal/current/?document_type=&locale=` | Public |

**Locales:** English (`en`), Kiswahili (`sw`).  
**Ops:** `python manage.py seed_terms` (optional `--force`).

### Models
- `LegalDocument` — versioned, localized, typed (`TERMS` / `PRIVACY`)
- `LegalAcceptance` — immutable per user+type+version

### Layers (refactor-friendly)
```text
views → LegalService → models
content/*.txt → seed_terms
```

## Planned next
- Privacy Policy content + same acceptance pattern  
- Help FAQ + contact  
- Support tickets with booking correlation  

## Android mapping
- Compose Terms: `ui.terms.TermsComposeFragment`  
- Gate: `support.terms.TermsGate` on splash + post-login  
- Settings → Terms row  
