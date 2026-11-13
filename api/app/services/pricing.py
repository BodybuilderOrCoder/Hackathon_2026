ROUND_TRIP_RULES = {"ROUND_TRIP", "RETURN_REQUIRED"}


def quote_cost(distance_km: float, stops: int, quote: dict, waiting_min: int = 0, return_km: float | None = None) -> int:
    """Carrier fare for one trip.

    ``distance_km`` is the loaded (outbound) distance from the depot to the last stop. ``return_km`` is the
    empty leg back to the depot; it is billed only when the tariff charges the return trip. When ``return_km``
    is omitted the return leg is assumed to mirror the outbound distance.
    """
    charges_return = quote["return_trip_rule"] in ROUND_TRIP_RULES
    if return_km is None:
        return_km = distance_km
    billable_distance = distance_km + (return_km if charges_return else 0)
    base = int(quote["callout_fee_vnd"] + billable_distance * quote["rate_per_km_vnd"] + max(0, stops - 1) * quote["stop_fee_vnd"])
    base = max(base, int(quote["minimum_fare_vnd"]))
    excess_wait = max(0, waiting_min - quote["waiting_free_min"])
    base += int((excess_wait / 60) * quote["waiting_fee_per_hour_vnd"])
    return round(base * (1 + quote["vat_rate_assumption"]))


def internal_cost(distance_km: float, vehicle: dict) -> int:
    """Internal trip cost: fixed cost per trip plus running cost for the full depot-to-depot distance."""
    return round(vehicle["fixed_cost_vnd"] + distance_km * vehicle["cost_per_km_vnd"])
