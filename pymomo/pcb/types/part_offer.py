#partoffer.py
from pymomo.utilities.formatting import indent_block

def convert(arg, **kwargs):
	if isinstance(arg, PartOffer):
		return arg

	if not isinstance(arg, dict):
		raise ValueError("conversion to part_offer from anything other than dict not supported")

	req = ['seller', 'moq', 'packaging', 'breaks', 'stock_quantity']
	for r in req:
		if r not in arg:
			raise ValueError('invalid dictionary used to initialize part_offer')

	return PartOffer(arg['seller'], arg['packaging'], arg['breaks'], arg['stock_quantity'], arg['moq'])

def default_formatter(arg, **kwargs):
	return str(arg)

class PartOffer:
	def __init__(self, seller, packaging, breaks, stock, moq):
		self.seller = seller
		self.packaging = packaging
		self.invalid = False

		self.breaks = breaks
		self.stock_quantity = stock
		
		if moq is not None:
			self.moq = moq
		elif len(self.breaks.breaks) > 0:
			self.moq = self.breaks.breaks[0][0]
		else:
			self.moq = None

	def best_price(self, quantity):
		if self.invalid:
			return None

		return self.breaks.unit_price(quantity)

	def __str__(self):
		res = "Seller: %s\n  Packaging: %s\n  Stock: %d\n  Minimum Order: %s" % (self.seller, self.packaging, self.stock_quantity, str(self.moq))
		breakstr = str(self.breaks)
		if breakstr != "":
			res += "\n  Breaks\n"
			res += indent_block(breakstr, 4)

		return res
