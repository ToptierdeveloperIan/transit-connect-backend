from random import random
from typing import Any, Optional

from .models import Destination, Route


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Uniform error payload for validation helpers and API views."""
    payload: dict[str, Any] = {
        "success": False,
        "error": code,
        "message": message,
    }
    payload.update(extra)
    return payload


def validate_route_and_stop(
    route_name: Optional[str],
    stop: Optional[str],
    *,
    user=None,
    promo_code: Optional[str] = None,
    include_pricing: bool = True,
) -> dict[str, Any]:
    """
    Professional validation of route + stop (drop-off) before booking/quote.

    Use this **before** CreateBooking refactor / as the light path body:

      validate_route_and_stop(route_name, stop, user=request.user, promo_code=...)

    Steps:
      1. Sanitize route_name and stop (required, non-empty after strip).
      2. Query Route by name (case-insensitive).
      3. Resolve allowed stops from ``destinations_list`` and/or Destination rows.
      4. Ensure stop is on that route (case-insensitive).
      5. Load coordinates (+ optional fare pricing via get_route_coordinates).

    Edge cases handled:
      - None / blank / whitespace-only inputs
      - Route missing in DB
      - Route with no destinations configured
      - Stop not on route
      - Coordinate payload missing geometry
      - Unexpected DB errors (logged shape, safe message)

    Returns:
      Success::
        {
          "success": True,
          "route_name": "<canonical DB name>",
          "stop": "<canonical stop name from catalog>",
          "coordinates": { ... geometry, destinations, fare fields ... },
        }

      Failure::
        {
          "success": False,
          "error": "<machine code>",
          "message": "<human message>",
        }

    Error codes:
      route_required, stop_required, route_not_found,
      destinations_unavailable, stop_not_on_route,
      coordinates_unavailable, internal_error

    Does **not** create a Booking or call store_details_by_route.
    """
    # --- 1) Input sanitization ---
    if route_name is None or not str(route_name).strip():
        return _error("route_required", "Route name is required.")
    if stop is None or not str(stop).strip():
        return _error("stop_required", "Stop (destination) is required.")

    route_key = str(route_name).strip()
    stop_key = str(stop).strip()

    try:
        # --- 2) Route lookup ---
        route = Route.objects.filter(name__iexact=route_key).first()
        if route is None:
            return _error(
                "route_not_found",
                f"No route found matching {route_key!r}.",
                route_name=route_key,
            )

        canonical_route = route.name

        # --- 3) Build stop catalog (JSON list + related Destination rows) ---
        allowed_stops = _resolve_route_stops(route)
        if not allowed_stops:
            return _error(
                "destinations_unavailable",
                f"Route {canonical_route!r} has no destinations configured.",
                route_name=canonical_route,
            )

        # --- 4) Stop must belong to route ---
        canonical_stop = _match_stop(stop_key, allowed_stops)
        if canonical_stop is None:
            return _error(
                "stop_not_on_route",
                f"Stop {stop_key!r} is not valid for route {canonical_route!r}.",
                route_name=canonical_route,
                stop=stop_key,
                allowed_stops=allowed_stops,
            )

        # --- 5) Coordinates (+ fare operator when include_pricing) ---
        if include_pricing:
            coords = get_route_coordinates(
                canonical_route,
                user=user,
                promo_code=promo_code,
            )
        else:
            coords = get_route_coordinates_geometry_only(canonical_route)

        if coords is None or (isinstance(coords, dict) and coords.get("error")):
            msg = (
                coords.get("error")
                if isinstance(coords, dict)
                else "Could not load route coordinates."
            )
            return _error(
                "coordinates_unavailable",
                msg or "Could not load route coordinates.",
                route_name=canonical_route,
                stop=canonical_stop,
            )

        if not _coords_have_geometry(coords):
            return _error(
                "coordinates_unavailable",
                f"Route {canonical_route!r} is missing geometry fields.",
                route_name=canonical_route,
                stop=canonical_stop,
            )

        return {
            "success": True,
            "route_name": canonical_route,
            "stop": canonical_stop,
            "coordinates": coords,
        }

    except Exception:
        # Avoid leaking internals to API clients
        import logging

        logging.getLogger(__name__).exception(
            "validate_route_and_stop failed route=%r stop=%r", route_key, stop_key
        )
        return _error(
            "internal_error",
            "Unexpected error while validating route and stop.",
        )


def _resolve_route_stops(route: Route) -> list[str]:
    """
    Union of destinations_list JSON and Destination child rows.
    Preserves order: JSON list first, then any DB-only names.
    """
    seen: set[str] = set()
    ordered: list[str] = []

    raw_list = route.destinations_list or []
    if isinstance(raw_list, list):
        for name in raw_list:
            if name is None:
                continue
            label = str(name).strip()
            if not label:
                continue
            key = label.lower()
            if key not in seen:
                seen.add(key)
                ordered.append(label)

    for dest in Destination.objects.filter(route=route).order_by("order", "name"):
        label = (dest.name or "").strip()
        if not label:
            continue
        key = label.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(label)

    return ordered


def _match_stop(stop_key: str, allowed_stops: list[str]) -> Optional[str]:
    """Case-insensitive match; returns catalog spelling or None."""
    needle = stop_key.lower()
    for name in allowed_stops:
        if name.lower() == needle:
            return name
    return None


def _coords_have_geometry(coords: dict[str, Any]) -> bool:
    required = ("start_lat", "start_lng", "end_lat", "end_lng")
    return all(k in coords and coords[k] is not None for k in required)


def get_route_coordinates_geometry_only(route_name: str) -> Optional[dict[str, Any]]:
    """
    Geometry + destinations + raw base fare only (no FareQuoteService / Redis).
    Used when validation must not open a payment quote.
    """
    route = Route.objects.filter(name__iexact=route_name).first()
    if not route:
        return {"error": "Route not found"}
    return {
        "start_lat": route.start_location_lat,
        "start_lng": route.start_location_lng,
        "end_lat": route.end_location_lat,
        "end_lng": route.end_location_lng,
        "destinations": route.destinations_list or [],
        "fare": route.price,
        "base_fare": route.price,
        "discounted_fare": None,
    }


def get_route_coordinates(
    route_name: str,
    user=None,
    promo_code: Optional[str] = None,
):
    """
    Load route geometry, destinations, and fare.

    Structure is still coordinates-first. Fare starts as Route.price; then
    FareQuoteService acts as an operator on that fare (base + discounted).

    Does not replace this function — only enriches the fare fields.

    Prefer ``validate_route_and_stop`` when the client sends both route and stop.

    Returns (success):
      start_lat, start_lng, end_lat, end_lng, destinations,
      fare          — base list price (same as base_fare)
      base_fare     — list price (never conceptually null)
      discounted_fare — pay amount (= fare if no valid promo); may be set by operator
      plus optional quote/promo metadata from FareQuoteService

    See FARE_QUOTE.md and VALIDATE_ROUTE_STOP.md.
    """
    try:
        route = Route.objects.filter(name__iexact=route_name).first()
        if not route:
            return {"error": "Route not found"}

        # Core coordinates payload (unchanged role)
        base_fare = route.price
        payload: dict[str, Any] = {
            "start_lat": route.start_location_lat,
            "start_lng": route.start_location_lng,
            "end_lat": route.end_location_lat,
            "end_lng": route.end_location_lng,
            "destinations": route.destinations_list,
            "fare": base_fare,
        }

        # Operator on fare only — does not alter coordinate fields
        from ride_matching.services.fare_quote_service import FareQuoteService

        pricing = FareQuoteService().apply_to_base_fare(
            base_fare,
            route_name=route.name,
            user=user,
            promo_code=promo_code,
            persist=bool(user),
        )
        payload["fare"] = pricing["base_fare"]
        payload["base_fare"] = pricing["base_fare"]
        payload["discounted_fare"] = pricing["discounted_fare"]
        for key in (
            "promo_applied",
            "promo_code",
            "promo_reject_reason",
            "quote_id",
            "quote_expires_at",
            "quote_status",
        ):
            if key in pricing:
                payload[key] = pricing[key]

        return payload
    except Route.DoesNotExist:
        return None


def rating_system(driver, new_rating):
    if driver.total_score == 0 or driver.rating_score is None:
        driver.rating_score = new_rating
        driver.total_score = 1
    else:
        total_score = driver.rating_score * driver.total_score
        total_score += new_rating
        driver.total_score += 1
        driver.rating_score = total_score / driver.total_score

        return driver.rating_score
