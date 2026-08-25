# Fare quote service

**Service:** `ride_matching.services.fare_quote_service.FareQuoteService`  
**Hook:** runs **inside** `get_route_coordinates` as an operator on `fare` (does not replace coordinates)

---

## Two prices only

| Field | Meaning |
|-------|---------|
| **`base_fare`** (`fare`) | List price from `Route.price`. **Never null** in DB (Booking default `0`). |
| **`discounted_fare`** | What the rider **pays**. Equals base if no valid promo. |

There is **no `amount_due` column**.  
Payment amount = **`discounted_fare`**.

---

## get_route_coordinates

Still returns geometry + destinations.  
Then FareQuoteService operates on fare:

```text
coords = geometry + destinations + fare(base)
pricing = FareQuoteService.apply_to_base_fare(fare, user?, promo?)
payload merges: base_fare, discounted_fare, quote/promo metadata
```

Coordinates logic is not rewritten — only fare is enriched.

---

## Booking DB

| Field | Null? |
|-------|--------|
| `base_fare` | **No** (default `0`) |
| `discounted_fare` | **Yes** until quote attached |
| `promo_code` / `fare_quote_id` | Yes |

---

## FareQuote DB

| Field | Null? |
|-------|--------|
| `base_fare` | No |
| `discounted_fare` | No (always set at quote time; = base if no promo) |

Statuses: OPEN → CONSUMED | ABANDONED | EXPIRED  
Redis + DB; `expire_fare_quotes` clears stale OPEN.

---

## Payment

```python
from paymentSystem.fare_bridge import payment_amount_for_quote
amount = payment_amount_for_quote(quote_id)  # discounted_fare
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03 | Introduced FareQuoteService + FareQuote |
| 2026-03 | Removed amount_due; pay = discounted_fare; base_fare non-null on Booking |
