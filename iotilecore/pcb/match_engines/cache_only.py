# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotilecore.pcb.bom_matcher import BOMMatcher

class CacheOnlyMatcher (BOMMatcher):
	"""
	Only return matches from the existing cache.

	If a component is not in the cache, do not attempt to match
	it in any way.  This is useful for offline purposes and writing
	unit tests.
	"""


	def __init__(self):
		super(CacheOnlyMatcher, self).__init__()

	def _match(self):
		pass
