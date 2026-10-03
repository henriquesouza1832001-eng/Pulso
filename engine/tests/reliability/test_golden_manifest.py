"""O catálogo de casos históricos não pode transformar lacunas em evidência."""
import json
from pathlib import Path


ROOT = Path(__file__).parents[1] / "golden"


def test_golden_manifest_lists_required_event_and_negative_campaigns_without_fake_data():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    assert manifest["schema_version"] == 1
    assert {c["id"] for c in cases if c["kind"] == "event"} == {
        "flood", "blackout", "storm", "fire", "traffic-collapse", "internet-outage", "public-transport-failure",
        "road-block", "airport-disruption",
    }
    assert {c["id"] for c in cases if c["kind"] == "negative"} == {
        "normal-weekday", "normal-weekend", "normal-rush-hour", "normal-rain", "normal-news-burst",
        "normal-social-burst", "normal-football-match", "normal-holiday",
    }
    assert all(c["status"] == "INCOMPLETE" for c in cases)
    assert not any(ROOT.glob("**/timeline.jsonl"))


def test_completed_case_must_have_real_replay_artifacts_before_it_can_be_measured():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        if case["status"] != "COMPLETE":
            continue
        root = ROOT / f"{case['kind']}s" / case["id"]
        assert (root / "metadata.json").is_file()
        assert (root / "timeline.jsonl").is_file()
        assert (root / "expected.json").is_file()
