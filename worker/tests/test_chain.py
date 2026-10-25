import uuid
from datetime import datetime, timedelta, timezone

from litmus_worker import chain


def make_chain(n=5):
    run_id = uuid.uuid4()
    t0 = datetime(2026, 10, 24, 20, 0, tzinfo=timezone.utc)
    prev = chain.GENESIS
    events = []
    for i in range(n):
        ev = {"id": uuid.uuid4(), "run_id": run_id, "seq": i, "t": t0 + timedelta(seconds=i),
              "kind": "quantity_added", "summary": f"Added 0.5 mL base ({i})",
              "payload": {"quantity": "base_ml", "value": 0.5}, "provenance": "reported",
              "confidence": None, "frame_ids": [], "prev_hash": prev}
        ev["hash"] = chain.compute_hash(prev, ev)
        prev = ev["hash"]
        events.append(ev)
    return events


def test_intact_chain_verifies():
    report = chain.verify_events(make_chain())
    assert report["intact"] and report["checked"] == 5


def test_edited_payload_breaks_chain_at_that_commit():
    events = make_chain()
    events[2]["payload"] = {"quantity": "base_ml", "value": 0.4}
    report = chain.verify_events(events)
    assert not report["intact"]
    assert report["broken_at_seq"] == 2


def test_deleted_commit_is_detected():
    events = make_chain()
    del events[1]
    report = chain.verify_events(events)
    assert not report["intact"] and report["broken_at_seq"] == 1


def test_canonical_json_is_key_order_independent():
    a = chain.canonical_json({"b": 1, "a": [1, 2]})
    b = chain.canonical_json({"a": [1, 2], "b": 1})
    assert a == b == '{"a":[1,2],"b":1}'


def test_readings_digest_detects_value_edit():
    t = datetime(2026, 10, 24, tzinfo=timezone.utc)
    rows = [{"time": t, "sensor": "light", "value": 0.8, "unit": "ratio", "provenance": "measured"}]
    edited = [dict(rows[0], value=0.7)]
    assert chain.readings_digest(rows) != chain.readings_digest(edited)
