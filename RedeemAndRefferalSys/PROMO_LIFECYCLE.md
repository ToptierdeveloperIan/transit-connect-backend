# Promo discount lifecycle (authoritative)

**Scope:** promo codes only (not referral).  
**Code:** `models.DiscountCode.Status`, `policy.py`, `services/discount_service.py`, `utils.py`, `Checkout/policy.py`.

---

## Terms (do not mix)

| Term | Meaning |
|------|---------|
| **Redemption** | User gains the ability to use the code object — **coupled to their account**. Status **REDEEMED**. Sets `redeemed_at` + `redeemed_by_user`. |
| **USED** | **Attempts have been deducted** after a successful payment spend. Not the same as redemption. |
| **RESERVED** | Checkout hold while payment is in flight. |
| **EXPIRED** | Killed by **time** (shelf life or claim window). Not USED. |
| **REVOKED** | Forced invalidation (admin/system). |

---

## State machine

```text
CREATED
  │  mint (generator / admin); expires_at ≈ created_at + 3 months
  │
  ▼  redemption (POST redeem-code/validate/ → activate_code)
REDEEMED          ← coupled to user; claim window = redeemed_at + 2 weeks
  │
  ▼  Checkout.validate_reserve_discount
RESERVED
  │
  ▼  payment SUCCESS → consume_discount / decrement_promo_attempt
  │
  ├─ attempts left == 0  →  USED
  └─ attempts left > 0   →  REDEEMED  (multi-use)

Time (any of CREATED / REDEEMED / RESERVED):
  → EXPIRED if shelf or claim window fails

Admin / force:
  → REVOKED
```

### Enum values (`DiscountCode.Status`)

| Value | Label | Role |
|-------|--------|------|
| `CREATED` | Created | Minted; not on an account |
| `REDEEMED` | Redeemed | On an account (was confusingly called ACTIVE) |
| `RESERVED` | Reserved | Checkout hold |
| `USED` | Used | Attempt budget spent via pay path |
| `EXPIRED` | Expired | Time policy |
| `REVOKED` | Revoked | Manual/system kill |

---

## Two clocks

| Clock | Anchor | Duration | Effect |
|-------|--------|----------|--------|
| **Shelf life** | `created_at` / `expires_at` | **3 months** (`policy.SHELF_LIFE`) | Code cannot be redeemed/used; mark **EXPIRED** |
| **Claim window** | `redeemed_at` | **2 weeks** (`policy.CLAIM_WINDOW`, tunable) | After account couple, entitlement expires → **EXPIRED** |

A code is time-valid only if **both** clocks allow it (when claim window applies).

`policy.should_revoke(...)` returns True when time should kill the code.  
Jobs / services then set status **EXPIRED** (not USED).

---

## Canonical spend (remember)

```text
REDEEMED → RESERVED → (payment success) → USED
```

- Do **not** mark USED on redeem-to-account.  
- Do **not** use deprecated `DiscountService.redeem_code` for spend.  
- Decrement attempts only on the **one** code row held for that checkout.

---

## Field notes

| Field | Meaning |
|-------|---------|
| `redeemed_at` | Account couple time (redemption), not payment time |
| `expires_at` | Shelf deadline (set at mint via `shelf_expires_at`) |
| `allowed_attempts` | Remaining spends; 0 ⇒ cannot reserve |

---

## Migration

`0002_promo_status_machine.py` maps legacy `ACTIVE` → `REDEEMED` and expands choices.

```bash
python manage.py migrate RedeemAndRefferalSys
```

---

## Related files

| File | Role |
|------|------|
| `models.py` | Status enum |
| `policy.py` | Clocks + `should_revoke` / `is_time_valid` |
| `services/discount_service.py` | Redemption to account |
| `utils.py` | Mint economics + attempt decrement |
| `admin.py` | Django admin mint / configure / revoke |
| `Checkout/policy.py` | Reserve + consume after pay |
| `PROMO_UTILS.md` | Helper function API |
| `PROMO_ADMIN.md` | Admin operator + connection points |
| `ride_matching/FARE_QUOTE.md` | Base vs discounted fare + payment amount (uses REDEEMED promos) |
