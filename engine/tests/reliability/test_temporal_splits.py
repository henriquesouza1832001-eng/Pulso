from datetime import datetime, timedelta, timezone

import pytest

from pulso_engine.validation.temporal import final_holdout, walk_forward_splits


def times(n: int):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [start + timedelta(hours=index) for index in range(n)]


def test_walk_forward_keeps_train_calibration_and_test_strictly_in_time_order():
    splits = walk_forward_splits(times(20), train_size=8, calibration_size=4, test_size=3, step=3)
    assert len(splits) == 2
    for split in splits:
        assert split.train[1] == split.calibration[0]
        assert split.calibration[1] == split.test[0]
        assert split.train[1] <= split.test[0]


def test_final_holdout_is_the_untouched_tail_of_the_dataset():
    values = times(10)
    assert final_holdout(values, holdout_size=3) == (7, 10)


@pytest.mark.parametrize("bad", [times(3)[::-1], [datetime(2026, 1, 1, tzinfo=timezone.utc)] * 3, [datetime(2026, 1, 1)] * 3])
def test_splits_reject_unordered_duplicate_or_naive_timestamps(bad):
    with pytest.raises(ValueError):
        walk_forward_splits(bad, train_size=1, calibration_size=1, test_size=1)


def test_splits_and_holdout_reject_invalid_sizes():
    with pytest.raises(ValueError):
        walk_forward_splits(times(5), train_size=2, calibration_size=1, test_size=1, step=0)
    with pytest.raises(ValueError):
        final_holdout(times(5), holdout_size=5)
