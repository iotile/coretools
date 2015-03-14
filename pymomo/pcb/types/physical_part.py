#physical_part.py
#An object representing a unique physical circuit part that can be sold by
#zero or more sellers

def convert(arg, **kwargs):
	if isinstance(arg, PhysicalPart):
		return arg

	if not isinstance(arg, dict):
		raise ValueError("conversion to physical_part from anything other than dict not supported")

	req = ['manu', 'mpn']
	for r in req:
		if r not in arg:
			raise ValueError('invalid dictionary used to initialize physical_part')

	desc = None
	if 'desc' in arg:
		desc = arg['desc']

	offers = []
	if 'offers' in arg:
		offers = arg['offers']

	return PhysicalPart(arg['manu'], arg['mpn'], offers, desc=desc)

def default_formatter(arg, **kwargs):
	return str(arg)

class PhysicalPart:
	"""
	A unique physical circuit component that can be purchased from zero or more suppliers.
	This would correspond to a single BOM line on a Bill of Materials for a circuit board.
	"""

	def __init__(self, manu, mpn, offers, desc=None):		
		self.offers = offers
		self.manu = manu
		self.mpn = mpn
		self.desc = desc

	def best_price(self, quantity, requirements):
		valid_offers = filter(lambda x: requirements.validate(x, quantity), self.offers)
		prices = map(lambda x: (x.best_price(quantity), x), valid_offers)		
		valid_prices = filter(lambda x: x[0] is not None, prices)

		sorted_prices = sorted(valid_prices, key=lambda x:x[0])

		if len(sorted_prices) > 0:
			return sorted_prices[0]

		return None

	def __str__(self):
		manu = self.manu
		mpn = self.mpn
		desc = self.desc

		#Make sure we get rid of non-ascii characters in case this 
		#string is printed since it would choke.
		if isinstance(manu, unicode):
			manu = manu.encode('ascii','ignore')
		if isinstance(mpn, unicode):
			mpn = mpn.encode('ascii','ignore')
		if isinstance(desc, unicode):
			desc = desc.encode('ascii','ignore')

		header = "Manufacturer: %s\nMPN: %s" % (manu, mpn)

		if self.desc is not None:
			header += "\nDescription: %s" % desc

		offers = map(str, self.offers)

		if len(offers) > 0:
			offerstr = "\n".join(offers)
			offerstr = "  " + offerstr.replace('\n', '\n  ')
			header += '\nOffers\n'
			header += offerstr

		return header
		