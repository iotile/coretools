
class Package:
	"""
	A pcb component package containing the number of pads and pins in the package
	as well as its name.
	"""

	def __init__(self, element):
		if element.tag != 'package':
			raise TypeError('You must pass an ElementTree element to Package.__init__')

		self.name = element.get('name', default="Unknown Name")

		pads = element.findall('./smd')
		self.num_pads = len(pads)

		pins = element.findall('./pad')
		self.num_pins = len(pins)