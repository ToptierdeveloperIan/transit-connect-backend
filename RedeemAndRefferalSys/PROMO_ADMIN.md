# Promo Django admin

**File:** `RedeemAndRefferalSys/admin.py`  
**Model:** `DiscountCode`  
**Related:** `PROMO_LIFECYCLE.md`, `PROMO_UTILS.md`, `utils.py`

---

## Role of admin

| Admin does | Admin does **not** |
|------------|---------------------|
| Mint codes | Mark **USED** (payment only) |
| Set value + max attempts | Couple code to a rider (`redeemed_by_user`) |
| Set / override `expires_at` | Call deprecated spend `redeem_code` |
| Set `created_by` (auto) | Treat REDEEMED as “already spent” |
| Force **REVOKED** | Bypass reserve/consume |

Admin = **mint + configure + revoke**.  
Rider API = **redemption** (REDEEMED).  
Checkout/payment = **RESERVED → USED**.

---

## How admin connects to the rest of the module

```text
Django Admin
    │
    ├─ discount_code_generator(max_attempts, value)
    │       → CREATED + expires_at (3 months shelf)
    │
    ├─ set_promo_code_economics(...)
    │       → allowed_attempts + value + Value_of_code
    │
    ├─ created_by = request.user
    │
    └─ action revoke → status REVOKED
            │
            ▼
    DiscountCode row
            │
            ▼  POST api/redeem-code/validate/
    REDEEMED (rider)
            │
            ▼  Checkout + payment
    RESERVED → USED
```

No parallel business rules in admin — only calls into `utils` / `policy` / status enum.

---

## Features implemented

### List / detail

- List: code, status, value, attempts, expires_at, redeemed_by_user, created_by, dates  
- Filter: status, dates  
- Search: code, usernames  
- Readonly: created_at, redeemed_at, redeemed_by_user, last_synced_at  
- After status leaves **CREATED**, code / coupling fields lock further edits  

### Save (Add / change promo)

1. Empty **code** on add → auto unique 8-char code.  
2. **`created_by`** = current admin user on first save.  
3. Empty **`expires_at`** → `shelf_expires_at(now)` (3 months).  
4. Status **CREATED** → `set_promo_code_economics` (attempts default to 1 if form had 0).  

### Actions

| Action | Behaviour |
|--------|-----------|
| **Mint 5 single-use promos** | 5× `discount_code_generator(max_attempts=1, value=10)` + `created_by` (full product mint path) |
| **Revoke selected** | status → **REVOKED**; skips **USED** |

---

## How to use (operator)

1. Open Django admin → **Discount codes**.  
2. Either:
   - **Add** with blank code + set attempts/value, or  
   - Select any rows → **Mint 5 single-use promos**.  
3. Confirm `allowed_attempts >= 1` and `expires_at` before sharing codes.  
4. To kill a campaign: select codes → **Revoke selected**.  

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03 | Registered `DiscountCodeAdmin` with mint actions, `created_by`, economics/expiry hooks, revoke action. |
