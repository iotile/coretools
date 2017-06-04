"""Remove unnecessary nodes with the copy_latest_a function.

These nodes are only necessary if there are not enough output links
on the input node to accomodate all outputs or if there is a 
triggering condition on an input other than intput A that triggers
the node to copy.
"""


class RemoveCopyLatestPass(object):
	"""Run the remove copy latest optimization pass.

	Args:
		sensor_graph (SensorGraph): The sensor graph to run
			the optimization pass on
	"""

	def __init__(self, sensor_graph):
		pass