"""Optimizers that can reduce the resources required to run a sensor graph.

Optimizers can eliminate redundant nodes that are provably not needed because
their results are known in advance and have no side effects.  They can also
remove dead code that can never be triggered.
"""

from .optimizer import SensorGraphOptimizer


__all__ = ['SensorGraphOptimizer']
