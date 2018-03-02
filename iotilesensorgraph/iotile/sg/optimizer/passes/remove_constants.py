"""Remove unnecessary constants."""

import logging
from iotile.sg import DataStream


class RemoveConstantsPass(object):
    """Run the remove constants optimization pass.

    Sometimes we remove nodes that would otherwise have a constant
    input and thus there are constants remaining in the sensor_graph
    added via `add_constant` that no longer exist in the underlying
    graph structure.  This optimization pass prunes those constants
    out.

    It is important because setting a nonexistent constant in some
    embedded sensorgraph engines is not allowed since storage for
    constant streams is entirely contained within the nodes that
    use them for inputs.

    Args:
        sensor_graph (SensorGraph): The sensor graph to run
            the optimization pass on
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def run(self, sensor_graph, model):
        inuse_constants = set()

        for node, _inputs, _outputs in sensor_graph.iterate_bfs():
            for input_walker, _trigger in node.inputs:
                if input_walker.selector is None:
                    continue

                if input_walker.selector.match_type == DataStream.ConstantType:
                    inuse_constants.add(input_walker.selector.as_stream())

        all_constants = set(sensor_graph.constant_database.keys())

        to_remove = all_constants - inuse_constants
        self.logger.debug("RemoveConstantsPass removing %d unused constants", len(to_remove))

        for val in to_remove:
            del sensor_graph.constant_database[val]
