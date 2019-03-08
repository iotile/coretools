"""Make sure the complex gate sensorgraph works correctly."""

from iotile.sg.sim import SensorGraphSimulator
from iotile.sg import DataStream


def test_complex_gate_basic(complex_gate, complex_gate_opt):
    """Make sure the sg compiled and optimized."""

    sg, sg_opt = complex_gate, complex_gate_opt

    # Check for regresions in the number of nodes we're able to
    # eliminate
    assert len(sg.nodes) == 41

    for node in sg_opt.nodes:
        print(node)

    assert len(sg_opt.nodes) <= 32


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

    assert len(sim1.trace) == 4
    assert len(sim2.trace) == 4
    assert sim1.trace == sim2.trace

    #Check that number of trigger streamer commands is same for optimized and unoptimized
    trigger_nodes       = [node for node in complex_gate.nodes if node.func_name == 'trigger_streamer']
    trigger_nodes_opt   = [node for node in complex_gate_opt.nodes if node.func_name == 'trigger_streamer']

    assert len(trigger_nodes) == len(trigger_nodes_opt)

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

    assert len(sim1.trace) == 4
    assert len(sim2.trace) == 4
    assert sim1.trace == sim2.trace
