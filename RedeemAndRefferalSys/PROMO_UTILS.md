# Promo utils documentation (`utils.py`)

**Scope:** promo discount only (not referral).  
**File:** `RedeemAndRefferalSys/utils.py`  
**Lifecycle (states, clocks):** `PROMO_LIFECYCLE.md`

---

## Business rules (one sentence each)

1. **Value** — Decide if the number is % or shillings so subsidized fare is correct.
2. **Attempts** — When creating a code, set `allowed_attempts >= 1`; `0` means never usable at checkout.
3. **Expiry** — Shelf: 3 months from creation; claim window: 2 weeks from redemption. Time ends as **EXPIRED**, not USED.
4. **Consume** — Only mark **USED** after payment via Checkout reserve then consume; never use deprecated `redeem_code` for spend.

### State machine

```text
CREATED  --redeem to account-->  REDEEMED
REDEEMED --Checkout reserve-->   RESERVED
RESERVED --payment success-->    USED  (or REDEEMED if multi-use attempts remain)
```

| Step | Where |
|------|--------|
| Mint economics | `build_promo_mint_fields` / `set_promo_code_economics` |
| Redemption | `DiscountService.activate_code` -> **REDEEMED** |
| Reserve | `Checkout.policy.validate_reserve_discount` |
| Spend | `Checkout.policy.consume_discount` / `decrement_promo_attempt` |

---

## Helper API

### Mint / setters

| Function | Purpose |
|----------|---------|
| `build_promo_mint_fields(max_attempts, value)` | Kwargs before `create` |
| `set_promo_code_economics(discount, max_attempts, value)` | Edit existing row |
| `discount_code_generator(..., max_attempts=, value=)` | Unique code + CREATED + shelf `expires_at` |

### Attempts

| Function | Purpose |
|----------|---------|
| `get_attempts_remaining` | Remaining uses |
| `decrement_promo_attempt` | -1 on one locked code; requires RESERVED |
| `resolve_promo_code` | Exact row by instance and/or code string |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03 | Mint setters + attempt tracking |
| 2026-03 | Status machine: ACTIVE renamed to REDEEMED; EXPIRED; 3mo/2wk clocks; PROMO_LIFECYCLE.md |
