import pytest
from iotile.core.exceptions import ArgumentError
from iotile.sg.sim.stop_conditions import TimeBasedStopCondition


def test_time_based_stop():
    """Make sure we can parse and use TimeBasedStopConditions."""

    cond1 = TimeBasedStopCondition.FromString(u'run_time 15 days')
    assert cond1.max_time == 15*24*60*60

    cond1 = TimeBasedStopCondition.FromString('run_time 15 days')
    assert cond1.max_time == 15*24*60*60

    cond1 = TimeBasedStopCondition.FromString(u'run_time 15 hours')
    assert cond1.max_time == 15*60*60

    cond1 = TimeBasedStopCondition.FromString(u'run_time 1 hour')
    assert cond1.max_time == 60*60

    cond1 = TimeBasedStopCondition.FromString(u'run_time 1 minute')
    assert cond1.max_time == 60

    cond1 = TimeBasedStopCondition.FromString(u'run_time 0x10 seconds')
    assert cond1.max_time == 16
    assert not cond1.should_stop(15, 15, None)
    assert cond1.should_stop(17, 17, None)

    with pytest.raises(ArgumentError):
        TimeBasedStopCondition.FromString('run_time random thing')
