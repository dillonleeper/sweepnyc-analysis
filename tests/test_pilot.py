import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("pilot", Path(__file__).parents[1] / "scripts" / "run_match_pilot.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_paginated_fetch_orders_every_page(monkeypatch):
    calls = []
    def fetch(dataset_id, **kwargs):
        calls.append(kwargs)
        return [{"n": 1}, {"n": 2}] if kwargs["offset"] == 0 else [{"n": 3}]
    monkeypatch.setattr(pilot, "fetch_rows", fetch)
    assert len(pilot.fetch_all("test", where="x", select="y", page_size=2)) == 3
    assert [c["offset"] for c in calls] == [0, 2]
    assert all(c["order"] == ":id" for c in calls)


def test_late_charge_description_is_eligible():
    assert pilot.is_cleanliness_candidate({"charge_10_code_description": "DIRTY SIDEWALK"})


def test_empty_denominator_and_replay(monkeypatch, tmp_path):
    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    monkeypatch.setattr(pilot, "OUTDIR", tmp_path / "results")
    monkeypatch.setattr(pilot, "metadata", lambda _: {})
    monkeypatch.setattr(pilot, "fetch_all", lambda *args, **kwargs: [])
    monkeypatch.setattr(pilot.sys, "argv", ["pilot"])
    assert pilot.main() == 0
    summary = json.loads((pilot.OUTDIR / "summary.json").read_text())
    assert summary["confident_match_rate"] is None
    assert summary["passes_threshold"] is None
    assert summary["status"] == "no_eligible_records"
    monkeypatch.setattr(pilot.sys, "argv", ["pilot", "--replay"])
    monkeypatch.setattr(pilot, "fetch_all", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called")))
    assert pilot.main() == 0
