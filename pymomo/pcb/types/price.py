#price.py
#An object encapsulating the price of something

from decimal import Decimal

two_places = Decimal('0.01')

def convert(arg, **kwargs):
	if isinstance(arg, Decimal):
		return arg

	return Decimal(arg)

def default_formatter(arg, **kwargs):
	return str(arg.quantize(two_places))
