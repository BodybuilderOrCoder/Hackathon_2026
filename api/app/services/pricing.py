def quote_cost(distance_km: float, stops: int, quote: dict, waiting_min: int = 0) -> int:
    billable_distance = distance_km * (2 if quote["return_trip_rule"] in {"ROUND_TRIP", "RETURN_REQUIRED"} else 1)
    base = int(quote["callout_fee_vnd"] + billable_distance * quote["rate_per_km_vnd"] + max(0, stops - 1) * quote["stop_fee_vnd"])
    base = max(base, int(quote["minimum_fare_vnd"]))
    excess_wait = max(0, waiting_min - quote["waiting_free_min"])
    base += int((excess_wait / 60) * quote["waiting_fee_per_hour_vnd"])
    return round(base * (1 + quote["vat_rate_assumption"]))


def internal_cost(distance_km: float, vehicle: dict) -> int:
    return round(vehicle["fixed_cost_vnd"] + distance_km * vehicle["cost_per_km_vnd"])
