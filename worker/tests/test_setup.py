from litmus_worker.ai.setup import ChoiceOut, ReagentOut, SetupOut, StepOut, build_protocol, flip_rule


def test_phenol_red_maps_to_red_green_rise():
    rule = flip_rule("#e8c33a", "#d6336c")
    assert rule["metric"] == "lab_a" and rule["direction"] == "rise" and 6 <= rule["delta"] <= 25


def test_starch_iodine_maps_to_lightness_fall():
    rule = flip_rule("#f2f2f2", "#141433")
    assert rule["metric"] == "lab_l" and rule["direction"] == "fall"


def test_build_titration_protocol_from_proposal():
    out = SetupOut(
        name="Vinegar titration", description="Titrate vinegar with baking soda solution.",
        result="amount_until_change", result_label="Base added", result_quantity="base_ml",
        color_before_hex="#e8c33a", color_after_hex="#d6336c", vessel_box=[300, 420, 700, 580],
        steps=[StepOut(title="Measure 10 mL vinegar", quantity_name="sample_ml", quantity_unit="mL", expected_amount=10),
               StepOut(title="Dilute with water"),
               StepOut(title="Titrate", quantity_name="base_ml", quantity_unit="mL", quantity_step=0.5, repeat=True)],
        reagents=[ReagentOut(key="water source", label="Water source", during_step=1, question="Which jug?",
                             choices=[ChoiceOut(key="tap", looks_like="jug labeled TAP"),
                                      ChoiceOut(key="distilled", looks_like="jug labeled DISTILLED")], expected="distilled")],
    )
    p = build_protocol(out)
    assert p["result"]["kind"] == "amount_until_change" and p["result"]["quantity"] == "base_ml"
    assert p["flip"]["metric"] == "lab_a"
    assert next(s for s in p["steps"] if s.get("repeat"))["arm_flip"] is True
    water = next(v for v in p["variables"] if v["key"] == "water_source")
    assert water["detect"]["step"] == p["steps"][1]["id"] and water["expected"] == "distilled"
    assert 0 < p["roi"]["w"] < 0.2


def test_unclear_bench_becomes_generic_observation():
    p = build_protocol(SetupOut(name="Bench observation", description="", result="amount_until_change", steps=[]))
    assert p["result"]["kind"] == "none"  # no expected colors, so nothing to detect: never invent a result
    assert "flip" not in p and p["steps"][0]["arm_flip"]
