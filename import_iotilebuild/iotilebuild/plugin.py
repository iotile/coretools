def setup_plugin():
	u = unicode('build')
	v = unicode('iotilebuild.build.build,build')
	
	d = unicode('depends')
	dv = unicode('iotilebuild.dev,DependencyManager')

	return [(u,v), (d,dv)]