from dependencies import DependenciesDirective

def setup_sphinx(app):
	"""Add custom IOTile directives into Sphinx

	This function is designed to be called from Sphinx's setup(app) function 
	inside of a conf.py file that configures Sphinx for building documenation
	for an IOTile component.

	Args:
		app: Sphinx application instance
	"""

	app.add_directive('dependencies', DependenciesDirective)


