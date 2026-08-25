# `validate_route_and_stop(route_name, stop)`

**File:** `ride_matching/utils.py`  
**Purpose:** Professional pre-booking / pre-quote validation before CreateBooking refactor.

Does **not** create a `Booking` or call `store_details_by_route`.

---

## Signature

```python
validate_route_and_stop(
    route_name,
    stop,
    user=None,
    promo_code=None,
    include_pricing=True,
) -> dict
```

| Arg | Role |
|-----|------|
| `route_name` | Catalog route (e.g. KITENGELA) |
| `stop` | Drop-off on that route |
| `user` | Optional; enables FareQuote persist + promo |
| `promo_code` | Optional; applied only if valid |
| `include_pricing` | `True` → full `get_route_coordinates` (fares/quote); `False` → geometry only, `discounted_fare=null` |

---

## Success

```json
{
  "success": true,
  "route_name": "KITENGELA",
  "stop": "CABANAS",
  "coordinates": {
    "start_lat": ...,
    "start_lng": ...,
    "end_lat": ...,
    "end_lng": ...,
    "destinations": [...],
    "fare": 200,
    "base_fare": 200,
    "discounted_fare": 160,
    "quote_id": "..."
  }
}
```

Canonical names come from DB (casing preserved from catalog).

---

## Failure

```json
{
  "success": false,
  "error": "stop_not_on_route",
  "message": "Stop 'X' is not valid for route 'Y'."
}
```

| `error` code | When |
|--------------|------|
| `route_required` | Blank/missing route |
| `stop_required` | Blank/missing stop |
| `route_not_found` | No Route row |
| `destinations_unavailable` | No stops on route |
| `stop_not_on_route` | Stop not in catalog (includes `allowed_stops`) |
| `coordinates_unavailable` | Geometry/coords load failed |
| `internal_error` | Unexpected exception |

---

## Edge cases

- Whitespace trimmed  
- Case-insensitive route and stop match  
- Stops from `Route.destinations_list` **and** `Destination` FK rows  
- Empty destinations list → hard fail  
- Missing lat/lng → hard fail  

---

## Used by Checkout API

`POST /api/bookings/checkout/` → `CheckoutView` → `validate_route_and_stop(...)`.

See `CHECKOUT_API.md`.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03 | Added `validate_route_and_stop` + geometry-only helper |
