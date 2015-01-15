#pricing.py
#An object to define options for which part offers are valid

class OfferRequirements:
	"""
	A simple class to validate whether a price offer object is valid based on
	who offers it, what packaging it comes in and whether it's in stock.
	"""

	def __init__(self, valid_sellers=None, invalid_sellers=[], 
				valid_packages=None, invalid_packages=[], in_stock=True):
		self.valid_sellers = set(self._wrap_single(valid_sellers))
		self.invalid_sellers = set(self._wrap_single(invalid_sellers))
		self.valid_packages = set(self._wrap_single(valid_packages))
		self.invalid_packages = set(self._wrap_single(invalid_packages))
		self.in_stock = in_stock

	def _wrap_single(self, s):
		if (isinstance(s, basestring)):
			return [s]

		if s is None:
			return []

		return s

	def validate(self, offer, quantity):
		if offer.invalid:
			return False

		if offer.seller_name in self.invalid_sellers:
			return False

		if offer.packaging in self.invalid_packages:
			return False

		if len(self.valid_sellers)>0 and offer.seller_name not in self.valid_sellers:
			return False

		if len(self.valid_packages)>0 and offer.packaging not in self.valid_packages:
			return False

		if self.in_stock and quantity > offer.in_stock_quant:
			return False

		return True