#identifier.py

class PartIdentifier:
	def __init__(self, part=None, digipn=None):

		if digipn is not None:
			self.sku = digipn
			self.mpn = None
			self.manu = None
		else:
			self.sku = part.digipn
			self.mpn = part.mpn
			self.manu = part.manu

	def build_reference(self):
		if self.sku:
			return "__SKU__" + self.sku

		else:
			return "__MPN__" + str(self.mpn)

	def build_query(self):
		if self.sku is not None:
			return {'sku': self.sku, 'reference': self.build_reference()}

		else:
			return {'mpn': self.mpn, 'reference': self.build_reference()}
