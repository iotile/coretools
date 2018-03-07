"""All-in-one sgf programmatic compilation routine."""

from .parser import SensorGraphFileParser
from .optimizer import SensorGraphOptimizer
from .model import DeviceModel


def compile_sgf(in_path, optimize=True, model=None):
    """Compile and optionally optimize an SGF file.

    Args:
        in_path (str): The input path to the sgf file to compile.
        optimize (bool): Whether to optimize the compiled result,
            defaults to True if not passed.
        model (DeviceModel): Optional device model if we are
            compiling for a nonstandard device.  Normally you should
            leave this blank.

    Returns:
        SensorGraph: The compiled sensorgraph object
    """

    if model is None:
        model = DeviceModel()

    parser = SensorGraphFileParser()
    parser.parse_file(in_path)
    parser.compile(model)

    if optimize:
        opt = SensorGraphOptimizer()
        opt.optimize(parser.sensor_graph, model=model)

    return parser.sensor_graph
