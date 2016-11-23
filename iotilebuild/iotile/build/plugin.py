def setup_plugin():
	u = unicode('build')
	v = unicode('iotile.build.build.build,build')
	
	d = unicode('depends')
	dv = unicode('iotile.build.dev,DependencyManager')

	return [(u,v), (d,dv)]
