#prices.py
#An object encapsulating a list of pricebreaks

from decimal import Decimal

class PriceList:
	def __init__(self, octo_pricelist):
		"""
		Create from an octopart PriceList json object
		Assume that we want to work in USD
		"""

		self.breaks = []

		if 'USD' not in octo_pricelist:
			raise ValueError('USD Not in Price Object')

		plist = octo_pricelist['USD']

		for i in xrange(0, len(plist)):
			q,val = plist[i]
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