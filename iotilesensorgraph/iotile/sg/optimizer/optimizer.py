from toposort import toposort_flatten
from .passes import RemoveCopyLatestPass


class SensorGraphOptimizer(object):
    """An optimizer that runs optimization rules on a sensor graph.

    The optimizer keeps track of which rules are disallowed and not
    run and which rules caused the elimination of which nodes.
    """

    def __init__(self):
        self._known_passes = {}

        # Add in our known optimization passes
        self.add_pass('remove-copy', RemoveCopyLatestPass)

    def add_pass(self, name, opt_pass, before=None, after=None):
        """Add an optimization pass to the optimizer.

        Optimization passes have a name that allows them
        to be enabled or disabled by name.  By default all
        optimization passed are enabled and unordered.  You can
        explicitly specify passes by name that this pass must run
        before or after this passs so that they can be properly
        ordered.

        Args:
            name (str): The name of the optimization pass to allow for
                enabling/disabling it by name
            opt_pass (OptimizationPass): The optimization pass class itself
            before (list(str)): A list of the passes that this pass should
                run before.
            after (list(str)): A list of the passes that this pass should
                run after.
        """

        if before is None:
            before = []
        if after is None:
            after = []

        self._known_passes[name] = (opt_pass, before, after)

    def _order_pases(self, passes):
        """Topologically sort optimization passes.

        This ensures that the resulting passes are run in order
        respecting before/after constraints.

        Args:
            passes (iterable): An iterable of pass names that should
                be included in the optimization passes run.
        """

        passes = set(passes)

        pass_deps = {}

        for opt in passes:
            _, before, after = self._known_passes[opt]

            if opt not in pass_deps:
                pass_deps[opt] = []

            pass_deps[opt].extend([x for x in after])

            # For passes that we are before, we may need to
            # preemptively add them to the list early
            for other in before:
                if other not in passes:
                    continue

                if other not in pass_deps:
                    pass_deps[other] = []

                pass_deps[other].append(opt)

        return toposort_flatten(pass_deps)

    def optimize(self, sensor_graph, model):
        """Optimize a sensor graph by running optimization passes.

        The passes are run one at a time and modify the sensor graph
        for future passes.

        Args:
            sensor_graph (SensorGraph): The graph to be optimized
            model (DeviceModel): The device that we are optimizing
                for, that OptimizationPass objects are free to use
                to guide their optimizations.
        """

        passes = self._order_pases(self._known_passes.keys())

        for opt in passes:
            rerun = True
            while rerun:
                rerun = opt(sensor_graph, model=model)
