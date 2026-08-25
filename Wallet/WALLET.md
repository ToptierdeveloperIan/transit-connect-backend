# Wallet API & domain reference

**Mount:** `/api/wallet/`  
**Auth:** JWT (except `health/`)  
**Policy:** [POLICY.md](./POLICY.md)

---

## Models

| Model | Purpose |
|-------|---------|
| `WalletAccount` | 1:1 user; cached `available_balance` / `held_balance` |
| `WalletIntent` | Deposit/spend lifecycle; provider correlation |
| `LedgerEntry` | Immutable money facts |

---

## Services

| Service | Responsibility |
|---------|----------------|
| `LedgerService` | post_entry, reverse_entry, rebuild_balance |
| `DepositService` | create intent, attach provider ref, **apply_provider_success/failure** |
| `SpendService` | wallet pay via fare_bridge amount; reverse_spend |
| `WalletService` | balance / ledger / intent reads |

---

## HTTP

| Method | Path | Notes |
|--------|------|--------|
| GET | `health/` | Public |
| GET | `balance/` | available, held, spendable |
| GET | `ledger/?limit=` | Recent entries |
| GET | `intents/?limit=` | Deposit/spend intents |
| POST | `deposits/` | Create deposit intent (no credit yet) |
| POST | `spend/` | Debit for `quote_id` (amount from server) |

### POST deposits/

```json
{
  "amount": "500.00",
  "channel": "MPESA",
  "idempotency_key": "uuid",
  "description": "Top up"
}
```

`channel`: `MPESA` | `AIRTEL`

### POST spend/

```json
{
  "quote_id": "uuid-of-open-fare-quote",
  "idempotency_key": "uuid",
  "booking_id": null
}
```

---

## Provider success (code API, not public HTTP yet)

```python
from Wallet.services import DepositService

DepositService.apply_provider_success(
    provider_reference=checkout_request_id,
    channel="MPESA",
    amount=None,  # optional verify vs intent
    raw_payload=callback_dict,
)
```

Wire this from `paymentSystem` STK callback when the payment purpose is **wallet deposit**.

---

## Admin

- `LedgerEntry`: read-only (no add/change/delete)  
- Intents / accounts: searchable by phone / provider ref  

---

## Migrations

```bash
python manage.py migrate Wallet
```

---

## Android (future)

Suggested client package: `wallet/` with balance UI, deposit (STK), pay-with-wallet at checkout using `quote_id` only.
