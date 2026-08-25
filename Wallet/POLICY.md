# Wallet policy — money movement & consistency

**App:** `Wallet`  
**Currency default:** KES  
**Rails:** M-Pesa (`MPESA`), Airtel Money (`AIRTEL`), internal wallet spend (`WALLET`)

---

## 1. Core rules (non-negotiable)

| # | Rule |
|---|------|
| R1 | **Ledger is append-only.** Never update/delete a posted `LedgerEntry` amount or type. |
| R2 | **No credit without canonical provider success** for deposits (callback SUCCESS / recon SUCCESS). |
| R3 | **No debit inventing prices.** Spend amount = `payment_amount_for_quote(quote_id)` → `FareQuote.discounted_fare`. |
| R4 | **Reversals are new opposite entries**, not edits. Original row stays for audit. |
| R5 | **Idempotency everywhere** (`idempotency_key`, unique provider refs). Retries must not double-pay. |
| R6 | **Balance cache is a projection.** Rebuildable as sum of signed ledger effects. |

---

## 2. What is *not* money movement

| Action | Ledger? |
|--------|---------|
| Create deposit intent | No |
| STK / Airtel “request accepted” | No |
| Provider failure / timeout / cancel | No |
| User views balance | No |
| Provider **CONFIRMED SUCCESS** | **Yes — CREDIT_DEPOSIT** |
| Wallet fare settle | **Yes — DEBIT_SPEND** |
| Refund / undo spend | **Yes — CREDIT_REVERSAL** |
| Undo mistaken deposit | **Yes — DEBIT_REVERSAL** |

This keeps reversals simple: one graph of facts, no “partial balance states” for failed rails.

---

## 3. Deposit flow (M-Pesa / Airtel)

```text
POST /api/wallet/deposits/  → Intent PENDING_PROVIDER  (no ledger)
       │
       ├─► Initiate STK / Airtel push (paymentSystem / future Airtel engine)
       ├─► attach_provider_reference(CheckoutRequestID)
       │         status PROVIDER_ACCEPTED  (no ledger)
       │
       ├─► Callback SUCCESS
       │         DepositService.apply_provider_success(...)
       │         → CREDIT_DEPOSIT + Intent SUCCEEDED
       │
       └─► Callback FAIL / timeout
                 apply_provider_failure(...)
                 → Intent FAILED  (still no ledger)
```

**Late failure after success** is not “FAILED”; it is **reversal** (`LedgerService.reverse_entry` on the credit). That avoids branching complexity: failure never applies to already-funded money.

---

## 4. Spend flow (pay ride from wallet)

```text
Checkout produced FareQuote (OPEN)
       │
POST /api/wallet/spend/ { quote_id, idempotency_key }
       │
       ├─ amount = fare_bridge.payment_amount_for_quote(quote_id)  // discounted_fare
       ├─ check spendable balance
       ├─ DEBIT_SPEND in same transaction
       └─ Intent SUCCEEDED
```

Client **must not** send amount. If client amount is ever added for display, server still ignores it for settlement.

After spend success, call existing promo/booking hooks as needed (`mark_quote_paid`, `consume_discount`) in the **payment orchestration layer**, not inside the ledger row itself — keep wallet focused on money facts.

---

## 5. Reversal without complexity

| Original | Compensating entry |
|----------|-------------------|
| CREDIT_DEPOSIT | DEBIT_REVERSAL |
| DEBIT_SPEND | CREDIT_REVERSAL |

- Link via `related_entry`  
- Same amount as original  
- Intent → `REVERSED`  
- Double-reverse blocked  

No multi-phase saga for simple refunds: one compensating post under lock.

---

## 6. Scale notes

| Concern | Approach |
|---------|----------|
| Hot wallet row | `select_for_update` on account per txn |
| Provider retries | Unique (channel, provider_reference) + intent idempotency_key |
| History growth | Append-only ledger; paginate reads; archive cold entries later |
| Event bus | Optional: emit outbox after ledger post (reuse paymentSystem patterns) |
| Multi-region | Single primary DB for ledger; never dual-write balances |

---

## 7. Relationship to paymentSystem

| Component | Role |
|-----------|------|
| `paymentSystem` | STK/B2C rails, PaymentEvent lifecycle, Kafka outbox |
| `Wallet` | User balance, ledger, deposit intents, wallet spend |
| `fare_bridge` | Amount truth for rides |

**Wire point (next implementation step):** on STK success for a *deposit* intent, call `DepositService.apply_provider_success`. On STK success for *direct trip pay* (non-wallet), keep existing payment path; do not double-credit wallet.

---

## 8. Fare / promo truth (do not fork)

Documented in `ride_matching/FARE_QUOTE.md` and `paymentSystem/fare_bridge.py`:

```text
pay_amount = FareQuote.discounted_fare
```

Wallet **reads** that method; it does not re-implement promo math.
