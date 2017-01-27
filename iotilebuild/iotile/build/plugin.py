def setup_plugin():
    u = unicode('build')
    v = unicode('iotile.build.build.build,build')
    
    d = unicode('depends')
    dv = unicode('iotile.build.dev,DependencyManager')

    b = unicode('release')
    bv = unicode('iotile.build.release.release,release')

    p = unicode('pull')
    pv = unicode('iotile.build.dev.pull_release,pull')

    return [(u,v), (d,dv), (b, bv), (p,pv)]
