from datetime import datetime, timezone

from pulso_engine.validation.replay import ReplayClock, ReplayDataset, ReplayItem


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 3, hour, minute, tzinfo=timezone.utc)


def test_future_data_is_hidden_at_the_replay_cutoff():
    dataset = ReplayDataset("flood", [
        ReplayItem("first-signal", event_time=at(17), observed_at=at(17)),
        ReplayItem("second-sensor", event_time=at(17, 12), observed_at=at(17, 12)),
        ReplayItem("anomaly", event_time=at(17, 25), observed_at=at(17, 25)),
        ReplayItem("news", event_time=at(17, 40), published_at=at(17, 40)),
        ReplayItem("official-confirmation", event_time=at(18), confirmed_at=at(18)),
    ])
    assert [item.item_id for item in dataset.visible(ReplayClock(at(17, 30)))] == ["first-signal", "second-sensor", "anomaly"]


def test_late_fetch_is_not_visible_when_event_already_happened():
    item = ReplayItem("late", event_time=at(17), published_at=at(17), fetched_at=at(17, 45))
    assert not item.visible_at(ReplayClock(at(17, 30)))
    assert item.visible_at(ReplayClock(at(17, 45)))
