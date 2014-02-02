#partoffer.py
#Class encapsulating an Octopart PartOffer response, exposing the 
#price breaks 

from prices import PriceList
import utilities

class PartOffer:
	def __init__(self, response):
		utilities.assert_class(response, 'PartOffer')

		self.seller_name = response['seller']['name']
		self.seller_uid = response['seller']['uid']
		self.packaging = response['packaging']
		self.invalid = False

		try:
			self.breaks = PriceList(response['prices'])
		except ValueError, e:
			self.breaks = None
			self.invalid = True

		self.in_stock_quant = response['in_stock_quantity']


	def best_price(self, quantity):
		if self.invalid:
			return None

		return self.breaks.unit_price(quantity)