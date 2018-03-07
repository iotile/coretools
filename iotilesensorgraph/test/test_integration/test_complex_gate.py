"""Make sure the complex gate sensorgraph works correctly."""

from __future__ import (absolute_import, unicode_literals, print_function)
from iotile.sg.sim import SensorGraphSimulator
from iotile.sg import DataStream


def test_complex_gate_basic(complex_gate, complex_gate_opt):
    """Make sure the sg compiled and optimized."""

    sg, sg_opt = complex_gate, complex_gate_opt

    # Check for regresions in the number of nodes we're able to
    # eliminate
    assert len(sg.nodes) == 40

    for node in sg_opt.nodes:
        print(node)

    assert len(sg_opt.nodes) <= 31


def test_complex_gate_optimization(complex_gate, complex_gate_opt):
    """Make sure the optimized version runs identically to the unoptimized."""

    sg, sg_opt = complex_gate, complex_gate_opt

    sim1 = SensorGraphSimulator(sg)
    sim1.stop_condition("run_time 10 minutes")

    sg.load_constants()
    sim1.record_trace()
    sim1.run()

    sim2 = SensorGraphSimulator(sg_opt)
    sim2.stop_condition("run_time 10 minutes")

    sg_opt.load_constants()
    sim2.record_trace()
    sim2.run()

    assert len(sim1.trace) == 0
    assert len(sim2.trace) == 0

    sim1.step(DataStream.FromString("system input 1034"), 1)
    sim2.step(DataStream.FromString("system input 1034"), 1)

    sim1.run()
    sim2.run()

    print("Unoptimized Output")
    for x in sim1.trace:
        print("%08d %s: %d" % (x.raw_time, DataStream.FromEncoded(x.stream), x.value))

    print("\nOptimized Output")
    for x in sim2.trace:
        print("%08d %s: %d" % (x.raw_time, DataStream.FromEncoded(x.stream), x.value))

    assert len(sim1.trace) == 3
    assert len(sim2.trace) == 3
    assert sim1.trace == sim2.trace


def test_user_tick_optimization(usertick_gate, usertick_gate_opt):
    """Make sure the optimized version runs identically to the unoptimized."""

    sg, sg_opt = usertick_gate, usertick_gate_opt

    for node in sg_opt.nodes:
        print(node)

    sim1 = SensorGraphSimulator(sg)
    sim1.stop_condition("run_time 10 minutes")

    sg.load_constants()
    sim1.record_trace()
    sim1.run()

    sim2 = SensorGraphSimulator(sg_opt)
    sim2.stop_condition("run_time 10 minutes")

    sg_opt.load_constants()
    sim2.record_trace()
    sim2.run()

    assert len(sim1.trace) == 0
    assert len(sim2.trace) == 0

    sim1.step(DataStream.FromString("system input 1034"), 1)
    sim2.step(DataStream.FromString("system input 1034"), 1)

    sim1.run()
    sim2.run()

    print("Unoptimized Output")
    for x in sim1.trace:
        print("%08d %s: %d" % (x.raw_time, DataStream.FromEncoded(x.stream), x.value))

    print("\nOptimized Output")
    for x in sim2.trace:
        print("%08d %s: %d" % (x.raw_time, DataStream.FromEncoded(x.stream), x.value))

    assert len(sim1.trace) == 3
    assert len(sim2.trace) == 3
    assert sim1.trace == sim2.trace
