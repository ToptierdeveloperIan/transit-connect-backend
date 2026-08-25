# Checkout API (light path)

**Endpoint:** `POST /api/bookings/checkout/`  
**View:** `ride_matching.views.CheckoutView`  
**Auth:** JWT required  

**Not** a canonical booking. Does not create `Booking` or assign a bus.

---

## Request

```json
{
  "route_name": "KITENGELA",
  "destination": "CABANAS",
  "promo_code": "ABCD1234"
}
```

| Field | Required | Notes |
|-------|----------|--------|
| `route_name` | Yes | Route catalog name |
| `destination` | Yes | Stop / drop-off on that route |
| `promo_code` | No | Applied only if REDEEMED + attempts + time OK |

---

## Pipeline

```text
CheckoutView
  → validate_route_and_stop(route, stop, user, promo)
       → Route + stop DB checks
       → get_route_coordinates(+ FareQuoteService)
  → 200 with coordinates + quote_id
```

Legacy create remains:

```text
POST /api/bookings/create/  → store_details_by_route (match + Booking.create)
```

---

## Success response (200)

```json
{
  "success": true,
  "message": "Checkout ready. Complete payment to confirm booking.",
  "route_name": "KITENGELA",
  "stop": "CABANAS",
  "destination": "CABANAS",
  "coordinates": {
    "start_lat": ...,
    "start_lng": ...,
    "end_lat": ...,
    "end_lng": ...,
    "destinations": [...],
    "fare": 200,
    "base_fare": 200,
    "discounted_fare": 160,
    "quote_id": "uuid",
    "promo_applied": true
  },
  "quote_id": "uuid",
  "booking_id": null
}
```

`discounted_fare` may be null on older/partial pricing paths; Android treats it as nullable.

---

## Error response (400)

```json
{
  "success": false,
  "error": "stop_not_on_route",
  "message": "..."
}
```

Same error codes as `validate_route_and_stop` (see VALIDATE_ROUTE_STOP.md).

---

## Android

Hits `bookings/checkout/` via `BookingRepository.checkout` (not create).  
See app `COORDINATES_API.md` and `CHECKOUT_CLIENT.md`.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03 | Added CheckoutView + URL; create left for canonical booking |
