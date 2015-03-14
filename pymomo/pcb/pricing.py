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
			return [self._canonicalize_name(s)]

		if s is None:
			return []

		return map(lambda x: self._canonicalize_name(x), s)

	def _canonicalize_name(self, name):
		"""
		Given a name, like a distributor's name, convert it to
		lowercase and remove all spaces,_ or - characters 
		"""

		if name is None:
			return "None"

		return name.lower().replace(' ', '').replace('-', '').replace('_', '')

	def validate(self, offer, quantity):
		if offer.invalid:
			return False

		if offer.moq is not None and quantity < offer.moq:
			return False

		if self._canonicalize_name(offer.seller) in self.invalid_sellers:
			return False

		if self._canonicalize_name(offer.packaging) in self.invalid_packages:
			return False

		if len(self.valid_sellers)>0 and self._canonicalize_name(offer.seller) not in self.valid_sellers:
			return False

		if len(self.valid_packages)>0 and self._canonicalize_name(offer.packaging) not in self.valid_packages:
			return False

		if self.in_stock and quantity > offer.stock_quantity:
			return False

		return True