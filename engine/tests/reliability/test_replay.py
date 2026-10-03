from datetime import datetime, timezone

from pulso_engine.validation.replay import ReplayClock, ReplayDataset, ReplayItem, ReplayRunner
from pulso_engine.validation.scenarios import normal_weekday


UTC = timezone.utc


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 3, hour, minute, tzinfo=UTC)


def test_replay_is_deterministic_and_time_ordered():
    data = ReplayDataset("ordered", [ReplayItem("b", observed_at=at(17, 12)), ReplayItem("a", observed_at=at(17))])
    runner = ReplayRunner(data, ReplayClock(at(16)))
    observe = lambda _clock, items: tuple(item.item_id for item in items)
    assert runner.run(observe) == (("a",), ("a", "b"))
    assert runner.run(observe) == (("a",), ("a", "b"))


def test_clock_cannot_go_backwards():
    clock = ReplayClock(at(17))
    try:
        clock.move_to(at(16))
    except ValueError as error:
        assert "voltar" in str(error)
    else:
        raise AssertionError("o replay aceitou voltar no tempo")


def test_negative_day_has_no_forced_event():
    dataset = normal_weekday()
    visible = dataset.visible(ReplayClock(datetime(2026, 10, 5, 13, tzinfo=UTC)))
    assert dataset.name == "normal_weekday" and len(visible) == 2
    assert all(item.payload["routine"] for item in visible)
