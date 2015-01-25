#prices.py
#An object encapsulating a list of pricebreaks

from decimal import Decimal

def convert(arg, **kwargs):
	if isinstance(arg, PriceList):
		return arg

	if isinstance(arg, basestring):
		raise ValueError("Converting to price_list from string is not yet supported")

	return PriceList(arg)

def default_formatter(arg, **kwargs):
	return str(arg)

class PriceList:
	def __init__(self, breaks):
		self.breaks = []

		for i in xrange(0, len(breaks)):
			q,val = breaks[i]
			price = Decimal(val)
			self.breaks.append((q, price))

	def unit_price(self, quantity):
		if len(self.breaks) == 0:
			return None

		for i in xrange(0, len(self.breaks)):
			if self.breaks[i][0] > quantity:
				if i == 0:
					return None

				return self.breaks[i-1][1]

		return self.breaks[-1][1]

	def total_price(self, quantity):
		up = self.unit_price(quantity)

		if up is None:
			return None

		return quantity*up

	def __str__(self):
		breaklist = map(lambda x: "%d: %s" % (x[0], x[1]), self.breaks)

		return "\n".join(breaklist)