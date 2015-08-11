import pint

ureg = pint.UnitRegistry()

class AcousticMaterial:
	"""
	An object representing a material through which sound waves can propogate.
	"""

	def __init__(self, c, impedance=None, density=None):
		"""
		Create an AcousticMaterial from its speed of sound and either
		its density or impedance.  If units are given, those are used,
		otherwise the following standard units are assumed:

		c: speed of sound in m/s
		impedance: acoustic impedance in MRayls
		density: material density in kg/m^3
		"""

		if not hasattr(c, 'magnitude'):
			c *= ureg.meter/ureg.second

		self.c = c

		if density is not None:
			if not hasattr(density, 'magnitude'):
				density *= ureg.kilogram / ureg.meter / ureg.meter/ureg.meter

			if impedance is None:
				impedance = c * density

		self.density = density

		if not hasattr(impedance, 'magnitude'):
			impedance *= ureg.kilogram / ureg.second / ureg.meter / ureg.meter

		self.z = impedance

	def reflection(self, other):
		"""
		Compute the complex amplitude relection coefficient
		"""