def setup_plugin():
	u = unicode('build')
	v = unicode('iotile.build.build.build,build')
	
	d = unicode('depends')
	dv = unicode('iotile.build.dev,DependencyManager')

	b = unicode('release')
	bv = unicode('iotile.build.release.release,release')

	return [(u,v), (d,dv), (b, bv)]
