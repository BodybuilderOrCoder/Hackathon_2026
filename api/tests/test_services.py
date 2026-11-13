from app.services.packing import pack_floor
from app.services.pricing import quote_cost
from app.services.seed import load_workbook_rows


def test_quote_cost_applies_minimum_fare_and_tax():
    quote = {"return_trip_rule":"ONE_WAY","callout_fee_vnd":100000,"rate_per_km_vnd":1000,
             "stop_fee_vnd":20000,"minimum_fare_vnd":360000,"waiting_free_min":60,
             "waiting_fee_per_hour_vnd":60000,"vat_rate_assumption":0.1}
    assert quote_cost(10, 2, quote) == 396000


def test_quote_cost_counts_return_leg_and_waiting():
    quote = {"return_trip_rule":"ROUND_TRIP","callout_fee_vnd":0,"rate_per_km_vnd":10000,
             "stop_fee_vnd":0,"minimum_fare_vnd":0,"waiting_free_min":30,
             "waiting_fee_per_hour_vnd":60000,"vat_rate_assumption":0}
    assert quote_cost(10, 1, quote, waiting_min=90) == 260000


def test_floor_packing_rejects_oversize_height_and_does_not_overlap():
    too_tall = [{"pallet_id":"P1","length_cm":50,"width_cm":50,"height_cm":201,"rotation_rule":"ANY"}]
    assert pack_floor(too_tall, 200, 200, 200)["status"] == "FAIL_HEIGHT"
    pallets = [{"pallet_id":f"P{i}","length_cm":80,"width_cm":50,"height_cm":80,"rotation_rule":"ANY"} for i in range(4)]
    result = pack_floor(pallets, 200, 100, 200)
    assert result["status"] == "PASS_2D_FLOOR_ONLY"
    placements = result["placements"]
    for i, a in enumerate(placements):
        assert a["x_cm"] + a["length_cm"] <= 200
        assert a["y_cm"] + a["width_cm"] <= 100
        for b in placements[i+1:]:
            separated = (a["x_cm"]+a["length_cm"] <= b["x_cm"] or b["x_cm"]+b["length_cm"] <= a["x_cm"] or
                         a["y_cm"]+a["width_cm"] <= b["y_cm"] or b["y_cm"]+b["width_cm"] <= a["y_cm"])
            assert separated


def test_seed_workbook_has_expected_synthetic_operations():
    rows=load_workbook_rows(__import__("pathlib").Path(__file__).resolve().parents[2] / "outputs" / "01a1cbad-1a1e-7de1-899b-92bedce65edf" / "FleetMix_ERP_Operational_Dataset.xlsx")
    assert len(rows["orders"]) == 24
    assert len(rows["pallets"]) == 53
    assert len(rows["customers"]) == 12
    assert len(rows["products"]) == 18
    customer_ids={row["customer_id"] for row in rows["customers"]}
    product_ids={row["sku_id"] for row in rows["products"]}
    assert all(row["customer_id"] in customer_ids for row in rows["orders"])
    assert all(row["sku_id"] in product_ids for row in rows["pallets"])
    assert max(int(p["length_cm"]) for p in rows["pallets"]) <= 120
    assert max(int(p["width_cm"]) for p in rows["pallets"]) <= 100
    for order in rows["orders"]:
        handling_units=[p for p in rows["pallets"] if p["order_id"] == order["order_id"]]
        assert int(order["total_weight_kg"]) == sum(int(p["weight_kg"]) for p in handling_units)
        assert abs(float(order["total_volume_m3"]) - sum(float(p["volume_m3"]) for p in handling_units)) < 0.001
    assert {str(a["confirmation_status"]).upper() for a in rows["availability"]} >= {"CONFIRMED", "PENDING"}

