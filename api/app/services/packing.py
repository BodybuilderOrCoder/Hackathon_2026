from dataclasses import dataclass


@dataclass
class Placement:
    pallet_id: str
    x_cm: int
    y_cm: int
    length_cm: int
    width_cm: int
    rotated: bool


def pack_floor(pallets: list[dict], length_cm: int, width_cm: int, height_cm: int) -> dict:
    """Conservative 2D floor packing; never assumes stacking. Returns explicit evidence/status."""
    if any(p["height_cm"] > height_cm for p in pallets):
        bad = next(p for p in pallets if p["height_cm"] > height_cm)
        return {"status": "FAIL_HEIGHT", "placements": [], "reason": f"{bad['pallet_id']} exceeds inner height"}
    # Largest footprints first; first-fit decreasing shelf rows with rotation only when allowed.
    ordered = sorted(pallets, key=lambda p: max(p["length_cm"], p["width_cm"]) * min(p["length_cm"], p["width_cm"]), reverse=True)
    placements: list[Placement] = []
    x = y = row_depth = 0
    for p in ordered:
        options = [(int(p["length_cm"]), int(p["width_cm"]), False)]
        if p.get("rotation_rule") in {"BASE_ROTATION_ALLOWED", "ROTATE_90_ALLOWED", "ANY"}:
            options.append((int(p["width_cm"]), int(p["length_cm"]), True))
        placed = None
        for l, w, rotated in options:
            if l > length_cm or w > width_cm:
                continue
            if x + l > length_cm:
                x, y, row_depth = 0, y + row_depth, 0
            if y + w <= width_cm:
                placed = Placement(p["pallet_id"], x, y, l, w, rotated)
                break
        if placed is None:
            return {"status": "FAIL_FLOOR", "placements": [vars(v) for v in placements], "reason": f"Cannot fit {p['pallet_id']} on floor without overlap"}
        placements.append(placed)
        x += placed.length_cm
        row_depth = max(row_depth, placed.width_cm)
    return {"status": "PASS_2D_FLOOR_ONLY", "placements": [vars(v) for v in placements],
            "reason": "2D floor fit only; stacking, axle balance and restraint are not certified"}


def check_vehicle_load(order_ids: list[str], orders_by_id: dict[str, dict], vehicle: dict) -> dict:
    orders = [orders_by_id[o] for o in order_ids]
    weight = sum(o["total_weight_kg"] for o in orders)
    volume = sum(o["total_volume_m3"] for o in orders)
    pallets = [p for o in orders for p in o["pallets"]]
    errors = []
    if weight > vehicle["capacity_kg"]: errors.append("WEIGHT_LIMIT")
    if volume > vehicle["usable_volume_m3"]: errors.append("VOLUME_LIMIT")
    packing = pack_floor(pallets, vehicle["inner_length_cm"], vehicle["inner_width_cm"], vehicle["inner_height_cm"])
    if not packing["status"].startswith("PASS"): errors.append(packing["status"])
    return {"feasible": not errors, "weight_kg": weight, "volume_m3": round(volume, 3), "errors": errors, "packing": packing}
