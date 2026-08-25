# Wallet

In-app **wallet** with **M-Pesa** and **Airtel Money** deposit rails and an **append-only ledger**.

## Read first

1. [POLICY.md](./POLICY.md) — when money moves, reversals, fare amount truth  
2. [WALLET.md](./WALLET.md) — API + services  

## Install

Registered in `INSTALLED_APPS` as `Wallet`.  
Mounted at **`/api/wallet/`**.

```bash
python manage.py migrate Wallet
```

## Package layout

```text
Wallet/
  models.py              # Account, Intent, LedgerEntry (commented)
  services/
    ledger_service.py    # Immutable posts + reverse
    deposit_service.py   # MPESA/AIRTEL top-up intents
    spend_service.py     # Pay fare from balance (fare_bridge)
    wallet_service.py    # Reads
  views.py / urls.py
  admin.py               # Ledger read-only
  POLICY.md / WALLET.md
```

## One-sentence summary

**Intents track provider work; the ledger only moves after success; reversals are new rows.**
