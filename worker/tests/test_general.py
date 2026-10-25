"""Labs with nothing to do with color: Gemini declares the measurements, code records and compares them."""

import uuid
from datetime import datetime, timedelta, timezone

from litmus_worker import dataset
from litmus_worker.ai.setup import MeasurementOut, SetupOut, StepOut, build_protocol
from litmus_worker.diff import NOTABLE, diff
from litmus_worker.main import _mixing_from_activity, _parse_number
from litmus_worker.rundata import RunData

T0 = datetime(2026, 10, 25, 9, 0, tzinfo=timezone.utc)


def seedling_protocol() -> dict:
    return build_protocol(SetupOut(
        name="Seedling growth under LED", description="Weigh and measure seedlings after 7 days.",
        result="measurement", result_measurement="mass_g",
        measurements=[
            MeasurementOut(key="mass_g", label="Seedling mass", unit="g", type="number", read_from="camera",
                           look_for="digital scale display", role="outcome", agg="mean"),
            MeasurementOut(key="height_cm", label="Height", unit="cm", type="number", read_from="either",
                           look_for="ruler next to the seedling", role="observation"),
            MeasurementOut(key="light", label="Light condition", type="text", read_from="speech",
                           look_for="researcher says it", role="condition"),
        ],
        steps=[StepOut(title="Tare the scale"), StepOut(title="Weigh each seedling"), StepOut(title="Measure height")],
    ))


def run_with(label: str, role: str, values: list[tuple[str, object]]) -> RunData:
    rid = uuid.uuid4()
    events = [{"id": uuid.uuid4(), "seq": 1, "t": T0, "kind": "run_started", "provenance": "measured", "payload": {}}]
    for i, (key, value) in enumerate(values, 2):
        events.append({"id": uuid.uuid4(), "seq": i, "t": T0 + timedelta(seconds=10 * i), "kind": "measurement",
                       "provenance": "inferred", "frame_ids": [uuid.uuid4()], "payload": {"key": key, "value": value}})
    return RunData(run={"id": rid, "label": label, "role": role, "status": "complete", "started_at": T0, "metadata": {}},
                   events=events, readings={})


def test_protocol_is_built_from_declared_measurements():
    p = seedling_protocol()
    assert p["result"] == {**p["result"], "kind": "measurement", "measurement": "mass_g", "unit": "g"}
    assert "flip" not in p and p["change"] is None
    keys = {v["key"] for v in p["variables"]}
    assert {"height_cm", "light", "temp_c", "step_order"} <= keys
    assert "start_color" not in keys and "mix_active_s" not in keys  # nothing about color or mixing in this lab
    assert next(v for v in p["variables"] if v["key"] == "light")["type"] == "categorical"


def test_outcome_aggregates_readings_and_diff_compares_them():
    p = seedling_protocol()
    refs = [run_with(f"Reference {i}", "reference", [("mass_g", m), ("light", "white")]) for i, m in enumerate((1.0, 1.1, 0.9), 1)]
    control = run_with("Control", "control", [("mass_g", 1.0), ("mass_g", 1.2), ("light", "white")])
    cand = run_with("Blue LED", "candidate", [("mass_g", 2.0), ("mass_g", 2.2), ("light", "blue")])
    d = diff(p, cand, [control], refs)
    assert d["result"]["candidate"]["value"] == 2.1 and d["result"]["status"] == NOTABLE
    assert "light" in d["notable"]
    assert "temp_c" in d["missing_evidence"]  # no thermometer: shown as not measured, never filled in


def test_dataset_rows_keep_provenance_and_evidence():
    p = seedling_protocol()
    rd = run_with("Run 1", "reference", [("mass_g", 1.5), ("height_cm", 4.2), ("light", "white")])
    cols = dataset.columns(p)
    assert cols[0]["key"] == "mass_g" and cols[0].get("result")
    row = dataset.row(rd, p, cols)
    assert row["cells"]["mass_g"]["value"] == 1.5 and row["cells"]["mass_g"]["provenance"] == "inferred"
    assert row["cells"]["mass_g"]["evidence_ids"][0].startswith("evt:")
    csv_text = dataset.to_csv({"columns": cols, "rows": [row]})
    assert "Seedling mass (g)" in csv_text.splitlines()[0] and "1.5" in csv_text


def test_numbers_are_parsed_exactly_as_shown():
    assert _parse_number("2.31 g") == 2.31
    assert _parse_number("1,204") == 1204
    assert _parse_number("-0.5") == -0.5
    assert _parse_number("cloudy") is None


def test_mixing_span_comes_from_frame_timestamps():
    frames = [{"id": i, "t": T0 + timedelta(seconds=2 * i)} for i in range(5)]
    [mix] = _mixing_from_activity(frames, ["idle", "mixing", "mixing", "idle", "nobody"])
    assert mix["payload"]["duration_s"] == 4.0 and mix["provenance"] == "inferred"
    assert _mixing_from_activity(frames, ["idle"]) == []  # labels that don't line up with frames are ignored
