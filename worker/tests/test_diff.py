import json
import uuid

import pytest

from litmus_worker import fixtures, lifecycle, rundata
from litmus_worker.config import settings
from litmus_worker.diff import diff, map_assumed_cause

PROTOCOL = json.loads((settings.experiments_dir / "vinegar-titration.json").read_text(encoding="utf-8"))


def build(spec) -> rundata.RunData:
    syn = fixtures.generate(spec, PROTOCOL, fps=1, width=64, height=36)
    events = [dict(e, seq=i, run_id=syn.run["id"]) for i, e in enumerate(syn.events)]
    frames = [{"id": f["id"], "t": f["t"], "url": "", "reason": f["reason"]} for f in syn.frames]
    rd = rundata.from_rows(syn.run, events, syn.readings, frames)
    for i, extra in enumerate(lifecycle.detect_flips(None, rd, PROTOCOL)):
        rd.events.append(dict(extra, id=uuid.uuid4(), seq=len(events) + i, run_id=syn.run["id"]))
    rd.events.sort(key=lambda e: e["t"])
    return rd


@pytest.fixture(scope="module")
def runs():
    specs = fixtures.demo_specs()
    return {s.label: build(s) for s in specs}


@pytest.fixture(scope="module")
def result(runs):
    refs = [r for k, r in runs.items() if k.startswith("Reference")]
    return diff(PROTOCOL, runs["Method B"], [runs["Method A"]], refs)


def test_hidden_confound_ranks_first(result):
    top = result["differences"][0]
    assert top["key"] == "water_source" and top["status"] == "notable"
    assert top["candidate"]["value"] == "tap"
    assert top["candidate"]["evidence_ids"], "every difference carries evidence"


def test_result_difference_is_outside_normal_variation(result):
    r = result["result"]
    assert r["status"] == "notable"
    assert r["percent_change"] < -30


def test_assumed_cause_contradicted_by_mixing_measurement(result):
    a = result["assumed_cause"]
    assert set(a["variable_keys"]) == {"mix_inversions", "mix_active_s"}
    assert a["label"] == "contradicted"
    assert any(e.startswith("ser:") for e in a["evidence_ids"]), "contradicted needs a measurement"
    assert "water_source" in a["confounds"]
    assert "time_to_flip_s" not in a["confounds"], "outcomes are never confounds"


def test_unmeasured_variables_are_missing_evidence(result):
    assert "humidity" in result["missing_evidence"]


def test_temperature_within_normal_variation(result):
    temp = next(i for i in result["differences"] if i["key"] == "temp_c")
    assert temp["status"] == "within_normal"
    assert temp["candidate"]["provenance"] == "reported"


def test_follow_up_targets_the_confound(result):
    assert result["follow_up"]["variable_key"] == "water_source"
    assert {o["means"] for o in result["follow_up"]["outcomes"]} == {"explained_by_confound", "supported", "unresolved"}


def test_identical_methods_raise_no_false_alarm(runs):
    refs = [r for k, r in runs.items() if k.startswith("Reference")]
    d = diff(PROTOCOL, runs["Reference 3"], [runs["Reference 1"]], refs)
    conditions = [k for k in d["notable"] if next(i for i in d["differences"] if i["key"] == k)["role"] != "outcome"]
    assert conditions == []
    assert d["result"]["status"] in ("same", "within_normal")


def test_alias_mapping_skips_outcomes():
    assert map_assumed_cause("B was faster because I stirred longer", PROTOCOL) == ["mix_inversions", "mix_active_s"]
    assert map_assumed_cause("the room was hot", PROTOCOL) == ["temp_c"]
