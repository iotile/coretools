#unit_price.py
#An object encapsulating a list of pricebreaks

from decimal import Decimal, getcontext

def convert(arg, **kwargs):
	if isinstance(arg, UnitPrice):
		return arg

	if isinstance(arg, basestring):
		raise ValueError("Converting to price_list from string is not yet supported")

	return UnitPrice(**arg)

def default_formatter(arg, **kwargs):
	return str(arg)

class UnitPrice:
	def __init__(self, price, offer):
		self.price = price
		self.offer = offer		

	def __str__(self):
		tp = Decimal('0.01')
		pricestr = str(self.price.quantize(tp))
		return "$%s from %s as %s" % (pricestr, self.offer.seller, self.offer.packaging)
