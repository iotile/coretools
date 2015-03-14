from pymomo.pcb.bom_matcher import BOMMatcher

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
